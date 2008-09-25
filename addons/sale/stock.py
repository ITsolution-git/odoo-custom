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
                'invoice_lines': [(6, 0, [invoice_line_id])],
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

stock_picking()



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

