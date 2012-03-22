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

class stock_config_settings(osv.osv_memory):
    _name = 'stock.config.settings'
    _inherit = 'res.config.settings'

    _columns = {
        'module_stock_no_autopicking': fields.boolean(
            "Allow an intermediate picking process to provide raw materials to production orders",
            help="""This module allows an intermediate picking process to provide raw materials to production orders.
                For example to manage production made by your suppliers (sub-contracting).
                To achieve this, set the assembled product which is sub-contracted to "No Auto-Picking"
                and put the location of the supplier in the routing of the assembly operation.
                This installs the module stock_no_autopicking."""),
        'module_claim_from_delivery': fields.boolean("Track claim issue from delivery",
            help="""Adds a Claim link to the delivery order.
                This installs the module claim_from_delivery."""),
        'module_stock_invoice_directly': fields.boolean("Invoice picking right after delivery",
            help="""This allows to automatically launch the invoicing wizard if the delivery is
                to be invoiced when you send or deliver goods.
                This installs the module stock_invoice_directly."""),
        'module_product_expiry': fields.boolean("Allow to manage expiry date on product",
            help="""Track different dates on products and production lots.
                The following dates can be tracked:
                    - end of life
                    - best before date
                    - removal date
                    - alert date.
                This installs the module product_expiry."""),
        'group_uom': fields.boolean("UOM per product",
            implied_group='product.group_uom',
            help="""Allows you to select and maintain different unit of measures per product."""),
        'group_stock_packaging': fields.boolean("Manage packaging by products",
            implied_group='base.group_stock_packaging',
            help="""Allows you to create and manage your packaging dimensions and types you want to be maintained in your system."""),
        'group_stock_production_lot': fields.boolean("Track production lots",
            implied_group='base.group_stock_production_lot',
            help="""This allows you to manage products produced by you using production lots (serial numbers).
                When you select a lot, you can get the upstream or downstream traceability of the products contained in lot."""),
        'group_stock_tracking_lot': fields.boolean("Track lots of your incoming and outgoing products",
            implied_group='base.group_stock_tracking_lot',
            help="""Allows you to get the upstream or downstream traceability of the products contained in lot."""),
        'group_stock_inventory_valuation': fields.boolean("Track inventory valuation by products",
            implied_group='base.group_stock_inventory_valuation',
            help="""This allows to split stock inventory lines according to production lots."""),
        'group_stock_counterpart_location': fields.boolean("Manage your stock counterpart by products",
            implied_group='base.group_stock_counterpart_location',
            help="""This allows to use different stock locations instead of the default one for procurement, production and inventory."""),
        'group_stock_inventory_properties': fields.boolean("Define stock locations",
            implied_group='base.group_stock_inventory_properties',
            help="""This allows you to set destination location for goods you send to partner, or goods you receive from the current partner."""),
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
