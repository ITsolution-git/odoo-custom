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
    "name" : "Sale CRM Stuff",
    "version" : "1.0",
    "author" : "Tiny",
    "website" : "http://www.openerp.com",
    "depends" : ["sale", "crm_configuration"],
    "category" : "Generic Modules/Sales & Purchases",
    "description": """
This module adds a shortcut on one or several cases in the CRM.
This shortcut allows you to generate a sale order based the selected case.
If different cases are open (a list), it generates one sale order by
case.
The case is then closed and linked to the generated sale order.

It also add a shortcut on one or several partners.
This shortcut allows you to generate a CRM case for the partners.

We suggest you to install this module if you installed both the sale and the
crm_configuration modules.
    """,
    "init_xml" : [],
    "demo_xml" : [],
    "update_xml" : [
        "sale_crm_wizard.xml",
        "sale_crm_view.xml",
        "process/sale_crm_process.xml"
    ],
    "active": False,
    "installable": True
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

