# -*- coding: utf-8 -*-
#
# Copyright P. Christeas <p_christ@hol.gr> 2008-2010
# Copyright 2010 OpenERP SA. (http://www.openerp.com)
#
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
###############################################################################

""" This file contains instance of the http server.


"""
from websrv_lib import *
import netsvc
import errno
import threading
import tools
import posixpath
import urllib
import os
import select
import socket
import xmlrpclib
import logging

from SimpleXMLRPCServer import SimpleXMLRPCDispatcher

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    from ssl import SSLError
except ImportError:
    class SSLError(Exception): pass

class ThreadedHTTPServer(ConnThreadingMixIn, SimpleXMLRPCDispatcher, HTTPServer):
    """ A threaded httpd server, with all the necessary functionality for us.

        It also inherits the xml-rpc dispatcher, so that some xml-rpc functions
        will be available to the request handler
    """
    encoding = None
    allow_none = False
    allow_reuse_address = 1
    _send_traceback_header = False
    i = 0

    def __init__(self, addr, requestHandler, proto='http',
                 logRequests=True, allow_none=False, encoding=None, bind_and_activate=True):
        self.logRequests = logRequests

        SimpleXMLRPCDispatcher.__init__(self, allow_none, encoding)
        HTTPServer.__init__(self, addr, requestHandler)
        
        self.numThreads = 0
        self.proto = proto
        self.__threadno = 0

        # [Bug #1222790] If possible, set close-on-exec flag; if a
        # method spawns a subprocess, the subprocess shouldn't have
        # the listening socket open.
        if fcntl is not None and hasattr(fcntl, 'FD_CLOEXEC'):
            flags = fcntl.fcntl(self.fileno(), fcntl.F_GETFD)
            flags |= fcntl.FD_CLOEXEC
            fcntl.fcntl(self.fileno(), fcntl.F_SETFD, flags)

    def handle_error(self, request, client_address):
        """ Override the error handler
        """
        
        logging.getLogger("init").exception("Server error in request from %s:" % (client_address,))

    def _mark_start(self, thread):
        self.numThreads += 1

    def _mark_end(self, thread):
        self.numThreads -= 1


    def _get_next_name(self):
        self.__threadno += 1
        return 'http-client-%d' % self.__threadno
class HttpLogHandler:
    """ helper class for uniform log handling
    Please define self._logger at each class that is derived from this
    """
    _logger = None
    
    def log_message(self, format, *args):
        self._logger.debug(format % args) # todo: perhaps other level

    def log_error(self, format, *args):
        self._logger.error(format % args)
        
    def log_exception(self, format, *args):
        self._logger.exception(format, *args)

    def log_request(self, code='-', size='-'):
        self._logger.log(netsvc.logging.DEBUG_RPC, '"%s" %s %s',
                        self.requestline, str(code), str(size))
    
class MultiHandler2(HttpLogHandler, MultiHTTPHandler):
    _logger = logging.getLogger('http')


class SecureMultiHandler2(HttpLogHandler, SecureMultiHTTPHandler):
    _logger = logging.getLogger('https')

    def getcert_fnames(self):
        tc = tools.config
        fcert = tc.get('secure_cert_file', 'server.cert')
        fkey = tc.get('secure_pkey_file', 'server.key')
        return (fcert,fkey)

class BaseHttpDaemon(threading.Thread, netsvc.Server):
    _RealProto = '??'

    def __init__(self, interface, port, handler):
        threading.Thread.__init__(self, name='%sDaemon-%d'%(self._RealProto, port))
        netsvc.Server.__init__(self)
        self.__port = port
        self.__interface = interface

        try:
            self.server = ThreadedHTTPServer((interface, port), handler, proto=self._RealProto)
            self.server.vdirs = []
            self.server.logRequests = True
            self.server.timeout = self._busywait_timeout
            logging.getLogger("web-services").info(
                        "starting %s service at %s port %d" %
                        (self._RealProto, interface or '0.0.0.0', port,))
        except Exception, e:
            logging.getLogger("httpd").exception("Error occured when starting the server daemon.")
            raise

    @property
    def socket(self):
        return self.server.socket

    def attach(self, path, gw):
        pass

    def stop(self):
        self.running = False
        self._close_socket()

    def run(self):
        self.running = True
        while self.running:
            try:
                self.server.handle_request()
            except (socket.error, select.error), e:
                if self.running or e.args[0] != errno.EBADF:
                    raise
        return True

    def stats(self):
        res = "%sd: " % self._RealProto + ((self.running and "running") or  "stopped")
        if self.server:
            res += ", %d threads" % (self.server.numThreads,)
        return res

    def append_svc(self, service):
        if not isinstance(service, HTTPDir):
            raise Exception("Wrong class for http service")
        
        pos = len(self.server.vdirs)
        lastpos = pos
        while pos > 0:
            pos -= 1
            if self.server.vdirs[pos].matches(service.path):
                lastpos = pos
            # we won't break here, but search all way to the top, to
            # ensure there is no lesser entry that will shadow the one
            # we are inserting.
        self.server.vdirs.insert(lastpos, service)

    def list_services(self):
        ret = []
        for svc in self.server.vdirs:
            ret.append( ( svc.path, str(svc.handler)) )
        
        return ret
    

class HttpDaemon(BaseHttpDaemon):
    _RealProto = 'HTTP'
    def __init__(self, interface, port):
        super(HttpDaemon, self).__init__(interface, port,
                                         handler=MultiHandler2)

class HttpSDaemon(BaseHttpDaemon):
    _RealProto = 'HTTPS'
    def __init__(self, interface, port):
        try:
            super(HttpSDaemon, self).__init__(interface, port,
                                              handler=SecureMultiHandler2)
        except SSLError, e:
            logging.getLogger('httpsd').exception( \
                        "Can not load the certificate and/or the private key files")
            raise

httpd = None
httpsd = None

def init_servers():
    global httpd, httpsd
    if tools.config.get('xmlrpc'):
        httpd = HttpDaemon(tools.config.get('xmlrpc_interface', ''),
                           int(tools.config.get('xmlrpc_port', 8069)))

    if tools.config.get('xmlrpcs'):
        httpsd = HttpSDaemon(tools.config.get('xmlrpcs_interface', ''),
                             int(tools.config.get('xmlrpcs_port', 8071)))

def reg_http_service(hts, secure_only = False):
    """ Register some handler to httpd.
        hts must be an HTTPDir
    """
    global httpd, httpsd

    if httpd and not secure_only:
        httpd.append_svc(hts)

    if httpsd:
        httpsd.append_svc(hts)

    if (not httpd) and (not httpsd):
        logging.getLogger('httpd').warning("No httpd available to register service %s" % hts.path)
    return

def list_http_services(protocol=None):
    global httpd, httpsd
    if httpd and (protocol == 'http' or protocol == None):
        return httpd.list_services()
    elif httpsd and (protocol == 'https' or protocol == None):
        return httpsd.list_services()
    else:
        raise Exception("Incorrect protocol or no http services")

import SimpleXMLRPCServer
class XMLRPCRequestHandler(netsvc.OpenERPDispatcher,FixSendError,HttpLogHandler,SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):
    rpc_paths = []
    protocol_version = 'HTTP/1.1'
    _logger = logging.getLogger('xmlrpc')

    def _dispatch(self, method, params):
        try:
            service_name = self.path.split("/")[-1]
            return self.dispatch(service_name, method, params)
        except netsvc.OpenERPDispatcherException, e:
            raise xmlrpclib.Fault(tools.exception_to_unicode(e.exception), e.traceback)

    def handle(self):
        pass

    def finish(self):
        pass

    def setup(self):
        self.connection = dummyconn()
        self.rpc_paths = map(lambda s: '/%s' % s, netsvc.ExportService._services.keys())


def init_xmlrpc():
    if tools.config.get('xmlrpc', False):
        # Example of http file serving:
        # reg_http_service(HTTPDir('/test/',HTTPHandler))
        reg_http_service(HTTPDir('/xmlrpc/', XMLRPCRequestHandler))
        logging.getLogger("web-services").info("Registered XML-RPC over HTTP")

    if tools.config.get('xmlrpcs', False) \
            and not tools.config.get('xmlrpc', False):
        # only register at the secure server
        reg_http_service(HTTPDir('/xmlrpc/', XMLRPCRequestHandler), True)
        logging.getLogger("web-services").info("Registered XML-RPC over HTTPS only")

class StaticHTTPHandler(HttpLogHandler, FixSendError, HttpOptions, HTTPHandler):
    _logger = logging.getLogger('httpd')
    _HTTP_OPTIONS = { 'Allow': ['OPTIONS', 'GET', 'HEAD'] }

    def __init__(self,request, client_address, server):
        HTTPHandler.__init__(self,request,client_address,server)
        document_root = tools.config.get('static_http_document_root', False)
        assert document_root, "Please specify static_http_document_root in configuration, or disable static-httpd!"
        self.__basepath = document_root

    def translate_path(self, path):
        """Translate a /-separated PATH to the local filename syntax.

        Components that mean special things to the local file system
        (e.g. drive or directory names) are ignored.  (XXX They should
        probably be diagnosed.)

        """
        # abandon query parameters
        path = path.split('?',1)[0]
        path = path.split('#',1)[0]
        path = posixpath.normpath(urllib.unquote(path))
        words = path.split('/')
        words = filter(None, words)
        path = self.__basepath
        for word in words:
            if word in (os.curdir, os.pardir): continue
            path = os.path.join(path, word)
        return path

def init_static_http():
    if not tools.config.get('static_http_enable', False):
        return
    
    document_root = tools.config.get('static_http_document_root', False)
    assert document_root, "Document root must be specified explicitly to enable static HTTP service (option --static-http-document-root)"
    
    base_path = tools.config.get('static_http_url_prefix', '/')
    
    reg_http_service(HTTPDir(base_path,StaticHTTPHandler))
    
    logging.getLogger("web-services").info("Registered HTTP dir %s for %s" % \
                        (document_root, base_path))

class OerpAuthProxy(AuthProxy):
    """ Require basic authentication..

        This is a copy of the BasicAuthProxy, which however checks/caches the db
        as well.
    """
    def __init__(self,provider):
        AuthProxy.__init__(self,provider)
        self.auth_creds = {}
        self.auth_tries = 0
        self.last_auth = None

    def checkRequest(self,handler,path, db=False):        
        auth_str = handler.headers.get('Authorization',False)
        try:
            if not db:
                db = handler.get_db_from_path(path)
        except Exception:
            if path.startswith('/'):
                path = path[1:]
            psp= path.split('/')
            if len(psp)>1:
                db = psp[0]
            else:
                #FIXME!
                self.provider.log("Wrong path: %s, failing auth" %path)
                raise AuthRejectedExc("Authorization failed. Wrong sub-path.") 
        if self.auth_creds.get(db):
            return True 
        if auth_str and auth_str.startswith('Basic '):
            auth_str=auth_str[len('Basic '):]
            (user,passwd) = base64.decodestring(auth_str).split(':')
            self.provider.log("Found user=\"%s\", passwd=\"***\" for db=\"%s\"" %(user,db))
            acd = self.provider.authenticate(db,user,passwd,handler.client_address)
            if acd != False:
                self.auth_creds[db] = acd
                self.last_auth = db
                return True
        if self.auth_tries > 5:
            self.provider.log("Failing authorization after 5 requests w/o password")
            raise AuthRejectedExc("Authorization failed.")
        self.auth_tries += 1
        raise AuthRequiredExc(atype='Basic', realm=self.provider.realm)

import security
class OpenERPAuthProvider(AuthProvider):
    def __init__(self,realm='OpenERP User'):
        self.realm = realm

    def setupAuth(self, multi, handler):
        if not multi.sec_realms.has_key(self.realm):
            multi.sec_realms[self.realm] = OerpAuthProxy(self)
        handler.auth_proxy = multi.sec_realms[self.realm]

    def authenticate(self, db, user, passwd, client_address):
        try:
            uid = security.login(db,user,passwd)
            if uid is False:
                return False
            return (user, passwd, db, uid)
        except Exception,e:
            logging.getLogger("auth").debug("Fail auth: %s" % e )
            return False

    def log(self, msg, lvl=logging.INFO):
        logging.getLogger("auth").log(lvl,msg)

#eof
