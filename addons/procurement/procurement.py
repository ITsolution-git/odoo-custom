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

from datetime import datetime
from dateutil.relativedelta import relativedelta

from openerp.osv import fields, osv
import openerp.addons.decimal_precision as dp
from openerp.tools.translate import _
import openerp

class procurement_group(osv.osv):
    '''
    The procurement requirement class is used to group products together
    when computing procurements. (tasks, physical products, ...)

    The goal is that when you have one sale order of several products
    and the products are pulled from the same or several location(s), to keep
    having the moves grouped into pickings that represent the sale order.

    Used in: sales order (to group delivery order lines like the so), pull/push
    rules (to pack like the delivery order), on orderpoints (e.g. for wave picking
    all the similar products together).

    Grouping is made only if the source and the destination is the same.
    Suppose you have 4 lines on a picking from Output where 2 lines will need
    to come from Input (crossdock) and 2 lines coming from Stock -> Output As
    the four procurement orders will have the same group ids from the SO, the
    move from input will have a stock.picking with 2 grouped lines and the move
    from stock will have 2 grouped lines also.

    The name is usually the name of the original document (sale order) or a
    sequence computed if created manually.
    '''
    _name = 'procurement.group'
    _description = 'Procurement Requisition'
    _order = "id desc"
    _columns = {
        'name': fields.char('Reference', required=True), 
        'move_type': fields.selection([
            ('direct', 'Partial'), ('one', 'All at once')],
            'Delivery Method', required=True),
        'partner_id': fields.many2one('res.partner', string = 'Partner'), #Sale should pass it here 
        'procurement_ids': fields.one2many('procurement.order', 'group_id', 'Procurements'), 
    }
    _defaults = {
        'name': lambda self, cr, uid, c: self.pool.get('ir.sequence').get(cr, uid, 'procurement.group') or '',
        'move_type': lambda self, cr, uid, c: 'one'
    }

class procurement_rule(osv.osv):
    '''
    A rule describe what a procurement should do; produce, buy, move, ...
    '''
    _name = 'procurement.rule'
    _description = "Procurement Rule"
    _order = "name"

    def _get_action(self, cr, uid, context=None):
        return []

    _columns = {
        'name': fields.char('Name', required=True,
            help="This field will fill the packing origin and the name of its moves"),
        'group_propagation_option': fields.selection([('none', 'Leave Empty'), ('propagate', 'Propagate'), ('fixed', 'Fixed')], string="Propagation of Procurement Group"),
        'group_id': fields.many2one('procurement.group', 'Fixed Procurement Group'),
        'action': fields.selection(selection=lambda s, cr, uid, context=None: s._get_action(cr, uid, context=context),
            string='Action', required=True),
        'sequence': fields.integer('Sequence'),
        'company_id': fields.many2one('res.company', 'Company'),
    }

    _defaults = {
        'group_propagation_option': 'propagate',
        'sequence': 20,
    }


class procurement_order(osv.osv):
    """
    Procurement Orders
    """
    _name = "procurement.order"
    _description = "Procurement"
    _order = 'priority desc, date_planned, id asc'
    _inherit = ['mail.thread']
    _log_create = False
    _columns = {
        'name': fields.text('Description', required=True),

        'origin': fields.char('Source Document', size=64,
            help="Reference of the document that created this Procurement.\n"
            "This is automatically completed by OpenERP."),
        'company_id': fields.many2one('res.company', 'Company', required=True),

        # These two fields are used for shceduling
        'priority': fields.selection([('0', 'Not urgent'), ('1', 'Normal'), ('2', 'Urgent'), ('3', 'Very Urgent')], 'Priority', required=True, select=True, track_visibility='onchange'),
        'date_planned': fields.datetime('Scheduled Date', required=True, select=True, track_visibility='onchange'),

        'group_id': fields.many2one('procurement.group', 'Procurement Group'),
        'rule_id': fields.many2one('procurement.rule', 'Rule', track_visibility='onchange', help="Chosen rule for the procurement resolution. Usually chosen by the system but can be manually set by the procurement manager to force an unusual behavior."),

        'product_id': fields.many2one('product.product', 'Product', required=True, states={'confirmed': [('readonly', False)]}, readonly=True),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'), required=True, states={'confirmed': [('readonly', False)]}, readonly=True),
        'product_uom': fields.many2one('product.uom', 'Product Unit of Measure', required=True, states={'confirmed': [('readonly', False)]}, readonly=True),

        'product_uos_qty': fields.float('UoS Quantity', states={'confirmed': [('readonly', False)]}, readonly=True),
        'product_uos': fields.many2one('product.uom', 'Product UoS', states={'confirmed': [('readonly', False)]}, readonly=True),

        'state': fields.selection([
            ('cancel', 'Cancelled'),
            ('confirmed', 'Confirmed'),
            ('exception', 'Exception'),
            ('running', 'Running'),
            ('done', 'Done')
        ], 'Status', required=True, track_visibility='onchange'),
    }

    _defaults = {
        'state': 'confirmed',
        'priority': '1',
        'date_planned': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'procurement.order', context=c)
    }

    def unlink(self, cr, uid, ids, context=None):
        procurements = self.read(cr, uid, ids, ['state'], context=context)
        unlink_ids = []
        for s in procurements:
            if s['state'] in ['draft', 'cancel']:
                unlink_ids.append(s['id'])
            else:
                raise osv.except_osv(_('Invalid Action!'),
                        _('Cannot delete Procurement Order(s) which are in %s state.') % s['state'])
        return osv.osv.unlink(self, cr, uid, unlink_ids, context=context)

    def do_view_procurements(self, cr, uid, ids, context=None):
        '''
        This function returns an action that display existing procurement orders
        of same procurement group of given ids.
        '''
        mod_obj = self.pool.get('ir.model.data')
        act_obj = self.pool.get('ir.actions.act_window')
        result = mod_obj.get_object_reference(cr, uid, 'procurement', 'do_view_procurements')
        id = result and result[1] or False
        result = act_obj.read(cr, uid, [id], context=context)[0]
        group_ids = set([proc.group_id.id for proc in self.browse(cr, uid, ids, context=context) if proc.group_id])
        result['domain'] = "[('group_id','in',[" + ','.join(map(str, list(group_ids))) + "])]"
        return result

    def onchange_product_id(self, cr, uid, ids, product_id, context=None):
        """ Finds UoM and UoS of changed product.
        @param product_id: Changed id of product.
        @return: Dictionary of values.
        """
        if product_id:
            w = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            v = {
                'product_uom': w.uom_id.id,
                'product_uos': w.uos_id and w.uos_id.id or w.uom_id.id
            }
            return {'value': v}
        return {}

    def get_cancel_ids(self, cr, uid, ids, context=None):
        return [proc.id for proc in self.browse(cr, uid, ids, context=context) if proc.state != 'done']

    def cancel(self, cr, uid, ids, context=None):
        #cancel only the procurements that aren't done already
        to_cancel_ids = self.get_cancel_ids(cr, uid, ids, context=context)
        if to_cancel_ids:
            return self.write(cr, uid, to_cancel_ids, {'state': 'cancel'}, context=context)

    def reset_to_confirmed(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'confirmed'}, context=context)

    def run(self, cr, uid, ids, context=None):
        for procurement_id in ids:
            procurement = self.browse(cr, uid, procurement_id, context=context)
            if procurement.state not in ("running", "done"):
                if self._assign(cr, uid, procurement, context=context):
                    procurement.refresh()
                    res = self._run(cr, uid, procurement, context=context or {})
                    if res:
                        self.write(cr, uid, [procurement.id], {'state': 'running'}, context=context)
                    else:
                        self.write(cr, uid, [procurement.id], {'state': 'exception'}, context=context)
                else:
                    self.message_post(cr, uid, [procurement.id], body=_('No rule matching this procurement'), context=context)
                    self.write(cr, uid, [procurement.id], {'state': 'exception'}, context=context)
        return True

    def check(self, cr, uid, ids, context=None):
        done_ids = []
        for procurement in self.browse(cr, uid, ids, context=context):
            result = self._check(cr, uid, procurement, context=context)
            if result:
                done_ids.append(procurement.id)
        if done_ids:
            self.write(cr, uid, done_ids, {'state': 'done'}, context=context)
        return done_ids

    #
    # Method to overwrite in different procurement modules
    #
    def _find_suitable_rule(self, cr, uid, procurement, context=None):
        '''This method returns a procurement.rule that depicts what to do with the given procurement
        in order to complete its needs. It returns False if no suiting rule is found.
            :param procurement: browse record
            :rtype: int or False
        '''
        return False

    def _assign(self, cr, uid, procurement, context=None):
        '''This method check what to do with the given procurement in order to complete its needs.
        It returns False if no solution is found, otherwise it stores the matching rule (if any) and
        returns True.
            :param procurement: browse record
            :rtype: boolean
        '''
        #if the procurement already has a rule assigned, we keep it (it has a higher priority as it may have been chosen manually)
        if procurement.rule_id:
            return True
        elif procurement.product_id.type != 'service':
            rule_id = self._find_suitable_rule(cr, uid, procurement, context=context)
            if rule_id:
                self.write(cr, uid, [procurement.id], {'rule_id': rule_id}, context=context)
                return True
        return False

    def _run(self, cr, uid, procurement, context=None):
        '''This method implements the resolution of the given procurement
            :param procurement: browse record
            :returns: True if the resolution of the procurement was a success, False otherwise to set it in exception
        '''
        return True

    def _check(self, cr, uid, procurement, context=None):
        '''Returns True if the given procurement is fulfilled, False otherwise
            :param procurement: browse record
            :rtype: boolean
        '''
        return False

    #
    # Scheduler
    #
    def run_scheduler(self, cr, uid, use_new_cursor=False, context=None):
        '''
        Call the scheduler to check the procurement order

        @param self: The object pointer
        @param cr: The current row, from the database cursor,
        @param uid: The current user ID for security checks
        @param ids: List of selected IDs
        @param use_new_cursor: False or the dbname
        @param context: A standard dictionary for contextual values
        @return:  Dictionary of values
        '''
        if context is None:
            context = {}
        try:
            if use_new_cursor:
                cr = openerp.registry(use_new_cursor).db.cursor()

            company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
            maxdate = (datetime.today() + relativedelta(days=company.schedule_range)).strftime('%Y-%m-%d %H:%M:%S')

            # Run confirmed procurements
            while True:
                ids = self.search(cr, uid, [('state', '=', 'confirmed'), ('date_planned', '<=', maxdate)], context=context)
                if not ids:
                    break
                self.run(cr, uid, ids, context=context)
                if use_new_cursor:
                    cr.commit()

            # Check if running procurements are done
            offset = 0
            while True:
                ids = self.search(cr, uid, [('state', '=', 'running'), ('date_planned', '<=', maxdate)], offset=offset, context=context)
                if not ids:
                    break
                done = self.check(cr, uid, ids, context=context)
                offset += len(ids) - len(done)
                if use_new_cursor:
                    cr.commit()

        finally:
            if use_new_cursor:
                try:
                    cr.close()
                except Exception:
                    pass
        return {}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
