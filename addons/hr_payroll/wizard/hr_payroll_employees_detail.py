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

from osv import fields, osv
from tools.translate import _

class hr_payroll_employees_detail(osv.osv):
   _name = "hr.payroll.employees.detail"
   _columns = {
        'employee_ids': fields.many2many('hr.employee', 'payroll_emp_rel','payroll_id','emp_id', 'Employees',required=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear', 'Fiscal Year', required=True)        
       } 
   def _get_defaults(self, cr, uid, ids, context={}):
        fiscal_ids=self.pool.get('account.fiscalyear').search(cr,uid,[])
        if fiscal_ids:
            return fiscal_ids[0]
        return False
   
   _defaults = {
        'fiscalyear_id':_get_defaults,
    }

   def print_report(self, cr, uid, ids, context={}):
        """
         To get the date and print the report
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param context: A standard dictionary
         @return : return report
        """

        datas = {'ids': context.get('active_ids', [])}
        
        res = self.read(cr, uid, ids, ['employee_ids', 'fiscalyear_id'], context)
        res = res and res[0] or {}
        datas['form'] = res
        datas['form']['fiscalyear_id']=res['fiscalyear_id'][0]
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'employees.salary',
            'datas': datas,
            'nodestroy':True,
       }
   
hr_payroll_employees_detail()