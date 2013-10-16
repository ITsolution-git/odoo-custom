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
    'name': 'WMS Accounting',
    'version': '1.1',
    'author': 'OpenERP SA',
    'summary': 'Inventory, Logistic, Valuation, Accounting',
    'description': """
TODO
======================
TODO

Key Features
------------
* Stock Valuation (periodical or automatic)
* Invoice from Picking

Dashboard / Reports for Warehouse Management will include:
----------------------------------------------------------
* TODO
    """,
    'website': 'http://www.openerp.com',
    'images': [],
    'depends': ['stock', 'account'],
    'category': 'Hidden',
    'sequence': 16,
    'demo': [
        'stock_account_demo.xml'
    ],
    'data': [
        'security/stock_account_security.xml',
        'security/ir.model.access.csv',
        'stock_account_data.xml',
        'wizard/stock_change_standard_price_view.xml',
        'wizard/stock_invoice_onshipping_view.xml',
        'product_data.xml',
        'product_view.xml',
        'stock_account_view.xml',
        'valuationandcostmethod.yml',
    ],
    'test': [

    ],
    'installable': True,
    'application': True,
    'auto_install': True,
}
