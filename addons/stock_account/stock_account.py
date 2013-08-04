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

from datetime import datetime
from dateutil.relativedelta import relativedelta
import time
from operator import itemgetter
from itertools import groupby

from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp import netsvc
from openerp import tools
from openerp.tools import float_compare, DEFAULT_SERVER_DATETIME_FORMAT
import openerp.addons.decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)


#----------------------------------------------------------
# Stock Location
#----------------------------------------------------------

class stock_location(osv.osv):
    _inherit = "stock.location"

    _columns = {
        'valuation_in_account_id': fields.many2one('account.account', 'Stock Valuation Account (Incoming)', domain = [('type','=','other')],
                                                   help="Used for real-time inventory valuation. When set on a virtual location (non internal type), "
                                                        "this account will be used to hold the value of products being moved from an internal location "
                                                        "into this location, instead of the generic Stock Output Account set on the product. "
                                                        "This has no effect for internal locations."),
        'valuation_out_account_id': fields.many2one('account.account', 'Stock Valuation Account (Outgoing)', domain = [('type','=','other')],
                                                   help="Used for real-time inventory valuation. When set on a virtual location (non internal type), "
                                                        "this account will be used to hold the value of products being moved out of this location "
                                                        "and into an internal location, instead of the generic Stock Output Account set on the product. "
                                                        "This has no effect for internal locations."),
    }

#----------------------------------------------------------
# Quants
#----------------------------------------------------------

class stock_quant(osv.osv):
    _inherit = "stock.quant"


    def _get_inventory_value(self, cr, uid, line, prodbrow, context=None):
        #TODO: what in case of partner_id
        if prodbrow[(line.company_id.id, line.product_id.id)].cost_method in ('real'):
            return line.cost * line.qty
        return super(stock_quant, self)._get_inventory_value(cr, uid, line, prodbrow, context=context)


    # FP Note: this is where we should post accounting entries for adjustment
    def _price_update(self, cr, uid, quant, newprice, context=None):
        super(stock_quant, self)._price_update(cr, uid, quant, newprice, context=context)
        # TODO: generate accounting entries

    """
    Accounting Valuation Entries

    location_from: can be None if it's a new quant
    """
    def _account_entry_move(self, cr, uid, quant, location_from, location_to, move, context=None):
        if context is None:
            context = {}
        if quant.product_id.valuation != 'real_time':
            return False
        if quant.lot_id and quant.lot_id.partner_id:
            #if the quant isn't owned by the company, we don't make any valuation entry
            return False
        if quant.qty <= 0 or quant.propagated_from_id:
            #we don't make any stock valuation for negative quants because we may not know the real cost price.
            #The valuation will be made at the time of the reconciliation of the negative quant.
            return False
        company_from = self._location_owner(cr, uid, quant, location_from, context=context)
        company_to = self._location_owner(cr, uid, quant, location_to, context=context)
        if company_from == company_to:
            return False

        # Create Journal Entry for products arriving in the company
        if company_to:
            ctx = context.copy()
            ctx['force_company'] = company_to.id
            journal_id, acc_src, acc_dest, acc_valuation = self._get_accounting_data_for_valuation(cr, uid, move, context=ctx)
            if location_from and location_from.usage == 'customer':
                #goods returned from customer
                self._create_account_move_line(cr, uid, quant, move, acc_dest, acc_valuation, journal_id, context=ctx)
            else:
                self._create_account_move_line(cr, uid, quant, move, acc_src, acc_valuation, journal_id, context=ctx)

        # Create Journal Entry for products leaving the company
        if company_from:
            ctx = context.copy()
            ctx['force_company'] = company_from.id
            journal_id, acc_src, acc_dest, acc_valuation = self._get_accounting_data_for_valuation(cr, uid, move, context=ctx)
            if location_to and location_to.usage == 'supplier':
                #goods returned to supplier
                self._create_account_move_line(cr, uid, quant, move, acc_valuation, acc_src, journal_id, context=ctx)
            else:
                self._create_account_move_line(cr, uid, quant, move, acc_valuation, acc_dest, journal_id, context=ctx)

    def move_single_quant(self, cr, uid, quant, qty, move, context=None):
        location_from = quant and quant.location_id or False
        quant = super(stock_quant, self).move_single_quant(cr, uid, quant, qty, move, context=context)
        quant.refresh()
        self._account_entry_move(cr, uid, quant, location_from, quant.location_id, move, context=context)
        return quant

    def _get_accounting_data_for_valuation(self, cr, uid, move, context=None):
        """
        Return the accounts and journal to use to post Journal Entries for the real-time
        valuation of the quant.

        :param context: context dictionary that can explicitly mention the company to consider via the 'force_company' key
        :returns: journal_id, source account, destination account, valuation account
        :raise: osv.except_osv() is any mandatory account or journal is not defined.
        """
        product_obj = self.pool.get('product.product')
        accounts = product_obj.get_product_accounts(cr, uid, move.product_id.id, context)
        if move.location_id.valuation_out_account_id:
            acc_src = move.location_id.valuation_out_account_id.id
        else:
            acc_src = accounts['stock_account_input']

        if move.location_dest_id.valuation_in_account_id:
            acc_dest = move.location_dest_id.valuation_in_account_id.id
        else:
            acc_dest = accounts['stock_account_output']

        acc_valuation = accounts.get('property_stock_valuation_account_id', False)
        journal_id = accounts['stock_journal']

        if not all([acc_src, acc_dest, acc_valuation, journal_id]):
            raise osv.except_osv(_('Error!'), _('''One of the following information is missing on the product or product category and prevents the accounting valuation entries to be created:
    Stock Input Account: %s
    Stock Output Account: %s
    Stock Valuation Account: %s
    Stock Journal: %s
    ''') % (acc_src, acc_dest, acc_valuation, journal_id))
        return journal_id, acc_src, acc_dest, acc_valuation

    def _prepare_account_move_line(self, cr, uid, quant, move, credit_account_id, debit_account_id, context=None):
        """
        Generate the account.move.line values to post to track the stock valuation difference due to the
        processing of the given quant.
        """
        valuation_amount = quant.product_id.cost_method == 'real' and quant.cost or quant.product_id.standard_price
        partner_id = (move.picking_id.partner_id and self.pool.get('res.partner')._find_accounting_partner(move.picking_id.partner_id).id) or False
        debit_line_vals = {
                    'name': move.name,
                    'product_id': quant.product_id.id,
                    'quantity': quant.qty,
                    'product_uom_id': quant.product_id.uom_id.id, 
                    'ref': move.picking_id and move.picking_id.name or False,
                    'date': time.strftime('%Y-%m-%d'),
                    'partner_id': partner_id,
                    'debit': valuation_amount * quant.qty,
                    'account_id': debit_account_id,
        }
        credit_line_vals = {
                    'name': move.name,
                    'product_id': quant.product_id.id,
                    'quantity': quant.qty,
                    'product_uom_id': quant.product_id.uom_id.id, 
                    'ref': move.picking_id and move.picking_id.name or False,
                    'date': time.strftime('%Y-%m-%d'),
                    'partner_id': partner_id,
                    'credit': valuation_amount * quant.qty,
                    'account_id': credit_account_id,
        }
        res = [(0, 0, debit_line_vals), (0, 0, credit_line_vals)]
        return res

    def _create_account_move_line(self, cr, uid, quant, move, credit_account_id, debit_account_id, journal_id, context=None):
        move_obj = self.pool.get('account.move')
        move_lines = self._prepare_account_move_line(cr, uid, quant, move, credit_account_id, debit_account_id, context=context)
        return move_obj.create(cr, uid, {'journal_id': journal_id,
                                  'line_id': move_lines,
                                  'ref': move.picking_id and move.picking_id.name}, context=context)

