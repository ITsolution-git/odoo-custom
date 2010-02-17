# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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

from osv import fields,osv
import tools
import time
from tools.config import config
from tools.translate import _
import netsvc
import re
import copy
import sys
from xml import dom

class actions(osv.osv):
    _name = 'ir.actions.actions'
    _table = 'ir_actions'
    _columns = {
        'name': fields.char('Action Name', required=True, size=64),
        'type': fields.char('Action Type', required=True, size=32),
        'usage': fields.char('Action Usage', size=32),
    }
    _defaults = {
        'usage': lambda *a: False,
    }
actions()

class report_custom(osv.osv):
    _name = 'ir.actions.report.custom'
    _table = 'ir_act_report_custom'
    _sequence = 'ir_actions_id_seq'
    _columns = {
        'name': fields.char('Report Name', size=64, required=True, translate=True),
        'type': fields.char('Report Type', size=32, required=True),
        'model':fields.char('Object', size=64, required=True),
        'report_id': fields.integer('Report Ref.', required=True),
        'usage': fields.char('Action Usage', size=32),
        'multi': fields.boolean('On multiple doc.', help="If set to true, the action will not be displayed on the right toolbar of a form view.")
    }
    _defaults = {
        'multi': lambda *a: False,
        'type': lambda *a: 'ir.actions.report.custom',
    }
report_custom()

class report_xml(osv.osv):

    def _report_content(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for report in self.browse(cursor, user, ids, context=context):
            data = report[name + '_data']
            if not data and report[name[:-8]]:
                try:
                    fp = tools.file_open(report[name[:-8]], mode='rb')
                    data = fp.read()
                except:
                    data = False
            res[report.id] = data
        return res

    def _report_content_inv(self, cursor, user, id, name, value, arg, context=None):
        self.write(cursor, user, id, {name+'_data': value}, context=context)

    def _report_sxw(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for report in self.browse(cursor, user, ids, context=context):
            if report.report_rml:
                res[report.id] = report.report_rml.replace('.rml', '.sxw')
            else:
                res[report.id] = False
        return res

    _name = 'ir.actions.report.xml'
    _table = 'ir_act_report_xml'
    _sequence = 'ir_actions_id_seq'
    _columns = {
        'name': fields.char('Name', size=64, required=True, translate=True),
        'type': fields.char('Report Type', size=32, required=True),
        'model': fields.char('Object', size=64, required=True),
        'report_name': fields.char('Internal Name', size=64, required=True),
        'report_xsl': fields.char('XSL path', size=256),
        'report_xml': fields.char('XML path', size=256),
        'report_rml': fields.char('RML path', size=256,
            help="The .rml path of the file or NULL if the content is in report_rml_content"),
        'report_sxw': fields.function(_report_sxw, method=True, type='char',
            string='SXW path'),
        'report_sxw_content_data': fields.binary('SXW content'),
        'report_rml_content_data': fields.binary('RML content'),
        'report_sxw_content': fields.function(_report_content,
            fnct_inv=_report_content_inv, method=True,
            type='binary', string='SXW content',),
        'report_rml_content': fields.function(_report_content,
            fnct_inv=_report_content_inv, method=True,
            type='binary', string='RML content'),
        'auto': fields.boolean('Automatic XSL:RML', required=True),
        'usage': fields.char('Action Usage', size=32),
        'header': fields.boolean('Add RML header',
            help="Add or not the coporate RML header"),
        'multi': fields.boolean('On multiple doc.',
            help="If set to true, the action will not be displayed on the right toolbar of a form view."),
        'report_type': fields.selection([
            ('pdf', 'pdf'),
            ('html', 'html'),
            ('raw', 'raw'),
            ('sxw', 'sxw'),
            ('txt', 'txt'),
            ('odt', 'odt'),
            ('html2html','HTML from HTML'),
            ('mako2html','HTML from HTML(Mako)'),
            ], string='Type', required=True),
        'groups_id': fields.many2many('res.groups', 'res_groups_report_rel', 'uid', 'gid', 'Groups'),
        'attachment': fields.char('Save As Attachment Prefix', size=128, help='This is the filename of the attachment used to store the printing result. Keep empty to not save the printed reports. You can use a python expression with the object and time variables.'),
        'attachment_use': fields.boolean('Reload from Attachment', help='If you check this, then the second time the user prints with same attachment name, it returns the previous report.')
    }
    _defaults = {
        'type': lambda *a: 'ir.actions.report.xml',
        'multi': lambda *a: False,
        'auto': lambda *a: True,
        'header': lambda *a: True,
        'report_sxw_content': lambda *a: False,
        'report_type': lambda *a: 'pdf',
        'attachment': lambda *a: False,
    }

report_xml()

class act_window(osv.osv):
    _name = 'ir.actions.act_window'
    _table = 'ir_act_window'
    _sequence = 'ir_actions_id_seq'

    def _check_model(self, cr, uid, ids, context={}):
        for action in self.browse(cr, uid, ids, context):
            if not self.pool.get(action.res_model):
                return False
            if action.src_model and not self.pool.get(action.src_model):
                return False
        return True
    _constraints = [
        (_check_model, 'Invalid model name in the action definition.', ['res_model','src_model'])
    ]

    def get_filters(self, cr, uid, model):
        cr.execute('select id from ir_act_window a where a.id not in (select act_id from ir_act_window_user_rel) and a.res_model=\''+model+'\' and a.filter=\'1\';')
        all_ids = cr.fetchall()
        filter_ids =  map(lambda x:x[0],all_ids)
        act_ids = self.search(cr,uid,[('res_model','=',model),('filter','=',1),('default_user_ids','in',(','.join(map(str,[uid,])),))])
        act_ids += filter_ids
        act_ids = list(set(act_ids))
        my_acts = self.read(cr, uid, act_ids, ['name', 'domain','context'])
        return my_acts

    def _views_get_fnc(self, cr, uid, ids, name, arg, context={}):
        res={}
        for act in self.browse(cr, uid, ids):
            res[act.id]=[(view.view_id.id, view.view_mode) for view in act.view_ids]
            modes = act.view_mode.split(',')
            if len(modes)>len(act.view_ids):
                find = False
                if act.view_id:
                    res[act.id].append((act.view_id.id, act.view_id.type))
                for t in modes[len(act.view_ids):]:
                    if act.view_id and (t == act.view_id.type) and not find:
                        find = True
                        continue
                    res[act.id].append((False, t))
        return res

    def _search_view(self, cr, uid, ids, name, arg, context={}):
        res = {}
        def encode(s):
            if isinstance(s, unicode):
                return s.encode('utf8')
            return s
        for act in self.browse(cr, uid, ids):
            fields_from_fields_get = self.pool.get(act.res_model).fields_get(cr, uid)
            if act.search_view_id:
                field_get = self.pool.get(act.res_model).fields_view_get(cr, uid, act.search_view_id.id, 'search', context)
                fields_from_fields_get.update(field_get['fields'])
                field_get['fields'] = fields_from_fields_get
                res[act.id] = str(field_get)
            else:
                def process_child(node, new_node, doc):
                    for child in node.childNodes:
                        if child.localName=='field' and child.hasAttribute('select') and child.getAttribute('select')=='1':
                            if child.childNodes:
                                fld = doc.createElement('field')
                                for attr in child.attributes.keys():
                                    fld.setAttribute(attr, child.getAttribute(attr))
                                new_node.appendChild(fld)
                            else:
                                new_node.appendChild(child)
                        elif child.localName in ('page','group','notebook'):
                            process_child(child, new_node, doc)

                form_arch = self.pool.get(act.res_model).fields_view_get(cr, uid, False, 'form', context)
                dom_arc = dom.minidom.parseString(encode(form_arch['arch']))
                new_node = copy.deepcopy(dom_arc)
                for child_node in new_node.childNodes[0].childNodes:
                    if child_node.nodeType == child_node.ELEMENT_NODE:
                        new_node.childNodes[0].removeChild(child_node)
                process_child(dom_arc.childNodes[0],new_node.childNodes[0],dom_arc)

                form_arch['arch'] = new_node.toxml()
                form_arch['fields'].update(fields_from_fields_get)
                res[act.id] = str(form_arch)
        return res

    _columns = {
        'name': fields.char('Action Name', size=64, translate=True),
        'type': fields.char('Action Type', size=32, required=True),
        'view_id': fields.many2one('ir.ui.view', 'View Ref.', ondelete='cascade'),
        'domain': fields.char('Domain Value', size=250),
        'context': fields.char('Context Value', size=250),
        'res_model': fields.char('Object', size=64),
        'src_model': fields.char('Source Object', size=64),
        'target': fields.selection([('current','Current Window'),('new','New Window')], 'Target Window'),
        'view_type': fields.selection((('tree','Tree'),('form','Form')),string='View Type'),
        'view_mode': fields.char('View Mode', size=250),
        'usage': fields.char('Action Usage', size=32),
        'view_ids': fields.one2many('ir.actions.act_window.view', 'act_window_id', 'Views'),
        'views': fields.function(_views_get_fnc, method=True, type='binary', string='Views'),
        'limit': fields.integer('Limit', help='Default limit for the list view'),
        'auto_refresh': fields.integer('Auto-Refresh',
            help='Add an auto-refresh on the view'),
        'groups_id': fields.many2many('res.groups', 'ir_act_window_group_rel',
            'act_id', 'gid', 'Groups'),
        'search_view_id': fields.many2one('ir.ui.view', 'Search View Ref.'),
        'filter': fields.boolean('Filter'),
        'default_user_ids': fields.many2many('res.users', 'ir_act_window_user_rel', 'act_id', 'uid', 'Users'),
        'search_view' : fields.function(_search_view, type='text', method=True, string='Search View'),
        'menus': fields.char('Menus', size=4096)
    }
    _defaults = {
        'type': lambda *a: 'ir.actions.act_window',
        'view_type': lambda *a: 'form',
        'view_mode': lambda *a: 'tree,form',
        'context': lambda *a: '{}',
        'limit': lambda *a: 80,
        'target': lambda *a: 'current',
        'auto_refresh': lambda *a: 0,
    }
act_window()

class act_window_view(osv.osv):
    _name = 'ir.actions.act_window.view'
    _table = 'ir_act_window_view'
    _rec_name = 'view_id'
    _columns = {
        'sequence': fields.integer('Sequence'),
        'view_id': fields.many2one('ir.ui.view', 'View'),
        'view_mode': fields.selection((
            ('tree', 'Tree'),
            ('form', 'Form'),
            ('graph', 'Graph'),
            ('calendar', 'Calendar'),
            ('gantt', 'Gantt')), string='View Type', required=True),
        'act_window_id': fields.many2one('ir.actions.act_window', 'Action', ondelete='cascade'),
        'multi': fields.boolean('On Multiple Doc.',
            help="If set to true, the action will not be displayed on the right toolbar of a form view."),
    }
    _defaults = {
        'multi': lambda *a: False,
    }
    _order = 'sequence'
act_window_view()

class act_wizard(osv.osv):
    _name = 'ir.actions.wizard'
    _inherit = 'ir.actions.actions'
    _table = 'ir_act_wizard'
    _sequence = 'ir_actions_id_seq'
    _columns = {
        'name': fields.char('Wizard Info', size=64, required=True, translate=True),
        'type': fields.char('Action Type', size=32, required=True),
        'wiz_name': fields.char('Wizard Name', size=64, required=True),
        'multi': fields.boolean('Action on Multiple Doc.', help="If set to true, the wizard will not be displayed on the right toolbar of a form view."),
        'groups_id': fields.many2many('res.groups', 'res_groups_wizard_rel', 'uid', 'gid', 'Groups'),
        'model': fields.char('Object', size=64),
    }
    _defaults = {
        'type': lambda *a: 'ir.actions.wizard',
        'multi': lambda *a: False,
    }
act_wizard()

class act_url(osv.osv):
    _name = 'ir.actions.url'
    _table = 'ir_act_url'
    _sequence = 'ir_actions_id_seq'
    _columns = {
        'name': fields.char('Action Name', size=64, translate=True),
        'type': fields.char('Action Type', size=32, required=True),
        'url': fields.text('Action URL',required=True),
        'target': fields.selection((
            ('new', 'New Window'),
            ('self', 'This Window')),
            'Action Target', required=True
        )
    }
    _defaults = {
        'type': lambda *a: 'ir.actions.act_url',
        'target': lambda *a: 'new'
    }
act_url()

def model_get(self, cr, uid, context={}):
    wkf_pool = self.pool.get('workflow')
    ids = wkf_pool.search(cr, uid, [])
    osvs = wkf_pool.read(cr, uid, ids, ['osv'])

    res = []
    mpool = self.pool.get('ir.model')
    for osv in osvs:
        model = osv.get('osv')
        id = mpool.search(cr, uid, [('model','=',model)])
        name = mpool.read(cr, uid, id)[0]['name']
        res.append((model, name))

    return res

class ir_model_fields(osv.osv):
    _inherit = 'ir.model.fields'
    _rec_name = 'field_description'
    _columns = {
        'complete_name': fields.char('Complete Name', size=64, select=1),
    }
ir_model_fields()

class server_object_lines(osv.osv):
    _name = 'ir.server.object.lines'
    _sequence = 'ir_actions_id_seq'
    _columns = {
        'server_id': fields.many2one('ir.actions.server', 'Object Mapping'),
        'col1': fields.many2one('ir.model.fields', 'Destination', required=True),
        'value': fields.text('Value', required=True),
        'type': fields.selection([
            ('value','Value'),
            ('equation','Formula')
        ], 'Type', required=True, size=32, change_default=True),
    }
    _defaults = {
        'type': lambda *a: 'equation',
    }
server_object_lines()

##
# Actions that are run on the server side
#
class actions_server(osv.osv):

    def _select_signals(self, cr, uid, context={}):
        cr.execute("select distinct t.signal as key, t.signal || ' - [ ' || w.osv || ' ] ' as val from wkf w, wkf_activity a, wkf_transition t "\
                        " where w.id = a.wkf_id " \
                        " and t.act_from = a.id " \
                        " or t.act_to = a.id and t.signal not in (null, NULL)")
        result = cr.fetchall() or []
        res = []
        for rs in result:
            if rs[0] is not None and rs[1] is not None:
                res.append(rs)
        return res

    _name = 'ir.actions.server'
    _table = 'ir_act_server'
    _sequence = 'ir_actions_id_seq'
    _order = 'sequence'
    _columns = {
        'name': fields.char('Action Name', required=True, size=64, help="Easy to Refer action by name e.g. One Sales Order -> Many Invoices", translate=True),
        'condition' : fields.char('Condition', size=256, required=True, help="Condition that is to be tested before action is executed, e.g. object.list_price > object.cost_price"),
        'state': fields.selection([
            ('client_action','Client Action'),
            ('dummy','Dummy'),
            ('loop','Iteration'),
            ('code','Python Code'),
            ('trigger','Trigger'),
            ('email','Email'),
            ('sms','SMS'),
            ('object_create','Create Object'),
            ('object_write','Write Object'),
            ('other','Multi Actions'),
        ], 'Action Type', required=True, size=32, help="Type of the Action that is to be executed"),
        'code':fields.text('Python Code', help="Python code to be executed"),
        'sequence': fields.integer('Sequence', help="Important when you deal with multiple actions, the execution order will be decided based on this, low number is higher priority."),
        'model_id': fields.many2one('ir.model', 'Object', required=True, help="Select the object on which the action will work (read, write, create)."),
        'action_id': fields.many2one('ir.actions.actions', 'Client Action', help="Select the Action Window, Report, Wizard to be executed."),
        'trigger_name': fields.selection(_select_signals, string='Trigger Name', size=128, help="Select the Signal name that is to be used as the trigger."),
        'wkf_model_id': fields.many2one('ir.model', 'Workflow On', help="Workflow to be executed on this model."),
        'trigger_obj_id': fields.many2one('ir.model.fields','Trigger On', help="Select the object from the model on which the workflow will executed."),
        'email': fields.char('Email Address', size=512, help="Provides the fields that will be used to fetch the email address, e.g. when you select the invoice, then `object.invoice_address_id.email` is the field which gives the correct address"),
        'subject': fields.char('Subject', size=1024, translate=True, help="Specify the subject. You can use fields from the object, e.g. `Hello [[ object.partner_id.name ]]`"),
        'message': fields.text('Message', translate=True, help="Specify the message. You can use the fields from the object. e.g. `Dear [[ object.partner_id.name ]]`"),
        'mobile': fields.char('Mobile No', size=512, help="Provides fields that be used to fetch the mobile number, e.g. you select the invoice, then `object.invoice_address_id.mobile` is the field which gives the correct mobile number"),
        'sms': fields.char('SMS', size=160, translate=True),
        'child_ids': fields.many2many('ir.actions.server', 'rel_server_actions', 'server_id', 'action_id', 'Other Actions'),
        'usage': fields.char('Action Usage', size=32),
        'type': fields.char('Action Type', size=32, required=True),
        'srcmodel_id': fields.many2one('ir.model', 'Model', help="Object in which you want to create / write the object. If it is empty then refer to the Object field."),
        'fields_lines': fields.one2many('ir.server.object.lines', 'server_id', 'Field Mappings.'),
        'record_id':fields.many2one('ir.model.fields', 'Create Id', help="Provide the field name where the record id is stored after the create operations. If it is empty, you can not track the new record."),
        'write_id':fields.char('Write Id', size=256, help="Provide the field name that the record id refers to for the write operation. If it is empty it will refer to the active id of the object."),
        'loop_action':fields.many2one('ir.actions.server', 'Loop Action', help="Select the action that will be executed. Loop action will not be avaliable inside loop."),
        'expression':fields.char('Loop Expression', size=512, help="Enter the field/expression that will return the list. E.g. select the sale order in Object, and you can have loop on the sales order line. Expression = `object.order_line`."),
    }
    _defaults = {
        'state': lambda *a: 'dummy',
        'condition': lambda *a: 'True',
        'type': lambda *a: 'ir.actions.server',
        'sequence': lambda *a: 5,
        'code': lambda *a: """# You can use the following variables
#    - object
#    - time
#    - cr
#    - uid
#    - ids
# If you plan to return an action, assign: action = {...}
""",
    }

    def get_email(self, cr, uid, action, context):
        logger = netsvc.Logger()
        obj_pool = self.pool.get(action.model_id.model)
        id = context.get('active_id')
        obj = obj_pool.browse(cr, uid, id)

        fields = None

        if '/' in action.email.complete_name:
            fields = action.email.complete_name.split('/')
        elif '.' in action.email.complete_name:
            fields = action.email.complete_name.split('.')

        for field in fields:
            try:
                obj = getattr(obj, field)
            except Exception,e :
                logger.notifyChannel('Workflow', netsvc.LOG_ERROR, 'Failed to parse : %s' % (field))

        return obj

    def get_mobile(self, cr, uid, action, context):
        logger = netsvc.Logger()
        obj_pool = self.pool.get(action.model_id.model)
        id = context.get('active_id')
        obj = obj_pool.browse(cr, uid, id)

        fields = None

        if '/' in action.mobile.complete_name:
            fields = action.mobile.complete_name.split('/')
        elif '.' in action.mobile.complete_name:
            fields = action.mobile.complete_name.split('.')

        for field in fields:
            try:
                obj = getattr(obj, field)
            except Exception,e :
                logger.notifyChannel('Workflow', netsvc.LOG_ERROR, 'Failed to parse : %s' % (field))

        return obj

    def merge_message(self, cr, uid, keystr, action, context):
        logger = netsvc.Logger()
        def merge(match):
            obj_pool = self.pool.get(action.model_id.model)
            id = context.get('active_id')
            obj = obj_pool.browse(cr, uid, id)
            exp = str(match.group()[2:-2]).strip()
            result = eval(exp, {'object':obj, 'context': context,'time':time})
            if result in (None, False):
                return str("--------")
            return tools.ustr(result)

        com = re.compile('(\[\[.+?\]\])')
        message = com.sub(merge, keystr)

        return message

    # Context should contains:
    #   ids : original ids
    #   id  : current id of the object
    # OUT:
    #   False : Finnished correctly
    #   ACTION_ID : Action to launch

    def run(self, cr, uid, ids, context={}):
        logger = netsvc.Logger()

        for action in self.browse(cr, uid, ids, context):
            obj_pool = self.pool.get(action.model_id.model)
            obj = obj_pool.browse(cr, uid, context['active_id'], context=context)
            cxt = {
                'context':context,
                'object': obj,
                'time':time,
                'cr': cr,
                'pool' : self.pool,
                'uid' : uid
            }
            expr = eval(str(action.condition), cxt)
            if not expr:
                continue

            if action.state=='client_action':
                if not action.action_id:
                    raise osv.except_osv(_('Error'), _("Please specify an action to launch !"))
                return self.pool.get(action.action_id.type)\
                    .read(cr, uid, action.action_id.id, context=context)

            if action.state == 'code':
                localdict = {
                    'self': self.pool.get(action.model_id.model),
                    'context': context,
                    'time': time,
                    'ids': ids,
                    'cr': cr,
                    'uid': uid,
                    'object':obj
                }
                exec action.code in localdict
                if 'action' in localdict:
                    return localdict['action']

            if action.state == 'email':
                user = config['email_from']
                address = str(action.email)
                try:
                    address =  eval(str(action.email), cxt)
                except:
                    pass

                if not address:
                    logger.notifyChannel('email', netsvc.LOG_INFO, 'Partner Email address not Specified!')
                    continue
                if not user:
                    raise osv.except_osv(_('Error'), _("Please specify server option --smtp-from !"))
                
                subject = self.merge_message(cr, uid, action.subject, action, context)
                body = self.merge_message(cr, uid, action.message, action, context)
                
                if tools.email_send(user, [address], subject, body, debug=False, subtype='html') == True:
                    logger.notifyChannel('email', netsvc.LOG_INFO, 'Email successfully send to : %s' % (address))
                else:
                    logger.notifyChannel('email', netsvc.LOG_ERROR, 'Failed to send email to : %s' % (address))

            if action.state == 'trigger':
                wf_service = netsvc.LocalService("workflow")
                model = action.wkf_model_id.model
                obj_pool = self.pool.get(action.model_id.model)
                res_id = self.pool.get(action.model_id.model).read(cr, uid, [context.get('active_id')], [action.trigger_obj_id.name])
                id = res_id [0][action.trigger_obj_id.name]
                wf_service.trg_validate(uid, model, int(id), action.trigger_name, cr)

            if action.state == 'sms':
                #TODO: set the user and password from the system
                # for the sms gateway user / password
                # USE smsclient module from extra-addons
                logger.notifyChannel('sms', netsvc.LOG_ERROR, 'SMS Facility has not been implemented yet. Use smsclient module!')

            if action.state == 'other':
                res = []
                for act in action.child_ids:
                    context['active_id'] = context['active_ids'][0]
                    result = self.run(cr, uid, [act.id], context)
                    if result:
                        res.append(result)

                return res

            if action.state == 'loop':
                obj_pool = self.pool.get(action.model_id.model)
                obj = obj_pool.browse(cr, uid, context['active_id'], context=context)
                cxt = {
                    'context':context,
                    'object': obj,
                    'time':time,
                    'cr': cr,
                    'pool' : self.pool,
                    'uid' : uid
                }
                expr = eval(str(action.expression), cxt)
                context['object'] = obj
                for i in expr:
                    context['active_id'] = i.id
                    result = self.run(cr, uid, [action.loop_action.id], context)

            if action.state == 'object_write':
                res = {}
                for exp in action.fields_lines:
                    euq = exp.value
                    if exp.type == 'equation':
                        obj_pool = self.pool.get(action.model_id.model)
                        obj = obj_pool.browse(cr, uid, context['active_id'], context=context)
                        cxt = {'context':context, 'object': obj, 'time':time}
                        expr = eval(euq, cxt)
                    else:
                        expr = exp.value
                    res[exp.col1.name] = expr

                if not action.write_id:
                    if not action.srcmodel_id:
                        obj_pool = self.pool.get(action.model_id.model)
                        obj_pool.write(cr, uid, [context.get('active_id')], res)
                    else:
                        write_id = context.get('active_id')
                        obj_pool = self.pool.get(action.srcmodel_id.model)
                        obj_pool.write(cr, uid, [write_id], res)

                elif action.write_id:
                    obj_pool = self.pool.get(action.srcmodel_id.model)
                    rec = self.pool.get(action.model_id.model).browse(cr, uid, context.get('active_id'))
                    id = eval(action.write_id, {'object': rec})
                    try:
                        id = int(id)
                    except:
                        raise osv.except_osv(_('Error'), _("Problem in configuration `Record Id` in Server Action!"))

                    if type(id) != type(1):
                        raise osv.except_osv(_('Error'), _("Problem in configuration `Record Id` in Server Action!"))
                    write_id = id
                    obj_pool.write(cr, uid, [write_id], res)

            if action.state == 'object_create':
                res = {}
                for exp in action.fields_lines:
                    euq = exp.value
                    if exp.type == 'equation':
                        obj_pool = self.pool.get(action.model_id.model)
                        obj = obj_pool.browse(cr, uid, context['active_id'], context=context)
                        expr = eval(euq, {'context':context, 'object': obj, 'time':time})
                    else:
                        expr = exp.value
                    res[exp.col1.name] = expr

                obj_pool = None
                res_id = False
                obj_pool = self.pool.get(action.srcmodel_id.model)
                res_id = obj_pool.create(cr, uid, res)
                cr.commit()
                if action.record_id:
                    self.pool.get(action.model_id.model).write(cr, uid, [context.get('active_id')], {action.record_id.name:res_id})

        return False

actions_server()

class act_window_close(osv.osv):
    _name = 'ir.actions.act_window_close'
    _inherit = 'ir.actions.actions'
    _table = 'ir_actions'
    _defaults = {
        'type': lambda *a: 'ir.actions.act_window_close',
    }
act_window_close()

# This model use to register action services.
TODO_STATES = [('open', 'Not Started'),
               ('done', 'Done'),
               ('skip','Skipped'),
               ('cancel','Cancel')]
class ir_actions_todo(osv.osv):
    _name = 'ir.actions.todo'
    _columns={
        'action_id': fields.many2one(
            'ir.actions.act_window', 'Action', select=True, required=True,
            ondelete='cascade'),
        'sequence': fields.integer('Sequence'),
        'active': fields.boolean('Active'),
        'state': fields.selection(TODO_STATES, string='State', required=True),
        'name':fields.char('Name', size=64),
        'note':fields.text('Text', translate=True),
    }
    _defaults={
        'state': lambda *a: 'open',
        'sequence': lambda *a: 10,
        'active': lambda *a: True,
    }
    _order="sequence"
ir_actions_todo()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

