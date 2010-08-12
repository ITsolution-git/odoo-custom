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

import os

from osv import fields, osv
import tools
from tools.translate import _

class hr_employee_category(osv.osv):
    _name = "hr.employee.category"
    _description = "Employee Category"
    _columns = {
        'name': fields.char("Category", size=64, required=True),
        'parent_id': fields.many2one('hr.employee.category', 'Parent Category', select=True),
        'child_ids': fields.one2many('hr.employee.category', 'parent_id', 'Child Categories')
    }

    def _check_recursion(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        level = 100
        while len(ids):
            cr.execute('select distinct parent_id from hr_employee_category where id IN %s', (tuple(ids), ))
            ids = filter(None, map(lambda x:x[0], cr.fetchall()))
            if not level:
                return False
            level -= 1
        return True

    _constraints = [
        (_check_recursion, 'Error ! You cannot create recursive Categories.', ['parent_id'])
    ]

hr_employee_category()

class hr_employee_marital_status(osv.osv):
    _name = "hr.employee.marital.status"
    _description = "Employee Marital Status"
    _columns = {
        'name': fields.char('Marital Status', size=32, required=True),
        'description': fields.text('Status Description'),
    }

hr_employee_marital_status()

class hr_job(osv.osv):

    def _no_of_employee(self, cr, uid, ids, name, args, context=None):
        if context is None:
            context = {}
        res = {}
        for emp in self.browse(cr, uid, ids):
            res[emp.id] = len(emp.employee_ids or [])
        return res

    _name = "hr.job"
    _description = "Job Description"
    _columns = {
        'name': fields.char('Job Name', size=128, required=True, select=True),
        'expected_employees': fields.integer('Expected Employees', help='Required number of Employees'),
        'no_of_employee': fields.function(_no_of_employee, method=True, string='No of Employees', type='integer', help='Number of Employees selected'),
        'employee_ids': fields.one2many('hr.employee', 'job_id', 'Employees'),
        'description': fields.text('Job Description'),
        'requirements': fields.text('Requirements'),
        'department_id': fields.many2one('hr.department', 'Department'),
        'company_id': fields.many2one('res.company', 'Company'),
        'state': fields.selection([('open', 'Open'),('old', 'Old'),('recruit', 'In Recruitement')], 'State', readonly=True, required=True),
    }
    _defaults = {
        'expected_employees': 1,
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'hr.job', context=c),
        'state': 'open'
    }

    def job_old(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state': 'old'})
        return True

    def job_recruitement(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state': 'recruit'})
        return True

    def job_open(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state': 'open'})
        return True

hr_job()

class hr_employee(osv.osv):
    _name = "hr.employee"
    _description = "Employee"
    _inherits = {'resource.resource': "resource_id"}
    _columns = {
        'country_id': fields.many2one('res.country', 'Nationality'),
        'birthday': fields.date("Birthday"),
        'ssnid': fields.char('SSN No', size=32, help='Social Security Number'),
        'sinid': fields.char('SIN No', size=32, help="Social Insurance Number"),
        'otherid': fields.char('Other ID', size=32),
        'gender': fields.selection([('male', 'Male'),('female', 'Female')], 'Gender'),
        'marital': fields.many2one('hr.employee.marital.status', 'Marital Status'),
        'bank_account': fields.char('Bank Account', size=64),
        'partner_id': fields.related('company_id', 'partner_id', type='many2one', relation='res.partner', readonly=True),
        'department_id':fields.many2one('hr.department', 'Department'),
        'address_id': fields.many2one('res.partner.address', 'Working Address'),
        'address_home_id': fields.many2one('res.partner.address', 'Home Address'),
        'work_phone': fields.related('address_id', 'phone', type='char', string='Work Phone', readonly=True),
        'work_email': fields.related('address_id', 'email', type='char', size=240, string='Work E-mail', readonly=True),
        'work_location': fields.char('Office Location', size=32),
        'notes': fields.text('Notes'),
        'parent_id': fields.related('department_id', 'manager_id', relation='hr.employee', string='Manager', type='many2one', store=True, select=True),
        'category_ids': fields.many2many('hr.employee.category', 'employee_category_rel','category_id','emp_id','Category'),
        'child_ids': fields.one2many('hr.employee', 'parent_id', 'Subordinates'),
        'resource_id': fields.many2one('resource.resource', 'Resource', ondelete='cascade'),
        'coach_id': fields.many2one('hr.employee', 'Coach'),
        'job_id': fields.many2one('hr.job', 'Job'),
        'photo': fields.binary('Photo')
    }

    def _get_photo(self, cr, uid, context=None):
        if context is None:
            context = {}
        return open(os.path.join(
            tools.config['addons_path'], 'hr/image', 'photo.png'),
                    'rb') .read().encode('base64')

    _defaults = {
        'active': 1,
        'photo': _get_photo,
    }

    def _check_recursion(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        level = 100
        while len(ids):
            cr.execute('select distinct parent_id from hr_employee where id IN %s',(tuple(ids),))
            ids = filter(None, map(lambda x:x[0], cr.fetchall()))
            if not level:
                return False
            level -= 1
        return True

    _constraints = [
        (_check_recursion, 'Error ! You cannot create recursive Hierarchy of Employees.', ['parent_id'])
    ]

hr_employee()

class hr_department(osv.osv):
    _description = "Department"
    _inherit = 'hr.department'
    _columns = {
        'manager_id': fields.many2one('hr.employee', 'Manager'),
#        'member_ids': fields.many2many('hr.employee', 'hr_department_user_rel', 'department_id', 'user_id', 'Members'),
        'member_ids': fields.one2many('hr.employee', 'department_id', 'Members'),
#       finding problem to implement one2many field as "hr_departmen_user_rel" is used in another module query
    }

hr_department()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: