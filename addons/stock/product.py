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
    def view_header_get(self, cr, user, view_id, view_type, context):
        res = super(product_product, self).view_header_get(cr, user, view_id, view_type, context)
        if res: return res
        if (context.get('location', False)):
            return _('Products: ')+self.pool.get('stock.location').browse(cr, user, context['location'], context).name
        return res

    def get_product_available(self,cr,uid,ids,context={}):
        states=context.get('states',[])
        what=context.get('what',())
        if not ids:
            ids = self.search(cr, uid, [])
        res = {}.fromkeys(ids, 0.0)
        if not ids:
            return res

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

        states_str = ','.join(map(lambda s: "'%s'" % s, states))

        product2uom = {}
        for product in self.browse(cr, uid, ids, context=context):
            product2uom[product.id] = product.uom_id.id

        prod_ids_str = ','.join(map(str, ids))
        location_ids_str = ','.join(map(str, location_ids))
        results = []
        results2 = []

        from_date=context.get('from_date',False)
        to_date=context.get('to_date',False)
        date_str=False
        if from_date and to_date:
            date_str="date>='%s' and date<=%s"%(from_date,to_date)
        elif from_date:
            date_str="date>='%s'"%(from_date)
        elif to_date:
            date_str="date<='%s'"%(to_date)

        if 'in' in what:
            # all moves from a location out of the set to a location in the set
            cr.execute(
                'select sum(product_qty), product_id, product_uom '\
                'from stock_move '\
                'where location_id not in ('+location_ids_str+') '\
                'and location_dest_id in ('+location_ids_str+') '\
                'and product_id in ('+prod_ids_str+') '\
                'and state in ('+states_str+') '+ (date_str and 'and '+date_str+' ' or '') +''\
                'group by product_id,product_uom'
            )
            results = cr.fetchall()
        if 'out' in what:
            # all moves from a location in the set to a location out of the set
            cr.execute(
                'select sum(product_qty), product_id, product_uom '\
                'from stock_move '\
                'where location_id in ('+location_ids_str+') '\
                'and location_dest_id not in ('+location_ids_str+') '\
                'and product_id in ('+prod_ids_str+') '\
                'and state in ('+states_str+') '+ (date_str and 'and '+date_str+' ' or '') + ''\
                'group by product_id,product_uom'
            )
            results2 = cr.fetchall()
        uom_obj = self.pool.get('product.uom')
        for amount, prod_id, prod_uom in results:
            amount = uom_obj._compute_qty(cr, uid, prod_uom, amount,
                    context.get('uom', False) or product2uom[prod_id])
            res[prod_id] += amount
        for amount, prod_id, prod_uom in results2:
            amount = uom_obj._compute_qty(cr, uid, prod_uom, amount,
                    context.get('uom', False) or product2uom[prod_id])
            res[prod_id] -= amount
        return res

    def _get_product_available_func(states, what):
        def _product_available(self, cr, uid, ids, field_names=False, arg=False, context={}):
            context.update({
                'states':states,
                'what':what
            })
            stock=self.get_product_available(cr,uid,ids,context=context)
            res = {}
            for id in ids:
                res[id] = {}.fromkeys(field_names, 0.0)
                for a in field_names:
                    res[id][a] = stock.get(id, 0.0)
            return res

        return _product_available

    _product_qty_available = _get_product_available_func(('done',), ('in', 'out'))
    _product_virtual_available = _get_product_available_func(('confirmed','waiting','assigned','done'), ('in', 'out'))
    _product_outgoing_qty = _get_product_available_func(('confirmed','waiting','assigned'), ('out',))
    _product_incoming_qty = _get_product_available_func(('confirmed','waiting','assigned'), ('in',))


    _columns = {
        'qty_available': fields.function(_product_qty_available, method=True, type='float', string='Real Stock',multi='qty_available', help="Current quantities of products in selected locations or all internal if none have been selected."),
        'virtual_available': fields.function(_product_virtual_available, method=True, type='float', string='Virtual Stock',multi='qty_available', help="Futur stock for this product according to the selected location or all internal if none have been selected. Computed as: Real Stock - Outgoing + Incoming."),
        'incoming_qty': fields.function(_product_incoming_qty, method=True, type='float', string='Incoming',multi='qty_available', help="Quantities of products that are planned to arrive in selected locations or all internal if none have been selected."),
        'outgoing_qty': fields.function(_product_outgoing_qty, method=True, type='float', string='Outgoing',multi='qty_available', help="Quantities of products that are planned to leave in selected locations or all internal if none have been selected."),
        'track_production' : fields.boolean('Track Production Lots' , help="Force to use a Production Lot during production order"),
        'track_incoming' : fields.boolean('Track Incomming Lots', help="Force to use a Production Lot during receptions"),
        'track_outgoing' : fields.boolean('Track Outging Lots', help="Force to use a Production Lot during deliveries"),
    }
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False):
        res = super(product_product,self).fields_view_get(cr, uid, view_id, view_type, context, toolbar)
        if ('location' in context) and context['location']:
            location_info = self.pool.get('stock.location').browse(cr, uid, context['location'])
            fields=res.get('fields',{})
            if fields:
                if location_info.usage == 'supplier':
                    if fields.get('virtual_available'):
                        res['fields']['virtual_available']['string'] = 'Futur Receptions'
                    if fields.get('qty_available'):
                        res['fields']['qty_available']['string'] = 'Received Qty'

                if location_info.usage == 'internal':
                    if fields.get('virtual_available'):
                        res['fields']['virtual_available']['string'] = 'Futur Stock'

                if location_info.usage == 'customer':
                    if fields.get('virtual_available'):
                        res['fields']['virtual_available']['string'] = 'Futur Deliveries'
                    if fields.get('qty_available'):
                        res['fields']['qty_available']['string'] = 'Delivered Qty'

                if location_info.usage == 'inventory':
                    if fields.get('virtual_available'):
                        res['fields']['virtual_available']['string'] = 'Futur P&L'
                    res['fields']['qty_available']['string'] = 'P&L Qty'

                if location_info.usage == 'procurement':
                    if fields.get('virtual_available'):
                        res['fields']['virtual_available']['string'] = 'Futur Qty'
                    if fields.get('qty_available'):
                        res['fields']['qty_available']['string'] = 'Unplanned Qty'

                if location_info.usage == 'production':
                    if fields.get('virtual_available'):
                        res['fields']['virtual_available']['string'] = 'Futur Productions'
                    if fields.get('qty_available'):
                        res['fields']['qty_available']['string'] = 'Produced Qty'

        return res
product_product()


class product_template(osv.osv):
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

product_template()


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

