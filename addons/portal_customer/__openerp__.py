# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2011 OpenERP S.A (<http://www.openerp.com>).
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
    'name' : "Customer Portal",
    'version' : "1.0",
    'depends' : ["portal"],
    'author' : "OpenERP SA",
    'category': 'Portal',
    'description': """
    The Customer Portal module helps customers to track their Sales Quotations, Orders, Invoices and various
    other possibilities.
    """,
    'website': 'http://www.openerp.com',
    'data': [
    ],
    "init_xml" : [
    ],
    "demo_xml" : [ 
        "portal_customer_demo.xml",
    ],
    "update_xml" : [
        "security/portal_customer_security.xml",
        "security/ir.model.access.csv",
        "board_portal_customer_view.xml",
        "portal_customer_view.xml",
        "portal_customer_menu.xml",
    ],
    'installable': True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
