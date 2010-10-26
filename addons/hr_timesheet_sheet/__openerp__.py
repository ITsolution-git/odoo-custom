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


{
    'name': 'Timesheets',
    'version': '1.0',
    'category': 'Generic Modules/Human Resources',
    'description': """
This module helps you to easily encode and validate timesheet and attendances
within the same view. The upper part of the view is for attendances and
track (sign in/sign out) events. The lower part is for timesheet.

Other tabs contains statistics views to help you analyse your
time or the time of your team:
* Time spent by day (with attendances)
* Time spent by project

This module also implements a complete timesheet validation process:
* Draft sheet
* Confirmation at the end of the period by the employee
* Validation by the project manager

The validation can be configured in the company:
* Period size (day, week, month, year)
* Maximal difference between timesheet and attendances
    """,
    'author': 'OpenERP SA',
    'website': 'http://www.openerp.com',
    'depends': ['hr_timesheet', 'hr_timesheet_invoice', 'process'],
    'init_xml': [],
    'update_xml': [
        'security/ir.model.access.csv',
        'security/hr_timesheet_sheet_security.xml',
        'hr_timesheet_sheet_view.xml',
        'hr_timesheet_workflow.xml',
        'process/hr_timesheet_sheet_process.xml',
        'board_hr_timesheet_view.xml',
        'report/hr_timesheet_report_view.xml',
        'report/timesheet_report_view.xml',
        'wizard/hr_timesheet_current_view.xml',
        'hr_timesheet_sheet_data.xml'
    ],
    'demo_xml': ['hr_timesheet_sheet_demo.xml',

                 ],
    'test':['test/test_hr_timesheet_sheet.yml'],
    'installable': True,
    'active': False,
    'certificate': '0073297700829',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
