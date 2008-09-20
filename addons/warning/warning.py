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

import time
from osv import fields,osv

class res_partner(osv.osv):
    _inherit = 'res.partner'
    _columns = {
                 'sale_warn' : fields.boolean('Sale Order'),
                 'sale_warn_msg' : fields.char('Message for Sale Order', size=64),
                 'purchase_warn' : fields.boolean('Purchase Order'),
                 'purchase_warn_msg' : fields.char('Message for Purchase Order', size=64),
                 'picking_warn' : fields.boolean('Stock Picking'),
                 'picking_warn_msg' : fields.char('Message for Stock Picking', size=64),
                 'invoice_warn' : fields.boolean('Invoice'),
                 'invoice_warn_msg' : fields.char('Message for Invoice', size=64),
                 }
res_partner()


class sale_order(osv.osv):
    _inherit = 'sale.order'
    def onchange_partner_id(self, cr, uid, ids, part):
        if not part:
            return {'value':{'partner_invoice_id': False, 'partner_shipping_id':False, 'partner_order_id':False, 'payment_term' : False}}
        warning = {}
        title=False
        message=False
        partner = self.pool.get('res.partner').browse(cr, uid, part)
        if partner.sale_warn:
            title= "Message",
            message=partner.sale_warn_msg
             
        result =  super(sale_order, self).onchange_partner_id(cr, uid, ids, part)['value']
        if result.get('warning',False):
            warning['title']=title and title+' & '+result['warning']['title'] or result['warning']['title']
            warning['message']=message and message +' '+result['warning']['message'] or result['warning']['message']
        return {'value': result, 'warning':warning}
sale_order()


class purchase_order(osv.osv):
    _inherit = 'purchase.order'
    def onchange_partner_id(self, cr, uid, ids, part):
        if not part:
            return {'value':{'partner_address_id': False}}
        warning = {}
        partner = self.pool.get('res.partner').browse(cr, uid, part)
        if partner.purchase_warn:
                warning={
                    'title': "Message",
                    'message': partner.purchase_warn_msg
                    }
        result =  super(purchase_order, self).onchange_partner_id(cr, uid, ids, part)['value']
        return {'value': result, 'warning':warning}
    
purchase_order()


class account_invoice(osv.osv):
    _inherit = 'account.invoice'
    def onchange_partner_id(self, cr, uid, ids, type, partner_id,
            date_invoice=False, payment_term=False, partner_bank_id=False):
        if not partner_id:
            return {'value': {
            'address_contact_id': False ,
            'address_invoice_id': False,
            'account_id': False,
            'payment_term': False,
            }
        }
        warning = {}
        partner = self.pool.get('res.partner').browse(cr, uid, partner_id)
        if partner.invoice_warn:
                warning={
                    'title': "Message",
                    'message': partner.invoice_warn_msg
                    }
        result =  super(account_invoice, self).onchange_partner_id(cr, uid, ids, type, partner_id,
            date_invoice=False, payment_term=False, partner_bank_id=False)['value']
        return {'value': result, 'warning':warning}
    
account_invoice()

class stock_picking(osv.osv):
    _inherit = 'stock.picking'
    
    def onchange_partner_in(self, cr, uid, context, partner_id=None):
        if not partner_id:
            return {}
        partner = self.pool.get('res.partner.address').browse(cr, uid, [partner_id])[0].partner_id
        warning = {}
        if partner.picking_warn:
            warning={
                'title': "Message",
                'message': partner.picking_warn_msg
            }
        result =  super(stock_picking, self).onchange_partner_in(cr, uid, context, partner_id)
        return {'value': result, 'warning':warning}
    
stock_picking()

class product_product(osv.osv):
    _inherit = 'product.product'
    _columns = {
                 'sale_line_warn' : fields.boolean('Sale Order Line'),
                 'sale_line_warn_msg' : fields.char('Message for Sale Order Line', size=64),
                 'purchase_line_warn' : fields.boolean('Purchase Order Line'),
                 'purchase_line_warn_msg' : fields.char('Message for Purchase Order Line', size=64),
                 }
product_product()

class sale_order_line(osv.osv):
    _inherit = 'sale.order.line'
    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False, packaging=False):
        warning = {}
        if not product:
            return {'value': {'th_weight' : 0, 'product_packaging': False,
                'product_uos_qty': qty}, 'domain': {'product_uom': [],
                   'product_uos': []}}
        product_obj = self.pool.get('product.product') 
        product_info = product_obj.browse(cr, uid, product)
        title=False
        message=False
        if product_info.sale_line_warn:
            title= "Message",
            message= product_info.sale_line_warn_msg
        result =  super(sale_order_line, self).product_id_change( cr, uid, ids, pricelist, product, qty,
            uom, qty_uos, uos, name, partner_id,
            lang, update_tax, date_order, packaging)
        if title and message:
             warning['title']=title[0]
             warning['message']=message
        if result.get('warning',False):
            warning['title']= title and title[0]+' & '+result['warning']['title'] or result['warning']['title']
            warning['message']=message and message +'\n\n'+result['warning']['message'] or result['warning']['message']
        return {'value': result['value'], 'warning':warning}
    
sale_order_line()

class purchase_order_line(osv.osv):
    _inherit = 'purchase.order.line'
    def product_id_change(self,cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False):
        warning = {}
        if not product:
            return {'value': {'price_unit': 0.0, 'name':'','notes':'', 'product_uom' : False}, 'domain':{'product_uom':[]}}
        product_obj = self.pool.get('product.product') 
        product_info = product_obj.browse(cr, uid, product)
        title=False
        message=False
        if product_info.purchase_line_warn:
            title =  "Message"
            message =  product_info.purchase_line_warn_msg
            
        result =  super(purchase_order_line, self).product_id_change(cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order)
        if title and message:
             warning['title']=title[0]
             warning['message']=message
        if result.get('warning',False):
            warning['title']= title and title[0]+' & '+result['warning']['title'] or result['warning']['title']
            warning['message']=message and message +'\n\n'+result['warning']['message'] or result['warning']['message']
        return {'value': result['value'], 'warning':warning}
    
purchase_order_line()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
