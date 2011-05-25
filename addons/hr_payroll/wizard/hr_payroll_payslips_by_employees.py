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
from datetime import datetime
from dateutil import relativedelta

from osv import fields, osv
from tools.translate import _

class hr_payslip_employees(osv.osv_memory):

    _name ='hr.payslip.employees'
    _description = 'Generate payslips for all selected employees'
    _columns = {
        'employee_ids': fields.many2many('hr.employee', 'hr_employee_group_rel', 'payslip_id', 'employee_id', 'Employees'),
        'date_from': fields.date('Date From', required=True, help='Starting date of the payslips generated from here.'),
        'date_to': fields.date('Date To', required=True, help='Ending date of the payslips generated from here.'),
        'credit_note': fields.boolean('Credit Note', readonly=False, help='If its checked, indicates that generated payslips are refund payslips.'),
    }
    
    def default_get(self, cr, uid, fields, context=None):
        """
         To get default values for the object.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param fields: List of fields for which we want default values
         @param context: A standard dictionary
         @return: A dictionary which of fields with values.
        """
        if context is None:
            context = {}
        run_pool = self.pool.get('hr.payslip.run')
        res = super(hr_payslip_employees, self).default_get(cr, uid, fields, context=context)
        if context and context.get('active_id', False):
            data = run_pool.read(cr, uid, context['active_id'], ['date_start', 'date_end', 'credit_note'])
            if 'date_from' in fields:
                res.update({'date_from': data.get('date_start', False)})
            if 'date_to' in fields:
                res.update({'date_to': data.get('date_end', False)})
            if 'credit_note' in fields:
                res.update({'credit_note': data.get('credit_note', False)})
        return res

    def compute_sheet(self, cr, uid, ids, context=None):
        emp_pool = self.pool.get('hr.employee')
        slip_pool = self.pool.get('hr.payslip')
        run_pool = self.pool.get('hr.payslip.run')
        slip_ids = []
        if context is None:
            context = {}
        data = self.read(cr, uid, ids, context=context)[0]
        from_date =  data.get('date_from', False)
        to_date = data.get('date_to', False)
        if not data['employee_ids']:
            raise osv.except_osv(_("Warning !"), _("You must select employee(s) to generate payslip(s)"))
        for emp in emp_pool.browse(cr, uid, data['employee_ids'], context=context):
            slip_data = slip_pool.onchange_employee_id(cr, uid, [], from_date, to_date, emp.id, contract_id=False, context=context)
            res = {
                'employee_id': emp.id,
                'name': slip_data['value'].get('name', False),
                'struct_id': slip_data['value'].get('struct_id', False),
                'contract_id': slip_data['value'].get('contract_id', False),
                'payslip_run_id': context.get('active_id', False),
                'input_line_ids': [(0, 0, x) for x in slip_data['value'].get('input_line_ids', False)],
                'worked_days_line_ids': [(0, 0, x) for x in slip_data['value'].get('worked_days_line_ids', False)],
                'date_from': from_date,
                'date_to': to_date,
                'credit_note': data.get('credit_note'),
            }
            slip_ids.append(slip_pool.create(cr, uid, res, context=context))
        slip_pool.compute_sheet(cr, uid, slip_ids, context=context)
        return {'type': 'ir.actions.act_window_close'}

hr_payslip_employees()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: