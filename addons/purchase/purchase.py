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

from osv import fields
from osv import osv
import time
import netsvc

import ir
from mx import DateTime
import pooler
from tools import config
from tools.translate import _

#
# Model definition
#
class purchase_order(osv.osv):
    def _calc_amount(self, cr, uid, ids, prop, unknow_none, unknow_dict):
        res = {}
        for order in self.browse(cr, uid, ids):
            res[order.id] = 0
            for oline in order.order_line:
                res[order.id] += oline.price_unit * oline.product_qty
        return res

    def _amount_untaxed(self, cr, uid, ids, field_name, arg, context):
        res = {}
        cur_obj=self.pool.get('res.currency')
        for purchase in self.browse(cr, uid, ids):
            res[purchase.id] = 0.0
            for line in purchase.order_line:
                res[purchase.id] += line.price_subtotal
            cur = purchase.pricelist_id.currency_id
            res[purchase.id] = cur_obj.round(cr, uid, cur, res[purchase.id])

        return res

    def _amount_tax(self, cr, uid, ids, field_name, arg, context):
        res = {}
        cur_obj=self.pool.get('res.currency')
        for order in self.browse(cr, uid, ids):
            val = 0.0
            cur=order.pricelist_id.currency_id
            for line in order.order_line:
                for c in self.pool.get('account.tax').compute(cr, uid, line.taxes_id, line.price_unit, line.product_qty, order.partner_address_id.id, line.product_id, order.partner_id):
                    val+= cur_obj.round(cr, uid, cur, c['amount'])
            res[order.id]=cur_obj.round(cr, uid, cur, val)
        return res

    def _amount_total(self, cr, uid, ids, field_name, arg, context):
        res = {}
        untax = self._amount_untaxed(cr, uid, ids, field_name, arg, context)
        tax = self._amount_tax(cr, uid, ids, field_name, arg, context)
        cur_obj=self.pool.get('res.currency')
        for id in ids:
            order=self.browse(cr, uid, [id])[0]
            cur=order.pricelist_id.currency_id
            res[id] = cur_obj.round(cr, uid, cur, untax.get(id, 0.0) + tax.get(id, 0.0))
        return res

    def _minimum_planned_date(self, cr, uid, ids, field_name, arg, context):
        res={}
        purchase_obj=self.browse(cr, uid, ids, context=context)
        for purchase in purchase_obj:
            res[purchase.id] = False
            if purchase.order_line:
                min_date=purchase.order_line[0].date_planned
                for line in purchase.order_line:
                    if line.date_planned < min_date:
                        min_date=line.date_planned
                res[purchase.id]=min_date
        return res

    def _invoiced_rate(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for purchase in self.browse(cursor, user, ids, context=context):
            tot = 0.0
            if purchase.invoice_id and purchase.invoice_id.state not in ('draft','cancel'):
                tot += purchase.invoice_id.amount_untaxed
            if purchase.amount_untaxed:
                res[purchase.id] = tot * 100.0 / purchase.amount_untaxed
            else:
                res[purchase.id] = 0.0
        return res

    def _shipped_rate(self, cr, uid, ids, name, arg, context=None):
        if not ids: return {}
        res = {}
        for id in ids:
            res[id] = [0.0,0.0]
        cr.execute('''SELECT
                p.purchase_id,sum(m.product_qty), m.state
            FROM
                stock_move m
            LEFT JOIN
                stock_picking p on (p.id=m.picking_id)
            WHERE
                p.purchase_id in ('''+','.join(map(str,ids))+''')
            GROUP BY m.state, p.purchase_id''')
        for oid,nbr,state in cr.fetchall():
            if state=='cancel':
                continue
            if state=='done':
                res[oid][0] += nbr or 0.0
                res[oid][1] += nbr or 0.0
            else:
                res[oid][1] += nbr or 0.0
        for r in res:
            if not res[r][1]:
                res[r] = 0.0
            else:
                res[r] = 100.0 * res[r][0] / res[r][1]
        return res

    _columns = {
        'name': fields.char('Order Reference', size=64, required=True, select=True),
        'origin': fields.char('Origin', size=64),
        'partner_ref': fields.char('Partner Ref.', size=64),
        'date_order':fields.date('Date Ordered', required=True, states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)]}),
        'date_approve':fields.date('Date Approved'),
        'partner_id':fields.many2one('res.partner', 'Supplier', required=True, states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)]}, change_default=True),
        'partner_address_id':fields.many2one('res.partner.address', 'Address', required=True, states={'posted':[('readonly',True)]}),

        'dest_address_id':fields.many2one('res.partner.address', 'Destination Address', states={'posted':[('readonly',True)]}),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse', states={'posted':[('readonly',True)]}),
        'location_id': fields.many2one('stock.location', 'Destination', required=True),

        'pricelist_id':fields.many2one('product.pricelist', 'Pricelist', required=True, states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)]}, help="The pricelist sets the currency used for this purchase order. It also computes the supplier price for the selected products/quantities."),

        'state': fields.selection([('draft', 'Request for Quotation'), ('wait', 'Waiting'), ('confirmed', 'Confirmed'), ('approved', 'Approved'),('except_picking', 'Shipping Exception'), ('except_invoice', 'Invoice Exception'), ('done', 'Done'), ('cancel', 'Cancelled')], 'Order Status', readonly=True, help="The state of the purchase order or the quotation request. A quotation is a purchase order in a 'Draft' state. Then the order has to be confirmed by the user, the state switch to 'Confirmed'. Then the supplier must confirm the order to change the state to 'Approved'. When the purchase order is paid and received, the state becomes 'Done'. If a cancel action occurs in the invoice or in the reception of goods, the state becomes in exception.", select=True),
        'order_line': fields.one2many('purchase.order.line', 'order_id', 'Order Lines', states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)]}),
        'validator' : fields.many2one('res.users', 'Validated by', readonly=True),
        'notes': fields.text('Notes'),
        'invoice_id': fields.many2one('account.invoice', 'Invoice', readonly=True),
        'picking_ids': fields.one2many('stock.picking', 'purchase_id', 'Picking List', readonly=True, help="This is the list of picking list that have been generated for this purchase"),
        'shipped':fields.boolean('Received', readonly=True, select=True),
        'shipped_rate': fields.function(_shipped_rate, method=True, string='Received', type='float'),
        'invoiced':fields.boolean('Invoiced & Paid', readonly=True, select=True),
        'invoiced_rate': fields.function(_invoiced_rate, method=True, string='Invoiced', type='float'),
        'invoice_method': fields.selection([('manual','Manual'),('order','From order'),('picking','From picking')], 'Invoicing Control', required=True),
        'minimum_planned_date':fields.function(_minimum_planned_date, method=True,store=True, string='Planned Date', type='date', help="This is computed as the minimum scheduled date of all purchase order lines' products."),
        'amount_untaxed': fields.function(_amount_untaxed, method=True, string='Untaxed Amount'),
        'amount_tax': fields.function(_amount_tax, method=True, string='Taxes'),
        'amount_total': fields.function(_amount_total, method=True, string='Total'),
    }
    _defaults = {
        'date_order': lambda *a: time.strftime('%Y-%m-%d'),
        'state': lambda *a: 'draft',
        'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'purchase.order'),
        'shipped': lambda *a: 0,
        'invoice_method': lambda *a: 'order',
        'invoiced': lambda *a: 0,
        'partner_address_id': lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['default'])['default'],
        'pricelist_id': lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').browse(cr, uid, context['partner_id']).property_product_pricelist_purchase.id,
    }
    _name = "purchase.order"
    _description = "Purchase order"
    _order = "name desc"

    def button_dummy(self, cr, uid, ids, context={}):
        return True

    def onchange_dest_address_id(self, cr, uid, ids, adr_id):
        if not adr_id:
            return {}
        part_id = self.pool.get('res.partner.address').read(cr, uid, [adr_id], ['partner_id'])[0]['partner_id'][0]
        loc_id = self.pool.get('res.partner').browse(cr, uid, part_id).property_stock_customer.id
        return {'value':{'location_id': loc_id, 'warehouse_id': False}}

    def onchange_warehouse_id(self, cr, uid, ids, warehouse_id):
        if not warehouse_id:
            return {}
        res = self.pool.get('stock.warehouse').read(cr, uid, [warehouse_id], ['lot_input_id'])[0]['lot_input_id'][0]
        return {'value':{'location_id': res, 'dest_address_id': False}}

    def onchange_partner_id(self, cr, uid, ids, part):
        if not part:
            return {'value':{'partner_address_id': False}}
        addr = self.pool.get('res.partner').address_get(cr, uid, [part], ['default'])
        pricelist = self.pool.get('res.partner').browse(cr, uid, part).property_product_pricelist_purchase.id
        return {'value':{'partner_address_id': addr['default'], 'pricelist_id': pricelist}}

    def wkf_approve_order(self, cr, uid, ids):
        self.write(cr, uid, ids, {'state': 'approved', 'date_approve': time.strftime('%Y-%m-%d')})
        return True

    def wkf_confirm_order(self, cr, uid, ids, context={}):
        for po in self.browse(cr, uid, ids):
            if self.pool.get('res.partner.event.type').check(cr, uid, 'purchase_open'):
                self.pool.get('res.partner.event').create(cr, uid, {'name':'Purchase Order: '+po.name, 'partner_id':po.partner_id.id, 'date':time.strftime('%Y-%m-%d %H:%M:%S'), 'user_id':uid, 'partner_type':'retailer', 'probability': 1.0, 'planned_cost':po.amount_untaxed})
        current_name = self.name_get(cr, uid, ids)[0][1]
        for id in ids:
            self.write(cr, uid, [id], {'state' : 'confirmed', 'validator' : uid})
        return True

    def wkf_warn_buyer(self, cr, uid, ids):
        self.write(cr, uid, ids, {'state' : 'wait', 'validator' : uid})
        request = pooler.get_pool(cr.dbname).get('res.request')
        for po in self.browse(cr, uid, ids):
            managers = []
            for oline in po.order_line:
                manager = oline.product_id.product_manager
                if manager and not (manager.id in managers):
                    managers.append(manager.id)
            for manager_id in managers:
                request.create(cr, uid,
                      {'name' : "Purchase amount over the limit",
                       'act_from' : uid,
                       'act_to' : manager_id,
                       'body': 'Somebody has just confirmed a purchase with an amount over the defined limit',
                       'ref_partner_id': po.partner_id.id,
                       'ref_doc1': 'purchase.order,%d' % (po.id,),
                       })
    def inv_line_create(self,a,ol):
        return (0, False, {
                    'name': ol.name,
                    'account_id': a,
                    'price_unit': ol.price_unit or 0.0,
                    'quantity': ol.product_qty,
                    'product_id': ol.product_id.id or False,
                    'uos_id': ol.product_uom.id or False,
                    'invoice_line_tax_id': [(6, 0, [x.id for x in ol.taxes_id])],
                    'account_analytic_id': ol.account_analytic_id.id,
                })

    def action_invoice_create(self, cr, uid, ids, *args):
        res = False
        for o in self.browse(cr, uid, ids):
            il = []
            for ol in o.order_line:

                if ol.product_id:
                    a = ol.product_id.product_tmpl_id.property_account_expense.id
                    if not a:
                        a = ol.product_id.categ_id.property_account_expense_categ.id
                    if not a:
                        raise osv.except_osv(_('Error !'), _('There is no expense account defined for this product: "%s" (id:%d)') % (ol.product_id.name, ol.product_id.id,))
                else:
                    a = self.pool.get('ir.property').get(cr, uid, 'property_account_expense_categ', 'product.category')
                il.append(self.inv_line_create(a,ol))
#               il.append((0, False, {
#                   'name': ol.name,
#                   'account_id': a,
#                   'price_unit': ol.price_unit or 0.0,
#                   'quantity': ol.product_qty,
#                   'product_id': ol.product_id.id or False,
#                   'uos_id': ol.product_uom.id or False,
#                   'invoice_line_tax_id': [(6, 0, [x.id for x in ol.taxes_id])],
#                   'account_analytic_id': ol.account_analytic_id.id,
#               }))

            a = o.partner_id.property_account_payable.id
            inv = {
                'name': o.partner_ref or o.name,
                'reference': "P%dPO%d" % (o.partner_id.id, o.id),
                'account_id': a,
                'type': 'in_invoice',
                'partner_id': o.partner_id.id,
                'currency_id': o.pricelist_id.currency_id.id,
                'address_invoice_id': o.partner_address_id.id,
                'address_contact_id': o.partner_address_id.id,
                'origin': o.name,
                'invoice_line': il,
            }
            inv_id = self.pool.get('account.invoice').create(cr, uid, inv, {'type':'in_invoice'})
            self.pool.get('account.invoice').button_compute(cr, uid, [inv_id], {'type':'in_invoice'}, set_total=True)

            self.write(cr, uid, [o.id], {'invoice_id': inv_id})
            res = inv_id
        return res

    def has_stockable_product(self,cr, uid, ids, *args):
        for order in self.browse(cr, uid, ids):
            for order_line in order.order_line:
                if order_line.product_id and order_line.product_id.product_tmpl_id.type in ('product', 'consu'):
                    return True
        return False

    def action_picking_create(self,cr, uid, ids, *args):
        picking_id = False
        for order in self.browse(cr, uid, ids):
            loc_id = order.partner_id.property_stock_supplier.id
            istate = 'none'
            if order.invoice_method=='picking':
                istate = '2binvoiced'
            picking_id = self.pool.get('stock.picking').create(cr, uid, {
                'origin': order.name+((order.origin and (':'+order.origin)) or ''),
                'type': 'in',
                'address_id': order.dest_address_id.id or order.partner_address_id.id,
                'invoice_state': istate,
                'purchase_id': order.id,
            })
            for order_line in order.order_line:
                if not order_line.product_id:
                    continue
                if order_line.product_id.product_tmpl_id.type in ('product', 'consu'):
                    dest = order.location_id.id
                    self.pool.get('stock.move').create(cr, uid, {
                        'name': 'PO:'+order_line.name,
                        'product_id': order_line.product_id.id,
                        'product_qty': order_line.product_qty,
                        'product_uos_qty': order_line.product_qty,
                        'product_uom': order_line.product_uom.id,
                        'product_uos': order_line.product_uom.id,
                        'date_planned': order_line.date_planned,
                        'location_id': loc_id,
                        'location_dest_id': dest,
                        'picking_id': picking_id,
                        'move_dest_id': order_line.move_dest_id.id,
                        'state': 'assigned',
                        'purchase_line_id': order_line.id,
                    })
                    if order_line.move_dest_id:
                        self.pool.get('stock.move').write(cr, uid, [order_line.move_dest_id.id], {'location_id':order.location_id.id})
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)
        return picking_id
    def copy(self, cr, uid, id, default=None,context={}):
        if not default:
            default = {}
        default.update({
            'state':'draft',
            'shipped':False,
            'invoiced':False,
            'invoice_id':False,
            'picking_ids':[],
            'name': self.pool.get('ir.sequence').get(cr, uid, 'purchase.order'),
        })
        return super(purchase_order, self).copy(cr, uid, id, default, context)

purchase_order()

class purchase_order_line(osv.osv):
    def _amount_line(self, cr, uid, ids, prop, unknow_none,unknow_dict):
        res = {}
        cur_obj=self.pool.get('res.currency')
        for line in self.browse(cr, uid, ids):
            cur = line.order_id.pricelist_id.currency_id
            res[line.id] = cur_obj.round(cr, uid, cur, line.price_unit * line.product_qty)
        return res

    _columns = {
        'name': fields.char('Description', size=64, required=True),
        'product_qty': fields.float('Quantity', required=True, digits=(16,2)),
        'date_planned': fields.date('Scheduled date', required=True),
        'taxes_id': fields.many2many('account.tax', 'purchase_order_taxe', 'ord_id', 'tax_id', 'Taxes'),
        'product_uom': fields.many2one('product.uom', 'Product UOM', required=True),
        'product_id': fields.many2one('product.product', 'Product', domain=[('purchase_ok','=',True)], change_default=True),
        'move_id': fields.many2one('stock.move', 'Reservation', ondelete='set null'),
        'move_dest_id': fields.many2one('stock.move', 'Reservation Destination', ondelete='set null'),
        'price_unit': fields.float('Unit Price', required=True, digits=(16, int(config['price_accuracy']))),
        'price_subtotal': fields.function(_amount_line, method=True, string='Subtotal'),
        'notes': fields.text('Notes'),
        'order_id': fields.many2one('purchase.order', 'Order Ref', select=True, required=True, ondelete='cascade'),
        'account_analytic_id':fields.many2one('account.analytic.account', 'Analytic Account',),
    }
    _defaults = {
        'product_qty': lambda *a: 1.0
    }
    _table = 'purchase_order_line'
    _name = 'purchase.order.line'
    _description = 'Purchase Order lines'
    def copy(self, cr, uid, id, default=None,context={}):
        if not default:
            default = {}
        default.update({'state':'draft', 'move_id':False})
        return super(purchase_order_line, self).copy(cr, uid, id, default, context)

    def product_id_change(self, cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False):
        if not pricelist:
            raise osv.except_osv(_('No Pricelist !'), _('You have to select a pricelist in the purchase form !\nPlease set one before choosing a product.'))
        if not product:
            return {'value': {'price_unit': 0.0, 'name':'','notes':''}, 'domain':{'product_uom':[]}}
        lang=False
        if partner_id:
            lang=self.pool.get('res.partner').read(cr, uid, [partner_id])[0]['lang']
        context={'lang':lang}

        prod = self.pool.get('product.product').read(cr, uid, [product], ['supplier_taxes_id','name','seller_delay','uom_po_id','description_purchase'])[0]
        prod_uom_po = prod['uom_po_id'][0]
        if not uom:
            uom = prod_uom_po
        if not date_order:
            date_order = time.strftime('%Y-%m-%d')
        price = self.pool.get('product.pricelist').price_get(cr,uid,[pricelist],
                product, qty or 1.0, partner_id, {
                    'uom': uom,
                    'date': date_order,
                    })[pricelist]
        dt = (DateTime.now() + DateTime.RelativeDateTime(days=prod['seller_delay'] or 0.0)).strftime('%Y-%m-%d')
        prod_name = self.pool.get('product.product').name_get(cr, uid, [product], context=context)[0][1]

        res = {'value': {'price_unit': price, 'name':prod_name, 'taxes_id':prod['supplier_taxes_id'], 'date_planned': dt,'notes':prod['description_purchase'], 'product_uom': uom}}
        domain = {}

        if res['value']['taxes_id']:
            taxes = self.pool.get('account.tax').browse(cr, uid,
                    [x.id for x in product.supplier_taxes_id])
            taxep = None
            if partner_id:
                taxep = self.pool.get('res.partner').browse(cr, uid,
                        partner_id).property_account_supplier_tax
            if not taxep or not taxep.id:
                res['value']['taxes_id'] = [x.id for x in product.taxes_id]
            else:
                res5 = [taxep.id]
                for t in taxes:
                    if not t.tax_group==taxep.tax_group:
                        res5.append(t.id)
                res['value']['taxes_id'] = res5

        res2 = self.pool.get('product.uom').read(cr, uid, [uom], ['category_id'])
        res3 = self.pool.get('product.uom').read(cr, uid, [prod_uom_po], ['category_id'])
        domain = {'product_uom':[('category_id','=',res2[0]['category_id'][0])]}
        if res2[0]['category_id'] != res3[0]['category_id']:
            raise osv.except_osv(_('Wrong Product UOM !'), _('You have to select a product UOM in the same category than the purchase UOM of the product'))

        res['domain'] = domain
        return res

    def product_uom_change(self, cr, uid, ids, pricelist, product, qty, uom,
            partner_id, date_order=False):
        res = self.product_id_change(cr, uid, ids, pricelist, product, qty, uom,
                partner_id, date_order=date_order)
        if 'product_uom' in res['value']:
            del res['value']['product_uom']
        if not uom:
            res['value']['price_unit'] = 0.0
        return res
purchase_order_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

