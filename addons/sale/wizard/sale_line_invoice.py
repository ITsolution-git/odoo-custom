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
from service import web_services
import wizard
import netsvc
import ir
import pooler

class sale_order_line_make_invoice(osv.osv_memory):
    _name = "sale.order.line.make.invoice"
    _description = "Sale OrderLine Make_invoice"
    _columns = {
        'grouped': fields.boolean('Group the invoices'),
    }
    _default = {
        'grouped' : lambda *a: False
    }

    def make_invoices(self, cr, uid, ids, context):
        """ 
             To make invoices.
            
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param ids: the ID or list of IDs 
             @param context: A standard dictionary 
             
             @return: A dictionary which of fields with values. 
        
        """        

        res = False
        invoices = {}

    #TODO: merge with sale.py/make_invoice
        def make_invoice(order, lines):
            """ 
                 To make invoices.
                
                 @param order: 
                 @param lines: 
                
                 @return:  
            
            """            
            a = order.partner_id.property_account_receivable.id
            if order.partner_id and order.partner_id.property_payment_term.id:
                pay_term = order.partner_id.property_payment_term.id
            else:
                pay_term = False
            inv = {
                'name': order.name,
                'origin': order.name,
                'type': 'out_invoice',
                'reference': "P%dSO%d" % (order.partner_id.id, order.id),
                'account_id': a,
                'partner_id': order.partner_id.id,
                'address_invoice_id': order.partner_invoice_id.id,
                'address_contact_id': order.partner_invoice_id.id,
                'invoice_line': [(6,0,lines)],
                'currency_id' : order.pricelist_id.currency_id.id,
                'comment': order.note,
                'payment_term': pay_term,
                'fiscal_position': order.partner_id.property_account_position.id or order.fiscal_position.id
            }
            inv_id = self.pool.get('account.invoice').create(cr, uid, inv)
            return inv_id

        sales_order_line_obj = self.pool.get('sale.order.line')
        sales_order_obj = self.pool.get('sale.order')
        wf_service = netsvc.LocalService('workflow')
        for line in sales_order_line_obj.browse(cr,uid,context['active_ids']):
            if (not line.invoiced) and (line.state not in ('draft','cancel')):
                if not line.order_id.id in invoices:
                    invoices[line.order_id.id] = []
                line_id = sales_order_line_obj.invoice_line_create(cr, uid,
                        [line.id])
                for lid in line_id:
                    invoices[line.order_id.id].append((line, lid))
                sales_order_line_obj.write(cr, uid, [line.id],
                        {'invoiced': True})
            flag = True
            data_sale = sales_order_obj.browse(cr,uid,line.order_id.id)
            for line in data_sale.order_line:
                if not line.invoiced:
                    flag = False
                    break
            if flag:
                wf_service.trg_validate(uid, 'sale.order', line.order_id.id, 'all_lines', cr)
                sales_order_obj.write(cr,uid,[line.order_id.id],{'state' : 'progress'})

        for result in invoices.values():
            order = result[0][0].order_id
            il = map(lambda x: x[1], result)
            res = make_invoice(order, il)
            cr.execute('INSERT INTO sale_order_invoice_rel \
                    (order_id,invoice_id) values (%s,%s)', (order.id, res))
        return {}


sale_order_line_make_invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
