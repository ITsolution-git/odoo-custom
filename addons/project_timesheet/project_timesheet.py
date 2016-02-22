# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import time
import datetime
from dateutil.relativedelta import relativedelta

from openerp.addons.analytic.models import analytic
from openerp.osv import fields, osv
from openerp import tools
from openerp.tools.translate import _
from openerp.exceptions import UserError

class project_project(osv.osv):
    _inherit = 'project.project'

    _columns = {
        'subtask_project_id': fields.many2one(
            'project.project', string='Sub-task Project',
            help="Choosing a sub-tasks project will both enable sub-tasks and set their default project (possibly the project itself)",
            ondelete="restrict"),
    }

    def open_timesheets(self, cr, uid, ids, context=None):
        """ open Timesheets view """
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')

        project = self.browse(cr, uid, ids[0], context)
        view_context = {
            'search_default_account_id': [project.analytic_account_id.id],
            'default_account_id': project.analytic_account_id.id,
            'default_is_timesheet':True
        }
        help = _("""<p class="oe_view_nocontent_create">Record your timesheets for the project '%s'.</p>""") % (project.name,)

        res = mod_obj.get_object_reference(cr, uid, 'hr_timesheet', 'act_hr_timesheet_line_evry1_all_form')
        id = res and res[1] or False
        result = act_obj.read(cr, uid, [id], context=context)[0]
        result['name'] = _('Timesheets')
        result['context'] = view_context
        result['help'] = help
        return result

    def open_contract(self, cr, uid, ids, context=None):
        """ open Contract view """

        res = self.pool['ir.actions.act_window'].for_xml_id(cr, uid, 'project_timesheet', 'action_project_analytic_account', context=context)
        contract_ids = self.browse(cr, uid, ids, context=context)
        account_ids = [x.analytic_account_id.id for x in contract_ids]
        res['res_id'] = account_ids and account_ids[0] or None
        return res


class task(osv.osv):
    _inherit = "project.task"

    # Compute: effective_hours, total_hours, progress
    def _hours_get(self, cr, uid, ids, field_names, args, context=None):
        def _get_child_hour(child, res):
            if child.stage_id and child.stage_id.fold:
                return res[child.id]['effective_hours'] + res[child.id]['children_hours']
            else:
                return max(child.planned_hours, res[child.id]['effective_hours'] + res[child.id]['children_hours'])

        res = {}
        task_to_read = self.search(cr, uid, [('id', 'child_of', ids)])
        task_to_sort = {}
        for task in self.browse(cr, uid, task_to_read, context=context):
            res[task.id] = {
                'effective_hours': 0.0,
                'remaining_hours': task.planned_hours,
                'progress': 0.0,
                'total_hours': task.planned_hours,
                'delay_hours': 0.0,
                'children_hours' : 0.0
            }
            task_to_sort[task.id] = [child.id for child in task.child_ids]

        tasks_data = self.pool['account.analytic.line'].read_group(
            cr, uid, [('task_id', 'in', task_to_read)], ['task_id','unit_amount'], ['task_id'], context=context)
        tasks_data_dict = {data['task_id'][0] : data for data in tasks_data}
        for task_id in tools.topological_sort(task_to_sort):
            task = self.browse(cr, uid, task_id, context=context)
            values = {
                'effective_hours': tasks_data_dict.get(task_id, {}).get('unit_amount', 0.0),
                'children_hours' : sum([_get_child_hour(child, res) for child in task.child_ids])
            }
            values['remaining_hours'] = task.planned_hours - values['effective_hours'] - values['children_hours']
            values['total_hours'] = values['remaining_hours'] + values['effective_hours']
            values['delay_hours'] = values['total_hours'] - task.planned_hours
            values['progress'] = 0.0
            # TDE CHECK: if task.state in ('done','cancelled'):
            if task.stage_id and task.stage_id.fold:
                values['progress'] = 100.0
            elif task.planned_hours > 0.0:
                values['progress'] = round(min(100.0 * (values['effective_hours'] + values['children_hours']) / task.planned_hours, 99.99),2)
            res[task.id] = values
        return {k : val for k, val in res.iteritems() if k in ids} #Filter only needed result

    def _get_subtask_count(self, cr, uid, ids, field_names, args, context=None):
        res = dict.fromkeys(ids, 0)
        for task_id in ids:
            res[task_id] = (self.search_count(
                cr, uid, [('id', 'child_of', task_id)], context=context) - 1) # don't count task itself
        return res

    def _get_task(self, cr, uid, ids, context=None):
        res = []
        for line in self.pool['account.analytic.line'].search_read(
                cr, uid, [('task_id', '!=', False), ('id', 'in', ids)], context=context):
            res.append(line['task_id'][0])
        return self.pool['project.task'].search(cr, uid, [('id', 'parent_of', res)])

    def _get_parent_tasks(self, cr, uid, ids, context=None):
        return self.pool['project.task'].search(cr, uid, [('id', 'parent_of', ids)])

    def _get_total_hours(self):
        return super(task, self)._get_total_hours() + self.effective_hours

    _columns = {
        'remaining_hours': fields.function(_hours_get, string='Remaining Hours', multi='line_id', help="Total remaining time, can be re-estimated periodically by the assignee of the task.",
            store = {
                'project.task': (_get_parent_tasks, ['timesheet_ids', 'remaining_hours', 'planned_hours', 'parent_id', 'stage_id'], 10),
                'account.analytic.line': (_get_task, ['task_id', 'unit_amount'], 10),
            }),
        'children_hours': fields.function(_hours_get, string='Sub-tasks Hours', type='float', multi='line_id',
            help="Sum of the planned hours of all sub-tasks (when a sub-task is closed or its spent hours exceed its planned hours, spent hours are counted instead)",
            store = {
                'project.task': (_get_parent_tasks, ['timesheet_ids', 'remaining_hours', 'planned_hours', 'parent_id', 'stage_id'], 10),
                'account.analytic.line': (_get_task, ['task_id', 'unit_amount'], 10),
            }),
        'effective_hours': fields.function(_hours_get, string='Hours Spent', multi='line_id', help="Computed using the sum of the task work done.",
            store = {
                'project.task': (_get_parent_tasks, ['timesheet_ids', 'remaining_hours', 'planned_hours', 'parent_id', 'stage_id'], 10),
                'account.analytic.line': (_get_task, ['task_id', 'unit_amount'], 10),
            }),
        'total_hours': fields.function(_hours_get, string='Total', multi='line_id', help="Computed as: Time Spent + Remaining Time.",
            store = {
                'project.task': (_get_parent_tasks, ['timesheet_ids', 'remaining_hours', 'planned_hours', 'parent_id', 'stage_id'], 10),
                'account.analytic.line': (_get_task, ['task_id', 'unit_amount'], 10),
            }),
        'progress': fields.function(_hours_get, string='Working Time Progress (%)', multi='line_id', group_operator="avg", help="If the task has a progress of 99.99% you should close the task if it's finished or reevaluate the time",
            store = {
                'project.task': (_get_parent_tasks, ['timesheet_ids', 'remaining_hours', 'planned_hours', 'parent_id', 'state', 'stage_id'], 10),
                'account.analytic.line': (_get_task, ['task_id', 'unit_amount'], 10),
            }),
        'delay_hours': fields.function(_hours_get, string='Delay Hours', multi='line_id', help="Computed as difference between planned hours by the project manager and the total hours of the task.",
            store = {
                'project.task': (_get_parent_tasks, ['timesheet_ids', 'remaining_hours', 'planned_hours','parent_id', 'stage_id'], 10),
                'account.analytic.line': (_get_task, ['task_id', 'unit_amount'], 10),
           }),
        'timesheet_ids': fields.one2many('account.analytic.line', 'task_id', 'Timesheets'),
        'analytic_account_id': fields.related('project_id', 'analytic_account_id',
            type='many2one', relation='account.analytic.account', string='Analytic Account', store=True),
        'parent_id' : fields.many2one('project.task', string='Parent Task', select=True),
        'child_ids' : fields.one2many('project.task', 'parent_id', string="Sub-tasks"),
        'subtask_project_id': fields.related('project_id', 'subtask_project_id',  type='many2one', relation='project.project', string='Sub-task Project'),
        'subtask_count' : fields.function(_get_subtask_count, type='integer', string="Sub-task count"),
    }

    _defaults = {
        'progress': 0,
    }

    _constraints = [(osv.osv._check_recursion, 'Circular references are not permitted between tasks and sub-tasks', ['parent_id'])]

    def _prepare_delegate_values(self, cr, uid, ids, delegate_data, context=None):
        vals = super(task, self)._prepare_delegate_values(cr, uid, ids, delegate_data, context)
        for task in self.browse(cr, uid, ids, context=context):
            vals[task.id]['planned_hours'] += task.effective_hours
        return vals

    def onchange_project(self, cr, uid, ids, project_id, context=None):
        result = super(task, self).onchange_project(cr, uid, ids, project_id, context=context)
        if not project_id:
            return result
        if 'value' not in result:
            result['value'] = {}
        project = self.pool['project.project'].browse(cr, uid, project_id, context=context)
        return result

class res_partner(osv.osv):
    _inherit = 'res.partner'

    def unlink(self, cursor, user, ids, context=None):
        parnter_id=self.pool.get('project.project').search(cursor, user, [('partner_id', 'in', ids)])
        if parnter_id:
            raise UserError(_('You cannot delete a partner which is assigned to project, but you can uncheck the active box.'))
        return super(res_partner,self).unlink(cursor, user, ids,
                context=context)

class account_analytic_line(osv.osv):
    _inherit = "account.analytic.line"
    _columns = {
        'task_id' : fields.many2one('project.task', 'Task'),
    }
