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
import pdb

import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging
from PIL import Image

import netsvc
from osv import fields, osv
from tools.translate import _
from decimal import Decimal
import decimal_precision as dp

_logger = logging.getLogger(__name__)

class pos_config(osv.osv):
    _name = 'pos.config'

    POS_CONFIG_STATE = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('deprecated', 'Deprecated')
    ]

    _columns = {
        'name' : fields.char('Point of Sale Name', size=32, select=1,
             required=True, help="An internal identification of the point of sale"),
        'journal_ids' : fields.many2many('account.journal', 'pos_config_journal_rel', 
             'pos_config_id', 'journal_id', 'Available Payment Methods',
             domain="[('journal_user', '=', True )]",),
        'shop_id' : fields.many2one('sale.shop', 'Shop',
             required=True),
        'journal_id' : fields.many2one('account.journal', 'Sale Journal',
             required=True, domain=[('type', '=', 'sale')],
             help="Accounting journal used to post sales entries."),
        'iface_self_checkout' : fields.boolean('Self Checkout Mode',
             help="Check this if this point of sale should open by default in a self checkout mode. If unchecked, OpenERP uses the normal cashier mode by default."),
        'iface_websql' : fields.boolean('WebSQL (Faster but Chrome Only)',
            help="If have more than 200 products, it's highly suggested to use WebSQL "\
                "to store the data in the browser, instead of localStore mechanism. "\
                "It's more efficient but works on the Chrome browser only."
            ),
        'iface_led' : fields.boolean('LED Interface'),
        'iface_cashdrawer' : fields.boolean('Cashdrawer Interface'),
        'iface_payment_terminal' : fields.boolean('Payment Terminal Interface'),
        'iface_electronic_scale' : fields.boolean('Electronic Scale Interface'),
        'iface_barscan' : fields.boolean('BarScan Interface'), 
        'iface_vkeyboard' : fields.boolean('Virtual KeyBoard Interface'),
        'iface_print_via_proxy' : fields.boolean('Print via Proxy'),

        'state' : fields.selection(POS_CONFIG_STATE, 'State', required=True, readonly=True),
        'sequence_id' : fields.many2one('ir.sequence', 'Order IDs Sequence', readonly=True,
            help="This sequence is automatically created by OpenERP but you can change it "\
                "to customize the reference numbers of your orders."),
        'session_ids': fields.one2many('pos.session', 'config_id', 'Sessions'),
        'group_by' : fields.boolean('Group By', help="Check this if you want to group the Journal Items by Product while a Session"),
    }

    def name_get(self, cr, uid, ids, context=None):
        result = []
        states = {
            'opening_control': _('Opening Control'),
            'opened': _('In Progress'),
            'closing_control': _('Closing Control'),
            'closed': _('Closed & Posted'),
        }
        for record in self.browse(cr, uid, ids, context=context):
            if (not record.session_ids) or (record.session_ids[0].state=='closed'):
                result.append((record.id, record.name+' ('+_('not used')+')'))
                continue
            session = record.session_ids[0]
            result.append((record.id, record.name + ' ('+session.user_id.name+', '+states[session.state]+')'))
        return result


    def _default_sale_journal(self, cr, uid, context=None):
        res = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'sale')], limit=1)
        return res and res[0] or False

    def _default_shop(self, cr, uid, context=None):
        res = self.pool.get('sale.shop').search(cr, uid, [])
        return res and res[0] or False

    _defaults = {
        'state' : POS_CONFIG_STATE[0][0],
        'shop_id': _default_shop,
        'journal_id': _default_sale_journal,
        'group_by' : True,
    }

    def set_active(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state' : 'active'}, context=context)

    def set_inactive(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state' : 'inactive'}, context=context)

    def set_deprecate(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state' : 'deprecated'}, context=context)

    def create(self, cr, uid, values, context=None):
        proxy = self.pool.get('ir.sequence')
        sequence_values = dict(
            name='PoS %s' % values['name'],
            padding=5,
            prefix="%s/"  % values['name'],
        )
        sequence_id = proxy.create(cr, uid, sequence_values, context=context)
        values['sequence_id'] = sequence_id
        return super(pos_config, self).create(cr, uid, values, context=context)

    def unlink(self, cr, uid, ids, context=None):
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.sequence_id:
                obj.sequence_id.unlink()
        return super(pos_config, self).unlink(cr, uid, ids, context=context)

pos_config()

class pos_session(osv.osv):
    _name = 'pos.session'
    _order = 'id desc'

    POS_SESSION_STATE = [
        ('opening_control', 'Opening Control'),  # Signal open
        ('opened', 'In Progress'),                    # Signal closing
        ('closing_control', 'Closing Control'),  # Signal close
        ('closed', 'Closed & Posted'),
    ]

    def _compute_cash_register_id(self, cr, uid, ids, fieldnames, args, context=None):
        result = dict.fromkeys(ids, False)
        for record in self.browse(cr, uid, ids, context=context):
            for st in record.statement_ids:
                if st.journal_id.type == 'cash':
                    result[record.id] = st.id
                    break
        return result

    def _compute_controls(self, cr, uid, ids, fieldnames, args, context=None):
        result = {}

        for record in self.browse(cr, uid, ids, context=context):
            has_opening_control = False
            has_closing_control = False

            for journal in record.config_id.journal_ids:
                if journal.opening_control == True:
                    has_opening_control = True
                if journal.closing_control == True:
                    has_closing_control = True

                if has_opening_control and has_closing_control:
                    break

            values = {
                'has_opening_control': has_opening_control,
                'has_closing_control': has_closing_control,
            }
            result[record.id] = values

        return result

    _columns = {
        'config_id' : fields.many2one('pos.config', 'Point of Sale',
                                      help="The physical point of sale you will use.",
                                      required=True,
                                      select=1,
                                      domain="[('state', '=', 'active')]",
#                                      readonly=True,
#                                      states={'draft' : [('readonly', False)]}
                                     ),

        'name' : fields.char('Session ID', size=32,
                             required=True,
#                             readonly=True,
#                             states={'draft' : [('readonly', False)]}
                            ),
        'user_id' : fields.many2one('res.users', 'Responsible',
                                    required=True,
                                    select=1,
#                                    readonly=True,
#                                    states={'draft' : [('readonly', False)]}
                                   ),
        'start_at' : fields.datetime('Opening Date'), 
        'stop_at' : fields.datetime('Closing Date'),

        'state' : fields.selection(POS_SESSION_STATE, 'State',
                required=True, readonly=True,
                select=1),

        'cash_register_id' : fields.function(_compute_cash_register_id, method=True, 
                type='many2one', relation='account.bank.statement',
                string='Cash Register', store=True),

        'opening_details_ids' : fields.related('cash_register_id', 'opening_details_ids', 
                type='one2many', relation='account.cashbox.line',
                string='Opening Cash Control'),
        'details_ids' : fields.related('cash_register_id', 'details_ids', 
                type='one2many', relation='account.cashbox.line',
                string='Cash Control'),

        'cash_register_balance_end_real' : fields.related('cash_register_id', 'balance_end_real',
                type='float',
                digits_compute=dp.get_precision('Account'),
                string="Ending Balance",
                help="Computed using the cash control lines",
                readonly=True),
        'cash_register_balance_start' : fields.related('cash_register_id', 'balance_start',
                type='float',
                digits_compute=dp.get_precision('Account'),
                string="Starting Balance",
                help="Computed using the cash control at the opening.",
                readonly=True),
        'cash_register_total_entry_encoding' : fields.related('cash_register_id', 'total_entry_encoding',
                string='Total Cash Transaction',
                readonly=True),
        'cash_register_balance_end' : fields.related('cash_register_id', 'balance_end',
                type='float',
                digits_compute=dp.get_precision('Account'),
                string="Computed Balance",
                help="Computed with the initial cash control and the sum of all payments.",
                readonly=True),
        'cash_register_difference' : fields.related('cash_register_id', 'difference',
                type='float',
                string='Difference',
                help="Difference between the counted cash control at the closing and the computed balance.",
                readonly=True),

        'journal_ids' : fields.related('config_id', 'journal_ids',
                                       type='many2many',
                                       readonly=True,
                                       relation='account.journal',
                                       string='Available Payment Methods'),
        'order_ids' : fields.one2many('pos.order', 'session_id', 'Orders'),

        'statement_ids' : fields.one2many('account.bank.statement', 'pos_session_id', 'Bank Statement', readonly=True),
        'has_opening_control' : fields.function(_compute_controls, string='Has Opening Control', multi='control', type='boolean'),
        'has_closing_control' : fields.function(_compute_controls, string='Has Closing Control', multi='control', type='boolean'),
    }

    _defaults = {
        'name' : '/',
        'user_id' : lambda obj, cr, uid, context: uid,
        'state' : 'opening_control',
    }

    _sql_constraints = [
        ('uniq_name', 'unique(name)', "The name of this POS Session must be unique !"),
    ]

    def _check_unicity(self, cr, uid, ids, context=None):
        for session in self.browse(cr, uid, ids, context=None):
            # open if there is no session in 'opening_control', 'opened', 'closing_control' for one user
            domain = [
                ('state', '!=', 'closed'),
                ('user_id', '=', uid)
            ]
            count = self.search_count(cr, uid, domain, context=context)
            if count>1:
                return False
        return True

    def _check_pos_config(self, cr, uid, ids, context=None):
        for session in self.browse(cr, uid, ids, context=None):
            domain = [
                ('state', '!=', 'closed'),
                ('config_id', '=', session.config_id.id)
            ]
            count = self.search_count(cr, uid, domain, context=context)
            if count>1:
                return False
        return True

    _constraints = [
        (_check_unicity, "You can not create two active sessions with the same responsible!", ['user_id', 'state']),
        (_check_pos_config, "You can not create two active sessions related to the same point of sale!", ['config_id']),
    ]

    def create(self, cr, uid, values, context=None):
        config_id = values.get('config_id', False) or False

        pos_config = None
        if config_id:
            pos_config = self.pool.get('pos.config').browse(cr, uid, config_id, context=context)

            bank_statement_ids = []
            for journal in pos_config.journal_ids:
                bank_values = {
                    'journal_id' : journal.id,
                    'user_id' : uid,
                }
                statement_id = self.pool.get('account.bank.statement').create(cr, uid, bank_values, context=context)
                bank_statement_ids.append(statement_id)

            values.update({
                'name' : pos_config.sequence_id._next(),
                'statement_ids' : [(6, 0, bank_statement_ids)]
            })

        return super(pos_session, self).create(cr, uid, values, context=context)

    def unlink(self, cr, uid, ids, context=None):
        for obj in self.browse(cr, uid, ids, context=context):
            for statement in obj.statement_ids:
                statement.unlink(context=context)
        return True

    def wkf_action_open(self, cr, uid, ids, context=None):
        # si pas de date start_at, je balance une date, sinon on utilise celle de l'utilisateur
        for record in self.browse(cr, uid, ids, context=context):
            values = {}
            if not record.start_at:
                values['start_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
            values['state'] = 'opened'
            record.write(values, context=context)
            for st in record.statement_ids:
                st.button_open(context=context)
        return True

    def wkf_action_opening_control(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state' : 'opening_control'}, context=context)

    def wkf_action_closing_control(self, cr, uid, ids, context=None):
        for session in self.browse(cr, uid, ids, context=context):
            for statement in session.statement_ids:
                if not statement.journal_id.closing_control:
                    if statement.balance_end<>statement.balance_end_real:
                        self.pool.get('account.bank.statement').write(cr, uid,
                            [statement.id], {'balance_end_real': statement.balance_end})
        return self.write(cr, uid, ids, {'state' : 'closing_control', 'stop_at' : time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)

    def wkf_action_close(self, cr, uid, ids, context=None):
        # Close CashBox
        bsl = self.pool.get('account.bank.statement.line')
        for record in self.browse(cr, uid, ids, context=context):
            for st in record.statement_ids:
                if abs(st.difference) > st.journal_id.amount_authorized_diff:
                    # The pos manager can close statements with maximums.
                    if not self.pool.get('ir.model.access').check_groups(cr, uid, "point_of_sale.group_pos_manager"):
                        raise osv.except_osv( _('Error !'),
                            _("Your ending balance is too different from the theorical cash closing (%.2f), the maximum allowed is: %.2f. You can contact your manager to force it.") % (st.difference, st.journal_id.amount_authorized_diff))
                if st.difference:
                    if st.difference > 0.0:
                        name= _('Point of Sale Profit')
                        account_id = st.journal_id.profit_account_id.id
                    else:
                        account_id = st.journal_id.loss_account_id.id
                        name= _('Point of Sale Loss')
                    if not account_id:
                        raise osv.except_osv( _('Error !'),
                        _("Please set your profit and loss accounts on your payment method '%s'.") % (st.journal_id.name,))
                    bsl.create(cr, uid, {
                        'statement_id': st.id,
                        'amount': st.difference,
                        'ref': record.name,
                        'name': name,
                        'account_id': account_id
                    }, context=context)

                getattr(st, 'button_confirm_%s' % st.journal_id.type)(context=context)
        self._confirm_orders(cr, uid, ids, context=context)
        return self.write(cr, uid, ids, {'state' : 'closed'}, context=context)

    def _confirm_orders(self, cr, uid, ids, context=None):
        wf_service = netsvc.LocalService("workflow")

        for session in self.browse(cr, uid, ids, context=context):
            order_ids = [order.id for order in session.order_ids if order.state == 'paid']

            move_id = self.pool.get('account.move').create(cr, uid, {'ref' : session.name, 'journal_id' : session.config_id.journal_id.id, }, context=context)
            print "### move_id: %r" % (move_id,)
            print "order_ids: %r" % (order_ids,)

            self.pool.get('pos.order')._create_account_move_line(cr, uid, order_ids, session, move_id, context=context)

            for order in session.order_ids:
                if order.state != 'paid':
                    raise osv.except_osv(
                        _('Error !'),
                        _("You can not confirm all orders of this session, because they have not the 'paid' status"))
                else:
                    wf_service.trg_validate(uid, 'pos.order', order.id, 'done', cr)

        return True

    def open_frontend_cb(self, cr, uid, ids, context=None):
        if not context:
            context = {}

        if not ids:
            return {}

        context.update({'session_id' : ids[0]})
        return {
            'type' : 'ir.actions.client',
            'name' : 'Start Point Of Sale',
            'tag' : 'pos.ui',
            'context' : context,
        }

pos_session()

class pos_order(osv.osv):
    _name = "pos.order"
    _description = "Point of Sale"
    _order = "id desc"

    def create_from_ui(self, cr, uid, orders, context=None):
        #_logger.info("orders: %r", orders)
        list = []
        for order in orders:
            # order :: {'name': 'Order 1329148448062', 'amount_paid': 9.42, 'lines': [[0, 0, {'discount': 0, 'price_unit': 1.46, 'product_id': 124, 'qty': 5}], [0, 0, {'discount': 0, 'price_unit': 0.53, 'product_id': 62, 'qty': 4}]], 'statement_ids': [[0, 0, {'journal_id': 7, 'amount': 9.42, 'name': '2012-02-13 15:54:12', 'account_id': 12, 'statement_id': 21}]], 'amount_tax': 0, 'amount_return': 0, 'amount_total': 9.42}
            order_obj = self.pool.get('pos.order')
            # get statements out of order because they will be generated with add_payment to ensure
            # the module behavior is the same when using the front-end or the back-end
            if not order['data']['statement_ids']:
                continue
            statement_ids = order['data'].pop('statement_ids')
            order_id = self.create(cr, uid, order, context)
            list.append(order_id)
            # call add_payment; refer to wizard/pos_payment for data structure
            # add_payment launches the 'paid' signal to advance the workflow to the 'paid' state
            data = {
                'journal': statement_ids[0][2]['journal_id'],
                'amount': order['data']['amount_paid'],
                'payment_name': order['data']['name'],
                'payment_date': statement_ids[0][2]['name'],
            }
            order_obj.add_payment(cr, uid, order_id, data, context=context)
        return list

    def unlink(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids, context=context):
            if rec.state not in ('draft','cancel'):
                raise osv.except_osv(_('Unable to Delete !'), _('In order to delete a sale, it must be new or cancelled.'))
        return super(pos_order, self).unlink(cr, uid, ids, context=context)

    def onchange_partner_id(self, cr, uid, ids, part=False, context=None):
        if not part:
            return {'value': {}}
        pricelist = self.pool.get('res.partner').browse(cr, uid, part, context=context).property_product_pricelist.id
        return {'value': {'pricelist_id': pricelist}}

    def _amount_all(self, cr, uid, ids, name, args, context=None):
        tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        res = {}
        for order in self.browse(cr, uid, ids, context=context):
            res[order.id] = {
                'amount_paid': 0.0,
                'amount_return':0.0,
                'amount_tax':0.0,
            }
            val1 = val2 = 0.0
            cur = order.pricelist_id.currency_id
            for payment in order.statement_ids:
                res[order.id]['amount_paid'] +=  payment.amount
                res[order.id]['amount_return'] += (payment.amount < 0 and payment.amount or 0)
            for line in order.lines:
                val1 += line.price_subtotal_incl
                val2 += line.price_subtotal
            res[order.id]['amount_tax'] = cur_obj.round(cr, uid, cur, val1-val2)
            res[order.id]['amount_total'] = cur_obj.round(cr, uid, cur, val1)
        return res

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        d = {
            'state': 'draft',
            'invoice_id': False,
            'account_move': False,
            'picking_id': False,
            'statement_ids': [],
            'nb_print': 0,
            'name': self.pool.get('ir.sequence').get(cr, uid, 'pos.order'),
        }
        d.update(default)
        return super(pos_order, self).copy(cr, uid, id, d, context=context)

    _columns = {
        'name': fields.char('Order Ref', size=64, required=True, readonly=True),
        'company_id':fields.many2one('res.company', 'Company', required=True, readonly=True),
        'shop_id': fields.related('session_id', 'config_id', 'shop_id', relation='sale.shop', type='many2one', string='Shop', store=True, readonly=True),
        'date_order': fields.datetime('Order Date', readonly=True, select=True),
        'user_id': fields.many2one('res.users', 'Salesman', help="Person who uses the the cash register. It could be a reliever, a student or an interim employee."),
        'amount_tax': fields.function(_amount_all, string='Taxes', digits_compute=dp.get_precision('Point Of Sale'), multi='all'),
        'amount_total': fields.function(_amount_all, string='Total', multi='all'),
        'amount_paid': fields.function(_amount_all, string='Paid', states={'draft': [('readonly', False)]}, readonly=True, digits_compute=dp.get_precision('Point Of Sale'), multi='all'),
        'amount_return': fields.function(_amount_all, 'Returned', digits_compute=dp.get_precision('Point Of Sale'), multi='all'),
        'lines': fields.one2many('pos.order.line', 'order_id', 'Order Lines', states={'draft': [('readonly', False)]}, readonly=True),
        'statement_ids': fields.one2many('account.bank.statement.line', 'pos_statement_id', 'Payments', states={'draft': [('readonly', False)]}, readonly=True),
        'pricelist_id': fields.many2one('product.pricelist', 'Pricelist', required=True, states={'draft': [('readonly', False)]}, readonly=True),
        'partner_id': fields.many2one('res.partner', 'Customer', change_default=True, select=1, states={'draft': [('readonly', False)], 'paid': [('readonly', False)]}),

        'session_id' : fields.many2one('pos.session', 'Session', 
                                        #required=True,
                                        select=1,
                                        domain="[('state', '=', 'opened')]",
                                        states={'draft' : [('readonly', False)]},
                                        readonly=True),

        'state': fields.selection([('draft', 'New'),
                                   ('cancel', 'Cancelled'),
                                   ('paid', 'Paid'),
                                   ('done', 'Posted'),
                                   ('invoiced', 'Invoiced')],
                                  'State', readonly=True),

        'invoice_id': fields.many2one('account.invoice', 'Invoice'),
        'account_move': fields.many2one('account.move', 'Journal Entry', readonly=True),
        'picking_id': fields.many2one('stock.picking', 'Picking', readonly=True),
        'note': fields.text('Internal Notes'),
        'nb_print': fields.integer('Number of Print', readonly=True),

        'sale_journal': fields.related('session_id', 'config_id', 'journal_id', relation='account.journal', type='many2one', string='Sale Journal', store=True, readonly=True),
    }

    def _default_session(self, cr, uid, context=None):
        so = self.pool.get('pos.session')
        session_ids = so.search(cr, uid, [('state','=', 'opened'), ('user_id','=',uid)], context=context)
        return session_ids and session_ids[0] or False

    def _default_pricelist(self, cr, uid, context=None):
        res = self.pool.get('sale.shop').search(cr, uid, [], context=context)
        if res:
            shop = self.pool.get('sale.shop').browse(cr, uid, res[0], context=context)
            return shop.pricelist_id and shop.pricelist_id.id or False
        return False

    _defaults = {
        'user_id': lambda self, cr, uid, context: uid,
        'state': 'draft',
        'name': '/', 
        'date_order': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'nb_print': 0,
        'session_id': _default_session,
        'company_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.id,
        'pricelist_id': _default_pricelist,
    }

    def create(self, cr, uid, values, context=None):
        print "#CREATE: %r" % (values,)
        values['name'] = self.pool.get('ir.sequence').get(cr, uid, 'pos.order')
        #values['session_id'] = 40
        return super(pos_order, self).create(cr, uid, values, context=context)

    def test_paid(self, cr, uid, ids, context=None):
        """A Point of Sale is paid when the sum
        @return: True
        """
        for order in self.browse(cr, uid, ids, context=context):
            if order.lines and not order.amount_total:
                return True
            if (not order.lines) or (not order.statement_ids) or \
                (abs(order.amount_total-order.amount_paid) > 0.00001):
                return False
        return True

    def create_picking(self, cr, uid, ids, context=None):
        """Create a picking for each order and validate it."""
        picking_obj = self.pool.get('stock.picking')
        partner_obj = self.pool.get('res.partner')
        move_obj = self.pool.get('stock.move')

        for order in self.browse(cr, uid, ids, context=context):
            if not order.state=='draft':
                continue
            addr = order.partner_id and partner_obj.address_get(cr, uid, [order.partner_id.id], ['delivery']) or {}
            picking_id = picking_obj.create(cr, uid, {
                'origin': order.name,
                'partner_id': addr.get('delivery',False),
                'type': 'out',
                'company_id': order.company_id.id,
                'move_type': 'direct',
                'note': order.note or "",
                'invoice_state': 'none',
                'auto_picking': True,
            }, context=context)
            self.write(cr, uid, [order.id], {'picking_id': picking_id}, context=context)
            location_id = order.shop_id.warehouse_id.lot_stock_id.id
            output_id = order.shop_id.warehouse_id.lot_output_id.id

            for line in order.lines:
                if line.product_id and line.product_id.type == 'service':
                    continue
                if line.qty < 0:
                    location_id, output_id = output_id, location_id

                move_obj.create(cr, uid, {
                    'name': line.name,
                    'product_uom': line.product_id.uom_id.id,
                    'product_uos': line.product_id.uom_id.id,
                    'picking_id': picking_id,
                    'product_id': line.product_id.id,
                    'product_uos_qty': abs(line.qty),
                    'product_qty': abs(line.qty),
                    'tracking_id': False,
                    'state': 'draft',
                    'location_id': location_id,
                    'location_dest_id': output_id,
                }, context=context)
                if line.qty < 0:
                    location_id, output_id = output_id, location_id

            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)
            picking_obj.force_assign(cr, uid, [picking_id], context)
        return True

    def cancel_order(self, cr, uid, ids, context=None):
        """ Changes order state to cancel
        @return: True
        """
        stock_picking_obj = self.pool.get('stock.picking')
        for order in self.browse(cr, uid, ids, context=context):
            wf_service.trg_validate(uid, 'stock.picking', order.picking_id.id, 'button_cancel', cr)
            if stock_picking_obj.browse(cr, uid, order.picking_id.id, context=context).state <> 'cancel':
                raise osv.except_osv(_('Error!'), _('Unable to cancel the picking.'))
        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        return True

    def add_payment(self, cr, uid, order_id, data, context=None):
        """Create a new payment for the order"""
        if not context:
            context = {}
        statement_obj = self.pool.get('account.bank.statement')
        statement_line_obj = self.pool.get('account.bank.statement.line')
        prod_obj = self.pool.get('product.product')
        property_obj = self.pool.get('ir.property')
        curr_c = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        curr_company = curr_c.id
        order = self.browse(cr, uid, order_id, context=context)
        ids_new = []
        args = {
            'amount': data['amount'],
        }
        if 'payment_date' in data.keys():
            args['date'] = data['payment_date']
        args['name'] = order.name
        if data.get('payment_name', False):
            args['name'] = args['name'] + ': ' + data['payment_name']
        account_def = property_obj.get(cr, uid, 'property_account_receivable', 'res.partner', context=context)
        args['account_id'] = (order.partner_id and order.partner_id.property_account_receivable \
                             and order.partner_id.property_account_receivable.id) or (account_def and account_def.id) or False
        args['partner_id'] = order.partner_id and order.partner_id.id or None

        if not args['account_id']:
            if not args['partner_id']:
                msg = _('There is no receivable account defined to make payment')
            else:
                msg = _('There is no receivable account defined to make payment for the partner: "%s" (id:%d)') % (order.partner_id.name, order.partner_id.id,)
            raise osv.except_osv(_('Configuration Error !'), msg)

        context.pop('pos_session_id', False)

        try:
            journal_id = long(data['journal'])
        except Exception:
            journal_id = False

        statement_id = False
        for statement in order.session_id.statement_ids:
            if statement.journal_id.id == journal_id:
                statement_id = statement.id
                break

        if not statement_id:
            raise osv.except_osv(_('Error !'), _('You have to open at least one cashbox'))

        args.update({
            'statement_id' : statement_id,
            'pos_statement_id' : order_id,
            'journal_id' : journal_id,
            'type' : 'customer',
            'ref' : order.name,
        })

        statement_line_obj.create(cr, uid, args, context=context)
        ids_new.append(statement_id)

        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_validate(uid, 'pos.order', order_id, 'paid', cr)
        wf_service.trg_write(uid, 'pos.order', order_id, cr)

        return statement_id

    def refund(self, cr, uid, ids, context=None):
        """Create a copy of order  for refund order"""
        clone_list = []
        line_obj = self.pool.get('pos.order.line')
        for order in self.browse(cr, uid, ids, context=context):
            clone_id = self.copy(cr, uid, order.id, {
                'name': order.name + ' REFUND',
            }, context=context)
            clone_list.append(clone_id)

        for clone in self.browse(cr, uid, clone_list, context=context):
            for order_line in clone.lines:
                line_obj.write(cr, uid, [order_line.id], {
                    'qty': -order_line.qty
                }, context=context)

        new_order = ','.join(map(str,clone_list))
        abs = {
            #'domain': "[('id', 'in', ["+new_order+"])]",
            'name': _('Return Products'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'pos.order',
            'res_id':clone_list[0],
            'view_id': False,
            'context':context,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
        }
        return abs

    def action_invoice_state(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state':'invoiced'}, context=context)

    def action_invoice(self, cr, uid, ids, context=None):
        wf_service = netsvc.LocalService("workflow")
        inv_ref = self.pool.get('account.invoice')
        inv_line_ref = self.pool.get('account.invoice.line')
        product_obj = self.pool.get('product.product')
        inv_ids = []

        for order in self.pool.get('pos.order').browse(cr, uid, ids, context=context):
            if order.invoice_id:
                inv_ids.append(order.invoice_id.id)
                continue

            if not order.partner_id:
                raise osv.except_osv(_('Error'), _('Please provide a partner for the sale.'))

            acc = order.partner_id.property_account_receivable.id
            inv = {
                'name': order.name,
                'origin': order.name,
                'account_id': acc,
                'journal_id': order.sale_journal.id or None,
                'type': 'out_invoice',
                'reference': order.name,
                'partner_id': order.partner_id.id,
                'comment': order.note or '',
                'currency_id': order.pricelist_id.currency_id.id, # considering partner's sale pricelist's currency
            }
            inv.update(inv_ref.onchange_partner_id(cr, uid, [], 'out_invoice', order.partner_id.id)['value'])
            if not inv.get('account_id', None):
                inv['account_id'] = acc
            inv_id = inv_ref.create(cr, uid, inv, context=context)

            self.write(cr, uid, [order.id], {'invoice_id': inv_id, 'state': 'invoiced'}, context=context)
            inv_ids.append(inv_id)
            for line in order.lines:
                inv_line = {
                    'invoice_id': inv_id,
                    'product_id': line.product_id.id,
                    'quantity': line.qty,
                }
                inv_name = product_obj.name_get(cr, uid, [line.product_id.id], context=context)[0][1]
                inv_line.update(inv_line_ref.product_id_change(cr, uid, [],
                                                               line.product_id.id,
                                                               line.product_id.uom_id.id,
                                                               line.qty, partner_id = order.partner_id.id,
                                                               fposition_id=order.partner_id.property_account_position.id)['value'])
                if line.product_id.description_sale:
                    inv_line['note'] = line.product_id.description_sale
                inv_line['price_unit'] = line.price_unit
                inv_line['discount'] = line.discount
                inv_line['name'] = inv_name
                inv_line['invoice_line_tax_id'] = ('invoice_line_tax_id' in inv_line)\
                    and [(6, 0, inv_line['invoice_line_tax_id'])] or []
                inv_line_ref.create(cr, uid, inv_line, context=context)
            inv_ref.button_reset_taxes(cr, uid, [inv_id], context=context)
            wf_service.trg_validate(uid, 'pos.order', order.id, 'invoice', cr)

        if not inv_ids: return {}

        mod_obj = self.pool.get('ir.model.data')
        res = mod_obj.get_object_reference(cr, uid, 'account', 'invoice_form')
        res_id = res and res[1] or False
        return {
            'name': _('Customer Invoice'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [res_id],
            'res_model': 'account.invoice',
            'context': "{'type':'out_invoice'}",
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'res_id': inv_ids and inv_ids[0] or False,
        }

    def create_account_move(self, cr, uid, ids, context=None):
        return self._create_account_move_line(cr, uid, ids, None, None, context=context)

    def _create_account_move_line(self, cr, uid, ids, session=None, move_id=None, context=None):
        # Tricky, via the workflow, we only have one id in the ids variable
        """Create a account move line of order grouped by products or not."""
        account_move_obj = self.pool.get('account.move')
        account_move_line_obj = self.pool.get('account.move.line')
        account_period_obj = self.pool.get('account.period')
        account_tax_obj = self.pool.get('account.tax')
        user_proxy = self.pool.get('res.users')
        property_obj = self.pool.get('ir.property')

        period = account_period_obj.find(cr, uid, context=context)[0]

        #session_ids = set(order.session_id for order in self.browse(cr, uid, ids, context=context))

        if session and not all(session.id == order.session_id.id for order in self.browse(cr, uid, ids, context=context)):
            raise osv.except_osv(_('Error!'), _('The selected orders do not have the same session !'))

        current_company = user_proxy.browse(cr, uid, uid, context=context).company_id

        grouped_data = {}
        have_to_group_by = session and session.config_id.group_by or False

        def compute_tax(amount, tax, line):
            if amount > 0:
                tax_code_id = tax['base_code_id']
                tax_amount = line.price_subtotal * tax['base_sign']
            else:
                tax_code_id = tax['ref_base_code_id']
                tax_amount = line.price_subtotal * tax['ref_base_sign']

            return (tax_code_id, tax_amount,)

        for order in self.browse(cr, uid, ids, context=context):
            if order.account_move:
                continue
            if order.state != 'paid':
                continue

            user_company = user_proxy.browse(cr, order.user_id.id, order.user_id.id).company_id

            group_tax = {}
            account_def = property_obj.get(cr, uid, 'property_account_receivable', 'res.partner', context=context).id

            order_account = order.partner_id and \
                            order.partner_id.property_account_receivable and \
                            order.partner_id.property_account_receivable.id or account_def or current_company.account_receivable.id

            if move_id is None:
                # Create an entry for the sale
                move_id = account_move_obj.create(cr, uid, {
                    'ref' : order.name,
                    'journal_id': order.sale_journal.id,
                }, context=context)

            def insert_data(data_type, values):
                # if have_to_group_by:

                if have_to_group_by:
                    sale_journal_id = session.config_id.journal_id.id
                else:
                    sale_journal_id = order.sale_journal.id

                # 'quantity': line.qty,
                # 'product_id': line.product_id.id,
                values.update({
                    'date': order.date_order[:10],
                    'ref': order.name,
                    'journal_id' : sale_journal_id,
                    'period_id' : period,
                    'move_id' : move_id,
                    'company_id': user_company and user_company.id or False,
                })

                if data_type == 'product':
                    key = ('product', values['product_id'],)
                elif data_type == 'tax':
                    key = ('tax', values['tax_code_id'],)
                elif data_type == 'counter_part':
                    key = ('counter_part',)
                else:
                    return

                grouped_data.setdefault(key, [])

                # if not have_to_group_by or (not grouped_data[key]):
                #     grouped_data[key].append(values)
                # else:
                #     pass

                if have_to_group_by:
                    if not grouped_data[key]:
                        grouped_data[key].append(values)
                    else:
                        current_value = grouped_data[key][0]
                        current_value['quantity'] = current_value.get('quantity', 0.0) +  values.get('quantity', 0.0)
                        current_value['credit'] = current_value.get('credit', 0.0) + values.get('credit', 0.0)
                        current_value['debit'] = current_value.get('debit', 0.0) + values.get('debit', 0.0)
                        current_value['tax_amount'] = current_value.get('tax_amount', 0.0) + values.get('tax_amount', 0.0)
                else:
                    grouped_data[key].append(values)

            # Create an move for each order line

            for line in order.lines:
                tax_amount = 0
                taxes = [t for t in line.product_id.taxes_id]
                computed_taxes = account_tax_obj.compute_all(cr, uid, taxes, line.price_unit * (100.0-line.discount) / 100.0, line.qty)['taxes']

                for tax in computed_taxes:
                    tax_amount += round(tax['amount'], 2)
                    group_key = (tax['tax_code_id'], tax['base_code_id'], tax['account_collected_id'], tax['id'])

                    group_tax.setdefault(group_key, 0)
                    group_tax[group_key] += round(tax['amount'], 2)

                amount = line.price_subtotal

                # Search for the income account
                if  line.product_id.property_account_income.id:
                    income_account = line.product_id.property_account_income.id
                elif line.product_id.categ_id.property_account_income_categ.id:
                    income_account = line.product_id.categ_id.property_account_income_categ.id
                else:
                    raise osv.except_osv(_('Error !'), _('There is no income '\
                        'account defined for this product: "%s" (id:%d)') \
                        % (line.product_id.name, line.product_id.id, ))

                # Empty the tax list as long as there is no tax code:
                tax_code_id = False
                tax_amount = 0
                while computed_taxes:
                    tax = computed_taxes.pop(0)
                    tax_code_id, tax_amount = compute_tax(amount, tax, line)

                    # If there is one we stop
                    if tax_code_id:
                        break

                # Create a move for the line
                insert_data('product', {
                    'name': line.product_id.name,
                    'quantity': line.qty,
                    'product_id': line.product_id.id,
                    'account_id': income_account,
                    'credit': ((amount>0) and amount) or 0.0,
                    'debit': ((amount<0) and -amount) or 0.0,
                    'tax_code_id': tax_code_id,
                    'tax_amount': tax_amount,
                    'partner_id': order.partner_id and order.partner_id.id or False
                })

                # For each remaining tax with a code, whe create a move line
                for tax in computed_taxes:
                    tax_code_id, tax_amount = compute_tax(amount, tax, line)
                    if not tax_code_id:
                        continue

                    insert_data('tax', {
                        'name': _('Tax'),
                        'product_id':line.product_id.id,
                        'quantity': line.qty,
                        'account_id': income_account,
                        'credit': 0.0,
                        'debit': 0.0,
                        'tax_code_id': tax_code_id,
                        'tax_amount': tax_amount,
                    })

            # Create a move for each tax group
            (tax_code_pos, base_code_pos, account_pos, tax_id)= (0, 1, 2, 3)

            for key, tax_amount in group_tax.items():
                tax = self.pool.get('account.tax').browse(cr, uid, key[tax_id], context=context)
                insert_data('tax', {
                    'name': _('Tax') + ' ' + tax.name,
                    'quantity': line.qty,
                    'product_id': line.product_id.id,
                    'account_id': key[account_pos],
                    'credit': ((tax_amount>0) and tax_amount) or 0.0,
                    'debit': ((tax_amount<0) and -tax_amount) or 0.0,
                    'tax_code_id': key[tax_code_pos],
                    'tax_amount': tax_amount,
                })

            # counterpart
            insert_data('counter_part', {
                'name': _("Trade Receivables"), #order.name,
                'account_id': order_account,
                'credit': ((order.amount_total < 0) and -order.amount_total) or 0.0,
                'debit': ((order.amount_total > 0) and order.amount_total) or 0.0,
                'partner_id': order.partner_id and order.partner_id.id or False
            })

            order.write({'state':'done', 'account_move': move_id})


        print "grouped_data: %r" % (grouped_data,)
        for group_key, group_data in grouped_data.iteritems():
            for value in group_data:
                print "value: %r" % (value,)
                account_move_line_obj.create(cr, uid, value, context=context)

        return True

    def action_payment(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'payment'}, context=context)

    def action_paid(self, cr, uid, ids, context=None):
        self.create_picking(cr, uid, ids, context=context)
        self.write(cr, uid, ids, {'state': 'paid'}, context=context)
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        return True

    def action_done(self, cr, uid, ids, context=None):
        self.create_account_move(cr, uid, ids, context=context)
        return True

pos_order()

class account_bank_statement(osv.osv):
    _inherit = 'account.bank.statement'
    _columns= {
        'user_id': fields.many2one('res.users', 'User', readonly=True),
    }
    _defaults = {
        'user_id': lambda self,cr,uid,c={}: uid
    }
account_bank_statement()

class account_bank_statement_line(osv.osv):
    _inherit = 'account.bank.statement.line'
    _columns= {
        'pos_statement_id': fields.many2one('pos.order', ondelete='cascade'),
    }
account_bank_statement_line()

class pos_order_line(osv.osv):
    _name = "pos.order.line"
    _description = "Lines of Point of Sale"
    _rec_name = "product_id"

    def _amount_line_all(self, cr, uid, ids, field_names, arg, context=None):
        res = dict([(i, {}) for i in ids])
        account_tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')
        for line in self.browse(cr, uid, ids, context=context):
            taxes = line.product_id.taxes_id
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = account_tax_obj.compute_all(cr, uid, line.product_id.taxes_id, price, line.qty, product=line.product_id, partner=line.order_id.partner_id or False)

            cur = line.order_id.pricelist_id.currency_id
            res[line.id]['price_subtotal'] = cur_obj.round(cr, uid, cur, taxes['total'])
            res[line.id]['price_subtotal_incl'] = cur_obj.round(cr, uid, cur, taxes['total_included'])
        return res

    def onchange_product_id(self, cr, uid, ids, pricelist, product_id, qty=0, partner_id=False, context=None):
       context = context or {}
       if not product_id:
            return {}
       if not pricelist:
           raise osv.except_osv(_('No Pricelist !'),
               _('You have to select a pricelist in the sale form !\n' \
               'Please set one before choosing a product.'))

       price = self.pool.get('product.pricelist').price_get(cr, uid, [pricelist],
               product_id, qty or 1.0, partner_id)[pricelist]

       result = self.onchange_qty(cr, uid, ids, product_id, 0.0, qty, price, context=context)
       result['value']['price_unit'] = price
       return result

    def onchange_qty(self, cr, uid, ids, product, discount, qty, price_unit, context=None):
        result = {}
        if not product:
            return result
        account_tax_obj = self.pool.get('account.tax')
        cur_obj = self.pool.get('res.currency')

        prod = self.pool.get('product.product').browse(cr, uid, product, context=context)

        taxes = prod.taxes_id
        price = price_unit * (1 - (discount or 0.0) / 100.0)
        taxes = account_tax_obj.compute_all(cr, uid, prod.taxes_id, price, qty, product=prod, partner=False)

        result['price_subtotal'] = taxes['total']
        result['price_subtotal_incl'] = taxes['total_included']
        return {'value': result}

    _columns = {
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'name': fields.char('Line No', size=32, required=True),
        'notice': fields.char('Discount Notice', size=128),
        'product_id': fields.many2one('product.product', 'Product', domain=[('sale_ok', '=', True)], required=True, change_default=True),
        'price_unit': fields.float(string='Unit Price', digits=(16, 2)),
        'qty': fields.float('Quantity', digits=(16, 2)),
        'price_subtotal': fields.function(_amount_line_all, multi='pos_order_line_amount', string='Subtotal w/o Tax', store=True),
        'price_subtotal_incl': fields.function(_amount_line_all, multi='pos_order_line_amount', string='Subtotal', store=True),
        'discount': fields.float('Discount (%)', digits=(16, 2)),
        'order_id': fields.many2one('pos.order', 'Order Ref', ondelete='cascade'),
        'create_date': fields.datetime('Creation Date', readonly=True),
    }

    _defaults = {
        'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'pos.order.line'),
        'qty': lambda *a: 1,
        'discount': lambda *a: 0.0,
        'company_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.id,
    }

    def copy_data(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'pos.order.line')
        })
        return super(pos_order_line, self).copy_data(cr, uid, id, default, context=context)

pos_order_line()

class pos_category(osv.osv):
    _name = 'pos.category'
    _description = "Point of Sale Category"
    _order = "sequence, name"
    def _check_recursion(self, cr, uid, ids, context=None):
        level = 100
        while len(ids):
            cr.execute('select distinct parent_id from pos_category where id IN %s',(tuple(ids),))
            ids = filter(None, map(lambda x:x[0], cr.fetchall()))
            if not level:
                return False
            level -= 1
        return True

    _constraints = [
        (_check_recursion, 'Error ! You cannot create recursive categories.', ['parent_id'])
    ]

    def name_get(self, cr, uid, ids, context=None):
        if not len(ids):
            return []
        reads = self.read(cr, uid, ids, ['name','parent_id'], context=context)
        res = []
        for record in reads:
            name = record['name']
            if record['parent_id']:
                name = record['parent_id'][1]+' / '+name
            res.append((record['id'], name))
        return res

    def _name_get_fnc(self, cr, uid, ids, prop, unknow_none, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    _columns = {
        'name': fields.char('Name', size=64, required=True, translate=True),
        'complete_name': fields.function(_name_get_fnc, type="char", string='Name'),
        'parent_id': fields.many2one('pos.category','Parent Category', select=True),
        'child_id': fields.one2many('pos.category', 'parent_id', string='Children Categories'),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying a list of product categories."),
    }
pos_category()

import io, StringIO

class product_product(osv.osv):
    _inherit = 'product.product'
    def _get_small_image(self, cr, uid, ids, prop, unknow_none, context=None):
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            if not obj.product_image:
                result[obj.id] = False
                continue

            image_stream = io.BytesIO(obj.product_image.decode('base64'))
            img = Image.open(image_stream)
            img.thumbnail((120, 100), Image.ANTIALIAS)
            img_stream = StringIO.StringIO()
            img.save(img_stream, "JPEG")
            result[obj.id] = img_stream.getvalue().encode('base64')
        return result

    _columns = {
        'income_pdt': fields.boolean('Point of Sale Cash In', help="This is a product you can use to put cash into a statement for the point of sale backend."),
        'expense_pdt': fields.boolean('Point of Sale Cash Out', help="This is a product you can use to take cash from a statement for the point of sale backend, exemple: money lost, transfer to bank, etc."),
        'pos_categ_id': fields.many2one('pos.category','Point of Sale Category',
            help="If you want to sell this product through the point of sale, select the category it belongs to."),
        'product_image_small': fields.function(_get_small_image, string='Small Image', type="binary",
            store = {
                'product.product': (lambda self, cr, uid, ids, c={}: ids, ['product_image'], 10),
            }),
        'to_weight' : fields.boolean('To Weight', help="This category contains products that should be weighted, mainly used for the self-checkout interface"),
    }
    _defaults = {
        'to_weight' : False,
    }

product_product()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
