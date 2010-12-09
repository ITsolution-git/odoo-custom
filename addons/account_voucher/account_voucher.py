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
from lxml import etree

import netsvc
from osv import fields
from osv import osv
from tools.translate import _

class account_move_line(osv.osv):
    _inherit = 'account.move.line'

    def _unreconciled(self, cr, uid, ids, prop, unknow_none, context):
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = line.debit - line.credit
            if line.reconcile_partial_id:
                res[line.id] = 0
                for partial in line.reconcile_partial_id.line_partial_ids:
                    res[line.id] += partial.debit - partial.credit
            res[line.id] = abs(res[line.id])
        return res

    _columns = {
        'amount_unreconciled': fields.function(_unreconciled, method=True, string='Unreconciled Amount'),
    }

account_move_line()

class account_voucher(osv.osv):

    def _get_type(self, cr, uid, ids, context={}):
        return context.get('type', False)

    def _get_period(self, cr, uid, context={}):
        if context.get('period_id', False):
            return context.get('period_id')
        periods = self.pool.get('account.period').find(cr, uid)
        return periods and periods[0] or False

    def _get_journal(self, cr, uid, context={}):
        journal_pool = self.pool.get('account.journal')
        if context.get('journal_id', False):
            return context.get('journal_id')
        if not context.get('journal_id', False) and context.get('search_default_journal_id', False):
            return context.get('search_default_journal_id')

        ttype = context.get('type', 'bank')
        if ttype in ('payment', 'receipt'):
            ttype = 'bank'
        res = journal_pool.search(cr, uid, [('type', '=', ttype)], limit=1)
        return res and res[0] or False

    def _get_tax(self, cr, uid, context={}):
        journal_pool = self.pool.get('account.journal')
        journal_id = context.get('journal_id', False)
        if not journal_id:
            ttype = context.get('type', 'bank')
            res = journal_pool.search(cr, uid, [('type', '=', ttype)], limit=1)
            if not res:
                return False
            journal_id = res[0]

        if not journal_id:
            return False
        journal = journal_pool.browse(cr, uid, journal_id)
        account_id = journal.default_credit_account_id or journal.default_debit_account_id
        if account_id and account_id.tax_ids:
            tax_id = account_id.tax_ids[0].id
            return tax_id
        return False

    def _get_currency(self, cr, uid, context):
        journal_pool = self.pool.get('account.journal')
        journal_id = context.get('journal_id', False)
        if journal_id:
            journal = journal_pool.browse(cr, uid, journal_id)
#            currency_id = journal.company_id.currency_id.id
            if journal.currency:
                return journal.currency.id
        return False

    def _get_partner(self, cr, uid, context={}):
        return context.get('partner_id', False)

    def _get_reference(self, cr, uid, context={}):
        return context.get('reference', False)

    def _get_narration(self, cr, uid, context={}):
        return context.get('narration', False)

    def _get_amount(self, cr, uid, context=None):
        if context is None:
            context= {}
        return context.get('amount', 0.0)

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        return [(r['id'], (str("%.2f" % r['amount']) or '')) for r in self.read(cr, uid, ids, ['amount'], context, load='_classic_write')]

    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        mod_obj = self.pool.get('ir.model.data')
        if not view_id and context.get('invoice_type', False):
            if context.get('invoice_type', False) in ('out_invoice', 'out_refund'):
                result = mod_obj.get_object_reference(cr, uid, 'account_voucher', 'view_vendor_receipt_form')
            else:
                result = mod_obj.get_object_reference(cr, uid, 'account_voucher', 'view_vendor_payment_form')
            result = result and result[1] or False
            view_id = result
        if not view_id and context.get('line_type', False):
            if context.get('line_type', False) == 'customer':
                result = mod_obj.get_object_reference(cr, uid, 'account_voucher', 'view_vendor_receipt_form')
            else:
                result = mod_obj.get_object_reference(cr, uid, 'account_voucher', 'view_vendor_payment_form')
            result = result and result[1] or False
            view_id = result

        res = super(account_voucher, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        doc = etree.XML(res['arch'])
        nodes = doc.xpath("//field[@name='partner_id']")
        if context.get('type', 'sale') in ('purchase', 'payment'):
            for node in nodes:
                node.set('domain', "[('supplier', '=', True)]")
            res['arch'] = etree.tostring(doc)
        return res

    def _get_writeoff_amount(self, cr, uid, ids, name, args, context=None):
        if not ids: return {}
        res = {}
        for voucher in self.browse(cr, uid, ids, context=context):
            debit= credit = 0.0
            if voucher.line_dr_ids:
                for line in voucher.line_dr_ids:
                    debit += line.amount_unreconciled
            if voucher.line_cr_ids:
                for line in voucher.line_cr_ids:
                    credit += line.amount_unreconciled
            res[voucher.id] = abs(voucher.amount - abs(credit - debit))
        return res

    _name = 'account.voucher'
    _description = 'Accounting Voucher'
    _order = "date desc, id desc"
#    _rec_name = 'number'
    _columns = {
        'type':fields.selection([
            ('sale','Sale'),
            ('purchase','Purchase'),
            ('payment','Payment'),
            ('receipt','Receipt'),
        ],'Default Type', readonly=True, states={'draft':[('readonly',False)]}),
        'name':fields.char('Memo', size=256, readonly=True, states={'draft':[('readonly',False)]}),
        'date':fields.date('Date', readonly=True, states={'draft':[('readonly',False)]}, help="Effective date for accounting entries"),
        'journal_id':fields.many2one('account.journal', 'Journal', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'account_id':fields.many2one('account.account', 'Account', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'line_ids':fields.one2many('account.voucher.line','voucher_id','Voucher Lines', readonly=True, states={'draft':[('readonly',False)]}),
        'line_cr_ids':fields.one2many('account.voucher.line','voucher_id','Credits',
            domain=[('type','=','cr')], context={'default_type':'cr'}, readonly=True, states={'draft':[('readonly',False)]}),
        'line_dr_ids':fields.one2many('account.voucher.line','voucher_id','Debits',
            domain=[('type','=','dr')], context={'default_type':'dr'}, readonly=True, states={'draft':[('readonly',False)]}),
        'period_id': fields.many2one('account.period', 'Period', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'narration':fields.text('Notes', readonly=True, states={'draft':[('readonly',False)]}),
        'currency_id':fields.many2one('res.currency', 'Currency', readonly=True, states={'draft':[('readonly',False)]}),
#        'currency_id': fields.related('journal_id','currency', type='many2one', relation='res.currency', string='Currency', store=True, readonly=True, states={'draft':[('readonly',False)]}),
        'company_id': fields.many2one('res.company', 'Company', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'state':fields.selection(
            [('draft','Draft'),
             ('proforma','Pro-forma'),
             ('posted','Posted'),
             ('cancel','Cancelled')
            ], 'State', readonly=True, size=32,
            help=' * The \'Draft\' state is used when a user is encoding a new and unconfirmed Voucher. \
                        \n* The \'Pro-forma\' when voucher is in Pro-forma state,voucher does not have an voucher number. \
                        \n* The \'Posted\' state is used when user create voucher,a voucher number is generated and voucher entries are created in account \
                        \n* The \'Cancelled\' state is used when user cancel voucher.'),
        'amount': fields.float('Total', digits=(16, 2), required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'tax_amount':fields.float('Tax Amount', digits=(14,2), readonly=True, states={'draft':[('readonly',False)]}),
        'reference': fields.char('Ref #', size=64, readonly=True, states={'draft':[('readonly',False)]}, help="Transaction reference number."),
        'number': fields.char('Number', size=32, readonly=True,),
        'move_id':fields.many2one('account.move', 'Account Entry'),
        'move_ids': fields.related('move_id','line_id', type='one2many', relation='account.move.line', string='Journal Items', readonly=True),
        'partner_id':fields.many2one('res.partner', 'Partner', change_default=1, readonly=True, states={'draft':[('readonly',False)]}),
        'audit': fields.related('move_id','to_check', type='boolean', relation='account.move', string='Audit Complete ?'),
        'pay_now':fields.selection([
            ('pay_now','Pay Directly'),
            ('pay_later','Pay Later or Group Funds'),
        ],'Payment', select=True, readonly=True, states={'draft':[('readonly',False)]}),
        'tax_id':fields.many2one('account.tax', 'Tax', readonly=True, states={'draft':[('readonly',False)]}),
        'pre_line':fields.boolean('Previous Payments ?', required=False),
        'date_due': fields.date('Due Date', readonly=True, states={'draft':[('readonly',False)]}),
        'payment_option':fields.selection([
                                           ('without_writeoff', 'Without Write-off'),
                                           ('with_writeoff', 'With Write-off'),
                                           ], 'Payment Option', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'writeoff_acc_id': fields.many2one('account.account', 'Write-Off account', readonly=True, states={'draft': [('readonly', False)]}),
        'writeoff_journal_id': fields.many2one('account.journal', 'Write-Off journal', readonly=True, states={'draft': [('readonly', False)]}),
        'comment': fields.char('Comment', size=64, readonly=True, states={'draft': [('readonly', False)]}),
        'analytic_id': fields.many2one('account.analytic.account','Analytic Account', readonly=True, states={'draft': [('readonly', False)]}),
        'writeoff_amount': fields.function(_get_writeoff_amount, method=True, string='Writeoff Amount', type='float', readonly=True),
    }
    _defaults = {
        'period_id': _get_period,
        'partner_id': _get_partner,
        'journal_id':_get_journal,
        'currency_id': _get_currency,
        'reference': _get_reference,
        'narration':_get_narration,
        'amount': _get_amount,
        'type':_get_type,
        'state': 'draft',
        'pay_now': 'pay_later',
        'name': '',
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.voucher',context=c),
        'tax_id': _get_tax,
        'payment_option': 'without_writeoff',
        'comment': 'Write-Off',
    }

    def compute_tax(self, cr, uid, ids, context={}):
        tax_pool = self.pool.get('account.tax')
        partner_pool = self.pool.get('res.partner')
        position_pool = self.pool.get('account.fiscal.position')
        voucher_line_pool = self.pool.get('account.voucher.line')
        voucher_pool = self.pool.get('account.voucher')

        for voucher in voucher_pool.browse(cr, uid, ids, context):
            voucher_amount = 0.0
            for line in voucher.line_ids:
                voucher_amount += line.untax_amount or line.amount
                line.amount = line.untax_amount or line.amount
                voucher_line_pool.write(cr, uid, [line.id], {'amount':line.amount, 'untax_amount':line.untax_amount})

            if not voucher.tax_id:
                self.write(cr, uid, [voucher.id], {'amount':voucher_amount, 'tax_amount':0.0})
                continue

            tax = [tax_pool.browse(cr, uid, voucher.tax_id.id)]
            partner = partner_pool.browse(cr, uid, voucher.partner_id.id) or False
            taxes = position_pool.map_tax(cr, uid, partner and partner.property_account_position or False, tax)
            tax = tax_pool.browse(cr, uid, taxes)

            total = voucher_amount
            total_tax = 0.0

            if not tax[0].price_include:
                for tax_line in tax_pool.compute_all(cr, uid, tax, voucher_amount, 1).get('taxes', []):
                    total_tax += tax_line.get('amount', 0.0)
                total += total_tax
            else:
                for line in voucher.line_ids:
                    line_total = 0.0
                    line_tax = 0.0

                    for tax_line in tax_pool.compute_all(cr, uid, tax, line.untax_amount or line.amount, 1).get('taxes', []):
                        line_tax += tax_line.get('amount', 0.0)
                        line_total += tax_line.get('price_unit')
                    total_tax += line_tax
                    untax_amount = line.untax_amount or line.amount
                    voucher_line_pool.write(cr, uid, [line.id], {'amount':line_total, 'untax_amount':untax_amount})

            self.write(cr, uid, [voucher.id], {'amount':total, 'tax_amount':total_tax})
        return True

    def onchange_price(self, cr, uid, ids, line_ids, tax_id, partner_id=False, context={}):
        tax_pool = self.pool.get('account.tax')
        partner_pool = self.pool.get('res.partner')
        position_pool = self.pool.get('account.fiscal.position')
        res = {
            'tax_amount': False,
            'amount': False,
        }
        voucher_total = 0.0
        voucher_line_ids = []

        total = 0.0
        total_tax = 0.0
        for line in line_ids:
            line_amount = 0.0
            line_amount = line[2] and line[2].get('amount',0.0) or 0.0
            voucher_line_ids += [line[1]]
            voucher_total += line_amount

        total = voucher_total
        total_tax = 0.0
        if tax_id:
            tax = [tax_pool.browse(cr, uid, tax_id)]
            if partner_id:
                partner = partner_pool.browse(cr, uid, partner_id) or False
                taxes = position_pool.map_tax(cr, uid, partner and partner.property_account_position or False, tax)
                tax = tax_pool.browse(cr, uid, taxes)

            if not tax[0].price_include:
                for tax_line in tax_pool.compute_all(cr, uid, tax, voucher_total, 1).get('taxes', []):
                    total_tax += tax_line.get('amount')
                total += total_tax

        res.update({
            'amount':total or voucher_total,
            'tax_amount':total_tax
        })
        return {
            'value':res
        }

    def onchange_term_id(self, cr, uid, ids, term_id, amount):
        term_pool = self.pool.get('account.payment.term')
        terms = False
        due_date = False
        default = {'date_due':False}
        if term_id and amount:
            terms = term_pool.compute(cr, uid, term_id, amount)
        if terms:
            due_date = terms[-1][0]
            default.update({
                'date_due':due_date
            })
        return {'value':default}

    def onchange_journal_voucher(self, cr, uid, ids, line_ids=False, tax_id=False, price=0.0, partner_id=False, journal_id=False, ttype=False, context={}):
        """price
        Returns a dict that contains new values and context

        @param partner_id: latest value from user input for field partner_id
        @param args: other arguments
        @param context: context arguments, like lang, time zone

        @return: Returns a dict which contains new values, and context
        """
        default = {
            'value':{},
        }

        if not partner_id or not journal_id:
            return default

        partner_pool = self.pool.get('res.partner')
        journal_pool = self.pool.get('account.journal')

        journal = journal_pool.browse(cr, uid, journal_id)
        partner = partner_pool.browse(cr, uid, partner_id)
        account_id = False
        tr_type = False
        if journal.type in ('sale','sale_refund'):
            account_id = partner.property_account_receivable.id
            tr_type = 'sale'
        elif journal.type in ('purchase', 'purchase_refund','expense'):
            account_id = partner.property_account_payable.id
            tr_type = 'purchase'
        else:
            account_id = journal.default_credit_account_id.id or journal.default_debit_account_id.id
            tr_type = 'receipt'

        default['value']['account_id'] = account_id
        default['value']['type'] = ttype or tr_type

        vals = self.onchange_journal(cr, uid, ids, journal_id, line_ids, tax_id, partner_id, context)
        default['value'].update(vals.get('value'))

        return default

    def onchange_partner_id(self, cr, uid, ids, partner_id, journal_id, price, currency_id, ttype, context=None):
        """price
        Returns a dict that contains new values and context

        @param partner_id: latest value from user input for field partner_id
        @param args: other arguments
        @param context: context arguments, like lang, time zone

        @return: Returns a dict which contains new values, and context
        """
        if not journal_id:
            return {}

        if context is None:
            context = {}
        currency_pool = self.pool.get('res.currency')
        line_pool = self.pool.get('account.voucher.line')
        move_line_pool = self.pool.get('account.move.line')
        partner_pool = self.pool.get('res.partner')
        journal_pool = self.pool.get('account.journal')

        vals = self.onchange_journal(cr, uid, ids, journal_id, [], False, partner_id, context)
        vals = vals.get('value')
        currency_id = vals.get('currency_id', currency_id)
        default = {
            'value':{'line_ids':[], 'line_dr_ids':[], 'line_cr_ids':[], 'pre_line': False, 'currency_id':currency_id},
        }

        if not partner_id:
            return default

        if not partner_id and ids:
            line_ids = line_pool.search(cr, uid, [('voucher_id', '=', ids[0])])
            if line_ids:
                line_pool.unlink(cr, uid, line_ids)
            return default

        journal = journal_pool.browse(cr, uid, journal_id)
        partner = partner_pool.browse(cr, uid, partner_id)
        account_id = False
        if journal.type in ('sale','sale_refund'):
            account_id = partner.property_account_receivable.id
        elif journal.type in ('purchase', 'purchase_refund','expense'):
            account_id = partner.property_account_payable.id
        else:
            account_id = journal.default_credit_account_id.id or journal.default_debit_account_id.id

        default['value']['account_id'] = account_id

        if journal.type not in ('cash', 'bank'):
            return default

        total_credit = 0.0
        total_debit = 0.0
        account_type = 'receivable'
        if ttype == 'payment':
            account_type = 'payable'
            total_debit = price or 0.0
        else:
            total_credit = price or 0.0
            account_type = 'receivable'

        if not context.get('move_line_ids', False):
            ids = move_line_pool.search(cr, uid, [('state','=','valid'), ('account_id.type', '=', account_type), ('reconcile_id', '=', False), ('partner_id', '=', partner_id)], context=context)
        else:
            ids = context['move_line_ids']
        ids.reverse()
        moves = move_line_pool.browse(cr, uid, ids)

        priority_moves = []
        unpriority_moves = []
        for line in moves:
            original_amount = line.credit or line.debit or 0.0
            if original_amount == price:
                priority_moves.append(line)
            else:
                unpriority_moves.append(line)
        moves = priority_moves + unpriority_moves

        company_currency = journal.company_id.currency_id.id
        if company_currency != currency_id and ttype == 'payment':
            total_debit = currency_pool.compute(cr, uid, currency_id, company_currency, total_debit)
        elif company_currency != currency_id and ttype == 'receipt':
            total_credit = currency_pool.compute(cr, uid, currency_id, company_currency, total_credit)

        for line in moves:
            if line.credit and line.reconcile_partial_id and ttype == 'receipt':
                continue
            if line.debit and line.reconcile_partial_id and ttype == 'payment':
                continue
            total_credit += line.credit or 0.0
            total_debit += line.debit or 0.0

        for line in moves:
            if line.credit and line.reconcile_partial_id and ttype == 'receipt':
                continue
            if line.debit and line.reconcile_partial_id and ttype == 'payment':
                continue

            original_amount = line.credit or line.debit or 0.0
            rs = {
                'name':line.move_id.name,
                'type': line.credit and 'dr' or 'cr',
                'move_line_id':line.id,
                'account_id':line.account_id.id,
                'amount_original':currency_pool.compute(cr, uid, company_currency, currency_id, original_amount),
                'date_original':line.date,
                'date_due':line.date_maturity,
                'amount_unreconciled':currency_pool.compute(cr, uid, company_currency, currency_id, line.amount_unreconciled)
            }
            if line.credit:
                amount = min(line.amount_unreconciled, total_debit)
                rs['amount'] = currency_pool.compute(cr, uid, company_currency, currency_id, amount)
                total_debit -= amount
            else:
                amount = min(line.amount_unreconciled, total_credit)
                rs['amount'] = currency_pool.compute(cr, uid, company_currency, currency_id, amount)
                total_credit -= amount

            default['value']['line_ids'].append(rs)
            if rs['type'] == 'cr':
                default['value']['line_cr_ids'].append(rs)
            else:
                default['value']['line_dr_ids'].append(rs)

            if ttype == 'payment' and len(default['value']['line_cr_ids']) > 0:
                default['value']['pre_line'] = 1
            elif ttype == 'receipt' and len(default['value']['line_dr_ids']) > 0:
                default['value']['pre_line'] = 1
        return default

    def onchange_date(self, cr, user, ids, date, context={}):
        """
        @param date: latest value from user input for field date
        @param args: other arguments
        @param context: context arguments, like lang, time zone
        @return: Returns a dict which contains new values, and context
        """
        period_pool = self.pool.get('account.period')
        pids = period_pool.search(cr, user, [('date_start', '<=', date), ('date_stop', '>=', date)])
        if not pids:
            return {}
        return {
            'value':{
                'period_id':pids[0]
            }
        }

    def onchange_journal(self, cr, uid, ids, journal_id, line_ids, tax_id, partner_id, context={}):
        if not journal_id:
            return False
        journal_pool = self.pool.get('account.journal')
        journal = journal_pool.browse(cr, uid, journal_id)
        account_id = journal.default_credit_account_id or journal.default_debit_account_id
        tax_id = False
        if account_id and account_id.tax_ids:
            tax_id = account_id.tax_ids[0].id

        vals = self.onchange_price(cr, uid, ids, line_ids, tax_id, partner_id, context)
        vals['value'].update({'tax_id':tax_id})
        currency_id = journal.company_id.currency_id.id
        if journal.currency:
            currency_id = journal.currency.id
        vals['value'].update({'currency_id':currency_id})
        return vals

    def proforma_voucher(self, cr, uid, ids, context=None):
        self.action_move_line_create(cr, uid, ids, context=context)
        return True

    def action_cancel_draft(self, cr, uid, ids, context={}):
        wf_service = netsvc.LocalService("workflow")
        for voucher_id in ids:
            wf_service.trg_create(uid, 'account.voucher', voucher_id, cr)
        self.write(cr, uid, ids, {'state':'draft'})
        return True

    def cancel_voucher(self, cr, uid, ids, context={}):
        reconcile_pool = self.pool.get('account.move.reconcile')
        move_pool = self.pool.get('account.move')

        for voucher in self.browse(cr, uid, ids):
            recs = []
            for line in voucher.move_ids:
                if line.reconcile_id:
                    recs += [line.reconcile_id.id]
                if line.reconcile_partial_id:
                    recs += [line.reconcile_partial_id.id]

            reconcile_pool.unlink(cr, uid, recs)

            if voucher.move_id:
                move_pool.button_cancel(cr, uid, [voucher.move_id.id])
                move_pool.unlink(cr, uid, [voucher.move_id.id])
        res = {
            'state':'cancel',
            'move_id':False,
        }
        self.write(cr, uid, ids, res)
        return True

    def unlink(self, cr, uid, ids, context=None):
        for t in self.read(cr, uid, ids, ['state'], context=context):
            if t['state'] not in ('draft', 'cancel'):
                raise osv.except_osv(_('Invalid action !'), _('Cannot delete Voucher(s) which are already opened or paid !'))
        return super(account_voucher, self).unlink(cr, uid, ids, context=context)

    # TODO: may be we can remove this method if not used anyware
    def onchange_payment(self, cr, uid, ids, pay_now, journal_id, partner_id, ttype='sale'):
        res = {}
        if not partner_id:
            return res
        res = {'account_id':False}
        partner_pool = self.pool.get('res.partner')
        journal_pool = self.pool.get('account.journal')
        if pay_now == 'pay_later':
            partner = partner_pool.browse(cr, uid, partner_id)
            journal = journal_pool.browse(cr, uid, journal_id)
            if journal.type in ('sale','sale_refund'):
                account_id = partner.property_account_receivable.id
            elif journal.type in ('purchase', 'purchase_refund','expense'):
                account_id = partner.property_account_payable.id
            else:
                account_id = journal.default_credit_account_id.id or journal.default_debit_account_id.id
            res['account_id'] = account_id
        return {'value':res}

    def action_move_line_create(self, cr, uid, ids, context=None):

        def _get_payment_term_lines(term_id, amount):
            term_pool = self.pool.get('account.payment.term')
            if term_id and amount:
                terms = term_pool.compute(cr, uid, term_id, amount)
                return terms
            return False
        if not context:
            context = {}
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        currency_pool = self.pool.get('res.currency')
        tax_obj = self.pool.get('account.tax')
        seq_obj = self.pool.get('ir.sequence')
        for inv in self.browse(cr, uid, ids):
            if inv.move_id:
                continue
            if inv.number:
                name = inv.number
            elif inv.journal_id.sequence_id:
                name = seq_obj.get_id(cr, uid, inv.journal_id.sequence_id.id)
            else:
                raise osv.except_osv(_('Error !'), _('Please define a sequence on the journal !'))
            if not inv.reference:
                ref = name.replace('/','')
            else:
                ref = inv.reference

            move = {
                'name': name,
                'journal_id': inv.journal_id.id,
                'narration': inv.narration,
                'date': inv.date,
                'ref': ref,
                'period_id': inv.period_id and inv.period_id.id or False
            }
            move_id = move_pool.create(cr, uid, move)

            #create the first line manually
            company_currency = inv.journal_id.company_id.currency_id.id
            current_currency = inv.currency_id.id
            debit = 0.0
            credit = 0.0
            # TODO: is there any other alternative then the voucher type ??
            # -for sale, purchase we have but for the payment and receipt we do not have as based on the bank/cash journal we can not know its payment or receipt
            if inv.type in ('purchase', 'payment'):
                credit = currency_pool.compute(cr, uid, current_currency, company_currency, inv.amount)
            elif inv.type in ('sale', 'receipt'):
                debit = currency_pool.compute(cr, uid, current_currency, company_currency, inv.amount)
            if debit < 0:
                credit = -debit
                debit = 0.0
            if credit < 0:
                debit = -credit
                credit = 0.0
            sign = debit - credit < 0 and -1 or 1
            move_line = {
                'name': inv.name or '/',
                'debit': debit,
                'credit': credit,
                'account_id': inv.account_id.id,
                'move_id': move_id,
                'journal_id': inv.journal_id.id,
                'period_id': inv.period_id.id,
                'partner_id': inv.partner_id.id,
                'currency_id': company_currency <> current_currency and  current_currency or False,
                'amount_currency': company_currency <> current_currency and sign * inv.amount or 0.0,
                'date': inv.date,
                'date_maturity': inv.date_due
            }
            if (debit == 0.0 or credit == 0.0 or debit+credit > 0) and (debit > 0.0 or credit > 0.0):
                master_line = move_line_pool.create(cr, uid, move_line)

            rec_list_ids = []
            line_total = debit - credit
            if inv.type == 'sale':
                line_total = line_total - currency_pool.compute(cr, uid, inv.currency_id.id, company_currency, inv.tax_amount)
            elif inv.type == 'purchase':
                line_total = line_total + currency_pool.compute(cr, uid, inv.currency_id.id, company_currency, inv.tax_amount)

            for line in inv.line_ids:
                if not line.amount:
                    continue
                amount = currency_pool.compute(cr, uid, current_currency, company_currency, line.amount)
                move_line = {
                    'journal_id': inv.journal_id.id,
                    'period_id': inv.period_id.id,
                    'name': line.name and line.name or '/',
                    'account_id': line.account_id.id,
                    'move_id': move_id,
                    'partner_id': inv.partner_id.id,
                    'currency_id': company_currency <> current_currency and current_currency or False,
                    'analytic_account_id': line.account_analytic_id and line.account_analytic_id.id or False,
                    'quantity': 1,
                    'credit': 0.0,
                    'debit': 0.0,
                    'date': inv.date
                }
                if amount < 0:
                    amount = -amount
                    if line.type == 'dr':
                        line.type = 'cr'
                    else:
                        line.type = 'dr'

                if (line.type=='dr'):
                    line_total += amount
                    move_line['debit'] = amount
                else:
                    line_total -= amount
                    move_line['credit'] = amount

                if inv.tax_id and inv.type in ('sale', 'purchase'):
                    move_line.update({
                        'account_tax_id': inv.tax_id.id,
                    })
                if move_line.get('account_tax_id', False):
                    tax_data = tax_obj.browse(cr, uid, [move_line['account_tax_id']], context=context)[0]
                    if not (tax_data.base_code_id and tax_data.tax_code_id):
                        raise osv.except_osv(_('No Account Base Code and Account Tax Code!'),_("You have to configure account base code and account tax code on the '%s' tax!") % (tax_data.name))
                sign = (move_line['debit'] - move_line['credit']) < 0 and -1 or 1
                move_line['amount_currency'] = company_currency <> current_currency and sign * line.amount or 0.0
                master_line = move_line_pool.create(cr, uid, move_line)
                if line.move_line_id.id:
                    rec_ids = [master_line, line.move_line_id.id]
                    rec_list_ids.append(rec_ids)
            writeoff_account_id = False
            writeoff_journal_id = False
            writeoff_period_id = inv.period_id.id,
            comment = False

            if not currency_pool.is_zero(cr, uid, inv.currency_id, line_total):
                diff = line_total
                move_line = {
                    'name': name,
                    'account_id': False,
                    'move_id': move_id,
                    'partner_id': inv.partner_id.id,
                    'date': inv.date,
                    'credit': diff > 0 and diff or 0.0,
                    'debit': diff < 0 and -diff or 0.0,
                    'amount_currency': company_currency <> current_currency and currency_pool.compute(cr, uid, company_currency, current_currency, diff * -1) or 0.0,
                    'currency_id': company_currency <> current_currency and current_currency or False,
                }
                account_id = False
                if inv.type in ('sale', 'receipt'):
#                if inv.journal_id.type in ('sale','sale_refund', 'cash', 'bank'):
                    account_id = inv.partner_id.property_account_receivable.id
                else:
                    account_id = inv.partner_id.property_account_payable.id
                move_line['account_id'] = account_id

                move_line_pool.create(cr, uid, move_line)
            for rec_ids in rec_list_ids:
                if len(rec_ids) >= 2:
                    if inv.payment_option == 'with_writeoff':
                        writeoff_account_id = inv.writeoff_acc_id.id
                        writeoff_journal_id = inv.writeoff_journal_id.id
                        comment = inv.comment
                        move_line_pool.reconcile(cr, uid, rec_ids, 'manual', writeoff_account_id, writeoff_period_id, writeoff_journal_id, context)
                    else:
                        move_line_pool.reconcile_partial(cr, uid, rec_ids)

            self.write(cr, uid, [inv.id], {
                'move_id': move_id,
                'state': 'posted',
                'number': name,
            })
            move_pool.post(cr, uid, [move_id], context={})
        return True

    def copy(self, cr, uid, id, default={}, context=None):
        default.update({
            'state': 'draft',
            'number': False,
            'move_id': False,
            'line_cr_ids': False,
            'line_dr_ids': False,
            'reference': False
        })
        if 'date' not in default:
            default['date'] = time.strftime('%Y-%m-%d')
        return super(account_voucher, self).copy(cr, uid, id, default, context)

account_voucher()

class account_voucher_line(osv.osv):
    _name = 'account.voucher.line'
    _description = 'Voucher Lines'
    _order = "move_line_id"

    def _compute_balance(self, cr, uid, ids, name, args, context=None):
        currency_pool = self.pool.get('res.currency')
        rs_data = {}
        for line in self.browse(cr, uid, ids):
            res = {}
            company_currency = line.voucher_id.journal_id.company_id.currency_id.id
            voucher_currency = line.voucher_id.currency_id.id
            move_line = line.move_line_id or False

            if not move_line:
                res['amount_original'] = 0.0
                res['amount_unreconciled'] = 0.0

            elif move_line and move_line.credit > 0:
                res['amount_original'] = currency_pool.compute(cr, uid, company_currency, voucher_currency, move_line.credit)
            else:
                res['amount_original'] = currency_pool.compute(cr, uid, company_currency, voucher_currency, move_line.debit)

            if move_line:
                res['amount_unreconciled'] = currency_pool.compute(cr, uid, company_currency, voucher_currency, move_line.amount_unreconciled)
            rs_data[line.id] = res
        return rs_data

    _columns = {
        'voucher_id':fields.many2one('account.voucher', 'Voucher', required=1, ondelete='cascade'),
        'name':fields.char('Description', size=256),
        'account_id':fields.many2one('account.account','Account', required=True),
        'partner_id':fields.related('voucher_id', 'partner_id', type='many2one', relation='res.partner', string='Partner'),
        'untax_amount':fields.float('Untax Amount'),
        'amount':fields.float('Amount', digits=(14,2)),
        'type':fields.selection([('dr','Debit'),('cr','Credit')], 'Cr/Dr'),
        'account_analytic_id':  fields.many2one('account.analytic.account', 'Analytic Account'),
        'move_line_id': fields.many2one('account.move.line', 'Journal Item'),
        'date_original': fields.related('move_line_id','date', type='date', relation='account.move.line', string='Date', readonly=1),
        'date_due': fields.related('move_line_id','date_maturity', type='date', relation='account.move.line', string='Due Date', readonly=1),
        'amount_original': fields.function(_compute_balance, method=True, multi='dc', type='float', string='Originial Amount', store=True),
        'amount_unreconciled': fields.function(_compute_balance, method=True, multi='dc', type='float', string='Open Balance', store=True),
        'company_id': fields.related('voucher_id','company_id', relation='res.company', string='Company', store=True),
    }
    _defaults = {
        'name': ''
    }
    def onchange_move_line_id(self, cr, user, ids, move_line_id, context={}):
        """
        Returns a dict that contains new values and context

        @param move_line_id: latest value from user input for field move_line_id
        @param args: other arguments
        @param context: context arguments, like lang, time zone

        @return: Returns a dict which contains new values, and context
        """
        res = {}
        move_line_pool = self.pool.get('account.move.line')
        if move_line_id:
            move_line = move_line_pool.browse(cr, user, move_line_id, context=context)
            if move_line.credit:
                ttype = 'dr'
            else:
                ttype = 'cr'
            account_id = move_line.account_id.id
            res.update({
                'account_id':account_id,
                'type': ttype
            })
        return {
            'value':res,
        }

    def default_get(self, cr, user, fields_list, context=None):
        """
        Returns default values for fields
        @param fields_list: list of fields, for which default values are required to be read
        @param context: context arguments, like lang, time zone

        @return: Returns a dict that contains default values for fields
        """
        journal_id = context.get('journal_id', False)
        partner_id = context.get('partner_id', False)
        journal_pool = self.pool.get('account.journal')
        partner_pool = self.pool.get('res.partner')
        values = super(account_voucher_line, self).default_get(cr, user, fields_list, context=context)
        if (not journal_id) or ('account_id' not in fields_list):
            return values
        journal = journal_pool.browse(cr, user, journal_id)
        account_id = False
        ttype = 'cr'
        if journal.type in ('sale', 'sale_refund'):
            account_id = journal.default_credit_account_id and journal.default_credit_account_id.id or False
            ttype = 'cr'
        elif journal.type in ('purchase', 'expense', 'purchase_refund'):
            account_id = journal.default_debit_account_id and journal.default_debit_account_id.id or False
            ttype = 'dr'
        elif partner_id:
            partner = partner_pool.browse(cr, user, partner_id, context=context)
            if context.get('type') == 'payment':
                ttype = 'dr'
                account_id = partner.property_account_payable.id
            elif context.get('type') == 'receipt':
                account_id = partner.property_account_receivable.id

        values.update({
            'account_id':account_id,
            'type':ttype
        })
        return values
account_voucher_line()

class account_bank_statement(osv.osv):
    _inherit = 'account.bank.statement'

    def button_cancel(self, cr, uid, ids, context=None):
        voucher_obj = self.pool.get('account.voucher')
        for st in self.browse(cr, uid, ids, context):
            voucher_ids = []
            for line in st.line_ids:
                if line.voucher_id:
                    voucher_ids.append(line.voucher_id.id)
            voucher_obj.cancel_voucher(cr, uid, voucher_ids, context)
        return super(account_bank_statement, self).button_cancel(cr, uid, ids, context=context)

    def create_move_from_st_line(self, cr, uid, st_line_id, company_currency_id, next_number, context=None):
        voucher_obj = self.pool.get('account.voucher')
        wf_service = netsvc.LocalService("workflow")
        move_line_obj = self.pool.get('account.move.line')
        bank_st_line_obj = self.pool.get('account.bank.statement.line')
        st_line = bank_st_line_obj.browse(cr, uid, st_line_id, context=context)
        if st_line.voucher_id:
            voucher_obj.write(cr, uid, [st_line.voucher_id.id], {'number': next_number}, context=context)
            if st_line.voucher_id.state == 'cancel':
                voucher_obj.action_cancel_draft(cr, uid, [st_line.voucher_id.id], context=context)
            wf_service.trg_validate(uid, 'account.voucher', st_line.voucher_id.id, 'proforma_voucher', cr)

            v = voucher_obj.browse(cr, uid, st_line.voucher_id.id, context=context)
            bank_st_line_obj.write(cr, uid, [st_line_id], {
                'move_ids': [(4, v.move_id.id, False)]
            })

            return move_line_obj.write(cr, uid, [x.id for x in v.move_ids], {'statement_id': st_line.statement_id.id}, context=context)
        return super(account_bank_statement, self).create_move_from_st_line(cr, uid, st_line.id, company_currency_id, next_number, context=context)

account_bank_statement()

class account_bank_statement_line(osv.osv):
    _inherit = 'account.bank.statement.line'

    def _amount_reconciled(self, cursor, user, ids, name, args, context=None):
        if not ids:
            return {}

        res = {}
#        company_currency_id = False
        for line in self.browse(cursor, user, ids, context=context):
#            if not company_currency_id:
#                company_currency_id = line.company_id.id
            if line.voucher_id:
                res[line.id] = line.voucher_id.amount#
#                        res_currency_obj.compute(cursor, user,
#                        company_currency_id, line.statement_id.currency.id,
#                        line.voucher_id.amount, context=context)
            else:
                res[line.id] = 0.0
        return res

    def _check_amount(self, cr, uid, ids, context=None):
        obj = self.browse(cr, uid, ids[0])
        if obj.voucher_id:
            if not (obj.amount == obj.voucher_id.amount):
                return False
            return True

    _constraints = [
        (_check_amount, 'The amount of the voucher must be the same amount as the one on the statement line', ['statement_id']),
    ]

    _columns = {
        'amount_reconciled': fields.function(_amount_reconciled,
            string='Amount reconciled', method=True, type='float'),
        'voucher_id': fields.many2one('account.voucher', 'Payment'),

    }

    def unlink(self, cr, uid, ids, context=None):
        voucher_obj = self.pool.get('account.voucher')
        statement_line = self.browse(cr, uid, ids, context)
        unlink_ids = []
        for st_line in statement_line:
            if st_line.voucher_id:
                unlink_ids.append(st_line.voucher_id.id)
        voucher_obj.unlink(cr, uid, unlink_ids, context=context)
        return super(account_bank_statement_line, self).unlink(cr, uid, ids, context=context)

account_bank_statement_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: