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

from datetime import datetime
from dateutil.relativedelta import relativedelta

from osv import fields, osv
from tools import config
from tools.translate import _
import math
import netsvc
import time
import tools

import decimal_precision as dp


#----------------------------------------------------------
# Incoterms
#----------------------------------------------------------
class stock_incoterms(osv.osv):
    _name = "stock.incoterms"
    _description = "Incoterms"
    _columns = {
        'name': fields.char('Name', size=64, required=True,help="Incoterms are series of sales terms.They are used to divide transaction costs and responsibilities between buyer and seller and reflect state-of-the-art transportation practices."),
        'code': fields.char('Code', size=3, required=True,help="Code for Incoterms"),
        'active': fields.boolean('Active', help="If the active field is set to true, it will allow you to hide the incoterms without removing it."),
    }
    _defaults = {
        'active': lambda *a: True,
    }

stock_incoterms()


#----------------------------------------------------------
# Stock Location
#----------------------------------------------------------
class stock_location(osv.osv):
    _name = "stock.location"
    _description = "Location"
    _parent_name = "location_id"
    _parent_store = True
    _parent_order = 'id'
    _order = 'parent_left'

    def name_get(self, cr, uid, ids, context={}):
        if not len(ids):
            return []
        reads = self.read(cr, uid, ids, ['name','location_id'], context)
        res = []
        for record in reads:
            name = record['name']
            if context.get('full',False):
                if record['location_id']:
                    name = record['location_id'][1]+' / '+name
                res.append((record['id'], name))
            else:
                res.append((record['id'], name))
        return res

    def _complete_name(self, cr, uid, ids, name, args, context):
        """ Forms complete name of location from parent location to child location.
        @return: Dictionary of values
        """
        def _get_one_full_name(location, level=4):
            if location.location_id:
                parent_path = _get_one_full_name(location.location_id, level-1) + "/"
            else:
                parent_path = ''
            return parent_path + location.name
        res = {}
        for m in self.browse(cr, uid, ids, context=context):
            res[m.id] = _get_one_full_name(m)
        return res

    def _product_qty_available(self, cr, uid, ids, field_names, arg, context={}):
        """ Finds real and virtual quantity for product available at particular location.
        @return: Dictionary of values
        """
        res = {}
        for id in ids:
            res[id] = {}.fromkeys(field_names, 0.0)
        if ('product_id' not in context) or not ids:
            return res
        #location_ids = self.search(cr, uid, [('location_id', 'child_of', ids)])
        for loc in ids:
            context['location'] = [loc]
            prod = self.pool.get('product.product').browse(cr, uid, context['product_id'], context)
            if 'stock_real' in field_names:
                res[loc]['stock_real'] = prod.qty_available
            if 'stock_virtual' in field_names:
                res[loc]['stock_virtual'] = prod.virtual_available
        return res

    def product_detail(self, cr, uid, id, field, context={}):
        """ Finds detail of product like price type, currency and then calculates its price. 
        @param field: Field name
        @return: Calculated price
        """
        res = {}
        res[id] = {}
        final_value = 0.0
        field_to_read = 'virtual_available'
        if field == 'stock_real_value':
            field_to_read = 'qty_available'
        cr.execute('select distinct product_id from stock_move where (location_id=%s) or (location_dest_id=%s)', (id, id))
        result = cr.dictfetchall()
        if result:
            # Choose the right filed standard_price to read
            # Take the user company
            price_type_id = self.pool.get('res.users').browse(cr,uid,uid).company_id.property_valuation_price_type.id
            pricetype = self.pool.get('product.price.type').browse(cr, uid, price_type_id)
            for r in result:
                c = (context or {}).copy()
                c['location'] = id
                product = self.pool.get('product.product').read(cr, uid, r['product_id'], [field_to_read], context=c)
                # Compute the amount_unit in right currency

                context['currency_id'] = self.pool.get('res.users').browse(cr,uid,uid).company_id.currency_id.id
                amount_unit = self.pool.get('product.product').browse(cr,uid,r['product_id']).price_get(pricetype.field, context)[r['product_id']]

                final_value += (product[field_to_read] * amount_unit)
        return final_value

    def _product_value(self, cr, uid, ids, field_names, arg, context={}):
        """ Calculates real and virtual stock value of a product.
        @param field_names: Name of field 
        @return: Dictionary of values
        """
        result = {}
        for id in ids:
            result[id] = {}.fromkeys(field_names, 0.0)
        for field_name in field_names:
            for loc in ids:
                ret_dict = self.product_detail(cr, uid, loc, field=field_name)
                result[loc][field_name] = ret_dict
        return result

    _columns = {
        'name': fields.char('Location Name', size=64, required=True, translate=True),
        'active': fields.boolean('Active', help="If the active field is set to true, it will allow you to hide the stock location without removing it."),
        'usage': fields.selection([('supplier', 'Supplier Location'), ('view', 'View'), ('internal', 'Internal Location'), ('customer', 'Customer Location'), ('inventory', 'Inventory'), ('procurement', 'Procurement'), ('production', 'Production')], 'Location Type', required=True),
        'allocation_method': fields.selection([('fifo', 'FIFO'), ('lifo', 'LIFO'), ('nearest', 'Nearest')], 'Allocation Method', required=True),

        'complete_name': fields.function(_complete_name, method=True, type='char', size=100, string="Location Name"),

        'stock_real': fields.function(_product_qty_available, method=True, type='float', string='Real Stock', multi="stock"),
        'stock_virtual': fields.function(_product_qty_available, method=True, type='float', string='Virtual Stock', multi="stock"),

        #'account_id': fields.many2one('account.account', string='Inventory Account', domain=[('type', '!=', 'view')]),
        'location_id': fields.many2one('stock.location', 'Parent Location', select=True, ondelete='cascade'),
        'child_ids': fields.one2many('stock.location', 'location_id', 'Contains'),

        'chained_location_id': fields.many2one('stock.location', 'Chained Location If Fixed'),
        'chained_location_type': fields.selection([('none', 'None'), ('customer', 'Customer'), ('fixed', 'Fixed Location')],
            'Chained Location Type', required=True),
        'chained_auto_packing': fields.selection(
            [('auto', 'Automatic Move'), ('manual', 'Manual Operation'), ('transparent', 'Automatic No Step Added')],
            'Automatic Move',
            required=True,
            help="This is used only if you select a chained location type.\n" \
                "The 'Automatic Move' value will create a stock move after the current one that will be "\
                "validated automatically. With 'Manual Operation', the stock move has to be validated "\
                "by a worker. With 'Automatic No Step Added', the location is replaced in the original move."
            ),
        'chained_delay': fields.integer('Chained lead time (days)'),
        'address_id': fields.many2one('res.partner.address', 'Location Address'),
        'icon': fields.selection(tools.icons, 'Icon', size=64),

        'comment': fields.text('Additional Information'),
        'posx': fields.integer('Corridor (X)'),
        'posy': fields.integer('Shelves (Y)'),
        'posz': fields.integer('Height (Z)'),

        'parent_left': fields.integer('Left Parent', select=1),
        'parent_right': fields.integer('Right Parent', select=1),
        'stock_real_value': fields.function(_product_value, method=True, type='float', string='Real Stock Value', multi="stock"),
        'stock_virtual_value': fields.function(_product_value, method=True, type='float', string='Virtual Stock Value', multi="stock"),
        'company_id': fields.many2one('res.company', 'Company', required=True,select=1),
        'scrap_location': fields.boolean('Scrap Location', help='Check this box if the current location is a place for destroyed items'),
    }
    _defaults = {
        'active': lambda *a: 1,
        'usage': lambda *a: 'internal',
        'allocation_method': lambda *a: 'fifo',
        'chained_location_type': lambda *a: 'none',
        'chained_auto_packing': lambda *a: 'manual',
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.location', context=c),
        'posx': lambda *a: 0,
        'posy': lambda *a: 0,
        'posz': lambda *a: 0,
        'icon': lambda *a: False,
        'scrap_location': lambda *a: False,
    }

    def chained_location_get(self, cr, uid, location, partner=None, product=None, context={}):
        """ Finds chained location
        @param location: Location id
        @param partner: Partner id
        @param product: Product id
        @return: List of values
        """
        result = None
        if location.chained_location_type == 'customer':
            if partner:
                result = partner.property_stock_customer
        elif location.chained_location_type == 'fixed':
            result = location.chained_location_id
        if result:
            return result, location.chained_auto_packing, location.chained_delay
        return result

    def picking_type_get(self, cr, uid, from_location, to_location, context={}):
        """ Gets type of picking.
        @param from_location: Source location
        @param to_location: Destination location
        @return: Location type
        """
        result = 'internal'
        if (from_location.usage=='internal') and (to_location and to_location.usage in ('customer', 'supplier')):
            result = 'delivery'
        elif (from_location.usage in ('supplier', 'customer')) and (to_location.usage=='internal'):
            result = 'in'
        return result

    def _product_get_all_report(self, cr, uid, ids, product_ids=False,
            context=None):
        return self._product_get_report(cr, uid, ids, product_ids, context,
                recursive=True)

    def _product_get_report(self, cr, uid, ids, product_ids=False,
            context=None, recursive=False):
        """ Finds the product quantity and price for particular location.
        @param product_ids: Ids of product
        @param recursive: True or False
        @return: Dictionary of values
        """
        if context is None:
            context = {}
        product_obj = self.pool.get('product.product')
        # Take the user company and pricetype
        price_type_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.property_valuation_price_type.id
        pricetype = self.pool.get('product.price.type').browse(cr, uid, price_type_id)
        context['currency_id'] = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id

        if not product_ids:
            product_ids = product_obj.search(cr, uid, [])

        products = product_obj.browse(cr, uid, product_ids, context=context)
        products_by_uom = {}
        products_by_id = {}
        for product in products:
            products_by_uom.setdefault(product.uom_id.id, [])
            products_by_uom[product.uom_id.id].append(product)
            products_by_id.setdefault(product.id, [])
            products_by_id[product.id] = product

        result = {}
        result['product'] = []
        for id in ids:
            quantity_total = 0.0
            total_price = 0.0
            for uom_id in products_by_uom.keys():
                fnc = self._product_get
                if recursive:
                    fnc = self._product_all_get
                ctx = context.copy()
                ctx['uom'] = uom_id
                qty = fnc(cr, uid, id, [x.id for x in products_by_uom[uom_id]],
                        context=ctx)
                for product_id in qty.keys():
                    if not qty[product_id]:
                        continue
                    product = products_by_id[product_id]
                    quantity_total += qty[product_id]

                    # Compute based on pricetype
                    # Choose the right filed standard_price to read
                    amount_unit = product.price_get(pricetype.field, context)[product.id]
                    price = qty[product_id] * amount_unit
                    # price = qty[product_id] * product.standard_price

                    total_price += price
                    result['product'].append({
                        'price': amount_unit,
                        'prod_name': product.name,
                        'code': product.default_code, # used by lot_overview_all report!
                        'variants': product.variants or '',
                        'uom': product.uom_id.name,
                        'prod_qty': qty[product_id],
                        'price_value': price,
                    })
        result['total'] = quantity_total
        result['total_price'] = total_price
        return result

    def _product_get_multi_location(self, cr, uid, ids, product_ids=False, context={}, 
                                    states=['done'], what=('in', 'out')):
        """ 
        @param product_ids: Ids of product
        @param states: List of states
        @param what: Tuple of
        @return: 
        """
        product_obj = self.pool.get('product.product')
        context.update({
            'states': states,
            'what': what,
            'location': ids
        })
        return product_obj.get_product_available(cr, uid, product_ids, context=context)

    def _product_get(self, cr, uid, id, product_ids=False, context={}, states=['done']):
        """
        @param product_ids:
        @param states:
        @return: 
        """
        ids = id and [id] or []
        return self._product_get_multi_location(cr, uid, ids, product_ids, context, states)

    def _product_all_get(self, cr, uid, id, product_ids=False, context={}, states=['done']):
        # build the list of ids of children of the location given by id
        ids = id and [id] or []
        location_ids = self.search(cr, uid, [('location_id', 'child_of', ids)])
        return self._product_get_multi_location(cr, uid, location_ids, product_ids, context, states)

    def _product_virtual_get(self, cr, uid, id, product_ids=False, context={}, states=['done']):
        return self._product_all_get(cr, uid, id, product_ids, context, ['confirmed', 'waiting', 'assigned', 'done'])

    #
    # TODO:
    #    Improve this function
    #
    # Returns:
    #    [ (tracking_id, product_qty, location_id) ]
    #
    def _product_reserve(self, cr, uid, ids, product_id, product_qty, context={}):
        """ 
        @param product_id: Id of product
        @param product_qty: Quantity of product
        @return: List of Values or False
        """
        result = []
        amount = 0.0
        for id in self.search(cr, uid, [('location_id', 'child_of', ids)]):
            cr.execute("select product_uom,sum(product_qty) as product_qty from stock_move where location_dest_id=%s and location_id<>%s and product_id=%s and state='done' group by product_uom", (id, id, product_id))
            results = cr.dictfetchall()
            cr.execute("select product_uom,-sum(product_qty) as product_qty from stock_move where location_id=%s and location_dest_id<>%s and product_id=%s and state in ('done', 'assigned') group by product_uom", (id, id, product_id))
            results += cr.dictfetchall()

            total = 0.0
            results2 = 0.0
            for r in results:
                amount = self.pool.get('product.uom')._compute_qty(cr, uid, r['product_uom'], r['product_qty'], context.get('uom', False))
                results2 += amount
                total += amount

            if total <= 0.0:
                continue

            amount = results2
            if amount > 0:
                if amount > min(total, product_qty):
                    amount = min(product_qty, total)
                result.append((amount, id))
                product_qty -= amount
                total -= amount
                if product_qty <= 0.0:
                    return result
                if total <= 0.0:
                    continue
        return False

stock_location()


class stock_tracking(osv.osv):
    _name = "stock.tracking"
    _description = "Stock Tracking Lots"
    
    def get_create_tracking_lot(self, cr, uid, ids, tracking_lot):
        """
        @param tracking_lot: Name of tracking lot
        @return: 
        """
        tracking_lot_list = self.search(cr, uid, [('name', '=', tracking_lot)],
                                            limit=1)
        if tracking_lot_list:
            tracking_lot = tracking_lot_list[0]
        tracking_obj = self.browse(cr, uid, tracking_lot)
        if not tracking_obj:
            tracking_lot_vals = {
                'name': tracking_lot
                }
            tracking_lot = self.create(cr, uid, tracking_lot_vals)
        return tracking_lot
    def checksum(sscc):
        salt = '31' * 8 + '3'
        sum = 0
        for sscc_part, salt_part in zip(sscc, salt):
            sum += int(sscc_part) * int(salt_part)
        return (10 - (sum % 10)) % 10
    checksum = staticmethod(checksum)

    def make_sscc(self, cr, uid, context={}):
        sequence = self.pool.get('ir.sequence').get(cr, uid, 'stock.lot.tracking')
        return sequence + str(self.checksum(sequence))

    _columns = {
        'name': fields.char('Tracking ID', size=64, required=True),
        'active': fields.boolean('Active', help="If the active field is set to true, it will allow you to hide the tracking lots without removing it."),
        'serial': fields.char('Reference', size=64),
        'move_ids': fields.one2many('stock.move', 'tracking_id', 'Moves Tracked'),
        'date': fields.datetime('Created Date', required=True),
    }
    
    _defaults = {
        'active': lambda *a: 1,
        'name': make_sscc,
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=100):
        if not args:
            args = []
        if not context:
            context = {}
        ids = self.search(cr, user, [('serial', '=', name)]+ args, limit=limit, context=context)
        ids += self.search(cr, user, [('name', operator, name)]+ args, limit=limit, context=context)
        return self.name_get(cr, user, ids, context)

    def name_get(self, cr, uid, ids, context={}):
        if not len(ids):
            return []
        res = [(r['id'], r['name']+' ['+(r['serial'] or '')+']') for r in self.read(cr, uid, ids, ['name', 'serial'], context)]
        return res

    def unlink(self, cr, uid, ids, context=None):
        raise osv.except_osv(_('Error'), _('You can not remove a lot line !'))

stock_tracking()


#----------------------------------------------------------
# Stock Picking
#----------------------------------------------------------
class stock_picking(osv.osv):
    _name = "stock.picking"
    _description = "Picking List"

    def _set_maximum_date(self, cr, uid, ids, name, value, arg, context):
        """ Calculates planned date if it is greater than 'value'.
        @param name: Name of field
        @param value: Value of field
        @param arg: User defined argument 
        @return: True or False
        """
        if not value:
            return False
        if isinstance(ids, (int, long)):
            ids = [ids]
        for pick in self.browse(cr, uid, ids, context):
            sql_str = """update stock_move set
                    date_planned='%s'
                where
                    picking_id=%d """ % (value, pick.id)

            if pick.max_date:
                sql_str += " and (date_planned='" + pick.max_date + "' or date_planned>'" + value + "')"
            cr.execute(sql_str)
        return True

    def _set_minimum_date(self, cr, uid, ids, name, value, arg, context):
        """ Calculates planned date if it is less than 'value'.
        @param name: Name of field
        @param value: Value of field
        @param arg: User defined argument 
        @return: True or False
        """
        if not value:
            return False
        if isinstance(ids, (int, long)):
            ids = [ids]
        for pick in self.browse(cr, uid, ids, context):
            sql_str = """update stock_move set
                    date_planned='%s'
                where
                    picking_id=%s """ % (value, pick.id)
            if pick.min_date:
                sql_str += " and (date_planned='" + pick.min_date + "' or date_planned<'" + value + "')"
            cr.execute(sql_str)
        return True

    def get_min_max_date(self, cr, uid, ids, field_name, arg, context={}):
        """ Finds minimum and maximum dates for picking.
        @return: Dictionary of values
        """
        res = {}
        for id in ids:
            res[id] = {'min_date': False, 'max_date': False}
        if not ids:
            return res
        cr.execute("""select
                picking_id,
                min(date_planned),
                max(date_planned)
            from
                stock_move
            where
                picking_id=ANY(%s)
            group by
                picking_id""",(ids,))
        for pick, dt1, dt2 in cr.fetchall():
            res[pick]['min_date'] = dt1
            res[pick]['max_date'] = dt2
        return res

    def create(self, cr, user, vals, context=None):
        if ('name' not in vals) or (vals.get('name')=='/'):
            seq_obj_name =  'stock.picking.' + vals['type']
            vals['name'] = self.pool.get('ir.sequence').get(cr, user, seq_obj_name)
        type_list = {
            'out':_('Packing List'),
            'in':_('Reception'),
            'internal': _('Internal picking'),
            'delivery': _('Delivery order')
        }
        if not vals.get('auto_picking', False):
            message = type_list.get(vals.get('type',_('Picking'))) + " '" + vals['name'] + "' "+ _("created.")
            self.log(cr, user, id, message)
        return super(stock_picking, self).create(cr, user, vals, context)

    _columns = {
        'name': fields.char('Reference', size=64, select=True),
        'origin': fields.char('Origin', size=64, help="Reference of the document that produced this picking."),
        'backorder_id': fields.many2one('stock.picking', 'Back Order', help="If the picking is splitted then the picking id in available state of move for this picking is stored in Backorder."),
        'type': fields.selection([('out', 'Sending Goods'), ('in', 'Getting Goods'), ('internal', 'Internal'), ('delivery', 'Delivery')], 'Shipping Type', required=True, select=True, help="Shipping type specify, goods coming in or going out."),
        'active': fields.boolean('Active', help="If the active field is set to true, it will allow you to hide the picking without removing it."),
        'note': fields.text('Notes'),

        'location_id': fields.many2one('stock.location', 'Location', help="Keep empty if you produce at the location where the finished products are needed." \
                "Set a location if you produce at a fixed location. This can be a partner location " \
                "if you subcontract the manufacturing operations."),
        'location_dest_id': fields.many2one('stock.location', 'Dest. Location',help="Location where the system will stock the finished products."),
        'move_type': fields.selection([('direct', 'Direct Delivery'), ('one', 'All at once')], 'Delivery Method', required=True, help="It specifies goods to be delivered all at once or by direct delivery"),
        'state': fields.selection([
            ('draft', 'Draft'),
            ('auto', 'Waiting'),
            ('confirmed', 'Confirmed'),
            ('assigned', 'Available'),
            ('done', 'Done'),
            ('cancel', 'Cancelled'),
            ], 'State', readonly=True, select=True,
            help=' * The \'Draft\' state is used when a user is encoding a new and unconfirmed picking. \
            \n* The \'Confirmed\' state is used for stock movement to do with unavailable products. \
            \n* The \'Available\' state is set automatically when the products are ready to be moved.\
            \n* The \'Waiting\' state is used in MTO moves when a movement is waiting for another one.'),
        'min_date': fields.function(get_min_max_date, fnct_inv=_set_minimum_date, multi="min_max_date",
                 method=True, store=True, type='datetime', string='Expected Date', select=1, help="Expected date for Picking. Default it takes current date"),
        'date': fields.datetime('Order Date', help="Date of Order"),
        'date_done': fields.datetime('Date Done', help="Date of Completion"),
        'max_date': fields.function(get_min_max_date, fnct_inv=_set_maximum_date, multi="min_max_date",
                 method=True, store=True, type='datetime', string='Max. Expected Date', select=2),
        'move_lines': fields.one2many('stock.move', 'picking_id', 'Internal Moves', states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}),
        'delivery_line':fields.one2many('stock.delivery', 'picking_id', 'Delivery lines', readonly=True),
        'auto_picking': fields.boolean('Auto-Picking'),
        'address_id': fields.many2one('res.partner.address', 'Partner', help="Address of partner"),
        'invoice_state': fields.selection([
            ("invoiced", "Invoiced"),
            ("2binvoiced", "To Be Invoiced"),
            ("none", "Not from Picking")], "Invoice Status",
            select=True, required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'company_id': fields.many2one('res.company', 'Company', required=True,select=1),
    }
    _defaults = {
        'name': lambda self, cr, uid, context: '/',
        'active': lambda *a: 1,
        'state': lambda *a: 'draft',
        'move_type': lambda *a: 'direct',
        'type': lambda *a: 'in',
        'invoice_state': lambda *a: 'none',
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock_picking', context=c)
    }

    def copy(self, cr, uid, id, default=None, context={}):
        if default is None:
            default = {}
        default = default.copy()
        if not default.get('name',False):
            default['name'] = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking')
        return super(stock_picking, self).copy(cr, uid, id, default, context)

    def onchange_partner_in(self, cr, uid, context, partner_id=None):
        return {}

    def action_explode(self, cr, uid, moves, context={}):
        return moves

    def action_confirm(self, cr, uid, ids, context={}):
        """ Confirms picking.
        @return: True 
        """
        self.write(cr, uid, ids, {'state': 'confirmed'})
        todo = []
        for picking in self.browse(cr, uid, ids, context=context):
            for r in picking.move_lines:
                if r.state == 'draft':
                    todo.append(r.id)
        todo = self.action_explode(cr, uid, todo, context)
        if len(todo):
            self.pool.get('stock.move').action_confirm(cr, uid, todo, context)
        return True

    def test_auto_picking(self, cr, uid, ids):
        # TODO: Check locations to see if in the same location ?
        return True

#    def button_confirm(self, cr, uid, ids, *args):
#        for id in ids:
#            wf_service = netsvc.LocalService("workflow")
#            wf_service.trg_validate(uid, 'stock.picking', id, 'button_confirm', cr)
#        self.force_assign(cr, uid, ids, *args)
#        return True

    def action_assign(self, cr, uid, ids, *args):
        """ Changes state of picking to available if all moves are confirmed.
        @return: True
        """
        for pick in self.browse(cr, uid, ids):
            move_ids = [x.id for x in pick.move_lines if x.state == 'confirmed']
            if not move_ids:
                raise osv.except_osv(_('Warning !'),_('Not Available. Moves are not confirmed.'))
            self.pool.get('stock.move').action_assign(cr, uid, move_ids)
        return True

    def force_assign(self, cr, uid, ids, *args):
        """ Changes state of picking to available if moves are confirmed or waiting.
        @return: True
        """
        wf_service = netsvc.LocalService("workflow")
        for pick in self.browse(cr, uid, ids):
            move_ids = [x.id for x in pick.move_lines if x.state in ['confirmed','waiting']]
#            move_ids = [x.id for x in pick.move_lines]
            self.pool.get('stock.move').force_assign(cr, uid, move_ids)
            wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
        return True

    def draft_force_assign(self, cr, uid, ids, *args):
        """ Confirms picking directly from draft state.
        @return: True
        """
        wf_service = netsvc.LocalService("workflow")
        for pick in self.browse(cr, uid, ids):
            wf_service.trg_validate(uid, 'stock.picking', pick.id,
                'button_confirm', cr)
            #move_ids = [x.id for x in pick.move_lines]
            #self.pool.get('stock.move').force_assign(cr, uid, move_ids)
            #wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
        return True

    def draft_validate(self, cr, uid, ids, *args):
        """ Validates picking directly from draft state.
        @return: True
        """
        wf_service = netsvc.LocalService("workflow")
        self.draft_force_assign(cr, uid, ids)
        for pick in self.browse(cr, uid, ids):
            move_ids = [x.id for x in pick.move_lines]
            self.pool.get('stock.move').force_assign(cr, uid, move_ids)
            wf_service.trg_write(uid, 'stock.picking', pick.id, cr)

            self.action_move(cr, uid, [pick.id])
            wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
        return True

    def cancel_assign(self, cr, uid, ids, *args):
        """ Cancels picking and moves. 
        @return: True
        """
        wf_service = netsvc.LocalService("workflow")
        for pick in self.browse(cr, uid, ids):
            move_ids = [x.id for x in pick.move_lines]
            self.pool.get('stock.move').cancel_assign(cr, uid, move_ids)
            wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
        return True

    def action_assign_wkf(self, cr, uid, ids, context=None):
        """ Changes picking state to assigned.
        @return: True
        """
        for pick in self.browse(cr, uid, ids, context=context):
            type_list = {
                'out':'Packing List',
                'in':'Reception',
                'internal': 'Internal picking',
                'delivery': 'Delivery order'
            }
            message = type_list.get(pick.type, _('Document')) + " '" + pick.name + "' "+ _("is ready to be processed.")
            self.log(cr, uid, id, message)
        self.write(cr, uid, ids, {'state': 'assigned'})
        return True

    def test_finnished(self, cr, uid, ids):
        """ Tests whether the move is in done or cancel state or not.
        @return: True or False
        """
        move_ids = self.pool.get('stock.move').search(cr, uid, [('picking_id', 'in', ids)])
        for move in self.pool.get('stock.move').browse(cr, uid, move_ids):
            if move.state not in ('done', 'cancel'):
                if move.product_qty != 0.0:
                    return False
                else:
                    move.write(cr, uid, [move.id], {'state': 'done'})
        return True

    def test_assigned(self, cr, uid, ids):
        """ Tests whether the move is in assigned state or not.
        @return: True or False
        """
        ok = True
        for pick in self.browse(cr, uid, ids):
            mt = pick.move_type
            for move in pick.move_lines:
                if (move.state in ('confirmed', 'draft')) and (mt == 'one'):
                    return False
                if (mt == 'direct') and (move.state == 'assigned') and (move.product_qty):
                    return True
                ok = ok and (move.state in ('cancel', 'done', 'assigned'))
        return ok

    def action_cancel(self, cr, uid, ids, context={}):
        """ Changes picking state to cancel.
        @return: True
        """
        for pick in self.browse(cr, uid, ids):
            ids2 = [move.id for move in pick.move_lines]
            self.pool.get('stock.move').action_cancel(cr, uid, ids2, context)
        self.write(cr, uid, ids, {'state': 'cancel', 'invoice_state': 'none'})
        return True

    #
    # TODO: change and create a move if not parents
    #
    def action_done(self, cr, uid, ids, context=None):
        """ Changes picking state to done.
        @return: True
        """
        self.write(cr, uid, ids, {'state': 'done', 'date_done': time.strftime('%Y-%m-%d %H:%M:%S')})
        return True

    def action_move(self, cr, uid, ids, context={}):
        """ Changes move state to assigned.
        @return: True
        """
        for pick in self.browse(cr, uid, ids):
            todo = []
            for move in pick.move_lines:
                if move.state == 'assigned':
                    todo.append(move.id)

            if len(todo):
                self.pool.get('stock.move').action_done(cr, uid, todo,
                        context=context)
        return True

    def get_currency_id(self, cr, uid, picking):
        return False

    def _get_payment_term(self, cr, uid, picking):
        """ Gets payment term from partner. 
        @return: Payment term
        """
        partner_obj = self.pool.get('res.partner')
        partner = picking.address_id.partner_id
        return partner.property_payment_term and partner.property_payment_term.id or False

    def _get_address_invoice(self, cr, uid, picking):
        """ Gets invoice address of a partner
        @return {'contact': address, 'invoice': address} for invoice
        """
        partner_obj = self.pool.get('res.partner')
        partner = picking.address_id.partner_id

        return partner_obj.address_get(cr, uid, [partner.id],
                ['contact', 'invoice'])

    def _get_comment_invoice(self, cr, uid, picking):
        """
        @return: comment string for invoice
        """
        return picking.note or ''

    def _get_price_unit_invoice(self, cr, uid, move_line, type, context=None):
        """ Gets price unit for invoice
        @param move_line: Stock move lines
        @param type: Type of invoice
        @return: The price unit for the move line
        """
        if context is None:
            context = {}

        if type in ('in_invoice', 'in_refund'):
            # Take the user company and pricetype
            price_type_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.property_valuation_price_type.id
            pricetype = self.pool.get('product.price.type').browse(cr, uid, price_type_id)
            context['currency_id'] = move_line.company_id.currency_id.id

            amount_unit = move_line.product_id.price_get(pricetype.field, context)[move_line.product_id.id]
            return amount_unit
        else:
            return move_line.product_id.list_price

    def _get_discount_invoice(self, cr, uid, move_line):
        '''Return the discount for the move line'''
        return 0.0

    def _get_taxes_invoice(self, cr, uid, move_line, type):
        """ Gets taxes on invoice
        @param move_line: Stock move lines
        @param type: Type of invoice  
        @return: Taxes Ids for the move line
        """
        if type in ('in_invoice', 'in_refund'):
            taxes = move_line.product_id.supplier_taxes_id
        else:
            taxes = move_line.product_id.taxes_id

        if move_line.picking_id and move_line.picking_id.address_id and move_line.picking_id.address_id.partner_id:
            return self.pool.get('account.fiscal.position').map_tax(
                cr,
                uid,
                move_line.picking_id.address_id.partner_id.property_account_position,
                taxes
            )
        else:
            return map(lambda x: x.id, taxes)

    def _get_account_analytic_invoice(self, cr, uid, picking, move_line):
        return False

    def _invoice_line_hook(self, cr, uid, move_line, invoice_line_id):
        '''Call after the creation of the invoice line'''
        return

    def _invoice_hook(self, cr, uid, picking, invoice_id):
        '''Call after the creation of the invoice'''
        return

    def action_invoice_create(self, cr, uid, ids, journal_id=False,
            group=False, type='out_invoice', context=None):
        """ Creates invoice based on the invoice state selected for picking.
        @param journal_id: Id of journal
        @param group: Whether to create a group invoice or not
        @param type: Type invoice to be created
        @return: Ids of created invoices for the pickings
        """
        if context is None:
            context = {}

        invoice_obj = self.pool.get('account.invoice')
        invoice_line_obj = self.pool.get('account.invoice.line')
        invoices_group = {}
        res = {}

        for picking in self.browse(cr, uid, ids, context=context):
            if picking.invoice_state != '2binvoiced':
                continue
            payment_term_id = False
            partner = picking.address_id and picking.address_id.partner_id
            if not partner:
                raise osv.except_osv(_('Error, no partner !'),
                    _('Please put a partner on the picking list if you want to generate invoice.'))

            if type in ('out_invoice', 'out_refund'):
                account_id = partner.property_account_receivable.id
                payment_term_id = self._get_payment_term(cr, uid, picking)
            else:
                account_id = partner.property_account_payable.id

            address_contact_id, address_invoice_id = \
                    self._get_address_invoice(cr, uid, picking).values()

            comment = self._get_comment_invoice(cr, uid, picking)
            if group and partner.id in invoices_group:
                invoice_id = invoices_group[partner.id]
                invoice = invoice_obj.browse(cr, uid, invoice_id)
                invoice_vals = {
                    'name': (invoice.name or '') + ', ' + (picking.name or ''),
                    'origin': (invoice.origin or '') + ', ' + (picking.name or '') + (picking.origin and (':' + picking.origin) or ''),
                    'comment': (comment and (invoice.comment and invoice.comment+"\n"+comment or comment)) or (invoice.comment and invoice.comment or ''),
                    'date_invoice':context.get('date_inv',False)
                }
                invoice_obj.write(cr, uid, [invoice_id], invoice_vals, context=context)
            else:
                invoice_vals = {
                    'name': picking.name,
                    'origin': (picking.name or '') + (picking.origin and (':' + picking.origin) or ''),
                    'type': type,
                    'account_id': account_id,
                    'partner_id': partner.id,
                    'address_invoice_id': address_invoice_id,
                    'address_contact_id': address_contact_id,
                    'comment': comment,
                    'payment_term': payment_term_id,
                    'fiscal_position': partner.property_account_position.id,
                    'date_invoice': context.get('date_inv',False),
                    'company_id': picking.company_id.id,
                    }
                cur_id = self.get_currency_id(cr, uid, picking)
                if cur_id:
                    invoice_vals['currency_id'] = cur_id
                if journal_id:
                    invoice_vals['journal_id'] = journal_id
                invoice_id = invoice_obj.create(cr, uid, invoice_vals,
                        context=context)
                invoices_group[partner.id] = invoice_id
            res[picking.id] = invoice_id
            for move_line in picking.move_lines:
                origin = move_line.picking_id.name
                if move_line.picking_id.origin:
                    origin += ':' + move_line.picking_id.origin
                if group:
                    name = (picking.name or '') + '-' + move_line.name
                else:
                    name = move_line.name

                if type in ('out_invoice', 'out_refund'):
                    account_id = move_line.product_id.product_tmpl_id.\
                            property_account_income.id
                    if not account_id:
                        account_id = move_line.product_id.categ_id.\
                                property_account_income_categ.id
                else:
                    account_id = move_line.product_id.product_tmpl_id.\
                            property_account_expense.id
                    if not account_id:
                        account_id = move_line.product_id.categ_id.\
                                property_account_expense_categ.id

                price_unit = self._get_price_unit_invoice(cr, uid,
                        move_line, type)
                discount = self._get_discount_invoice(cr, uid, move_line)
                tax_ids = self._get_taxes_invoice(cr, uid, move_line, type)
                account_analytic_id = self._get_account_analytic_invoice(cr, uid, picking, move_line)

                #set UoS if it's a sale and the picking doesn't have one
                uos_id = move_line.product_uos and move_line.product_uos.id or False
                if not uos_id and type in ('out_invoice', 'out_refund'):
                    uos_id = move_line.product_uom.id

                account_id = self.pool.get('account.fiscal.position').map_account(cr, uid, partner.property_account_position, account_id)
                notes = False
                if move_line.sale_line_id:
                    notes = move_line.sale_line_id.notes
                elif move_line.purchase_line_id:
                    notes = move_line.purchase_line_id.notes

                invoice_line_id = invoice_line_obj.create(cr, uid, {
                    'name': name,
                    'origin': origin,
                    'invoice_id': invoice_id,
                    'uos_id': uos_id,
                    'product_id': move_line.product_id.id,
                    'account_id': account_id,
                    'price_unit': price_unit,
                    'discount': discount,
                    'quantity': move_line.product_uos_qty or move_line.product_qty,
                    'invoice_line_tax_id': [(6, 0, tax_ids)],
                    'account_analytic_id': account_analytic_id,
                    'note': notes,
                    }, context=context)
                self._invoice_line_hook(cr, uid, move_line, invoice_line_id)

            invoice_obj.button_compute(cr, uid, [invoice_id], context=context,
                    set_total=(type in ('in_invoice', 'in_refund')))
            self.write(cr, uid, [picking.id], {
                'invoice_state': 'invoiced',
                }, context=context)
            self._invoice_hook(cr, uid, picking, invoice_id)
        self.write(cr, uid, res.keys(), {
            'invoice_state': 'invoiced',
            }, context=context)
        return res

    def test_cancel(self, cr, uid, ids, context={}):
        """ Test whether the move lines are canceled or not.
        @return: True or False
        """
        for pick in self.browse(cr, uid, ids, context=context):
            if not pick.move_lines:
                return False
            for move in pick.move_lines:
                if move.state not in ('cancel',):
                    return False
        return True

    def unlink(self, cr, uid, ids, context=None):
        move_obj = self.pool.get('stock.move')
        if not context:
            context = {}
            
        for pick in self.browse(cr, uid, ids, context=context):
            if pick.state in ['done','cancel']:
                raise osv.except_osv(_('Error'), _('You cannot remove the picking which is in %s state !')%(pick.state,))
            elif pick.state in ['confirmed','assigned', 'draft']:
                ids2 = [move.id for move in pick.move_lines]
                ctx = context.copy()
                ctx.update({'call_unlink':True})
                if pick.state != 'draft':
                    #Cancelling the move in order to affect Virtual stock of product
                    move_obj.action_cancel(cr, uid, ids2, ctx)
                #Removing the move
                move_obj.unlink(cr, uid, ids2, ctx)
                    
        return super(stock_picking, self).unlink(cr, uid, ids, context=context)

    def do_partial(self, cr, uid, ids, partial_datas, context={}):
        """ Makes partial picking and moves done.
        @param partial_datas : Dictionary containing details of partial picking
                          like partner_id, address_id, delivery_date, 
                          delivery moves with product_id, product_qty, uom
        @return: Dictionary of values
        """
        res = {}
        
        move_obj = self.pool.get('stock.move')
        delivery_obj = self.pool.get('stock.delivery')
        product_obj = self.pool.get('product.product')
        currency_obj = self.pool.get('res.currency')
        users_obj = self.pool.get('res.users')
        uom_obj = self.pool.get('product.uom')
        price_type_obj = self.pool.get('product.price.type')
        sequence_obj = self.pool.get('ir.sequence')
        wf_service = netsvc.LocalService("workflow")
        partner_id = partial_datas.get('partner_id', False)
        address_id = partial_datas.get('address_id', False)
        delivery_date = partial_datas.get('delivery_date', False)
        for pick in self.browse(cr, uid, ids, context=context):
            new_picking = None
            new_moves = []

            complete, too_many, too_few = [], [], []
            move_product_qty = {}
            for move in pick.move_lines:
                if move.state in ('done', 'cancel'):
                    continue
                partial_data = partial_datas.get('move%s'%(move.id), False)
                assert partial_data, _('Do not Found Partial data of Stock Move Line :%s' %(move.id))
                product_qty = partial_data.get('product_qty',0.0)
                move_product_qty[move.id] = product_qty
                product_uom = partial_data.get('product_uom',False)
                product_price = partial_data.get('product_price',0.0)
                product_currency = partial_data.get('product_currency',False)
                if move.product_qty == product_qty:
                    complete.append(move)
                elif move.product_qty > product_qty:
                    too_few.append(move)
                else:
                    too_many.append(move)

                # Average price computation
                if (pick.type == 'in') and (move.product_id.cost_method == 'average'):
                    product = product_obj.browse(cr, uid, move.product_id.id)
                    user = users_obj.browse(cr, uid, uid)
                    context['currency_id'] = move.company_id.currency_id.id
                    qty = uom_obj._compute_qty(cr, uid, product_uom, product_qty, product.uom_id.id)
                    pricetype = False
                    if user.company_id.property_valuation_price_type:
                        pricetype = price_type_obj.browse(cr, uid, user.company_id.property_valuation_price_type.id)
                    if pricetype and qty > 0:
                        new_price = currency_obj.compute(cr, uid, product_currency,
                                user.company_id.currency_id.id, product_price)
                        new_price = uom_obj._compute_price(cr, uid, product_uom, new_price,
                                product.uom_id.id)
                        if product.qty_available <= 0:
                            new_std_price = new_price
                        else:
                            # Get the standard price
                            amount_unit = product.price_get(pricetype.field, context)[product.id]
                            new_std_price = ((amount_unit * product.qty_available)\
                                + (new_price * qty))/(product.qty_available + qty)

                        # Write the field according to price type field
                        product_obj.write(cr, uid, [product.id],
                                {pricetype.field: new_std_price})
                        move_obj.write(cr, uid, [move.id], {'price_unit': new_price})


            for move in too_few:
                product_qty = move_product_qty[move.id]
                if not new_picking:

                    new_picking = self.copy(cr, uid, pick.id,
                            {
                                'name': sequence_obj.get(cr, uid, 'stock.picking.%s'%(pick.type)),
                                'move_lines' : [],
                                'state':'draft',
                            })
                if product_qty != 0:

                    new_obj = move_obj.copy(cr, uid, move.id,
                        {
                            'product_qty' : product_qty,
                            'product_uos_qty': product_qty, #TODO: put correct uos_qty
                            'picking_id' : new_picking,
                            'state': 'assigned',
                            'move_dest_id': False,
                            'price_unit': move.price_unit,
                        })

                move_obj.write(cr, uid, [move.id],
                        {
                            'product_qty' : move.product_qty - product_qty,
                            'product_uos_qty':move.product_qty - product_qty, #TODO: put correct uos_qty

                        })

            if new_picking:
                move_obj.write(cr, uid, [c.id for c in complete], {'picking_id': new_picking})
                for move in too_many:
                    product_qty = move_product_qty[move.id]
                    move_obj.write(cr, uid, [move.id],
                            {
                                'product_qty' : product_qty,
                                'product_uos_qty': product_qty, #TODO: put correct uos_qty
                                'picking_id': new_picking,
                            })
            else:
                for move in too_many:
                    product_qty = move_product_qty[move.id]
                    move_obj.write(cr, uid, [move.id],
                            {
                                'product_qty': product_qty,
                                'product_uos_qty': product_qty #TODO: put correct uos_qty
                            })

            # At first we confirm the new picking (if necessary)
            if new_picking:
                wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_confirm', cr)
            # Then we finish the good picking
            if new_picking:
                self.write(cr, uid, [pick.id], {'backorder_id': new_picking})
                self.action_move(cr, uid, [new_picking])
                wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_done', cr)
                wf_service.trg_write(uid, 'stock.picking', pick.id, cr)
                delivered_pack_id = new_picking
            else:
                self.action_move(cr, uid, [pick.id])
                wf_service.trg_validate(uid, 'stock.picking', pick.id, 'button_done', cr)
                delivered_pack_id = pick.id

            delivered_pack = self.browse(cr, uid, delivered_pack_id, context=context)
            delivery_id = delivery_obj.create(cr, uid, {
                'name':  delivered_pack.name or move.name,
                'partner_id': partner_id,
                'address_id': address_id,
                'date': delivery_date,
                'picking_id' :  pick.id,
                'move_delivered' : [(6,0, map(lambda x:x.id, delivered_pack.move_lines))]
            }, context=context)
            res[pick.id] = {'delivered_picking': delivered_pack.id or False}
        return res

stock_picking()


class stock_production_lot(osv.osv):
    def name_get(self, cr, uid, ids, context={}):
        if not ids:
            return []
        reads = self.read(cr, uid, ids, ['name', 'prefix', 'ref'], context)
        res = []
        for record in reads:
            name = record['name']
            prefix = record['prefix']
            if prefix:
                name = prefix + '/' + name
            if record['ref']:
                name = '%s [%s]' % (name, record['ref'])
            res.append((record['id'], name))
        return res

    _name = 'stock.production.lot'
    _description = 'Production lot'

    def _get_stock(self, cr, uid, ids, field_name, arg, context={}):
        """ Gets stock of products for locations
        @return: Dictionary of values
        """
        if 'location_id' not in context:
            locations = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'internal')], context=context)
        else:
            locations = context['location_id'] and [context['location_id']] or []

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}.fromkeys(ids, 0.0)
        if locations:
            cr.execute('''select
                    prodlot_id,
                    sum(name)
                from
                    stock_report_prodlots
                where
                    location_id =ANY(%s) and prodlot_id =ANY(%s) group by prodlot_id''',(locations,ids,))
            res.update(dict(cr.fetchall()))
        return res

    def _stock_search(self, cr, uid, obj, name, args, context):
        """ Searches Ids of products
        @return: Ids of locations
        """
        locations = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'internal')])
        cr.execute('''select
                prodlot_id,
                sum(name)
            from
                stock_report_prodlots
            where
                location_id =ANY(%s) group by prodlot_id
            having  sum(name) '''+ str(args[0][1]) + str(args[0][2]),(locations,))
        res = cr.fetchall()
        ids = [('id', 'in', map(lambda x: x[0], res))]
        return ids

    _columns = {
        'name': fields.char('Serial', size=64, required=True),
        'ref': fields.char('Internal Reference', size=256),
        'prefix': fields.char('Prefix', size=64),
        'product_id': fields.many2one('product.product', 'Product', required=True),
        'date': fields.datetime('Created Date', required=True),
        'stock_available': fields.function(_get_stock, fnct_search=_stock_search, method=True, type="float", string="Available", select="2"),
        'revisions': fields.one2many('stock.production.lot.revision', 'lot_id', 'Revisions'),
        'company_id': fields.many2one('res.company','Company',select=1),
    }
    
    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'name': lambda x, y, z, c: x.pool.get('ir.sequence').get(y, z, 'stock.lot.serial'),
        'product_id': lambda x, y, z, c: c.get('product_id', False),
    }
    _sql_constraints = [
        ('name_ref_uniq', 'unique (name, ref)', 'The serial/ref must be unique !'),
    ]

stock_production_lot()

class stock_production_lot_revision(osv.osv):
    _name = 'stock.production.lot.revision'
    _description = 'Production lot revisions'
    
    _columns = {
        'name': fields.char('Revision Name', size=64, required=True),
        'description': fields.text('Description'),
        'date': fields.date('Revision Date'),
        'indice': fields.char('Revision', size=16),
        'author_id': fields.many2one('res.users', 'Author'),
        'lot_id': fields.many2one('stock.production.lot', 'Production lot', select=True, ondelete='cascade'),
        'company_id': fields.related('lot_id','company_id',type='many2one',relation='res.company',string='Company',store=True),
    }

    _defaults = {
        'author_id': lambda x, y, z, c: z,
        'date': lambda *a: time.strftime('%Y-%m-%d'),
    }

stock_production_lot_revision()

class stock_delivery(osv.osv):

    """ Traceability of partial deliveries """

    _name = "stock.delivery"
    _description = "Delivery"
    
    _columns = {
        'name': fields.char('Name', size=60, required=True),
        'date': fields.datetime('Date', required=True),
        'partner_id': fields.many2one('res.partner', 'Partner', required=True),
        'address_id': fields.many2one('res.partner.address', 'Address', required=True),
        'move_delivered':fields.one2many('stock.move', 'delivered_id', 'Move Delivered'),
        'picking_id': fields.many2one('stock.picking', 'Picking list'),

    }
stock_delivery()
# ----------------------------------------------------
# Move
# ----------------------------------------------------

#
# Fields:
#   location_dest_id is only used for predicting futur stocks
#
class stock_move(osv.osv):
    def _getSSCC(self, cr, uid, context={}):
        cr.execute('select id from stock_tracking where create_uid=%s order by id desc limit 1', (uid,))
        res = cr.fetchone()
        return (res and res[0]) or False
    _name = "stock.move"
    _description = "Stock Move"
    _log_create = False

    def name_get(self, cr, uid, ids, context={}):
        res = []
        for line in self.browse(cr, uid, ids, context):
            res.append((line.id, (line.product_id.code or '/')+': '+line.location_id.name+' > '+line.location_dest_id.name))
        return res

    def _check_tracking(self, cr, uid, ids):
        """ Checks if production lot is assigned to stock move or not.
        @return: True or False
        """
        for move in self.browse(cr, uid, ids):
            if not move.prodlot_id and \
               (move.state == 'done' and \
               ( \
                   (move.product_id.track_production and move.location_id.usage=='production') or \
                   (move.product_id.track_production and move.location_dest_id.usage=='production') or \
                   (move.product_id.track_incoming and move.location_id.usage in ('supplier','internal')) or \
                   (move.product_id.track_outgoing and move.location_dest_id.usage in ('customer','internal')) \
               )):
                return False
        return True

    def _check_product_lot(self, cr, uid, ids):
        """ Checks whether move is done or not and production lot is assigned to that move.
        @return: True or False
        """
        for move in self.browse(cr, uid, ids):
            if move.prodlot_id and move.state == 'done' and (move.prodlot_id.product_id.id != move.product_id.id):
                return False
        return True

    _columns = {
        'name': fields.char('Name', size=64, required=True, select=True),
        'priority': fields.selection([('0', 'Not urgent'), ('1', 'Urgent')], 'Priority'),

        'date': fields.datetime('Created Date'),
        'date_planned': fields.datetime('Date Planned', required=True, help="Scheduled date for the movement of the products or real date if the move is done."),
        'date_expected': fields.datetime('Date Expected', readonly=True,required=True, help="Scheduled date for the movement of the products"),
        'product_id': fields.many2one('product.product', 'Product', required=True, select=True),

        'product_qty': fields.float('Quantity', required=True),
        'product_uom': fields.many2one('product.uom', 'Product UOM', required=True),
        'product_uos_qty': fields.float('Quantity (UOS)'),
        'product_uos': fields.many2one('product.uom', 'Product UOS'),
        'product_packaging': fields.many2one('product.packaging', 'Packaging', help="It specifies attributes of packaging like type, quantity of packaging,etc."),

        'location_id': fields.many2one('stock.location', 'Source Location', required=True, select=True, help="Sets a location if you produce at a fixed location. This can be a partner location if you subcontract the manufacturing operations."),
        'location_dest_id': fields.many2one('stock.location', 'Dest. Location', required=True, select=True, help="Location where the system will stock the finished products."),
        'address_id': fields.many2one('res.partner.address', 'Dest. Address', help="Address where goods are to be delivered"),

        'prodlot_id': fields.many2one('stock.production.lot', 'Production Lot', help="Production lot is used to put a serial number on the production"),
        'tracking_id': fields.many2one('stock.tracking', 'Tracking Lot', select=True, help="Tracking lot is the code that will be put on the logistical unit/pallet"),
#       'lot_id': fields.many2one('stock.lot', 'Consumer lot', select=True, readonly=True),

        'auto_validate': fields.boolean('Auto Validate'),

        'move_dest_id': fields.many2one('stock.move', 'Dest. Move'),
        'move_history_ids': fields.many2many('stock.move', 'stock_move_history_ids', 'parent_id', 'child_id', 'Move History'),
        'move_history_ids2': fields.many2many('stock.move', 'stock_move_history_ids', 'child_id', 'parent_id', 'Move History'),
        'picking_id': fields.many2one('stock.picking', 'Picking List', select=True),

        'note': fields.text('Notes'),

        'state': fields.selection([('draft', 'Draft'), ('waiting', 'Waiting'), ('confirmed', 'Confirmed'), ('assigned', 'Available'), ('done', 'Done'), ('cancel', 'Cancelled')], 'State', readonly=True, select=True,
                                  help='When the stock move is created it is in the \'Draft\' state.\n After that it is set to \'Confirmed\' state.\n If stock is available state is set to \'Avaiable\'.\n When the picking it done the state is \'Done\'.\
                                  \nThe state is \'Waiting\' if the move is waiting for another one.'),
        'price_unit': fields.float('Unit Price',
            digits_compute= dp.get_precision('Account')),
        'company_id': fields.many2one('res.company', 'Company', required=True,select=1),
        'partner_id': fields.related('picking_id','address_id','partner_id',type='many2one', relation="res.partner", string="Partner"),
        'backorder_id': fields.related('picking_id','backorder_id',type='many2one', relation="stock.picking", string="Back Orders"),
        'origin': fields.related('picking_id','origin',type='char', size=64, relation="stock.picking", string="Origin"),
        'move_stock_return_history': fields.many2many('stock.move', 'stock_move_return_history', 'move_id', 'return_move_id', 'Move Return History',readonly=True),
        'delivered_id': fields.many2one('stock.delivery', 'Product delivered'),
        'scraped': fields.related('location_dest_id','scrap_location',type='boolean',relation='stock.location',string='Scraped'),
    }
    _constraints = [
        (_check_tracking,
            'You must assign a production lot for this product',
            ['prodlot_id']),
        (_check_product_lot,
            'You try to assign a lot which is not from the same product',
            ['prodlot_id'])]

    def _default_location_destination(self, cr, uid, context={}):
        """ Gets default address of partner for destination location
        @return: Address id or False
        """
        if context.get('move_line', []):
            if context['move_line'][0]:
                if isinstance(context['move_line'][0], (tuple, list)):
                    return context['move_line'][0][2] and context['move_line'][0][2]['location_dest_id'] or False
                else:
                    move_list = self.pool.get('stock.move').read(cr, uid, context['move_line'][0], ['location_dest_id'])
                    return move_list and move_list['location_dest_id'][0] or False
        if context.get('address_out_id', False):
            return self.pool.get('res.partner.address').browse(cr, uid, context['address_out_id'], context).partner_id.property_stock_customer.id
        return False

    def _default_location_source(self, cr, uid, context={}):
        """ Gets default address of partner for source location
        @return: Address id or False
        """
        if context.get('move_line', []):
            try:
                return context['move_line'][0][2]['location_id']
            except:
                pass
        if context.get('address_in_id', False):
            return self.pool.get('res.partner.address').browse(cr, uid, context['address_in_id'], context).partner_id.property_stock_supplier.id
        return False

    _defaults = {
        'location_id': _default_location_source,
        'location_dest_id': _default_location_destination,
        'state': lambda *a: 'draft',
        'priority': lambda *a: '1',
        'product_qty': lambda *a: 1.0,
        'scraped' : lambda *a: False,
        'date_planned': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.move', context=c),
        'date_expected': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),        
    }

    def copy(self, cr, uid, id, default=None, context={}):
        if default is None:
            default = {}
        default = default.copy()
        default['move_stock_return_history'] = []
        return super(stock_move, self).copy(cr, uid, id, default, context)

    def create(self, cr, user, vals, context=None):
        if vals.get('move_stock_return_history',False):
            vals['move_stock_return_history'] = []
        # Check that the stock.move is in draft state at creation to force
        # passing through button_confirm
        if vals.get('state','draft') not in ('draft','done','waiting'):
            logger = netsvc.Logger()
            logger.notifyChannel("code", netsvc.LOG_WARNING, "All new stock.move must be in state draft at the creation !")
        return super(stock_move, self).create(cr, user, vals, context)

    def _auto_init(self, cursor, context):
        res = super(stock_move, self)._auto_init(cursor, context)
        cursor.execute('SELECT indexname \
                FROM pg_indexes \
                WHERE indexname = \'stock_move_location_id_location_dest_id_product_id_state\'')
        if not cursor.fetchone():
            cursor.execute('CREATE INDEX stock_move_location_id_location_dest_id_product_id_state \
                    ON stock_move (location_id, location_dest_id, product_id, state)')
            cursor.commit()
        return res

    def onchange_lot_id(self, cr, uid, ids, prodlot_id=False, product_qty=False, 
                        loc_id=False, product_id=False, context=None):
        """ On change of production lot gives a warning message.
        @param prodlot_id: Changed production lot id
        @param product_qty: Quantity of product
        @param loc_id: Location id
        @param product_id: Product id
        @return: Warning message
        """
        if not prodlot_id or not loc_id:
            return {}
        ctx = context and context.copy() or {}
        ctx['location_id'] = loc_id
        prodlot = self.pool.get('stock.production.lot').browse(cr, uid, prodlot_id, ctx)
        location = self.pool.get('stock.location').browse(cr, uid, loc_id)
        warning = {}
        if (location.usage == 'internal') and (product_qty > (prodlot.stock_available or 0.0)):
            warning = {
                'title': 'Bad Lot Assignation !',
                'message': 'You are moving %.2f products but only %.2f available in this lot.' % (product_qty, prodlot.stock_available or 0.0)
            }
        return {'warning': warning}

    def onchange_quantity(self, cr, uid, ids, product_id, product_qty, 
                          product_uom, product_uos):
        """ On change of product quantity finds UoM and UoS quantities
        @param product_id: Product id
        @param product_qty: Changed Quantity of product
        @param product_uom: Unit of measure of product
        @param product_uos: Unit of sale of product 
        @return: Dictionary of values
        """
        result = {
                  'product_uos_qty': 0.00
          }

        if (not product_id) or (product_qty <=0.0):
            return {'value': result}

        product_obj = self.pool.get('product.product')
        uos_coeff = product_obj.read(cr, uid, product_id, ['uos_coeff'])

        if product_uos and product_uom and (product_uom != product_uos):
            result['product_uos_qty'] = product_qty * uos_coeff['uos_coeff']
        else:
            result['product_uos_qty'] = product_qty

        return {'value': result}

    def onchange_product_id(self, cr, uid, ids, prod_id=False, loc_id=False, 
                            loc_dest_id=False, address_id=False):
        """ On change of product id, if finds UoM, UoS, quantity and UoS quantity.
        @param prod_id: Changed Product id
        @param loc_id: Source location id
        @param loc_id: Destination location id
        @param address_id: Address id of partner 
        @return: Dictionary of values
        """
        if not prod_id:
            return {}
        lang = False
        if address_id:
            addr_rec = self.pool.get('res.partner.address').browse(cr, uid, address_id)
            if addr_rec:
                lang = addr_rec.partner_id and addr_rec.partner_id.lang or False
        ctx = {'lang': lang}

        product = self.pool.get('product.product').browse(cr, uid, [prod_id], context=ctx)[0]
        uos_id  = product.uos_id and product.uos_id.id or False
        result = {
            'product_uom': product.uom_id.id,
            'product_uos': uos_id,
            'product_qty': 1.00,
            'product_uos_qty' : self.pool.get('stock.move').onchange_quantity(cr, uid, ids, prod_id, 1.00, product.uom_id.id, uos_id)['value']['product_uos_qty']
        }
        if not ids:
            result['name'] = product.partner_ref
        if loc_id:
            result['location_id'] = loc_id
        if loc_dest_id:
            result['location_dest_id'] = loc_dest_id
        return {'value': result}

    def _chain_compute(self, cr, uid, moves, context={}):
        """ Finds whether the location has chained location type or not.
        @param moves: Stock moves
        @return: Dictionary containing destination location with chained location type.
        """
        result = {}
        for m in moves:
            dest = self.pool.get('stock.location').chained_location_get(
                cr,
                uid,
                m.location_dest_id,
                m.picking_id and m.picking_id.address_id and m.picking_id.address_id.partner_id,
                m.product_id,
                context
            )
            if dest:
                if dest[1] == 'transparent':
                    self.write(cr, uid, [m.id], {
                        'date_planned': (datetime.strptime(m.date_planned, '%Y-%m-%d %H:%M:%S') + \
                            relativedelta(days=dest[2] or 0)).strftime('%Y-%m-%d'),
                        'location_dest_id': dest[0].id})
                else:
                    result.setdefault(m.picking_id, [])
                    result[m.picking_id].append( (m, dest) )
        return result

    def action_confirm(self, cr, uid, ids, context={}):
        """ Confirms stock move.
        @return: List of ids.
        """
#        ids = map(lambda m: m.id, moves)
        moves = self.browse(cr, uid, ids)
        self.write(cr, uid, ids, {'state': 'confirmed'})
        i = 0

        def create_chained_picking(self, cr, uid, moves, context):
            new_moves = []
            for picking, todo in self._chain_compute(cr, uid, moves, context).items():
                ptype = self.pool.get('stock.location').picking_type_get(cr, uid, todo[0][0].location_dest_id, todo[0][1][0])
                pick_name = ''
                if ptype == 'delivery':
                    pick_name = self.pool.get('ir.sequence').get(cr, uid, 'stock.picking.delivery')
                pickid = self.pool.get('stock.picking').create(cr, uid, {
                    'name': pick_name or picking.name,
                    'origin': str(picking.origin or ''),
                    'type': ptype,
                    'note': picking.note,
                    'move_type': picking.move_type,
                    'auto_picking': todo[0][1][1] == 'auto',
                    'address_id': picking.address_id.id,
                    'invoice_state': 'none'
                })
                for move, (loc, auto, delay) in todo:
                    # Is it smart to copy ? May be it's better to recreate ?
                    new_id = self.pool.get('stock.move').copy(cr, uid, move.id, {
                        'location_id': move.location_dest_id.id,
                        'location_dest_id': loc.id,
                        'date_moved': time.strftime('%Y-%m-%d'),
                        'picking_id': pickid,
                        'state': 'waiting',
                        'move_history_ids': [],
                        'date_planned': (datetime.strptime(move.date_planned, '%Y-%m-%d %H:%M:%S') + relativedelta(days=delay or 0)).strftime('%Y-%m-%d'),
                        'move_history_ids2': []}
                    )
                    self.pool.get('stock.move').write(cr, uid, [move.id], {
                        'move_dest_id': new_id,
                        'move_history_ids': [(4, new_id)]
                    })
                    new_moves.append(self.browse(cr, uid, [new_id])[0])
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'stock.picking', pickid, 'button_confirm', cr)
            if new_moves:
                create_chained_picking(self, cr, uid, new_moves, context)
        create_chained_picking(self, cr, uid, moves, context)
        return []

    def action_assign(self, cr, uid, ids, *args):
        """ Changes state to confirmed or waiting.
        @return: List of values
        """
        todo = []
        for move in self.browse(cr, uid, ids):
            if move.state in ('confirmed', 'waiting'):
                todo.append(move.id)
        res = self.check_assign(cr, uid, todo)
        return res

    def force_assign(self, cr, uid, ids, context={}):
        """ Changes the state to assigned.
        @return: True
        """
        self.write(cr, uid, ids, {'state': 'assigned'})
        return True

    def cancel_assign(self, cr, uid, ids, context={}):
        """ Changes the state to confirmed.
        @return: True
        """
        self.write(cr, uid, ids, {'state': 'confirmed'})
        return True

    #
    # Duplicate stock.move
    #
    def check_assign(self, cr, uid, ids, context={}):
        """ Checks the product type and accordingly writes the state.
        @return: No. of moves done
        """
        done = []
        count = 0
        pickings = {}
        for move in self.browse(cr, uid, ids):
            if move.product_id.type == 'consu':
                if move.state in ('confirmed', 'waiting'):
                    done.append(move.id)
                pickings[move.picking_id.id] = 1
                continue
            if move.state in ('confirmed', 'waiting'):
                res = self.pool.get('stock.location')._product_reserve(cr, uid, [move.location_id.id], move.product_id.id, move.product_qty, {'uom': move.product_uom.id})
                if res:
                    #_product_available_test depends on the next status for correct functioning
                    #the test does not work correctly if the same product occurs multiple times
                    #in the same order. This is e.g. the case when using the button 'split in two' of
                    #the stock outgoing form
                    self.write(cr, uid, move.id, {'state':'assigned'})
                    done.append(move.id)
                    pickings[move.picking_id.id] = 1
                    r = res.pop(0)
                    cr.execute('update stock_move set location_id=%s, product_qty=%s where id=%s', (r[1], r[0], move.id))

                    while res:
                        r = res.pop(0)
                        move_id = self.copy(cr, uid, move.id, {'product_qty': r[0], 'location_id': r[1]})
                        done.append(move_id)
                        #cr.execute('insert into stock_move_history_ids values (%s,%s)', (move.id,move_id))
        if done:
            count += len(done)
            self.write(cr, uid, done, {'state': 'assigned'})

        if count:
            for pick_id in pickings:
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_write(uid, 'stock.picking', pick_id, cr)
        return count

    #
    # Cancel move => cancel others move and pickings
    #
    def action_cancel(self, cr, uid, ids, context={}):
        """ Cancels the moves and if all moves are cancelled it cancels the picking.
        @return: True
        """
        if not len(ids):
            return True
        pickings = {}
        for move in self.browse(cr, uid, ids):
            if move.state in ('confirmed', 'waiting', 'assigned', 'draft'):
                if move.picking_id:
                    pickings[move.picking_id.id] = True
            if move.move_dest_id and move.move_dest_id.state == 'waiting':
                self.write(cr, uid, [move.move_dest_id.id], {'state': 'assigned'})
                if context.get('call_unlink',False) and move.move_dest_id.picking_id:
                    wf_service = netsvc.LocalService("workflow")
                    wf_service.trg_write(uid, 'stock.picking', move.move_dest_id.picking_id.id, cr)
        self.write(cr, uid, ids, {'state': 'cancel', 'move_dest_id': False})
        if not context.get('call_unlink',False):
            for pick in self.pool.get('stock.picking').browse(cr, uid, pickings.keys()):
                if all(move.state == 'cancel' for move in pick.move_lines):
                    self.pool.get('stock.picking').write(cr, uid, [pick.id], {'state': 'cancel'})

        wf_service = netsvc.LocalService("workflow")
        for id in ids:
            wf_service.trg_trigger(uid, 'stock.move', id, cr)
        #self.action_cancel(cr,uid, ids2, context)
        return True

    def action_done(self, cr, uid, ids, context={}):
        """ Makes the move done and if all moves are done, it will finish the picking.
        @return: 
        """
        track_flag = False
        picking_ids = []
        product_uom_obj = self.pool.get('product.uom')
        price_type_obj = self.pool.get('product.price.type')
        move_obj = self.pool.get('account.move')
        for move in self.browse(cr, uid, ids):
            if move.picking_id: picking_ids.append(move.picking_id.id)
            if move.move_dest_id.id and (move.state != 'done'):
                cr.execute('insert into stock_move_history_ids (parent_id,child_id) values (%s,%s)', (move.id, move.move_dest_id.id))
                if move.move_dest_id.state in ('waiting', 'confirmed'):
                    self.write(cr, uid, [move.move_dest_id.id], {'state': 'assigned'})
                    if move.move_dest_id.picking_id:
                        wf_service = netsvc.LocalService("workflow")
                        wf_service.trg_write(uid, 'stock.picking', move.move_dest_id.picking_id.id, cr)
                    else:
                        pass
                        # self.action_done(cr, uid, [move.move_dest_id.id])
                    if move.move_dest_id.auto_validate:
                        self.action_done(cr, uid, [move.move_dest_id.id], context=context)

            #
            # Accounting Entries
            #
            acc_src = None
            acc_dest = None
            if move.product_id.valuation=='real_time':
                journal_id = move.product_id.categ_id.property_stock_journal and  move.product_id.categ_id.property_stock_journal.id or False                
                if(move.location_id.usage=='internal' and  move.location_dest_id.usage=='internal' and  move.location_id.company_id.id!=move.location_dest_id.company_id.id) or ( move.location_id.usage=='internal' or move.location_dest_id.usage=='internal'):
                    test = [('product.product', move.product_id.id)]
                    if move.product_id.categ_id:
                        test.append( ('product.category', move.product_id.categ_id.id) )
                    if not acc_src:
                        acc_src = move.product_id.product_tmpl_id.\
                                property_stock_account_input.id
                        if not acc_src:
                            acc_src = move.product_id.categ_id.\
                                    property_stock_account_input_categ.id
                        if not acc_src:
                            raise osv.except_osv(_('Error!'),
                                    _('There is no stock input account defined ' \
                                            'for this product: "%s" (id: %d)') % \
                                            (move.product_id.name,
                                                move.product_id.id,))
                    if not acc_dest:
                        acc_dest = move.product_id.product_tmpl_id.\
                                property_stock_account_output.id
                        if not acc_dest:
                            acc_dest = move.product_id.categ_id.\
                                    property_stock_account_output_categ.id
                        if not acc_dest:
                            raise osv.except_osv(_('Error!'),
                                    _('There is no stock output account defined ' \
                                            'for this product: "%s" (id: %d)') % \
                                            (move.product_id.name,
                                                move.product_id.id,))
                    if not move.product_id.categ_id.property_stock_journal.id:
                        raise osv.except_osv(_('Error!'),
                            _('There is no journal defined '\
                                'on the product category: "%s" (id: %d)') % \
                                (move.product_id.categ_id.name,
                                    move.product_id.categ_id.id,))
                    journal_id = move.product_id.categ_id.property_stock_journal.id
                    if acc_src != acc_dest:
                        ref = move.picking_id and move.picking_id.name or False
                        default_uom = move.product_id.uom_id.id
                        date = time.strftime('%Y-%m-%d')
                        q = product_uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, default_uom)
                        if move.product_id.cost_method == 'average' and move.price_unit:
                            amount = q * move.price_unit
                        # Base computation on valuation price type
                        else:
                            company_id = move.company_id.id
                            context['currency_id'] = move.company_id.currency_id.id
                            pricetype = price_type_obj.browse(cr,uid,move.company_id.property_valuation_price_type.id)
                            amount_unit = move.product_id.price_get(pricetype.field, context)[move.product_id.id]
                            amount = amount_unit * q or 1.0
                            # amount = q * move.product_id.standard_price
    
                        partner_id = False
                        if move.picking_id:
                            partner_id = move.picking_id.address_id and (move.picking_id.address_id.partner_id and move.picking_id.address_id.partner_id.id or False) or False
                        lines = [
                                (0, 0, {
                                    'name': move.name,
                                    'quantity': move.product_qty,
                                    'product_id': move.product_id and move.product_id.id or False,
                                    'credit': amount,
                                    'account_id': acc_src,
                                    'ref': ref,
                                    'date': date,
                                    'partner_id': partner_id}),
                                (0, 0, {
                                    'name': move.name,
                                    'product_id': move.product_id and move.product_id.id or False,
                                    'quantity': move.product_qty,
                                    'debit': amount,
                                    'account_id': acc_dest,
                                    'ref': ref,
                                    'date': date,
                                    'partner_id': partner_id})
                        ]
                        move_obj.create(cr, uid, {
                            'name': move.name,
                            'journal_id': journal_id,
                            'line_id': lines,
                            'ref': ref,
                        })
        tracking_lot = False                    
        if context:
            tracking_lot = context.get('tracking_lot', False)
            if tracking_lot:
                rec_id = context and context.get('active_id', False)
                tracking = self.pool.get('stock.tracking')
                tracking_lot = tracking.get_create_tracking_lot(cr, uid,[rec_id], tracking_lot)        
                 
        self.write(cr, uid, ids, {'state': 'done', 'date_planned': time.strftime('%Y-%m-%d %H:%M:%S'), 'tracking_id': tracking_lot or False})
        picking_obj = self.pool.get('stock.picking')
        for pick in picking_obj.browse(cr, uid, picking_ids):
            if all(move.state == 'done' for move in pick.move_lines):
                picking_obj.action_done(cr, uid, [pick.id])

        wf_service = netsvc.LocalService("workflow")
        for id in ids:
            wf_service.trg_trigger(uid, 'stock.move', id, cr)
        return True

    def unlink(self, cr, uid, ids, context=None):
        if context is None:
            context = {}        
        for move in self.browse(cr, uid, ids, context=context):
            if move.state != 'draft':
                raise osv.except_osv(_('UserError'),
                        _('You can only delete draft moves.'))
        return super(stock_move, self).unlink(
            cr, uid, ids, context=context)

    def _create_lot(self, cr, uid, ids, product_id, prefix=False):
        """ Creates production lot
        @return: Production lot id
        """
        prodlot_obj = self.pool.get('stock.production.lot')
        ir_sequence_obj = self.pool.get('ir.sequence')
        sequence = ir_sequence_obj.get(cr, uid, 'stock.lot.serial')
        if not sequence:
            raise osv.except_osv(_('Error!'), _('No production sequence defined'))
        prodlot_id = prodlot_obj.create(cr, uid, {'name': sequence, 'prefix': prefix}, {'product_id': product_id})
        prodlot = prodlot_obj.browse(cr, uid, prodlot_id)
        ref = ','.join(map(lambda x:str(x),ids))
        if prodlot.ref:
            ref = '%s, %s' % (prodlot.ref, ref)
        prodlot_obj.write(cr, uid, [prodlot_id], {'ref': ref})
        return prodlot_id


    def action_scrap(self, cr, uid, ids, quantity, location_id, context=None):
        """ Move the scrap/damaged product into scrap location
        @param cr: the database cursor
        @param uid: the user id
        @param ids: ids of stock move object to be scraped
        @param quantity : specify scrap qty
        @param location_id : specify scrap location
        @param context: context arguments
        @return: Scraped lines
        """
        if quantity <= 0:
            raise osv.except_osv(_('Warning!'), _('Please provide Proper Quantity !'))
        res = []
        for move in self.browse(cr, uid, ids, context=context):
            move_qty = move.product_qty
            uos_qty = quantity / move_qty * move.product_uos_qty
            default_val = {
                    'product_qty': quantity,
                    'product_uos_qty': uos_qty,
                    'state': move.state,
                    'scraped' : True,
                    'location_dest_id': location_id
                }
            new_move = self.copy(cr, uid, move.id, default_val)
            #self.write(cr, uid, [new_move], {'move_history_ids':[(4,move.id)]}) #TODO : to track scrap moves
            res += [new_move]
        self.action_done(cr, uid, res)
        return res

    def action_split(self, cr, uid, ids, quantity, split_by_qty=1, prefix=False, with_lot=True, context=None):
        """ Split Stock Move lines into production lot which specified split by quantity.
        @param cr: the database cursor
        @param uid: the user id
        @param ids: ids of stock move object to be splited
        @param split_by_qty : specify split by qty
        @param prefix : specify prefix of production lot
        @param with_lot : if true, prodcution lot will assign for split line otherwise not.
        @param context: context arguments
        @return: Splited move lines
        """

        if quantity <= 0:
            raise osv.except_osv(_('Warning!'), _('Please provide Proper Quantity !'))

        res = []

        for move in self.browse(cr, uid, ids):
            if split_by_qty <= 0 or quantity == 0:
                return res

            uos_qty = split_by_qty / move.product_qty * move.product_uos_qty

            quantity_rest = quantity % split_by_qty
            uos_qty_rest = split_by_qty / move.product_qty * move.product_uos_qty

            update_val = {
                'product_qty': split_by_qty,
                'product_uos_qty': uos_qty,
            }
            for idx in range(int(quantity//split_by_qty)):
                if not idx and move.product_qty<=quantity:
                    current_move = move.id
                else:
                    current_move = self.copy(cr, uid, move.id, {'state': move.state})
                res.append(current_move)
                if with_lot:
                    update_val['prodlot_id'] = self._create_lot(cr, uid, [current_move], move.product_id.id)

                self.write(cr, uid, [current_move], update_val)


            if quantity_rest > 0:
                idx = int(quantity//split_by_qty)
                update_val['product_qty'] = quantity_rest
                update_val['product_uos_qty'] = uos_qty_rest
                if not idx and move.product_qty<=quantity:
                    current_move = move.id
                else:
                    current_move = self.copy(cr, uid, move.id, {'state': move.state})

                res.append(current_move)


                if with_lot:
                    update_val['prodlot_id'] = self._create_lot(cr, uid, [current_move], move.product_id.id)

                self.write(cr, uid, [current_move], update_val)
        return res

    def action_consume(self, cr, uid, ids, quantity, location_id=False,  context=None):
        """ Consumed product with specific quatity from specific source location
        @param cr: the database cursor
        @param uid: the user id
        @param ids: ids of stock move object to be consumed
        @param quantity : specify consume quantity
        @param location_id : specify source location
        @param context: context arguments
        @return: Consumed lines
        """
        if context is None:
            context = {}

        if quantity <= 0:
            raise osv.except_osv(_('Warning!'), _('Please provide Proper Quantity !'))

        res = []
        for move in self.browse(cr, uid, ids, context=context):
            move_qty = move.product_qty
            quantity_rest = move.product_qty

            quantity_rest -= quantity
            uos_qty_rest = quantity_rest / move_qty * move.product_uos_qty
            if quantity_rest <= 0:
                quantity_rest = 0
                uos_qty_rest = 0
                quantity = move.product_qty

            uos_qty = quantity / move_qty * move.product_uos_qty

            if quantity_rest > 0:
                default_val = {
                    'product_qty': quantity,
                    'product_uos_qty': uos_qty,
                    'state': move.state,
                    'location_id': location_id
                }
                if move.product_id.track_production and location_id:
                    # IF product has checked track for production lot, move lines will be split by 1
                    res += self.action_split(cr, uid, [move.id], quantity, split_by_qty=1, context=context)
                else:
                    current_move = self.copy(cr, uid, move.id, default_val)
                    res += [current_move]

                update_val = {}
                update_val['product_qty'] = quantity_rest
                update_val['product_uos_qty'] = uos_qty_rest
                self.write(cr, uid, [move.id], update_val)

            else:
                quantity_rest = quantity
                uos_qty_rest =  uos_qty

                if move.product_id.track_production and location_id:
                    res += self.split_lines(cr, uid, [move.id], quantity_rest, split_by_qty=1, context=context)
                else:
                    res += [move.id]
                    update_val = {
                        'product_qty' : quantity_rest,
                        'product_uos_qty' : uos_qty_rest,
                        'location_id': location_id
                    }

                    self.write(cr, uid, [move.id], update_val)

        self.action_done(cr, uid, res)
        return res

    def do_partial(self, cr, uid, ids, partial_datas, context={}):
        """ Makes partial pickings and moves done.
        @param partial_datas: Dictionary containing details of partial picking
                          like partner_id, address_id, delivery_date, delivery 
                          moves with product_id, product_qty, uom
        """
        res = {}
        picking_obj = self.pool.get('stock.picking')
        delivery_obj = self.pool.get('stock.delivery')
        product_obj = self.pool.get('product.product')
        currency_obj = self.pool.get('res.currency')
        users_obj = self.pool.get('res.users')
        uom_obj = self.pool.get('product.uom')
        price_type_obj = self.pool.get('product.price.type')
        sequence_obj = self.pool.get('ir.sequence')
        wf_service = netsvc.LocalService("workflow")
        partner_id = partial_datas.get('partner_id', False)
        address_id = partial_datas.get('address_id', False)
        delivery_date = partial_datas.get('delivery_date', False)
        tracking_lot = context.get('tracking_lot', False)
        
        new_moves = []

        complete, too_many, too_few = [], [], []
        move_product_qty = {}
        for move in self.browse(cr, uid, ids, context=context):
            if move.state in ('done', 'cancel'):
                continue
            partial_data = partial_datas.get('move%s'%(move.id), False)
            assert partial_data, _('Do not Found Partial data of Stock Move Line :%s' %(move.id))
            product_qty = partial_data.get('product_qty',0.0)
            move_product_qty[move.id] = product_qty
            product_uom = partial_data.get('product_uom',False)
            product_price = partial_data.get('product_price',0.0)
            product_currency = partial_data.get('product_currency',False)
            if move.product_qty == product_qty:
                self.write(cr, uid, move.id,
                {
                    'tracking_id': tracking_lot
                })
                complete.append(move)
            elif move.product_qty > product_qty:
                too_few.append(move)
            else:
                too_many.append(move)

            # Average price computation
            if (move.picking_id.type == 'in') and (move.product_id.cost_method == 'average'):
                product = product_obj.browse(cr, uid, move.product_id.id)
                user = users_obj.browse(cr, uid, uid)
                context['currency_id'] = move.company_id.currency_id.id
                qty = uom_obj._compute_qty(cr, uid, product_uom, product_qty, product.uom_id.id)
                pricetype = False
                if user.company_id.property_valuation_price_type:
                    pricetype = price_type_obj.browse(cr, uid, user.company_id.property_valuation_price_type.id)
                if pricetype and qty > 0:
                    new_price = currency_obj.compute(cr, uid, product_currency,
                            user.company_id.currency_id.id, product_price)
                    new_price = uom_obj._compute_price(cr, uid, product_uom, new_price,
                            product.uom_id.id)
                    if product.qty_available <= 0:
                        new_std_price = new_price
                    else:
                        # Get the standard price
                        amount_unit = product.price_get(pricetype.field, context)[product.id]
                        new_std_price = ((amount_unit * product.qty_available)\
                            + (new_price * qty))/(product.qty_available + qty)

                    # Write the field according to price type field
                    product_obj.write(cr, uid, [product.id],
                            {pricetype.field: new_std_price})
                    self.write(cr, uid, [move.id], {'price_unit': new_price})

        for move in too_few:
            product_qty = move_product_qty[move.id]
            if product_qty != 0:
                new_move = self.copy(cr, uid, move.id,
                    {
                        'product_qty' : product_qty,
                        'product_uos_qty': product_qty,
                        'picking_id' : move.picking_id.id,
                        'state': 'assigned',
                        'move_dest_id': False,
                        'price_unit': move.price_unit,
                        'tracking_id': tracking_lot,
                    })
                complete.append(self.browse(cr, uid, new_move))
            self.write(cr, uid, move.id,
                    {
                        'product_qty' : move.product_qty - product_qty,
                        'product_uos_qty':move.product_qty - product_qty,
                    })


        for move in too_many:
            self.write(cr, uid, move.id,
                    {
                        'product_qty': move.product_qty,
                        'product_uos_qty': move.product_qty,
                        'tracking_id': tracking_lot
                    })
            complete.append(move)

        for move in complete:
            self.action_done(cr, uid, [move.id], context)

            # TOCHECK : Done picking if all moves are done
            cr.execute("""
                SELECT move.id FROM stock_picking pick
                RIGHT JOIN stock_move move ON move.picking_id = pick.id AND move.state = %s
                WHERE pick.id = %s""",
                        ('done', move.picking_id.id))
            res = cr.fetchall()
            if len(res) == len(move.picking_id.move_lines):
                picking_obj.action_move(cr, uid, [move.picking_id.id])
                wf_service.trg_validate(uid, 'stock.picking', move.picking_id.id, 'button_done', cr)

        ref = {}
        done_move_ids = []
        for move in complete:
            done_move_ids.append(move.id)
            if move.picking_id.id not in ref:
                delivery_id = delivery_obj.create(cr, uid, {
                    'partner_id': partner_id,
                    'address_id': address_id,
                    'date': delivery_date,
                    'name' : move.picking_id.name,
                    'picking_id':  move.picking_id.id
                }, context=context)
                ref[move.picking_id.id] = delivery_id
            delivery_obj.write(cr, uid, ref[move.picking_id.id], {
                'move_delivered' : [(4,move.id)]
            })
        return done_move_ids

stock_move()


class stock_inventory(osv.osv):
    _name = "stock.inventory"
    _description = "Inventory"
    _columns = {
        'name': fields.char('Inventory', size=64, required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date': fields.datetime('Date create', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date_done': fields.datetime('Date done'),
        'inventory_line_id': fields.one2many('stock.inventory.line', 'inventory_id', 'Inventories', states={'done': [('readonly', True)]}),
        'move_ids': fields.many2many('stock.move', 'stock_inventory_move_rel', 'inventory_id', 'move_id', 'Created Moves'),
        'state': fields.selection( (('draft', 'Draft'), ('done', 'Done'), ('cancel','Cancelled')), 'State', readonly=True),
        'company_id': fields.many2one('res.company','Company',required=True,select=1),
    }
    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'state': lambda *a: 'draft',
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.inventory', context=c)
    }


    def _inventory_line_hook(self, cr, uid, inventory_line, move_vals):
        """ Creates a stock move from an inventory line
        @param inventory_line:
        @param move_vals:
        @return: 
        """
        return self.pool.get('stock.move').create(cr, uid, move_vals)

    def action_done(self, cr, uid, ids, context=None):
        """ Finishes the inventory and writes its finished date
        @return: True
        """
        for inv in self.browse(cr, uid, ids):
            move_ids = []
            move_line = []
            for line in inv.inventory_line_id:
                pid = line.product_id.id

                # price = line.product_id.standard_price or 0.0
                amount = self.pool.get('stock.location')._product_get(cr, uid, line.location_id.id, [pid], {'uom': line.product_uom.id})[pid]
                change = line.product_qty - amount
                lot_id = line.prod_lot_id.id
                if change:
                    location_id = line.product_id.product_tmpl_id.property_stock_inventory.id
                    value = {
                        'name': 'INV:' + str(line.inventory_id.id) + ':' + line.inventory_id.name,
                        'product_id': line.product_id.id,
                        'product_uom': line.product_uom.id,
                        'prodlot_id': lot_id,
                        'date': inv.date,
                        'date_planned': inv.date,
                        'state': 'assigned'
                    }
                    if change > 0:
                        value.update( {
                            'product_qty': change,
                            'location_id': location_id,
                            'location_dest_id': line.location_id.id,
                        })
                    else:
                        value.update( {
                            'product_qty': -change,
                            'location_id': line.location_id.id,
                            'location_dest_id': location_id,
                        })
                    if lot_id:
                        value.update({
                            'prodlot_id': lot_id,
                            'product_qty': line.product_qty
                        })
                    move_ids.append(self._inventory_line_hook(cr, uid, line, value))
            if len(move_ids):
                self.pool.get('stock.move').action_done(cr, uid, move_ids,
                        context=context)
            self.write(cr, uid, [inv.id], {'state': 'done', 'date_done': time.strftime('%Y-%m-%d %H:%M:%S'), 'move_ids': [(6, 0, move_ids)]})
        return True

    def action_cancel(self, cr, uid, ids, context={}):
        """ Cancels the stock move and change inventory state to draft.
        @return: True
        """
        for inv in self.browse(cr, uid, ids):
            self.pool.get('stock.move').action_cancel(cr, uid, [x.id for x in inv.move_ids], context)
            self.write(cr, uid, [inv.id], {'state': 'draft'})
        return True

    def action_cancel_inventary(self, cr, uid, ids, context={}):
        """ Cancels both stock move and inventory
        @return: True
        """
        for inv in self.browse(cr,uid,ids):
            self.pool.get('stock.move').action_cancel(cr, uid, [x.id for x in inv.move_ids], context)
            self.write(cr, uid, [inv.id], {'state':'cancel'})
        return True

stock_inventory()


class stock_inventory_line(osv.osv):
    _name = "stock.inventory.line"
    _description = "Inventory Line"
    _columns = {
        'inventory_id': fields.many2one('stock.inventory', 'Inventory', ondelete='cascade', select=True),
        'location_id': fields.many2one('stock.location', 'Location', required=True),
        'product_id': fields.many2one('product.product', 'Product', required=True),
        'product_uom': fields.many2one('product.uom', 'Product UOM', required=True),
        'product_qty': fields.float('Quantity'),
        'company_id': fields.related('inventory_id','company_id',type='many2one',relation='res.company',string='Company',store=True),
        'prod_lot_id': fields.many2one('stock.production.lot', 'Production Lot', domain="[('product_id','=',product_id)]"),
        'state': fields.related('inventory_id','state',type='char',string='State',readonly=True),
    }

    def on_change_product_id(self, cr, uid, ids, location_id, product, uom=False):
        """ Changes UoM and name if product_id changes.
        @param location_id: Location id
        @param product: Changed product_id
        @param uom: UoM product 
        @return:  Dictionary of changed values
        """
        if not product:
            return {}
        if not uom:
            prod = self.pool.get('product.product').browse(cr, uid, [product], {'uom': uom})[0]
            uom = prod.uom_id.id
        amount = self.pool.get('stock.location')._product_get(cr, uid, location_id, [product], {'uom': uom})[product]
        result = {'product_qty': amount, 'product_uom': uom}
        return {'value': result}

stock_inventory_line()


#----------------------------------------------------------
# Stock Warehouse
#----------------------------------------------------------
class stock_warehouse(osv.osv):
    _name = "stock.warehouse"
    _description = "Warehouse"
    _columns = {
        'name': fields.char('Name', size=60, required=True),
#       'partner_id': fields.many2one('res.partner', 'Owner'),
        'company_id': fields.many2one('res.company','Company',required=True,select=1),
        'partner_address_id': fields.many2one('res.partner.address', 'Owner Address'),
        'lot_input_id': fields.many2one('stock.location', 'Location Input', required=True, domain=[('usage','<>','view')]),
        'lot_stock_id': fields.many2one('stock.location', 'Location Stock', required=True, domain=[('usage','<>','view')]),
        'lot_output_id': fields.many2one('stock.location', 'Location Output', required=True, domain=[('usage','<>','view')]),
    }
    _defaults = {
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.inventory', context=c),
    }
stock_warehouse()


# Move wizard :
#    get confirm or assign stock move lines of partner and put in current picking.
class stock_picking_move_wizard(osv.osv_memory):
    _name = 'stock.picking.move.wizard'

    def _get_picking(self, cr, uid, ctx):
        if ctx.get('action_id', False):
            return ctx['action_id']
        return False

    def _get_picking_address(self, cr, uid, ctx):
        picking_obj = self.pool.get('stock.picking')
        if ctx.get('action_id', False):
            picking = picking_obj.browse(cr, uid, [ctx['action_id']])[0]
            return picking.address_id and picking.address_id.id or False
        return False

    _columns = {
        'name': fields.char('Name', size=64, invisible=True),
        #'move_lines': fields.one2many('stock.move', 'picking_id', 'Move lines',readonly=True),
        'move_ids': fields.many2many('stock.move', 'picking_move_wizard_rel', 'picking_move_wizard_id', 'move_id', 'Entry lines', required=True),
        'address_id': fields.many2one('res.partner.address', 'Dest. Address', invisible=True),
        'picking_id': fields.many2one('stock.picking', 'Picking list', select=True, invisible=True),
    }
    _defaults = {
        'picking_id': _get_picking,
        'address_id': _get_picking_address,
    }

    def action_move(self, cr, uid, ids, context=None):
        move_obj = self.pool.get('stock.move')
        picking_obj = self.pool.get('stock.picking')
        account_move_obj = self.pool.get('account.move')
        for act in self.read(cr, uid, ids):
            move_lines = move_obj.browse(cr, uid, act['move_ids'])
            for line in move_lines:
                if line.picking_id:
                    picking_obj.write(cr, uid, [line.picking_id.id], {'move_lines': [(1, line.id, {'picking_id': act['picking_id']})]})
                    picking_obj.write(cr, uid, [act['picking_id']], {'move_lines': [(1, line.id, {'picking_id': act['picking_id']})]})
                    old_picking = picking_obj.read(cr, uid, [line.picking_id.id])[0]
                    if not len(old_picking['move_lines']):
                        picking_obj.write(cr, uid, [old_picking['id']], {'state': 'done'})
                else:
                    raise osv.except_osv(_('UserError'),
                        _('You can not create new moves.'))
        return {'type': 'ir.actions.act_window_close'}

stock_picking_move_wizard()

class report_products_to_received_planned(osv.osv):
    _name = "report.products.to.received.planned"
    _description = "Product to Received Vs Planned"
    _auto = False
    _columns = {
        'date':fields.date('Date'),
        'qty': fields.integer('Actual Qty'),
        'planned_qty': fields.integer('Planned Qty'),

    }

    def init(self, cr):
        tools.drop_view_if_exists(cr, 'report_products_to_received_planned')
        cr.execute("""
            create or replace view report_products_to_received_planned as (
               select stock.date, min(stock.id) as id, sum(stock.product_qty) as qty, 0 as planned_qty
                   from stock_picking picking
                    inner join stock_move stock
                    on picking.id = stock.picking_id and picking.type = 'in'
                    where stock.date between (select cast(date_trunc('week', current_date) as date)) and (select cast(date_trunc('week', current_date) as date) + 7)
                    group by stock.date

                    union

               select stock.date_planned, min(stock.id) as id, 0 as actual_qty, sum(stock.product_qty) as planned_qty
                    from stock_picking picking
                    inner join stock_move stock
                    on picking.id = stock.picking_id and picking.type = 'in'
                    where stock.date_planned between (select cast(date_trunc('week', current_date) as date)) and (select cast(date_trunc('week', current_date) as date) + 7)
        group by stock.date_planned
                )
        """)
report_products_to_received_planned()

class report_delivery_products_planned(osv.osv):
    _name = "report.delivery.products.planned"
    _description = "Number of Delivery products vs planned"
    _auto = False
    _columns = {
        'date':fields.date('Date'),
        'qty': fields.integer('Actual Qty'),
        'planned_qty': fields.integer('Planned Qty'),

    }

    def init(self, cr):
        tools.drop_view_if_exists(cr, 'report_delivery_products_planned')
        cr.execute("""
            create or replace view report_delivery_products_planned as (
                select stock.date, min(stock.id) as id, sum(stock.product_qty) as qty, 0 as planned_qty
                   from stock_picking picking
                    inner join stock_move stock
                    on picking.id = stock.picking_id and picking.type = 'out'
                    where stock.date between (select cast(date_trunc('week', current_date) as date)) and (select cast(date_trunc('week', current_date) as date) + 7)
                    group by stock.date

                    union

               select stock.date_planned, min(stock.id), 0 as actual_qty, sum(stock.product_qty) as planned_qty
                    from stock_picking picking
                    inner join stock_move stock
                    on picking.id = stock.picking_id and picking.type = 'out'
                    where stock.date_planned between (select cast(date_trunc('week', current_date) as date)) and (select cast(date_trunc('week', current_date) as date) + 7)
        group by stock.date_planned


                )
        """)
report_delivery_products_planned()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
