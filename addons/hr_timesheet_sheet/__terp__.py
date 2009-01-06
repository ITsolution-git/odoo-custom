# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


{
    'name': 'Timesheets',
    'version': '1.0',
    'category': 'Generic Modules/Human Resources',
    'description': """
This module help you easily encode and validate timesheet and attendances
within the same view. The upper part of the view is for attendances and
track (sign in/sign out) events. The lower part is for timesheet.

Others tabs contains statistics views to help you analyse your
time or the time of your team:
* Time spent by day (with attendances)
* Time spent by project

This module also implement a complete timesheet validation process:
* Draft sheet
* Confirmation at the end of the period by the employee
* Validation by the project manager

The validation can be configured in te company:
* Period size (day, week, month, year)
* Maximal difference between timesheet and attendances
    """,
    'author': 'Tiny',
    'website': 'http://www.openerp.com',
    'depends': ['hr_timesheet', 'hr_timesheet_invoice', 'process'],
    'init_xml': [],
    'update_xml': [
        'security/ir.model.access.csv',
        'hr_timesheet_sheet_view.xml',
        'hr_timesheet_workflow.xml',
        'process/hr_timesheet_sheet_process.xml'
    ],
    'demo_xml': ['hr_timesheet_sheet_demo.xml'],
    'installable': True,
    'active': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
