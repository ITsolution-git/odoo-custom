# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 OpenERP s.a. (<http://openerp.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

""" WSGI stuffs (proof of concept for now)

This module offers a WSGI interface to OpenERP.

"""

from wsgiref.simple_server import make_server
from SimpleXMLRPCServer import SimpleXMLRPCDispatcher
import xmlrpclib

import os
import signal
import sys
import time

import openerp
import openerp.tools.config as config

def xmlrpc_return(start_response, service, method, params):
    """ Helper to call a service's method with some params, using a
    wsgi-supplied ``start_response`` callback."""
    # This mimics SimpleXMLRPCDispatcher._marshaled_dispatch() for exception
    # handling.
    try:
        result = openerp.netsvc.dispatch_rpc(service, method, params, None) # TODO auth
        response = xmlrpclib.dumps((result,), methodresponse=1, allow_none=False, encoding=None)
    except openerp.netsvc.OpenERPDispatcherException, e:
        fault = xmlrpclib.Fault(openerp.tools.exception_to_unicode(e.exception), e.traceback)
        response = xmlrpclib.dumps(fault, allow_none=False, encoding=None)
    except:
        exc_type, exc_value, exc_tb = sys.exc_info()
        fault = xmlrpclib.Fault(1, "%s:%s" % (exc_type, exc_value))
        response = xmlrpclib.dumps(fault, allow_none=None, encoding=None)
    start_response("200 OK", [('Content-Type','text/xml'), ('Content-Length', str(len(response)))])
    return [response]

def wsgi_xmlrpc(environ, start_response):
    """ The main OpenERP WSGI handler."""
    if environ['REQUEST_METHOD'] == 'POST' and environ['PATH_INFO'].startswith('/openerp/xmlrpc'):
        length = int(environ['CONTENT_LENGTH'])
        data = environ['wsgi.input'].read(length)

        params, method = xmlrpclib.loads(data)

        path = environ['PATH_INFO'][len('/openerp/xmlrpc'):]
        if path.startswith('/'): path = path[1:]
        if path.endswith('/'): p = path[:-1]
        path = path.split('/')

        # All routes are hard-coded. Need a way to register addons-supplied handlers.

        # No need for a db segment.
        if len(path) == 1:
            service = path[0]

            if service == 'common':
                if method in ('create_database', 'list', 'server_version'):
                    return xmlrpc_return(start_response, 'db', method, params)
                else:
                    return xmlrpc_return(start_response, 'common', method, params)
        # A db segment must be given.
        elif len(path) == 2:
            service, db_name = path
            params = (db_name,) + params

            if service == 'model':
                return xmlrpc_return(start_response, 'object', method, params)
            elif service == 'report':
                return xmlrpc_return(start_response, 'report', method, params)

def legacy_wsgi_xmlrpc(environ, start_response):
    if environ['REQUEST_METHOD'] == 'POST' and environ['PATH_INFO'].startswith('/xmlrpc/'):
        length = int(environ['CONTENT_LENGTH'])
        data = environ['wsgi.input'].read(length)
        path = environ['PATH_INFO'][len('/xmlrpc/'):] # expected to be one of db, object, ...

        params, method = xmlrpclib.loads(data)
        return xmlrpc_return(start_response, path, method, params)

def wsgi_jsonrpc(environ, start_response):
    pass

def wsgi_modules(environ, start_response):
    """ WSGI handler dispatching to addons-provided entry points."""
    pass

# WSGI handlers provided by modules loaded with the --load command-line option.
module_handlers = []

def register_wsgi_handler(handler):
    """ Register a WSGI handler.

    Handlers are tried in the order they are added. We might provide a way to
    register a handler for specific routes later.
    """
    module_handlers.append(handler)

def application(environ, start_response):
    """ WSGI entry point."""

    # Try all handlers until one returns some result (i.e. not None).
    wsgi_handlers = [
        wsgi_xmlrpc,
        wsgi_jsonrpc,
        legacy_wsgi_xmlrpc,
        wsgi_modules,
        ] + module_handlers
    for handler in wsgi_handlers:
        result = handler(environ, start_response)
        if result is None:
            continue
        return result

    # We never returned from the loop. Needs something else than 200 OK.
    response = 'No handler found.\n'
    start_response('200 OK', [('Content-Type', 'text/plain'), ('Content-Length', str(len(response)))])
    return [response]

def serve():
    """ Serve XMLRPC requests via wsgiref's simple_server.

    Blocking, should probably be called in its own process.
    """
    httpd = make_server('localhost', config['xmlrpc_port'], application)
    httpd.serve_forever()

# Master process id, can be used for signaling.
arbiter_pid = None

# Application setup before we can spawn any worker process.
# This is suitable for e.g. gunicorn's on_starting hook.
def on_starting(server):
    global arbiter_pid
    arbiter_pid = os.getpid() # TODO check if this is true even after replacing the executable
    config = openerp.tools.config
    config['addons_path'] = '/home/openerp/repos/addons/trunk-xmlrpc-no-osv-memory' # need a config file
    #openerp.tools.cache = kill_workers_cache
    openerp.netsvc.init_logger()
    openerp.osv.osv.start_object_proxy()
    openerp.service.web_services.start_web_services()

# Install our own signal handler on the master process.
def when_ready(server):
    # Hijack gunicorn's SIGWINCH handling; we can choose another one.
    signal.signal(signal.SIGWINCH, make_winch_handler(server))

# Our signal handler will signal a SGIQUIT to all workers.
def make_winch_handler(server):
    def handle_winch(sig, fram):
        server.kill_workers(signal.SIGQUIT) # This is gunicorn specific.
    return handle_winch

# Kill gracefuly the workers (e.g. because we want to clear their cache).
# This is done by signaling a SIGWINCH to the master process, so it can be
# called by the workers themselves.
def kill_workers():
    try:
        os.kill(arbiter_pid, signal.SIGWINCH)
    except OSError, e:
        if e.errno == errno.ESRCH: # no such pid
            return
        raise            

class kill_workers_cache(openerp.tools.ormcache):
    def clear(self, dbname, *args, **kwargs):
        kill_workers()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
