# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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

from osv import osv, fields
import decimal_precision as dp

class account_asset_category(osv.osv):
    _name = 'account.asset.category'
    _description = 'Asset category'

    _columns = {
        'name': fields.char('Name', size=64, required=True, select=1),
        'note': fields.text('Note'),
        'account_analytic_id': fields.many2one('account.analytic.account', 'Analytic account'),
        'account_asset_id': fields.many2one('account.account', 'Asset Account', required=True),
        'account_depreciation_id': fields.many2one('account.account', 'Depreciation Account', required=True),
        'account_expense_depreciation_id': fields.many2one('account.account', 'Depr. Expense Account', required=True),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'method': fields.selection([('linear','Linear'),('progressif','Progressive')], 'Computation method', required=True),
        'method_delay': fields.integer('Number of Depreciation'),
        'method_period': fields.integer('Period Length', help="State here the time between 2 depreciations, in months"),
        'method_progress_factor': fields.float('Progressif Factor'),
        'method_time': fields.selection([('delay','Delay'),('end','Ending Period')], 'Time Method', required=True),
        'method_end': fields.date('Ending date'),
        'prorata':fields.boolean('Prorata Temporis', help='Indicates that the accounting entries for this asset have to be done from the purchase date instead of the first January'),
        'open_asset': fields.boolean('Skip Draft State', help="Check this if you want to automatically confirm the assets of this category when created by invoice."),
    }

    _defaults = {
        'company_id': lambda self, cr, uid, context: self.pool.get('res.company')._company_default_get(cr, uid, 'account.asset.category', context=context),
        'method': 'linear',
        'method_delay': 5,
        'method_time': 'delay',
        'method_period': 12,
        'method_progress_factor': 0.3,
    }

    def onchange_account_asset(self, cr, uid, ids, account_asset_id, context=None):
        res = {'value':{}}
        if account_asset_id:
           res['value'] = {'account_depreciation_id': account_asset_id}
        return res

account_asset_category()

#class one2many_mod_asset(fields.one2many):
#
#    def get(self, cr, obj, ids, name, user=None, offset=0, context=None, values=None):
#        prinasset_property_id        if context is None:
#            context = {}
#        if not values:
#            values = {}
#        res = {}
#        for id in ids:
#            res[id] = []
#        #compute depreciation board
#        depreciation_line_ids = obj.pool.get('account.asset.asset').compute_depreciation_board(cr, user, ids, context=context)
#        for key, value in depreciation_line_ids.items():
#            #write values on asset
#            obj.pool.get(self._obj).write(cr, user, key, {'depreciation_line_ids': [6,0,value]})
#        return depreciation_line_ids

class account_asset_asset(osv.osv):
    _name = 'account.asset.asset'
    _description = 'Asset'

    def _get_period(self, cr, uid, context={}):
        periods = self.pool.get('account.period').find(cr, uid)
        if periods:
            return periods[0]
        else:
            return False

    def _get_last_depreciation_date(self, cr, uid, ids, context=None):
        """
        @param id: ids of a account.asset.asset objects
        @return: Returns a dictionary of the effective dates of the last depreciation entry made for given asset ids. If there isn't any, return the purchase date of this asset
        """
        cr.execute("""
            SELECT a.id as id, COALESCE(MAX(l.date),a.purchase_date) AS date
            FROM account_asset_asset a
            LEFT JOIN account_move_line l ON (l.asset_id = a.id)
            WHERE a.id IN %s
            GROUP BY a.id, a.purchase_date """, (tuple(ids),))
        return dict(cr.fetchall())

    def calculate_date(self, date, period):
        return datetime(date.year, date.month, date.day) + relativedelta(months=+period)

    def compute_depreciation_board(self, cr, uid,ids, context=None):
        depreciation_lin_obj = self.pool.get('account.asset.depreciation.line')
        for asset in self.browse(cr, uid, ids, context=context):
            if asset.value_residual == 0.0:
                continue
            posted_depreciation_line_ids = depreciation_lin_obj.search(cr, uid, [('asset_id', '=', asset.id), ('move_check', '=', True)])
            old_depreciation_line_ids = depreciation_lin_obj.search(cr, uid, [('asset_id', '=', asset.id), ('move_id', '=', False)])
            if old_depreciation_line_ids:
                depreciation_lin_obj.unlink(cr, uid, old_depreciation_line_ids, context=context)
            
            amount_to_depr = residual_amount = asset.value_residual

            depreciation_date = datetime.strptime(self._get_last_depreciation_date(cr, uid, [asset.id], context)[asset.id], '%Y-%m-%d')
            total_days = (depreciation_date.year % 4) and 365 or 366
            undone_dotation_number = asset.method_delay
            # Considering Depr. Period as months
            time_period = asset.method_period
            if asset.method_time == 'end':
                end_date = datetime.strptime(asset.method_end, '%Y-%m-%d')
                if time_period != 12:
                    total_days = time_period * 30
                undone_dotation_number = (end_date - depreciation_date).days / total_days
            if asset.prorata or asset.method_time == 'end':
                undone_dotation_number += 1
            if posted_depreciation_line_ids:
                add_months = time_period * len(posted_depreciation_line_ids)
                depreciation_date = self.calculate_date(depreciation_date, add_months)
            for x in range(len(posted_depreciation_line_ids), undone_dotation_number):
                i = x + 1
                if i == undone_dotation_number:
                    amount = residual_amount
                else:
                    if asset.method == 'linear':
                        amount = amount_to_depr / (undone_dotation_number - len(posted_depreciation_line_ids))
                        if asset.prorata:
                            amount = amount_to_depr / asset.method_delay
                            if i == 1:
                                days = total_days - float(depreciation_date.strftime('%j'))
                                amount = (amount_to_depr / asset.method_delay) / total_days * days
                            elif i == undone_dotation_number:
                                amount = (amount_to_depr / asset.method_delay) / total_days * (total_days - days)
                    else:
                        amount = residual_amount * asset.method_progress_factor
                residual_amount -= amount
                vals = {
                     'amount': amount,
                     'asset_id': asset.id,
                     'sequence': i,
                     'name': str(asset.id) +'/' + str(i),
                     'remaining_value': residual_amount,
                     'depreciated_value': (asset.purchase_value - asset.salvage_value) - (residual_amount + amount),
                     'depreciation_date': depreciation_date.strftime('%Y-%m-%d'),
                }
                depreciation_lin_obj.create(cr, uid, vals, context=context)
                depreciation_date = self.calculate_date(depreciation_date, time_period)
        return True

    def validate(self, cr, uid, ids, context={}):
        return self.write(cr, uid, ids, {
            'state':'open'
        }, context)

    def _amount_residual(self, cr, uid, ids, name, args, context=None):
        cr.execute("""SELECT
                l.asset_id as id, round(SUM(abs(l.debit-l.credit))) AS amount
            FROM
                account_move_line l
            WHERE
                l.asset_id IN %s GROUP BY l.asset_id """, (tuple(ids),))
        res=dict(cr.fetchall())
        for asset in self.browse(cr, uid, ids, context):
            res[asset.id] = asset.purchase_value - res.get(asset.id, 0.0) - asset.salvage_value
        for id in ids:
            res.setdefault(id, 0.0)
        return res

    _columns = {
        'period_id': fields.many2one('account.period', 'First Period', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'account_move_line_ids': fields.one2many('account.move.line', 'asset_id', 'Entries', readonly=True, states={'draft':[('readonly',False)]}),

        'name': fields.char('Asset', size=64, required=True, select=1),
        'code': fields.char('Reference ', size=16, select=1),
        'purchase_value': fields.float('Gross value ', required=True, size=16, select=1),
        'currency_id': fields.many2one('res.currency','Currency',required=True,size=5,select=1),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'note': fields.text('Note'),
        'category_id': fields.many2one('account.asset.category', 'Asset category',required=True, change_default=True),
        'localisation': fields.char('Localisation', size=32, select=2),
        'parent_id': fields.many2one('account.asset.asset', 'Parent Asset'),
        'child_ids': fields.one2many('account.asset.asset', 'parent_id', 'Children Assets'),
        'purchase_date': fields.date('Purchase Date', required=True),
        'state': fields.selection([('draft','Draft'),('open','Running'),('close','Close')], 'State', required=True),
        'active': fields.boolean('Active', select=2),
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'method': fields.selection([('linear','Linear'),('progressif','Progressive')], 'Computation Method', required=True, readonly=True, states={'draft':[('readonly',False)]}, help="Linear: Calculated on basis of Gross Value/During (interval) \
         \nProgressive: Calculated on basis of Gross Value * Progressif Factor"),
        'method_delay': fields.integer('Number of Depreciation', readonly=True, states={'draft':[('readonly',False)]}, help="Calculates Depreciation within specified interval"),
        'method_period': fields.integer('Period Length', readonly=True, states={'draft':[('readonly',False)]}, help="State here the time during 2 depreciations, in months"),
        'method_end': fields.date('Ending date', readonly=True, states={'draft':[('readonly',False)]}),
        'method_progress_factor': fields.float('Progressif Factor', readonly=True, states={'draft':[('readonly',False)]}),
        'value_residual': fields.function(_amount_residual, method=True, digits_compute=dp.get_precision('Account'), string='Residual Value'),
        'method_time': fields.selection([('delay','Delay'),('end','Ending Period')], 'Time Method', required=True, readonly=True, states={'draft':[('readonly',False)]}, help="Delay: Allow users to enter number of periods to generate depreciation lines \n Ending Period: Calculates depreciation lines on the basis of Ending Period Date and Number of Depreciation"),
        'prorata':fields.boolean('Prorata Temporis', Readonly="True", help='Indicates that the accounting entries for this asset have to be done from the purchase date instead of the first January'),
        'history_ids': fields.one2many('account.asset.history', 'asset_id', 'History', readonly=True),
        'depreciation_line_ids': fields.one2many('account.asset.depreciation.line', 'asset_id', 'Depreciation Lines'),
        'salvage_value': fields.float('Salvage Value', digits_compute=dp.get_precision('Account'), help="It is the amount you plan to have that you cannot depreciate."),
    }
    _defaults = {
        'code': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'account.asset.code'),
        'purchase_date': lambda obj, cr, uid, context: time.strftime('%Y-%m-%d'),
        'active': lambda obj, cr, uid, context: True,
        'state': lambda obj, cr, uid, context: 'draft',
        'period_id': _get_period,
        'method': lambda obj, cr, uid, context: 'linear',
        'method_delay': lambda obj, cr, uid, context: 5,
        'method_time': lambda obj, cr, uid, context: 'delay',
        'method_period': lambda obj, cr, uid, context: 12,
        'method_progress_factor': lambda obj, cr, uid, context: 0.3,
        'currency_id': lambda self,cr,uid,c: self.pool.get('res.users').browse(cr, uid, uid, c).company_id.currency_id.id,
        'company_id': lambda self, cr, uid, context: self.pool.get('res.company')._company_default_get(cr, uid, 'account.asset.asset',context=context),
    }

    def _check_prorata(self, cr, uid, ids, context=None):
        for asset in self.browse(cr, uid, ids, context=context):
            if asset.prorata and (asset.method != 'linear' or asset.method_time != 'delay'):
                return False
        return True

    _constraints = [
        (_check_prorata, '\nProrata temporis can be applied only for computation method linear and time method delay.', ['prorata']),
    ]

    def onchange_category_id(self, cr, uid, ids, category_id, context=None):
        res = {'value':{}}
        asset_categ_obj = self.pool.get('account.asset.category')
        if category_id:
            category_obj = asset_categ_obj.browse(cr, uid, category_id, context=context)
            res['value'] = {
                            'method': category_obj.method,
                            'method_delay': category_obj.method_delay,
                            'method_time': category_obj.method_time,
                            'method_period': category_obj.method_period,
                            'method_progress_factor': category_obj.method_progress_factor,
                            'method_end': category_obj.method_end,
                            'prorata': category_obj.prorata,
            }
        return res

    def onchange_method_time(self, cr, uid, ids, method='linear', method_time='delay', context=None):
        res = {'value': {}}
        if method != 'linear' or method_time != 'delay':
            res['value'] = {'prorata': False}
        return res

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        if context is None:
            context = {}
        default.update({'depreciation_line_ids': [], 'state': 'draft'})
        return super(account_asset_asset, self).copy(cr, uid, id, default, context=context)

    def _compute_period(self, cr, uid, property, context={}):
        if (len(property.entry_asset_ids or [])/2)>=property.method_delay:
            return False
        if len(property.entry_asset_ids):
            cp = property.entry_asset_ids[-1].period_id
            cpid = self.pool.get('account.period').next(cr, uid, cp, property.method_period, context)
            current_period = self.pool.get('account.period').browse(cr, uid, cpid, context)
        else:
            current_period = property.asset_id.period_id
        return current_period

    def _compute_move(self, cr, uid, property, period, context={}):
        #FIXME: fucntion not working OK
        result = []
        total = 0.0
        for move in property.asset_id.entry_ids:
            total += move.debit-move.credit
        for move in property.entry_asset_ids:
            if move.account_id == property.account_asset_ids:
                total += move.debit
                total += -move.credit
        periods = (len(property.entry_asset_ids)/2) - property.method_delay

        if periods==1:
            amount = total
        else:
            if property.method == 'linear':
                amount = total / periods
            else:
                amount = total * property.method_progress_factor

        move_id = self.pool.get('account.move').create(cr, uid, {
            'journal_id': property.journal_id.id,
            'period_id': period.id,
            'name': property.name or property.asset_id.name,
            'ref': property.asset_id.code
        })
        result = [move_id]
        id = self.pool.get('account.move.line').create(cr, uid, {
            'name': property.name or property.asset_id.name,
            'move_id': move_id,
            'account_id': property.account_asset_id.id,
            'debit': amount>0 and amount or 0.0,
            'credit': amount<0 and -amount or 0.0,
            'ref': property.asset_id.code,
            'period_id': period.id,
            'journal_id': property.journal_id.id,
            'partner_id': property.asset_id.partner_id.id,
            'date': time.strftime('%Y-%m-%d'),
        })
        id2 = self.pool.get('account.move.line').create(cr, uid, {
            'name': property.name or property.asset_id.name,
            'move_id': move_id,
            'account_id': property.account_actif_id.id,
            'credit': amount>0 and amount or 0.0,
            'debit': amount<0 and -amount or 0.0,
            'ref': property.asset_id.code,
            'period_id': period.id,
            'journal_id': property.journal_id.id,
            'partner_id': property.asset_id.partner_id.id,
            'date': time.strftime('%Y-%m-%d'),
        })
    #
        self.pool.get('account.asset.asset').write(cr, uid, [property.id], {
            'entry_asset_ids': [(4, id2, False),(4,id,False)]
        })
        if property.method_delay - (len(property.entry_asset_ids)/2)<=1:
            #self.pool.get('account.asset.property')._close(cr, uid, property, context)
            return result
        return result

    def _compute_entries(self, cr, uid, asset, period_id, context={}):
        #FIXME: function not working CHECK all res
        result = []
        date_start = self.pool.get('account.period').browse(cr, uid, period_id, context).date_start
        for property in asset.property_ids:
            if property.state=='open':
                period = self._compute_period(cr, uid, property, context)
                if period and (period.date_start<=date_start):
                    result += self._compute_move(cr, uid, property, period, context)
        return result
account_asset_asset()

class account_asset_depreciation_line(osv.osv):
    _name = 'account.asset.depreciation.line'
    _description = 'Asset depreciation line'

    def _get_move_check(self, cr, uid, ids, name, args, context=None):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = bool(line.move_id)
        return res

    _columns = {
        'name': fields.char('Depreciation Name', size=64, required=True, select=1),
        'sequence': fields.integer('Sequence of the depreciation', required=True),
        'asset_id': fields.many2one('account.asset.asset', 'Asset', required=True),
        'amount': fields.float('Depreciation Amount', required=True),
        'remaining_value': fields.float('Amount to Depreciate', required=True),
        'depreciated_value': fields.float('Amount Already Depreciated', required=True),
        'depreciation_date': fields.char('Depreciation Date', size=64, select=1),
        'move_id': fields.many2one('account.move', 'Depreciation Entry'),
        'move_check': fields.function(_get_move_check, method=True, type='boolean', string='Posted', store=True)
    }

    def create_move(self, cr, uid,ids, context=None):
        if context is None:
            context = {}
        asset_obj = self.pool.get('account.asset.asset')
        period_obj = self.pool.get('account.period')
        move_obj = self.pool.get('account.move')
        move_line_obj = self.pool.get('account.move.line')
        currency_obj = self.pool.get('res.currency')
        for line in self.browse(cr, uid, ids, context=context):
            depreciation_date = line.asset_id.prorata and line.asset_id.purchase_date or time.strftime('%Y-%m-%d')
            period_ids = period_obj.find(cr, uid, depreciation_date, context=context)
            company_currency = line.asset_id.company_id.currency_id.id
            current_currency = line.asset_id.currency_id.id
            context.update({'date': depreciation_date})
            amount = currency_obj.compute(cr, uid, current_currency, company_currency, line.amount, context=context)
            sign = line.asset_id.category_id.journal_id.type = 'purchase' and 1 or -1
            move_vals = {
                'name': line.name,
                'date': depreciation_date,
                'ref': line.name,
                'period_id': period_ids and period_ids[0] or False,
                'journal_id': line.asset_id.category_id.journal_id.id,
                }
            move_id = move_obj.create(cr, uid, move_vals, context=context)
            move_line_obj.create(cr, uid, {
                'name': line.name,
                'ref': line.name,
                'move_id': move_id,
                'account_id': line.asset_id.category_id.account_depreciation_id.id,
                'debit': 0.0,
                'credit': amount,
                'period_id': period_ids and period_ids[0] or False,
                'journal_id': line.asset_id.category_id.journal_id.id,
                'partner_id': line.asset_id.partner_id.id,
                'currency_id': company_currency <> current_currency and  current_currency or False,
                'amount_currency': company_currency <> current_currency and - sign * line.amount or 0.0,
                'date': depreciation_date,
            })
            move_line_obj.create(cr, uid, {
                'name': line.name,
                'ref': line.name,
                'move_id': move_id,
                'account_id': line.asset_id.category_id.account_expense_depreciation_id.id,
                'credit': 0.0,
                'debit': amount,
                'period_id': period_ids and period_ids[0] or False,
                'journal_id': line.asset_id.category_id.journal_id.id,
                'partner_id': line.asset_id.partner_id.id,
                'currency_id': company_currency <> current_currency and  current_currency or False,
                'amount_currency': company_currency <> current_currency and sign * line.amount or 0.0,
                'analytic_account_id': line.asset_id.category_id.account_analytic_id.id,
                'date': depreciation_date,
                'asset_id': line.asset_id.id
            })
            self.write(cr, uid, line.id, {'move_id': move_id}, context=context)
        return True

account_asset_depreciation_line()

#class account_asset_property(osv.osv):
#    def _amount_total(self, cr, uid, ids, name, args, context={}):
#        id_set=",".join(map(str,ids))
#        cr.execute("""SELECT l.asset_id,abs(SUM(l.debit-l.credit)) AS amount FROM
#                account_asset_property p
#            left join
#                account_move_line l on (p.asset_id=l.asset_id)
#            WHERE p.id IN ("""+id_set+") GROUP BY l.asset_id ")
#        res=dict(cr.fetchall())
#        for id in ids:
#            res.setdefault(id, 0.0)
#        return res
#
#    def _close(self, cr, uid, property, context={}):
#        if property.state<>'close':
#            self.pool.get('account.asset.property').write(cr, uid, [property.id], {
#                'state': 'close'
#            })
#            property.state='close'
#        ok = property.asset_id.state=='open'
#        for prop in property.asset_id.property_ids:
#            ok = ok and prop.state=='close'
#        self.pool.get('account.asset.asset').write(cr, uid, [property.asset_id.id], {
#            'state': 'close'
#        }, context)
#        return True
#
#    _name = 'account.asset.property'
#    _description = 'Asset property'
#    _columns = {
#        'name': fields.char('Method name', size=64, select=1),
#        'type': fields.selection([('direct','Direct'),('indirect','Indirect')], 'Depr. method type', select=2, required=True),
#        'asset_id': fields.many2one('account.asset.asset', 'Asset', required=True),
#        'account_asset_id': fields.many2one('account.account', 'Asset account', required=True),
#        'account_actif_id': fields.many2one('account.account', 'Depreciation account', required=True),
#        'journal_id': fields.many2one('account.journal', 'Journal', required=True),
#        'journal_analytic_id': fields.many2one('account.analytic.journal', 'Analytic journal'),
#        'account_analytic_id': fields.many2one('account.analytic.account', 'Analytic account'),
#
#        'method': fields.selection([('linear','Linear'),('progressif','Progressive')], 'Computation method', required=True, readonly=True, states={'draft':[('readonly',False)]}),
#        'method_delay': fields.integer('During', readonly=True, states={'draft':[('readonly',False)]}),
#        'method_period': fields.integer('Depre. all', readonly=True, states={'draft':[('readonly',False)]}),
#        'method_end': fields.date('Ending date'),
#
#        'date': fields.date('Date created'),
#    #'test': fields.one2many('account.pre', 'asset_id',  readonly=True, states={'draft':[('readonly',False)]}),
#        'entry_asset_ids': fields.many2many('account.move.line', 'account_move_asset_entry_rel', 'asset_property_id', 'move_id', 'Asset Entries'),
#        'board_ids': fields.one2many('account.asset.board', 'asset_id', 'Asset board'),
#
#        'value_total': fields.function(_amount_total, method=True, digits=(16,2),string='Gross value'),
#        'state': fields.selection([('draft','Draft'), ('open','Open'), ('close','Close')], 'State', required=True),
#        'history_ids': fields.one2many('account.asset.property.history', 'asset_property_id', 'History', readonly=True)
##    'parent_id': fields.many2one('account.asset.asset', 'Parent asset'),
##    'partner_id': fields.many2one('res.partner', 'Partner'),
##    'note': fields.text('Note'),
#
#    }
#    _defaults = {
#        'type': lambda obj, cr, uid, context: 'direct',
#        'state': lambda obj, cr, uid, context: 'draft',
#        'method': lambda obj, cr, uid, context: 'linear',
#        'method_time': lambda obj, cr, uid, context: 'delay',
#        'method_progress_factor': lambda obj, cr, uid, context: 0.3,
#        'method_delay': lambda obj, cr, uid, context: 5,
#        'method_period': lambda obj, cr, uid, context: 12,
#        'date': lambda obj, cr, uid, context: time.strftime('%Y-%m-%d')
#    }
#account_asset_property()

class account_move_line(osv.osv):
    _inherit = 'account.move.line'
    _columns = {
        'asset_id': fields.many2one('account.asset.asset', 'Asset'),
        'entry_ids': fields.one2many('account.move.line', 'asset_id', 'Entries', readonly=True, states={'draft':[('readonly',False)]}),

    }
account_move_line()

class account_asset_history(osv.osv):
    _name = 'account.asset.history'
    _description = 'Asset history'
    _columns = {
        'name': fields.char('History name', size=64, select=1),
        'user_id': fields.many2one('res.users', 'User', required=True),
        'date': fields.date('Date', required=True),
        'asset_id': fields.many2one('account.asset.asset', 'Asset', required=True),
        'method_delay': fields.integer('Number of interval'),
        'method_period': fields.integer('Period per interval'),
        'method_end': fields.date('Ending date'),
        'note': fields.text('Note'),
    }
    _defaults = {
        'date': lambda *args: time.strftime('%Y-%m-%d'),
        'user_id': lambda self,cr, uid,ctx: uid
    }
account_asset_history()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
