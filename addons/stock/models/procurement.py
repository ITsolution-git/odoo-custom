# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.tools.misc import split_every
from psycopg2 import OperationalError

from odoo import api, fields, models, registry, _
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare, \
    float_round, pycompat

import logging

_logger = logging.getLogger(__name__)

class ProcurementGroup(models.Model):
    _inherit = 'procurement.group'

    partner_id = fields.Many2one('res.partner', 'Partner')


class ProcurementRule(models.Model):
    """ Pull rules """
    _inherit = 'procurement.rule'

    location_id = fields.Many2one('stock.location', 'Procurement Location')
    location_src_id = fields.Many2one('stock.location', 'Source Location', help="Source location is action=move")
    route_id = fields.Many2one('stock.location.route', 'Route', required=True, ondelete='cascade')
    procure_method = fields.Selection([
        ('make_to_stock', 'Take From Stock'),
        ('make_to_order', 'Create Procurement')], string='Move Supply Method',
        default='make_to_stock', required=True,
        help="""Determines the procurement method of the stock move that will be generated: whether it will need to 'take from the available stock' in its source location or needs to ignore its stock and create a procurement over there.""")
    route_sequence = fields.Integer('Route Sequence', related='route_id.sequence', store=True)
    picking_type_id = fields.Many2one(
        'stock.picking.type', 'Operation Type',
        required=True,
        help="Operation Type determines the way the picking should be shown in the view, reports, ...")
    delay = fields.Integer('Number of Days', default=0)
    partner_address_id = fields.Many2one('res.partner', 'Partner Address')
    propagate = fields.Boolean(
        'Propagate cancel and split', default=True,
        help='If checked, when the previous move of the move (which was generated by a next procurement) is cancelled or split, the move generated by this move will too')
    warehouse_id = fields.Many2one('stock.warehouse', 'Served Warehouse', help='The warehouse this rule is for')
    propagate_warehouse_id = fields.Many2one(
        'stock.warehouse', 'Warehouse to Propagate',
        help="The warehouse to propagate on the created move/procurement, which can be different of the warehouse this rule is for (e.g for resupplying rules from another warehouse)")

    @api.model
    def _get_action(self):
        result = super(ProcurementRule, self)._get_action()
        return result + [('move', _('Move From Another Location'))]


class ProcurementOrder(models.Model):
    _inherit = "procurement.order"

    location_id = fields.Many2one('stock.location', 'Procurement Location')  # not required because task may create procurements that aren't linked to a location with sale_service
    partner_dest_id = fields.Many2one('res.partner', 'Customer Address', help="In case of dropshipping, we need to know the destination address more precisely")
    move_ids = fields.One2many('stock.move', 'procurement_id', 'Moves', help="Moves created by the procurement")
    move_dest_id = fields.Many2one('stock.move', 'Destination Move', help="Move which caused (created) the procurement")
    route_ids = fields.Many2many(
        'stock.location.route', 'stock_location_route_procurement', 'procurement_id', 'route_id', 'Preferred Routes',
        help="Preferred route to be followed by the procurement order. Usually copied from the generating document (SO) but could be set up manually.")
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', help="Warehouse to consider for the route selection")
    orderpoint_id = fields.Many2one('stock.warehouse.orderpoint', 'Minimum Stock Rule')

    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        if self.warehouse_id:
            self.location_id = self.warehouse_id.lot_stock_id.id

    @api.multi
    def propagate_cancels(self):
        # set the context for the propagation of the procurement cancellation
        # TDE FIXME: was in cancel, moved here for consistency
        cancel_moves = self.with_context(cancel_procurement=True).filtered(lambda order: order.rule_id.action == 'move').mapped('move_ids')
        if cancel_moves:
            cancel_moves.action_cancel()
        return self.search([('move_dest_id', 'in', cancel_moves.filtered(lambda move: move.propagate).ids)])

    @api.multi
    def cancel(self):
        propagated_procurements = self.filtered(lambda order: order.state != 'done').propagate_cancels()
        if propagated_procurements:
            propagated_procurements.cancel()
        return super(ProcurementOrder, self).cancel()

    @api.multi
    def do_view_pickings(self):
        """ Return an action to display the pickings belonging to the same
        procurement group of given ids. """
        action = self.env.ref('stock.do_view_pickings').read()[0]
        action['domain'] = [('group_id', 'in', self.mapped('group_id').ids)]
        return action

    @api.multi
    @api.returns('procurement.rule', lambda value: value.id if value else False)
    def _find_suitable_rule(self):
        rule = super(ProcurementOrder, self)._find_suitable_rule()
        if not rule:
            # a rule defined on 'Stock' is suitable for a procurement in 'Stock\Bin A'
            all_parent_location_ids = self._find_parent_locations()
            rule = self._search_suitable_rule([('location_id', 'in', all_parent_location_ids.ids)])
        return rule

    def _find_parent_locations(self):
        parent_locations = self.env['stock.location']
        location = self.location_id
        while location:
            parent_locations |= location
            location = location.location_id
        return parent_locations

    def _search_suitable_rule(self, domain):
        """ First find a rule among the ones defined on the procurement order
        group; then try on the routes defined for the product; finally fallback
        on the default behavior """
        if self.warehouse_id:
            domain = expression.AND([['|', ('warehouse_id', '=', self.warehouse_id.id), ('warehouse_id', '=', False)], domain])
        Pull = self.env['procurement.rule']
        res = self.env['procurement.rule']
        if self.route_ids:
            res = Pull.search(expression.AND([[('route_id', 'in', self.route_ids.ids)], domain]), order='route_sequence, sequence', limit=1)
        if not res:
            product_routes = self.product_id.route_ids | self.product_id.categ_id.total_route_ids
            if product_routes:
                res = Pull.search(expression.AND([[('route_id', 'in', product_routes.ids)], domain]), order='route_sequence, sequence', limit=1)
        if not res:
            warehouse_routes = self.warehouse_id.route_ids
            if warehouse_routes:
                res = Pull.search(expression.AND([[('route_id', 'in', warehouse_routes.ids)], domain]), order='route_sequence, sequence', limit=1)
        return res

    def _get_stock_move_values(self):
        ''' Returns a dictionary of values that will be used to create a stock move from a procurement.
        This function assumes that the given procurement has a rule (action == 'move') set on it.

        :param procurement: browse record
        :rtype: dictionary
        '''
        group_id = False
        if self.rule_id.group_propagation_option == 'propagate':
            group_id = self.group_id.id
        elif self.rule_id.group_propagation_option == 'fixed':
            group_id = self.rule_id.group_id.id
        date_expected = (datetime.strptime(self.date_planned, DEFAULT_SERVER_DATETIME_FORMAT) - relativedelta(days=self.rule_id.delay or 0)).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        # it is possible that we've already got some move done, so check for the done qty and create
        # a new move with the correct qty
        qty_done = sum(self.move_ids.filtered(lambda move: move.state == 'done').mapped('product_uom_qty'))
        qty_left = max(self.product_qty - qty_done, 0)
        return {
            'name': self.name,
            'company_id': self.rule_id.company_id.id or self.rule_id.location_src_id.company_id.id or self.rule_id.location_id.company_id.id or self.company_id.id,
            'product_id': self.product_id.id,
            'product_uom': self.product_uom.id,
            'product_uom_qty': qty_left,
            'partner_id': self.rule_id.partner_address_id.id or (self.group_id and self.group_id.partner_id.id) or False,
            'location_id': self.rule_id.location_src_id.id,
            'location_dest_id': self.location_id.id,
            'move_dest_id': self.move_dest_id and self.move_dest_id.id or False,
            'procurement_id': self.id,
            'rule_id': self.rule_id.id,
            'procure_method': self.rule_id.procure_method,
            'origin': self.origin,
            'picking_type_id': self.rule_id.picking_type_id.id,
            'group_id': group_id,
            'route_ids': [(4, route.id) for route in self.route_ids],
            'warehouse_id': self.rule_id.propagate_warehouse_id.id or self.rule_id.warehouse_id.id,
            'date': date_expected,
            'date_expected': date_expected,
            'propagate': self.rule_id.propagate,
            'priority': self.priority,
        }

    @api.multi
    def _run(self):
        if self.rule_id.action == 'move':
            if not self.rule_id.location_src_id:
                self.message_post(body=_('No source location defined!'))
                return False
            # create the move as SUPERUSER because the current user may not have the rights to do it (mto product launched by a sale for example)
            self.env['stock.move'].sudo().create(self._get_stock_move_values())
            return True
        return super(ProcurementOrder, self)._run()

    @api.multi
    def run(self, autocommit=False):
        # TDE CLEANME: unused context key procurement_auto_defer remove
        new_self = self.filtered(lambda order: order.state not in ['running', 'done', 'cancel'])
        res = super(ProcurementOrder, new_self).run(autocommit=autocommit)

        # after all the procurements are run, check if some created a draft stock move that needs to be confirmed
        # (we do that in batch because it fasts the picking assignation and the picking state computation)
        new_self.filtered(lambda order: order.state == 'running' and order.rule_id.action == 'move').mapped('move_ids').filtered(lambda move: move.state == 'draft').action_confirm()

        # TDE FIXME: action_confirm in stock_move already call run() ... necessary ??
        # If procurements created other procurements, run the created in batch
        new_procurements = self.search([('move_dest_id.procurement_id', 'in', new_self.ids)], order='id')
        if new_procurements:
            res = new_procurements.run(autocommit=autocommit)
        return res

    @api.multi
    def _check(self):
        """ Checking rules of type 'move': satisfied only if all related moves
        are done/cancel and if the requested quantity is moved. """
        if self.rule_id.action == 'move':
            # In case Phantom BoM splits only into procurements
            if not self.move_ids:
                return True
            move_all_done_or_cancel = all(move.state in ['done', 'cancel'] for move in self.move_ids)
            move_all_cancel = all(move.state == 'cancel' for move in self.move_ids)
            if not move_all_done_or_cancel:
                return False
            elif move_all_done_or_cancel and not move_all_cancel:
                return True
            else:
                self.message_post(body=_('All stock moves have been cancelled for this procurement.'))
                # TDE FIXME: strange that a check method actually modified the procurement...
                self.write({'state': 'cancel'})
                return False
        return super(ProcurementOrder, self)._check()

    @api.model
    def run_scheduler(self, use_new_cursor=False, company_id=False):
        ''' Call the scheduler in order to check the running procurements (super method), to check the minimum stock rules
        and the availability of moves. This function is intended to be run for all the companies at the same time, so
        we run functions as SUPERUSER to avoid intercompanies and access rights issues. '''
        super(ProcurementOrder, self).run_scheduler(use_new_cursor=use_new_cursor, company_id=company_id)
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME

            # Minimum stock rules
            self.sudo()._procure_orderpoint_confirm(use_new_cursor=use_new_cursor, company_id=company_id)

            # Search all confirmed stock_moves and try to assign them
            confirmed_moves = self.env['stock.move'].search([('state', '=', 'confirmed')], limit=None, order='priority desc, date_expected asc')
            for moves_chunk in split_every(100, confirmed_moves.ids):
                # TDE CLEANME: muf muf
                self.env['stock.move'].browse(moves_chunk).action_assign()
                if use_new_cursor:
                    self._cr.commit()
            if use_new_cursor:
                self._cr.commit()
        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception:
                    pass
        return {}

    @api.model
    def _procurement_from_orderpoint_get_order(self):
        return 'location_id'

    @api.model
    def _procurement_from_orderpoint_get_grouping_key(self, orderpoint_ids):
        orderpoints = self.env['stock.warehouse.orderpoint'].browse(orderpoint_ids)
        return orderpoints.location_id.id

    @api.model
    def _procurement_from_orderpoint_get_groups(self, orderpoint_ids):
        """ Make groups for a given orderpoint; by default schedule all operations in one without date """
        return [{'to_date': False, 'procurement_values': dict()}]

    @api.model
    def _procurement_from_orderpoint_post_process(self, orderpoint_ids):
        return True

    def _get_orderpoint_domain(self, company_id=False):
        domain = [('company_id', '=', company_id)] if company_id else []
        domain += [('product_id.active', '=', True)]
        return domain

    @api.model
    def _procure_orderpoint_confirm(self, use_new_cursor=False, company_id=False):
        """ Create procurements based on orderpoints.
        :param bool use_new_cursor: if set, use a dedicated cursor and auto-commit after processing
            1000 orderpoints.
            This is appropriate for batch jobs only.
        """

        OrderPoint = self.env['stock.warehouse.orderpoint']
        domain = self._get_orderpoint_domain(company_id=company_id)
        orderpoints_noprefetch = OrderPoint.with_context(prefetch_fields=False).search(domain,
            order=self._procurement_from_orderpoint_get_order()).ids
        while orderpoints_noprefetch:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))
            OrderPoint = self.env['stock.warehouse.orderpoint']
            Procurement = self.env['procurement.order']
            ProcurementAutorundefer = Procurement.with_context(procurement_autorun_defer=True)
            procurement_list = []

            orderpoints = OrderPoint.browse(orderpoints_noprefetch[:1000])
            orderpoints_noprefetch = orderpoints_noprefetch[1000:]

            # Calculate groups that can be executed together
            location_data = defaultdict(lambda: dict(products=self.env['product.product'], orderpoints=self.env['stock.warehouse.orderpoint'], groups=list()))
            for orderpoint in orderpoints:
                key = self._procurement_from_orderpoint_get_grouping_key([orderpoint.id])
                location_data[key]['products'] += orderpoint.product_id
                location_data[key]['orderpoints'] += orderpoint
                location_data[key]['groups'] = self._procurement_from_orderpoint_get_groups([orderpoint.id])

            for location_id, location_data in pycompat.items(location_data):
                location_orderpoints = location_data['orderpoints']
                product_context = dict(self._context, location=location_orderpoints[0].location_id.id)
                substract_quantity = location_orderpoints.subtract_procurements_from_orderpoints()

                for group in location_data['groups']:
                    if group['to_date']:
                        product_context['to_date'] = group['to_date'].strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                    product_quantity = location_data['products'].with_context(product_context)._product_available()
                    for orderpoint in location_orderpoints:
                        try:
                            op_product_virtual = product_quantity[orderpoint.product_id.id]['virtual_available']
                            if op_product_virtual is None:
                                continue
                            if float_compare(op_product_virtual, orderpoint.product_min_qty, precision_rounding=orderpoint.product_uom.rounding) <= 0:
                                qty = max(orderpoint.product_min_qty, orderpoint.product_max_qty) - op_product_virtual
                                remainder = orderpoint.qty_multiple > 0 and qty % orderpoint.qty_multiple or 0.0

                                if float_compare(remainder, 0.0, precision_rounding=orderpoint.product_uom.rounding) > 0:
                                    qty += orderpoint.qty_multiple - remainder

                                if float_compare(qty, 0.0, precision_rounding=orderpoint.product_uom.rounding) < 0:
                                    continue

                                qty -= substract_quantity[orderpoint.id]
                                qty_rounded = float_round(qty, precision_rounding=orderpoint.product_uom.rounding)
                                if qty_rounded > 0:
                                    new_procurement = ProcurementAutorundefer.create(
                                        orderpoint._prepare_procurement_values(qty_rounded, **group['procurement_values']))
                                    procurement_list.append(new_procurement)
                                    new_procurement.message_post_with_view('mail.message_origin_link',
                                        values={'self': new_procurement, 'origin': orderpoint},
                                        subtype_id=self.env.ref('mail.mt_note').id)
                                    self._procurement_from_orderpoint_post_process([orderpoint.id])
                                if use_new_cursor:
                                    cr.commit()

                        except OperationalError:
                            if use_new_cursor:
                                orderpoints_noprefetch += [orderpoint.id]
                                cr.rollback()
                                continue
                            else:
                                raise

            try:
                # TDE CLEANME: use record set ?
                procurement_list.reverse()
                procurements = self.env['procurement.order']
                for p in procurement_list:
                    procurements += p
                procurements.run()
                if use_new_cursor:
                    cr.commit()
            except OperationalError:
                if use_new_cursor:
                    cr.rollback()
                    continue
                else:
                    raise

            if use_new_cursor:
                cr.commit()
                cr.close()

        return {}
