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

import netsvc
from osv import osv,fields
from tools.translate import _

class add_product(osv.osv_memory):
    _name = 'pos.add.product'
    _description = 'Add Product'

    _columns = {
                'product_id': fields.many2one('product.product', 'Product',required=True),
                'quantity': fields.float('Quantity ', required=True),
    }
    _defaults = {
                    'quantity': lambda *a: 1,
                }
    
    def select_product(self, cr, uid, ids, context):
        """ 
             @summary: To get the product and quantity and add in order .            
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param context: A standard dictionary 
             @return : Retrun the add product form again for addin more product
        """        
        this = self.browse(cr, uid, ids[0], context=context)
        record_id = context and context.get('record_id',False)
        if record_id:
             order_obj = self.pool.get('pos.order')
             order_obj.add_product(cr, uid, record_id, this.product_id.id,this.quantity,context=context)
        
        return {            
                'name': _('Add Product'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'pos.add.product',
                'view_id': False,
                'target':'new',
                'views': False,
                'type': 'ir.actions.act_window',
                }
add_product()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

