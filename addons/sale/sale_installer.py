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

from osv import fields, osv

class sale_installer(osv.osv_memory):
    _name = 'sale.installer'
    _inherit = 'res.config.installer'

    _columns = {
        'delivery': fields.boolean('Delivery Costs', 
            help="Allows you to compute delivery costs on your quotations."),
        'sale_journal': fields.boolean('Invoicing journals',
            help="Allows you to group and invoice your delivery orders according to different invoicing types: daily, weekly, etc."),
        'sale_layout': fields.boolean('Sales Order Layout Improvement',
            help="Provides some features to improve the layout of the Sales Order reports."),
        'sale_margin': fields.boolean('Margins in Sales Orders',
            help="Gives the margin of profitability by calculating "
                 "the difference between Unit Price and Cost Price."),
        'sale_order_dates': fields.boolean('Sales Order Dates',
            help="Adds commitment, requested and effective dates on Sales Orders."),
    }
    
sale_installer()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
