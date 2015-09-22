import json
import hashlib
import storjcore
from datetime import datetime
from sqlalchemy import DateTime
from dataserv.run import db, app
from btctxstore import BtcTxStore


from dataserv.config import logging
logger = logging.getLogger(__name__)
is_btc_address = BtcTxStore().validate_address


def sha256(content):
    """Finds the sha256 hash of the content."""
    content = content.encode('utf-8')
    return hashlib.sha256(content).hexdigest()


class Farmer(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    btc_addr = db.Column(db.String(35), unique=True)
    payout_addr = db.Column(db.String(35))
    height = db.Column(db.Integer, default=0)

    last_seen = db.Column(DateTime, index=True, default=datetime.utcnow)
    reg_time = db.Column(DateTime, default=datetime.utcnow)
    uptime = db.Column(db.Integer, default=0)

    def __init__(self, btc_addr, last_seen=None):
        """
        A farmer is a un-trusted client that provides some disk space
        in exchange for payment. We use this object to keep track of
        farmers connected to this node.

        """
        if not is_btc_address(btc_addr):
            msg = "Invalid BTC Address: {0}".format(btc_addr)
            logger.warning(msg)
            raise ValueError(msg)
        self.btc_addr = btc_addr
        self.last_seen = last_seen

    def __repr__(self):
        return '<Farmer BTC Address: %r>' % self.btc_addr

    @staticmethod
    def get_server_address():
        return app.config["ADDRESS"]

    @staticmethod
    def get_server_authentication_timeout():
        return app.config["AUTHENTICATION_TIMEOUT"]

    def authenticate(self, headers):
        if app.config["SKIP_AUTHENTICATION"]:
            return True

        if not headers.get("Authorization"):
            raise storjcore.auth.AuthError("Authorization header required!")
        if not headers.get("Date"):
            raise storjcore.auth.AuthError("Date header required!")

        btctxstore = BtcTxStore()
        timeout = self.get_server_authentication_timeout()
        recipient_address = self.get_server_address()
        sender_address = self.btc_addr
        return storjcore.auth.verify_headers(btctxstore, headers, timeout,
                                             sender_address, recipient_address)

    def validate(self, registering=False):
        """Make sure this farmer fits the rules for this node."""
        if not is_btc_address(self.payout_addr):
            msg = "Invalid BTC Address: {0}".format(self.payout_addr)
            logger.warning(msg)
            raise ValueError(msg)
        exists = self.exists()
        if exists and registering:
            msg = "Address already registered: {0}".format(self.payout_addr)
            logger.warning(msg)
            raise LookupError(msg)

    def register(self, payout_addr=None):
        """Add the farmer to the database."""
        self.payout_addr = payout_addr if payout_addr else self.btc_addr
        self.validate(registering=True)
        db.session.add(self)
        db.session.commit()

    def exists(self):
        """Check to see if this address is already listed."""
        return Farmer.query.filter(Farmer.btc_addr ==
                                   self.btc_addr).count() > 0

    def lookup(self):
        """Return the Farmer object for the bitcoin address passed."""
        farmer = Farmer.query.filter_by(btc_addr=self.btc_addr).first()
        if not farmer:
            msg = "Address not registered: {0}".format(self.btc_addr)
            logger.warning(msg)
            raise LookupError(msg)
        return farmer

    def ping(self, before_commit_callback=None):
        """
        Keep-alive for the farmer. Validation can take a long time, so
        we just want to know if they are still there.

        """
        ping_time = datetime.utcnow()

        # make sure the farmer is valid
        farmer = self.lookup()
        # find time delta since we last pinged
        delta = ping_time - farmer.last_seen

        # if we are above the time limit, update last seen
        if delta.seconds >= app.config["MAX_PING"]:
            farmer.last_seen = ping_time
            # if the farmer has been online in the last ONLINE_TIME seconds
            # then we can update their uptime statistic
            if delta.seconds <= (app.config["ONLINE_TIME"] * 60):
                farmer.uptime += delta.seconds
            # call to the authentication module
            if before_commit_callback:
                before_commit_callback()
            db.session.commit()

    # TODO: Actually do an audit.
    def audit(self):
        """
        Complete a cryptographic audit of files stored on the farmer. If
        the farmer completes an audit we also update when we last saw them.

        """
        self.ping()

    def set_height(self, height):
        """Set the farmers advertised height."""
        farmer = self.lookup()
        farmer.height = height
        farmer.last_seen = datetime.utcnow()
        db.session.commit()
        return self.height

    def calculate_uptime(self):
        """Calculate uptime from registration date."""
        farmer = self.lookup()
        # time delta from registration
        delta_reg = datetime.utcnow() - farmer.reg_time

        # convert to seconds
        delta_reg = delta_reg.seconds

        # in case registration happened a short bit ago
        if delta_reg == 0:
            delta_reg = 1
        farmer_uptime = farmer.uptime + (app.config["ONLINE_TIME"] * 60)
        uptime = round(farmer_uptime / delta_reg, 3)
        # clip if we completed the audit recently (which sends us over 100%)
        uptime *= 100  # covert from decimal to percentage
        if uptime > 100:
            uptime = 100

        return round(uptime, 3)

    def to_json(self):
        """Object to JSON payload."""
        payload = {
            "btc_addr": self.btc_addr,
            "payout_addr": self.payout_addr,
            "last_seen": (datetime.utcnow() - self.last_seen).seconds,
            "height": self.height,
            "uptime": self.calculate_uptime()
        }
        return json.dumps(payload)
