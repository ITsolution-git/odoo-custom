# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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
    "name": "Lunch Module",
    "author": "OpenERP SA",
    "Description": """
    The lunch module is for keeping record of the order placed and payment of the orders.
    The products are defined under categories and the payment records are maintained user wise
    Every user has a cashbox which keeps track of the amount paid for a particular order.

    """,
    "version": "0.1",
    "depends": ["base_tools"],
    "category" : "Tools",
    'description': """
    The base module to manage lunch

    keep track for the Lunch Order ,Cash Moves ,CashBox ,Product.
    Apply Different Category for the product.
    """,
    "init_xml": [],
    "update_xml": [
        'security/lunch_security.xml',
        'security/ir.model.access.csv',
        'wizard/lunch_order_cancel_view.xml',
        'wizard/lunch_order_confirm_view.xml',
        'wizard/lunch_cashbox_clean_view.xml',
        'lunch_view.xml',
        'lunch_report.xml',
        'report/report_lunch_order_view.xml',
    ],
    "demo_xml": ['lunch_demo.xml'],
    "test": ['test/test_lunch.yml', 'test/lunch_report.yml'],
    "installable": True,
    "certificate" : "001292377792581874189",
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
