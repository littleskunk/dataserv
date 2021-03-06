#!/usr/bin/env python
# coding: utf-8


from setuptools import setup, find_packages

exec(open('dataserv/version.py').read())  # load __version__
DOWNLOAD_URL = "%(baseurl)s/%(name)s/%(name)s-%(version)s-py2.py3-none-any.whl" % {
    'baseurl': "https://pypi.python.org/packages/3.4/d",
    'name': 'dataserv',
    'version': __version__  # NOQA
}


setup(
    name='dataserv',
    version=__version__,  # NOQA
    description=('Federated server for getting, pushing,'
                 ' and auditing data on untrusted nodes.'),
    long_description=open("README.rst").read(),
    keywords="",
    url='http://storj.io',
    author='Shawn Wilkinson',
    author_email='shawn+dataserv@storj.io',
    license='MIT',
    packages=find_packages(),
    include_package_data = True,
    package_data = {
        "dataserv.migrations": [ "*.*" ],
        "dataserv.migrations.versions": [ "*.*" ],
    },
    download_url=DOWNLOAD_URL,
    test_suite="tests",
    install_requires=open("requirements.txt").readlines(),
    tests_require=open("test_requirements.txt").readlines(),
    zip_safe=False,
    classifiers=[
        # "Development Status :: 1 - Planning",
        # "Development Status :: 2 - Pre-Alpha",
        "Development Status :: 3 - Alpha",
        # "Development Status :: 4 - Beta",
        # "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
