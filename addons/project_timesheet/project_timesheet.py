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
import time
import datetime

from osv import fields, osv
import pooler
import tools
from tools.translate import _

class project_work(osv.osv):
    _inherit = "project.task.work"

    def get_user_related_details(self, cr, uid, user_id):
        res = {}
        emp_obj = self.pool.get('hr.employee')
        emp_id = emp_obj.search(cr, uid, [('user_id', '=', user_id)])
        if not emp_id:
            user_name = self.pool.get('res.users').read(cr, uid, [user_id], ['name'])[0]['name']
            raise osv.except_osv(_('Bad Configuration !'),
                 _('No employee defined for user "%s". You must create one.')% (user_name,))
        emp = self.pool.get('hr.employee').browse(cr, uid, emp_id[0])
        if not emp.product_id:
            raise osv.except_osv(_('Bad Configuration !'),
                 _('No product defined on the related employee.\nFill in the timesheet tab of the employee form.'))

        if not emp.journal_id:
            raise osv.except_osv(_('Bad Configuration !'),
                 _('No journal defined on the related employee.\nFill in the timesheet tab of the employee form.'))

        a =  emp.product_id.product_tmpl_id.property_account_expense.id
        if not a:
            a = emp.product_id.categ_id.property_account_expense_categ.id
            if not a:
                raise osv.except_osv(_('Bad Configuration !'),
                        _('No product and product category property account defined on the related employee.\nFill in the timesheet tab of the employee form.'))
        res['product_id'] = emp.product_id.id
        res['journal_id'] = emp.journal_id.id
        res['general_account_id'] = a
        res['product_uom_id'] = emp.product_id.uom_id.id
        return res

    def create(self, cr, uid, vals, *args, **kwargs):
        obj_timesheet = self.pool.get('hr.analytic.timesheet')
        task_obj = self.pool.get('project.task')
        vals_line = {}
        context = kwargs.get('context', {})
        obj_task = task_obj.browse(cr, uid, vals['task_id'])
        result = self.get_user_related_details(cr, uid, vals.get('user_id', uid))
        vals_line['name'] = '%s: %s' % (tools.ustr(obj_task.name), tools.ustr(vals['name']) or '/')
        vals_line['user_id'] = vals['user_id']
        vals_line['product_id'] = result['product_id']
        vals_line['date'] = vals['date'][:10]
        vals_line['unit_amount'] = vals['hours']
        acc_id = obj_task.project_id.analytic_account_id.id
        vals_line['account_id'] = acc_id
        res = obj_timesheet.on_change_account_id(cr, uid, False, acc_id)
        if res.get('value'):
            vals_line.update(res['value'])
        vals_line['general_account_id'] = result['general_account_id']
        vals_line['journal_id'] = result['journal_id']
        vals_line['amount'] = 0.0
        vals_line['product_uom_id'] = result['product_uom_id']
        amount = vals_line['unit_amount']
        prod_id = vals_line['product_id']
        unit = False
        timeline_id = obj_timesheet.create(cr, uid, vals=vals_line, context=context)

        # Compute based on pricetype
        amount_unit = obj_timesheet.on_change_unit_amount(cr, uid, timeline_id,
            prod_id, amount, unit, context=context)
        if amount_unit and 'amount' in amount_unit.get('value',{}):
            updv = { 'amount': amount_unit['value']['amount'] * (-1.0) }
            obj_timesheet.write(cr, uid, [timeline_id], updv, context=context)
        vals['hr_analytic_timesheet_id'] = timeline_id
        return super(project_work,self).create(cr, uid, vals, *args, **kwargs)

    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        obj = self.pool.get('hr.analytic.timesheet')
        timesheet_obj = self.pool.get('hr.analytic.timesheet')
        if isinstance(ids, (long, int)):
            ids = [ids,]

        for task in self.browse(cr, uid, ids, context=context):
            line_id = task.hr_analytic_timesheet_id
            if not line_id:
                # if a record is deleted from timesheet, the line_id will become
                # null because of the foreign key on-delete=set null
                continue
            vals_line = {}
            if 'name' in vals:
                vals_line['name'] = '%s: %s' % (tools.ustr(task.task_id.name), tools.ustr(vals['name']) or '/')
            if 'user_id' in vals:
                vals_line['user_id'] = vals['user_id']
                result = self.get_user_related_details(cr, uid, vals['user_id'])
                for fld in ('product_id', 'general_account_id', 'journal_id', 'product_uom_id'):
                    if result.get(fld, False):
                        vals_line[fld] = result[fld]
                        
            if 'date' in vals:
                vals_line['date'] = vals['date'][:10]
            if 'hours' in vals:
                vals_line['unit_amount'] = vals['hours']
                prod_id = vals_line.get('product_id', line_id.product_id.id) # False may be set
                # Compute based on pricetype
                amount_unit = obj.on_change_unit_amount(cr, uid, line_id.id,
                    prod_id=prod_id,
                    unit_amount=vals_line['unit_amount'], unit=False, context=context)

                if amount_unit and 'amount' in amount_unit.get('value',{}):
                    vals_line['amount'] = amount_unit['value']['amount'] * (-1.0)

            obj.write(cr, uid, [line_id.id], vals_line, context=context)
            
        return super(project_work,self).write(cr, uid, ids, vals, context)

    def unlink(self, cr, uid, ids, *args, **kwargs):
        hat_obj = self.pool.get('hr.analytic.timesheet')
        hat_ids = []
        for task in self.browse(cr, uid, ids):
            if task.hr_analytic_timesheet_id:
                hat_ids.append(task.hr_analytic_timesheet_id)
#            delete entry from timesheet too while deleting entry to task.
        if hat_ids:
            hat_obj.unlink(cr, uid, hat_ids, *args, **kwargs)
        return super(project_work,self).unlink(cr, uid, ids, *args, **kwargs)

    _columns={
        'hr_analytic_timesheet_id':fields.many2one('hr.analytic.timesheet','Related Timeline Id', ondelete='set null'),
    }

project_work()

class task(osv.osv):
    _inherit = "project.task"

    def unlink(self, cr, uid, ids, *args, **kwargs):
        for task_obj in self.browse(cr, uid, ids, *args, **kwargs):
            if task_obj.work_ids:
                work_ids = [x.id for x in task_obj.work_ids]
                self.pool.get('project.task.work').unlink(cr, uid, work_ids, *args, **kwargs)

        return super(task,self).unlink(cr, uid, ids, *args, **kwargs)

    def write(self, cr, uid, ids,vals,context=None):
        if context is None:
            context = {}
        if (vals.has_key('project_id') and vals['project_id']) or (vals.has_key('name') and vals['name']):
            vals_line = {}
            hr_anlytic_timesheet = self.pool.get('hr.analytic.timesheet')
            task_obj_l = self.browse(cr, uid, ids, context)
            if (vals.has_key('project_id') and vals['project_id']):
                project_obj = self.pool.get('project.project').browse(cr, uid, vals['project_id'])
                acc_id = project_obj.analytic_account_id.id

            for task_obj in task_obj_l:
                if len(task_obj.work_ids):
                    for task_work in task_obj.work_ids:
                        line_id = task_work.hr_analytic_timesheet_id
                        if (vals.has_key('project_id') and vals['project_id']):
                            vals_line['account_id'] = acc_id
                        if (vals.has_key('name') and vals['name']):
                            vals_line['name'] = '%s: %s' % (tools.ustr(vals['name']), tools.ustr(task_work.name) or '/')
                        hr_anlytic_timesheet.write(cr, uid, [line_id], vals_line, {})
        return super(task,self).write(cr, uid, ids, vals, context)

task()

class project_project(osv.osv):
    _inherit = "project.project"

    def name_get(self, cr, user, ids, context=None):
        if context is None:
            context = {}
        result = []
        for project in self.browse(cr, user, ids, context):
            name = "[%s] %s" % (project.analytic_account_id and project.analytic_account_id.code or '?', project.name)
            result.append((project.id, name))
        return result

project_project()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
