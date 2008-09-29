# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2004-2008 Tiny SPRL (http://tiny.be) All Rights Reserved.
#
# $Id$
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
###############################################################################
{
    "name" : "Timesheets",
    "version" : "1.0",
    "author" : "Tiny",
    "category" : "Generic Modules/Human Resources",
    "website" : "http://tinyerp.com/module_hr.html",
    "description": """
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
    "depends" : ["hr_timesheet", "hr_timesheet_invoice", "process"],
    "init_xml" : [],
    "demo_xml" : ["hr_timesheet_sheet_demo.xml",],
    "update_xml" : [
        "security/ir.model.access.csv",
        "hr_timesheet_sheet_view.xml",
        "hr_timesheet_workflow.xml",
        "process/hr_timesheet_sheet_process.xml"
    ],
    "active": False,
    "installable": True
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

