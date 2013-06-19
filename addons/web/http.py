# -*- coding: utf-8 -*-
#----------------------------------------------------------
# OpenERP Web HTTP layer
#----------------------------------------------------------
import ast
import cgi
import contextlib
import functools
import getpass
import logging
import mimetypes
import os
import pprint
import random
import sys
import tempfile
import threading
import time
import traceback
import urlparse
import uuid
import errno

import babel.core
import simplejson
import werkzeug.contrib.sessions
import werkzeug.datastructures
import werkzeug.exceptions
import werkzeug.utils
import werkzeug.wrappers
import werkzeug.wsgi
import werkzeug.routing as routing
import urllib2

import openerp

import session

import inspect
import functools

_logger = logging.getLogger(__name__)

#----------------------------------------------------------
# RequestHandler
#----------------------------------------------------------
class WebRequest(object):
    """ Parent class for all OpenERP Web request types, mostly deals with
    initialization and setup of the request object (the dispatching itself has
    to be handled by the subclasses)

    :param request: a wrapped werkzeug Request object
    :type request: :class:`werkzeug.wrappers.BaseRequest`

    .. attribute:: httprequest

        the original :class:`werkzeug.wrappers.Request` object provided to the
        request

    .. attribute:: httpsession

        a :class:`~collections.Mapping` holding the HTTP session data for the
        current http session

    .. attribute:: params

        :class:`~collections.Mapping` of request parameters, not generally
        useful as they're provided directly to the handler method as keyword
        arguments

    .. attribute:: session_id

        opaque identifier for the :class:`session.OpenERPSession` instance of
        the current request

    .. attribute:: session

        :class:`~session.OpenERPSession` instance for the current request

    .. attribute:: context

        :class:`~collections.Mapping` of context values for the current request

    .. attribute:: debug

        ``bool``, indicates whether the debug mode is active on the client

    .. attribute:: db

        ``str``, the name of the database linked to the current request. Can be ``None``
        if the current request uses the ``nodb`` authentication.

    .. attribute:: uid

        ``int``, the id of the user related to the current request. Can be ``None``
        if the current request uses the ``nodb`` or the ``noauth`` authenticatoin.
    """
    def __init__(self, httprequest):
        self.httprequest = httprequest
        self.httpresponse = None
        self.httpsession = httprequest.session
        self.db = None
        self.uid = None
        self.func = None
        self.auth_method = None
        self._cr_cm = None
        self._cr = None
        self.func_request_type = None

    def init(self, params):
        self.params = dict(params)
        # OpenERP session setup
        self.session_id = self.params.pop("session_id", None)
        if not self.session_id:
            i0 = self.httprequest.cookies.get("instance0|session_id", None)
            if i0:
                self.session_id = simplejson.loads(urllib2.unquote(i0))
            else:
                self.session_id = uuid.uuid4().hex
        self.session = self.httpsession.get(self.session_id)
        if not self.session:
            self.session = session.OpenERPSession()
            self.httpsession[self.session_id] = self.session

        with set_request(self):
            self.db = (self.session._db or openerp.addons.web.controllers.main.db_monodb()).lower()

        # TODO: remove this
        # set db/uid trackers - they're cleaned up at the WSGI
        # dispatching phase in openerp.service.wsgi_server.application
        if self.session._db:
            threading.current_thread().dbname = self.session._db
        if self.session._uid:
            threading.current_thread().uid = self.session._uid

        self.context = self.params.pop('context', {})
        self.debug = self.params.pop('debug', False) is not False
        # Determine self.lang
        lang = self.params.get('lang', None)
        if lang is None:
            lang = self.context.get('lang')
        if lang is None:
            lang = self.httprequest.cookies.get('lang')
        if lang is None:
            lang = self.httprequest.accept_languages.best
        if not lang:
            lang = 'en_US'
        # tranform 2 letters lang like 'en' into 5 letters like 'en_US'
        lang = babel.core.LOCALE_ALIASES.get(lang, lang)
        # we use _ as seprator where RFC2616 uses '-'
        self.lang = lang.replace('-', '_')

    def _authenticate(self):
        if self.auth_method == "nodb":
            self.db = None
            self.uid = None
        elif self.auth_method == "noauth":
            self.db = (self.session._db or openerp.addons.web.controllers.main.db_monodb()).lower()
            if not self.db:
                raise session.SessionExpiredException("No valid database for request %s" % self.httprequest)
            self.uid = None
        else: # auth
            try:
                self.session.check_security()
            except session.SessionExpiredException, e:
                raise session.SessionExpiredException("Session expired for request %s" % self.httprequest)
            self.db = self.session._db
            self.uid = self.session._uid

    @property
    def registry(self):
        """
        The registry to the database linked to this request. Can be ``None`` if the current request uses the
        ``nodb'' authentication.
        """
        return openerp.modules.registry.RegistryManager.get(self.db) if self.db else None

    @property
    def cr(self):
        """
        The cursor initialized for the current method call. If the current request uses the ``nodb`` authentication
        trying to access this property will raise an exception.
        """
        # some magic to lazy create the cr
        if not self._cr_cm:
            self._cr_cm = self.registry.cursor()
            self._cr = self._cr_cm.__enter__()
        return self._cr

    def _call_function(self, *args, **kwargs):
        self._authenticate()
        try:
            # ugly syntax only to get the __exit__ arguments to pass to self._cr
            request = self
            class with_obj(object):
                def __enter__(self):
                    pass
                def __exit__(self, *args):
                    if request._cr_cm:
                        request._cr_cm.__exit__(*args)
                        request._cr_cm = None
                        request._cr = None

            with with_obj():
                if self.func_request_type != self._request_type:
                    raise Exception("%s, %s: Function declared as capable of handling request of type '%s' but called with a request of type '%s'" \
                        % (self.func, self.httprequest.path, self.func_request_type, self._request_type))
                return self.func(*args, **kwargs)
        finally:
            # just to be sure no one tries to re-use the request
            self.db = None
            self.uid = None

def route(route, type="http", authentication="auth"):
    """
    Decorator marking the decorated method as being a handler for requests. The method must be part of a subclass
    of ``Controller``.

    Decorator to put on a controller method to inform it does not require a user to be logged. When this decorator
    is used, ``request.uid`` will be ``None``. The request will still try to detect the database and an exception
    will be launched if there is no way to guess it.

    :param route: string or array. The route part that will determine which http requests will match the decorated
    method. Can be a single string or an array of strings. See werkzeug's routing documentation for the format of
    route expression ( http://werkzeug.pocoo.org/docs/routing/ ).
    :param type: The type of request, can be ``'http'`` or ``'json'``.
    :param authentication: The type of authentication method, can on of the following:

        * ``auth``: The user must be authenticated.
        * ``noauth``: There is no need for the user to be authenticated but there must be a way to find the current
        database.
        * ``nodb``: The method is always active, even if there is no database. Mainly used by the framework and
        authentication modules.
    """
    def decorator(f):
        if isinstance(route, list):
            f.routes = route
        else:
            f.routes = [route]
        f.exposed = type
        if getattr(f, "auth", None) is None:
            f.auth = authentication
        return f
    return decorator

def noauth(f):
    f.auth = "noauth"
    return f

def nodb(f):
    f.auth = "nodb"
    return f

def reject_nonliteral(dct):
    if '__ref' in dct:
        raise ValueError(
            "Non literal contexts can not be sent to the server anymore (%r)" % (dct,))
    return dct

class JsonRequest(WebRequest):
    """ JSON-RPC2 over HTTP.

    Sucessful request::

      --> {"jsonrpc": "2.0",
           "method": "call",
           "params": {"session_id": "SID",
                      "context": {},
                      "arg1": "val1" },
           "id": null}

      <-- {"jsonrpc": "2.0",
           "result": { "res1": "val1" },
           "id": null}

    Request producing a error::

      --> {"jsonrpc": "2.0",
           "method": "call",
           "params": {"session_id": "SID",
                      "context": {},
                      "arg1": "val1" },
           "id": null}

      <-- {"jsonrpc": "2.0",
           "error": {"code": 1,
                     "message": "End user error message.",
                     "data": {"code": "codestring",
                              "debug": "traceback" } },
           "id": null}

    """
    _request_type = "json"

    def __init__(self, *args):
        super(JsonRequest, self).__init__(*args)

        self.jsonp_handler = None

        args = self.httprequest.args
        jsonp = args.get('jsonp')
        self.jsonp = jsonp
        request = None
        request_id = args.get('id')

        if jsonp and self.httprequest.method == 'POST':
            # jsonp 2 steps step1 POST: save call
            self.init(args)

            def handler():
                self.session.jsonp_requests[request_id] = self.httprequest.form['r']
                headers=[('Content-Type', 'text/plain; charset=utf-8')]
                r = werkzeug.wrappers.Response(request_id, headers=headers)
                return r
            self.jsonp_handler = handler
            return
        elif jsonp and args.get('r'):
            # jsonp method GET
            request = args.get('r')
        elif jsonp and request_id:
            # jsonp 2 steps step2 GET: run and return result
            self.init(args)
            request = self.session.jsonp_requests.pop(request_id, "")
        else:
            # regular jsonrpc2
            request = self.httprequest.stream.read()

        # Read POST content or POST Form Data named "request"
        self.jsonrequest = simplejson.loads(request, object_hook=reject_nonliteral)
        self.init(self.jsonrequest.get("params", {}))

    def dispatch(self):
        """ Calls the method asked for by the JSON-RPC2 or JSONP request

        :returns: an utf8 encoded JSON-RPC2 or JSONP reply
        """
        if self.jsonp_handler:
            return self.jsonp_handler()
        response = {"jsonrpc": "2.0" }
        error = None
        try:
            #if _logger.isEnabledFor(logging.DEBUG):
            #    _logger.debug("--> %s.%s\n%s", func.im_class.__name__, func.__name__, pprint.pformat(self.jsonrequest))
            response['id'] = self.jsonrequest.get('id')
            response["result"] = self._call_function(**self.params)
        except session.AuthenticationError, e:
            _logger.exception("Exception during JSON request handling.")
            se = serialize_exception(e)
            error = {
                'code': 100,
                'message': "OpenERP Session Invalid",
                'data': se
            }
        except Exception, e:
            _logger.exception("Exception during JSON request handling.")
            se = serialize_exception(e)
            error = {
                'code': 200,
                'message': "OpenERP Server Error",
                'data': se
            }
        if error:
            response["error"] = error

        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug("<--\n%s", pprint.pformat(response))

        if self.jsonp:
            # If we use jsonp, that's mean we are called from another host
            # Some browser (IE and Safari) do no allow third party cookies
            # We need then to manage http sessions manually.
            response['httpsessionid'] = self.httpsession.sid
            mime = 'application/javascript'
            body = "%s(%s);" % (self.jsonp, simplejson.dumps(response),)
        else:
            mime = 'application/json'
            body = simplejson.dumps(response)

        r = werkzeug.wrappers.Response(body, headers=[('Content-Type', mime), ('Content-Length', len(body))])
        return r

def serialize_exception(e):
    tmp = {
        "name": type(e).__module__ + "." + type(e).__name__ if type(e).__module__ else type(e).__name__,
        "debug": traceback.format_exc(),
        "message": u"%s" % e,
        "arguments": to_jsonable(e.args),
    }
    if isinstance(e, openerp.osv.osv.except_osv):
        tmp["exception_type"] = "except_osv"
    elif isinstance(e, openerp.exceptions.Warning):
        tmp["exception_type"] = "warning"
    elif isinstance(e, openerp.exceptions.AccessError):
        tmp["exception_type"] = "access_error"
    elif isinstance(e, openerp.exceptions.AccessDenied):
        tmp["exception_type"] = "access_denied"
    return tmp

def to_jsonable(o):
    if isinstance(o, str) or isinstance(o,unicode) or isinstance(o, int) or isinstance(o, long) \
        or isinstance(o, bool) or o is None or isinstance(o, float):
        return o
    if isinstance(o, list) or isinstance(o, tuple):
        return [to_jsonable(x) for x in o]
    if isinstance(o, dict):
        tmp = {}
        for k, v in o.items():
            tmp[u"%s" % k] = to_jsonable(v)
        return tmp
    return u"%s" % o

def jsonrequest(f):
    """ Decorator marking the decorated method as being a handler for a
    JSON-RPC request (the exact request path is specified via the
    ``$(Controller._cp_path)/$methodname`` combination.

    If the method is called, it will be provided with a :class:`JsonRequest`
    instance and all ``params`` sent during the JSON-RPC request, apart from
    the ``session_id``, ``context`` and ``debug`` keys (which are stripped out
    beforehand)
    """
    f.combine = True
    base = f.__name__
    if f.__name__ == "index":
        base = ""
    return route([base, os.path.join(base, "<path:path>")], type="json", authentication="auth")(f)

class HttpRequest(WebRequest):
    """ Regular GET/POST request
    """
    _request_type = "http"

    def __init__(self, *args):
        super(HttpRequest, self).__init__(*args)
        params = dict(self.httprequest.args)
        params.update(self.httprequest.form)
        params.update(self.httprequest.files)
        self.init(params)

    def dispatch(self):
        akw = {}
        for key, value in self.httprequest.args.iteritems():
            if isinstance(value, basestring) and len(value) < 1024:
                akw[key] = value
            else:
                akw[key] = type(value)
        #_logger.debug("%s --> %s.%s %r", self.httprequest.func, func.im_class.__name__, func.__name__, akw)
        try:
            r = self._call_function(**self.params)
        except werkzeug.exceptions.HTTPException, e:
            r = e
        except Exception, e:
            _logger.exception("An exception occured during an http request")
            se = serialize_exception(e)
            error = {
                'code': 200,
                'message': "OpenERP Server Error",
                'data': se
            }
            r = werkzeug.exceptions.InternalServerError(cgi.escape(simplejson.dumps(error)))
        else:
            if not r:
                r = werkzeug.wrappers.Response(status=204)  # no content
        if isinstance(r, (werkzeug.wrappers.BaseResponse, werkzeug.exceptions.HTTPException)):
            _logger.debug('<-- %s', r)
        else:
            _logger.debug("<-- size: %s", len(r))
        return r

    def make_response(self, data, headers=None, cookies=None):
        """ Helper for non-HTML responses, or HTML responses with custom
        response headers or cookies.

        While handlers can just return the HTML markup of a page they want to
        send as a string if non-HTML data is returned they need to create a
        complete response object, or the returned data will not be correctly
        interpreted by the clients.

        :param basestring data: response body
        :param headers: HTTP headers to set on the response
        :type headers: ``[(name, value)]``
        :param collections.Mapping cookies: cookies to set on the client
        """
        response = werkzeug.wrappers.Response(data, headers=headers)
        if cookies:
            for k, v in cookies.iteritems():
                response.set_cookie(k, v)
        return response

    def not_found(self, description=None):
        """ Helper for 404 response, return its result from the method
        """
        return werkzeug.exceptions.NotFound(description)

def httprequest(f):
    """ Decorator marking the decorated method as being a handler for a
    normal HTTP request (the exact request path is specified via the
    ``$(Controller._cp_path)/$methodname`` combination.

    If the method is called, it will be provided with a :class:`HttpRequest`
    instance and all ``params`` sent during the request (``GET`` and ``POST``
    merged in the same dictionary), apart from the ``session_id``, ``context``
    and ``debug`` keys (which are stripped out beforehand)
    """
    f.combine = True
    base = f.__name__
    if f.__name__ == "index":
        base = ""
    return route([base, os.path.join(base, "<path:path>")], type="http", authentication="auth")(f)

#----------------------------------------------------------
# Local storage of requests
#----------------------------------------------------------
from werkzeug.local import LocalStack

_request_stack = LocalStack()

def set_request(request):
    class with_obj(object):
        def __enter__(self):
            _request_stack.push(request)
        def __exit__(self, *args):
            _request_stack.pop()
    return with_obj()

"""
    A global proxy that always redirect to the current request object.
"""
request = _request_stack()

#----------------------------------------------------------
# Controller registration with a metaclass
#----------------------------------------------------------
addons_module = {}
addons_manifest = {}
controllers_per_module = {}

class ControllerType(type):
    def __init__(cls, name, bases, attrs):
        super(ControllerType, cls).__init__(name, bases, attrs)

        # create wrappers for old-style methods with req as first argument
        cls._methods_wrapper = {}
        for k, v in attrs.items():
            if inspect.isfunction(v):
                spec = inspect.getargspec(v)
                first_arg = spec.args[1] if len(spec.args) >= 2 else None
                if first_arg in ["req", "request"]:
                    def build_new(nv):
                        return lambda self, *args, **kwargs: nv(self, request, *args, **kwargs)
                    cls._methods_wrapper[k] = build_new(v)

        # store the controller in the controllers list
        name_class = ("%s.%s" % (cls.__module__, cls.__name__), cls)
        class_path = name_class[0].split(".")
        if not class_path[:2] == ["openerp", "addons"]:
            return
        module = class_path[2]
        controllers_per_module.setdefault(module, []).append(name_class)

class Controller(object):
    __metaclass__ = ControllerType

    """def __new__(cls, *args, **kwargs):
        subclasses = [c for c in cls.__subclasses__() if getattr(c, "_cp_path", None) == getattr(cls, "_cp_path", None)]
        if subclasses:
            name = "%s (extended by %s)" % (cls.__name__, ', '.join(sub.__name__ for sub in subclasses))
            cls = type(name, tuple(reversed(subclasses)), {})

        return object.__new__(cls)"""

    def get_wrapped_method(self, name):
        if name in self.__class__._methods_wrapper:
            return functools.partial(self.__class__._methods_wrapper[name], self)
        else:
            return getattr(self, name)

#----------------------------------------------------------
# Session context manager
#----------------------------------------------------------
@contextlib.contextmanager
def session_context(request, session_store, session_lock, sid):
    with session_lock:
        if sid:
            request.session = session_store.get(sid)
        else:
            request.session = session_store.new()
    try:
        yield request.session
    finally:
        # Remove all OpenERPSession instances with no uid, they're generated
        # either by login process or by HTTP requests without an OpenERP
        # session id, and are generally noise
        removed_sessions = set()
        for key, value in request.session.items():
            if not isinstance(value, session.OpenERPSession):
                continue
            if getattr(value, '_suicide', False) or (
                        not value._uid
                    and not value.jsonp_requests
                    # FIXME do not use a fixed value
                    and value._creation_time + (60*5) < time.time()):
                _logger.debug('remove session %s', key)
                removed_sessions.add(key)
                del request.session[key]

        with session_lock:
            if sid:
                # Re-load sessions from storage and merge non-literal
                # contexts and domains (they're indexed by hash of the
                # content so conflicts should auto-resolve), otherwise if
                # two requests alter those concurrently the last to finish
                # will overwrite the previous one, leading to loss of data
                # (a non-literal is lost even though it was sent to the
                # client and client errors)
                #
                # note that domains_store and contexts_store are append-only (we
                # only ever add items to them), so we can just update one with the
                # other to get the right result, if we want to merge the
                # ``context`` dict we'll need something smarter
                in_store = session_store.get(sid)
                for k, v in request.session.iteritems():
                    stored = in_store.get(k)
                    if stored and isinstance(v, session.OpenERPSession):
                        if hasattr(v, 'contexts_store'):
                            del v.contexts_store
                        if hasattr(v, 'domains_store'):
                            del v.domains_store
                        if not hasattr(v, 'jsonp_requests'):
                            v.jsonp_requests = {}
                        v.jsonp_requests.update(getattr(
                            stored, 'jsonp_requests', {}))

                # add missing keys
                for k, v in in_store.iteritems():
                    if k not in request.session and k not in removed_sessions:
                        request.session[k] = v

            session_store.save(request.session)

def session_gc(session_store):
    if random.random() < 0.001:
        # we keep session one week
        last_week = time.time() - 60*60*24*7
        for fname in os.listdir(session_store.path):
            path = os.path.join(session_store.path, fname)
            try:
                if os.path.getmtime(path) < last_week:
                    os.unlink(path)
            except OSError:
                pass

#----------------------------------------------------------
# WSGI Application
#----------------------------------------------------------
# Add potentially missing (older ubuntu) font mime types
mimetypes.add_type('application/font-woff', '.woff')
mimetypes.add_type('application/vnd.ms-fontobject', '.eot')
mimetypes.add_type('application/x-font-ttf', '.ttf')

class DisableCacheMiddleware(object):
    def __init__(self, app):
        self.app = app
    def __call__(self, environ, start_response):
        def start_wrapped(status, headers):
            referer = environ.get('HTTP_REFERER', '')
            parsed = urlparse.urlparse(referer)
            debug = parsed.query.count('debug') >= 1

            new_headers = []
            unwanted_keys = ['Last-Modified']
            if debug:
                new_headers = [('Cache-Control', 'no-cache')]
                unwanted_keys += ['Expires', 'Etag', 'Cache-Control']

            for k, v in headers:
                if k not in unwanted_keys:
                    new_headers.append((k, v))

            start_response(status, new_headers)
        return self.app(environ, start_wrapped)

def session_path():
    try:
        username = getpass.getuser()
    except Exception:
        username = "unknown"
    path = os.path.join(tempfile.gettempdir(), "oe-sessions-" + username)
    try:
        os.mkdir(path, 0700)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            # directory exists: ensure it has the correct permissions
            # this will fail if the directory is not owned by the current user
            os.chmod(path, 0700)
        else:
            raise
    return path

class Root(object):
    """Root WSGI application for the OpenERP Web Client.
    """
    def __init__(self):
        self.addons = {}
        self.statics = {}

        self.db_routers = {}
        self.db_routers_lock = threading.Lock()

        self.load_addons()

        # Setup http sessions
        path = session_path()
        self.session_store = werkzeug.contrib.sessions.FilesystemSessionStore(path)
        self.session_lock = threading.Lock()
        _logger.debug('HTTP sessions stored in: %s', path)


    def __call__(self, environ, start_response):
        """ Handle a WSGI request
        """
        return self.dispatch(environ, start_response)

    def dispatch(self, environ, start_response):
        """
        Performs the actual WSGI dispatching for the application, may be
        wrapped during the initialization of the object.

        Call the object directly.
        """
        httprequest = werkzeug.wrappers.Request(environ)
        httprequest.parameter_storage_class = werkzeug.datastructures.ImmutableDict
        httprequest.app = self

        sid = httprequest.cookies.get('sid')
        if not sid:
            sid = httprequest.args.get('sid')

        session_gc(self.session_store)

        with session_context(httprequest, self.session_store, self.session_lock, sid) as session:
            request = self._build_request(httprequest)
            db = request.db

            if db:
                updated = openerp.modules.registry.RegistryManager.check_registry_signaling(db)
                if updated:
                    with self.db_routers_lock:
                        del self.db_routers[db]

            with set_request(request):
                self.find_handler()
                result = request.dispatch()

            if db:
                openerp.modules.registry.RegistryManager.signal_caches_change(db)

            if isinstance(result, basestring):
                headers=[('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', len(result))]
                response = werkzeug.wrappers.Response(result, headers=headers)
            else:
                response = result

            if hasattr(response, 'set_cookie'):
                response.set_cookie('sid', session.sid)

            return response(environ, start_response)

    def _build_request(self, httprequest):
        if httprequest.args.get('jsonp'):
            return JsonRequest(httprequest)

        content = httprequest.stream.read()
        import cStringIO
        httprequest.stream = cStringIO.StringIO(content)
        try:
            simplejson.loads(content)
            return JsonRequest(httprequest)
        except:
            return HttpRequest(httprequest)

    def load_addons(self):
        """ Load all addons from addons patch containg static files and
        controllers and configure them.  """

        for addons_path in openerp.modules.module.ad_paths:
            for module in sorted(os.listdir(str(addons_path))):
                if module not in addons_module:
                    manifest_path = os.path.join(addons_path, module, '__openerp__.py')
                    path_static = os.path.join(addons_path, module, 'static')
                    if os.path.isfile(manifest_path) and os.path.isdir(path_static):
                        manifest = ast.literal_eval(open(manifest_path).read())
                        manifest['addons_path'] = addons_path
                        _logger.debug("Loading %s", module)
                        if 'openerp.addons' in sys.modules:
                            m = __import__('openerp.addons.' + module)
                        else:
                            m = __import__(module)
                        addons_module[module] = m
                        addons_manifest[module] = manifest
                        self.statics['/%s/static' % module] = path_static

        app = werkzeug.wsgi.SharedDataMiddleware(self.dispatch, self.statics)
        self.dispatch = DisableCacheMiddleware(app)

    def _build_router(self, db):
        _logger.info("Generating routing configuration for database %s" % db)
        routing_map = routing.Map()
        modules_set = set(controllers_per_module.keys())
        modules_set -= set("web")

        modules = ["web"] + sorted(modules_set)
        # building all nodb methods
        for module in modules:
            for v in controllers_per_module[module]:
                members = inspect.getmembers(v[1]())
                for mk, mv in members:
                    if inspect.ismethod(mv) and getattr(mv, 'exposed', False) and getattr(mv, 'auth', None) == "nodb":
                        o = v[1]()
                        function = (o.get_wrapped_method(mk), mv)
                        for url in mv.routes:
                            if getattr(mv, "combine", False):
                                url = os.path.join(o._cp_path, url)
                                if url.endswith("/") and len(url) > 1:
                                    url = url[: -1]
                            print "<<<<<<<<<<<<<<<< nodb", url
                            routing_map.add(routing.Rule(url, endpoint=function))

        if not db:
            return routing_map

        registry = openerp.modules.registry.RegistryManager.get(db)
        with registry.cursor() as cr:
            m = registry.get('ir.module.module')
            ids = m.search(cr, openerp.SUPERUSER_ID, [('state','=','installed')])
            installed = set([x['name'] for x in m.read(cr, 1, ids, ['name'])])
            modules_set -= set(installed)
        modules = ["web"] + sorted(modules_set)
        # building all other methods
        for module in modules:
            for v in controllers_per_module[module]:
                o = v[1]()
                members = inspect.getmembers(o)
                for mk, mv in members:
                    if inspect.ismethod(mv) and getattr(mv, 'exposed', False) and getattr(mv, 'auth', None) != "nodb":
                        function = (o.get_wrapped_method(mk), mv)
                        for url in mv.routes:
                            if getattr(mv, "combine", False):
                                url = os.path.join(o._cp_path, url)
                                if url.endswith("/") and len(url) > 1:
                                    url = url[: -1]
                            print "<<<<<<<<<<<<<<<< db", url
                            routing_map.add(routing.Rule(url, endpoint=function))
        return routing_map

    def get_db_router(self, db):
        with self.db_routers_lock:
            router = self.db_routers.get(db)
        if not router:
            router = self._build_router(db)
            with self.db_routers_lock:
                router = self.db_routers[db] = router
        return router

    def find_handler(self):
        """
        Tries to discover the controller handling the request for the path
        specified by the provided parameters

        :param path: path to match
        :returns: a callable matching the path sections
        :rtype: ``Controller | None``
        """
        path = request.httprequest.path
        urls = self.get_db_router(request.db).bind("")
        func, original = urls.match(path)[0]

        request.func = func
        request.auth_method = getattr(original, "auth", "auth")
        request.func_request_type = original.exposed

def wsgi_postload():
    openerp.wsgi.register_wsgi_handler(Root())

# vim:et:ts=4:sw=4:
