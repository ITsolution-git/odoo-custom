#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    d$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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
{
    'name': 'Human Resource Payroll Accounting',
    'version': '1.0',
    'category': 'Generic Modules/Human Resources',
    'description': """Generic Payroll system Integrated with Accountings
    * Expense Encoding
    * Payment Encoding
    * Company Contribution Management
    """,
    'author':'OpenERP SA',
    'website':'http://www.openerp.com',
    'depends': [
        'hr_payroll',
        'account',
        'hr_expense'
    ],
    'init_xml': [
    ],
    'update_xml': [
        "security/ir.model.access.csv", 
        "hr_payroll_account_view.xml",
    ],
    'demo_xml': [
        'hr_payroll_demo.xml'
    ],
    'installable': True,
    'active': False,
    'certificate' : '00923971112835220957',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
