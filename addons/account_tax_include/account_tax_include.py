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

from osv import fields, osv

class account_invoice(osv.osv):
    _inherit = "account.invoice"
    _columns = {
        'price_type': fields.selection([('tax_included','Tax included'),
                                        ('tax_excluded','Tax excluded')],
                                        'Price method', required=True, readonly=True,
                                        states={'draft': [('readonly', False)]}),
    }
    _defaults = {
        'price_type': 'tax_excluded',
    }

    def refund(self, cr, uid, ids, date=None, period_id=None, description=None):
        map_old_new = {}
        refund_ids = []
        for old_inv_id in ids:
            new_id = super(account_invoice,self).refund(cr, uid, ids, date=date, period_id=period_id, description=description)
            refund_ids += new_id
            map_old_new[old_inv_id] = new_id[0]

        for old_inv_id in map_old_new.keys():
            old_inv_record = self.read(cr, uid, [old_inv_id], ['price_type'])[0]['price_type']
            self.write(cr, uid, [map_old_new[old_inv_id]], {'price_type' : old_inv_record})
        return refund_ids

account_invoice()

class account_invoice_line(osv.osv):
    _inherit = "account.invoice.line"

    def _amount_line2(self, cr, uid, ids, name, args, context=None):
        """
        Return the subtotal excluding taxes with respect to price_type.
        """
        res = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        dec_obj = self.pool.get('decimal.precision')
        for line in self.browse(cr, uid, ids):
            cur = line.invoice_id and line.invoice_id.currency_id or False
            res_init = super(account_invoice_line, self)._amount_line(cr, uid, [line.id], name, args, context)
            res[line.id] = {
                'price_subtotal': 0.0,
                'price_subtotal_incl': 0.0,
                'data': []
            }
            if not line.quantity:
                continue
            if line.invoice_id:
                product_taxes = []
                if line.product_id:
                    if line.invoice_id.type in ('out_invoice', 'out_refund'):
                        product_taxes = filter(lambda x: x.price_include, line.product_id.taxes_id)
                    else:
                        product_taxes = filter(lambda x: x.price_include, line.product_id.supplier_taxes_id)

                if ((set(product_taxes) == set(line.invoice_line_tax_id)) or not product_taxes) and (line.invoice_id.price_type == 'tax_included'):
                    res[line.id]['price_subtotal_incl'] = cur and cur_obj.round(cr, uid, cur, res_init[line.id]) or res_init[line.id]
                else:
                    res[line.id]['price_subtotal'] = cur and cur_obj.round(cr, uid, cur, res_init[line.id]) or res_init[line.id]
                    for tax in tax_obj.compute_inv(cr, uid, product_taxes, res_init[line.id]/line.quantity, line.quantity):
                        res[line.id]['price_subtotal'] = res[line.id]['price_subtotal'] - round(tax['amount'], dec_obj.precision_get(cr, uid, 'Account'))
            else:
                res[line.id]['price_subtotal'] = cur and cur_obj.round(cr, uid, cur, res_init[line.id]) or res_init[line.id]

            if res[line.id]['price_subtotal']:
                res[line.id]['price_subtotal_incl'] = res[line.id]['price_subtotal']
                for tax in tax_obj.compute(cr, uid, line.invoice_line_tax_id, res[line.id]['price_subtotal']/line.quantity, line.quantity):
                    res[line.id]['price_subtotal_incl'] = res[line.id]['price_subtotal_incl'] + tax['amount']
                    res[line.id]['data'].append(tax)
            else:
                res[line.id]['price_subtotal'] = res[line.id]['price_subtotal_incl']
                for tax in tax_obj.compute_inv(cr, uid, line.invoice_line_tax_id, res[line.id]['price_subtotal_incl']/line.quantity, line.quantity):
                    res[line.id]['price_subtotal'] = res[line.id]['price_subtotal'] - tax['amount']
                    res[line.id]['data'].append(tax)

            res[line.id]['price_subtotal']= round(res[line.id]['price_subtotal'], dec_obj.precision_get(cr, uid, 'Account'))
            res[line.id]['price_subtotal_incl']= round(res[line.id]['price_subtotal_incl'], dec_obj.precision_get(cr, uid, 'Account'))
        return res

    def _price_unit_default(self, cr, uid, context=None):
        if context is None:
            context = {}
        if 'check_total' in context:
            t = context['check_total']
            if context.get('price_type', False) == 'tax_included':
                for l in context.get('invoice_line', {}):
                    if len(l) >= 3 and l[2]:
                        p = l[2].get('price_unit', 0) * (1-l[2].get('discount', 0)/100.0)
                        t = t - (p * l[2].get('quantity'))
                return t
            return super(account_invoice_line, self)._price_unit_default(cr, uid, context)
        return 0

    def _get_invoice(self, cr, uid, ids, context=None):
        result = {}
        for inv in self.pool.get('account.invoice').browse(cr, uid, ids, context=context):
            for line in inv.invoice_line:
                result[line.id] = True
        return result.keys()

    _columns = {
        'price_subtotal': fields.function(_amount_line2, method=True, string='Subtotal w/o tax', multi='amount',
            store={'account.invoice':(_get_invoice,['price_type'], 10), 'account.invoice.line': (lambda self, cr, uid, ids, c={}: ids, None,10)}),
        'price_subtotal_incl': fields.function(_amount_line2, method=True, string='Subtotal', multi='amount',
            store={'account.invoice':(_get_invoice,['price_type'], 10), 'account.invoice.line': (lambda self, cr, uid, ids, c={}: ids, None,10)}),
                }

    _defaults = {
        'price_unit': _price_unit_default,
                }

    def move_line_get_item(self, cr, uid, line, context=None):
        return {
                'type':'src',
                'name':line.name,
                'price_unit':(line.quantity) and (line.price_subtotal / line.quantity) or line.price_subtotal,
                'quantity':line.quantity,
                'price':line.price_subtotal,
                'account_id':line.account_id.id,
                'product_id': line.product_id.id,
                'uos_id':line.uos_id.id,
                'account_analytic_id':line.account_analytic_id.id,
                }

    def product_id_change_unit_price_inv(self, cr, uid, tax_id, price_unit, qty, address_invoice_id, product, partner_id, context=None):
        if context is None:
            context = {}
        # if the tax is already included, just return the value without calculations
        if context.get('price_type', False) == 'tax_included':
            return {'price_unit': price_unit,'invoice_line_tax_id': tax_id}
        else:
            return super(account_invoice_line, self).product_id_change_unit_price_inv(cr, uid, tax_id, price_unit, qty, address_invoice_id, product, partner_id, context=context)

    def product_id_change(self, cr, uid, ids, product, uom, qty=0, name='', type='out_invoice', partner_id=False, fposition_id=False, price_unit=False, address_invoice_id=False, currency_id=False, context=None):
        # note: will call product_id_change_unit_price_inv with context...

        # Temporary trap, for bad context that came from koo:
        # if isinstance(context, str):
        #       print "str context:", context

        ctx = (context and context.copy()) or {}
        ctx.update({'price_type': ctx.get('price_type', 'tax_excluded')})
        return super(account_invoice_line, self).product_id_change(cr, uid, ids, product, uom, qty, name, type, partner_id, fposition_id, price_unit, address_invoice_id, currency_id=currency_id, context=ctx)

account_invoice_line()

class account_invoice_tax(osv.osv):
    _inherit = "account.invoice.tax"

    def compute(self, cr, uid, invoice_id, context=None):
        tax_grouped = {}
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        line_obj = self.pool.get('account.invoice.line')

        inv = self.pool.get('account.invoice').browse(cr, uid, invoice_id)
        line_ids = map(lambda x: x.id, inv.invoice_line)

        cur = inv.currency_id
        company_currency = inv.company_id.currency_id.id

        for line in inv.invoice_line:
            data = line_obj._amount_line2(cr, uid, [line.id], [], [], context)[line.id]
            for tax in data['data']:
                val={}
                val['invoice_id'] = inv.id
                val['name'] = tax['name']
                val['amount'] = tax['amount']
                val['manual'] = False
                val['sequence'] = tax['sequence']
                val['base'] = tax['price_unit'] * line['quantity']

                if inv.type in ('out_invoice','in_invoice'):
                    val['base_code_id'] = tax['base_code_id']
                    val['tax_code_id'] = tax['tax_code_id']
                    val['base_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['base'] * tax['base_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['tax_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['amount'] * tax['tax_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['account_id'] = tax['account_collected_id'] or line.account_id.id
                else:
                    val['base_code_id'] = tax['ref_base_code_id']
                    val['tax_code_id'] = tax['ref_tax_code_id']
                    val['base_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['base'] * tax['ref_base_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['tax_amount'] = cur_obj.compute(cr, uid, inv.currency_id.id, company_currency, val['amount'] * tax['ref_tax_sign'], context={'date': inv.date_invoice or time.strftime('%Y-%m-%d')}, round=False)
                    val['account_id'] = tax['account_paid_id'] or line.account_id.id

                key = (val['tax_code_id'], val['base_code_id'], val['account_id'])
                if not key in tax_grouped:
                    tax_grouped[key] = val
                else:
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base'] += val['base']
                    tax_grouped[key]['base_amount'] += val['base_amount']
                    tax_grouped[key]['tax_amount'] += val['tax_amount']

        for t in tax_grouped.values():
            t['amount'] = cur_obj.round(cr, uid, cur, t['amount'])
            t['base_amount'] = cur_obj.round(cr, uid, cur, t['base_amount'])
            t['tax_amount'] = cur_obj.round(cr, uid, cur, t['tax_amount'])

        return tax_grouped

account_invoice_tax()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: