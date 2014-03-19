# -*- coding: utf-8 -*-
"""
The module :mod:`openerp.tests.common` provides unittest2 test cases and a few
helpers and classes to write tests.

"""
import errno
import json
import logging
import os
import select
import subprocess
import threading
import time
import unittest2
import urllib2
import xmlrpclib
from datetime import datetime, timedelta

import werkzeug

import openerp

_logger = logging.getLogger(__name__)

# The openerp library is supposed already configured.
ADDONS_PATH = openerp.tools.config['addons_path']
HOST = '127.0.0.1'
PORT = openerp.tools.config['xmlrpc_port']
DB = openerp.tools.config['db_name']
# If the database name is not provided on the command-line,
# use the one on the thread (which means if it is provided on
# the command-line, this will break when installing another
# database from XML-RPC).
if not DB and hasattr(threading.current_thread(), 'dbname'):
    DB = threading.current_thread().dbname
# Useless constant, tests are aware of the content of demo data
ADMIN_USER_ID = openerp.SUPERUSER_ID

# Magic session_id, unfortunately we have to serialize access to the cursors to
# serialize requests. We first tried to duplicate the database for each tests
# but this proved too slow. Any idea to improve this is welcome.
HTTP_SESSION = {}

def acquire_test_cursor(session_id):
    if openerp.tools.config['test_enable']:
        cr = HTTP_SESSION.get(session_id)
        if cr:
            cr._test_lock.acquire()
            return cr

def release_test_cursor(cr):
    if openerp.tools.config['test_enable']:
        if hasattr(cr, '_test_lock'):
            cr._test_lock.release()
            return True
    return False

def at_install(flag):
    """ Sets the at-install state of a test, the flag is a boolean specifying
    whether the test should (``True``) or should not (``False``) run during
    module installation.

    By default, tests are run at install.
    """
    def decorator(obj):
        obj.at_install = flag
        return obj
    return decorator
def post_install(flag):
    """ Sets the post-install state of a test. The flag is a boolean
    specifying whether the test should or should not run after a set of
    module installations.

    By default, tests are *not* run after installation.
    """
    def decorator(obj):
        obj.post_install = flag
        return obj
    return decorator

class BaseCase(unittest2.TestCase):
    """
    Subclass of TestCase for common OpenERP-specific code.
    
    This class is abstract and expects self.cr and self.uid to be initialized by subclasses.
    """

    @classmethod
    def cursor(self):
        return openerp.modules.registry.RegistryManager.get(DB).db.cursor()

    @classmethod
    def registry(self, model):
        return openerp.modules.registry.RegistryManager.get(DB)[model]

    @classmethod
    def ref(self, xid):
        """ Returns database ID corresponding to a given identifier.

            :param xid: fully-qualified record identifier, in the form ``module.identifier``
            :raise: ValueError if not found
        """
        assert "." in xid, "this method requires a fully qualified parameter, in the following form: 'module.identifier'"
        module, xid = xid.split('.')
        _, id = self.registry('ir.model.data').get_object_reference(self.cr, self.uid, module, xid)
        return id

    @classmethod
    def browse_ref(self, xid):
        """ Returns a browsable record for the given identifier.

            :param xid: fully-qualified record identifier, in the form ``module.identifier``
            :raise: ValueError if not found
        """
        assert "." in xid, "this method requires a fully qualified parameter, in the following form: 'module.identifier'"
        module, xid = xid.split('.')
        return self.registry('ir.model.data').get_object(self.cr, self.uid, module, xid)


class TransactionCase(BaseCase):
    """
    Subclass of BaseCase with a single transaction, rolled-back at the end of
    each test (method).
    """

    def setUp(self):
        # Store cr and uid in class variables, to allow ref() and browse_ref to be BaseCase @classmethods
        # and still access them
        TransactionCase.cr = self.cursor()
        TransactionCase.uid = openerp.SUPERUSER_ID

    def tearDown(self):
        self.cr.rollback()
        self.cr.close()


class SingleTransactionCase(BaseCase):
    """
    Subclass of BaseCase with a single transaction for the whole class,
    rolled-back after all the tests.
    """

    @classmethod
    def setUpClass(cls):
        cls.cr = cls.cursor()
        cls.uid = openerp.SUPERUSER_ID

    @classmethod
    def tearDownClass(cls):
        cls.cr.rollback()
        cls.cr.close()


class HttpCase(TransactionCase):
    """ Transactionnal HTTP TestCase with url_open and phantomjs helpers.
    """

    def __init__(self, methodName='runTest'):
        super(HttpCase, self).__init__(methodName)
        # v8 api with correct xmlrpc exception handling.
        self.xmlrpc_url = url_8 = 'http://%s:%d/xmlrpc/2/' % (HOST, PORT)
        self.xmlrpc_common = xmlrpclib.ServerProxy(url_8 + 'common')
        self.xmlrpc_db = xmlrpclib.ServerProxy(url_8 + 'db')
        self.xmlrpc_object = xmlrpclib.ServerProxy(url_8 + 'object')

    def setUp(self):
        super(HttpCase, self).setUp()
        # setup a magic session_id that will be rollbacked
        self.session = openerp.http.root.session_store.new()
        self.session_id = self.session.sid
        self.session.db = DB
        openerp.http.root.session_store.save(self.session)
        self.cr._test_lock = threading.RLock()
        HTTP_SESSION[self.session_id] = self.cr

    def tearDown(self):
        del HTTP_SESSION[self.session_id]
        super(HttpCase, self).tearDown()

    def url_open(self, url, data=None, timeout=10):
        opener = urllib2.build_opener()
        opener.addheaders.append(('Cookie', 'session_id=%s' % self.session_id))
        if url.startswith('/'):
            url = "http://localhost:%s%s" % (PORT, url)
        return opener.open(url, data, timeout)

    def phantom_poll(self, phantom, timeout):
        """ Phantomjs Test protocol.

        Use console.log in phantomjs to output test results:

        - for a success: console.log("ok")
        - for an error:  console.log("error")

        Other lines are relayed to the test log.

        """
        t0 = datetime.now()
        td = timedelta(seconds=timeout)
        buf = bytearray()
        while True:
            # timeout
            self.assertLess(datetime.now() - t0, td,
                "PhantomJS tests should take less than %s seconds" % timeout)

            # read a byte
            try:
                ready, _, _ = select.select([phantom.stdout], [], [], 0.5)
            except select.error, e:
                # In Python 2, select.error has no relation to IOError or
                # OSError, and no errno/strerror/filename, only a pair of
                # unnamed arguments (matching errno and strerror)
                err, _ = e.args
                if err == errno.EINTR:
                    continue
                raise

            if ready:
                s = phantom.stdout.read(1)
                if not s:
                    break
                buf.append(s)

            # process lines
            if '\n' in buf:
                line, buf = buf.split('\n', 1)
                line = str(line)

                # relay everything from console.log, even 'ok' or 'error...' lines
                _logger.info("phantomjs: %s", line)

                if line == "ok":
                    break
                if line.startswith("error"):
                    line_ = line[6:]
                    # when error occurs the execution stack may be sent as as JSON
                    try:
                        line_ = json.loads(line_)
                    except ValueError: 
                        pass
                    self.fail(line_ or "phantomjs test failed")

    def phantom_run(self, cmd, timeout):
        _logger.info('phantom_run executing %s', ' '.join(cmd))
        try:
            phantom = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except OSError:
            raise unittest2.SkipTest("PhantomJS not found")
        try:
            self.phantom_poll(phantom, timeout)
        finally:
            # kill phantomjs if phantom.exit() wasn't called in the test
            if phantom.poll() is None:
                phantom.terminate()
            _logger.info("phantom_run execution finished")

    def phantom_jsfile(self, jsfile, timeout=30, **kw):
        options = {
            'timeout' : timeout,
            'port': PORT,
            'db': DB,
            'session_id': self.session_id,
        }
        options.update(kw)
        phantomtest = os.path.join(os.path.dirname(__file__), 'phantomtest.js')
        # phantom.args[0] == phantomtest path
        # phantom.args[1] == options
        cmd = ['phantomjs', jsfile, phantomtest, json.dumps(options)]
        self.phantom_run(cmd, timeout)

    def phantom_js(self, url_path, code, ready="window", login=None, timeout=30, **kw):
        """ Test js code running in the browser
        - optionnally log as 'login'
        - load page given by url_path
        - wait for ready object to be available
        - eval(code) inside the page

        To signal success test do:
        console.log('ok')

        To signal failure do:
        console.log('error')

        If neither are done before timeout test fails.
        """
        options = {
            'port': PORT,
            'db': DB,
            'url_path': url_path,
            'code': code,
            'ready': ready,
            'timeout' : timeout,
            'login' : login,
            'session_id': self.session_id,
        }
        options.update(kw)
        options.setdefault('password', options.get('login'))
        phantomtest = os.path.join(os.path.dirname(__file__), 'phantomtest.js')
        cmd = ['phantomjs', phantomtest, json.dumps(options)]
        self.phantom_run(cmd, timeout)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
