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
    "name" : "Human Resources Expenses Tracking",
    "version" : "1.0",
    "author" : "Tiny",
    "category" : "Generic Modules/Human Resources",
    "website" : "http://tinyerp.com/module_hr.html",
    "depends" : ["hr","account", "account_tax_include",],
    "description": """
    This module aims to manage employee's expenses.

    The whole workflow is implemented:
    * Draft expense
    * Confirmation of the sheet by the employee
    * Validation by his manager
    * Validation by the accountant and invoice creation
    * Payment of the invoice to the employee

    This module also use the analytic accounting and is compatible with
    the invoice on timesheet module so that you will be able to automatcally
    re-invoice your customer's expenses if your work by project.
    """,
    "init_xml" : [],
    "demo_xml" : ["hr_expense_demo.xml", "hr.expense.expense.csv"],
    "update_xml" : [
        "security/ir.model.access.csv",
        "hr_expense_sequence.xml",
        "hr_expense_workflow.xml",
        "hr_expense_view.xml",
        "hr_expense_report.xml",
    ],
    "active": False,
    "installable": True
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

