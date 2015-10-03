import time
import json
import unittest
import storjcore
from time import mktime
from datetime import datetime
from datetime import timedelta
from dataserv.app import db, app
from btctxstore import BtcTxStore
from email.utils import formatdate
from dataserv.Farmer import sha256
from dataserv.Farmer import Farmer


class FarmerTest(unittest.TestCase):

    def setUp(self):
        app.config["SKIP_AUTHENTICATION"] = True  # monkey patch
        app.config["DISABLE_CACHING"] = True

        self.btctxstore = BtcTxStore()
        self.bad_addr = 'notvalidaddress'

        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_repr(self):
        farmer = Farmer('191GVvAaTRxLmz3rW3nU5jAV1rF186VxQc')
        ans = "<Farmer BTC Address: '191GVvAaTRxLmz3rW3nU5jAV1rF186VxQc'>"
        self.assertEqual(repr(farmer), ans)

    def test_sha256(self):
        an = 'c059c8035bbd74aa81f4c787c39390b57b974ec9af25a7248c46a3ebfe0f9dc8'
        self.assertEqual(sha256("storj"), an)
        self.assertNotEqual(sha256("not storj"), an)

    def test_register(self):
        # test success
        btc_addr = self.btctxstore.get_address(self.btctxstore.get_key(
                                        self.btctxstore.create_wallet()))
        farmer1 = Farmer(btc_addr)
        self.assertFalse(farmer1.exists())
        farmer1.register()
        self.assertTrue(farmer1.exists())

        # test duplicate error
        self.assertRaises(LookupError, farmer1.register)

        def callback_a():
            Farmer(self.bad_addr)
        self.assertRaises(ValueError, callback_a)

    def test_ping(self):
        btc_addr = self.btctxstore.get_address(self.btctxstore.get_key(
                                        self.btctxstore.create_wallet()))
        farmer = Farmer(btc_addr)

        # test ping before registration
        self.assertRaises(LookupError, farmer.ping)

        # register farmer
        farmer.register()

        # get register time, and make sure the ping work
        register_time = farmer.last_seen
        # ping faster than max_ping would be ignored
        time.sleep(app.config["MAX_PING"] + 1)
        farmer.ping()  # update last seen
        ping_time = farmer.last_seen
        self.assertTrue(register_time < ping_time)

    def test_ping_time_limit(self):
        btc_addr = self.btctxstore.get_address(self.btctxstore.get_key(
                                        self.btctxstore.create_wallet()))
        farmer = Farmer(btc_addr)
        farmer.register()

        register_time = farmer.last_seen
        time.sleep(2)
        farmer.ping()

        # should still be around 0
        delta_seconds = int((farmer.last_seen - register_time).seconds)
        self.assertEqual(delta_seconds, 0)

    def test_height(self):
        btc_addr = self.btctxstore.get_address(self.btctxstore.get_key(
                                        self.btctxstore.create_wallet()))
        farmer = Farmer(btc_addr)
        farmer.register()

        # set height and check function output
        self.assertEqual(farmer.height, 0)
        self.assertEqual(farmer.set_height(5), 5)
        self.assertEqual(farmer.height, 5)

        # check the db object as well
        farmer2 = farmer.lookup()
        self.assertEqual(farmer2.height, 5)

    def test_audit(self):
        btc_addr = self.btctxstore.get_address(self.btctxstore.get_key(
                                        self.btctxstore.create_wallet()))
        farmer = Farmer(btc_addr)

        # test audit before registration
        self.assertRaises(LookupError, farmer.audit)

        # register farmer
        farmer.register()

        # get register time, and make sure the ping work
        register_time = farmer.last_seen
        # ping faster than max_ping would be ignored
        time.sleep(app.config["MAX_PING"] + 1)
        farmer.audit()
        ping_time = farmer.last_seen
        self.assertTrue(register_time < ping_time)

    def test_to_json(self):
        btc_addr = self.btctxstore.get_address(self.btctxstore.get_key(
                                        self.btctxstore.create_wallet()))
        farmer = Farmer(btc_addr)
        farmer.register()

        farmer.ping()
        farmer.set_height(50)

        test_json = {
            "height": 50,
            "btc_addr": btc_addr,
            'payout_addr': btc_addr,
            "last_seen": 0,
            "uptime": 100
        }
        call_payload = json.loads(farmer.to_json())
        self.assertEqual(test_json, call_payload)


class FarmerAuthenticationTest(unittest.TestCase):

    def setUp(self):
        app.config["SKIP_AUTHENTICATION"] = False  # monkey patch
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_authentication_success(self):
        blockchain = BtcTxStore()
        wif = blockchain.create_key()
        address = blockchain.get_address(wif)
        farmer = Farmer(address)

        header_date = formatdate(timeval=mktime(datetime.now().timetuple()),
                                 localtime=True, usegmt=True)
        message = farmer.get_server_address() + " " + header_date
        header_authorization = blockchain.sign_unicode(wif, message)
        headers = {"Date": header_date, "Authorization": header_authorization}
        self.assertTrue(farmer.authenticate(headers))

    def test_authentication_timeout_success(self):
        blockchain = BtcTxStore()
        wif = blockchain.create_key()
        address = blockchain.get_address(wif)
        farmer = Farmer(address)

        timeout = farmer.get_server_authentication_timeout() - 5

        date = datetime.now() - timedelta(seconds=timeout)
        header_date = formatdate(timeval=mktime(date.timetuple()),
                                 localtime=True, usegmt=True)
        message = farmer.get_server_address() + " " + header_date
        header_authorization = blockchain.sign_unicode(wif, message)
        headers = {"Date": header_date, "Authorization": header_authorization}
        self.assertTrue(farmer.authenticate(headers))

    def test_authentication_timeout_future_success(self):
        blockchain = BtcTxStore()
        wif = blockchain.create_key()
        address = blockchain.get_address(wif)
        farmer = Farmer(address)

        timeout = farmer.get_server_authentication_timeout() - 5

        date = datetime.now() + timedelta(seconds=timeout)
        header_date = formatdate(timeval=mktime(date.timetuple()),
                                 localtime=True, usegmt=True)
        message = farmer.get_server_address() + " " + header_date
        header_authorization = blockchain.sign_unicode(wif, message)
        headers = {"Date": header_date, "Authorization": header_authorization}
        self.assertTrue(farmer.authenticate(headers))

    def test_authentication_no_date(self):
        def callback():
            blockchain = BtcTxStore()
            wif = blockchain.create_key()
            address = blockchain.get_address(wif)
            farmer = Farmer(address)

            header_date = formatdate(timeval=mktime(datetime.now().timetuple())
                                     , localtime=True, usegmt=True)
            message = farmer.get_server_address() + " " + header_date
            header_authorization = blockchain.sign_unicode(wif, message)
            headers = {"Date": None, "Authorization": header_authorization}
            farmer.authenticate(headers)
        self.assertRaises(storjcore.auth.AuthError, callback)

    def test_authentication_timeout(self):
        def callback():
            blockchain = BtcTxStore()
            wif = blockchain.create_key()
            address = blockchain.get_address(wif)
            farmer = Farmer(address)

            timeout = farmer.get_server_authentication_timeout()

            date = datetime.now() - timedelta(seconds=timeout)
            header_date = formatdate(timeval=mktime(date.timetuple()),
                                     localtime=True, usegmt=True)
            message = farmer.get_server_address() + " " + header_date
            header_authorization = blockchain.sign_unicode(wif, message)
            headers = {"Date": header_date,
                       "Authorization": header_authorization}
            farmer.authenticate(headers)
        self.assertRaises(storjcore.auth.AuthError, callback)

    def test_authentication_day_timeout(self):
        def callback():
            blockchain = BtcTxStore()
            wif = blockchain.create_key()
            address = blockchain.get_address(wif)
            farmer = Farmer(address)

            date = datetime.now() - timedelta(days=1)
            header_date = formatdate(timeval=mktime(date.timetuple()),
                                     localtime=True, usegmt=True)
            message = farmer.get_server_address() + " " + header_date
            header_authorization = blockchain.sign_unicode(wif, message)
            headers = {"Date": header_date,
                       "Authorization": header_authorization}
            farmer.authenticate(headers)
        self.assertRaises(storjcore.auth.AuthError, callback)

    # TODO test incorrect address

    def test_authentication_bad_sig(self):
        def callback():
            blockchain = BtcTxStore()
            wif = blockchain.create_key()
            address = blockchain.get_address(wif)
            farmer = Farmer(address)

            header_date = formatdate(timeval=mktime(datetime.now().timetuple())
                                     , localtime=True, usegmt=True)
            header_authorization = blockchain.sign_unicode(wif, "lalala-wrong")
            headers = {"Date": header_date,
                       "Authorization": header_authorization}
            farmer.authenticate(headers)
        self.assertRaises(storjcore.auth.AuthError, callback)

class FarmerUpTime(unittest.TestCase):

    def setUp(self):
        app.config["SKIP_AUTHENTICATION"] = True  # monkey patch
        app.config["DISABLE_CACHING"] = True

        self.btctxstore = BtcTxStore()

        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_register(self):
        btc_addr = self.btctxstore.get_address(self.btctxstore.get_key(
                                        self.btctxstore.create_wallet()))
        farmer = Farmer(btc_addr)
        farmer.register()

        test_json = {
            "height": 0,
            "btc_addr": btc_addr,
            'payout_addr': btc_addr,
            "last_seen": 0,
            "uptime": 100
        }
        call_payload = json.loads(farmer.to_json())
        call_payload["uptime"] = round(call_payload["uptime"])
        self.assertEqual(test_json, call_payload)

        # reg_time = max online time -> 100% uptime
        delta = timedelta(minutes=app.config["ONLINE_TIME"])
        farmer.last_seen = datetime.utcnow() - delta
        farmer.reg_time = datetime.utcnow() - delta

        test_json = {
            "height": 0,
            "btc_addr": btc_addr,
            'payout_addr': btc_addr,
            "last_seen": delta.seconds,
            "uptime": 100
        }
        call_payload = json.loads(farmer.to_json())
        call_payload["uptime"] = round(call_payload["uptime"])
        self.assertEqual(test_json, call_payload)

        # reg_time = 2 * max online time -> 50% uptime
        delta = timedelta(minutes=(2*app.config["ONLINE_TIME"]))
        farmer.last_seen = datetime.utcnow() - delta
        farmer.reg_time = datetime.utcnow() - delta
        farmer.ping()

        test_json = {
            "height": 0,
            "btc_addr": btc_addr,
            'payout_addr': btc_addr,
            "last_seen": 0,
            "uptime": 50
        }
        call_payload = json.loads(farmer.to_json())
        call_payload["uptime"] = round(call_payload["uptime"])
        self.assertEqual(test_json, call_payload)

    def test_ping_100(self):
        btc_addr = self.btctxstore.get_address(self.btctxstore.get_key(
                                        self.btctxstore.create_wallet()))
        farmer = Farmer(btc_addr)
        farmer.register()
        
        # lastest ping for 100%
        delta = timedelta(minutes=app.config["ONLINE_TIME"])
        farmer.last_seen = datetime.utcnow() - delta
        farmer.reg_time = datetime.utcnow() - delta
        farmer.ping()

        test_json = {
            "height": 0,
            "btc_addr": btc_addr,
            'payout_addr': btc_addr,
            "last_seen": 0,
            "uptime": 100
        }
        call_payload = json.loads(farmer.to_json())
        call_payload["uptime"] = round(call_payload["uptime"])
        self.assertEqual(test_json, call_payload)

    def test_ping_50(self):
        btc_addr = self.btctxstore.get_address(self.btctxstore.get_key(
                                        self.btctxstore.create_wallet()))
        farmer = Farmer(btc_addr)
        farmer.register()
        
        # lastest ping for 100%
        delta = timedelta(minutes=(2*app.config["ONLINE_TIME"]))
        farmer.last_seen = datetime.utcnow() - delta
        farmer.reg_time = datetime.utcnow() - delta
        farmer.ping()

        test_json = {
            "height": 0,
            "btc_addr": btc_addr,
            'payout_addr': btc_addr,
            "last_seen": 0,
            "uptime": 50
        }
        call_payload = json.loads(farmer.to_json())
        call_payload["uptime"] = round(call_payload["uptime"])
        self.assertEqual(test_json, call_payload)

    def test_ping_25(self):
        btc_addr = self.btctxstore.get_address(self.btctxstore.get_key(
                                        self.btctxstore.create_wallet()))
        farmer = Farmer(btc_addr)
        farmer.register()
        
        # ping to late -> 50%
        delta = timedelta(minutes=(4*app.config["ONLINE_TIME"]))
        farmer.last_seen = datetime.utcnow() - delta
        farmer.reg_time = datetime.utcnow() - delta
        farmer.ping()

        test_json = {
            "height": 0,
            "btc_addr": btc_addr,
            'payout_addr': btc_addr,
            "last_seen": 0,
            "uptime": 25
        }
        call_payload = json.loads(farmer.to_json())
        call_payload["uptime"] = round(call_payload["uptime"])
        self.assertEqual(test_json, call_payload)

    def test_ping_days(self):
        btc_addr = self.btctxstore.get_address(self.btctxstore.get_key(
                                        self.btctxstore.create_wallet()))
        farmer = Farmer(btc_addr)
        farmer.register()
        
        # ping to late -> 50%
        delta = timedelta(days=2)
        farmer.last_seen = datetime.utcnow() - delta
        farmer.reg_time = datetime.utcnow() - delta
        farmer.uptime = 86401 # 1 / 2 days farmer was online
        farmer.ping()

        test_json = {
            "height": 0,
            "btc_addr": btc_addr,
            'payout_addr': btc_addr,
            "last_seen": 0,
            "uptime": 50
        }
        call_payload = json.loads(farmer.to_json())
        call_payload["uptime"] = round(call_payload["uptime"])
        self.assertEqual(test_json, call_payload)

    def test_height_100(self):
        btc_addr = self.btctxstore.get_address(self.btctxstore.get_key(
                                        self.btctxstore.create_wallet()))
        farmer = Farmer(btc_addr)
        farmer.register()

        # lastest ping for 100%
        delta = timedelta(minutes=app.config["ONLINE_TIME"])
        farmer.last_seen = datetime.utcnow() - delta
        farmer.reg_time = datetime.utcnow() - delta
        farmer.set_height(100)

        test_json = {
            "height": 100,
            "btc_addr": btc_addr,
            'payout_addr': btc_addr,
            "last_seen": 0,
            "uptime": 100
        }
        call_payload = json.loads(farmer.to_json())
        call_payload["uptime"] = round(call_payload["uptime"])
        self.assertEqual(test_json, call_payload)

    def test_height_50(self):
        btc_addr = self.btctxstore.get_address(self.btctxstore.get_key(
                                        self.btctxstore.create_wallet()))
        farmer = Farmer(btc_addr)
        farmer.register()

        # lastest ping for 100%
        delta = timedelta(minutes=(2*app.config["ONLINE_TIME"]))
        farmer.last_seen = datetime.utcnow() - delta
        farmer.reg_time = datetime.utcnow() - delta
        farmer.set_height(50)

        test_json = {
            "height": 50,
            "btc_addr": btc_addr,
            'payout_addr': btc_addr,
            "last_seen": 0,
            "uptime": 50
        }
        call_payload = json.loads(farmer.to_json())
        call_payload["uptime"] = round(call_payload["uptime"])
        self.assertEqual(test_json, call_payload)

    def test_height_25(self):
        btc_addr = self.btctxstore.get_address(self.btctxstore.get_key(
                                        self.btctxstore.create_wallet()))
        farmer = Farmer(btc_addr)
        farmer.register()

        #ping to late -> 50%
        delta = timedelta(minutes=(4*app.config["ONLINE_TIME"]))
        farmer.last_seen = datetime.utcnow() - delta
        farmer.reg_time = datetime.utcnow() - delta
        farmer.set_height(25)

        test_json = {
            "height": 25,
            "btc_addr": btc_addr,
            'payout_addr': btc_addr,
            "last_seen": 0,
            "uptime": 25
        }
        call_payload = json.loads(farmer.to_json())
        call_payload["uptime"] = round(call_payload["uptime"])
        self.assertEqual(test_json, call_payload)
