# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp import api, fields, models


class StockLocationRoute(models.Model):
    _inherit = "stock.location.route"

    sale_selectable = fields.Boolean(string="Selectable on Sales Order Line")

class StockMove(models.Model):
    _inherit = "stock.move"

    to_refund_so = fields.Boolean(string="To Refund in SO", default=False,
        help='Trigger a decrease of the delivered quantity in the associated Sale Order')

    @api.multi
    def action_done(self):
        result = super(StockMove, self).action_done()

        # Update delivered quantities on sale order lines
        todo = self.env['sale.order.line']
        for move in self:
            if (move.procurement_id.sale_line_id) and (move.product_id.expense_policy=='no'):
                todo |= move.procurement_id.sale_line_id
        for line in todo:
            line.qty_delivered = line._get_delivered_qty()
        return result

    @api.multi
    def assign_picking(self):
        result = super(StockMove, self).assign_picking()
        for move in self:
            if move.picking_id and move.picking_id.group_id:
                picking = move.picking_id
                order = self.env['sale.order'].search([('procurement_group_id', '=', picking.group_id.id)])
                picking.message_post_with_view('mail.message_origin_link',
                    values={'self': picking, 'origin': order},
                    subtype_id=self.env.ref('mail.mt_note').id)
        return result

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.depends('move_lines')
    def _compute_sale_id(self):
        for picking in self:
            sale_order = False
            for move in picking.move_lines:
                if move.procurement_id.sale_line_id:
                    sale_order = move.procurement_id.sale_line_id.order_id
                    break
            picking.sale_id = sale_order.id if sale_order else False

    def _search_sale_id(self, operator, value):
        moves = self.env['stock.move'].search(
            [('picking_id', '!=', False), ('procurement_id.sale_line_id.order_id', operator, value)]
        )
        return [('id', 'in', moves.mapped('picking_id').ids)]

    sale_id = fields.Many2one(comodel_name='sale.order', string="Sale Order",
                              compute='_compute_sale_id', search='_search_sale_id')

    @api.multi
    def _create_backorder(self, backorder_moves=[]):
        res = super(StockPicking, self)._create_backorder(backorder_moves)
        for picking in self.filtered(lambda pick: pick.picking_type_id.code == 'outgoing'):
            backorder = picking.search([('backorder_id', '=', picking.id)])
            order = self.env['sale.order'].search([('procurement_group_id', '=', backorder.group_id.id)])
            backorder.message_post_with_view('mail.message_origin_link',
                values={'self': backorder, 'origin': order},
                subtype_id=self.env.ref('mail.mt_note').id)
        return res

class StockReturnPicking(models.TransientModel):
    _inherit = "stock.return.picking"

    @api.multi
    def _create_returns(self):
        new_picking_id, pick_type_id = super(StockReturnPicking, self)._create_returns()
        new_picking = self.env['stock.picking'].browse([new_picking_id])
        for move in new_picking.move_lines:
            return_picking_line = self.product_return_moves.filtered(lambda r: r.move_id == move.origin_returned_move_id)
            if return_picking_line and return_picking_line.to_refund_so:
                move.to_refund_so = True

        return new_picking_id, pick_type_id


class StockReturnPickingLine(models.TransientModel):
    _inherit = "stock.return.picking.line"

    to_refund_so = fields.Boolean(string="To Refund", help='Trigger a decrease of the delivered quantity in the associated Sale Order')