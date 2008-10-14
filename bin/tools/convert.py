# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2004-2008 Tiny SPRL (http://tiny.be) All Rights Reserved.
#
# $Id$
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
#----------------------------------------------------------
# Convert
#----------------------------------------------------------
import re
import StringIO,xml.dom.minidom
import osv,ir,pooler

import csv
import os.path
import misc
import netsvc

from config import config
import logging

from lxml import etree
import pickle


class ConvertError(Exception):
    def __init__(self, doc, orig_excpt):
        self.d = doc
        self.orig = orig_excpt

    def __str__(self):
        return 'Exception:\n\t%s\nUsing file:\n%s' % (self.orig, self.d)

def _ref(self, cr):
    return lambda x: self.id_get(cr, False, x)

def _obj(pool, cr, uid, model_str, context=None):
    model = pool.get(model_str)
    return lambda x: model.browse(cr, uid, x, context=context)

def _eval_xml(self,node, pool, cr, uid, idref, context=None):
    if context is None:
        context = {}
    if node.nodeType == node.TEXT_NODE:
        return node.data.encode("utf8")
    elif node.nodeType == node.ELEMENT_NODE:
        if node.nodeName in ('field','value'):
            t = node.getAttribute('type') or 'char'
            f_model = node.getAttribute("model").encode('ascii')
            if len(node.getAttribute('search')):
                f_search = node.getAttribute("search").encode('utf-8')
                f_use = node.getAttribute("use").encode('ascii')
                f_name = node.getAttribute("name").encode('utf-8')
                if len(f_use)==0:
                    f_use = "id"
                q = eval(f_search, idref)
                ids = pool.get(f_model).search(cr, uid, q)
                if f_use<>'id':
                    ids = map(lambda x: x[f_use], pool.get(f_model).read(cr, uid, ids, [f_use]))
                _cols = pool.get(f_model)._columns
                if (f_name in _cols) and _cols[f_name]._type=='many2many':
                    return ids
                f_val = False
                if len(ids):
                    f_val = ids[0]
                    if isinstance(f_val, tuple):
                        f_val = f_val[0]
                return f_val
            a_eval = node.getAttribute('eval')
            if len(a_eval):
                import time
                idref['time'] = time
                import release
                idref['version'] = release.version.rsplit('.', 1)[0]
                idref['ref'] = lambda x: self.id_get(cr, False, x)
                if len(f_model):
                    idref['obj'] = _obj(self.pool, cr, uid, f_model, context=context)
                try:
                    import pytz
                except:
                    logger = netsvc.Logger()
                    logger.notifyChannel("init", netsvc.LOG_INFO, 'could not find pytz library')
                    class pytzclass(object):
                        all_timezones=[]
                    pytz=pytzclass()
                idref['pytz'] = pytz
		try:
			return eval(a_eval, idref)
		except:
			logger = netsvc.Logger()
			logger.notifyChannel("init", netsvc.LOG_WARNING, 'could eval(%s) for %s in %s, please get back and fix it!' % (a_eval,node.getAttribute('name'),context))
			return ""
            if t == 'xml':
                def _process(s, idref):
                    m = re.findall('[^%]%\((.*?)\)[ds]', s)
                    for id in m:
                        if not id in idref:
                            idref[id]=self.id_get(cr, False, id)
                    return s % idref
                txt = '<?xml version="1.0"?>\n'+_process("".join([i.toxml().encode("utf8") for i in node.childNodes]), idref)
#               txt = '<?xml version="1.0"?>\n'+"".join([i.toxml().encode("utf8") for i in node.childNodes]) % idref

                return txt
            if t in ('char', 'int', 'float'):
                d = ""
                for n in [i for i in node.childNodes]:
                    d+=str(_eval_xml(self,n,pool,cr,uid,idref))
                if t == 'int':
                    d = d.strip()
                    if d=='None':
                        return None
                    else:
                        d=int(d.strip())
                elif t=='float':
                    d=float(d.strip())
                return d
            elif t in ('list','tuple'):
                res=[]
                for n in [i for i in node.childNodes if (i.nodeType == i.ELEMENT_NODE and i.nodeName=='value')]:
                    res.append(_eval_xml(self,n,pool,cr,uid,idref))
                if t=='tuple':
                    return tuple(res)
                return res
        elif node.nodeName=="getitem":
            for n in [i for i in node.childNodes if (i.nodeType == i.ELEMENT_NODE)]:
                res=_eval_xml(self,n,pool,cr,uid,idref)
            if not res:
                raise LookupError
            elif node.getAttribute('type') in ("int", "list"):
                return res[int(node.getAttribute('index'))]
            else:
                return res[node.getAttribute('index').encode("utf8")]
        elif node.nodeName=="function":
            args = []
            a_eval = node.getAttribute('eval')
            if len(a_eval):
                idref['ref'] = lambda x: self.id_get(cr, False, x)
                args = eval(a_eval, idref)
            for n in [i for i in node.childNodes if (i.nodeType == i.ELEMENT_NODE)]:
                args.append(_eval_xml(self,n, pool, cr, uid, idref, context))
            model = pool.get(node.getAttribute('model'))
            method = node.getAttribute('name')
            res = getattr(model, method)(cr, uid, *args)
            return res
        elif node.nodeName=="test":
            d = ""
            for n in [i for i in node.childNodes]:
                d+=str(_eval_xml(self,n,pool,cr,uid,idref, context=context))
            return d


escape_re = re.compile(r'(?<!\\)/')
def escape(x):
    return x.replace('\\/', '/')

class assertion_report(object):
    def __init__(self):
        self._report = {}

    def record_assertion(self, success, severity):
        """
            Records the result of an assertion for the failed/success count
            retrurns success
        """
        if severity in self._report:
            self._report[severity][success] += 1
        else:
            self._report[severity] = {success:1, not success: 0}
        return success

    def get_report(self):
        return self._report

    def __str__(self):
        res = '\nAssertions report:\nLevel\tsuccess\tfailed\n'
        success = failed = 0
        for sev in self._report:
            res += sev + '\t' + str(self._report[sev][True]) + '\t' + str(self._report[sev][False]) + '\n'
            success += self._report[sev][True]
            failed += self._report[sev][False]
        res += 'total\t' + str(success) + '\t' + str(failed) + '\n'
        res += 'end of report (' + str(success + failed) + ' assertion(s) checked)'
        return res

class xml_import(object):

    def isnoupdate(self, data_node = None):
        return self.noupdate or (data_node and data_node.getAttribute('noupdate'))

    def get_context(self, data_node, node, eval_dict):
        data_node_context = (data_node and data_node.getAttribute('context').encode('utf8'))
        if data_node_context:
            context = eval(data_node_context, eval_dict)
        else:
            context = {}

        node_context = node.getAttribute("context").encode('utf8')
        if len(node_context):
            context.update(eval(node_context, eval_dict))

        return context

    def get_uid(self, cr, uid, data_node, node):
        node_uid = node.getAttribute('uid') or (data_node and data_node.getAttribute('uid'))
        if len(node_uid):
            return self.id_get(cr, None, node_uid)
        return uid

    def _test_xml_id(self, xml_id):
        id = xml_id
        if '.' in xml_id:
            module, id = xml_id.split('.', 1)
            assert '.' not in id, """The ID reference "%s" must contains
maximum one dot. They are used to refer to other modules ID, in the
form: module.record_id""" % (xml_id,)
            if module != self.module:
                modcnt = self.pool.get('ir.module.module').search_count(self.cr, self.uid, ['&', ('name', '=', module), ('state', 'in', ['installed'])])
                assert modcnt == 1, """The ID "%s" refer to an uninstalled module""" % (xml_id,)

        if len(id) > 64:
            self.logger.notifyChannel('init', netsvc.LOG_ERROR, 'id: %s is to long (max: 64)'% (id,))

    def _tag_delete(self, cr, rec, data_node=None):
        d_model = rec.getAttribute("model")
        d_search = rec.getAttribute("search")
        d_id = rec.getAttribute("id")
        ids = []
        if len(d_search):
            ids = self.pool.get(d_model).search(cr,self.uid,eval(d_search))
        if len(d_id):
            ids.append(self.id_get(cr, d_model, d_id))
        if len(ids):
            self.pool.get(d_model).unlink(cr, self.uid, ids)
            #self.pool.get('ir.model.data')._unlink(cr, self.uid, d_model, ids, direct=True)
        return False

    def _tag_report(self, cr, rec, data_node=None):
        res = {}
        for dest,f in (('name','string'),('model','model'),('report_name','name')):
            res[dest] = rec.getAttribute(f).encode('utf8')
            assert res[dest], "Attribute %s of report is empty !" % (f,)
        for field,dest in (('rml','report_rml'),('xml','report_xml'),('xsl','report_xsl'),('attachment','attachment')):
            if rec.hasAttribute(field):
                res[dest] = rec.getAttribute(field).encode('utf8')
        if rec.hasAttribute('auto'):
            res['auto'] = eval(rec.getAttribute('auto'))
        if rec.hasAttribute('sxw'):
            sxw_content = misc.file_open(rec.getAttribute('sxw')).read()
            res['report_sxw_content'] = sxw_content
        if rec.hasAttribute('header'):
            res['header'] = eval(rec.getAttribute('header'))
        res['multi'] = rec.hasAttribute('multi') and  eval(rec.getAttribute('multi'))
        xml_id = rec.getAttribute('id').encode('utf8')
        self._test_xml_id(xml_id)

        if rec.hasAttribute('groups'):
            g_names = rec.getAttribute('groups').split(',')
            groups_value = []
            groups_obj = self.pool.get('res.groups')
            for group in g_names:
                if group.startswith('-'):
                    group_id = self.id_get(cr, 'res.groups', group[1:])
                    groups_value.append((3, group_id))
                else:
                    group_id = self.id_get(cr, 'res.groups', group)
                    groups_value.append((4, group_id))
            res['groups_id'] = groups_value

        id = self.pool.get('ir.model.data')._update(cr, self.uid, "ir.actions.report.xml", self.module, res, xml_id, mode=self.mode)
        self.idref[xml_id] = int(id)
        if not rec.hasAttribute('menu') or eval(rec.getAttribute('menu')):
            keyword = str(rec.getAttribute('keyword') or 'client_print_multi')
            keys = [('action',keyword),('res_model',res['model'])]
            value = 'ir.actions.report.xml,'+str(id)
            replace = rec.hasAttribute('replace') and rec.getAttribute("replace")
            self.pool.get('ir.model.data').ir_set(cr, self.uid, 'action', keyword, res['name'], [res['model']], value, replace=replace, isobject=True, xml_id=xml_id)
        return False

    def _tag_function(self, cr, rec, data_node=None):
        if self.isnoupdate(data_node) and self.mode != 'init':
            return
        context = self.get_context(data_node, rec, {'ref': _ref(self, cr)})
        uid = self.get_uid(cr, self.uid, data_node, rec)
        _eval_xml(self,rec, self.pool, cr, uid, self.idref, context=context)
        return False

    def _tag_wizard(self, cr, rec, data_node=None):
        string = rec.getAttribute("string").encode('utf8')
        model = rec.getAttribute("model").encode('utf8')
        name = rec.getAttribute("name").encode('utf8')
        xml_id = rec.getAttribute('id').encode('utf8')
        self._test_xml_id(xml_id)
        multi = rec.hasAttribute('multi') and  eval(rec.getAttribute('multi'))
        res = {'name': string, 'wiz_name': name, 'multi': multi, 'model': model}

        if rec.hasAttribute('groups'):
            g_names = rec.getAttribute('groups').split(',')
            groups_value = []
            groups_obj = self.pool.get('res.groups')
            for group in g_names:
                if group.startswith('-'):
                    group_id = self.id_get(cr, 'res.groups', group[1:])
                    groups_value.append((3, group_id))
                else:
                    group_id = self.id_get(cr, 'res.groups', group)
                    groups_value.append((4, group_id))
            res['groups_id'] = groups_value

        id = self.pool.get('ir.model.data')._update(cr, self.uid, "ir.actions.wizard", self.module, res, xml_id, mode=self.mode)
        self.idref[xml_id] = int(id)
        # ir_set
        if (not rec.hasAttribute('menu') or eval(rec.getAttribute('menu'))) and id:
            keyword = str(rec.getAttribute('keyword') or 'client_action_multi')
            keys = [('action',keyword),('res_model',model)]
            value = 'ir.actions.wizard,'+str(id)
            replace = rec.hasAttribute('replace') and \
                    rec.getAttribute("replace") or True
            self.pool.get('ir.model.data').ir_set(cr, self.uid, 'action', keyword, string, [model], value, replace=replace, isobject=True, xml_id=xml_id)
        return False

    def _tag_url(self, cr, rec, data_node=None):
        url = rec.getAttribute("string").encode('utf8')
        target = rec.getAttribute("target").encode('utf8')
        name = rec.getAttribute("name").encode('utf8')
        xml_id = rec.getAttribute('id').encode('utf8')
        self._test_xml_id(xml_id)

        res = {'name': name, 'url': url, 'target':target}

        id = self.pool.get('ir.model.data')._update(cr, self.uid, "ir.actions.url", self.module, res, xml_id, mode=self.mode)
        self.idref[xml_id] = int(id)
        # ir_set
        if (not rec.hasAttribute('menu') or eval(rec.getAttribute('menu'))) and id:
            keyword = str(rec.getAttribute('keyword') or 'client_action_multi')
            keys = [('action',keyword)]
            value = 'ir.actions.url,'+str(id)
            replace = rec.hasAttribute('replace') and \
                    rec.getAttribute("replace") or True
            self.pool.get('ir.model.data').ir_set(cr, self.uid, 'action', keyword, url, ["ir.actions.url"], value, replace=replace, isobject=True, xml_id=xml_id)
        return False

    def _tag_act_window(self, cr, rec, data_node=None):
        name = rec.hasAttribute('name') and rec.getAttribute('name').encode('utf-8')
        xml_id = rec.getAttribute('id').encode('utf8')
        self._test_xml_id(xml_id)
        type = rec.hasAttribute('type') and rec.getAttribute('type').encode('utf-8') or 'ir.actions.act_window'
        view_id = False
        if rec.hasAttribute('view'):
            view_id = self.id_get(cr, 'ir.actions.act_window', rec.getAttribute('view').encode('utf-8'))
        domain = rec.hasAttribute('domain') and rec.getAttribute('domain').encode('utf-8')
        context = rec.hasAttribute('context') and rec.getAttribute('context').encode('utf-8') or '{}'
        res_model = rec.getAttribute('res_model').encode('utf-8')
        src_model = rec.hasAttribute('src_model') and rec.getAttribute('src_model').encode('utf-8')
        view_type = rec.hasAttribute('view_type') and rec.getAttribute('view_type').encode('utf-8') or 'form'
        view_mode = rec.hasAttribute('view_mode') and rec.getAttribute('view_mode').encode('utf-8') or 'tree,form'
        usage = rec.hasAttribute('usage') and rec.getAttribute('usage').encode('utf-8')
        limit = rec.hasAttribute('limit') and rec.getAttribute('limit').encode('utf-8')
        auto_refresh = rec.hasAttribute('auto_refresh') \
                and rec.getAttribute('auto_refresh').encode('utf-8')
#        groups_id = rec.hasAttribute('groups') and rec.getAttribute('groups').encode('utf-8')

        res = {
            'name': name,
            'type': type,
            'view_id': view_id,
            'domain': domain,
            'context': context,
            'res_model': res_model,
            'src_model': src_model,
            'view_type': view_type,
            'view_mode': view_mode,
            'usage': usage,
            'limit': limit,
            'auto_refresh': auto_refresh,
#            'groups_id':groups_id,
        }

        if rec.hasAttribute('groups'):
            g_names = rec.getAttribute('groups').split(',')
            groups_value = []
            groups_obj = self.pool.get('res.groups')
            for group in g_names:
                if group.startswith('-'):
                    group_id = self.id_get(cr, 'res.groups', group[1:])
                    groups_value.append((3, group_id))
                else:
                    group_id = self.id_get(cr, 'res.groups', group)
                    groups_value.append((4, group_id))
            res['groups_id'] = groups_value

        if rec.hasAttribute('target'):
            res['target'] = rec.getAttribute('target')
        id = self.pool.get('ir.model.data')._update(cr, self.uid, 'ir.actions.act_window', self.module, res, xml_id, mode=self.mode)
        self.idref[xml_id] = int(id)

        if src_model:
            keyword = 'client_action_relate'
            keys = [('action', keyword), ('res_model', res_model)]
            value = 'ir.actions.act_window,'+str(id)
            replace = rec.hasAttribute('replace') and rec.getAttribute('replace')
            self.pool.get('ir.model.data').ir_set(cr, self.uid, 'action', keyword, xml_id, [src_model], value, replace=replace, isobject=True, xml_id=xml_id)
        # TODO add remove ir.model.data
        return False

    def _tag_ir_set(self, cr, rec, data_node=None):
        if not self.mode=='init':
            return False
        res = {}
        for field in [i for i in rec.childNodes if (i.nodeType == i.ELEMENT_NODE and i.nodeName=="field")]:
            f_name = field.getAttribute("name").encode('utf-8')
            f_val = _eval_xml(self,field,self.pool, cr, self.uid, self.idref)
            res[f_name] = f_val
        self.pool.get('ir.model.data').ir_set(cr, self.uid, res['key'], res['key2'], res['name'], res['models'], res['value'], replace=res.get('replace',True), isobject=res.get('isobject', False), meta=res.get('meta',None))
        return False

    def _tag_workflow(self, cr, rec, data_node=None):
        if self.isnoupdate(data_node) and self.mode != 'init':
            return
        model = str(rec.getAttribute('model'))
        w_ref = rec.getAttribute('ref')
        if len(w_ref):
            id = self.id_get(cr, model, w_ref)
        else:
            assert rec.childNodes, 'You must define a child node if you dont give a ref'
            element_childs = [i for i in rec.childNodes if i.nodeType == i.ELEMENT_NODE]
            assert len(element_childs) == 1, 'Only one child node is accepted (%d given)' % len(rec.childNodes)
            id = _eval_xml(self, element_childs[0], self.pool, cr, self.uid, self.idref)

        uid = self.get_uid(cr, self.uid, data_node, rec)
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, model,
            id,
            str(rec.getAttribute('action')), cr)
        return False

    #
    # Support two types of notation:
    #   name="Inventory Control/Sending Goods"
    # or
    #   action="action_id"
    #   parent="parent_id"
    #
    def _tag_menuitem(self, cr, rec, data_node=None):
        rec_id = rec.getAttribute("id").encode('ascii')
        self._test_xml_id(rec_id)
        m_l = map(escape, escape_re.split(rec.getAttribute("name").encode('utf8')))

        values = {'parent_id': False}
        if not rec.hasAttribute('parent'):
            pid = False
            for idx, menu_elem in enumerate(m_l):
                if pid:
                    cr.execute('select id from ir_ui_menu where parent_id=%d and name=%s', (pid, menu_elem))
                else:
                    cr.execute('select id from ir_ui_menu where parent_id is null and name=%s', (menu_elem,))
                res = cr.fetchone()
                if idx==len(m_l)-1:
                    values = {'parent_id': pid,'name':menu_elem}
                elif res:
                    pid = res[0]
                    xml_id = idx==len(m_l)-1 and rec.getAttribute('id').encode('utf8')
                    try:
                        npid = self.pool.get('ir.model.data')._update_dummy(cr, self.uid, 'ir.ui.menu', self.module, xml_id, idx==len(m_l)-1)
                    except:
                        print 'Menu Error', self.module, xml_id, idx==len(m_l)-1
                else:
                    # the menuitem does't exist but we are in branch (not a leaf)
                    self.logger.notifyChannel("init", netsvc.LOG_INFO, 'Warning no ID for submenu %s of menu %s !' % (menu_elem, str(m_l)))
                    pid = self.pool.get('ir.ui.menu').create(cr, self.uid, {'parent_id' : pid, 'name' : menu_elem})
        else:
            menu_parent_id = self.id_get(cr, 'ir.ui.menu', rec.getAttribute('parent'))
            values = {'parent_id': menu_parent_id}
            if rec.hasAttribute('name'):
                values['name'] = rec.getAttribute('name')
            try:
                res = [ self.id_get(cr, 'ir.ui.menu', rec.getAttribute('id')) ]
            except:
                res = None

        if rec.hasAttribute('action'):
            a_action = rec.getAttribute('action').encode('utf8')
            a_type = rec.getAttribute('type').encode('utf8') or 'act_window'
            icons = {
                "act_window": 'STOCK_NEW',
                "report.xml": 'STOCK_PASTE',
                "wizard": 'STOCK_EXECUTE',
                "url": 'STOCK_JUMP_TO'
            }
            values['icon'] = icons.get(a_type,'STOCK_NEW')
            if a_type=='act_window':
                a_id = self.id_get(cr, 'ir.actions.%s'% a_type, a_action)
                cr.execute('select view_type,view_mode,name,view_id,target from ir_act_window where id=%d', (int(a_id),))
                action_type,action_mode,action_name,view_id,target = cr.fetchone()
                if view_id:
                    cr.execute('SELECT type FROM ir_ui_view WHERE id=%d', (int(view_id),))
                    action_mode, = cr.fetchone()
                cr.execute('SELECT view_mode FROM ir_act_window_view WHERE act_window_id=%d ORDER BY sequence LIMIT 1', (int(a_id),))
                if cr.rowcount:
                    action_mode, = cr.fetchone()
                if action_type=='tree':
                    values['icon'] = 'STOCK_INDENT'
                elif action_mode and action_mode.startswith('tree'):
                    values['icon'] = 'STOCK_JUSTIFY_FILL'
                elif action_mode and action_mode.startswith('graph'):
                    values['icon'] = 'terp-graph'
                elif action_mode and action_mode.startswith('calendar'):
                    values['icon'] = 'terp-calendar'
                if target=='new':
                    values['icon'] = 'STOCK_EXECUTE'
                if not values.get('name', False):
                    values['name'] = action_name
            elif a_type=='wizard':
                a_id = self.id_get(cr, 'ir.actions.%s'% a_type, a_action)
                cr.execute('select name from ir_act_wizard where id=%d', (int(a_id),))
                resw = cr.fetchone()
                if (not values.get('name', False)) and resw:
                    values['name'] = resw[0]
        if rec.hasAttribute('sequence'):
            values['sequence'] = int(rec.getAttribute('sequence'))
        if rec.hasAttribute('icon'):
            values['icon'] = str(rec.getAttribute('icon'))

        if rec.hasAttribute('groups'):
            g_names = rec.getAttribute('groups').split(',')
            groups_value = []
            groups_obj = self.pool.get('res.groups')
            for group in g_names:
                if group.startswith('-'):
                    group_id = self.id_get(cr, 'res.groups', group[1:])
                    groups_value.append((3, group_id))
                else:
                    group_id = self.id_get(cr, 'res.groups', group)
                    groups_value.append((4, group_id))
            values['groups_id'] = groups_value

        xml_id = rec.getAttribute('id').encode('utf8')
        self._test_xml_id(xml_id)
        pid = self.pool.get('ir.model.data')._update(cr, self.uid, 'ir.ui.menu', self.module, values, xml_id, True, mode=self.mode, res_id=res and res[0] or False)

        if rec_id and pid:
            self.idref[rec_id] = int(pid)

        if rec.hasAttribute('action') and pid:
            a_action = rec.getAttribute('action').encode('utf8')
            a_type = rec.getAttribute('type').encode('utf8') or 'act_window'
            a_id = self.id_get(cr, 'ir.actions.%s' % a_type, a_action)
            action = "ir.actions.%s,%d" % (a_type, a_id)
            self.pool.get('ir.model.data').ir_set(cr, self.uid, 'action', 'tree_but_open', 'Menuitem', [('ir.ui.menu', int(pid))], action, True, True, xml_id=rec_id)
        return ('ir.ui.menu', pid)

    def _assert_equals(self, f1, f2, prec = 4):
        return not round(f1 - f2, prec)

    def _tag_assert(self, cr, rec, data_node=None):
        if self.isnoupdate(data_node) and self.mode != 'init':
            return

        rec_model = rec.getAttribute("model").encode('ascii')
        model = self.pool.get(rec_model)
        assert model, "The model %s does not exist !" % (rec_model,)
        rec_id = rec.getAttribute("id").encode('ascii')
        self._test_xml_id(rec_id)
        rec_src = rec.getAttribute("search").encode('utf8')
        rec_src_count = rec.getAttribute("count")

        severity = rec.getAttribute("severity").encode('ascii') or 'info'

        rec_string = rec.getAttribute("string").encode('utf8') or 'unknown'

        ids = None
        eval_dict = {'ref': _ref(self, cr)}
        context = self.get_context(data_node, rec, eval_dict)
        uid = self.get_uid(cr, self.uid, data_node, rec)
        if len(rec_id):
            ids = [self.id_get(cr, rec_model, rec_id)]
        elif len(rec_src):
            q = eval(rec_src, eval_dict)
            ids = self.pool.get(rec_model).search(cr, uid, q, context=context)
            if len(rec_src_count):
                count = int(rec_src_count)
                if len(ids) != count:
                    self.assert_report.record_assertion(False, severity)
                    self.logger.notifyChannel('init', severity, 'assertion "' + rec_string + '" failed ! (search count is incorrect: ' + str(len(ids)) + ')' )
                    sevval = getattr(logging, severity.upper())
                    if sevval > config['assert_exit_level']:
                        # TODO: define a dedicated exception
                        raise Exception('Severe assertion failure')
                    return

        assert ids != None, 'You must give either an id or a search criteria'

        ref = _ref(self, cr)
        for id in ids:
            brrec =  model.browse(cr, uid, id, context)
            class d(dict):
                def __getitem__(self2, key):
                    if key in brrec:
                        return brrec[key]
                    return dict.__getitem__(self2, key)
            globals = d()
            globals['floatEqual'] = self._assert_equals
            globals['ref'] = ref
            globals['_ref'] = ref
            for test in [i for i in rec.childNodes if (i.nodeType == i.ELEMENT_NODE and i.nodeName=="test")]:
                f_expr = test.getAttribute("expr").encode('utf-8')
                f_val = _eval_xml(self, test, self.pool, cr, uid, self.idref, context=context) or True
                if eval(f_expr, globals) != f_val: # assertion failed
                    self.assert_report.record_assertion(False, severity)
                    self.logger.notifyChannel('init', severity, 'assertion "' + rec_string + '" failed ! (tag ' + test.toxml() + ')' )
                    sevval = getattr(logging, severity.upper())
                    if sevval > config['assert_exit_level']:
                        # TODO: define a dedicated exception
                        raise Exception('Severe assertion failure')
                    return
        else: # all tests were successful for this assertion tag (no break)
            self.assert_report.record_assertion(True, severity)

    def _tag_record(self, cr, rec, data_node=None):
        rec_model = rec.getAttribute("model").encode('ascii')
        model = self.pool.get(rec_model)
        assert model, "The model %s does not exist !" % (rec_model,)
        rec_id = rec.getAttribute("id").encode('ascii')
        self._test_xml_id(rec_id)

#       if not rec_id and not self.isnoupdate(data_node):
#           print "Warning", rec_model

        if self.isnoupdate(data_node) and not self.mode == 'init':
            # check if the xml record has an id string
            if rec_id:
                id = self.pool.get('ir.model.data')._update_dummy(cr, self.uid, rec_model, self.module, rec_id)
                # check if the resource already existed at the last update
                if id:
                    # if it existed, we don't update the data, but we need to
                    # know the id of the existing record anyway
                    self.idref[rec_id] = int(id)
                    return None
                else:
                    # if the resource didn't exist
                    if rec.getAttribute("forcecreate"):
                        # we want to create it, so we let the normal "update" behavior happen
                        pass
                    else:
                        # otherwise do nothing
                        return None
            else:
                # otherwise it is skipped
                return None

        res = {}
        for field in [i for i in rec.childNodes if (i.nodeType == i.ELEMENT_NODE and i.nodeName=="field")]:
#TODO: most of this code is duplicated above (in _eval_xml)...
            f_name = field.getAttribute("name").encode('utf-8')
            f_ref = field.getAttribute("ref").encode('ascii')
            f_search = field.getAttribute("search").encode('utf-8')
            f_model = field.getAttribute("model").encode('ascii')
            if not f_model and model._columns.get(f_name,False):
                f_model = model._columns[f_name]._obj
            f_use = field.getAttribute("use").encode('ascii') or 'id'
            f_val = False

            if len(f_search):
                q = eval(f_search, self.idref)
                field = []
                assert f_model, 'Define an attribute model="..." in your .XML file !'
                f_obj = self.pool.get(f_model)
                # browse the objects searched
                s = f_obj.browse(cr, self.uid, f_obj.search(cr, self.uid, q))
                # column definitions of the "local" object
                _cols = self.pool.get(rec_model)._columns
                # if the current field is many2many
                if (f_name in _cols) and _cols[f_name]._type=='many2many':
                    f_val = [(6, 0, map(lambda x: x[f_use], s))]
                elif len(s):
                    # otherwise (we are probably in a many2one field),
                    # take the first element of the search
                    f_val = s[0][f_use]
            elif len(f_ref):
                if f_ref=="null":
                    f_val = False
                else:
                    f_val = self.id_get(cr, f_model, f_ref)
            else:
                f_val = _eval_xml(self,field, self.pool, cr, self.uid, self.idref)
                if model._columns.has_key(f_name):
                    if isinstance(model._columns[f_name], osv.fields.integer):
                        f_val = int(f_val)
            res[f_name] = f_val
        id = self.pool.get('ir.model.data')._update(cr, self.uid, rec_model, self.module, res, rec_id or False, not self.isnoupdate(data_node), noupdate=self.isnoupdate(data_node), mode=self.mode )
        if rec_id:
            self.idref[rec_id] = int(id)
        if config.get('import_partial', False):
            cr.commit()
        return rec_model, id

    def id_get(self, cr, model, id_str):
        if id_str in self.idref:
            return self.idref[id_str]
        mod = self.module
        if '.' in id_str:
            mod,id_str = id_str.split('.')
        result = self.pool.get('ir.model.data')._get_id(cr, self.uid, mod, id_str)
        return int(self.pool.get('ir.model.data').read(cr, self.uid, [result], ['res_id'])[0]['res_id'])

    def parse(self, xmlstr):
        d = xml.dom.minidom.parseString(xmlstr)
        de = d.documentElement

        if not de.nodeName in ['terp', 'openerp']:
            self.logger.notifyChannel("init", netsvc.LOG_ERROR, "Mismatch xml format" )
            raise Exception( "Mismatch xml format: only terp or openerp as root tag" )

        if de.nodeName == 'terp':
            self.logger.notifyChannel("init", netsvc.LOG_WARNING, "The tag <terp /> is deprecated, use <openerp/>")

        for n in [i for i in de.childNodes if (i.nodeType == i.ELEMENT_NODE and i.nodeName=="data")]:
            for rec in n.childNodes:
                if rec.nodeType == rec.ELEMENT_NODE:
                    if rec.nodeName in self._tags:
                        try:
                            self._tags[rec.nodeName](self.cr, rec, n)
                        except:
                            self.logger.notifyChannel("init", netsvc.LOG_INFO, '\n'+rec.toxml())
                            self.cr.rollback()
                            raise
        return True

    def __init__(self, cr, module, idref, mode, report=assertion_report(), noupdate = False):
        self.logger = netsvc.Logger()
        self.mode = mode
        self.module = module
        self.cr = cr
        self.idref = idref
        self.pool = pooler.get_pool(cr.dbname)
#       self.pool = osv.osv.FakePool(module)
        self.uid = 1
        self.assert_report = report
        self.noupdate = noupdate
        self._tags = {
            'menuitem': self._tag_menuitem,
            'record': self._tag_record,
            'assert': self._tag_assert,
            'report': self._tag_report,
            'wizard': self._tag_wizard,
            'delete': self._tag_delete,
            'ir_set': self._tag_ir_set,
            'function': self._tag_function,
            'workflow': self._tag_workflow,
            'act_window': self._tag_act_window,
            'url': self._tag_url
        }

def convert_csv_import(cr, module, fname, csvcontent, idref=None, mode='init',
        noupdate=False):
    '''Import csv file :
        quote: "
        delimiter: ,
        encoding: utf-8'''
    if not idref:
        idref={}
    model = ('.'.join(fname.split('.')[:-1]).split('-'))[0]
    #remove folder path from model
    head, model = os.path.split(model)

    pool = pooler.get_pool(cr.dbname)

    input = StringIO.StringIO(csvcontent)
    reader = csv.reader(input, quotechar='"', delimiter=',')
    fields = reader.next()

    fname_partial = ""
    if config.get('import_partial'):
        fname_partial = module + '/'+ fname
        if not os.path.isfile(config.get('import_partial')):
            pickle.dump({}, file(config.get('import_partial'),'w+'))
        else:
            data = pickle.load(file(config.get('import_partial')))
            if fname_partial in data:
                if not data[fname_partial]:
                    return
                else:
                    for i in range(data[fname_partial]):
                        reader.next()

    if not (mode == 'init' or 'id' in fields):
        return

    uid = 1
    datas = []
    for line in reader:
        if (not line) or not reduce(lambda x,y: x or y, line) :
            continue
        datas.append( map(lambda x:x.decode('utf8').encode('utf8'), line))
    pool.get(model).import_data(cr, uid, fields, datas,mode, module,noupdate,filename=fname_partial)

    if config.get('import_partial'):
        data = pickle.load(file(config.get('import_partial')))
        data[fname_partial] = 0
        pickle.dump(data, file(config.get('import_partial'),'wb'))

#
# xml import/export
#
def convert_xml_import(cr, module, xmlfile, idref=None, mode='init', noupdate = False, report=None):
    xmlstr = xmlfile.read()
    xmlfile.seek(0)
    relaxng_doc = etree.parse(file(os.path.join( config['root_path'], 'import_xml.rng' )))
    relaxng = etree.RelaxNG(relaxng_doc)

    doc = etree.parse(xmlfile)
    try:
        relaxng.assert_(doc)
    except Exception, e:
        logger = netsvc.Logger()
        logger.notifyChannel('init', netsvc.LOG_ERROR, 'The XML file do not fit the required schema !')
        logger.notifyChannel('init', netsvc.LOG_ERROR, relaxng.error_log.last_error)
        raise

    if not idref:
        idref={}
    if report is None:
        report=assertion_report()
    obj = xml_import(cr, module, idref, mode, report=report, noupdate = noupdate)
    obj.parse(xmlstr)
    del obj
    return True

def convert_xml_export(res):
    uid=1
    pool=pooler.get_pool(cr.dbname)
    cr=pooler.db.cursor()
    idref = {}
    d = xml.dom.minidom.getDOMImplementation().createDocument(None, "terp", None)
    de = d.documentElement
    data=d.createElement("data")
    de.appendChild(data)
    de.appendChild(d.createTextNode('Some textual content.'))
    cr.commit()
    cr.close()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

