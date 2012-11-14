# -*- coding: utf-8 -*-

import ast
import base64
import csv
import glob
import itertools
import logging
import operator
import datetime
import hashlib
import os
import re
import simplejson
import time
import urllib2
import xmlrpclib
import zlib
from xml.etree import ElementTree
from cStringIO import StringIO

import babel.messages.pofile
import werkzeug.utils
import werkzeug.wrappers
try:
    import xlwt
except ImportError:
    xlwt = None

import openerp

from .. import http
from .. import nonliterals
openerpweb = http

#----------------------------------------------------------
# OpenERP Web helpers
#----------------------------------------------------------

def rjsmin(script):
    """ Minify js with a clever regex.
    Taken from http://opensource.perlig.de/rjsmin
    Apache License, Version 2.0 """
    def subber(match):
        """ Substitution callback """
        groups = match.groups()
        return (
            groups[0] or
            groups[1] or
            groups[2] or
            groups[3] or
            (groups[4] and '\n') or
            (groups[5] and ' ') or
            (groups[6] and ' ') or
            (groups[7] and ' ') or
            ''
        )

    result = re.sub(
        r'([^\047"/\000-\040]+)|((?:(?:\047[^\047\\\r\n]*(?:\\(?:[^\r\n]|\r?'
        r'\n|\r)[^\047\\\r\n]*)*\047)|(?:"[^"\\\r\n]*(?:\\(?:[^\r\n]|\r?\n|'
        r'\r)[^"\\\r\n]*)*"))[^\047"/\000-\040]*)|(?:(?<=[(,=:\[!&|?{};\r\n]'
        r')(?:[\000-\011\013\014\016-\040]|(?:/\*[^*]*\*+(?:[^/*][^*]*\*+)*/'
        r'))*((?:/(?![\r\n/*])[^/\\\[\r\n]*(?:(?:\\[^\r\n]|(?:\[[^\\\]\r\n]*'
        r'(?:\\[^\r\n][^\\\]\r\n]*)*\]))[^/\\\[\r\n]*)*/)[^\047"/\000-\040]*'
        r'))|(?:(?<=[\000-#%-,./:-@\[-^`{-~-]return)(?:[\000-\011\013\014\01'
        r'6-\040]|(?:/\*[^*]*\*+(?:[^/*][^*]*\*+)*/))*((?:/(?![\r\n/*])[^/'
        r'\\\[\r\n]*(?:(?:\\[^\r\n]|(?:\[[^\\\]\r\n]*(?:\\[^\r\n][^\\\]\r\n]'
        r'*)*\]))[^/\\\[\r\n]*)*/)[^\047"/\000-\040]*))|(?<=[^\000-!#%&(*,./'
        r':-@\[\\^`{|~])(?:[\000-\011\013\014\016-\040]|(?:/\*[^*]*\*+(?:[^/'
        r'*][^*]*\*+)*/))*(?:((?:(?://[^\r\n]*)?[\r\n]))(?:[\000-\011\013\01'
        r'4\016-\040]|(?:/\*[^*]*\*+(?:[^/*][^*]*\*+)*/))*)+(?=[^\000-\040"#'
        r'%-\047)*,./:-@\\-^`|-~])|(?<=[^\000-#%-,./:-@\[-^`{-~-])((?:[\000-'
        r'\011\013\014\016-\040]|(?:/\*[^*]*\*+(?:[^/*][^*]*\*+)*/)))+(?=[^'
        r'\000-#%-,./:-@\[-^`{-~-])|(?<=\+)((?:[\000-\011\013\014\016-\040]|'
        r'(?:/\*[^*]*\*+(?:[^/*][^*]*\*+)*/)))+(?=\+)|(?<=-)((?:[\000-\011\0'
        r'13\014\016-\040]|(?:/\*[^*]*\*+(?:[^/*][^*]*\*+)*/)))+(?=-)|(?:[\0'
        r'00-\011\013\014\016-\040]|(?:/\*[^*]*\*+(?:[^/*][^*]*\*+)*/))+|(?:'
        r'(?:(?://[^\r\n]*)?[\r\n])(?:[\000-\011\013\014\016-\040]|(?:/\*[^*'
        r']*\*+(?:[^/*][^*]*\*+)*/))*)+', subber, '\n%s\n' % script
    ).strip()
    return result

def db_list(req):
    dbs = []
    proxy = req.session.proxy("db")
    dbs = proxy.list()
    h = req.httprequest.environ['HTTP_HOST'].split(':')[0]
    d = h.split('.')[0]
    r = openerp.tools.config['dbfilter'].replace('%h', h).replace('%d', d)
    dbs = [i for i in dbs if re.match(r, i)]
    return dbs

def db_monodb(req):
    # if only one db is listed returns it else return False
    try:
        dbs = db_list(req)
        if len(dbs) == 1:
            return dbs[0]
    except xmlrpclib.Fault:
        # ignore access denied
        pass
    return False

def module_topological_sort(modules):
    """ Return a list of module names sorted so that their dependencies of the
    modules are listed before the module itself

    modules is a dict of {module_name: dependencies}

    :param modules: modules to sort
    :type modules: dict
    :returns: list(str)
    """

    dependencies = set(itertools.chain.from_iterable(modules.itervalues()))
    # incoming edge: dependency on other module (if a depends on b, a has an
    # incoming edge from b, aka there's an edge from b to a)
    # outgoing edge: other module depending on this one

    # [Tarjan 1976], http://en.wikipedia.org/wiki/Topological_sorting#Algorithms
    #L ← Empty list that will contain the sorted nodes
    L = []
    #S ← Set of all nodes with no outgoing edges (modules on which no other
    #    module depends)
    S = set(module for module in modules if module not in dependencies)

    visited = set()
    #function visit(node n)
    def visit(n):
        #if n has not been visited yet then
        if n not in visited:
            #mark n as visited
            visited.add(n)
            #change: n not web module, can not be resolved, ignore
            if n not in modules: return
            #for each node m with an edge from m to n do (dependencies of n)
            for m in modules[n]:
                #visit(m)
                visit(m)
            #add n to L
            L.append(n)
    #for each node n in S do
    for n in S:
        #visit(n)
        visit(n)
    return L

def module_installed(req):
    # Candidates module the current heuristic is the /static dir
    loadable = openerpweb.addons_manifest.keys()
    modules = {}

    # Retrieve database installed modules
    # TODO The following code should move to ir.module.module.list_installed_modules()
    Modules = req.session.model('ir.module.module')
    domain = [('state','=','installed'), ('name','in', loadable)]
    for module in Modules.search_read(domain, ['name', 'dependencies_id']):
        modules[module['name']] = []
        deps = module.get('dependencies_id')
        if deps:
            deps_read = req.session.model('ir.module.module.dependency').read(deps, ['name'])
            dependencies = [i['name'] for i in deps_read]
            modules[module['name']] = dependencies

    sorted_modules = module_topological_sort(modules)
    return sorted_modules

def module_installed_bypass_session(dbname):
    loadable = openerpweb.addons_manifest.keys()
    modules = {}
    try:
        import openerp.modules.registry
        registry = openerp.modules.registry.RegistryManager.get(dbname)
        with registry.cursor() as cr:
            m = registry.get('ir.module.module')
            # TODO The following code should move to ir.module.module.list_installed_modules()
            domain = [('state','=','installed'), ('name','in', loadable)]
            ids = m.search(cr, 1, [('state','=','installed'), ('name','in', loadable)])
            for module in m.read(cr, 1, ids, ['name', 'dependencies_id']):
                modules[module['name']] = []
                deps = module.get('dependencies_id')
                if deps:
                    deps_read = registry.get('ir.module.module.dependency').read(cr, 1, deps, ['name'])
                    dependencies = [i['name'] for i in deps_read]
                    modules[module['name']] = dependencies
    except Exception,e:
        pass
    sorted_modules = module_topological_sort(modules)
    return sorted_modules

def module_boot(req):
    server_wide_modules = openerp.conf.server_wide_modules or ['web']
    serverside = []
    dbside = []
    for i in server_wide_modules:
        if i in openerpweb.addons_manifest:
            serverside.append(i)
    monodb = db_monodb(req)
    if monodb:
        dbside = module_installed_bypass_session(monodb)
        dbside = [i for i in dbside if i not in serverside]
    addons = serverside + dbside
    return addons

def concat_xml(file_list):
    """Concatenate xml files

    :param list(str) file_list: list of files to check
    :returns: (concatenation_result, checksum)
    :rtype: (str, str)
    """
    checksum = hashlib.new('sha1')
    if not file_list:
        return '', checksum.hexdigest()

    root = None
    for fname in file_list:
        with open(fname, 'rb') as fp:
            contents = fp.read()
            checksum.update(contents)
            fp.seek(0)
            xml = ElementTree.parse(fp).getroot()

        if root is None:
            root = ElementTree.Element(xml.tag)
        #elif root.tag != xml.tag:
        #    raise ValueError("Root tags missmatch: %r != %r" % (root.tag, xml.tag))

        for child in xml.getchildren():
            root.append(child)
    return ElementTree.tostring(root, 'utf-8'), checksum.hexdigest()

def concat_files(file_list, reader=None, intersperse=""):
    """ Concatenates contents of all provided files

    :param list(str) file_list: list of files to check
    :param function reader: reading procedure for each file
    :param str intersperse: string to intersperse between file contents
    :returns: (concatenation_result, checksum)
    :rtype: (str, str)
    """
    checksum = hashlib.new('sha1')
    if not file_list:
        return '', checksum.hexdigest()

    if reader is None:
        def reader(f):
            with open(f, 'rb') as fp:
                return fp.read()

    files_content = []
    for fname in file_list:
        contents = reader(fname)
        checksum.update(contents)
        files_content.append(contents)

    files_concat = intersperse.join(files_content)
    return files_concat, checksum.hexdigest()

def concat_js(file_list):
    content, checksum = concat_files(file_list, intersperse=';')
    content = rjsmin(content)
    return content, checksum 

def manifest_glob(req, addons, key):
    if addons is None:
        addons = module_boot(req)
    else:
        addons = addons.split(',')
    r = []
    for addon in addons:
        manifest = openerpweb.addons_manifest.get(addon, None)
        if not manifest:
            continue
        # ensure does not ends with /
        addons_path = os.path.join(manifest['addons_path'], '')[:-1]
        globlist = manifest.get(key, [])
        for pattern in globlist:
            for path in glob.glob(os.path.normpath(os.path.join(addons_path, addon, pattern))):
                r.append((path, path[len(addons_path):]))
    return r

def manifest_list(req, mods, extension):
    if not req.debug:
        path = '/web/webclient/' + extension
        if mods is not None:
            path += '?mods=' + mods
        return [path]
    files = manifest_glob(req, mods, extension)
    i_am_diabetic = req.httprequest.environ["QUERY_STRING"].count("no_sugar") >= 1 or \
                    req.httprequest.environ.get('HTTP_REFERER', '').count("no_sugar") >= 1
    if i_am_diabetic:
        return [wp for _fp, wp in files]
    else:
        return ['%s?debug=%s' % (wp, os.path.getmtime(fp)) for fp, wp in files]

def get_last_modified(files):
    """ Returns the modification time of the most recently modified
    file provided

    :param list(str) files: names of files to check
    :return: most recent modification time amongst the fileset
    :rtype: datetime.datetime
    """
    files = list(files)
    if files:
        return max(datetime.datetime.fromtimestamp(os.path.getmtime(f))
                   for f in files)
    return datetime.datetime(1970, 1, 1)

def make_conditional(req, response, last_modified=None, etag=None):
    """ Makes the provided response conditional based upon the request,
    and mandates revalidation from clients

    Uses Werkzeug's own :meth:`ETagResponseMixin.make_conditional`, after
    setting ``last_modified`` and ``etag`` correctly on the response object

    :param req: OpenERP request
    :type req: web.common.http.WebRequest
    :param response: Werkzeug response
    :type response: werkzeug.wrappers.Response
    :param datetime.datetime last_modified: last modification date of the response content
    :param str etag: some sort of checksum of the content (deep etag)
    :return: the response object provided
    :rtype: werkzeug.wrappers.Response
    """
    response.cache_control.must_revalidate = True
    response.cache_control.max_age = 0
    if last_modified:
        response.last_modified = last_modified
    if etag:
        response.set_etag(etag)
    return response.make_conditional(req.httprequest)

def login_and_redirect(req, db, login, key, redirect_url='/'):
    req.session.authenticate(db, login, key, {})
    return set_cookie_and_redirect(req, redirect_url)

def set_cookie_and_redirect(req, redirect_url):
    redirect = werkzeug.utils.redirect(redirect_url, 303)
    redirect.autocorrect_location_header = False
    cookie_val = urllib2.quote(simplejson.dumps(req.session_id))
    redirect.set_cookie('instance0|session_id', cookie_val)
    return redirect

def eval_context_and_domain(session, context, domain=None):
    e_context = session.eval_context(context)
    # should we give the evaluated context as an evaluation context to the domain?
    e_domain = session.eval_domain(domain or [])

    return e_context, e_domain

def load_actions_from_ir_values(req, key, key2, models, meta):
    context = req.session.eval_context(req.context)
    Values = req.session.model('ir.values')
    actions = Values.get(key, key2, models, meta, context)

    return [(id, name, clean_action(req, action))
            for id, name, action in actions]

def clean_action(req, action, do_not_eval=False):
    action.setdefault('flags', {})

    context = req.session.eval_context(req.context)
    eval_ctx = req.session.evaluation_context(context)

    if not do_not_eval:
        # values come from the server, we can just eval them
        if action.get('context') and isinstance(action.get('context'), basestring):
            action['context'] = eval( action['context'], eval_ctx ) or {}

        if action.get('domain') and isinstance(action.get('domain'), basestring):
            action['domain'] = eval( action['domain'], eval_ctx ) or []
    else:
        if 'context' in action:
            action['context'] = parse_context(action['context'], req.session)
        if 'domain' in action:
            action['domain'] = parse_domain(action['domain'], req.session)

    action_type = action.setdefault('type', 'ir.actions.act_window_close')
    if action_type == 'ir.actions.act_window':
        return fix_view_modes(action)
    return action

# I think generate_views,fix_view_modes should go into js ActionManager
def generate_views(action):
    """
    While the server generates a sequence called "views" computing dependencies
    between a bunch of stuff for views coming directly from the database
    (the ``ir.actions.act_window model``), it's also possible for e.g. buttons
    to return custom view dictionaries generated on the fly.

    In that case, there is no ``views`` key available on the action.

    Since the web client relies on ``action['views']``, generate it here from
    ``view_mode`` and ``view_id``.

    Currently handles two different cases:

    * no view_id, multiple view_mode
    * single view_id, single view_mode

    :param dict action: action descriptor dictionary to generate a views key for
    """
    view_id = action.get('view_id') or False
    if isinstance(view_id, (list, tuple)):
        view_id = view_id[0]

    # providing at least one view mode is a requirement, not an option
    view_modes = action['view_mode'].split(',')

    if len(view_modes) > 1:
        if view_id:
            raise ValueError('Non-db action dictionaries should provide '
                             'either multiple view modes or a single view '
                             'mode and an optional view id.\n\n Got view '
                             'modes %r and view id %r for action %r' % (
                view_modes, view_id, action))
        action['views'] = [(False, mode) for mode in view_modes]
        return
    action['views'] = [(view_id, view_modes[0])]

def fix_view_modes(action):
    """ For historical reasons, OpenERP has weird dealings in relation to
    view_mode and the view_type attribute (on window actions):

    * one of the view modes is ``tree``, which stands for both list views
      and tree views
    * the choice is made by checking ``view_type``, which is either
      ``form`` for a list view or ``tree`` for an actual tree view

    This methods simply folds the view_type into view_mode by adding a
    new view mode ``list`` which is the result of the ``tree`` view_mode
    in conjunction with the ``form`` view_type.

    TODO: this should go into the doc, some kind of "peculiarities" section

    :param dict action: an action descriptor
    :returns: nothing, the action is modified in place
    """
    if not action.get('views'):
        generate_views(action)

    if action.pop('view_type', 'form') != 'form':
        return action

    if 'view_mode' in action:
        action['view_mode'] = ','.join(
            mode if mode != 'tree' else 'list'
            for mode in action['view_mode'].split(','))
    action['views'] = [
        [id, mode if mode != 'tree' else 'list']
        for id, mode in action['views']
    ]

    return action

def parse_domain(domain, session):
    """ Parses an arbitrary string containing a domain, transforms it
    to either a literal domain or a :class:`nonliterals.Domain`

    :param domain: the domain to parse, if the domain is not a string it
                   is assumed to be a literal domain and is returned as-is
    :param session: Current OpenERP session
    :type session: openerpweb.OpenERPSession
    """
    if not isinstance(domain, basestring):
        return domain
    try:
        return ast.literal_eval(domain)
    except ValueError:
        # not a literal
        return nonliterals.Domain(session, domain)

def parse_context(context, session):
    """ Parses an arbitrary string containing a context, transforms it
    to either a literal context or a :class:`nonliterals.Context`

    :param context: the context to parse, if the context is not a string it
           is assumed to be a literal domain and is returned as-is
    :param session: Current OpenERP session
    :type session: openerpweb.OpenERPSession
    """
    if not isinstance(context, basestring):
        return context
    try:
        return ast.literal_eval(context)
    except ValueError:
        return nonliterals.Context(session, context)

def _local_web_translations(trans_file):
    messages = []
    try:
        with open(trans_file) as t_file:
            po = babel.messages.pofile.read_po(t_file)
    except Exception:
        return
    for x in po:
        if x.id and x.string and "openerp-web" in x.auto_comments:
            messages.append({'id': x.id, 'string': x.string})
    return messages

def xml2json_from_elementtree(el, preserve_whitespaces=False):
    """ xml2json-direct
    Simple and straightforward XML-to-JSON converter in Python
    New BSD Licensed
    http://code.google.com/p/xml2json-direct/
    """
    res = {}
    if el.tag[0] == "{":
        ns, name = el.tag.rsplit("}", 1)
        res["tag"] = name
        res["namespace"] = ns[1:]
    else:
        res["tag"] = el.tag
    res["attrs"] = {}
    for k, v in el.items():
        res["attrs"][k] = v
    kids = []
    if el.text and (preserve_whitespaces or el.text.strip() != ''):
        kids.append(el.text)
    for kid in el:
        kids.append(xml2json_from_elementtree(kid, preserve_whitespaces))
        if kid.tail and (preserve_whitespaces or kid.tail.strip() != ''):
            kids.append(kid.tail)
    res["children"] = kids
    return res

def content_disposition(filename, req):
    filename = filename.encode('utf8')
    escaped = urllib2.quote(filename)
    browser = req.httprequest.user_agent.browser
    version = int((req.httprequest.user_agent.version or '0').split('.')[0])
    if browser == 'msie' and version < 9:
        return "attachment; filename=%s" % escaped
    elif browser == 'safari':
        return "attachment; filename=%s" % filename
    else:
        return "attachment; filename*=UTF-8''%s" % escaped


#----------------------------------------------------------
# OpenERP Web web Controllers
#----------------------------------------------------------

html_template = """<!DOCTYPE html>
<html style="height: 100%%">
    <head>
        <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1"/>
        <meta http-equiv="content-type" content="text/html; charset=utf-8" />
        <title>OpenERP</title>
        <link rel="shortcut icon" href="/web/static/src/img/favicon.ico" type="image/x-icon"/>
        <link rel="stylesheet" href="/web/static/src/css/full.css" />
        %(css)s
        %(js)s
        <script type="text/javascript">
            $(function() {
                var s = new openerp.init(%(modules)s);
                %(init)s
            });
        </script>
    </head>
    <body>
        <!--[if lte IE 8]>
        <script src="http://ajax.googleapis.com/ajax/libs/chrome-frame/1/CFInstall.min.js"></script>
        <script>
            var test = function() {
                CFInstall.check({
                    mode: "overlay"
                });
            };
            if (window.localStorage && false) {
                if (! localStorage.getItem("hasShownGFramePopup")) {
                    test();
                    localStorage.setItem("hasShownGFramePopup", true);
                }
            } else {
                test();
            }
        </script>
        <![endif]-->
    </body>
</html>
"""

class Home(openerpweb.Controller):
    _cp_path = '/'

    @openerpweb.httprequest
    def index(self, req, s_action=None, **kw):
        js = "\n        ".join('<script type="text/javascript" src="%s"></script>' % i for i in manifest_list(req, None, 'js'))
        css = "\n        ".join('<link rel="stylesheet" href="%s">' % i for i in manifest_list(req, None, 'css'))

        r = html_template % {
            'js': js,
            'css': css,
            'modules': simplejson.dumps(module_boot(req)),
            'init': 'var wc = new s.web.WebClient();wc.appendTo($(document.body));'
        }
        return r

    @openerpweb.httprequest
    def login(self, req, db, login, key):
        return login_and_redirect(req, db, login, key)

class WebClient(openerpweb.Controller):
    _cp_path = "/web/webclient"

    @openerpweb.jsonrequest
    def csslist(self, req, mods=None):
        return manifest_list(req, mods, 'css')

    @openerpweb.jsonrequest
    def jslist(self, req, mods=None):
        return manifest_list(req, mods, 'js')

    @openerpweb.jsonrequest
    def qweblist(self, req, mods=None):
        return manifest_list(req, mods, 'qweb')

    @openerpweb.httprequest
    def css(self, req, mods=None):
        files = list(manifest_glob(req, mods, 'css'))
        last_modified = get_last_modified(f[0] for f in files)
        if req.httprequest.if_modified_since and req.httprequest.if_modified_since >= last_modified:
            return werkzeug.wrappers.Response(status=304)

        file_map = dict(files)

        rx_import = re.compile(r"""@import\s+('|")(?!'|"|/|https?://)""", re.U)
        rx_url = re.compile(r"""url\s*\(\s*('|"|)(?!'|"|/|https?://|data:)""", re.U)

        def reader(f):
            """read the a css file and absolutify all relative uris"""
            with open(f, 'rb') as fp:
                data = fp.read().decode('utf-8')

            path = file_map[f]
            # convert FS path into web path
            web_dir = '/'.join(os.path.dirname(path).split(os.path.sep))

            data = re.sub(
                rx_import,
                r"""@import \1%s/""" % (web_dir,),
                data,
            )

            data = re.sub(
                rx_url,
                r"""url(\1%s/""" % (web_dir,),
                data,
            )
            return data.encode('utf-8')

        content, checksum = concat_files((f[0] for f in files), reader)

        return make_conditional(
            req, req.make_response(content, [('Content-Type', 'text/css')]),
            last_modified, checksum)

    @openerpweb.httprequest
    def js(self, req, mods=None):
        files = [f[0] for f in manifest_glob(req, mods, 'js')]
        last_modified = get_last_modified(files)
        if req.httprequest.if_modified_since and req.httprequest.if_modified_since >= last_modified:
            return werkzeug.wrappers.Response(status=304)

        content, checksum = concat_js(files)

        return make_conditional(
            req, req.make_response(content, [('Content-Type', 'application/javascript')]),
            last_modified, checksum)

    @openerpweb.httprequest
    def qweb(self, req, mods=None):
        files = [f[0] for f in manifest_glob(req, mods, 'qweb')]
        last_modified = get_last_modified(files)
        if req.httprequest.if_modified_since and req.httprequest.if_modified_since >= last_modified:
            return werkzeug.wrappers.Response(status=304)

        content, checksum = concat_xml(files)

        return make_conditional(
            req, req.make_response(content, [('Content-Type', 'text/xml')]),
            last_modified, checksum)

    @openerpweb.jsonrequest
    def bootstrap_translations(self, req, mods):
        """ Load local translations from *.po files, as a temporary solution
            until we have established a valid session. This is meant only
            for translating the login page and db management chrome, using
            the browser's language. """
        # For performance reasons we only load a single translation, so for
        # sub-languages (that should only be partially translated) we load the
        # main language PO instead - that should be enough for the login screen.
        lang = req.lang.split('_')[0]

        translations_per_module = {}
        for addon_name in mods:
            if openerpweb.addons_manifest[addon_name].get('bootstrap'):
                addons_path = openerpweb.addons_manifest[addon_name]['addons_path']
                f_name = os.path.join(addons_path, addon_name, "i18n", lang + ".po")
                if not os.path.exists(f_name):
                    continue
                translations_per_module[addon_name] = {'messages': _local_web_translations(f_name)}

        return {"modules": translations_per_module,
                "lang_parameters": None}

    @openerpweb.jsonrequest
    def translations(self, req, mods, lang):
        res_lang = req.session.model('res.lang')
        ids = res_lang.search([("code", "=", lang)])
        lang_params = None
        if ids:
            lang_params = res_lang.read(ids[0], ["direction", "date_format", "time_format",
                                                "grouping", "decimal_point", "thousands_sep"])

        # Regional languages (ll_CC) must inherit/override their parent lang (ll), but this is
        # done server-side when the language is loaded, so we only need to load the user's lang.
        ir_translation = req.session.model('ir.translation')
        translations_per_module = {}
        messages = ir_translation.search_read([('module','in',mods),('lang','=',lang),
                                               ('comments','like','openerp-web'),('value','!=',False),
                                               ('value','!=','')],
                                              ['module','src','value','lang'], order='module') 
        for mod, msg_group in itertools.groupby(messages, key=operator.itemgetter('module')):
            translations_per_module.setdefault(mod,{'messages':[]})
            translations_per_module[mod]['messages'].extend({'id': m['src'],
                                                             'string': m['value']} \
                                                                for m in msg_group)
        return {"modules": translations_per_module,
                "lang_parameters": lang_params}

    @openerpweb.jsonrequest
    def version_info(self, req):
        return {
            "version": openerp.release.version
        }

class Proxy(openerpweb.Controller):
    _cp_path = '/web/proxy'

    @openerpweb.jsonrequest
    def load(self, req, path):
        """ Proxies an HTTP request through a JSON request.

        It is strongly recommended to not request binary files through this,
        as the result will be a binary data blob as well.

        :param req: OpenERP request
        :param path: actual request path
        :return: file content
        """
        from werkzeug.test import Client
        from werkzeug.wrappers import BaseResponse

        return Client(req.httprequest.app, BaseResponse).get(path).data

class Database(openerpweb.Controller):
    _cp_path = "/web/database"

    @openerpweb.jsonrequest
    def get_list(self, req):
        return db_list(req)

    @openerpweb.jsonrequest
    def create(self, req, fields):
        params = dict(map(operator.itemgetter('name', 'value'), fields))
        create_attrs = (
            params['super_admin_pwd'],
            params['db_name'],
            bool(params.get('demo_data')),
            params['db_lang'],
            params['create_admin_pwd']
        )

        return req.session.proxy("db").create_database(*create_attrs)

    @openerpweb.jsonrequest
    def drop(self, req, fields):
        password, db = operator.itemgetter(
            'drop_pwd', 'drop_db')(
                dict(map(operator.itemgetter('name', 'value'), fields)))

        try:
            return req.session.proxy("db").drop(password, db)
        except xmlrpclib.Fault, e:
            if e.faultCode and e.faultCode.split(':')[0] == 'AccessDenied':
                return {'error': e.faultCode, 'title': 'Drop Database'}
        return {'error': 'Could not drop database !', 'title': 'Drop Database'}

    @openerpweb.httprequest
    def backup(self, req, backup_db, backup_pwd, token):
        try:
            db_dump = base64.b64decode(
                req.session.proxy("db").dump(backup_pwd, backup_db))
            filename = "%(db)s_%(timestamp)s.dump" % {
                'db': backup_db,
                'timestamp': datetime.datetime.utcnow().strftime(
                    "%Y-%m-%d_%H-%M-%SZ")
            }
            return req.make_response(db_dump,
               [('Content-Type', 'application/octet-stream; charset=binary'),
               ('Content-Disposition', content_disposition(filename, req))],
               {'fileToken': int(token)}
            )
        except xmlrpclib.Fault, e:
            return simplejson.dumps([[],[{'error': e.faultCode, 'title': 'backup Database'}]])

    @openerpweb.httprequest
    def restore(self, req, db_file, restore_pwd, new_db):
        try:
            data = base64.b64encode(db_file.read())
            req.session.proxy("db").restore(restore_pwd, new_db, data)
            return ''
        except xmlrpclib.Fault, e:
            if e.faultCode and e.faultCode.split(':')[0] == 'AccessDenied':
                raise Exception("AccessDenied")

    @openerpweb.jsonrequest
    def change_password(self, req, fields):
        old_password, new_password = operator.itemgetter(
            'old_pwd', 'new_pwd')(
                dict(map(operator.itemgetter('name', 'value'), fields)))
        try:
            return req.session.proxy("db").change_admin_password(old_password, new_password)
        except xmlrpclib.Fault, e:
            if e.faultCode and e.faultCode.split(':')[0] == 'AccessDenied':
                return {'error': e.faultCode, 'title': 'Change Password'}
        return {'error': 'Error, password not changed !', 'title': 'Change Password'}

class Session(openerpweb.Controller):
    _cp_path = "/web/session"

    def session_info(self, req):
        req.session.ensure_valid()
        return {
            "session_id": req.session_id,
            "uid": req.session._uid,
            "context": req.session.get_context() if req.session._uid else {},
            "db": req.session._db,
            "login": req.session._login,
        }

    @openerpweb.jsonrequest
    def get_session_info(self, req):
        return self.session_info(req)

    @openerpweb.jsonrequest
    def authenticate(self, req, db, login, password, base_location=None):
        wsgienv = req.httprequest.environ
        env = dict(
            base_location=base_location,
            HTTP_HOST=wsgienv['HTTP_HOST'],
            REMOTE_ADDR=wsgienv['REMOTE_ADDR'],
        )
        req.session.authenticate(db, login, password, env)

        return self.session_info(req)

    @openerpweb.jsonrequest
    def change_password (self,req,fields):
        old_password, new_password,confirm_password = operator.itemgetter('old_pwd', 'new_password','confirm_pwd')(
                dict(map(operator.itemgetter('name', 'value'), fields)))
        if not (old_password.strip() and new_password.strip() and confirm_password.strip()):
            return {'error':'All passwords have to be filled.','title': 'Change Password'}
        if new_password != confirm_password:
            return {'error': 'The new password and its confirmation must be identical.','title': 'Change Password'}
        try:
            if req.session.model('res.users').change_password(
                old_password, new_password):
                return {'new_password':new_password}
        except Exception:
            return {'error': 'Original password incorrect, your password was not changed.', 'title': 'Change Password'}
        return {'error': 'Error, password not changed !', 'title': 'Change Password'}

    @openerpweb.jsonrequest
    def sc_list(self, req):
        return req.session.model('ir.ui.view_sc').get_sc(
            req.session._uid, "ir.ui.menu", req.session.eval_context(req.context))

    @openerpweb.jsonrequest
    def get_lang_list(self, req):
        try:
            return {
                'lang_list': (req.session.proxy("db").list_lang() or []),
                'error': ""
            }
        except Exception, e:
            return {"error": e, "title": "Languages"}

    @openerpweb.jsonrequest
    def modules(self, req):
        # return all installed modules. Web client is smart enough to not load a module twice
        return module_installed(req)

    @openerpweb.jsonrequest
    def eval_domain_and_context(self, req, contexts, domains,
                                group_by_seq=None):
        """ Evaluates sequences of domains and contexts, composing them into
        a single context, domain or group_by sequence.

        :param list contexts: list of contexts to merge together. Contexts are
                              evaluated in sequence, all previous contexts
                              are part of their own evaluation context
                              (starting at the session context).
        :param list domains: list of domains to merge together. Domains are
                             evaluated in sequence and appended to one another
                             (implicit AND), their evaluation domain is the
                             result of merging all contexts.
        :param list group_by_seq: list of domains (which may be in a different
                                  order than the ``contexts`` parameter),
                                  evaluated in sequence, their ``'group_by'``
                                  key is extracted if they have one.
        :returns:
            a 3-dict of:

            context (``dict``)
                the global context created by merging all of
                ``contexts``

            domain (``list``)
                the concatenation of all domains

            group_by (``list``)
                a list of fields to group by, potentially empty (in which case
                no group by should be performed)
        """
        context, domain = eval_context_and_domain(req.session,
                                                  nonliterals.CompoundContext(*(contexts or [])),
                                                  nonliterals.CompoundDomain(*(domains or [])))

        group_by_sequence = []
        for candidate in (group_by_seq or []):
            ctx = req.session.eval_context(candidate, context)
            group_by = ctx.get('group_by')
            if not group_by:
                continue
            elif isinstance(group_by, basestring):
                group_by_sequence.append(group_by)
            else:
                group_by_sequence.extend(group_by)

        return {
            'context': context,
            'domain': domain,
            'group_by': group_by_sequence
        }

    @openerpweb.jsonrequest
    def save_session_action(self, req, the_action):
        """
        This method store an action object in the session object and returns an integer
        identifying that action. The method get_session_action() can be used to get
        back the action.

        :param the_action: The action to save in the session.
        :type the_action: anything
        :return: A key identifying the saved action.
        :rtype: integer
        """
        saved_actions = req.httpsession.get('saved_actions')
        if not saved_actions:
            saved_actions = {"next":0, "actions":{}}
            req.httpsession['saved_actions'] = saved_actions
        # we don't allow more than 10 stored actions
        if len(saved_actions["actions"]) >= 10:
            del saved_actions["actions"][min(saved_actions["actions"])]
        key = saved_actions["next"]
        saved_actions["actions"][key] = the_action
        saved_actions["next"] = key + 1
        return key

    @openerpweb.jsonrequest
    def get_session_action(self, req, key):
        """
        Gets back a previously saved action. This method can return None if the action
        was saved since too much time (this case should be handled in a smart way).

        :param key: The key given by save_session_action()
        :type key: integer
        :return: The saved action or None.
        :rtype: anything
        """
        saved_actions = req.httpsession.get('saved_actions')
        if not saved_actions:
            return None
        return saved_actions["actions"].get(key)

    @openerpweb.jsonrequest
    def check(self, req):
        req.session.assert_valid()
        return None

    @openerpweb.jsonrequest
    def destroy(self, req):
        req.session._suicide = True

class Menu(openerpweb.Controller):
    _cp_path = "/web/menu"

    @openerpweb.jsonrequest
    def load(self, req):
        return {'data': self.do_load(req)}

    @openerpweb.jsonrequest
    def get_user_roots(self, req):
        return self.do_get_user_roots(req)

    def do_get_user_roots(self, req):
        """ Return all root menu ids visible for the session user.

        :param req: A request object, with an OpenERP session attribute
        :type req: < session -> OpenERPSession >
        :return: the root menu ids
        :rtype: list(int)
        """
        s = req.session
        context = s.eval_context(req.context)
        Menus = s.model('ir.ui.menu')
        # If a menu action is defined use its domain to get the root menu items
        user_menu_id = s.model('res.users').read([s._uid], ['menu_id'], context)[0]['menu_id']

        menu_domain = [('parent_id', '=', False)]
        if user_menu_id:
            domain_string = s.model('ir.actions.act_window').read([user_menu_id[0]], ['domain'], context)[0]['domain']
            if domain_string:
                menu_domain = ast.literal_eval(domain_string)

        return Menus.search(menu_domain, 0, False, False, context)

    def do_load(self, req):
        """ Loads all menu items (all applications and their sub-menus).

        :param req: A request object, with an OpenERP session attribute
        :type req: < session -> OpenERPSession >
        :return: the menu root
        :rtype: dict('children': menu_nodes)
        """
        context = req.session.eval_context(req.context)
        Menus = req.session.model('ir.ui.menu')

        menu_roots = Menus.read(self.do_get_user_roots(req), ['name', 'sequence', 'parent_id', 'action', 'needaction_enabled', 'needaction_counter'], context)
        menu_root = {'id': False, 'name': 'root', 'parent_id': [-1, ''], 'children' : menu_roots}

        # menus are loaded fully unlike a regular tree view, cause there are a
        # limited number of items (752 when all 6.1 addons are installed)
        menu_ids = Menus.search([], 0, False, False, context)
        menu_items = Menus.read(menu_ids, ['name', 'sequence', 'parent_id', 'action', 'needaction_enabled', 'needaction_counter'], context)
        # adds roots at the end of the sequence, so that they will overwrite
        # equivalent menu items from full menu read when put into id:item
        # mapping, resulting in children being correctly set on the roots.
        menu_items.extend(menu_roots)

        # make a tree using parent_id
        menu_items_map = dict((menu_item["id"], menu_item) for menu_item in menu_items)
        for menu_item in menu_items:
            if menu_item['parent_id']:
                parent = menu_item['parent_id'][0]
            else:
                parent = False
            if parent in menu_items_map:
                menu_items_map[parent].setdefault(
                    'children', []).append(menu_item)

        # sort by sequence a tree using parent_id
        for menu_item in menu_items:
            menu_item.setdefault('children', []).sort(
                key=operator.itemgetter('sequence'))

        return menu_root

    @openerpweb.jsonrequest
    def action(self, req, menu_id):
        actions = load_actions_from_ir_values(req,'action', 'tree_but_open',
                                             [('ir.ui.menu', menu_id)], False)
        return {"action": actions}

class DataSet(openerpweb.Controller):
    _cp_path = "/web/dataset"

    @openerpweb.jsonrequest
    def search_read(self, req, model, fields=False, offset=0, limit=False, domain=None, sort=None):
        return self.do_search_read(req, model, fields, offset, limit, domain, sort)
    def do_search_read(self, req, model, fields=False, offset=0, limit=False, domain=None
                       , sort=None):
        """ Performs a search() followed by a read() (if needed) using the
        provided search criteria

        :param req: a JSON-RPC request object
        :type req: openerpweb.JsonRequest
        :param str model: the name of the model to search on
        :param fields: a list of the fields to return in the result records
        :type fields: [str]
        :param int offset: from which index should the results start being returned
        :param int limit: the maximum number of records to return
        :param list domain: the search domain for the query
        :param list sort: sorting directives
        :returns: A structure (dict) with two keys: ids (all the ids matching
                  the (domain, context) pair) and records (paginated records
                  matching fields selection set)
        :rtype: list
        """
        Model = req.session.model(model)

        context, domain = eval_context_and_domain(
            req.session, req.context, domain)

        ids = Model.search(domain, offset or 0, limit or False, sort or False, context)
        if limit and len(ids) == limit:
            length = Model.search_count(domain, context)
        else:
            length = len(ids) + (offset or 0)
        if fields and fields == ['id']:
            # shortcut read if we only want the ids
            return {
                'length': length,
                'records': [{'id': id} for id in ids]
            }

        records = Model.read(ids, fields or False, context)
        records.sort(key=lambda obj: ids.index(obj['id']))
        return {
            'length': length,
            'records': records
        }

    @openerpweb.jsonrequest
    def load(self, req, model, id, fields):
        m = req.session.model(model)
        value = {}
        r = m.read([id], False, req.session.eval_context(req.context))
        if r:
            value = r[0]
        return {'value': value}

    def call_common(self, req, model, method, args, domain_id=None, context_id=None):
        has_domain = domain_id is not None and domain_id < len(args)
        has_context = context_id is not None and context_id < len(args)

        domain = args[domain_id] if has_domain else []
        context = args[context_id] if has_context else {}
        c, d = eval_context_and_domain(req.session, context, domain)
        if has_domain:
            args[domain_id] = d
        if has_context:
            args[context_id] = c

        return self._call_kw(req, model, method, args, {})
    
    def _call_kw(self, req, model, method, args, kwargs):
        for i in xrange(len(args)):
            if isinstance(args[i], nonliterals.BaseContext):
                args[i] = req.session.eval_context(args[i])
            elif isinstance(args[i], nonliterals.BaseDomain):
                args[i] = req.session.eval_domain(args[i])
        for k in kwargs.keys():
            if isinstance(kwargs[k], nonliterals.BaseContext):
                kwargs[k] = req.session.eval_context(kwargs[k])
            elif isinstance(kwargs[k], nonliterals.BaseDomain):
                kwargs[k] = req.session.eval_domain(kwargs[k])

        # Temporary implements future display_name special field for model#read()
        if method == 'read' and kwargs.get('context') and kwargs['context'].get('future_display_name'):
            if 'display_name' in args[1]:
                names = req.session.model(model).name_get(args[0], **kwargs)
                args[1].remove('display_name')
                r = getattr(req.session.model(model), method)(*args, **kwargs)
                for i in range(len(r)):
                    r[i]['display_name'] = names[i][1] or "%s#%d" % (model, names[i][0])
                return r

        return getattr(req.session.model(model), method)(*args, **kwargs)

    @openerpweb.jsonrequest
    def onchange(self, req, model, method, args, context_id=None):
        """ Support method for handling onchange calls: behaves much like call
        with the following differences:

        * Does not take a domain_id
        * Is aware of the return value's structure, and will parse the domains
          if needed in order to return either parsed literal domains (in JSON)
          or non-literal domain instances, allowing those domains to be used
          from JS

        :param req:
        :type req: web.common.http.JsonRequest
        :param str model: object type on which to call the method
        :param str method: name of the onchange handler method
        :param list args: arguments to call the onchange handler with
        :param int context_id: index of the context object in the list of
                               arguments
        :return: result of the onchange call with all domains parsed
        """
        result = self.call_common(req, model, method, args, context_id=context_id)
        if not result or 'domain' not in result:
            return result

        result['domain'] = dict(
            (k, parse_domain(v, req.session))
            for k, v in result['domain'].iteritems())

        return result

    @openerpweb.jsonrequest
    def call(self, req, model, method, args, domain_id=None, context_id=None):
        return self.call_common(req, model, method, args, domain_id, context_id)
    
    @openerpweb.jsonrequest
    def call_kw(self, req, model, method, args, kwargs):
        return self._call_kw(req, model, method, args, kwargs)

    @openerpweb.jsonrequest
    def call_button(self, req, model, method, args, domain_id=None, context_id=None):
        action = self.call_common(req, model, method, args, domain_id, context_id)
        if isinstance(action, dict) and action.get('type') != '':
            return clean_action(req, action)
        return False

    @openerpweb.jsonrequest
    def exec_workflow(self, req, model, id, signal):
        return req.session.exec_workflow(model, id, signal)

    @openerpweb.jsonrequest
    def resequence(self, req, model, ids, field='sequence', offset=0):
        """ Re-sequences a number of records in the model, by their ids

        The re-sequencing starts at the first model of ``ids``, the sequence
        number is incremented by one after each record and starts at ``offset``

        :param ids: identifiers of the records to resequence, in the new sequence order
        :type ids: list(id)
        :param str field: field used for sequence specification, defaults to
                          "sequence"
        :param int offset: sequence number for first record in ``ids``, allows
                           starting the resequencing from an arbitrary number,
                           defaults to ``0``
        """
        m = req.session.model(model)
        if not m.fields_get([field]):
            return False
        # python 2.6 has no start parameter
        for i, id in enumerate(ids):
            m.write(id, { field: i + offset })
        return True

class View(openerpweb.Controller):
    _cp_path = "/web/view"

    def fields_view_get(self, req, model, view_id, view_type,
                        transform=True, toolbar=False, submenu=False):
        Model = req.session.model(model)
        context = req.session.eval_context(req.context)
        fvg = Model.fields_view_get(view_id, view_type, context, toolbar, submenu)
        # todo fme?: check that we should pass the evaluated context here
        self.process_view(req.session, fvg, context, transform, (view_type == 'kanban'))
        if toolbar and transform:
            self.process_toolbar(req, fvg['toolbar'])
        return fvg

    def process_view(self, session, fvg, context, transform, preserve_whitespaces=False):
        # depending on how it feels, xmlrpclib.ServerProxy can translate
        # XML-RPC strings to ``str`` or ``unicode``. ElementTree does not
        # enjoy unicode strings which can not be trivially converted to
        # strings, and it blows up during parsing.

        # So ensure we fix this retardation by converting view xml back to
        # bit strings.
        if isinstance(fvg['arch'], unicode):
            arch = fvg['arch'].encode('utf-8')
        else:
            arch = fvg['arch']
        fvg['arch_string'] = arch

        if transform:
            evaluation_context = session.evaluation_context(context or {})
            xml = self.transform_view(arch, session, evaluation_context)
        else:
            xml = ElementTree.fromstring(arch)
        fvg['arch'] = xml2json_from_elementtree(xml, preserve_whitespaces)

        if 'id' in fvg['fields']:
            # Special case for id's
            id_field = fvg['fields']['id']
            id_field['original_type'] = id_field['type']
            id_field['type'] = 'id'

        for field in fvg['fields'].itervalues():
            if field.get('views'):
                for view in field["views"].itervalues():
                    self.process_view(session, view, None, transform)
            if field.get('domain'):
                field["domain"] = parse_domain(field["domain"], session)
            if field.get('context'):
                field["context"] = parse_context(field["context"], session)

    def process_toolbar(self, req, toolbar):
        """
        The toolbar is a mapping of section_key: [action_descriptor]

        We need to clean all those actions in order to ensure correct
        round-tripping
        """
        for actions in toolbar.itervalues():
            for action in actions:
                if 'context' in action:
                    action['context'] = parse_context(
                        action['context'], req.session)
                if 'domain' in action:
                    action['domain'] = parse_domain(
                        action['domain'], req.session)

    @openerpweb.jsonrequest
    def add_custom(self, req, view_id, arch):
        CustomView = req.session.model('ir.ui.view.custom')
        CustomView.create({
            'user_id': req.session._uid,
            'ref_id': view_id,
            'arch': arch
        }, req.session.eval_context(req.context))
        return {'result': True}

    @openerpweb.jsonrequest
    def undo_custom(self, req, view_id, reset=False):
        CustomView = req.session.model('ir.ui.view.custom')
        context = req.session.eval_context(req.context)
        vcustom = CustomView.search([('user_id', '=', req.session._uid), ('ref_id' ,'=', view_id)],
                                    0, False, False, context)
        if vcustom:
            if reset:
                CustomView.unlink(vcustom, context)
            else:
                CustomView.unlink([vcustom[0]], context)
            return {'result': True}
        return {'result': False}

    def transform_view(self, view_string, session, context=None):
        # transform nodes on the fly via iterparse, instead of
        # doing it statically on the parsing result
        parser = ElementTree.iterparse(StringIO(view_string), events=("start",))
        root = None
        for event, elem in parser:
            if event == "start":
                if root is None:
                    root = elem
                self.parse_domains_and_contexts(elem, session)
        return root

    def parse_domains_and_contexts(self, elem, session):
        """ Converts domains and contexts from the view into Python objects,
        either literals if they can be parsed by literal_eval or a special
        placeholder object if the domain or context refers to free variables.

        :param elem: the current node being parsed
        :type param: xml.etree.ElementTree.Element
        :param session: OpenERP session object, used to store and retrieve
                        non-literal objects
        :type session: openerpweb.openerpweb.OpenERPSession
        """
        for el in ['domain', 'filter_domain']:
            domain = elem.get(el, '').strip()
            if domain:
                elem.set(el, parse_domain(domain, session))
                elem.set(el + '_string', domain)
        for el in ['context', 'default_get']:
            context_string = elem.get(el, '').strip()
            if context_string:
                elem.set(el, parse_context(context_string, session))
                elem.set(el + '_string', context_string)

    @openerpweb.jsonrequest
    def load(self, req, model, view_id, view_type, toolbar=False):
        return self.fields_view_get(req, model, view_id, view_type, toolbar=toolbar)

class TreeView(View):
    _cp_path = "/web/treeview"

    @openerpweb.jsonrequest
    def action(self, req, model, id):
        return load_actions_from_ir_values(
            req,'action', 'tree_but_open',[(model, id)],
            False)

class SearchView(View):
    _cp_path = "/web/searchview"

    @openerpweb.jsonrequest
    def load(self, req, model, view_id):
        fields_view = self.fields_view_get(req, model, view_id, 'search')
        return {'fields_view': fields_view}

    @openerpweb.jsonrequest
    def fields_get(self, req, model):
        Model = req.session.model(model)
        fields = Model.fields_get(False, req.session.eval_context(req.context))
        for field in fields.values():
            # shouldn't convert the views too?
            if field.get('domain'):
                field["domain"] = parse_domain(field["domain"], req.session)
            if field.get('context'):
                field["context"] = parse_context(field["context"], req.session)
        return {'fields': fields}

    @openerpweb.jsonrequest
    def get_filters(self, req, model):
        logger = logging.getLogger(__name__ + '.SearchView.get_filters')
        Model = req.session.model("ir.filters")
        filters = Model.get_filters(model)
        for filter in filters:
            try:
                parsed_context = parse_context(filter["context"], req.session)
                filter["context"] = (parsed_context
                        if not isinstance(parsed_context, nonliterals.BaseContext)
                        else req.session.eval_context(parsed_context))

                parsed_domain = parse_domain(filter["domain"], req.session)
                filter["domain"] = (parsed_domain
                        if not isinstance(parsed_domain, nonliterals.BaseDomain)
                        else req.session.eval_domain(parsed_domain))
            except Exception:
                logger.exception("Failed to parse custom filter %s in %s",
                                 filter['name'], model)
                filter['disabled'] = True
                del filter['context']
                del filter['domain']
        return filters

class Binary(openerpweb.Controller):
    _cp_path = "/web/binary"

    @openerpweb.httprequest
    def image(self, req, model, id, field, **kw):
        last_update = '__last_update'
        Model = req.session.model(model)
        context = req.session.eval_context(req.context)
        headers = [('Content-Type', 'image/png')]
        etag = req.httprequest.headers.get('If-None-Match')
        hashed_session = hashlib.md5(req.session_id).hexdigest()
        id = None if not id else simplejson.loads(id)
        if type(id) is list:
            id = id[0] # m2o
        if etag:
            if not id and hashed_session == etag:
                return werkzeug.wrappers.Response(status=304)
            else:
                date = Model.read([id], [last_update], context)[0].get(last_update)
                if hashlib.md5(date).hexdigest() == etag:
                    return werkzeug.wrappers.Response(status=304)

        retag = hashed_session
        try:
            if not id:
                res = Model.default_get([field], context).get(field)
                image_base64 = res
            else:
                res = Model.read([id], [last_update, field], context)[0]
                retag = hashlib.md5(res.get(last_update)).hexdigest()
                image_base64 = res.get(field)

            if kw.get('resize'):
                resize = kw.get('resize').split(',');
                if len(resize) == 2 and int(resize[0]) and int(resize[1]):
                    width = int(resize[0])
                    height = int(resize[1])
                    # resize maximum 500*500
                    if width > 500: width = 500
                    if height > 500: height = 500
                    image_base64 = openerp.tools.image_resize_image(base64_source=image_base64, size=(width, height), encoding='base64', filetype='PNG')
            
            image_data = base64.b64decode(image_base64)

        except (TypeError, xmlrpclib.Fault):
            image_data = self.placeholder(req)
        headers.append(('ETag', retag))
        headers.append(('Content-Length', len(image_data)))
        try:
            ncache = int(kw.get('cache'))
            headers.append(('Cache-Control', 'no-cache' if ncache == 0 else 'max-age=%s' % (ncache)))
        except:
            pass
        return req.make_response(image_data, headers)
    def placeholder(self, req):
        addons_path = openerpweb.addons_manifest['web']['addons_path']
        return open(os.path.join(addons_path, 'web', 'static', 'src', 'img', 'placeholder.png'), 'rb').read()

    @openerpweb.httprequest
    def saveas(self, req, model, field, id=None, filename_field=None, **kw):
        """ Download link for files stored as binary fields.

        If the ``id`` parameter is omitted, fetches the default value for the
        binary field (via ``default_get``), otherwise fetches the field for
        that precise record.

        :param req: OpenERP request
        :type req: :class:`web.common.http.HttpRequest`
        :param str model: name of the model to fetch the binary from
        :param str field: binary field
        :param str id: id of the record from which to fetch the binary
        :param str filename_field: field holding the file's name, if any
        :returns: :class:`werkzeug.wrappers.Response`
        """
        Model = req.session.model(model)
        context = req.session.eval_context(req.context)
        fields = [field]
        if filename_field:
            fields.append(filename_field)
        if id:
            res = Model.read([int(id)], fields, context)[0]
        else:
            res = Model.default_get(fields, context)
        filecontent = base64.b64decode(res.get(field, ''))
        if not filecontent:
            return req.not_found()
        else:
            filename = '%s_%s' % (model.replace('.', '_'), id)
            if filename_field:
                filename = res.get(filename_field, '') or filename
            return req.make_response(filecontent,
                [('Content-Type', 'application/octet-stream'),
                 ('Content-Disposition', content_disposition(filename, req))])

    @openerpweb.httprequest
    def saveas_ajax(self, req, data, token):
        jdata = simplejson.loads(data)
        model = jdata['model']
        field = jdata['field']
        id = jdata.get('id', None)
        filename_field = jdata.get('filename_field', None)
        context = jdata.get('context', dict())

        context = req.session.eval_context(context)
        Model = req.session.model(model)
        fields = [field]
        if filename_field:
            fields.append(filename_field)
        if id:
            res = Model.read([int(id)], fields, context)[0]
        else:
            res = Model.default_get(fields, context)
        filecontent = base64.b64decode(res.get(field, ''))
        if not filecontent:
            raise ValueError("No content found for field '%s' on '%s:%s'" %
                (field, model, id))
        else:
            filename = '%s_%s' % (model.replace('.', '_'), id)
            if filename_field:
                filename = res.get(filename_field, '') or filename
            return req.make_response(filecontent,
                headers=[('Content-Type', 'application/octet-stream'),
                        ('Content-Disposition', content_disposition(filename, req))],
                cookies={'fileToken': int(token)})

    @openerpweb.httprequest
    def upload(self, req, callback, ufile):
        # TODO: might be useful to have a configuration flag for max-length file uploads
        try:
            out = """<script language="javascript" type="text/javascript">
                        var win = window.top.window;
                        win.jQuery(win).trigger(%s, %s);
                    </script>"""
            data = ufile.read()
            args = [len(data), ufile.filename,
                    ufile.content_type, base64.b64encode(data)]
        except Exception, e:
            args = [False, e.message]
        return out % (simplejson.dumps(callback), simplejson.dumps(args))

    @openerpweb.httprequest
    def upload_attachment(self, req, callback, model, id, ufile):
        context = req.session.eval_context(req.context)
        Model = req.session.model('ir.attachment')
        try:
            out = """<script language="javascript" type="text/javascript">
                        var win = window.top.window;
                        win.jQuery(win).trigger(%s, %s);
                    </script>"""
            attachment_id = Model.create({
                'name': ufile.filename,
                'datas': base64.encodestring(ufile.read()),
                'datas_fname': ufile.filename,
                'res_model': model,
                'res_id': int(id)
            }, context)
            args = {
                'filename': ufile.filename,
                'id':  attachment_id
            }
        except Exception, e:
            args = { 'error': e.message }
        return out % (simplejson.dumps(callback), simplejson.dumps(args))

class Action(openerpweb.Controller):
    _cp_path = "/web/action"

    @openerpweb.jsonrequest
    def load(self, req, action_id, do_not_eval=False):
        Actions = req.session.model('ir.actions.actions')
        value = False
        context = req.session.eval_context(req.context)

        try:
            action_id = int(action_id)
        except ValueError:
            try:
                module, xmlid = action_id.split('.', 1)
                model, action_id = req.session.model('ir.model.data').get_object_reference(module, xmlid)
                assert model.startswith('ir.actions.')
            except Exception:
                action_id = 0   # force failed read

        base_action = Actions.read([action_id], ['type'], context)
        if base_action:
            ctx = {}
            action_type = base_action[0]['type']
            if action_type == 'ir.actions.report.xml':
                ctx.update({'bin_size': True})
            ctx.update(context)
            action = req.session.model(action_type).read([action_id], False, ctx)
            if action:
                value = clean_action(req, action[0], do_not_eval)
        return value

    @openerpweb.jsonrequest
    def run(self, req, action_id):
        return_action = req.session.model('ir.actions.server').run(
            [action_id], req.session.eval_context(req.context))
        if return_action:
            return clean_action(req, return_action)
        else:
            return False

class Export(View):
    _cp_path = "/web/export"

    @openerpweb.jsonrequest
    def formats(self, req):
        """ Returns all valid export formats

        :returns: for each export format, a pair of identifier and printable name
        :rtype: [(str, str)]
        """
        return sorted([
            controller.fmt
            for path, controller in openerpweb.controllers_path.iteritems()
            if path.startswith(self._cp_path)
            if hasattr(controller, 'fmt')
        ], key=operator.itemgetter("label"))

    def fields_get(self, req, model):
        Model = req.session.model(model)
        fields = Model.fields_get(False, req.session.eval_context(req.context))
        return fields

    @openerpweb.jsonrequest
    def get_fields(self, req, model, prefix='', parent_name= '',
                   import_compat=True, parent_field_type=None,
                   exclude=None):

        if import_compat and parent_field_type == "many2one":
            fields = {}
        else:
            fields = self.fields_get(req, model)

        if import_compat:
            fields.pop('id', None)
        else:
            fields['.id'] = fields.pop('id', {'string': 'ID'})

        fields_sequence = sorted(fields.iteritems(),
            key=lambda field: field[1].get('string', ''))

        records = []
        for field_name, field in fields_sequence:
            if import_compat:
                if exclude and field_name in exclude:
                    continue
                if field.get('readonly'):
                    # If none of the field's states unsets readonly, skip the field
                    if all(dict(attrs).get('readonly', True)
                           for attrs in field.get('states', {}).values()):
                        continue

            id = prefix + (prefix and '/'or '') + field_name
            name = parent_name + (parent_name and '/' or '') + field['string']
            record = {'id': id, 'string': name,
                      'value': id, 'children': False,
                      'field_type': field.get('type'),
                      'required': field.get('required'),
                      'relation_field': field.get('relation_field')}
            records.append(record)

            if len(name.split('/')) < 3 and 'relation' in field:
                ref = field.pop('relation')
                record['value'] += '/id'
                record['params'] = {'model': ref, 'prefix': id, 'name': name}

                if not import_compat or field['type'] == 'one2many':
                    # m2m field in import_compat is childless
                    record['children'] = True

        return records

    @openerpweb.jsonrequest
    def namelist(self,req,  model, export_id):
        # TODO: namelist really has no reason to be in Python (although itertools.groupby helps)
        export = req.session.model("ir.exports").read([export_id])[0]
        export_fields_list = req.session.model("ir.exports.line").read(
            export['export_fields'])

        fields_data = self.fields_info(
            req, model, map(operator.itemgetter('name'), export_fields_list))

        return [
            {'name': field['name'], 'label': fields_data[field['name']]}
            for field in export_fields_list
        ]

    def fields_info(self, req, model, export_fields):
        info = {}
        fields = self.fields_get(req, model)

        # To make fields retrieval more efficient, fetch all sub-fields of a
        # given field at the same time. Because the order in the export list is
        # arbitrary, this requires ordering all sub-fields of a given field
        # together so they can be fetched at the same time
        #
        # Works the following way:
        # * sort the list of fields to export, the default sorting order will
        #   put the field itself (if present, for xmlid) and all of its
        #   sub-fields right after it
        # * then, group on: the first field of the path (which is the same for
        #   a field and for its subfields and the length of splitting on the
        #   first '/', which basically means grouping the field on one side and
        #   all of the subfields on the other. This way, we have the field (for
        #   the xmlid) with length 1, and all of the subfields with the same
        #   base but a length "flag" of 2
        # * if we have a normal field (length 1), just add it to the info
        #   mapping (with its string) as-is
        # * otherwise, recursively call fields_info via graft_subfields.
        #   all graft_subfields does is take the result of fields_info (on the
        #   field's model) and prepend the current base (current field), which
        #   rebuilds the whole sub-tree for the field
        #
        # result: because we're not fetching the fields_get for half the
        # database models, fetching a namelist with a dozen fields (including
        # relational data) falls from ~6s to ~300ms (on the leads model).
        # export lists with no sub-fields (e.g. import_compatible lists with
        # no o2m) are even more efficient (from the same 6s to ~170ms, as
        # there's a single fields_get to execute)
        for (base, length), subfields in itertools.groupby(
                sorted(export_fields),
                lambda field: (field.split('/', 1)[0], len(field.split('/', 1)))):
            subfields = list(subfields)
            if length == 2:
                # subfields is a seq of $base/*rest, and not loaded yet
                info.update(self.graft_subfields(
                    req, fields[base]['relation'], base, fields[base]['string'],
                    subfields
                ))
            else:
                info[base] = fields[base]['string']

        return info

    def graft_subfields(self, req, model, prefix, prefix_string, fields):
        export_fields = [field.split('/', 1)[1] for field in fields]
        return (
            (prefix + '/' + k, prefix_string + '/' + v)
            for k, v in self.fields_info(req, model, export_fields).iteritems())

    #noinspection PyPropertyDefinition
    @property
    def content_type(self):
        """ Provides the format's content type """
        raise NotImplementedError()

    def filename(self, base):
        """ Creates a valid filename for the format (with extension) from the
         provided base name (exension-less)
        """
        raise NotImplementedError()

    def from_data(self, fields, rows):
        """ Conversion method from OpenERP's export data to whatever the
        current export class outputs

        :params list fields: a list of fields to export
        :params list rows: a list of records to export
        :returns:
        :rtype: bytes
        """
        raise NotImplementedError()

    @openerpweb.httprequest
    def index(self, req, data, token):
        model, fields, ids, domain, import_compat = \
            operator.itemgetter('model', 'fields', 'ids', 'domain',
                                'import_compat')(
                simplejson.loads(data))

        context = req.session.eval_context(req.context)
        Model = req.session.model(model)
        ids = ids or Model.search(domain, 0, False, False, context)

        field_names = map(operator.itemgetter('name'), fields)
        import_data = Model.export_data(ids, field_names, context).get('datas',[])

        if import_compat:
            columns_headers = field_names
        else:
            columns_headers = [val['label'].strip() for val in fields]


        return req.make_response(self.from_data(columns_headers, import_data),
            headers=[('Content-Disposition',
                            content_disposition(self.filename(model), req)),
                     ('Content-Type', self.content_type)],
            cookies={'fileToken': int(token)})

class CSVExport(Export):
    _cp_path = '/web/export/csv'
    fmt = {'tag': 'csv', 'label': 'CSV'}

    @property
    def content_type(self):
        return 'text/csv;charset=utf8'

    def filename(self, base):
        return base + '.csv'

    def from_data(self, fields, rows):
        fp = StringIO()
        writer = csv.writer(fp, quoting=csv.QUOTE_ALL)

        writer.writerow([name.encode('utf-8') for name in fields])

        for data in rows:
            row = []
            for d in data:
                if isinstance(d, basestring):
                    d = d.replace('\n',' ').replace('\t',' ')
                    try:
                        d = d.encode('utf-8')
                    except UnicodeError:
                        pass
                if d is False: d = None
                row.append(d)
            writer.writerow(row)

        fp.seek(0)
        data = fp.read()
        fp.close()
        return data

class ExcelExport(Export):
    _cp_path = '/web/export/xls'
    fmt = {
        'tag': 'xls',
        'label': 'Excel',
        'error': None if xlwt else "XLWT required"
    }

    @property
    def content_type(self):
        return 'application/vnd.ms-excel'

    def filename(self, base):
        return base + '.xls'

    def from_data(self, fields, rows):
        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet('Sheet 1')

        for i, fieldname in enumerate(fields):
            worksheet.write(0, i, fieldname)
            worksheet.col(i).width = 8000 # around 220 pixels

        style = xlwt.easyxf('align: wrap yes')

        for row_index, row in enumerate(rows):
            for cell_index, cell_value in enumerate(row):
                if isinstance(cell_value, basestring):
                    cell_value = re.sub("\r", " ", cell_value)
                if cell_value is False: cell_value = None
                worksheet.write(row_index + 1, cell_index, cell_value, style)

        fp = StringIO()
        workbook.save(fp)
        fp.seek(0)
        data = fp.read()
        fp.close()
        return data

class Reports(View):
    _cp_path = "/web/report"
    POLLING_DELAY = 0.25
    TYPES_MAPPING = {
        'doc': 'application/vnd.ms-word',
        'html': 'text/html',
        'odt': 'application/vnd.oasis.opendocument.text',
        'pdf': 'application/pdf',
        'sxw': 'application/vnd.sun.xml.writer',
        'xls': 'application/vnd.ms-excel',
    }

    @openerpweb.httprequest
    def index(self, req, action, token):
        action = simplejson.loads(action)

        report_srv = req.session.proxy("report")
        context = req.session.eval_context(
            nonliterals.CompoundContext(
                req.context or {}, action[ "context"]))

        report_data = {}
        report_ids = context["active_ids"]
        if 'report_type' in action:
            report_data['report_type'] = action['report_type']
        if 'datas' in action:
            if 'ids' in action['datas']:
                report_ids = action['datas'].pop('ids')
            report_data.update(action['datas'])

        report_id = report_srv.report(
            req.session._db, req.session._uid, req.session._password,
            action["report_name"], report_ids,
            report_data, context)

        report_struct = None
        while True:
            report_struct = report_srv.report_get(
                req.session._db, req.session._uid, req.session._password, report_id)
            if report_struct["state"]:
                break

            time.sleep(self.POLLING_DELAY)

        report = base64.b64decode(report_struct['result'])
        if report_struct.get('code') == 'zlib':
            report = zlib.decompress(report)
        report_mimetype = self.TYPES_MAPPING.get(
            report_struct['format'], 'octet-stream')
        file_name = action.get('name', 'report')
        if 'name' not in action:
            reports = req.session.model('ir.actions.report.xml')
            res_id = reports.search([('report_name', '=', action['report_name']),],
                                    0, False, False, context)
            if len(res_id) > 0:
                file_name = reports.read(res_id[0], ['name'], context)['name']
            else:
                file_name = action['report_name']
        file_name = '%s.%s' % (file_name, report_struct['format'])

        return req.make_response(report,
             headers=[
                 ('Content-Disposition', content_disposition(file_name, req)),
                 ('Content-Type', report_mimetype),
                 ('Content-Length', len(report))],
             cookies={'fileToken': int(token)})

# vim:expandtab:tabstop=4:softtabstop=4:shiftwidth=4:
