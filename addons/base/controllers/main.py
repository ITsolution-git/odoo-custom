# -*- coding: utf-8 -*-
import glob, os
from xml.etree import ElementTree

import simplejson

import openerpweb


class Xml2Json:
    # xml2json-direct
    # Simple and straightforward XML-to-JSON converter in Python
    # New BSD Licensed
    #
    # URL: http://code.google.com/p/xml2json-direct/
    @staticmethod
    def convert_to_json(s):
        return simplejson.dumps(Xml2Json.convert_to_structure(s), sort_keys=True, indent=4)

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

class Session(openerpweb.Controller):
    _cp_path = "/base/session"

    def manifest_glob(self, modlist, key):
        files = []
        for i in modlist:
            globlist = openerpweb.addons_manifest.get(i, {}).get(key, [])
            for j in globlist:
                for k in glob.glob(os.path.join(openerpweb.path_addons, i, j)):
                    files.append(k[len(openerpweb.path_addons):])
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
    def modules(self, req):
        return {"modules": ["base", "base_hello", "base_calendar"]}

    @openerpweb.jsonrequest
    def csslist(self, req, mods='base,base_hello'):
        return {'files': self.manifest_glob(mods.split(','), 'css')}

    @openerpweb.jsonrequest
    def jslist(self, req, mods='base,base_hello'):
        return {'files': self.manifest_glob(mods.split(','), 'js')}

    def css(self, req, mods='base,base_hello'):
        files = self.manifest_glob(mods.split(','), 'css')
        concat = self.concat_files(files)[0]
        # TODO request set the Date of last modif and Etag
        return concat
    css.exposed = True

    def js(self, req, mods='base,base_hello'):
        files = self.manifest_glob(mods.split(','), 'js')
        concat = self.concat_files(files)[0]
        # TODO request set the Date of last modif and Etag
        return concat
    js.exposed = True


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
        menu_ids = Menus.search([])
        menu_items = Menus.read(menu_ids, ['name', 'sequence', 'parent_id'])
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
        m = req.session.model('ir.values')
        r = m.get('action', 'tree_but_open', [('ir.ui.menu', menu_id)], False, {})
        res = {"action": r}
        return res


class DataSet(openerpweb.Controller):
    _cp_path = "/base/dataset"

    @openerpweb.jsonrequest
    def fields(self, req, model):
        return {'fields': req.session.model(model).fields_get()}

    @openerpweb.jsonrequest
    def find(self, request, model, fields=False, offset=0, limit=False,
             domain=None, context=None, sort=None):
        Model = request.session.model(model)
        ids = Model.search(domain or [], offset or 0, limit or False,
                           sort or False, context or False)
        if fields and fields == ['id']:
            # shortcut read if we only want the ids
            return map(lambda id: {'id': id}, ids)
        return Model.read(ids, fields or False)


class DataRecord(openerpweb.Controller):
    _cp_path = "/base/datarecord"

    @openerpweb.jsonrequest
    def load(self, req, model, id, fields):
        m = req.session.model(model)
        value = {}
        r = m.read([id])
        if r:
            value = r[0]
        return {'value': value}


class FormView(openerpweb.Controller):
    _cp_path = "/base/formview"

    @openerpweb.jsonrequest
    def load(self, req, model, view_id):
        m = req.session.model(model)
        r = m.fields_view_get(view_id, 'form')
        r["arch"] = Xml2Json.convert_to_structure(r["arch"])
        return {'fields_view': r}


class ListView(openerpweb.Controller):
    _cp_path = "/base/listview"

    @openerpweb.jsonrequest
    def load(self, req, model, view_id):
        m = req.session.model(model)
        r = m.fields_view_get(view_id, 'tree')
        r["arch"] = Xml2Json.convert_to_structure(r["arch"])
        return {'fields_view': r}


class SearchView(openerpweb.Controller):
    _cp_path = "/base/searchview"

    @openerpweb.jsonrequest
    def load(self, req, model, view_id):
        m = req.session.model(model)
        r = m.fields_view_get(view_id, 'search')
        r["arch"] = Xml2Json.convert_to_structure(r["arch"])
        return {'fields_view': r}


class Action(openerpweb.Controller):
    _cp_path = "/base/action"

    @openerpweb.jsonrequest
    def load(self, req, action_id):
        return {}
