# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2004-2008 TINY SPRL. (http://tiny.be) All Rights Reserved.
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
#
##############################################################################

from osv import fields, osv

class product_product(osv.osv):
    _inherit = "product.product"
#    def view_header_get(self, cr, user, view_id, view_type, context):
#        print self, cr, user
#        res = super(product_product, self).view_header_get(cr, user, view_id, view_type, context)
#        if res: return res
#        if (not context.get('location', False)):
#            return False
#        cr.execute('select name from stock_location where id=%d', (context['location'],))
#        j = cr.fetchone()[0]
#        if j:
#            return 'Products: '+j
#        return False
#
    def _get_product_available_func(states, what):
        def _product_available(self, cr, uid, ids, name, arg, context={}):
            if context.get('shop', False):
                cr.execute('select warehouse_id from sale_shop where id=%d', (int(context['shop']),))
                res2 = cr.fetchone()
                if res2:
                    context['warehouse'] = res2[0]

            if context.get('warehouse', False):
                cr.execute('select lot_stock_id from stock_warehouse where id=%d', (int(context['warehouse']),))
                res2 = cr.fetchone()
                if res2:
                    context['location'] = res2[0]

            if context.get('location', False):
                location_ids = [context['location']]
            else:
                cr.execute("select lot_stock_id from stock_warehouse")
                location_ids = [id for (id,) in cr.fetchall()]

            # build the list of ids of children of the location given by id
            location_ids = self.pool.get('stock.location').search(cr, uid, [('location_id', 'child_of', location_ids)])
            res = self.pool.get('stock.location')._product_get_multi_location(cr, uid, location_ids, ids, context, states, what)
            for id in ids:
                res.setdefault(id, 0.0)
            return res
        return _product_available

    _product_qty_available = _get_product_available_func(('done',), ('in', 'out'))
    _product_virtual_available = _get_product_available_func(('confirmed','waiting','assigned','done'), ('in', 'out'))
    _product_outgoing_qty = _get_product_available_func(('confirmed','waiting','assigned'), ('out',))
    _product_incoming_qty = _get_product_available_func(('confirmed','waiting','assigned'), ('in',))
    _columns = {
        'qty_available': fields.function(_product_qty_available, method=True, type='float', string='Real Stock', help="Current quantities of products in selected locations or all internal if none have been selected."),
        'virtual_available': fields.function(_product_virtual_available, method=True, type='float', string='Virtual Stock', help="Futur stock for this product according to the selected location or all internal if none have been selected. Computed as: Real Stock - Outgoing + Incoming."),
        'incoming_qty': fields.function(_product_incoming_qty, method=True, type='float', string='Incoming', help="Quantities of products that are planned to arrive in selected locations or all internal if none have been selected."),
        'outgoing_qty': fields.function(_product_outgoing_qty, method=True, type='float', string='Outgoing', help="Quantities of products that are planned to leave in selected locations or all internal if none have been selected."),
        'track_production' : fields.boolean('Track Production Lots' , help="Force to use a Production Lot during production order"),
        'track_incoming' : fields.boolean('Track Incomming Lots', help="Force to use a Production Lot during receptions"),
        'track_outgoing' : fields.boolean('Track Outging Lots', help="Force to use a Production Lot during deliveries"),
    }
product_product()


class product_product(osv.osv):
    _name = 'product.template'
    _inherit = 'product.template'
    _columns = {
        'property_stock_procurement': fields.property(
            'stock.location',
            type='many2one',
            relation='stock.location',
            string="Procurement Location",
            method=True,
            view_load=True,
            help="For the current product (template), this stock location will be used, instead of the default one, as the source location for stock moves generated by procurements"),
        'property_stock_production': fields.property(
            'stock.location',
            type='many2one',
            relation='stock.location',
            string="Production Location",
            method=True,
            view_load=True,
            help="For the current product (template), this stock location will be used, instead of the default one, as the source location for stock moves generated by production orders"),
        'property_stock_inventory': fields.property(
            'stock.location',
            type='many2one',
            relation='stock.location',
            string="Inventory Location",
            method=True,
            view_load=True,
            help="For the current product (template), this stock location will be used, instead of the default one, as the source location for stock moves generated when you do an inventory"),
        'property_stock_account_input': fields.property('account.account',
            type='many2one', relation='account.account',
            string='Stock Input Account', method=True, view_load=True,
            help='This account will be used, instead of the default one, to value input stock'),
        'property_stock_account_output': fields.property('account.account',
            type='many2one', relation='account.account',
            string='Stock Output Account', method=True, view_load=True,
            help='This account will be used, instead of the default one, to value output stock'),
    }

product_product()


class product_category(osv.osv):
    _inherit = 'product.category'
    _columns = {
        'property_stock_journal': fields.property('account.journal',
            relation='account.journal', type='many2one',
            string='Stock journal', method=True, view_load=True,
            help="This journal will be used for the accounting move generated by stock move"),
        'property_stock_account_input_categ': fields.property('account.account',
            type='many2one', relation='account.account',
            string='Stock Input Account', method=True, view_load=True,
            help='This account will be used to value the input stock'),
        'property_stock_account_output_categ': fields.property('account.account',
            type='many2one', relation='account.account',
            string='Stock Output Account', method=True, view_load=True,
            help='This account will be used to value the output stock'),
    }

product_category()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

