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

import pooler
import netsvc
from osv import fields, osv

import time

class make_procurement(osv.osv_memory):
    '''Wizard that create a procurement from a product form'''
    
    _name = 'make.procurement'
    _description = 'Make Procurements'
    
    def onchange_product_id(self, cr, uid, ids, prod_id):
        product = self.pool.get('product.product').browse(cr, uid, prod_id)
        return {'value': {'uom_id': product.uom_id.id}}
    
    _columns = {
        'qty': fields.float('Quantity', digits=(16,2), required=True),
        'product_id': fields.many2one('product.product', 'Product', required=True, readonly=1),
        'uom_id': fields.many2one('product.uom', 'Unit of Measure', required=True),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse', required=True),
        'date_planned': fields.date('Planned Date', required=True),
    }
    
    _defaults = {
            'date_planned': lambda *args: time.strftime('%Y-%m-%d'),
            'qty': lambda *args: 1.0,
    }
    
    def make_procurement(self, cr, uid, ids, context=None):
        '''Create procurement'''
        for proc in self.browse(cr, uid, ids):
            wh = self.pool.get('stock.warehouse').browse(cr, uid, proc.id, context)
            user = self.pool.get('res.users').browse(cr, uid, uid, context)
            procure_id = self.pool.get('mrp.procurement').create(cr, uid, {
                'name':'INT:'+str(user.login),
                'date_planned': proc.date_planned,
                'product_id': proc.product_id.id,
                'product_qty': proc.qty,
                'product_uom': proc.uom_id.id,
                'location_id': wh.lot_stock_id.id,
                'procure_method':'make_to_order',
            })
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'mrp.procurement', procure_id, 'button_confirm', cr)
        
        data_obj = self.pool.get('ir.model.data')
        id2 = data_obj._get_id(cr, uid, 'mrp', 'mrp_procurement_tree_view')
        id3 = data_obj._get_id(cr, uid, 'mrp', 'mrp_procurement_form_view')
        if id2:
            id2 = data_obj.browse(cr, uid, id2, context=context).res_id
        if id3:
            id3 = data_obj.browse(cr, uid, id3, context=context).res_id
        
        return {
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_model': 'mrp.procurement',
                'res_id' : procure_id,
                'views': [(id3,'form'),(id2,'tree')],
                'type': 'ir.actions.act_window',
        }
    
    def default_get(self, cr, uid, fields, context=None):
        record_id = context and context.get('record_id', False) or False

        res = super(make_procurement, self).default_get(cr, uid, fields, context=context)

        if record_id:
            product_id = self.pool.get('product.product').browse(cr, uid, record_id, context=context).id
            res['product_id'] = product_id

        return res

make_procurement()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

