# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2005-2006 TINY SPRL. (http://tiny.be) All Rights Reserved.
#
# $Id: make_invoice.py 1070 2005-07-29 12:41:24Z nicoe $
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

import wizard
import pooler
from osv import fields, osv

form = """<?xml version="1.0"?>
<form string="Advance Payment">
    <field name="product_id"/>
    <newline />
    <field name="qtty"/>
    <field name="amount"/>
    <newline />
</form>
"""
fields = {
        'product_id': {'string':'Product', 'type':'many2one','relation':'product.product','required':True},
        'amount': {'string':'Unit Price', 'type':'float', 'size':(16,2),'required':True},
        'qtty': {'string':'Quantity', 'type':'float', 'size':(16,2),'required':True, 'default': lambda *a: 1},
}

form_msg = """<?xml version="1.0"?>
<form string="Invoices">
   <label string="Invoice Created"/>
</form>
"""
fields_msg = {}

def _createInvoices(self, cr, uid, data, context={}):
    list_inv = []
    pool_obj = pooler.get_pool(cr.dbname)
    obj_sale = pool_obj.get('sale.order')
    data_sale = obj_sale.browse(cr,uid,data['ids'])
    obj_lines = pool_obj.get('account.invoice.line')
    for sale in data_sale:
        address_contact = False
        address_invoice = False
        create_ids = []
        ids_inv = []
        if sale.order_policy == 'postpaid':
            raise osv.except_osv(
                _('Error'),
                _('You must cannot make an advance on a sale order that is defined as \'Automatic Invoice after delivery\'.'))
        val = obj_lines.product_id_change(cr, uid, [], data['form']['product_id'],uom = False, partner_id = sale.partner_id.id)
        line_id =obj_lines.create(cr, uid, {
        'name': val['value']['name'],
        'account_id':val['value']['account_id'],
        'price_unit': data['form']['amount'],
        'quantity': data['form']['qtty'],
        'discount': False,
        'uos_id': val['value']['uos_id'],
        'product_id':data['form']['product_id'],
        'invoice_line_tax_id': [(6,0,val['value']['invoice_line_tax_id'])],
        'note':'',
        })
        create_ids.append(line_id)
        inv = {
            'name': sale.name,
            'origin': sale.name,
            'type': 'out_invoice',
            'reference': False,
            'account_id': sale.partner_id.property_account_receivable.id,
            'partner_id': sale.partner_id.id,
            'address_invoice_id':sale.partner_invoice_id.id,
            'address_contact_id':sale.partner_order_id.id,
            'invoice_line': [(6,0,create_ids)],
            'currency_id' :sale.pricelist_id.currency_id.id,
            'comment': '',
            'payment_term':sale.partner_id.property_payment_term.id,
            }
        inv_obj = pool_obj.get('account.invoice')
        inv_id = inv_obj.create(cr, uid, inv)

        for inv in sale.invoice_ids:
            ids_inv.append(inv.id)
        ids_inv.append(inv_id)
        obj_sale.write(cr,uid,sale.id,{'invoice_ids':[(6,0,ids_inv)]})
        list_inv.append(inv_id)
    return {'invoice_ids':list_inv}

class sale_advance_payment(wizard.interface):
    def _open_invoice(self, cr, uid, data, context):
        pool_obj = pooler.get_pool(cr.dbname)
        model_data_ids = pool_obj.get('ir.model.data').search(cr,uid,[('model','=','ir.ui.view'),('name','=','invoice_form')])
        resource_id = pool_obj.get('ir.model.data').read(cr,uid,model_data_ids,fields=['res_id'])[0]['res_id']
        return {
            'domain': "[('id','in', ["+','.join(map(str,data['form']['invoice_ids']))+"])]",
            'name': 'Invoices',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.invoice',
            'views': [(False,'tree'),(resource_id,'form')],
            'context': "{'type':'out_invoice'}",
            'type': 'ir.actions.act_window'
        }

    states = {
        'init' : {
            'actions' : [],
            'result' : {'type' : 'form' ,   'arch' : form,'fields' : fields,'state' : [('end','Cancel'),('create','Make Invoice')]}
        },
        'create': {
            'actions': [_createInvoices],
            'result': {'type' : 'form' ,'arch' : form_msg,'fields' : fields_msg, 'state':[('end','Ok'),('open','Open Invoice')]}
        },
        'open': {
            'actions': [],
            'result': {'type':'action', 'action':_open_invoice, 'state':'end'}
        }
    }

sale_advance_payment("sale.advance_payment_inv")
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

