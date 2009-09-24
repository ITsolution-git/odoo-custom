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

import time
import netsvc
from osv import fields, osv

class product_category(osv.osv):
    _inherit = "product.category"
    _columns = {
        'property_account_income_categ': fields.property(
            'account.account',
            type='many2one',
            relation='account.account',
            string="Income Account",
            method=True,
            view_load=True,
            help="This account will be used to value incoming stock(i.e. credit of incoming goods) for the current product category"),
        'property_account_expense_categ': fields.property(
            'account.account',
            type='many2one',
            relation='account.account',
            string="Expense Account",
            method=True,
            view_load=True,
            help="This account will be used to value outgoing stock(i.e. debit of outgoing goods) for the current product category"),
    }
product_category()

#----------------------------------------------------------
# Products
#----------------------------------------------------------
class product_template(osv.osv):
    _inherit = "product.template"
    _columns = {
        'taxes_id': fields.many2many('account.tax', 'product_taxes_rel',
            'prod_id', 'tax_id', 'Customer Taxes',
            domain=[('parent_id','=',False),('type_tax_use','in',['sale','all'])]),
        'supplier_taxes_id': fields.many2many('account.tax',
            'product_supplier_taxes_rel', 'prod_id', 'tax_id',
            'Supplier Taxes', domain=[('parent_id', '=', False),('type_tax_use','in',['purchase','all'])]),
        'property_account_income': fields.property(
            'account.account',
            type='many2one',
            relation='account.account',
            string="Income Account",
            method=True,
            view_load=True,
            help="This account will be used instead of the default one to value incoming stock for the current product"),
        'property_account_expense': fields.property(
            'account.account',
            type='many2one',
            relation='account.account',
            string="Expense Account",
            method=True,
            view_load=True,
            help="This account will be used instead of the default one to value outgoing stock for the current product"),
    }
product_template()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

