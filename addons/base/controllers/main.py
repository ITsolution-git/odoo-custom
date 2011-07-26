# -*- coding: utf-8 -*-

import base64, glob, os, re
from xml.etree import ElementTree
from cStringIO import StringIO

import simplejson

import openerpweb
import openerpweb.ast
import openerpweb.nonliterals

import cherrypy
import xmlrpclib

# Should move to openerpweb.Xml2Json
class Xml2Json:
    # xml2json-direct
    # Simple and straightforward XML-to-JSON converter in Python
    # New BSD Licensed
    #
    # URL: http://code.google.com/p/xml2json-direct/
    @staticmethod
    def convert_to_json(s):
        return simplejson.dumps(
            Xml2Json.convert_to_structure(s), sort_keys=True, indent=4)

    @staticmethod
    def convert_to_structure(s):
        root = ElementTree.fromstring(s)
        return Xml2Json.convert_element(root)

    @staticmethod
    def convert_element(el, skip_whitespaces=True):
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
        if el.text and (not skip_whitespaces or el.text.strip() != ''):
            kids.append(el.text)
        for kid in el:
            kids.append(Xml2Json.convert_element(kid))
            if kid.tail and (not skip_whitespaces or kid.tail.strip() != ''):
                kids.append(kid.tail)
        res["children"] = kids
        return res

#----------------------------------------------------------
# OpenERP Web base Controllers
#----------------------------------------------------------

class DatabaseCreationError(Exception): pass
class DatabaseCreationCrash(DatabaseCreationError): pass

class Database(openerpweb.Controller):
    _cp_path = "/base/database"

    @openerpweb.jsonrequest
    def get_databases_list(self, req):
        proxy = req.session.proxy("db")
        dbs = proxy.list()
        h = req.httprequest.headers['Host'].split(':')[0]
        d = h.split('.')[0]
        r = cherrypy.config['openerp.dbfilter'].replace('%h', h).replace('%d', d)
        dbs = [i for i in dbs if re.match(r, i)]
        return {"db_list": dbs}
    
    @openerpweb.jsonrequest
    def create_db(self, req, **kw):
        
        super_admin_pwd = kw.get('super_admin_pwd')
        dbname = kw.get('db') 
        demo_data = kw.get('demo_data')
        db_lang = kw.get('db_lang')
        admin_pwd = kw.get('admin_pwd')
        confirm_pwd = kw.get('confirm_pwd')
        
        if not re.match('^[a-zA-Z][a-zA-Z0-9_]+$', dbname):
            return {'error': "You must avoid all accents, space or special characters.", 'title': 'Bad database name'}
        
        ok = False
        try:
            return req.session.proxy("db").create(super_admin_pwd, dbname, demo_data, db_lang, admin_pwd)
#                while True:
#                    try:
#                        progress, users = req.session.proxy('db').get_progress(super_admin_pwd, res)
#                        if progress == 1.0:
#                            for x in users:
#                                if x['login'] == 'admin':
#                                    req.session.login(dbname, 'admin', x['password'])
#                                    ok = True
#                            break
#                        else:
#                            time.sleep(1)
#                    except:
#                        raise DatabaseCreationCrash()
#            except DatabaseCreationCrash:
#                return {'error': "The server crashed during installation.\nWe suggest you to drop this database.",
#                        'title': 'Error during database creation'}
        except Exception, e:
            if e.faultCode and e.faultCode.split(':')[0] == 'AccessDenied':
                return {'error': 'Bad super admin password !', 'title': 'Create Database'}
            else:
                return {'error': 'Could not create database !', 'title': 'Create Database'}

    @openerpweb.jsonrequest
    def drop_db(self, req, **kw):
        db = kw.get('db')
        password = kw.get('password')
        
        try:
            return req.session.proxy("db").drop(password, db)
        except Exception, e:
            if e.faultCode and e.faultCode.split(':')[0] == 'AccessDenied':
                return {'error': 'Bad super admin password !', 'title': 'Drop Database'}
            else:
                return {'error': 'Could not drop database !', 'title': 'Drop Database'}

    @openerpweb.jsonrequest
    def backup_db(self, req, **kw):
        db = kw.get('db')
        password = kw.get('password')
        try:
            res = req.session.proxy("db").dump(password, db)
            if res:
                cherrypy.response.headers['Content-Type'] = "application/data"
                cherrypy.response.headers['Content-Disposition'] = 'filename="' + db + '.dump"'
                return base64.decodestring(res)
        except Exception, e:
            if e.faultCode and e.faultCode.split(':')[0] == 'AccessDenied':
                return {'error': 'Bad super admin password !', 'title': 'Backup Database'}
            else:
                return {'error': 'Could not drop database !', 'title': 'Backup Database'}
            
    @openerpweb.jsonrequest
    def restore_db(self, req, **kw):
        filename = kw.get('filename')
        db = kw.get('db')
        password = kw.get('password')
        
        try:
            data = base64.encodestring(filename.file.read())
            return req.session.proxy("db").restore(password, db, data)
        except Exception, e:
            if e.faultCode and e.faultCode.split(':')[0] == 'AccessDenied':
                return {'error': 'Bad super admin password !', 'title': 'Restore Database'}
            else:
                return {'error': 'Could not restore database !', 'title': 'Restore Database'}
        
    @openerpweb.jsonrequest
    def change_password_db(self, req, **kw):
        old_password = kw.get('old_password')
        new_password = kw.get('new_password')
        confirm_password = kw.get('confirm_password')
        
        try:
            return req.session.proxy("db").change_admin_password(old_password, new_password)
        except Exception, e:
            if e.faultCode and e.faultCode.split(':')[0] == 'AccessDenied':
                return {'error': 'Bad super admin password !', 'title': 'Change Password'}
            else:
                return {'error': 'Error, password not changed !', 'title': 'Change Password'}

class Session(openerpweb.Controller):
    _cp_path = "/base/session"

    def manifest_glob(self, addons, key):
        files = []
        for addon in addons:
            globlist = openerpweb.addons_manifest.get(addon, {}).get(key, [])

            files.extend([
                resource_path[len(openerpweb.path_addons):]
                for pattern in globlist
                for resource_path in glob.glob(os.path.join(
                    openerpweb.path_addons, addon, pattern))
            ])
        return files

    def concat_files(self, file_list):
        """ Concatenate file content
        return (concat,timestamp)
        concat: concatenation of file content
        timestamp: max(os.path.getmtime of file_list)
        """
        root = openerpweb.path_root
        files_content = []
        files_timestamp = 0
        for i in file_list:
            fname = os.path.join(root, i)
            ftime = os.path.getmtime(fname)
            if ftime > files_timestamp:
                files_timestamp = ftime
            files_content = open(fname).read()
        files_concat = "".join(files_content)
        return files_concat

    @openerpweb.jsonrequest
    def login(self, req, db, login, password):
        req.session.login(db, login, password)

        return {
            "session_id": req.session_id,
            "uid": req.session._uid,
        }

    @openerpweb.jsonrequest
    def sc_list(self, req):
        return req.session.model('ir.ui.view_sc').get_sc(req.session._uid, "ir.ui.menu",
                                                         req.session.eval_context(req.context))

    @openerpweb.jsonrequest
    def get_lang_list(self, req):
        lang_list = [('en_US', 'English (US)')]
        try:
            lang_list = lang_list + (req.session.proxy("db").list_lang() or [])
        except Exception, e:
            pass
        return {"lang_list": lang_list}
            
    @openerpweb.jsonrequest
    def modules(self, req):
        return {"modules": [name
            for name, manifest in openerpweb.addons_manifest.iteritems()
            if manifest.get('active', True)]}

    @openerpweb.jsonrequest
    def csslist(self, req, mods='base'):
        return {'files': self.manifest_glob(mods.split(','), 'css')}

    @openerpweb.jsonrequest
    def jslist(self, req, mods='base'):
        return {'files': self.manifest_glob(mods.split(','), 'js')}

    def css(self, req, mods='base'):
        files = self.manifest_glob(mods.split(','), 'css')
        concat = self.concat_files(files)[0]
        # TODO request set the Date of last modif and Etag
        return concat
    css.exposed = True

    def js(self, req, mods='base'):
        files = self.manifest_glob(mods.split(','), 'js')
        concat = self.concat_files(files)[0]
        # TODO request set the Date of last modif and Etag
        return concat
    js.exposed = True

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
                                                  openerpweb.nonliterals.CompoundContext(*(contexts or [])),
                                                  openerpweb.nonliterals.CompoundDomain(*(domains or [])))
        
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
        saved_actions = cherrypy.session.get('saved_actions')
        if not saved_actions:
            saved_actions = {"next":0, "actions":{}}
            cherrypy.session['saved_actions'] = saved_actions
        # we don't allow more than 10 stored actions
        if len(saved_actions["actions"]) >= 10:
            del saved_actions["actions"][min(saved_actions["actions"].keys())]
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
        saved_actions = cherrypy.session.get('saved_actions')
        if not saved_actions:
            return None
        return saved_actions["actions"].get(key)

def eval_context_and_domain(session, context, domain=None):
    e_context = session.eval_context(context)
    # should we give the evaluated context as an evaluation context to the domain?
    e_domain = session.eval_domain(domain or [])

    return e_context, e_domain

def load_actions_from_ir_values(req, key, key2, models, meta, context):
    Values = req.session.model('ir.values')
    actions = Values.get(key, key2, models, meta, context)

    return [(id, name, clean_action(action, req.session))
            for id, name, action in actions]

def clean_action(action, session):
    if action['type'] != 'ir.actions.act_window':
        return action
    # values come from the server, we can just eval them
    if isinstance(action.get('context', None), basestring):
        action['context'] = eval(
            action['context'],
            session.evaluation_context()) or {}

    if isinstance(action.get('domain', None), basestring):
        action['domain'] = eval(
            action['domain'],
            session.evaluation_context(
                action.get('context', {}))) or []
    if 'flags' not in action:
        # Set empty flags dictionary for web client.
        action['flags'] = dict()
    return fix_view_modes(action)

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
    view_id = action.get('view_id', False)
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
    if 'views' not in action:
        generate_views(action)

    if action.pop('view_type') != 'form':
        return action

    action['views'] = [
        [id, mode if mode != 'tree' else 'list']
        for id, mode in action['views']
    ]

    return action

class Menu(openerpweb.Controller):
    _cp_path = "/base/menu"

    @openerpweb.jsonrequest
    def load(self, req):
        return {'data': self.do_load(req)}

    def do_load(self, req):
        """ Loads all menu items (all applications and their sub-menus).

        :param req: A request object, with an OpenERP session attribute
        :type req: < session -> OpenERPSession >
        :return: the menu root
        :rtype: dict('children': menu_nodes)
        """
        Menus = req.session.model('ir.ui.menu')
        # menus are loaded fully unlike a regular tree view, cause there are
        # less than 512 items
        context = req.session.eval_context(req.context)
        menu_ids = Menus.search([], 0, False, False, context)
        menu_items = Menus.read(menu_ids, ['name', 'sequence', 'parent_id'], context)
        menu_root = {'id': False, 'name': 'root', 'parent_id': [-1, '']}
        menu_items.append(menu_root)
        
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
                key=lambda x:x["sequence"])

        return menu_root

    @openerpweb.jsonrequest
    def action(self, req, menu_id):
        actions = load_actions_from_ir_values(req,'action', 'tree_but_open',
                                             [('ir.ui.menu', menu_id)], False,
                                             req.session.eval_context(req.context))
        return {"action": actions}

class DataSet(openerpweb.Controller):
    _cp_path = "/base/dataset"

    @openerpweb.jsonrequest
    def fields(self, req, model):
        return {'fields': req.session.model(model).fields_get(False,
                                                              req.session.eval_context(req.context))}

    @openerpweb.jsonrequest
    def search_read(self, request, model, fields=False, offset=0, limit=False, domain=None, sort=None):
        return self.do_search_read(request, model, fields, offset, limit, domain, sort)
    def do_search_read(self, request, model, fields=False, offset=0, limit=False, domain=None
                       , sort=None):
        """ Performs a search() followed by a read() (if needed) using the
        provided search criteria

        :param request: a JSON-RPC request object
        :type request: openerpweb.JsonRequest
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
        Model = request.session.model(model)
        context, domain = eval_context_and_domain(
            request.session, request.context, domain)

        ids = Model.search(domain, 0, False, sort or False, context)
        # need to fill the dataset with all ids for the (domain, context) pair,
        # so search un-paginated and paginate manually before reading
        paginated_ids = ids[offset:(offset + limit if limit else None)]
        if fields and fields == ['id']:
            # shortcut read if we only want the ids
            return {
                'ids': ids,
                'records': map(lambda id: {'id': id}, paginated_ids)
            }

        records = Model.read(paginated_ids, fields or False, context)
        records.sort(key=lambda obj: ids.index(obj['id']))
        return {
            'ids': ids,
            'records': records
        }


    @openerpweb.jsonrequest
    def get(self, request, model, ids, fields=False):
        return self.do_get(request, model, ids, fields)
    def do_get(self, request, model, ids, fields=False):
        """ Fetches and returns the records of the model ``model`` whose ids
        are in ``ids``.

        The results are in the same order as the inputs, but elements may be
        missing (if there is no record left for the id)

        :param request: the JSON-RPC2 request object
        :type request: openerpweb.JsonRequest
        :param model: the model to read from
        :type model: str
        :param ids: a list of identifiers
        :type ids: list
        :param fields: a list of fields to fetch, ``False`` or empty to fetch
                       all fields in the model
        :type fields: list | False
        :returns: a list of records, in the same order as the list of ids
        :rtype: list
        """
        Model = request.session.model(model)
        records = Model.read(ids, fields, request.session.eval_context(request.context))

        record_map = dict((record['id'], record) for record in records)

        return [record_map[id] for id in ids if record_map.get(id)]
    
    @openerpweb.jsonrequest
    def load(self, req, model, id, fields):
        m = req.session.model(model)
        value = {}
        r = m.read([id], False, req.session.eval_context(req.context))
        if r:
            value = r[0]
        return {'value': value}

    @openerpweb.jsonrequest
    def create(self, req, model, data):
        m = req.session.model(model)
        r = m.create(data, req.session.eval_context(req.context))
        return {'result': r}

    @openerpweb.jsonrequest
    def save(self, req, model, id, data):
        m = req.session.model(model)
        r = m.write([id], data, req.session.eval_context(req.context))
        return {'result': r}

    @openerpweb.jsonrequest
    def unlink(self, request, model, ids=()):
        Model = request.session.model(model)
        return Model.unlink(ids, request.session.eval_context(request.context))

    def call_common(self, req, model, method, args, domain_id=None, context_id=None):
        domain = args[domain_id] if domain_id and len(args) - 1 >= domain_id  else []
        context = args[context_id] if context_id and len(args) - 1 >= context_id  else {}
        c, d = eval_context_and_domain(req.session, context, domain)
        if domain_id and len(args) - 1 >= domain_id:
            args[domain_id] = d
        if context_id and len(args) - 1 >= context_id:
            args[context_id] = c

        return getattr(req.session.model(model), method)(*args)

    @openerpweb.jsonrequest
    def call(self, req, model, method, args, domain_id=None, context_id=None):
        return self.call_common(req, model, method, args, domain_id, context_id)

    @openerpweb.jsonrequest
    def call_button(self, req, model, method, args, domain_id=None, context_id=None):
        action = self.call_common(req, model, method, args, domain_id, context_id)
        if isinstance(action, dict) and action.get('type') != '':
            return {'result': clean_action(action, req.session)}
        return {'result': False}

    @openerpweb.jsonrequest
    def exec_workflow(self, req, model, id, signal):
        r = req.session.exec_workflow(model, id, signal)
        return {'result': r}

    @openerpweb.jsonrequest
    def default_get(self, req, model, fields):
        Model = req.session.model(model)
        return Model.default_get(fields, req.session.eval_context(req.context))

class DataGroup(openerpweb.Controller):
    _cp_path = "/base/group"
    @openerpweb.jsonrequest
    def read(self, request, model, fields, group_by_fields, domain=None, sort=None):
        Model = request.session.model(model)
        context, domain = eval_context_and_domain(request.session, request.context, domain)

        return Model.read_group(
            domain or [], fields, group_by_fields, 0, False,
            dict(context, group_by=group_by_fields), sort or False)

class View(openerpweb.Controller):
    _cp_path = "/base/view"

    def fields_view_get(self, request, model, view_id, view_type,
                        transform=True, toolbar=False, submenu=False):
        Model = request.session.model(model)
        context = request.session.eval_context(request.context)
        fvg = Model.fields_view_get(view_id, view_type, context, toolbar, submenu)
        # todo fme?: check that we should pass the evaluated context here
        self.process_view(request.session, fvg, context, transform)
        return fvg

    def process_view(self, session, fvg, context, transform):
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

        if transform:
            evaluation_context = session.evaluation_context(context or {})
            xml = self.transform_view(arch, session, evaluation_context)
        else:
            xml = ElementTree.fromstring(arch)
        fvg['arch'] = Xml2Json.convert_element(xml)

        for field in fvg['fields'].itervalues():
            if field.get('views'):
                for view in field["views"].itervalues():
                    self.process_view(session, view, None, transform)
            if field.get('domain'):
                field["domain"] = self.parse_domain(field["domain"], session)
            if field.get('context'):
                field["context"] = self.parse_context(field["context"], session)

    @openerpweb.jsonrequest
    def add_custom(self, request, view_id, arch):
        CustomView = request.session.model('ir.ui.view.custom')
        CustomView.create({
            'user_id': request.session._uid,
            'ref_id': view_id,
            'arch': arch
        }, request.session.eval_context(request.context))
        return {'result': True}

    @openerpweb.jsonrequest
    def undo_custom(self, request, view_id, reset=False):
        CustomView = request.session.model('ir.ui.view.custom')
        context = request.session.eval_context(request.context)
        vcustom = CustomView.search([('user_id', '=', request.session._uid), ('ref_id' ,'=', view_id)],
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

    def parse_domain(self, domain, session):
        """ Parses an arbitrary string containing a domain, transforms it
        to either a literal domain or a :class:`openerpweb.nonliterals.Domain`

        :param domain: the domain to parse, if the domain is not a string it is assumed to
        be a literal domain and is returned as-is
        :param session: Current OpenERP session
        :type session: openerpweb.openerpweb.OpenERPSession
        """
        if not isinstance(domain, (str, unicode)):
            return domain
        try:
            return openerpweb.ast.literal_eval(domain)
        except ValueError:
            # not a literal
            return openerpweb.nonliterals.Domain(session, domain)
        
    def parse_context(self, context, session):
        """ Parses an arbitrary string containing a context, transforms it
        to either a literal context or a :class:`openerpweb.nonliterals.Context`

        :param context: the context to parse, if the context is not a string it is assumed to
        be a literal domain and is returned as-is
        :param session: Current OpenERP session
        :type session: openerpweb.openerpweb.OpenERPSession
        """
        if not isinstance(context, (str, unicode)):
            return context
        try:
            return openerpweb.ast.literal_eval(context)
        except ValueError:
            return openerpweb.nonliterals.Context(session, context)

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
                elem.set(el, self.parse_domain(domain, session))
        for el in ['context', 'default_get']:
            context_string = elem.get(el, '').strip()
            if context_string:
                elem.set(el, self.parse_context(context_string, session))

class FormView(View):
    _cp_path = "/base/formview"

    @openerpweb.jsonrequest
    def load(self, req, model, view_id, toolbar=False):
        fields_view = self.fields_view_get(req, model, view_id, 'form', toolbar=toolbar)
        return {'fields_view': fields_view}

class ListView(View):
    _cp_path = "/base/listview"

    @openerpweb.jsonrequest
    def load(self, req, model, view_id, toolbar=False):
        fields_view = self.fields_view_get(req, model, view_id, 'tree', toolbar=toolbar)
        return {'fields_view': fields_view}

    def process_colors(self, view, row, context):
        colors = view['arch']['attrs'].get('colors')

        if not colors:
            return None

        color = [
            pair.split(':')[0]
            for pair in colors.split(';')
            if eval(pair.split(':')[1], dict(context, **row))
        ]

        if not color:
            return None
        elif len(color) == 1:
            return color[0]
        return 'maroon'

class SearchView(View):
    _cp_path = "/base/searchview"

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
                field["domain"] = self.parse_domain(field["domain"], req.session)
            if field.get('context'):
                field["context"] = self.parse_domain(field["context"], req.session)
        return {'fields': fields}

class Binary(openerpweb.Controller):
    _cp_path = "/base/binary"

    @openerpweb.httprequest
    def image(self, request, session_id, model, id, field, **kw):
        cherrypy.response.headers['Content-Type'] = 'image/png'
        Model = request.session.model(model)
        context = request.session.eval_context(request.context)
        try:
            if not id:
                res = Model.default_get([field], context).get(field, '')
            else:
                res = Model.read([int(id)], [field], context)[0].get(field, '')
            return base64.decodestring(res)
        except: # TODO: what's the exception here?
            return self.placeholder()
    def placeholder(self):
        return open(os.path.join(openerpweb.path_addons, 'base', 'static', 'src', 'img', 'placeholder.png'), 'rb').read()

    @openerpweb.httprequest
    def saveas(self, request, session_id, model, id, field, fieldname, **kw):
        Model = request.session.model(model)
        context = request.session.eval_context(request.context)
        res = Model.read([int(id)], [field, fieldname], context)[0]
        filecontent = res.get(field, '')
        if not filecontent:
            raise cherrypy.NotFound
        else:
            cherrypy.response.headers['Content-Type'] = 'application/octet-stream'
            filename = '%s_%s' % (model.replace('.', '_'), id)
            if fieldname:
                filename = res.get(fieldname, '') or filename
            cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=' +  filename
            return base64.decodestring(filecontent)

    @openerpweb.httprequest
    def upload(self, request, session_id, callback, ufile=None):
        cherrypy.response.timeout = 500
        headers = {}
        for key, val in cherrypy.request.headers.iteritems():
            headers[key.lower()] = val
        size = int(headers.get('content-length', 0))
        # TODO: might be useful to have a configuration flag for max-length file uploads
        try:
            out = """<script language="javascript" type="text/javascript">
                        var win = window.top.window,
                            callback = win[%s];
                        if (typeof(callback) === 'function') {
                            callback.apply(this, %s);
                        } else {
                            win.jQuery('#oe_notification', win.document).notify('create', {
                                title: "Ajax File Upload",
                                text: "Could not find callback"
                            });
                        }
                    </script>"""
            data = ufile.file.read()
            args = [size, ufile.filename, ufile.headers.getheader('Content-Type'), base64.encodestring(data)]
        except Exception, e:
            args = [False, e.message]
        return out % (simplejson.dumps(callback), simplejson.dumps(args))

    @openerpweb.httprequest
    def upload_attachment(self, request, session_id, callback, model, id, ufile=None):
        cherrypy.response.timeout = 500
        context = request.session.eval_context(request.context)
        Model = request.session.model('ir.attachment')
        try:
            out = """<script language="javascript" type="text/javascript">
                        var win = window.top.window,
                            callback = win[%s];
                        if (typeof(callback) === 'function') {
                            callback.call(this, %s);
                        }
                    </script>"""
            attachment_id = Model.create({
                'name': ufile.filename,
                'datas': base64.encodestring(ufile.file.read()),
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
    _cp_path = "/base/action"

    @openerpweb.jsonrequest
    def load(self, req, action_id):
        Actions = req.session.model('ir.actions.actions')
        value = False
        context = req.session.eval_context(req.context)
        action_type = Actions.read([action_id], ['type'], context)
        if action_type:
            action = req.session.model(action_type[0]['type']).read([action_id], False,
                                                                    context)
            if action:
                value = clean_action(action[0], req.session)
        return {'result': value}

    @openerpweb.jsonrequest
    def run(self, req, action_id):
        return clean_action(req.session.model('ir.actions.server').run(
            [action_id], req.session.eval_context(req.context)), req.session)

#
