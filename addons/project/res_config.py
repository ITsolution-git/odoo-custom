# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp.osv import fields, osv
from openerp.tools.translate import _

class project_configuration(osv.osv_memory):
    _name = 'project.config.settings'
    _inherit = 'res.config.settings'

    _columns = {
        'module_sale_service': fields.boolean('Generate tasks from sale orders',
            help='This feature automatically creates project tasks from service products in sale orders. '
                 'In order to make it work,  the product has to be a service and \'Create Task Automatically\' '
                 'has to be flagged on the procurement tab in the product form.\n'
                 '-This installs the module sale_service.'),
        'module_pad': fields.boolean("Use integrated collaborative note pads on task",
            help='Lets the company customize which Pad installation should be used to link to new pads '
                 '(for example: http://ietherpad.com/).\n'
                 '-This installs the module pad.'),
        'module_project_timesheet': fields.boolean("Record timesheet lines per tasks",
            help='This allows you to transfer the entries under tasks defined for Project Management to '
                 'the timesheet line entries for particular date and user, with the effect of creating, '
                 'editing and deleting either ways.\n'
                 '-This installs the module project_timesheet.'),
        'module_project_issue': fields.boolean("Track issues and bugs",
            help='Provides management of issues/bugs in projects.\n'
                 '-This installs the module project_issue.'),
        'module_rating_project': fields.boolean('Allow customers to rate provided services',
            help="This allows customers to give rating on provided services"),
        'time_unit': fields.many2one('product.uom', 'Working time unit', required=True,
            help='This will set the unit of measure used in projects and tasks.\n'
                 'Changing the unit will only impact new entries.'),
        'module_project_issue_sheet': fields.boolean("Invoice working time on issues",
            help='Provides timesheet support for the issues/bugs management in project.\n'
                 '-This installs the module project_issue_sheet.'),
        'group_tasks_work_on_tasks': fields.boolean("Log work activities on tasks",
            implied_group='project.group_tasks_work_on_tasks',
            help="Allows you to compute work on tasks."),
        'group_time_work_estimation_tasks': fields.boolean("Manage time estimation on tasks",
            implied_group='project.group_time_work_estimation_tasks',
            help="Allows you to compute Time Estimation on tasks."),
        'generate_project_alias': fields.boolean("Automatically generate an email alias at the project creation",
            help="Odoo will generate an email alias at the project creation from project name."),
    }

    def get_default_time_unit(self, cr, uid, fields, context=None):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        return {'time_unit': user.company_id.project_time_mode_id.id}

    def set_time_unit(self, cr, uid, ids, context=None):
        config = self.browse(cr, uid, ids[0], context)
        user = self.pool.get('res.users').browse(cr, uid, uid, context)
        user.company_id.write({'project_time_mode_id': config.time_unit.id})

    def onchange_time_estimation_project_timesheet(self, cr, uid, ids, group_time_work_estimation_tasks, module_project_timesheet):
        if group_time_work_estimation_tasks or module_project_timesheet:
            return {'value': {'group_tasks_work_on_tasks': True}}
        return {}

    def set_default_generate_project_alias(self, cr, uid, ids, context=None):
        config_value = self.browse(cr, uid, ids, context=context).generate_project_alias
        self.pool.get('ir.values').set_default(cr, uid, 'project.config.settings', 'generate_project_alias', config_value)
