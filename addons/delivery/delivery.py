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

import time
from osv import fields,osv
from tools.translate import _

class delivery_carrier(osv.osv):
    _name = "delivery.carrier"
    _description = "Carrier"

    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        if context is None:
            context = {}
        order_id = context.get('order_id',False)
        if not order_id:
            res = super(delivery_carrier, self).name_get(cr, uid, ids, context=context)
        else:
            order = self.pool.get('sale.order').browse(cr, uid, order_id, context=context)
            currency = order.pricelist_id.currency_id.name or ''
            res = [(r['id'], r['name']+' ('+(str(r['price']))+' '+currency+')') for r in self.read(cr, uid, ids, ['name', 'price'], context)]
        return res
    def get_price(self, cr, uid, ids, field_name, arg=None, context=None):
        res={}
        if context is None:
            context = {}
        sale_obj=self.pool.get('sale.order')
        grid_obj=self.pool.get('delivery.grid')
        for carrier in self.browse(cr, uid, ids, context=context):
            order_id=context.get('order_id',False)
            price=False
            if order_id:
              order = sale_obj.browse(cr, uid, order_id, context=context)
              carrier_grid=self.grid_get(cr,uid,[carrier.id],order.partner_shipping_id.id,context)
              if carrier_grid:
                  price=grid_obj.get_price(cr, uid, carrier_grid, order, time.strftime('%Y-%m-%d'), context)
              else:
                  price = 0.0
            res[carrier.id]=price
        return res
    _columns = {
        'name': fields.char('Carrier', size=64, required=True),
        'partner_id': fields.many2one('res.partner', 'Carrier Partner', required=True),
        'product_id': fields.many2one('product.product', 'Delivery Product', required=True),
        'grids_id': fields.one2many('delivery.grid', 'carrier_id', 'Delivery Grids'),
        'price' : fields.function(get_price, method=True,string='Price'),
        'active': fields.boolean('Active', help="If the active field is set to False, it will allow you to hide the delivery carrier without removing it."),
        'normal_price': fields.float('Normal Price'),
        'international_price': fields.boolean('International Price'),
        'free_if_more_than': fields.boolean('Free If More Than'),
        'delivery_country_ids': fields.one2many('delivery.carrier.country',\
                            'delivery_carrier_id', 'Delivery Country'),
        'amount': fields.float('Amount'),

    }

    _defaults = {
        'active': lambda *args:1,
        'international_price': lambda *args: False,
        'free_if_more_than': lambda *args: False
    }

    def grid_get(self, cr, uid, ids, contact_id, context=None):
        contact = self.pool.get('res.partner.address').browse(cr, uid, contact_id, context=context)
        for carrier in self.browse(cr, uid, ids, context=context):
            for grid in carrier.grids_id:
                get_id = lambda x: x.id
                country_ids = map(get_id, grid.country_ids)
                state_ids = map(get_id, grid.state_ids)
                if country_ids and not contact.country_id.id in country_ids:
                    continue
                if state_ids and not contact.state_id.id in state_ids:
                    continue
                if grid.zip_from and (contact.zip or '')< grid.zip_from:
                    continue
                if grid.zip_to and (contact.zip or '')> grid.zip_to:
                    continue
                return grid.id
        return False

    def create_grid_lines(self, cr, uid, ids, vals, context=None):
        if context == None:
            context = {}
        grid_line_pool = self.pool.get('delivery.grid.line')
        grid_pool = self.pool.get('delivery.grid')
        for record in self.browse(cr, uid, ids, context=context):
            grid_id = grid_pool.search(cr, uid, [('carrier_id', '=', record.id)], context=context)
            if not grid_id:
                record_data = {
                    'name': vals.get('name', False),
                    'carrier_id': record.id,
                    'seqeunce': 10,
                }
                new_grid_id = grid_pool.create(cr, uid, record_data, context=context)
                grid_id = [new_grid_id]

            if record.free_if_more_than:
                grid_lines = []
                for line in grid_pool.browse(cr, uid, grid_id[0]).line_ids:
                    if line.type == 'price':
                        grid_lines.append(line.id)
                grid_line_pool.unlink(cr, uid, grid_lines, context=context)
                data = {
                    'grid_id': grid_id and grid_id[0],
                    'name': _('Free if more than %d') % record.amount,
                    'type': 'price',
                    'operator': '>=',
                    'max_value': record.amount,
                    'standard_price': 0.0,
                    'list_price': 0.0,
                }
                grid_line_pool.create(cr, uid, data, context=context)
            else:
                _lines = []
                for line in grid_pool.browse(cr, uid, grid_id[0], context=context).line_ids:
                    if line.type == 'price':
                        _lines.append(line.id)
                grid_line_pool.unlink(cr, uid, _lines, context=context)

            if record.international_price:
                lines = []
                for line in grid_pool.browse(cr, uid, grid_id[0], context=context).line_ids:
                    if line.type == 'country':
                        lines.append(line.id)
                grid_line_pool.unlink(cr, uid, lines, context=context)
                for country_rec in record.delivery_country_ids:
                    for country in country_rec.country:
                        values = {
                            'grid_id': grid_id[0],
                            'name': _('Country is %s') %country.name,
                            'country_id': country.id,
                            'type': 'country',
                            'standard_price': country_rec.price,
                            'list_price': 0.0,
                            'operator': '==',
                            'max_value': 0.0
                        }
                        grid_line_pool.create(cr, uid, values, context=context)
            else:
                l = []
                for line in grid_pool.browse(cr, uid, grid_id[0]).line_ids:
                    if line.type == 'country':
                        l.append(line.id)
                grid_line_pool.unlink(cr, uid, l, context=context)

            if record.normal_price:
                default_data = {
                    'grid_id': grid_id and grid_id[0],
                    'name': _('Default price'),
                    'type': 'price',
                    'operator': '>=',
                    'max_value': 0.0,
                    'standard_price': record.normal_price,
                    'list_price': record.normal_price,
                }
                grid_line_pool.create(cr, uid, default_data, context=context)

        return True

    def write(self, cr, uid, ids, vals, context=None):
        if context == None:
            context = {}
        res_id = super(delivery_carrier, self).write(cr, uid, ids, vals, context=context)
        self.create_grid_lines(cr, uid, ids, vals, context=context)
        return res_id

    def create(self, cr, uid, vals, context=None):
        if context == None:
            context = {}
        res_id = super(delivery_carrier, self).create(cr, uid, vals, context=context)
        self.create_grid_lines(cr, uid, [res_id], vals, context=context)
        return res_id

delivery_carrier()


class delivery_carrier_country(osv.osv):
    _name = "delivery.carrier.country"
    _description = "Delivery Carrier Country"

    _columns = {
        'country' : fields.many2many('res.country', 'delivery_country_rel',\
                        'delivery_id', 'country_id', 'Country'),
        'price': fields.float('Price'),
        'delivery_carrier_id': fields.many2one('delivery.carrier', 'Carrier'),
    }

delivery_carrier_country()

class delivery_grid(osv.osv):
    _name = "delivery.grid"
    _description = "Delivery Grid"
    _columns = {
        'name': fields.char('Grid Name', size=64, required=True),
        'sequence': fields.integer('Sequence', size=64, required=True, help="Gives the sequence order when displaying a list of delivery grid."),
        'carrier_id': fields.many2one('delivery.carrier', 'Carrier', required=True, ondelete='cascade'),
        'country_ids': fields.many2many('res.country', 'delivery_grid_country_rel', 'grid_id', 'country_id', 'Countries'),
        'state_ids': fields.many2many('res.country.state', 'delivery_grid_state_rel', 'grid_id', 'state_id', 'States'),
        'zip_from': fields.char('Start Zip', size=12),
        'zip_to': fields.char('To Zip', size=12),
        'line_ids': fields.one2many('delivery.grid.line', 'grid_id', 'Grid Line'),
        'active': fields.boolean('Active', help="If the active field is set to False, it will allow you to hide the delivery grid without removing it."),
    }
    _defaults = {
        'active': lambda *a: 1,
        'sequence': lambda *a: 1,
    }
    _order = 'sequence'

    def get_price(self, cr, uid, id, order, dt, context=None):
        total = 0
        weight = 0
        volume = 0
        for line in order.order_line:
            if not line.product_id:
                continue
            total += line.price_subtotal or 0.0
            weight += (line.product_id.weight or 0.0) * line.product_uom_qty
            volume += (line.product_id.volume or 0.0) * line.product_uom_qty


        return self.get_price_from_picking(cr, uid, id, total,weight, volume, context=context)

    def get_price_from_picking(self, cr, uid, id, total, weight, volume, context=None):
        grid = self.browse(cr, uid, id, context=context)
        price = 0.0
        ok = False

        for line in grid.line_ids:
            price_dict = {'price': total, 'volume':volume, 'weight': weight, 'wv':volume*weight}
            test = eval(line.type+line.operator+str(line.max_value), price_dict)
            if test:
                if line.price_type=='variable':
                    price = line.list_price * price_dict[line.variable_factor]
                else:
                    price = line.list_price
                ok = True
                break
        if not ok:
            raise osv.except_osv(_('No price available !'), _('No line matched this order in the choosed delivery grids !'))

        return price


delivery_grid()

class delivery_grid_line(osv.osv):
    _name = "delivery.grid.line"
    _description = "Delivery Grid Line"
    _columns = {
        'name': fields.char('Name', size=32, required=True),
        'grid_id': fields.many2one('delivery.grid', 'Grid',required=True),
        'type': fields.selection([('weight','Weight'),('volume','Volume'),\
                                  ('wv','Weight * Volume'), ('price','Price'),\
                                  ('country', 'Country')],\
                                  'Variable', required=True),
        'operator': fields.selection([('==','='),('<=','<='),('>=','>=')], 'Operator', required=True),
        'max_value': fields.float('Maximum Value', required=True),
        'price_type': fields.selection([('fixed','Fixed'),('variable','Variable')], 'Price Type', required=True),
        'variable_factor': fields.selection([('weight','Weight'),('volume','Volume'),('wv','Weight * Volume'), ('price','Price')], 'Variable Factor', required=True),
        'list_price': fields.float('Sale Price', required=True),
        'standard_price': fields.float('Cost Price', required=True),
        'country_id': fields.many2one('res.country', 'Country'),
    }
    _defaults = {
        'type': lambda *args: 'weight',
        'operator': lambda *args: '<=',
        'price_type': lambda *args: 'fixed',
        'variable_factor': lambda *args: 'weight',
    }
    _order = 'list_price'

    def on_change_type(self, cr, uid, ids, type):
        if type == 'country':
            return {'value': {'operator': '=='}}
        return {}


delivery_grid_line()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

