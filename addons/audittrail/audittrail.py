# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from osv import fields, osv
from osv.osv import osv_pool
from tools.translate import _
import ir
import pooler
import time
import tools

class audittrail_rule(osv.osv):
    """
    For Auddittrail Rule
    """
    _name = 'audittrail.rule'
    _description = "Audittrail Rule"
    _columns = {
        "name": fields.char("Rule Name", size=32, required=True),
        "object_id": fields.many2one('ir.model', 'Object', required=True),
        "user_id": fields.many2many('res.users', 'audittail_rules_users',
                                            'user_id', 'rule_id', 'Users', help="if  User is not added then it will applicable for all users"),
        "log_read": fields.boolean("Log Reads"),
        "log_write": fields.boolean("Log Writes"),
        "log_unlink": fields.boolean("Log Deletes"),
        "log_create": fields.boolean("Log Creates"),
        "log_action": fields.boolean("Log Action"),
        "log_workflow": fields.boolean("Log Workflow"),
        "state": fields.selection((("draft", "Draft"),
                                   ("subscribed", "Subscribed")),
                                   "State", required=True),
        "action_id": fields.many2one('ir.actions.act_window', "Action ID"),

    }

    _defaults = {
        'state': lambda *a: 'draft',
        'log_create': lambda *a: 1,
        'log_unlink': lambda *a: 1,
        'log_write': lambda *a: 1,
    }

    _sql_constraints = [
        ('model_uniq', 'unique (object_id)', """There is a rule defined on this object\n You can not define other on the same!""")
    ]
    __functions = {}

    def subscribe(self, cr, uid, ids, *args):
        """
        Subscribe Rule for auditing changes on object and apply shortcut for logs on that object.
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of Auddittrail Rule’s IDs.
        @return: True
        """
        obj_action = self.pool.get('ir.actions.act_window')
        obj_model = self.pool.get('ir.model.data')
        #start Loop
        for thisrule in self.browse(cr, uid, ids):
            obj = self.pool.get(thisrule.object_id.model)
            if not obj:
                raise osv.except_osv(
                        _('WARNING: audittrail is not part of the pool'),
                        _('Change audittrail depends -- Setting rule as DRAFT'))
                self.write(cr, uid, [thisrule.id], {"state": "draft"})
            val = {
                 "name": 'View Log',
                 "res_model": 'audittrail.log',
                 "src_model": thisrule.object_id.model,
                 "domain": "[('object_id','=', " + str(thisrule.object_id.id) + "), ('res_id', '=', active_id)]"

            }
            id = obj_action.create(cr, uid, val)
            self.write(cr, uid, [thisrule.id], {"state": "subscribed", "action_id": id})
            keyword = 'client_action_relate'
            value = 'ir.actions.act_window,' + str(id)
            res = obj_model.ir_set(cr, uid, 'action', keyword, 'View_log_' + thisrule.object_id.model, [thisrule.object_id.model], value, replace=True, isobject=True, xml_id=False)
            #End Loop
        return True

    def unsubscribe(self, cr, uid, ids, *args):
        """
        Unsubscribe Auditing Rule on object
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of Auddittrail Rule’s IDs.
        @return: True
        """
        obj_action = self.pool.get('ir.actions.act_window')
        val_obj = self.pool.get('ir.values')
        #start Loop
        for thisrule in self.browse(cr, uid, ids):
            if thisrule.id in self.__functions:
                for function in self.__functions[thisrule.id]:
                    setattr(function[0], function[1], function[2])
            w_id = obj_action.search(cr, uid, [('name', '=', 'View Log'), ('res_model', '=', 'audittrail.log'), ('src_model', '=', thisrule.object_id.model)])
            obj_action.unlink(cr, uid, w_id)
            value = "ir.actions.act_window" + ',' + str(w_id[0])
            val_id = val_obj.search(cr, uid, [('model', '=', thisrule.object_id.model), ('value', '=', value)])
            if val_id:
                res = ir.ir_del(cr, uid, val_id[0])
            self.write(cr, uid, [thisrule.id], {"state": "draft"})
        #End Loop
        return True

audittrail_rule()


class audittrail_log(osv.osv):
    """
    For Audittrail Log
    """
    _name = 'audittrail.log'
    _description = "Audittrail Log"

    _columns = {
        "name": fields.char("Name", size=32),
        "object_id": fields.many2one('ir.model', 'Object'),
        "user_id": fields.many2one('res.users', 'User'),
        "method": fields.selection((('read', 'Read'),
                                    ('write', 'Write'),
                                    ('unlink', 'Delete'),
                                    ('create', 'Create'),
                                    ('action','Action'),
                                    ('workflow','Workflow')), "Method"),
        "timestamp": fields.datetime("Date"),
        "res_id": fields.integer('Resource Id'),
        "method_name": fields.char("Method Name", size=32),
        "line_ids": fields.one2many('audittrail.log.line', 'log_id', 'Log lines'),
    }

    _defaults = {
        "timestamp": lambda *a: time.strftime("%Y-%m-%d %H:%M:%S")
    }
    _order = "timestamp desc"

audittrail_log()


class audittrail_log_line(osv.osv):
    """
    Audittrail Log Line.
    """
    _name = 'audittrail.log.line'
    _description = "Log Line"
    _columns = {
          'field_id': fields.many2one('ir.model.fields', 'Fields', required=True),
          'log_id': fields.many2one('audittrail.log', 'Log'),
          'log': fields.integer("Log ID"),
          'old_value': fields.text("Old Value"),
          'new_value': fields.text("New Value"),
          'old_value_text': fields.text('Old value Text'),
          'new_value_text': fields.text('New value Text'),
          'field_description': fields.char('Field Description', size=64),
        }

audittrail_log_line()


class audittrail_objects_proxy(osv_pool):
    """ Uses Object proxy for auditing changes on object of subscribed Rules"""

    def get_value_text(self, cr, uid, field_name, values, object, context=None):
        """
        Gets textual values for the fields
        e.g.: For field of type many2one it gives its name value instead of id

        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param field_name: List of fields for text values
        @param values: Values for field to be converted into textual values
        @return: values: List of textual values for given fields
        """
        if not context:
            context = {}
        pool = pooler.get_pool(cr.dbname)
        f_id = pool.get('ir.model.fields').search(cr, uid, [('name', '=', field_name), ('model_id', '=', object.id)])
        if f_id:
            field = pool.get('ir.model.fields').read(cr, uid, f_id)[0]
            model = field['relation']

            if field['ttype'] == 'many2one':
                if values:
                    if type(values) == tuple:
                        values = values[0]
                    val = pool.get(model).read(cr, uid, [values], [pool.get(model)._rec_name])
                    if val:
                        return val[0][pool.get(model)._rec_name]
            elif field['ttype'] == 'many2many':
                value = []
                if values:
                    for id in values:
                        val = pool.get(model).read(cr, uid, [id], [pool.get(model)._rec_name])
                        if val:
                            value.append(val[0][pool.get(model)._rec_name])
                return value

            elif field['ttype'] == 'one2many':
                if values:
                    value = []
                    for id in values:
                        val = pool.get(model).read(cr, uid, [id], [pool.get(model)._rec_name])

                        if val:
                            value.append(val[0][pool.get(model)._rec_name])
                    return value
            return values

    def create_log_line(self, cr, uid, id, object, lines=[]):
        """
        Creates lines for changed fields with its old and new values

        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param object: Object who's values are being changed
        @param lines: List of values for line is to be created
        """
        pool = pooler.get_pool(cr.dbname)
        obj = pool.get(object.model)
        #start Loop
        for line in lines:
            if obj._inherits:
                inherits_ids = pool.get('ir.model').search(cr, uid, [('model', '=', obj._inherits.keys()[0])])
                f_id = pool.get('ir.model.fields').search(cr, uid, [('name', '=', line['name']), ('model_id', 'in', (object.id, inherits_ids[0]))])
            else:
                f_id = pool.get('ir.model.fields').search(cr, uid, [('name', '=', line['name']), ('model_id', '=', object.id)])
            if f_id:
                fields = pool.get('ir.model.fields').read(cr, uid, f_id)
                old_value = 'old_value' in line and  line['old_value'] or ''
                new_value = 'new_value' in line and  line['new_value'] or ''
                old_value_text = 'old_value_text' in line and  line['old_value_text'] or ''
                new_value_text = 'new_value_text' in line and  line['new_value_text'] or ''

                if old_value_text == new_value_text:
                    continue
                if fields[0]['ttype'] == 'many2one':
                    if type(old_value) == tuple:
                        old_value = old_value[0]
                    if type(new_value) == tuple:
                        new_value = new_value[0]
                vals = {
                        "log_id": id,
                        "field_id": f_id[0],
                        "old_value": old_value,
                        "new_value": new_value,
                        "old_value_text": old_value_text,
                        "new_value_text": new_value_text,
                        "field_description": fields[0]['field_description']
                        }
                line_id = pool.get('audittrail.log.line').create(cr, uid, vals)
                cr.commit()
                #End Loop
        return True


    def log_fct(self, db, uid, object, method, fct_src, *args):
        """
        Logging function: This function is performs logging oprations according to method
        @param db: the current database
        @param uid: the current user’s ID for security checks,
        @param object: Object who's values are being changed
        @param method: method to log: create, read, write, unlink
        @param fct_src: execute method of Object proxy

        @return: Returns result as per method of Object proxy
        """
        logged_uids = []
        res2 = args
        pool = pooler.get_pool(db)
        cr = pooler.get_db(db).cursor()
        obj_ids = pool.get('ir.model').search(cr, uid, [('model', '=', object)])
        model_object = pool.get('ir.model').browse(cr, uid, obj_ids)[0]

        if method in ('create'):
            res_id = fct_src(db, uid, object, method, *args)
            cr.commit()
            new_value = pool.get(model_object.model).read(cr, uid, [res_id], args[0].keys())[0]
            if 'id' in new_value:
                del new_value['id']
            if not logged_uids or uid in logged_uids:
                resource_pool = pool.get(model_object.model)
                resource_name = hasattr(resource_pool,'name_get')
            if not resource_name:
                resource_name = pool.get(model_object.model).name_get(cr, uid, [res_id])
                resource_name = resource_name and resource_name[0][1] or ''
                vals = {
                        "method": method,
                        "object_id": model_object.id,
                        "user_id": uid, "res_id": res_id,
                        "name": resource_name
                        }
                id = pool.get('audittrail.log').create(cr, uid, vals)
                lines = []
                for field in new_value:
                    if new_value[field]:
                        line = {
                              'name': field,
                              'new_value': new_value[field],
                              'new_value_text': self.get_value_text(cr, uid, field, new_value[field], model_object)
                              }
                        lines.append(line)
                self.create_log_line(cr, uid, id, model_object, lines)
            cr.commit()
            cr.close()
            return res_id

        if method in ('write'):
            res_ids = args[0]
            for res_id in res_ids:
                old_values = pool.get(model_object.model).read(cr, uid, res_id, args[1].keys())
                old_values_text = {}
                for field in args[1].keys():
                    old_values_text[field] = self.get_value_text(cr, uid, field, old_values[field], model_object)
                res = fct_src(db, uid, object, method, *args)
                cr.commit()
                if res:
                    new_values = pool.get(model_object.model).read(cr, uid, res_ids, args[1].keys())[0]
                    if not logged_uids or uid in logged_uids:
                        resource_name = pool.get(model_object.model).name_get(cr, uid, [res_id])
                        resource_name = resource_name and resource_name[0][1] or ''
                        id = pool.get('audittrail.log').create(cr, uid, {"method": method, "object_id": model_object.id, "user_id": uid, "res_id": res_id, "name": resource_name})
                        lines = []
                        for field in args[1].keys():
                            if args[1].keys():
                                line = {
                                      'name': field,
                                      'new_value': field in new_values and new_values[field] or '',
                                      'old_value': field in old_values and old_values[field] or '',
                                      'new_value_text': self.get_value_text(cr, uid, field, new_values[field], model_object),
                                      'old_value_text': old_values_text[field]
                                      }
                                lines.append(line)
                        cr.commit()
                        self.create_log_line(cr, uid, id, model_object, lines)
                cr.close()
                return res

        if method in ('read'):
            res_ids = args[0]
            old_values = {}
            res = fct_src(db, uid, object, method, *args)
            if type(res) == list:

                for v in res:
                    old_values[v['id']] = v
            else:
                old_values[res['id']] = res
            for res_id in old_values:
                if not logged_uids or uid in logged_uids:
                    resource_name = pool.get(model_object.model).name_get(cr, uid, [res_id])
                    resource_name = resource_name and resource_name[0][1] or ''
                    id = pool.get('audittrail.log').create(cr, uid, {"method": method, "object_id": model_object.id, "user_id": uid, "res_id": res_id, "name": resource_name})
                    lines = []
                    for field in old_values[res_id]:
                        if old_values[res_id][field]:
                            line = {
                                      'name': field,
                                      'old_value': old_values[res_id][field],
                                      'old_value_text': self.get_value_text(cr, uid, field, old_values[res_id][field], model_object)
                                      }
                            lines.append(line)
                cr.commit()
                self.create_log_line(cr, uid, id, model_object, lines)
            cr.close()
            return res

        if method in ('unlink'):
            res_ids = args[0]
            old_values = {}
            for res_id in res_ids:
                old_values[res_id] = pool.get(model_object.model).read(cr, uid, res_id, [])

            for res_id in res_ids:
                if not logged_uids or uid in logged_uids:
                    resource_name = pool.get(model_object.model).name_get(cr, uid, [res_id])
                    resource_name = resource_name and resource_name[0][1] or ''
                    id = pool.get('audittrail.log').create(cr, uid, {"method": method, "object_id": model_object.id, "user_id": uid, "res_id": res_id, "name": resource_name})
                    lines = []
                    for field in old_values[res_id]:
                        if old_values[res_id][field]:
                            line = {
                                  'name': field,
                                  'old_value': old_values[res_id][field],
                                  'old_value_text': self.get_value_text(cr, uid, field, old_values[res_id][field], model_object)
                                  }
                            lines.append(line)
                    cr.commit()
                    self.create_log_line(cr, uid, id, model_object, lines)
            res = fct_src(db, uid, object, method, *args)
            cr.close()
            return res
        cr.close()

    def action_log(self, db, uid, object, method, fct_src, *args):
        """
        Logging function: This function is performs logging oprations according to method
        @param db: the current database
        @param uid: the current user’s ID for security checks,
        @param object: Object who's values are being changed
        @param method: method to log: create, read, write, unlink
        @param fct_src: execute method of Object proxy

        @return: Returns result as per method of Object proxy
        """
        logged_uids = []
        pool = pooler.get_pool(db)
        cr = pooler.get_db(db).cursor()
        obj_ids = pool.get('ir.model').search(cr, uid, [('model', '=', object)])
        model_object = pool.get('ir.model').browse(cr, uid, obj_ids)[0]

        res_id = args[0]

        old_values_text = {}
        old_values = {}
        new_values = {}
        old_values = pool.get(model_object.model).read(cr, uid, res_id,[])[0]
        for field in old_values.keys():
            old_values_text[field] = self.get_value_text(cr, uid, field, old_values[field], model_object)

        res = super(audittrail_objects_proxy, self).execute(db, uid, object, method,*args)
        cr.commit()
        new_values = pool.get(model_object.model).read(cr, uid, res_id,[])[0]

        resource_pool = pool.get(model_object.model)
        resource_name = hasattr(resource_pool,'name_get')
        if not resource_name:
            resource_name = pool.get(model_object.model).name_get(cr, uid, args[0])
            resource_name = resource_name and resource_name[0][1] or ''
        id =args and args[0] and args[0][0]
        l_id = pool.get('audittrail.log').create(cr, uid, {"method": 'action', "object_id": model_object.id, "user_id": uid, "res_id": id, "name": resource_name, "method_name": method})
        diff = {}
        log_line_pool = pool.get('audittrail.log.line')
        for field in old_values.keys():
            if old_values[field] == new_values[field]:
                continue
            else:
                diff.update({field: (old_values[field], new_values[field])})

            if model_object._inherits:
                inherits_ids = pool.get('ir.model').search(cr, uid, [('model', '=', model_object._inherits.keys()[0])])
                f_id = pool.get('ir.model.fields').search(cr, uid, [('name', '=', field), ('model_id', 'in', (model_object.id, inherits_ids[0]))])
            else:
                f_id = pool.get('ir.model.fields').search(cr, uid, [('name', '=', field), ('model_id', '=', model_object.id)])
            if f_id:
                fields = pool.get('ir.model.fields').read(cr, uid, f_id)
                log_line_pool.create(cr, uid, {'field_id': f_id[0], 'log_id': l_id, \
                                'old_value': str(old_values[field]),\
                                 'new_value': str(new_values[field]),\
                                 'old_value_text':str(old_values_text[field]),
                                 'new_value_text':self.get_value_text(cr, uid, field, new_values[field], model_object),
                                 })
        cr.commit()
        cr.close()
        return res


    def execute(self, db, uid, object, method, *args, **kw):
        """
        Overrides Object Proxy execute method
        @param db: the current database
        @param uid: the current user’s ID for security checks,
        @param object: Object who's values are being changed
        @param method: method to log: create, read, write, unlink

        @return: Returns result as per method of Object proxy
        """

        pool = pooler.get_pool(db)
        cr = pooler.get_db(db).cursor()
        cr.autocommit(True)
        logged_uids = []
        fct_src = super(audittrail_objects_proxy, self).execute

        def my_fct(db, uid, object, method, *args):
            field = method
            rule = False
            obj_ids = pool.get('ir.model').search(cr, uid, [('model', '=', object)])
            for obj_name in pool.obj_list():
                if obj_name == 'audittrail.rule':
                    rule = True
            if not rule:
                return fct_src(db, uid, object, method, *args)
            if not obj_ids:
                return fct_src(db, uid, object, method, *args)
            rule_ids = pool.get('audittrail.rule').search(cr, uid, [('object_id', '=', obj_ids[0]), ('state', '=', 'subscribed')])
            if not rule_ids:
                return fct_src(db, uid, object, method, *args)

            for thisrule in pool.get('audittrail.rule').browse(cr, uid, rule_ids):
                for user in thisrule.user_id:
                    logged_uids.append(user.id)
                if not logged_uids or uid in logged_uids:
                    if field in ('read', 'write', 'create', 'unlink'):

                        if getattr(thisrule, 'log_' + field):
                            return self.log_fct(db, uid, object, method, fct_src, *args)

                    elif field not in ('default_get','read','fields_view_get','fields_get','search','search_count','name_search','name_get','get','request_get', 'get_sc', 'unlink') and (field != 'write' and field != 'create'):
                        if thisrule.log_action:
                            return self.action_log(db, uid, object, method, fct_src, *args)
                return fct_src(db, uid, object, method, *args)
        res = my_fct(db, uid, object, method, *args)
        cr.close()
        return res


    def workflow_log(self, db, uid, object, method,*args, **argv):
        """
        Logging function: This function is performs logging oprations according to method
        @param db: the current database
        @param uid: the current user’s ID for security checks,
        @param object: Object who's values are being changed
        @param method: method to log: create, read, write, unlink
        @param fct_src: execute method of Object proxy

        @return: Returns result as per method of Object proxy
        """

        logged_uids = []
        pool = pooler.get_pool(db)
        cr = pooler.get_db(db).cursor()
        obj_ids = pool.get('ir.model').search(cr, uid, [('model', '=', object)])
        model_object = pool.get('ir.model').browse(cr, uid, obj_ids)[0]

        workflow_obj = pool.get('workflow')
        wkf_ids = workflow_obj.search(cr, uid, [('osv', '=', object)])
        wkf_name= workflow_obj.browse(cr, uid, wkf_ids)[0].name

        res_id = args[0]
        old_values_text = {}
        old_values = pool.get(model_object.model).read(cr, uid, res_id)
        for field in old_values.keys():
            old_values_text[field] = self.get_value_text(cr, uid, field, old_values[field], model_object)

        res = super(audittrail_objects_proxy, self).exec_workflow(db, uid, object, method, *args, **argv)
        cr.commit()
        new_values = pool.get(model_object.model).read(cr, uid, res_id)

        resource_name = pool.get(model_object.model).name_get(cr, uid, [args[0]])
        resource_name = resource_name and resource_name[0][1] or ''
        l_id = pool.get('audittrail.log').create(cr, uid, {"method": 'workflow', "object_id": model_object.id, "user_id": uid, "res_id": args[0], "name": resource_name +"/"+ wkf_name })
        lines = []
        diff = {}
        log_line_pool = pool.get('audittrail.log.line')

        for field in old_values.keys():
            if old_values[field] == new_values[field]:
                continue
            else:
                diff.update({field: (old_values[field], new_values[field])})
                f_id = pool.get('ir.model.fields').search(cr, uid, [('name', '=', field), ('model_id', '=', model_object.id)])
                log_line_pool.create(cr, uid, {'field_id': f_id[0], 'log_id': l_id, \
                                'old_value': str(old_values[field]),\
                                 'new_value': str(new_values[field]),\
                                 'old_value_text':str(old_values_text[field]),
                                 'new_value_text':self.get_value_text(cr, uid, field, new_values[field], model_object),
                                 })
        cr.commit()
        cr.close()
        return res


    def exec_workflow(self, db, uid, object, method, *args, **argv):
        pool = pooler.get_pool(db)
        cr = pooler.get_db(db).cursor()
        cr.autocommit(True)
        logged_uids = []
        fct_src = super(audittrail_objects_proxy, self).execute
        field = method
        rule = False
        obj_ids = pool.get('ir.model').search(cr, uid, [('model', '=', object)])
        for obj_name in pool.obj_list():
            if obj_name == 'audittrail.rule':
                rule = True
        if not rule:
            return super(audittrail_objects_proxy, self).exec_workflow(db, uid, object, method, *args, **argv)
        if not obj_ids:
            return super(audittrail_objects_proxy, self).exec_workflow(db, uid, object, method, *args, **argv)
        rule_ids = pool.get('audittrail.rule').search(cr, uid, [('object_id', '=', obj_ids[0]), ('state', '=', 'subscribed')])
        if not rule_ids:
             res = super(audittrail_objects_proxy, self).exec_workflow(db, uid, object, method, *args, **argv)

        for thisrule in pool.get('audittrail.rule').browse(cr, uid, rule_ids):
            for user in thisrule.user_id:
                logged_uids.append(user.id)
            if not logged_uids or uid in logged_uids:
                 if thisrule.log_workflow:
                     return self.workflow_log(db, uid, object, method, *args,**argv)
            return super(audittrail_objects_proxy, self).exec_workflow(db, uid, object, method, *args, **argv)

        cr.close()

audittrail_objects_proxy()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

