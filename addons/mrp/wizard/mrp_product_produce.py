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
from tools.translate import _
import netsvc

class mrp_product_produce(osv.osv_memory):
    _name = "mrp.product.produce"
    _description = "Product Produce"
    
    _columns = {
        'product_qty': fields.float('Quantity', required=True), 
        'mode': fields.selection([('consume_produce', 'Consume & Produce'), 
                                  ('consume', 'Consume Only')], 'Mode', required=True)
    }

    def _get_product_qty(self, cr, uid, context):
        prod = self.pool.get('mrp.production').browse(cr, uid, 
                                context['active_id'], context=context)
        done = 0.0
        for move in prod.move_created_ids2:
                done += move.product_qty
        return (prod.product_qty - done) or prod.product_qty
    
    _defaults = {
                 'product_qty': _get_product_qty, 
                 'mode': lambda *x: 'consume_produce'
                 }

    def do_produce(self, cr, uid, ids, context={}):
        prod_obj = self.pool.get('mrp.production')
        move_ids = context['active_ids']
        for data in self.read(cr, uid, ids):
            for move_id in move_ids:
                prod_obj.do_produce(cr, uid, move_id, 
                                    data['product_qty'], data['mode'], context=context)
        return {}

mrp_product_produce()

