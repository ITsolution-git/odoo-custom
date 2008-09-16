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
import netsvc
from osv import fields, osv
import ir
from mx import DateTime
from tools import config
from tools.translate import _

class sale_shop(osv.osv):
    _name = "sale.shop"
    _description = "Sale Shop"
    _columns = {
        'name': fields.char('Shop name',size=64, required=True),
        'payment_default_id': fields.many2one('account.payment.term','Default Payment Term',required=True),
        'payment_account_id': fields.many2many('account.account','sale_shop_account','shop_id','account_id','Payment accounts'),
        'warehouse_id': fields.many2one('stock.warehouse','Warehouse'),
        'pricelist_id': fields.many2one('product.pricelist', 'Pricelist'),
        'project_id': fields.many2one('account.analytic.account', 'Analytic Account'),
    }
sale_shop()

def _incoterm_get(self, cr, uid, context={}):
    cr.execute('select code, code||\', \'||name from stock_incoterms where active')
    return cr.fetchall()

class sale_order(osv.osv):
    _name = "sale.order"
    _description = "Sale Order"
    def copy(self, cr, uid, id, default=None,context={}):
        if not default:
            default = {}
        default.update({
            'state':'draft',
            'shipped':False,
            'invoice_ids':[],
            'picking_ids':[],
            'name': self.pool.get('ir.sequence').get(cr, uid, 'sale.order'),
        })
        return super(sale_order, self).copy(cr, uid, id, default, context)

    def _amount_untaxed(self, cr, uid, ids, field_name, arg, context):
        res = {}
        cur_obj=self.pool.get('res.currency')
        for sale in self.browse(cr, uid, ids):
            res[sale.id] = 0.0
            for line in sale.order_line:
                res[sale.id] += line.price_subtotal
            cur = sale.pricelist_id.currency_id
            res[sale.id] = cur_obj.round(cr, uid, cur, res[sale.id])
        return res

    def _amount_tax(self, cr, uid, ids, field_name, arg, context):
        res = {}
        cur_obj=self.pool.get('res.currency')
        for order in self.browse(cr, uid, ids):
            val = 0.0
            cur=order.pricelist_id.currency_id
            for line in order.order_line:
                for c in self.pool.get('account.tax').compute(cr, uid, line.tax_id, line.price_unit * (1-(line.discount or 0.0)/100.0), line.product_uom_qty, order.partner_invoice_id.id, line.product_id, order.partner_id):
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

    def _picked_rate(self, cr, uid, ids, name, arg, context=None):
        if not ids: return {}
        res = {}
        for id in ids:
            res[id] = [0.0,0.0]
        cr.execute('''SELECT
                p.sale_id,sum(m.product_qty), m.state
            FROM
                stock_move m
            LEFT JOIN
                stock_picking p on (p.id=m.picking_id)
            WHERE
                p.sale_id in ('''+','.join(map(str,ids))+''')
            GROUP BY m.state, p.sale_id''')
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
        for order in self.browse(cr, uid, ids, context):
            if order.shipped:
                res[order.id] = 100.0
        return res

    def _invoiced_rate(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for sale in self.browse(cursor, user, ids, context=context):
            if sale.invoiced:
                res[sale.id] = 100.0
                continue
            tot = 0.0
            for invoice in sale.invoice_ids:
                if invoice.state not in ('draft','cancel'):
                    tot += invoice.amount_untaxed
            if tot:
                res[sale.id] = tot * 100.0 / sale.amount_untaxed
            else:
                res[sale.id] = 0.0
        return res

    def _invoiced(self, cursor, user, ids, name, arg, context=None):
        res = {}
        for sale in self.browse(cursor, user, ids, context=context):
            res[sale.id] = True
            for invoice in sale.invoice_ids:
                if invoice.state <> 'paid':
                    res[sale.id] = False
                    break
            if not sale.invoice_ids:
                res[sale.id] = False
        return res

    def _invoiced_search(self, cursor, user, obj, name, args):
        if not len(args):
            return []
        clause = ''
        no_invoiced = False
        for arg in args:
            if arg[1] == '=':
                if arg[2]:
                    clause += 'AND inv.state = \'paid\''
                else:
                    clause += 'AND inv.state <> \'paid\''
                    no_invoiced = True
        cursor.execute('SELECT rel.order_id ' \
                'FROM sale_order_invoice_rel AS rel, account_invoice AS inv ' \
                'WHERE rel.invoice_id = inv.id ' + clause)
        res = cursor.fetchall()
        if no_invoiced:
            cursor.execute('SELECT sale.id ' \
                    'FROM sale_order AS sale ' \
                    'WHERE sale.id NOT IN ' \
                        '(SELECT rel.order_id ' \
                        'FROM sale_order_invoice_rel AS rel)')
            res.extend(cursor.fetchall())
        if not res:
            return [('id', '=', 0)]
        return [('id', 'in', [x[0] for x in res])]

    _columns = {
        'name': fields.char('Order Reference', size=64, required=True, select=True),
        'shop_id':fields.many2one('sale.shop', 'Shop', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'origin': fields.char('Origin', size=64),
        'client_order_ref': fields.char('Customer Ref.',size=64),

        'state': fields.selection([
            ('draft','Quotation'),
            ('waiting_date','Waiting Schedule'),
            ('manual','Manual in progress'),
            ('progress','In progress'),
            ('shipping_except','Shipping Exception'),
            ('invoice_except','Invoice Exception'),
            ('done','Done'),
            ('cancel','Cancel')
            ], 'Order State', readonly=True, help="Gives the state of the quotation or sale order. The exception state is automatically set when a cancel operation occurs in the invoice validation (Invoice Exception) or in the packing list process (Shipping Exception). The 'Waiting Schedule' state is set when the invoice is confirmed but waiting for the scheduler to be on the date 'Date Ordered'.", select=True),
        'date_order':fields.date('Date Ordered', required=True, readonly=True, states={'draft':[('readonly',False)]}),

        'user_id':fields.many2one('res.users', 'Salesman', states={'draft':[('readonly',False)]}, select=True),
        'partner_id':fields.many2one('res.partner', 'Customer', readonly=True, states={'draft':[('readonly',False)]}, change_default=True, select=True),
        'partner_invoice_id':fields.many2one('res.partner.address', 'Invoice Address', readonly=True, required=True, states={'draft':[('readonly',False)]}),
        'partner_order_id':fields.many2one('res.partner.address', 'Ordering Contact', readonly=True, required=True, states={'draft':[('readonly',False)]}, help="The name and address of the contact that requested the order or quotation."),
        'partner_shipping_id':fields.many2one('res.partner.address', 'Shipping Address', readonly=True, required=True, states={'draft':[('readonly',False)]}),

        'incoterm': fields.selection(_incoterm_get, 'Incoterm',size=3),
        'picking_policy': fields.selection([('direct','Partial Delivery'),('one','Complete Delivery')], 'Packing Policy', required=True ),
        'order_policy': fields.selection([
            ('prepaid','Payment before delivery'),
            ('manual','Shipping & Manual Invoice'),
            ('postpaid','Automatic Invoice after delivery'),
            ('picking','Invoice from the packings'),
        ], 'Shipping Policy', required=True, readonly=True, states={'draft':[('readonly',False)]},
                    help="""The Shipping Policy is used to synchronise invoice and delivery operations.
  - The 'Pay before delivery' choice will first generate the invoice and then generate the packing order after the payment of this invoice.
  - The 'Shipping & Manual Invoice' will create the packing order directly and wait for the user to manually click on the 'Invoice' button to generate the draft invoice.
  - The 'Invoice after delivery' choice will generate the draft invoice after the packing list have been finished.
  - The 'Invoice from the packings' choice is used to create an invoice during the packing process."""),
        'pricelist_id':fields.many2one('product.pricelist', 'Pricelist', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'project_id':fields.many2one('account.analytic.account', 'Analytic account', readonly=True, states={'draft':[('readonly', False)]}),

        'order_line': fields.one2many('sale.order.line', 'order_id', 'Order Lines', readonly=True, states={'draft':[('readonly',False)]}),
        'invoice_ids': fields.many2many('account.invoice', 'sale_order_invoice_rel', 'order_id', 'invoice_id', 'Invoice', help="This is the list of invoices that have been generated for this sale order. The same sale order may have been invoiced in several times (by line for example)."),
        'picking_ids': fields.one2many('stock.picking', 'sale_id', 'Related Packings', readonly=True, help="This is the list of picking list that have been generated for this invoice"),
        'shipped':fields.boolean('Picked', readonly=True),
        'picked_rate': fields.function(_picked_rate, method=True, string='Picked', type='float'),
        'invoiced_rate': fields.function(_invoiced_rate, method=True, string='Invoiced', type='float'),
        'invoiced': fields.function(_invoiced, method=True, string='Paid',
            fnct_search=_invoiced_search, type='boolean'),
        'note': fields.text('Notes'),
        'amount_untaxed': fields.function(_amount_untaxed, method=True, string='Untaxed Amount'),
        'amount_tax': fields.function(_amount_tax, method=True, string='Taxes'),
        'amount_total': fields.function(_amount_total, method=True, string='Total'),
        'invoice_quantity': fields.selection([('order','Ordered Quantities'),('procurement','Shipped Quantities')], 'Invoice on', help="The sale order will automatically create the invoice proposition (draft invoice). Ordered and delivered quantities may not be the same. You have to choose if you invoice based on ordered or shipped quantities. If the product is a service, shipped quantities means hours spent on the associated tasks."),
        'payment_term' : fields.many2one('account.payment.term', 'Payment Term'),
    }
    _defaults = {
        'picking_policy': lambda *a: 'direct',
        'date_order': lambda *a: time.strftime('%Y-%m-%d'),
        'order_policy': lambda *a: 'manual',
        'state': lambda *a: 'draft',
        'user_id': lambda obj, cr, uid, context: uid,
        'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'sale.order'),
        'invoice_quantity': lambda *a: 'order',
        'partner_invoice_id': lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['invoice'])['invoice'],
        'partner_order_id': lambda self, cr, uid, context: context.get('partner_id', False) and  self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['contact'])['contact'],
        'partner_shipping_id': lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').address_get(cr, uid, [context['partner_id']], ['delivery'])['delivery'],
        'pricelist_id': lambda self, cr, uid, context: context.get('partner_id', False) and self.pool.get('res.partner').browse(cr, uid, context['partner_id']).property_product_pricelist.id,
    }
    _order = 'name desc'

    # Form filling
    def onchange_shop_id(self, cr, uid, ids, shop_id):
        v={}
        if shop_id:
            shop=self.pool.get('sale.shop').browse(cr,uid,shop_id)
            v['project_id']=shop.project_id.id
            # Que faire si le client a une pricelist a lui ?
            if shop.pricelist_id.id:
                v['pricelist_id']=shop.pricelist_id.id
            #v['payment_default_id']=shop.payment_default_id.id
        return {'value':v}

    def action_cancel_draft(self, cr, uid, ids, *args):
        if not len(ids):
            return False
        cr.execute('select id from sale_order_line where order_id in ('+','.join(map(str, ids))+')', ('draft',))
        line_ids = map(lambda x: x[0], cr.fetchall())
        self.write(cr, uid, ids, {'state':'draft', 'invoice_ids':[], 'shipped':0})
        self.pool.get('sale.order.line').write(cr, uid, line_ids, {'invoiced':False, 'state':'draft', 'invoice_lines':[(6,0,[])]})
        wf_service = netsvc.LocalService("workflow")
        for inv_id in ids:
            wf_service.trg_create(uid, 'sale.order', inv_id, cr)
        return True

    def onchange_partner_id(self, cr, uid, ids, part):
        if not part:
            return {'value':{'partner_invoice_id': False, 'partner_shipping_id':False, 'partner_order_id':False, 'payment_term' : False}}
        addr = self.pool.get('res.partner').address_get(cr, uid, [part], ['delivery','invoice','contact'])
        pricelist = self.pool.get('res.partner').browse(cr, uid, part).property_product_pricelist.id
        payment_term = self.pool.get('res.partner').browse(cr, uid, part).property_payment_term.id
        return {'value':{'partner_invoice_id': addr['invoice'], 'partner_order_id':addr['contact'], 'partner_shipping_id':addr['delivery'], 'pricelist_id': pricelist, 'payment_term' : payment_term}}

    def button_dummy(self, cr, uid, ids, context={}):
        return True

#FIXME: the method should return the list of invoices created (invoice_ids)
# and not the id of the last invoice created (res). The problem is that we
# cannot change it directly since the method is called by the sale order
# workflow and I suppose it expects a single id...
    def _inv_get(self, cr, uid, order, context={}):
        return {}

    def _make_invoice(self, cr, uid, order, lines, context={}):
        a = order.partner_id.property_account_receivable.id
        if order.payment_term:
            pay_term = order.payment_term.id
        else:
            pay_term = False
        for preinv in order.invoice_ids:
            if preinv.state in ('open','paid','proforma'):
                for preline in preinv.invoice_line:
                    inv_line_id = self.pool.get('account.invoice.line').copy(cr, uid, preline.id, {'invoice_id':False, 'price_unit':-preline.price_unit})
                    lines.append(inv_line_id)
        inv = {
            'name': order.client_order_ref or order.name,
            'origin': order.name,
            'type': 'out_invoice',
            'reference': "P%dSO%d"%(order.partner_id.id,order.id),
            'account_id': a,
            'partner_id': order.partner_id.id,
            'address_invoice_id': order.partner_invoice_id.id,
            'address_contact_id': order.partner_invoice_id.id,
            'invoice_line': [(6,0,lines)],
            'currency_id' : order.pricelist_id.currency_id.id,
            'comment': order.note,
            'payment_term': pay_term,
        }
        inv_obj = self.pool.get('account.invoice')
        inv.update(self._inv_get(cr, uid, order))
        inv_id = inv_obj.create(cr, uid, inv)
        data = inv_obj.onchange_payment_term_date_invoice(cr, uid, [inv_id],
            pay_term,time.strftime('%Y-%m-%d'))
        if data.get('value',False):
            inv_obj.write(cr, uid, [inv_id], inv.update(data['value']), context=context)
        inv_obj.button_compute(cr, uid, [inv_id])
        return inv_id


    def action_invoice_create(self, cr, uid, ids, grouped=False, states=['confirmed','done']):
        res = False
        invoices = {}
        invoice_ids = []

        for o in self.browse(cr,uid,ids):
            lines = []
            for line in o.order_line:
                if (line.state in states) and not line.invoiced:
                    lines.append(line.id)
            created_lines = self.pool.get('sale.order.line').invoice_line_create(cr, uid, lines)
            if created_lines:
                invoices.setdefault(o.partner_id.id, []).append((o, created_lines))

        if not invoices:
            for o in self.browse(cr, uid, ids):
                for i in o.invoice_ids:
                    if i.state == 'draft':
                        return i.id

        for val in invoices.values():
            if grouped:
                res = self._make_invoice(cr, uid, val[0][0], reduce(lambda x,y: x + y, [l for o,l in val], []))
                for o,l in val:
                    self.write(cr, uid, [o.id], {'state' : 'progress'})
                    cr.execute('insert into sale_order_invoice_rel (order_id,invoice_id) values (%d,%d)', (o.id, res))
            else:
                for order, il in val:
                    res = self._make_invoice(cr, uid, order, il)
                    invoice_ids.append(res)
                    self.write(cr, uid, [order.id], {'state' : 'progress'})
                    cr.execute('insert into sale_order_invoice_rel (order_id,invoice_id) values (%d,%d)', (order.id, res))
        return res

    def action_invoice_cancel(self, cr, uid, ids, context={}):
        for sale in self.browse(cr, uid, ids):
            for line in sale.order_line:
                invoiced=False
                for iline in line.invoice_lines:
                    if iline.invoice_id and iline.invoice_id.state == 'cancel':
                        continue
                    else:
                        invoiced=True
                self.pool.get('sale.order.line').write(cr, uid, [line.id], {'invoiced': invoiced})
        self.write(cr, uid, ids, {'state':'invoice_except', 'invoice_ids':False})
        return True


    def action_cancel(self, cr, uid, ids, context={}):
        ok = True
        sale_order_line_obj = self.pool.get('sale.order.line')
        for sale in self.browse(cr, uid, ids):
            for pick in sale.picking_ids:
                if pick.state not in ('draft','cancel'):
                    raise osv.except_osv(
                        _('Could not cancel sale order !'),
                        _('You must first cancel all packings attached to this sale order.'))
            for r in self.read(cr,uid,ids,['picking_ids']):
                for pick in r['picking_ids']:
                    wf_service = netsvc.LocalService("workflow")
                    wf_service.trg_validate(uid, 'stock.picking', pick, 'button_cancel', cr)
            for inv in sale.invoice_ids:
                if inv.state not in ('draft','cancel'):
                    raise osv.except_osv(
                        _('Could not cancel this sale order !'),
                        _('You must first cancel all invoices attached to this sale order.'))
            for r in self.read(cr,uid,ids,['invoice_ids']):
                for inv in r['invoice_ids']:
                    wf_service = netsvc.LocalService("workflow")
                    wf_service.trg_validate(uid, 'account.invoice', inv, 'invoice_cancel', cr)
            sale_order_line_obj.write(cr, uid, [l.id for l in  sale.order_line],
                    {'state': 'cancel'})
        self.write(cr,uid,ids,{'state':'cancel'})
        return True

    def action_wait(self, cr, uid, ids, *args):
        event_p = self.pool.get('res.partner.event.type').check(cr, uid, 'sale_open')
        event_obj = self.pool.get('res.partner.event')
        for o in self.browse(cr, uid, ids):
            if event_p:
                event_obj.create(cr, uid, {'name': 'Sale Order: '+ o.name,\
                        'partner_id': o.partner_id.id,\
                        'date': time.strftime('%Y-%m-%d %H:%M:%S'),\
                        'user_id': (o.user_id and o.user_id.id) or uid,\
                        'partner_type': 'customer', 'probability': 1.0,\
                        'planned_revenue': o.amount_untaxed})
            if (o.order_policy == 'manual') and (not o.invoice_ids):
                self.write(cr, uid, [o.id], {'state': 'manual'})
            else:
                self.write(cr, uid, [o.id], {'state': 'progress'})
            self.pool.get('sale.order.line').button_confirm(cr, uid, [x.id for x in o.order_line])

    def procurement_lines_get(self, cr, uid, ids, *args):
        res = []
        for order in self.browse(cr, uid, ids, context={}):
            for line in order.order_line:
                if line.procurement_id:
                    res.append(line.procurement_id.id)
        return res

    # if mode == 'finished':
    #   returns True if all lines are done, False otherwise
    # if mode == 'canceled':
    #   returns True if there is at least one canceled line, False otherwise
    def test_state(self, cr, uid, ids, mode, *args):
        assert mode in ('finished', 'canceled'), _("invalid mode for test_state")
        finished = True
        canceled = False
        write_done_ids = []
        write_cancel_ids = []
        for order in self.browse(cr, uid, ids, context={}):
            for line in order.order_line:
                if line.procurement_id and (line.procurement_id.state != 'done') and (line.state!='done'):
                    finished = False
                if line.procurement_id and line.procurement_id.state == 'cancel':
                    canceled = True
                # if a line is finished (ie its procuremnt is done or it has not procuremernt and it
                # is not already marked as done, mark it as being so...
                if ((not line.procurement_id) or line.procurement_id.state == 'done') and line.state != 'done':
                    write_done_ids.append(line.id)
                # ... same for canceled lines
                if line.procurement_id and line.procurement_id.state == 'cancel' and line.state != 'cancel':
                    write_cancel_ids.append(line.id)
        if write_done_ids:
            self.pool.get('sale.order.line').write(cr, uid, write_done_ids, {'state': 'done'})
        if write_cancel_ids:
            self.pool.get('sale.order.line').write(cr, uid, write_cancel_ids, {'state': 'cancel'})

        if mode=='finished':
            return finished
        elif mode=='canceled':
            return canceled

    def action_ship_create(self, cr, uid, ids, *args):
        picking_id=False
        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        for order in self.browse(cr, uid, ids, context={}):
            output_id = order.shop_id.warehouse_id.lot_output_id.id
            picking_id = False
            for line in order.order_line:
                proc_id=False
                date_planned = DateTime.now() + DateTime.RelativeDateTime(days=line.delay or 0.0)
                date_planned = (date_planned - DateTime.RelativeDateTime(days=company.security_lead)).strftime('%Y-%m-%d')
                if line.state == 'done':
                    continue
                if line.product_id and line.product_id.product_tmpl_id.type in ('product', 'consu'):
                    location_id = order.shop_id.warehouse_id.lot_stock_id.id
                    if not picking_id:
                        loc_dest_id = order.partner_id.property_stock_customer.id
                        picking_id = self.pool.get('stock.picking').create(cr, uid, {
                            'origin': order.name,
                            'type': 'out',
                            'state': 'auto',
                            'move_type': order.picking_policy,
                            'sale_id': order.id,
                            'address_id': order.partner_shipping_id.id,
                            'note': order.note,
                            'invoice_state': (order.order_policy=='picking' and '2binvoiced') or 'none',

                        })

                    move_id = self.pool.get('stock.move').create(cr, uid, {
                        'name': line.name[:64],
                        'picking_id': picking_id,
                        'product_id': line.product_id.id,
                        'date_planned': date_planned,
                        'product_qty': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                        'product_uos_qty': line.product_uos_qty,
                        'product_uos': (line.product_uos and line.product_uos.id)\
                                or line.product_uom.id,
                        'product_packaging' : line.product_packaging.id,
                        'address_id' : line.address_allotment_id.id or order.partner_shipping_id.id,
                        'location_id': location_id,
                        'location_dest_id': output_id,
                        'sale_line_id': line.id,
                        'tracking_id': False,
                        'state': 'waiting',
                        'note': line.notes,
                    })
                    proc_id = self.pool.get('mrp.procurement').create(cr, uid, {
                        'name': order.name,
                        'origin': order.name,
                        'date_planned': date_planned,
                        'product_id': line.product_id.id,
                        'product_qty': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                        'product_uos_qty': line.product_uos_qty,
                        'product_uos': (line.product_uos and line.product_uos.id)\
                                or line.product_uom.id,
                        'location_id': order.shop_id.warehouse_id.lot_stock_id.id,
                        'procure_method': line.type,
                        'move_id': move_id,
                        'property_ids': [(6, 0, [x.id for x in line.property_ids])],
                    })
                    wf_service = netsvc.LocalService("workflow")
                    wf_service.trg_validate(uid, 'mrp.procurement', proc_id, 'button_confirm', cr)
                    self.pool.get('sale.order.line').write(cr, uid, [line.id], {'procurement_id': proc_id})
                elif line.product_id and line.product_id.product_tmpl_id.type=='service':
                    proc_id = self.pool.get('mrp.procurement').create(cr, uid, {
                        'name': line.name,
                        'origin': order.name,
                        'date_planned': date_planned,
                        'product_id': line.product_id.id,
                        'product_qty': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                        'location_id': order.shop_id.warehouse_id.lot_stock_id.id,
                        'procure_method': line.type,
                        'property_ids': [(6, 0, [x.id for x in line.property_ids])],
                    })
                    wf_service = netsvc.LocalService("workflow")
                    wf_service.trg_validate(uid, 'mrp.procurement', proc_id, 'button_confirm', cr)
                    self.pool.get('sale.order.line').write(cr, uid, [line.id], {'procurement_id': proc_id})
                else:
                    #
                    # No procurement because no product in the sale.order.line.
                    #
                    pass

            val = {}
            if picking_id:
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)

            if order.state=='shipping_except':
                val['state'] = 'progress'
                if (order.order_policy == 'manual') and order.invoice_ids:
                    val['state'] = 'manual'
            self.write(cr, uid, [order.id], val)

        return True

    def action_ship_end(self, cr, uid, ids, context={}):
        for order in self.browse(cr, uid, ids):
            val = {'shipped':True}
            if order.state=='shipping_except':
                if (order.order_policy=='manual') and not order.invoice_ids:
                    val['state'] = 'manual'
                else:
                    val['state'] = 'progress'
            self.write(cr, uid, [order.id], val)
        return True

    def _log_event(self, cr, uid, ids, factor=0.7, name='Open Order'):
        invs = self.read(cr, uid, ids, ['date_order','partner_id','amount_untaxed'])
        for inv in invs:
            part=inv['partner_id'] and inv['partner_id'][0]
            pr = inv['amount_untaxed'] or 0.0
            partnertype = 'customer'
            eventtype = 'sale'
            self.pool.get('res.partner.event').create(cr, uid, {'name':'Order: '+name, 'som':False, 'description':'Order '+str(inv['id']), 'document':'', 'partner_id':part, 'date':time.strftime('%Y-%m-%d'), 'canal_id':False, 'user_id':uid, 'partner_type':partnertype, 'probability':1.0, 'planned_revenue':pr, 'planned_cost':0.0, 'type':eventtype})

    def has_stockable_products(self,cr, uid, ids, *args):
        for order in self.browse(cr, uid, ids):
            for order_line in order.order_line:
                if order_line.product_id and order_line.product_id.product_tmpl_id.type in ('product', 'consu'):
                    return True
        return False
sale_order()

# TODO add a field price_unit_uos
# - update it on change product and unit price
# - use it in report if there is a uos
class sale_order_line(osv.osv):
    def copy(self, cr, uid, id, default=None, context={}):
        if not default: default = {}
        default.update( {'invoice_lines':[]})
        return super(sale_order_line, self).copy(cr, uid, id, default, context)

    def _amount_line_net(self, cr, uid, ids, field_name, arg, context):
        res = {}
        for line in self.browse(cr, uid, ids):
            res[line.id] = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
        return res

    def _amount_line(self, cr, uid, ids, field_name, arg, context):
        res = {}
        cur_obj=self.pool.get('res.currency')
        for line in self.browse(cr, uid, ids):
            res[line.id] = line.price_unit * line.product_uom_qty * (1 - (line.discount or 0.0) / 100.0)
            cur = line.order_id.pricelist_id.currency_id
            res[line.id] = cur_obj.round(cr, uid, cur, res[line.id])
        return res

    def _number_packages(self, cr, uid, ids, field_name, arg, context):
        res = {}
        for line in self.browse(cr, uid, ids):
            try:
                res[line.id] = int(line.product_uom_qty / line.product_packaging.qty)
            except:
                res[line.id] = 1
        return res

    _name = 'sale.order.line'
    _description = 'Sale Order line'
    _columns = {
        'order_id': fields.many2one('sale.order', 'Order Ref', required=True, ondelete='cascade', select=True),
        'name': fields.char('Description', size=256, required=True, select=True),
        'sequence': fields.integer('Sequence'),
        'delay': fields.float('Delivery Delay', required=True),
        'product_id': fields.many2one('product.product', 'Product', domain=[('sale_ok','=',True)], change_default=True),
        'invoice_lines': fields.many2many('account.invoice.line', 'sale_order_line_invoice_rel', 'order_line_id','invoice_id', 'Invoice Lines', readonly=True),
        'invoiced': fields.boolean('Invoiced', readonly=True),
        'procurement_id': fields.many2one('mrp.procurement', 'Procurement'),
        'price_unit': fields.float('Unit Price', required=True, digits=(16, int(config['price_accuracy']))),
        'price_net': fields.function(_amount_line_net, method=True, string='Net Price', digits=(16, int(config['price_accuracy']))),
        'price_subtotal': fields.function(_amount_line, method=True, string='Subtotal'),
        'tax_id': fields.many2many('account.tax', 'sale_order_tax', 'order_line_id', 'tax_id', 'Taxes'),
        'type': fields.selection([('make_to_stock','from stock'),('make_to_order','on order')],'Procure Method', required=True),
        'property_ids': fields.many2many('mrp.property', 'sale_order_line_property_rel', 'order_id', 'property_id', 'Properties'),
        'address_allotment_id' : fields.many2one('res.partner.address', 'Allotment Partner'),
        'product_uom_qty': fields.float('Quantity (UoM)', digits=(16,2), required=True),
        'product_uom': fields.many2one('product.uom', 'Product UoM', required=True),
        'product_uos_qty': fields.float('Quantity (UOS)'),
        'product_uos': fields.many2one('product.uom', 'Product UOS'),
        'product_packaging': fields.many2one('product.packaging', 'Packaging'),
        'move_ids': fields.one2many('stock.move', 'sale_line_id', 'Inventory Moves', readonly=True),
        'discount': fields.float('Discount (%)', digits=(16,2)),
        'number_packages': fields.function(_number_packages, method=True, type='integer', string='Number packages'),
        'notes': fields.text('Notes'),
        'th_weight' : fields.float('Weight'),
        'state': fields.selection([('draft','Draft'),('confirmed','Confirmed'),('done','Done'),('cancel','Canceled')], 'Status', required=True, readonly=True),
    }
    _order = 'sequence, id'
    _defaults = {
        'discount': lambda *a: 0.0,
        'delay': lambda *a: 0.0,
        'product_uom_qty': lambda *a: 1,
        'product_uos_qty': lambda *a: 1,
        'sequence': lambda *a: 10,
        'invoiced': lambda *a: 0,
        'state': lambda *a: 'draft',
        'type': lambda *a: 'make_to_stock',
        'product_packaging': lambda *a: False
    }
    def invoice_line_create(self, cr, uid, ids, context={}):
        def _get_line_qty(line):
            if (line.order_id.invoice_quantity=='order') or not line.procurement_id:
                if line.product_uos:
                    return line.product_uos_qty or 0.0
                return line.product_uom_qty
            else:
                return self.pool.get('mrp.procurement').quantity_get(cr, uid,
                        line.procurement_id.id, context)

        def _get_line_uom(line):
            if (line.order_id.invoice_quantity=='order') or not line.procurement_id:
                if line.product_uos:
                    return line.product_uos.id
                return line.product_uom.id
            else:
                return self.pool.get('mrp.procurement').uom_get(cr, uid,
                        line.procurement_id.id, context)

        create_ids = []
        for line in self.browse(cr, uid, ids, context):
            if not line.invoiced:
                if line.product_id:
                    a =  line.product_id.product_tmpl_id.property_account_income.id
                    if not a:
                        a = line.product_id.categ_id.property_account_income_categ.id
                    if not a:
                        raise osv.except_osv(_('Error !'),
                                _('There is no income account defined ' \
                                        'for this product: "%s" (id:%d)') % \
                                        (line.product_id.name, line.product_id.id,))
                else:
                    a = self.pool.get('ir.property').get(cr, uid,
                            'property_account_income_categ', 'product.category',
                            context=context)
                uosqty = _get_line_qty(line)
                uos_id = _get_line_uom(line)
                pu = 0.0
                if uosqty:
                    pu = round(line.price_unit * line.product_uom_qty / uosqty,
                            int(config['price_accuracy']))
                inv_id = self.pool.get('account.invoice.line').create(cr, uid, {
                    'name': line.name,
                    'account_id': a,
                    'price_unit': pu,
                    'quantity': uosqty,
                    'discount': line.discount,
                    'uos_id': uos_id,
                    'product_id': line.product_id.id or False,
                    'invoice_line_tax_id': [(6,0,[x.id for x in line.tax_id])],
                    'note': line.notes,
                    'account_analytic_id': line.order_id.project_id.id,
                })
                cr.execute('insert into sale_order_line_invoice_rel (order_line_id,invoice_id) values (%d,%d)', (line.id, inv_id))
                self.write(cr, uid, [line.id], {'invoiced':True})
                create_ids.append(inv_id)
        return create_ids

    def button_confirm(self, cr, uid, ids, context={}):
        return self.write(cr, uid, ids, {'state':'confirmed'})

    def button_done(self, cr, uid, ids, context={}):
        wf_service = netsvc.LocalService("workflow")
        res = self.write(cr, uid, ids, {'state':'done'})
        for line in self.browse(cr,uid,ids,context):
            wf_service.trg_write(uid, 'sale.order', line.order_id.id, cr)

        return res

    def uos_change(self, cr, uid, ids, product_uos, product_uos_qty=0, product_id=None):
        product_obj = self.pool.get('product.product')
        if not product_id:
            return {'value': {'product_uom': product_uos,
                'product_uom_qty': product_uos_qty}, 'domain':{}}

        product = product_obj.browse(cr, uid, product_id)
        value = {
            'product_uom' : product.uom_id.id,
        }
        # FIXME must depend on uos/uom of the product and not only of the coeff.
        try:
            value.update({
                'product_uom_qty' : product_uos_qty / product.uos_coeff,
                'th_weight' : product_uos_qty / product.uos_coeff * product.weight
            })
        except ZeroDivisionError:
            pass
        return {'value' : value}

    def copy(self, cr, uid, id, default=None,context={}):
        if not default:
            default = {}
        default.update({'state':'draft', 'move_ids':[], 'invoiced':False, 'invoice_lines':[]})
        return super(sale_order_line, self).copy(cr, uid, id, default, context)

    def product_id_change(self, cr, uid, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False, packaging=False):
        product_uom_obj = self.pool.get('product.uom')
        partner_obj = self.pool.get('res.partner')
        product_obj = self.pool.get('product.product')

        if partner_id:
            lang = partner_obj.browse(cr, uid, partner_id).lang
        context = {'lang': lang, 'partner_id': partner_id}

        if not product:
            return {'value': {'th_weight' : 0, 'product_packaging': False,
                'product_uos_qty': qty}, 'domain': {'product_uom': [],
                    'product_uos': []}}

        if not date_order:
            date_order = time.strftime('%Y-%m-%d')

        result = {}
        product_obj = product_obj.browse(cr, uid, product, context=context)
        if packaging:
            default_uom = product_obj.uom_id and product_obj.uom_id.id
            pack = self.pool.get('product.packaging').browse(cr, uid, packaging, context)
            q = product_uom_obj._compute_qty(cr, uid, uom, pack.qty, default_uom)
            qty = qty - qty % q + q
            result['product_uom_qty'] = qty

        if uom:
            uom2 = product_uom_obj.browse(cr, uid, uom)
            if product_obj.uom_id.category_id.id <> uom2.category_id.id:
                uom = False

        if uos:
            if product_obj.uos_id:
                uos2 = product_uom_obj.browse(cr, uid, uos)
                if product_obj.uos_id.category_id.id <> uos2.category_id.id:
                    uos = False
            else:
                uos = False

        result .update({'type': product_obj.procure_method})
        if product_obj.description_sale:
            result['notes'] = product_obj.description_sale

        if update_tax: #The quantity only have changed
            result['delay'] = (product_obj.sale_delay or 0.0)
            taxes = self.pool.get('account.tax').browse(cr, uid,
                    [x.id for x in product_obj.taxes_id])
            taxep = None
            if partner_id:
                taxep = self.pool.get('res.partner').browse(cr, uid,
                        partner_id).property_account_tax
            if not taxep or not taxep.id:
                result['tax_id'] = [x.id for x in product_obj.taxes_id]
            else:
                res5 = [taxep.id]
                for t in taxes:
                    if not t.tax_group==taxep.tax_group:
                        res5.append(t.id)
                result['tax_id'] = res5

        result['name'] = product_obj.partner_ref

        domain = {}
        if not uom and not uos:
            result['product_uom'] = product_obj.uom_id.id
            if product_obj.uos_id:
                result['product_uos'] = product_obj.uos_id.id
                result['product_uos_qty'] = qty * product_obj.uos_coeff
                uos_category_id = product_obj.uos_id.category_id.id
            else:
                result['product_uos'] = False
                result['product_uos_qty'] = qty
                uos_category_id = False
            result['th_weight'] = qty * product_obj.weight
            domain = {'product_uom':
                        [('category_id', '=', product_obj.uom_id.category_id.id)],
                        'product_uos':
                        [('category_id', '=', uos_category_id)]}
        elif uom: # whether uos is set or not
            default_uom = product_obj.uom_id and product_obj.uom_id.id
            q = product_uom_obj._compute_qty(cr, uid, uom, qty, default_uom)
            if product_obj.uos_id:
                result['product_uos'] = product_obj.uos_id.id
                result['product_uos_qty'] = q * product_obj.uos_coeff
            else:
                result['product_uos'] = False
                result['product_uos_qty'] = q
            result['th_weight'] = q * product_obj.weight
        elif uos: # only happens if uom is False
            result['product_uom'] = product_obj.uom_id and product_obj.uom_id.id
            result['product_uom_qty'] = qty_uos / product_obj.uos_coeff
            result['th_weight'] = result['product_uom_qty'] * product_obj.weight
        # Round the quantity up

        # get unit price
        warning={}
        if not pricelist:
            warning={
                'title':'No Pricelist !',
                'message':
                    'You have to select a pricelist in the sale form !\n'
                    'Please set one before choosing a product.'
                }
        else:
            price = self.pool.get('product.pricelist').price_get(cr, uid, [pricelist],
                    product, qty or 1.0, partner_id, {
                        'uom': uom,
                        'date': date_order,
                        })[pricelist]
            if price is False:
                 warning={
                    'title':'No valid pricelist line found !',
                    'message':
                        "Couldn't find a pricelist line matching this product and quantity.\n"
                        "You have to change either the product, the quantity or the pricelist."
                    }
            else:
                result.update({'price_unit': price})


        return {'value': result, 'domain': domain,'warning':warning}

    def product_uom_change(self, cursor, user, ids, pricelist, product, qty=0,
            uom=False, qty_uos=0, uos=False, name='', partner_id=False,
            lang=False, update_tax=True, date_order=False):
        res = self.product_id_change(cursor, user, ids, pricelist, product,
                qty=0, uom=uom, qty_uos=qty_uos, uos=uos, name=name,
                partner_id=partner_id, lang=lang, update_tax=update_tax,
                date_order=date_order)
        if 'product_uom' in res['value']:
            del res['value']['product_uom']
        if not uom:
            res['value']['price_unit'] = 0.0
        return res

sale_order_line()



_policy_form = '''<?xml version="1.0"?>
<form string="Select Bank Account">
    <field name="picking_policy" colspan="4"/>
</form>'''

_policy_fields = {
    'picking_policy': {'string': 'Packing Policy', 'type': 'selection','selection': [('direct','Direct Delivery'),('one','All at once')],'required': True,}
}
class sale_config_picking_policy(osv.osv_memory):
    _name='sale.config.picking_policy'
    _columns = {
        'name':fields.char('Name', size=64),
        'picking_policy': fields.selection([('direct','Direct Delivery'),('one','All at once')], 'Packing Policy', required=True ),
    }
    _defaults={
        'picking_policy': lambda *a: 'direct',
    }
    def set_default(self, cr, uid, ids, context=None):
        if 'name' in context:
            ir_values_obj = self.pool.get('ir.values')
            ir_values_obj.set(cr,uid,'default',False,'picking_policy',['sale.order'],context['picking_policy'])
        return {
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'ir.module.module.configuration.wizard',
                'type': 'ir.actions.act_window',
                'target':'new',
         }
    def action_cancel(self,cr,uid,ids,conect=None):
        return {
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'ir.module.module.configuration.wizard',
                'type': 'ir.actions.act_window',
                'target':'new',
         }
sale_config_picking_policy()


