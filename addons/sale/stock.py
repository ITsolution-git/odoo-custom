# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2008 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import osv, fields

class stock_move(osv.osv):
    _inherit = 'stock.move'
    _columns = {
        'sale_line_id': fields.many2one('sale.order.line', 'Sale Order Line', ondelete='set null', select=True, readonly=True),
    }
    _defaults = {
        'sale_line_id': lambda *a:False
    }
stock_move()

class stock_picking(osv.osv):
    _inherit = 'stock.picking'
    _columns = {
        'sale_id': fields.many2one('sale.order', 'Sale Order', ondelete='set null', select=True, readonly=True),
    }
    _defaults = {
        'sale_id': lambda *a: False
    }

    def get_currency_id(self, cursor, user, picking):
        if picking.sale_id:
            return picking.sale_id.pricelist_id.currency_id.id
        return False

    def _get_payment_term(self, cursor, user, picking):
        res = {}
        if picking.sale_id and picking.sale_id.payment_term:
            return picking.sale_id.payment_term.id
        return super(stock_picking, self)._get_payment_term(cursor,
                user, picking)

    def _get_address_invoice(self, cursor, user, picking):
        res = {}
        if picking.sale_id:
            res['contact'] = picking.sale_id.partner_order_id.id
            res['invoice'] = picking.sale_id.partner_invoice_id.id
            return res
        return super(stock_picking, self)._get_address_invoice(cursor,
                user, picking)

    def _get_comment_invoice(self, cursor, user, picking):
        if picking.sale_id and picking.sale_id.note:
            if picking.note:
                return picking.note + '\n' + picking.sale_id.note
            else:
                return picking.sale_id.note
        return super(stock_picking, self)._get_comment_invoice(cursor, user,
                picking)

    def _get_price_unit_invoice(self, cursor, user, move_line, type):
        if move_line.sale_line_id:
            return move_line.sale_line_id.price_unit
        return super(stock_picking, self)._get_price_unit_invoice(cursor,
                user, move_line, type)

    def _get_discount_invoice(self, cursor, user, move_line):
        if move_line.sale_line_id:
            return move_line.sale_line_id.discount
        return super(stock_picking, self)._get_discount_invoice(cursor, user,
                move_line)

    def _get_taxes_invoice(self, cursor, user, move_line, type):
        if move_line.sale_line_id:
            return [x.id for x in move_line.sale_line_id.tax_id]
        return super(stock_picking, self)._get_taxes_invoice(cursor, user,
                move_line, type)

    def _get_account_analytic_invoice(self, cursor, user, picking, move_line):
        if picking.sale_id:
            return picking.sale_id.project_id.id
        return super(stock_picking, self)._get_account_analytic_invoice(cursor,
                user, picking, move_line)

    def _invoice_line_hook(self, cursor, user, move_line, invoice_line_id):
        sale_line_obj = self.pool.get('sale.order.line')
        if move_line.sale_line_id:
            sale_line_obj.write(cursor, user, [move_line.sale_line_id.id], {'invoiced':True,
                'invoice_lines': [(4, invoice_line_id)],
                })
        return super(stock_picking, self)._invoice_line_hook(cursor, user,
                move_line, invoice_line_id)

    def _invoice_hook(self, cursor, user, picking, invoice_id):
        sale_obj = self.pool.get('sale.order')
        if picking.sale_id:
            sale_obj.write(cursor, user, [picking.sale_id.id], {
                'invoice_ids': [(4, invoice_id)],
                })
        return super(stock_picking, self)._invoice_hook(cursor, user,
                picking, invoice_id)

    def action_invoice_create(self, cursor, user, ids, journal_id=False,
            group=False, type='out_invoice', context=None):
        invoice_obj = self.pool.get('account.invoice')
        picking_obj = self.pool.get('stock.picking')
        invoice_line_obj = self.pool.get('account.invoice.line')

        result = super(stock_picking, self).action_invoice_create(cursor, user,
                ids, journal_id=journal_id, group=group, type=type,
                context=context)

        picking_ids = result.keys()
        invoice_ids = result.values()

        invoices = {}
        for invoice in invoice_obj.browse(cursor, user, invoice_ids,
                context=context):
            invoices[invoice.id] = invoice

        for picking in picking_obj.browse(cursor, user, picking_ids,
                context=context):

            if not picking.sale_id:
                continue
            sale_lines = picking.sale_id.order_line
            for sale_line in sale_lines:
                if sale_line.product_id.type == 'service' and sale_line.invoiced == False:
                    if group:
                        name = picking.name + '-' + sale_line.name
                    else:
                        name = sale_line.name
                    if type in ('out_invoice', 'out_refund'):
                        account_id = sale_line.product_id.product_tmpl_id.\
                                property_account_income.id
                        if not account_id:
                            account_id = sale_line.product_id.categ_id.\
                                    property_account_income_categ.id
                    else:
                        account_id = sale_line.product_id.product_tmpl_id.\
                                property_account_expense.id
                        if not account_id:
                            account_id = sale_line.product_id.categ_id.\
                                    property_account_expense_categ.id
                    price_unit = sale_line.price_unit
                    discount = sale_line.discount
                    tax_ids = sale_line.tax_id

                    account_analytic_id = self._get_account_analytic_invoice(cursor,
                            user, picking, sale_line)

                    account_id = self.pool.get('account.fiscal.position').map_account(cursor, user, picking.sale_id.partner_id, account_id)
                    invoice = invoices[result[picking.id]]
                    invoice_line_id = invoice_line_obj.create(cursor, user, {
                        'name': name,
                        'invoice_id': invoice.id,
                        'uos_id': sale_line.product_uos.id or sale_line.product_uom.id,
                        'product_id': sale_line.product_id.id,
                        'account_id': account_id,
                        'price_unit': price_unit,
                        'discount': discount,
                        'quantity': sale_line.product_uos_qty,
                        'invoice_line_tax_id': [(6, 0, tax_ids)],
                        'account_analytic_id': account_analytic_id,
                        }, context=context)
                    self.pool.get('sale.order.line').write(cursor, user, [sale_line.id], {'invoiced':True,
                        'invoice_lines': [(6, 0, [invoice_line_id])],
                        })

        return result


stock_picking()



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

