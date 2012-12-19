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

from datetime import datetime
from datetime import timedelta
import time
from openerp import SUPERUSER_ID

from openerp.osv import fields, osv
from openerp.tools.translate import _


def get_datetime(date_field):
    '''Return a datetime from a date string or a datetime string'''
    #complete date time if date_field contains only a date
    date_split = date_field.split(' ')
    if len(date_split) == 1:
        date_field = date_split[0] + " 00:00:00"

    return datetime.strptime(date_field[:19], '%Y-%m-%d %H:%M:%S')


class base_action_rule(osv.osv):
    """ Base Action Rules """

    _name = 'base.action.rule'
    _description = 'Action Rules'

    def _state_get(self, cr, uid, context=None):
        """ Get State """
        return self.state_get(cr, uid, context=context)

    def state_get(self, cr, uid, context=None):
        """ Get State """
        return [('', '')]

    _columns = {
        'name':  fields.char('Rule Name', size=64, required=True),
        'model_id': fields.many2one('ir.model', 'Related Document Model',
            required=True, domain=[('osv_memory', '=', False)]),
        'model': fields.related('model_id', 'model', type="char", size=256, string='Model'),
        'create_date': fields.datetime('Create Date', readonly=1),
        'active': fields.boolean('Active',
            help="When unchecked, the rule is hidden and will not be executed."),
        'sequence': fields.integer('Sequence',
            help="Gives the sequence order when displaying a list of rules."),
        'trg_date_type':  fields.selection([
            ('none', 'None'),
            ('create', 'Creation Date'),
            ('write', 'Last Modified Date'),
            ('action_last', 'Last Action Date'),
            ('date', 'Date'),
            ('deadline', 'Deadline'),
            ], 'Trigger Date', size=16),
        'trg_date_range': fields.integer('Delay after trigger date',
            help="Delay after the trigger date." \
            "You can put a negative number if you need a delay before the" \
            "trigger date, like sending a reminder 15 minutes before a meeting."),
        'trg_date_range_type': fields.selection([('minutes', 'Minutes'), ('hour', 'Hours'),
                                ('day', 'Days'), ('month', 'Months')], 'Delay type'),
        'act_user_id': fields.many2one('res.users', 'Set Responsible to'),
        'act_state': fields.selection(_state_get, 'Set State to', size=16),
        'act_followers': fields.many2many("res.partner", string="Set Followers"),
        'server_action_ids': fields.one2many('ir.actions.server', 'action_rule_id',
            domain="[('model_id', '=', model_id)]",
            string='Server Action',
            help="Example: email reminders, call object service, etc."),
        'filter_pre_id': fields.many2one('ir.filters', string='Before Filter',
            ondelete='restrict',
            domain="[('model_id', '=', model_id.model)]",
            help="If present, this condition must be satisfied before the update of the record."),
        'filter_id': fields.many2one('ir.filters', string='After Filter',
            ondelete='restrict',
            domain="[('model_id', '=', model_id.model)]",
            help="If present, this condition must be satisfied after the update of the record."),
        'last_run': fields.datetime('Last Run', readonly=1),
    }

    _defaults = {
        'active': True,
        'trg_date_type': 'none',
        'trg_date_range_type': 'day',
    }

    _order = 'sequence'

    def post_action(self, cr, uid, ids, model, precondition_ok=None, context=None):
        # Searching for action rules
        cr.execute("SELECT model.model, rule.id  FROM base_action_rule rule \
                        LEFT JOIN ir_model model on (model.id = rule.model_id) \
                        WHERE active and model = %s", (model,))
        res = cr.fetchall()
        # Check if any rule matching with current object
        for obj_name, rule_id in res:
            model_pool = self.pool.get(obj_name)
            # If the rule doesn't involve a time condition, run it immediately
            # Otherwise we let the scheduler run the action
            if self.browse(cr, uid, rule_id, context=context).trg_date_type == 'none':
                self._action(cr, uid, [rule_id], model_pool.browse(cr, uid, ids, context=context), precondition_ok=precondition_ok, context=context)
        return True

    def _wrap_create(self, old_create, model):
        """
        Return a wrapper around `old_create` calling both `old_create` and
        `post_action`, in that order.
        """
        def wrapper(cr, uid, vals, context=context):
            if context is None:
                context = {}
            new_id = old_create(cr, uid, vals, context=context)
            #As it is a new record, we can assume that the precondition is true for every filter. 
            #(There is nothing before the create so no condition)
            precondition_ok = {}
            precondition_ok[new_id] = {}
            for action in self.browse(cr, uid, self.search(cr, uid, [], context=context), context=context):
                if action.filter_pre_id:
                    precondition_ok[new_id][action.id] = False
                else:
                    precondition_ok[new_id][action.id] = True
            if not context.get('action'):
                self.post_action(cr, uid, [new_id], model, precondition_ok=precondition_ok, context=context)
            return new_id
        return wrapper

    def _wrap_write(self, old_write, model):
        """
        Return a wrapper around `old_write` calling both `old_write` and
        `post_action`, in that order.
        """
        def wrapper(cr, uid, ids, vals, context=context):
            old_records = {}
            if context is None:
                context = {}
            if isinstance(ids, (str, int, long)):
                ids = [ids]
            model_pool = self.pool.get(model)
            # We check for the pre-filter. We must apply it before the write
            precondition_ok = {}
            for id in ids:
                precondition_ok[id] = {}
                for action in self.browse(cr, uid, self.search(cr, uid, [], context=context), context=context):
                    precondition_ok[id][action.id] = True
                    if action.filter_pre_id and action.model_id.model == action.filter_pre_id.model_id:
                        ctx = dict(context)
                        ctx.update(eval(action.filter_pre_id.context))
                        obj_ids = []
                        if self.pool.get(action.model_id.model)!=None:
                            obj_ids = self.pool.get(action.model_id.model).search(cr, uid, eval(action.filter_pre_id.domain), context=ctx)
                        precondition_ok[id][action.id] = id in obj_ids
            old_write(cr, uid, ids, vals, context=context)
            if not context.get('action'):
                self.post_action(cr, uid, ids, model, precondition_ok=precondition_ok, context=context)
            return True
        return wrapper

    def _register_hook(self, cr, ids=None):
        """ Wrap the methods `create` and `write` of the models specified by
            the rules given by `ids` (or all existing rules if `ids` is `Ǹone`.)
        """
        if ids is None:
            ids = self.search(cr, SUPERUSER_ID, [])
        for action_rule in self.browse(cr, SUPERUSER_ID, ids):
            model = action_rule.model_id.model
            model_obj = self.pool.get(model)
            if not hasattr(model_obj, 'base_action_ruled'):
                model_obj.create = self._wrap_create(model_obj.create, model)
                model_obj.write = self._wrap_write(model_obj.write, model)
                model_obj.base_action_ruled = True
        return True

    def create(self, cr, uid, vals, context=None):
        res_id = super(base_action_rule, self).create(cr, uid, vals, context=context)
        self._register_hook(cr, [res_id])
        return res_id

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        super(base_action_rule, self).write(cr, uid, ids, vals, context=context)
        self._register_hook(cr, ids)
        return True

    def _check(self, cr, uid, automatic=False, use_new_cursor=False, \
                       context=None):
        """
        This Function is call by scheduler.
        """
        rule_ids = self.search(cr, uid, [], context=context)
        if context is None:
            context = {}
        for rule in self.browse(cr, uid, rule_ids, context=context):
            model = rule.model_id.model
            model_pool = self.pool.get(model)
            last_run = False
            if rule.last_run:
                last_run = get_datetime(rule.last_run)
            now = datetime.now()
            ctx = dict(context)            
            if rule.filter_id and rule.model_id.model == rule.filter_id.model_id:
                ctx.update(eval(rule.filter_id.context))
                obj_ids = model_pool.search(cr, uid, eval(rule.filter_id.domain), context=ctx)
            else:
                obj_ids = model_pool.search(cr, uid, [], context=ctx)
            for obj in model_pool.browse(cr, uid, obj_ids, context=ctx):
                # Calculate when this action should next occur for this object
                base = False
                if rule.trg_date_type=='create' and hasattr(obj, 'create_date'):
                    base = obj.create_date
                elif rule.trg_date_type=='write' and hasattr(obj, 'write_date'):
                    base = obj.write_date
                elif (rule.trg_date_type=='action_last'
                        and hasattr(obj, 'create_date')):
                    if hasattr(obj, 'date_action_last') and obj.date_action_last:
                        base = obj.date_action_last
                    else:
                        base = obj.create_date
                elif (rule.trg_date_type=='deadline'
                        and hasattr(obj, 'date_deadline')
                        and obj.date_deadline):
                    base = obj.date_deadline
                elif (rule.trg_date_type=='date'
                        and hasattr(obj, 'date')
                        and obj.date):
                    base = obj.date
                if base:
                    fnct = {
                        'minutes': lambda interval: timedelta(minutes=interval),
                        'day': lambda interval: timedelta(days=interval),
                        'hour': lambda interval: timedelta(hours=interval),
                        'month': lambda interval: timedelta(months=interval),
                    }
                    base = get_datetime(base)
                    delay = fnct[rule.trg_date_range_type](rule.trg_date_range)
                    action_date = base + delay
                    if (not last_run or (last_run <= action_date < now)):
                        try:
                            self._action(cr, uid, [rule.id], obj, context=ctx)
                            self.write(cr, uid, [rule.id], {'last_run': now}, context=context)
                        except Exception, e:
                            import traceback
                            print traceback.format_exc()
                        
                        

    def do_check(self, cr, uid, action, obj, precondition_ok=True, context=None):
        """ check Action """
        if context is None:
            context = {}
        ok = precondition_ok
        if action.filter_id and action.model_id.model == action.filter_id.model_id:
            ctx = dict(context)
            ctx.update(eval(action.filter_id.context))
            obj_ids = self.pool.get(action.model_id.model).search(cr, uid, eval(action.filter_id.domain), context=ctx)
            ok = ok and obj.id in obj_ids
        return ok

    def do_action(self, cr, uid, action, obj, context=None):
        """ Do Action """
        if context is None:
            context = {}
        ctx = dict(context)
        model_obj = self.pool.get(action.model_id.model)
        action_server_obj = self.pool.get('ir.actions.server')
        if action.server_action_ids:
            ctx.update({'active_model': action.model_id.model, 'active_id':obj.id, 'active_ids':[obj.id]})
            action_server_obj.run(cr, uid, [x.id for x in action.server_action_ids], context=ctx)

        write = {}
        if hasattr(obj, 'user_id') and action.act_user_id:
            write['user_id'] = action.act_user_id.id
        if hasattr(obj, 'date_action_last'):
            write['date_action_last'] = time.strftime('%Y-%m-%d %H:%M:%S')
        if hasattr(obj, 'state') and action.act_state:
            write['state'] = action.act_state

        model_obj.write(cr, uid, [obj.id], write, context)
        if hasattr(obj, 'state') and hasattr(obj, 'message_post') and action.act_state:
            model_obj.message_post(cr, uid, [obj], _(action.act_state), context=context)
        
        if hasattr(obj, 'message_subscribe') and action.act_followers:
            exits_followers = [x.id for x in obj.message_follower_ids]
            new_followers = [x.id for x in action.act_followers if x.id not in exits_followers]
            if new_followers:
                model_obj.message_subscribe(cr, uid, [obj.id], new_followers, context=context)
        return True

    def _action(self, cr, uid, ids, objects, scrit=None, precondition_ok=None, context=None):
        """ Do Action """
        if context is None:
            context = {}
        context.update({'action': True})
        if not isinstance(objects, list):
            objects = [objects]
        for action in self.browse(cr, uid, ids, context=context):
            for obj in objects:
                ok = True
                if precondition_ok!=None:
                    ok = precondition_ok[obj.id][action.id]
                if self.do_check(cr, uid, action, obj, precondition_ok=ok, context=context):
                    self.do_action(cr, uid, action, obj, context=context)
        context.update({'action': False})
        return True

class actions_server(osv.osv):
    _inherit = 'ir.actions.server'
    _columns = {
        'action_rule_id': fields.many2one("base.action.rule", string="Action Rule")
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
