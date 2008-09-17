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
    "name" : "Invoice on analytic lines",
    "version" : "1.0",
    "author" : "Tiny",
    "category" : "Generic Modules/Accounting",
    "website" : "http://tinyerp.com/",
    "depends" : ["account",'hr_timesheet'],
    "description": """
Module to generate invoices based on costs (human ressources, expenses, ...).
You can define pricelists in analytic account, make some theorical revenue
reports, eso.""",
    "init_xml" : [],
    "demo_xml" : [
        'hr_timesheet_invoice_demo.xml'
    ],
    "update_xml" : [
        "security/ir.model.access.csv",
        'hr_timesheet_invoice_view.xml',
        'hr_timesheet_invoice_wizard.xml',
        'hr_timesheet_invoice_report.xml'
    ],
    "active": False,
    "installable": True
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

