# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2008 PC Solutions (<http://pcsol.be>). All Rights Reserved
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
import time
from mx import DateTime
from decimal import Decimal
from tools.translate import _

class account_cashbox_line(osv.osv):
    
    """ Cash Box Details """
    
    _name = 'account.cashbox.line'
    _description = 'CashBox Line'

    def _sub_total(self, cr, uid, ids, name, arg, context=None):
       
        """ Calculates Sub total
        @param name: Names of fields.
        @param arg: User defined arguments
        @return: Dictionary of values.
        """
        res = {}
        for obj in self.browse(cr, uid, ids):
            res[obj.id] = obj.pieces * obj.number
        return res

    def on_change_sub(self, cr, uid, ids, pieces, number,*a):

        """ Calculates Sub total on change of number
        @param pieces: Names of fields.
        @param number:
        """           
        sub=pieces*number
        return {'value':{'subtotal': sub or 0.0}}

    _columns = {
        'pieces': fields.float('Values', digits=(16,2)),
        'number': fields.integer('Number'),
        'subtotal': fields.function(_sub_total, method=True, string='Sub Total', type='float',digits=(16,2)),
        'starting_id': fields.many2one('account.bank.statement',ondelete='cascade'),
        'ending_id': fields.many2one('account.bank.statement',ondelete='cascade'),
     }
account_cashbox_line()

class account_cash_statement(osv.osv):
    
    _inherit = 'account.bank.statement'
    
    def _get_starting_balance(self, cr, uid, ids, name, arg, context=None):

        """ Find starting balance  "
        @param name: Names of fields.
        @param arg: User defined arguments
        @return: Dictionary of values.
        """          
        res ={}
        for statement in self.browse(cr, uid, ids):
            amount_total=0.0
            for line in statement.starting_details_ids:
                amount_total+= line.pieces * line.number
            res[statement.id]=amount_total
        return res
    
    def _balance_end_cash(self, cr, uid, ids, name, arg, context=None):
        """ Find ending balance  "
        @param name: Names of fields.
        @param arg: User defined arguments
        @return: Dictionary of values.
        """          
        res ={}
        for statement in self.browse(cr, uid, ids):
            amount_total=0.0
            for line in statement.ending_details_ids:
                amount_total+= line.pieces * line.number
            res[statement.id]=amount_total
        return res
        
    def _get_sum_entry_encoding(self, cr, uid, ids, name, arg, context=None):

        """ Find encoding total of statements "
        @param name: Names of fields.
        @param arg: User defined arguments
        @return: Dictionary of values.
        """
        res2={}
        for statement in self.browse(cr, uid, ids):
            encoding_total=0.0
            for line in statement.line_ids:
               encoding_total+= line.amount
            res2[statement.id]=encoding_total
        return res2

    def _default_journal_id(self, cr, uid, context={}):

        """ To get default journal for the object" 
        @param name: Names of fields.
        @return: journal 
        """  
        company_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.id
        journal = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'cash'), ('company_id', '=', company_id)])
        if journal:
            return journal[0]
        else:
            return False
    
    def _end_balance(self, cursor, user, ids, name, attr, context=None):
        res_currency_obj = self.pool.get('res.currency')
        res_users_obj = self.pool.get('res.users')

        res = {}

        company_currency_id = res_users_obj.browse(cursor, user, user,
                context=context).company_id.currency_id.id

        statements = self.browse(cursor, user, ids, context=context)
        for statement in statements:
            res[statement.id] = statement.balance_start
            currency_id = statement.currency.id
            for line in statement.move_line_ids:
                if line.debit > 0:
                    if line.account_id.id == \
                            statement.journal_id.default_debit_account_id.id:
                        res[statement.id] += res_currency_obj.compute(cursor,
                                user, company_currency_id, currency_id,
                                line.debit, context=context)
                else:
                    if line.account_id.id == \
                            statement.journal_id.default_credit_account_id.id:
                        res[statement.id] -= res_currency_obj.compute(cursor,
                                user, company_currency_id, currency_id,
                                line.credit, context=context)
            if statement.state in ('draft', 'open'):
                for line in statement.line_ids:
                    res[statement.id] += line.amount
        for r in res:
            res[r] = round(res[r], 2)
        return res
    
    def _get_company(self, cr, uid, ids, context={}):
        user_pool = self.pool.get('res.users')
        company_pool = self.pool.get('res.company')
        user = user_pool.browse(cr, uid, uid, uid)
        company_id = user.company_id and user.company_id.id
        if not company_id:
            company_id = company_pool.search(cr, uid, [])[0]
        
        return company_id
        
    _columns = {
        'company_id':fields.many2one('res.company', 'Company', required=False),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True),
        'balance_start': fields.function(_get_starting_balance, store=True, method=True, string='Opening Balance', type='float',digits=(16,2), help="Opening balance based on cashBox"),
        'balance_end_real': fields.float('Closing Balance', digits=(16,2), states={'confirm':[('readonly', True)]}, help="closing balance entered by the cashbox verifier"),
        'state': fields.selection(
            [('draft', 'Draft'),
            ('confirm', 'Confirm'),
            ('open','Open')], 'State', required=True, states={'confirm': [('readonly', True)]}, readonly="1"),
        'total_entry_encoding':fields.function(_get_sum_entry_encoding, method=True, store=True, string="Cash Transaction", help="Total cash transactions"),
        'date':fields.datetime("Open On"),
        'closing_date':fields.datetime("Closed On"),
        'balance_end': fields.function(_end_balance, method=True, store=True, string='Balance', help="Closing balance based on transactions"),
        'balance_end_cash': fields.function(_balance_end_cash, method=True, store=True, string='Balance', help="Closing balance based on cashBox"),
        'starting_details_ids': fields.one2many('account.cashbox.line', 'starting_id', string='Opening Cashbox'),
        'ending_details_ids': fields.one2many('account.cashbox.line', 'ending_id', string='Closing Cashbox'),
        'name': fields.char('Name', size=64, required=True, readonly=True),
        'user_id':fields.many2one('res.users', 'Responsible', required=False),
    }
    _defaults = {
        'state': lambda *a: 'draft',
        'name': lambda *a: '/',
        'date': lambda *a:time.strftime("%Y-%m-%d %H:%M:%S"),
        'journal_id': _default_journal_id,
        'user_id': lambda self, cr, uid, context=None: uid,
        'company_id': _get_company
     }

    def create(self, cr, uid, vals, context=None):
        company_id = vals and vals.get('company_id',False)
        if company_id:
            open_jrnl = self.search(cr, uid, [('company_id', '=', vals['company_id']), ('journal_id', '=', vals['journal_id']), ('state', '=', 'open')])
            if open_jrnl:
                raise osv.except_osv('Error', u'Une caisse de type espèce est déjà ouverte')
            if 'starting_details_ids' in vals:
                vals['starting_details_ids'] = starting_details_ids = map(list, vals['starting_details_ids'])
                for i in starting_details_ids:
                    if i and i[0] and i[1]:
                        i[0], i[1] = 0, 0
        res = super(account_cash_statement, self).create(cr, uid, vals, context=context)
        return res
    
    def onchange_journal_id(self, cr, uid, statement_id, journal_id, context={}):
        """ Changes balance start and starting details if journal_id changes" 
        @param statement_id: Changed statement_id
        @param journal_id: Changed journal_id
        @return:  Dictionary of changed values
        """
        
        cash_pool = self.pool.get('account.cashbox.line')
        statement_pool = self.pool.get('account.bank.statement')

        res = {}
        balance_start = 0.0
        
        if not journal_id:
            res.update({
                'balance_start': balance_start
            })
            return res
        
        
        res = super(account_cash_statement, self).onchange_journal_id(cr, uid, statement_id, journal_id, context)
        return res

    def button_open(self, cr, uid, ids, context=None):
        
        """ Changes statement state to Running.
        @return: True 
        """
        cash_pool = self.pool.get('account.cashbox.line')
        statement_pool = self.pool.get('account.bank.statement')

        statement = statement_pool.browse(cr, uid, ids[0])
        number = self.pool.get('ir.sequence').get(cr, uid, 'account.bank.statement')
        
        if len(statement.starting_details_ids) > 0:
            sid = []
            for line in statement.starting_details_ids:
                sid.append(line.id)
            
            cash_pool.unlink(cr, uid, sid)
        
        cr.execute("select id from account_bank_statement where journal_id=%s and user_id=%s and state=%s order by id desc limit 1", (statement.journal_id.id, uid, 'confirm'))
        rs = cr.fetchone()
        rs = rs and rs[0] or None
        if rs:
            statement = statement_pool.browse(cr, uid, rs)
            balance_start = statement.balance_end_real or 0.0
            open_ids = cash_pool.search(cr, uid, [('ending_id','=',statement.id)])
            for sid in open_ids:
                default = {
                    'ending_id': False,
                    'starting_id':ids[0]
                }
                cash_pool.copy(cr, uid, sid, default)
            
        vals = {
            'date':time.strftime("%Y-%m-%d %H:%M:%S"), 
            'state':'open',
            'name':number
        }
        
        self.write(cr, uid, ids, vals)
        return True

    def button_confirm(self, cr, uid, ids, context={}):
        
        """ Check the starting and ending detail of  statement 
        @return: True 
        """
        done = []
        res_currency_obj = self.pool.get('res.currency')
        res_users_obj = self.pool.get('res.users')
        account_move_obj = self.pool.get('account.move')
        account_move_line_obj = self.pool.get('account.move.line')
        account_bank_statement_line_obj = self.pool.get('account.bank.statement.line')

        company_currency_id = res_users_obj.browse(cr, uid, uid, context=context).company_id.currency_id.id

        for st in self.browse(cr, uid, ids, context):
            if not st.state == 'open':
                continue
                
            if st.balance_end != st.balance_end_cash:
                raise osv.except_osv(_('Error !'), _('Cash balance is not matching with closing balance !'))
                
            if not (abs((st.balance_end or 0.0) - st.balance_end_real) < 0.0001):
                raise osv.except_osv(_('Error !'),
                        _('The statement balance is incorrect !\n') +
                        _('The expected balance (%.2f) is different than the computed one. (%.2f)') % (st.balance_end_real, st.balance_end))
            if (not st.journal_id.default_credit_account_id) \
                    or (not st.journal_id.default_debit_account_id):
                raise osv.except_osv(_('Configuration Error !'),
                        _('Please verify that an account is defined in the journal.'))

            for line in st.move_line_ids:
                if line.state <> 'valid':
                    raise osv.except_osv(_('Error !'),
                            _('The account entries lines are not in valid state.'))
            # for bank.statement.lines
            # In line we get reconcile_id on bank.ste.rec.
            # in bank stat.rec we get line_new_ids on bank.stat.rec.line
            for move in st.line_ids:
                context.update({'date':move.date})
                move_id = account_move_obj.create(cr, uid, {
                    'journal_id': st.journal_id.id,
                    'period_id': st.period_id.id,
                    'date': move.date,
                }, context=context)
                account_bank_statement_line_obj.write(cr, uid, [move.id], {
                    'move_ids': [(4,move_id, False)]
                })
                if not move.amount:
                    continue

                torec = []
                if move.amount >= 0:
                    account_id = st.journal_id.default_credit_account_id.id
                else:
                    account_id = st.journal_id.default_debit_account_id.id
                acc_cur = ((move.amount<=0) and st.journal_id.default_debit_account_id) or move.account_id
                amount = res_currency_obj.compute(cr, uid, st.currency.id,
                        company_currency_id, move.amount, context=context,
                        account=acc_cur)
                if move.reconcile_id and move.reconcile_id.line_new_ids:
                    for newline in move.reconcile_id.line_new_ids:
                        amount += newline.amount

                val = {
                    'name': move.name,
                    'date': move.date,
                    'ref': move.ref,
                    'move_id': move_id,
                    'partner_id': ((move.partner_id) and move.partner_id.id) or False,
                    'account_id': (move.account_id) and move.account_id.id,
                    'credit': ((amount>0) and amount) or 0.0,
                    'debit': ((amount<0) and -amount) or 0.0,
                    'statement_id': st.id,
                    'journal_id': st.journal_id.id,
                    'period_id': st.period_id.id,
                    'currency_id': st.currency.id,
                }

                amount = res_currency_obj.compute(cr, uid, st.currency.id,
                        company_currency_id, move.amount, context=context,
                        account=acc_cur)
                if st.currency.id <> company_currency_id:
                    amount_cur = res_currency_obj.compute(cr, uid, company_currency_id,
                                st.currency.id, amount, context=context,
                                account=acc_cur)
                    val['amount_currency'] = -amount_cur

                if move.account_id and move.account_id.currency_id and move.account_id.currency_id.id <> company_currency_id:
                    val['currency_id'] = move.account_id.currency_id.id
                    if company_currency_id==move.account_id.currency_id.id:
                        amount_cur = move.amount
                    else:
                        amount_cur = res_currency_obj.compute(cr, uid, company_currency_id,
                                move.account_id.currency_id.id, amount, context=context,
                                account=acc_cur)
                    val['amount_currency'] = amount_cur

                torec.append(account_move_line_obj.create(cr, uid, val , context=context))

                if move.reconcile_id and move.reconcile_id.line_new_ids:
                    for newline in move.reconcile_id.line_new_ids:
                        account_move_line_obj.create(cr, uid, {
                            'name': newline.name or move.name,
                            'date': move.date,
                            'ref': move.ref,
                            'move_id': move_id,
                            'partner_id': ((move.partner_id) and move.partner_id.id) or False,
                            'account_id': (newline.account_id) and newline.account_id.id,
                            'debit': newline.amount>0 and newline.amount or 0.0,
                            'credit': newline.amount<0 and -newline.amount or 0.0,
                            'statement_id': st.id,
                            'journal_id': st.journal_id.id,
                            'period_id': st.period_id.id,
                            'analytic_account_id':newline.analytic_id and newline.analytic_id.id or False,

                        }, context=context)

                # Fill the secondary amount/currency
                # if currency is not the same than the company
                amount_currency = False
                currency_id = False
                if st.currency.id <> company_currency_id:
                    amount_currency = move.amount
                    currency_id = st.currency.id
                account_move_line_obj.create(cr, uid, {
                    'name': move.name,
                    'date': move.date,
                    'ref': move.ref,
                    'move_id': move_id,
                    'partner_id': ((move.partner_id) and move.partner_id.id) or False,
                    'account_id': account_id,
                    'credit': ((amount < 0) and -amount) or 0.0,
                    'debit': ((amount > 0) and amount) or 0.0,
                    'statement_id': st.id,
                    'journal_id': st.journal_id.id,
                    'period_id': st.period_id.id,
                    'amount_currency': amount_currency,
                    'currency_id': currency_id,
                    }, context=context)

                for line in account_move_line_obj.browse(cr, uid, [x.id for x in
                        account_move_obj.browse(cr, uid, move_id,
                            context=context).line_id],
                        context=context):
                    if line.state <> 'valid':
                        raise osv.except_osv(_('Error !'),
                                _('Ledger Posting line "%s" is not valid') % line.name)

                if move.reconcile_id and move.reconcile_id.line_ids:
                    torec += map(lambda x: x.id, move.reconcile_id.line_ids)
                    #try:
                    if abs(move.reconcile_amount-move.amount)<0.0001:

                        writeoff_acc_id = False
                        #There should only be one write-off account!
                        for entry in move.reconcile_id.line_new_ids:
                            writeoff_acc_id = entry.account_id.id
                            break

                        account_move_line_obj.reconcile(cr, uid, torec, 'statement', writeoff_acc_id=writeoff_acc_id, writeoff_period_id=st.period_id.id, writeoff_journal_id=st.journal_id.id, context=context)
                    else:
                        account_move_line_obj.reconcile_partial(cr, uid, torec, 'statement', context)
                    #except:
                    #    raise osv.except_osv(_('Error !'), _('Unable to reconcile entry "%s": %.2f') % (move.name, move.amount))

                if st.journal_id.entry_posted:
                    account_move_obj.write(cr, uid, [move_id], {'state':'posted'})
            done.append(st.id)
        self.write(cr, uid, done, {'state':'confirm'}, context=context)
        return True

    def button_cancel(self, cr, uid, ids, context={}):
        done = []
        for st in self.browse(cr, uid, ids, context):
            ids = []
            for line in st.line_ids:
                ids += [x.id for x in line.move_ids]
            self.pool.get('account.move').unlink(cr, uid, ids, context)
            done.append(st.id)
        self.write(cr, uid, done, {'state':'draft'}, context=context)
        return True

account_cash_statement()

