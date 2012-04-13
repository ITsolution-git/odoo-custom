# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 OpenERP SA (<http://openerp.com>).
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
{
    'name': 'French Payroll Rules',
    'category': 'Localization/Payroll',
    'author': 'SYNERPGY',
    'depends': ['hr_payroll', 'hr_payroll_account', 'l10n_fr'],
    'version': '1.0',
    'description': """
French Payroll Rules
=======================

    -Configuration of hr_payroll for french localization
	-Contributions Rules
	-Accounting configuration
	-New payslip report	
    """,

    'active': False,
    'update_xml':[
     'l10n_fr_hr_payroll_view.xml',
     'l10n_fr_hr_payroll_data.xml',
    ],
    'installable': True
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
