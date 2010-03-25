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

class change_standard_price(osv.osv_memory):
    _name = "stock.change.standard.price"
    _description = "Change Standard Price"
    _columns = {
            'new_price': fields.float('Price', required=True),
            'stock_account_input':fields.many2one('account.account', 'Stock Input Account'),
            'stock_account_output':fields.many2one('account.account', 'Stock Output Account'),
            'stock_journal':fields.many2one('account.journal', 'Stock journal', required=True),            
            'enable_stock_in_out_acc':fields.boolean('Enable Related Account',),
    }
    
    def default_get(self, cr, uid, fields, context):
        """ 
         To get default values for the object.
        
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param fields: List of fields for which we want default values 
         @param context: A standard dictionary 
         
         @return: A dictionary which of fields with values. 
        
        """ 
        product_obj = self.pool.get('product.product').browse(cr, uid, context.get('active_id', False))
        res = super(change_standard_price, self).default_get(cr, uid, fields, context=context)   
        
        stock_input_acc = product_obj.property_stock_account_input and product_obj.property_stock_account_input.id or False 
        if not stock_input_acc:
            stock_input_acc = product_obj.categ_id.property_stock_account_input_categ and product_obj.categ_id.property_stock_account_input_categ.id or False
        
        stock_output_acc = product_obj.property_stock_account_output and product_obj.property_stock_account_output.id or False
        if not stock_output_acc:
            stock_output_acc = product_obj.categ_id.property_stock_account_output_categ and product_obj.categ_id.property_stock_account_output_categ.id or False

        price = product_obj.standard_price
        journal_id = product_obj.categ_id.property_stock_journal and product_obj.categ_id.property_stock_journal.id or False
        
        if 'new_price' in fields:
            res.update({'new_price': price})
        if 'stock_account_input' in fields:
            res.update({'stock_account_input': stock_input_acc})         
        if 'stock_account_output' in fields:
            res.update({'stock_account_output': stock_output_acc})         
        if 'stock_journal' in fields:
            res.update({'stock_journal': journal_id})  
        if 'enable_stock_in_out_acc' in fields:
            res.update({'enable_stock_in_out_acc': True})              
                 
                     
        return res
    
    def onchange_price(self, cr, uid, ids, new_price, context = {}):
        product_obj = self.pool.get('product.product').browse(cr, uid, context.get('active_id', False))
        price = product_obj.standard_price
        diff = price - new_price
        if diff > 0 : 
            return {'value' : {'enable_stock_in_out_acc':False}}
        else :
            return {'value' : {'enable_stock_in_out_acc':True}}
        
    def change_price(self, cr, uid, ids, context):
        """ 
             Changes the Standard Price of Product. 
             And creates an account move accordingly.
            
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param ids: List of IDs selected 
             @param context: A standard dictionary 
             
             @return:  
        
        """
        rec_id = context and context.get('active_id', False)
        assert rec_id, _('Active ID is not set in Context')
        prod_obj = self.pool.get('product.product')
        res = self.browse(cr, uid, ids)        
        datas = {
            'new_price' : res[0].new_price,
            'stock_output_account' : res[0].stock_account_output.id,
            'stock_input_account' : res[0].stock_account_input.id,
            'stock_journal' : res[0].stock_journal.id
        }
        prod_obj.do_change_standard_price(cr, uid, [rec_id], datas, context)
        return {}        

change_standard_price()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
