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

import netsvc
from osv import fields, osv
from tools.translate import _
import decimal_precision as dp
import tools

class account_move_line(osv.osv):
    _name = "account.move.line"
    _description = "Journal Items"

    def _query_get(self, cr, uid, obj='l', context={}):
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        fiscalperiod_obj = self.pool.get('account.period')
        fiscalyear_ids = []
        fiscalperiod_ids = []
        initial_bal = context.get('initial_bal', False)
        company_clause = ""
        if context.get('company_id', False):
            company_clause = " AND " +obj+".company_id = %s" % context.get('company_id', False)
        if not context.get('fiscalyear', False):
            fiscalyear_ids = fiscalyear_obj.search(cr, uid, [('state', '=', 'draft')])
        else:
            if initial_bal:
                fiscalyear_date_start = fiscalyear_obj.read(cr, uid, context['fiscalyear'], ['date_start'])['date_start']
                fiscalyear_ids = fiscalyear_obj.search(cr, uid, [('date_stop', '<', fiscalyear_date_start), ('state', '=', 'draft')], context=context)
            else:
                fiscalyear_ids = [context['fiscalyear']]

        fiscalyear_clause = (','.join([str(x) for x in fiscalyear_ids])) or '0'
        state = context.get('state',False)

        where_move_state = ''
        where_move_lines_by_date = ''

        if context.get('date_from', False) and context.get('date_to', False):
            if initial_bal:
                where_move_lines_by_date = " AND " +obj+".move_id in ( select id from account_move  where date < '"+context['date_from']+"')"
            else:
                where_move_lines_by_date = " AND " +obj+".move_id in ( select id from account_move  where date >= '" +context['date_from']+"' AND date <= '"+context['date_to']+"')"

        if state:
            if state.lower() not in ['all']:
                where_move_state= " AND "+obj+".move_id in (select id from account_move where account_move.state = '"+state+"')"

        if context.get('period_from', False) and context.get('period_to', False) and not context.get('periods', False):
            if initial_bal:
                period_company_id = fiscalperiod_obj.browse(cr, uid, context['period_from'], context=context).company_id.id
                first_period = fiscalperiod_obj.search(cr, uid, [('company_id', '=', period_company_id)], order='date_start', limit=1)[0]
                context['periods'] = fiscalperiod_obj.build_ctx_periods(cr, uid, first_period, context['period_from'])
            else:
                context['periods'] = fiscalperiod_obj.build_ctx_periods(cr, uid, context['period_from'], context['period_to'])
        if context.get('periods', False):
            if initial_bal:
                query = obj+".state<>'draft' AND "+obj+".period_id in (SELECT id from account_period WHERE fiscalyear_id in (%s) %s %s)" % (fiscalyear_clause, where_move_state, where_move_lines_by_date)
                period_ids = fiscalperiod_obj.search(cr, uid, [('id', 'in', context['periods'])], order='date_start', limit=1)
                if period_ids and period_ids[0]:
                    first_period = fiscalperiod_obj.browse(cr, uid, period_ids[0], context=context)
                    # Find the old periods where date start of those periods less then Start period
                    periods = fiscalperiod_obj.search(cr, uid, [('date_start', '<', first_period.date_start)])
                    periods = ','.join([str(x) for x in periods])
                    if periods:
                        query = obj+".state<>'draft' AND "+obj+".period_id in (SELECT id from account_period WHERE fiscalyear_id in (%s) OR id in (%s)) %s %s" % (fiscalyear_clause, periods, where_move_state, where_move_lines_by_date)
            else:
                ids = ','.join([str(x) for x in context['periods']])
                query = obj+".state<>'draft' AND "+obj+".period_id in (SELECT id from account_period WHERE fiscalyear_id in (%s) AND id in (%s)) %s %s" % (fiscalyear_clause, ids, where_move_state, where_move_lines_by_date)
        else:
            query = obj+".state<>'draft' AND "+obj+".period_id in (SELECT id from account_period WHERE fiscalyear_id in (%s) %s %s)" % (fiscalyear_clause,where_move_state,where_move_lines_by_date)

        if context.get('journal_ids', False):
            query += ' AND '+obj+'.journal_id in (%s)' % ','.join(map(str, context['journal_ids']))

        if context.get('chart_account_id', False):
            child_ids = self.pool.get('account.account')._get_children_and_consol(cr, uid, [context['chart_account_id']], context=context)
            query += ' AND '+obj+'.account_id in (%s)' % ','.join(map(str, child_ids))

        query += company_clause

        return query

    def default_get(self, cr, uid, fields, context={}):
        data = self._default_get(cr, uid, fields, context)
        for f in data.keys():
            if f not in fields:
                del data[f]
        return data

    def create_analytic_lines(self, cr, uid, ids, context={}):
        for obj_line in self.browse(cr, uid, ids, context):
            if obj_line.analytic_account_id:
                if not obj_line.journal_id.analytic_journal_id:
                    raise osv.except_osv(_('No Analytic Journal !'),_("You have to define an analytic journal on the '%s' journal!") % (obj_line.journal_id.name,))
                amt = (obj_line.credit or  0.0) - (obj_line.debit or 0.0)
                vals_lines={
                    'name': obj_line.name,
                    'date': obj_line.date,
                    'account_id': obj_line.analytic_account_id.id,
                    'unit_amount':obj_line.quantity,
                    'product_id': obj_line.product_id and obj_line.product_id.id or False,
                    'product_uom_id': obj_line.product_uom_id and obj_line.product_uom_id.id or False,
                    'amount': amt,
                    'general_account_id': obj_line.account_id.id,
                    'journal_id': obj_line.journal_id.analytic_journal_id.id,
                    'ref': obj_line.ref,
                    'move_id':obj_line.id,
                    'user_id': uid
                }
                new_id = self.pool.get('account.analytic.line').create(cr,uid,vals_lines)
        return True

    def _default_get_move_form_hook(self, cursor, user, data):
        '''Called in the end of default_get method for manual entry in account_move form'''
        if data.has_key('analytic_account_id'):
            del(data['analytic_account_id'])
        if data.has_key('account_tax_id'):
            del(data['account_tax_id'])
        return data

    def convert_to_period(self, cr, uid, context={}):
        period_obj = self.pool.get('account.period')

        #check if the period_id changed in the context from client side
        if context.get('period_id', False):
            period_id = context.get('period_id')
            if type(period_id) == str:
                ids = period_obj.search(cr, uid, [('name','ilike',period_id)])
                context.update({
                    'period_id':ids[0]
                })

        return context

    def _default_get(self, cr, uid, fields, context={}):

        if not context.get('journal_id', False) and context.get('search_default_journal_id', False):
            context['journal_id'] = context.get('search_default_journal_id')

        period_obj = self.pool.get('account.period')

        context = self.convert_to_period(cr, uid, context)

        # Compute simple values
        data = super(account_move_line, self).default_get(cr, uid, fields, context)
        # Starts: Manual entry from account.move form
        if context.get('lines',[]):

            total_new=0.00
            for i in context['lines']:
                if i[2]:
                    total_new +=(i[2]['debit'] or 0.00)- (i[2]['credit'] or 0.00)
                    for item in i[2]:
                            data[item]=i[2][item]
            if context['journal']:
                journal_obj=self.pool.get('account.journal').browse(cr, uid, context['journal'])
                if journal_obj.type == 'purchase':
                    if total_new > 0:
                        account = journal_obj.default_credit_account_id
                    else:
                        account = journal_obj.default_debit_account_id
                else:
                    if total_new > 0:
                        account = journal_obj.default_credit_account_id
                    else:
                        account = journal_obj.default_debit_account_id

                if account and ((not fields) or ('debit' in fields) or ('credit' in fields)) and 'partner_id' in data and (data['partner_id']):
                    part = self.pool.get('res.partner').browse(cr, uid, data['partner_id'])
                    account = self.pool.get('account.fiscal.position').map_account(cr, uid, part and part.property_account_position or False, account.id)
                    account = self.pool.get('account.account').browse(cr, uid, account)
                    data['account_id'] =  account.id

            s = -total_new
            data['debit'] = s>0  and s or 0.0
            data['credit'] = s<0  and -s or 0.0
            data = self._default_get_move_form_hook(cr, uid, data)
            return data
        # Ends: Manual entry from account.move form

        if not 'move_id' in fields: #we are not in manual entry
            return data

        # Compute the current move
        move_id = False
        partner_id = False
        if context.get('journal_id', False) and context.get('period_id', False):
            if 'move_id' in fields:
                cr.execute('select move_id \
                    from \
                        account_move_line \
                    where \
                        journal_id=%s and period_id=%s and create_uid=%s and state=%s \
                    order by id desc limit 1',
                    (context['journal_id'], context['period_id'], uid, 'draft'))
                res = cr.fetchone()
                move_id = (res and res[0]) or False

                if not move_id:
                    return data
                else:
                    data['move_id'] = move_id

            if 'date' in fields:
                cr.execute('select date  \
                    from \
                        account_move_line \
                    where \
                        journal_id=%s and period_id=%s and create_uid=%s \
                    order by id desc',
                    (context['journal_id'], context['period_id'], uid))
                res = cr.fetchone()
                if res:
                    data['date'] = res[0]
                else:
                    period = period_obj.browse(cr, uid, context['period_id'],
                            context=context)
                    data['date'] = period.date_start
        if not move_id:
            return data

        total = 0
        ref_id = False
        move = self.pool.get('account.move').browse(cr, uid, move_id, context)
        if 'name' in fields:
            data.setdefault('name', move.line_id[-1].name)
        acc1 = False
        for l in move.line_id:
            acc1 = l.account_id
            partner_id = partner_id or l.partner_id.id
            ref_id = ref_id or l.ref
            total += (l.debit or 0.0) - (l.credit or 0.0)

        if 'ref' in fields:
            data['ref'] = ref_id
        if 'partner_id' in fields:
            data['partner_id'] = partner_id

        if move.journal_id.type == 'purchase':
            if total>0:
                account = move.journal_id.default_credit_account_id
            else:
                account = move.journal_id.default_debit_account_id
        else:
            if total>0:
                account = move.journal_id.default_credit_account_id
            else:
                account = move.journal_id.default_debit_account_id

        part = partner_id and self.pool.get('res.partner').browse(cr, uid, partner_id) or False
        # part = False is acceptable for fiscal position.
        account = self.pool.get('account.fiscal.position').map_account(cr, uid, part and part.property_account_position or False, account.id)
        if account:
            account = self.pool.get('account.account').browse(cr, uid, account)

        if account and ((not fields) or ('debit' in fields) or ('credit' in fields)):
            data['account_id'] = account.id
            # Propose the price VAT excluded, the VAT will be added when confirming line
            if account.tax_ids:
                taxes = self.pool.get('account.fiscal.position').map_tax(cr, uid, part and part.property_account_position or False, account.tax_ids)
                tax = self.pool.get('account.tax').browse(cr, uid, taxes)
                for t in self.pool.get('account.tax').compute_inv(cr, uid, tax, total, 1):
                    total -= t['amount']

        s = -total
        data['debit'] = s>0  and s or 0.0
        data['credit'] = s<0  and -s or 0.0

        if account and account.currency_id:
            data['currency_id'] = account.currency_id.id
            acc = account
            if s>0:
                acc = acc1
            v = self.pool.get('res.currency').compute(cr, uid,
                account.company_id.currency_id.id,
                data['currency_id'],
                s, account=acc, account_invert=True)
            data['amount_currency'] = v
        return data

    def on_create_write(self, cr, uid, id, context={}):
        ml = self.browse(cr, uid, id, context)
        return map(lambda x: x.id, ml.move_id.line_id)

    def _balance(self, cr, uid, ids, name, arg, context=None):
        if context is None:
            context = {}

        c = context.copy()
        c['initital_bal'] = True

        sql = [
            """select l2.id, sum(l1.debit-l1.credit) from account_move_line l1, account_move_line l2""",
            """where l2.account_id=l1.account_id""",
            """and""",
            """l1.id<=l2.id""",
            """and""",
            """l2.id in %s""",
            """and""",
            self._query_get(cr, uid, obj='l1', context=c),
            """ group by l2.id""",
        ]

        cr.execute('\n'.join(sql), [tuple(ids)])
        res = dict(cr.fetchall())
        return res

    def _invoice(self, cursor, user, ids, name, arg, context=None):
        invoice_obj = self.pool.get('account.invoice')
        res = {}
        for line_id in ids:
            res[line_id] = False
        cursor.execute('SELECT l.id, i.id ' \
                        'FROM account_move_line l, account_invoice i ' \
                        'WHERE l.move_id = i.move_id ' \
                        'AND l.id IN %s',
                        (tuple(ids),))
        invoice_ids = []
        for line_id, invoice_id in cursor.fetchall():
            res[line_id] = invoice_id
            invoice_ids.append(invoice_id)
        invoice_names = {False: ''}
        for invoice_id, name in invoice_obj.name_get(cursor, user,
                invoice_ids, context=context):
            invoice_names[invoice_id] = name
        for line_id in res.keys():
            invoice_id = res[line_id]
            res[line_id] = (invoice_id, invoice_names[invoice_id])
        return res

    def name_get(self, cr, uid, ids, context={}):
        if not ids:
            return []
        result = []
        for line in self.browse(cr, uid, ids, context):
            if line.ref:
                result.append((line.id, (line.move_id.name or '')+' ('+line.ref+')'))
            else:
                result.append((line.id, line.move_id.name))
        return result

    def _balance_search(self, cursor, user, obj, name, args, domain=None, context=None):
        if context is None:
            context = {}

        if not args:
            return []
        where = ' and '.join(map(lambda x: '(abs(sum(debit-credit))'+x[1]+str(x[2])+')',args))
        cursor.execute('select id, sum(debit-credit) from account_move_line \
                     group by id, debit, credit having '+where)
        res = cursor.fetchall()
        if not res:
            return [('id', '=', '0')]
        return [('id', 'in', [x[0] for x in res])]

    def _invoice_search(self, cursor, user, obj, name, args, context):
        if not args:
            return []
        invoice_obj = self.pool.get('account.invoice')

        i = 0
        while i < len(args):
            fargs = args[i][0].split('.', 1)
            if len(fargs) > 1:
                args[i] = (fargs[0], 'in', invoice_obj.search(cursor, user,
                    [(fargs[1], args[i][1], args[i][2])]))
                i += 1
                continue
            if isinstance(args[i][2], basestring):
                res_ids = invoice_obj.name_search(cursor, user, args[i][2], [],
                        args[i][1])
                args[i] = (args[i][0], 'in', [x[0] for x in res_ids])
            i += 1
        qu1, qu2 = [], []
        for x in args:
            if x[1] != 'in':
                if (x[2] is False) and (x[1] == '='):
                    qu1.append('(i.id IS NULL)')
                elif (x[2] is False) and (x[1] == '<>' or x[1] == '!='):
                    qu1.append('(i.id IS NOT NULL)')
                else:
                    qu1.append('(i.id %s %s)' % (x[1], '%s'))
                    qu2.append(x[2])
            elif x[1] == 'in':
                if len(x[2]) > 0:
                    qu1.append('(i.id in (%s))' % (','.join(['%s'] * len(x[2]))))
                    qu2 += x[2]
                else:
                    qu1.append(' (False)')
        if qu1:
            qu1 = ' AND' + ' AND'.join(qu1)
        else:
            qu1 = ''
        cursor.execute('SELECT l.id ' \
                'FROM account_move_line l, account_invoice i ' \
                'WHERE l.move_id = i.move_id ' + qu1, qu2)
        res = cursor.fetchall()
        if not res:
            return [('id', '=', '0')]
        return [('id', 'in', [x[0] for x in res])]

    def _get_move_lines(self, cr, uid, ids, context={}):
        result = []
        for move in self.pool.get('account.move').browse(cr, uid, ids, context=context):
            for line in move.line_id:
                result.append(line.id)
        return result

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'quantity': fields.float('Quantity', digits=(16,2), help="The optional quantity expressed by this line, eg: number of product sold. The quantity is not a legal requirement but is very useful for some reports."),
        'product_uom_id': fields.many2one('product.uom', 'UoM'),
        'product_id': fields.many2one('product.product', 'Product'),
        'debit': fields.float('Debit', digits_compute=dp.get_precision('Account')),
        'credit': fields.float('Credit', digits_compute=dp.get_precision('Account')),
        'account_id': fields.many2one('account.account', 'Account', required=True, ondelete="cascade", domain=[('type','<>','view'), ('type', '<>', 'closed')], select=2),
        'move_id': fields.many2one('account.move', 'Move', ondelete="cascade", help="The move of this entry line.", select=2, required=True),
        'narration': fields.related('move_id','narration', type='text', relation='account.move', string='Narration'),
        'ref': fields.related('move_id', 'ref', string='Reference', type='char', size=64, store=True),
        'statement_id': fields.many2one('account.bank.statement', 'Statement', help="The bank statement used for bank reconciliation", select=1),
        'reconcile_id': fields.many2one('account.move.reconcile', 'Reconcile', readonly=True, ondelete='set null', select=2),
        'reconcile_partial_id': fields.many2one('account.move.reconcile', 'Partial Reconcile', readonly=True, ondelete='set null', select=2),
        'amount_currency': fields.float('Amount Currency', help="The amount expressed in an optional other currency if it is a multi-currency entry.", digits_compute=dp.get_precision('Account')),
        'currency_id': fields.many2one('res.currency', 'Currency', help="The optional other currency if it is a multi-currency entry."),

        'period_id': fields.many2one('account.period', 'Period', required=True, select=2),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True, select=1),
        'blocked': fields.boolean('Litigation', help="You can check this box to mark this journal item as a litigation with the associated partner"),

        'partner_id': fields.many2one('res.partner', 'Partner'),
        'date_maturity': fields.date('Due date', help="This field is used for payable and receivable journal entries. You can put the limit date for the payment of this line."),
        'date': fields.related('move_id','date', string='Effective date', type='date', required=True,
            store={
                'account.move': (_get_move_lines, ['date'], 20)
            }),
        'date_created': fields.date('Creation date'),
        'analytic_lines': fields.one2many('account.analytic.line', 'move_id', 'Analytic lines'),
        'centralisation': fields.selection([('normal','Normal'),('credit','Credit Centralisation'),('debit','Debit Centralisation')], 'Centralisation', size=6),
        'balance': fields.function(_balance, fnct_search=_balance_search, method=True, string='Balance'),
        'state': fields.selection([('draft','Unbalanced'), ('valid','Valid')], 'State', readonly=True,
                                  help='When new move line is created the state will be \'Draft\'.\n* When all the payments are done it will be in \'Valid\' state.'),
        'tax_code_id': fields.many2one('account.tax.code', 'Tax Account', help="The Account can either be a base tax code or a tax code account."),
        'tax_amount': fields.float('Tax/Base Amount', digits_compute=dp.get_precision('Account'), select=True, help="If the Tax account is a tax code account, this field will contain the taxed amount.If the tax account is base tax code, "\
                    "this field will contain the basic amount(without tax)."),
        'invoice': fields.function(_invoice, method=True, string='Invoice',
            type='many2one', relation='account.invoice', fnct_search=_invoice_search),
        'account_tax_id':fields.many2one('account.tax', 'Tax'),
        'analytic_account_id': fields.many2one('account.analytic.account', 'Analytic Account'),
        #TODO: remove this
        #'amount_taxed':fields.float("Taxed Amount", digits_compute=dp.get_precision('Account')),
        'company_id': fields.related('account_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True)

    }

    def _get_date(self, cr, uid, context):
        period_obj = self.pool.get('account.period')
        dt = time.strftime('%Y-%m-%d')
        if ('journal_id' in context) and ('period_id' in context):
            cr.execute('select date from account_move_line ' \
                    'where journal_id=%s and period_id=%s ' \
                    'order by id desc limit 1',
                    (context['journal_id'], context['period_id']))
            res = cr.fetchone()
            if res:
                dt = res[0]
            else:
                period = period_obj.browse(cr, uid, context['period_id'],
                        context=context)
                dt = period.date_start
        return dt

    def _get_currency(self, cr, uid, context={}):
        if not context.get('journal_id', False):
            return False
        cur = self.pool.get('account.journal').browse(cr, uid, context['journal_id']).currency
        return cur and cur.id or False

    _defaults = {
        'blocked': lambda *a: False,
        'centralisation': lambda *a: 'normal',
        'date': _get_date,
        'date_created': lambda *a: time.strftime('%Y-%m-%d'),
        'state': lambda *a: 'draft',
        'currency_id': _get_currency,
        'journal_id': lambda self, cr, uid, c: c.get('journal_id', False),
        'period_id': lambda self, cr, uid, c: c.get('period_id', False),
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.move.line', context=c)
    }
    _order = "date desc,id desc"
    _sql_constraints = [
        ('credit_debit1', 'CHECK (credit*debit=0)',  'Wrong credit or debit value in accounting entry !'),
        ('credit_debit2', 'CHECK (credit+debit>=0)', 'Wrong credit or debit value in accounting entry !'),
    ]

    def _auto_init(self, cr, context={}):
        super(account_move_line, self)._auto_init(cr, context)
        cr.execute('SELECT indexname FROM pg_indexes WHERE indexname = \'account_move_line_journal_id_period_id_index\'')
        if not cr.fetchone():
            cr.execute('CREATE INDEX account_move_line_journal_id_period_id_index ON account_move_line (journal_id, period_id)')

    def _check_no_view(self, cr, uid, ids):
        lines = self.browse(cr, uid, ids)
        for l in lines:
            if l.account_id.type == 'view':
                return False
        return True

    def _check_no_closed(self, cr, uid, ids):
        lines = self.browse(cr, uid, ids)
        for l in lines:
            if l.account_id.type == 'closed':
                return False
        return True

    def _check_company_id(self, cr, uid, ids):
        lines = self.browse(cr, uid, ids)
        for l in lines:
            if l.company_id != l.account_id.company_id or l.company_id != l.period_id.company_id:
                return False
        return True

    _constraints = [
        (_check_no_view, 'You can not create move line on view account.', ['account_id']),
        (_check_no_closed, 'You can not create move line on closed account.', ['account_id']),
        (_check_company_id,'Company must be same for its related account and period.',['company_id'] ),
    ]

    #TODO: ONCHANGE_ACCOUNT_ID: set account_tax_id

    def onchange_currency(self, cr, uid, ids, account_id, amount, currency_id, date=False, journal=False):
        if (not currency_id) or (not account_id):
            return {}
        result = {}
        acc =self.pool.get('account.account').browse(cr, uid, account_id)
        if (amount>0) and journal:
            x = self.pool.get('account.journal').browse(cr, uid, journal).default_credit_account_id
            if x: acc = x
        v = self.pool.get('res.currency').compute(cr, uid, currency_id,acc.company_id.currency_id.id, amount, account=acc)
        result['value'] = {
            'debit': v>0 and v or 0.0,
            'credit': v<0 and -v or 0.0
        }
        return result

    def onchange_partner_id(self, cr, uid, ids, move_id, partner_id, account_id=None, debit=0, credit=0, date=False, journal=False):
        val = {}
        val['date_maturity'] = False

        if not partner_id:
            return {'value':val}
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        part = self.pool.get('res.partner').browse(cr, uid, partner_id)

        if part.property_payment_term:
            res = self.pool.get('account.payment.term').compute(cr, uid, part.property_payment_term.id, 100, date)
            if res:
                val['date_maturity'] = res[0][0]
        if not account_id:
            id1 = part.property_account_payable.id
            id2 =  part.property_account_receivable.id
            if journal:
                jt = self.pool.get('account.journal').browse(cr, uid, journal).type
                #FIXME: Bank and cash journal are such a journal we can not assume a account based on this 2 journals
                # Bank and cash journal can have a payment or receipt transaction, and in both type partner account
                # will not be same id payment then payable, and if receipt then receivable
                #if jt in ('sale', 'purchase_refund', 'bank', 'cash'):
                if jt in ('sale', 'purchase_refund'):
                    val['account_id'] = self.pool.get('account.fiscal.position').map_account(cr, uid, part and part.property_account_position or False, id2)
                elif jt in ('purchase', 'sale_refund', 'expense', 'bank', 'cash'):
                    val['account_id'] = self.pool.get('account.fiscal.position').map_account(cr, uid, part and part.property_account_position or False, id1)

                if val.get('account_id', False):
                    d = self.onchange_account_id(cr, uid, ids, val['account_id'])
                    val.update(d['value'])

        return {'value':val}

    def onchange_account_id(self, cr, uid, ids, account_id=False, partner_id=False):
        val = {}
        if account_id:
            res = self.pool.get('account.account').browse(cr, uid, account_id)
            tax_ids = res.tax_ids
            if tax_ids and partner_id:
                part = self.pool.get('res.partner').browse(cr, uid, partner_id)
                tax_id = self.pool.get('account.fiscal.position').map_tax(cr, uid, part and part.property_account_position or False, tax_ids)[0]
            else:
                tax_id = tax_ids and tax_ids[0].id or False
            val['account_tax_id'] = tax_id
        return {'value':val}

    #
    # type: the type if reconciliation (no logic behind this field, for info)
    #
    # writeoff; entry generated for the difference between the lines
    #

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        if context is None:
            context = {}
        if context and context.get('next_partner_only', False):
            if not context.get('partner_id', False):
                partner = self.get_next_partner_only(cr, uid, offset, context)
            else:
                partner = context.get('partner_id', False)
            if not partner:
                return []
            args.append(('partner_id', '=', partner[0]))
        return super(account_move_line, self).search(cr, uid, args, offset, limit, order, context, count)

    def get_next_partner_only(self, cr, uid, offset=0, context=None):
        cr.execute(
             """
             SELECT p.id
             FROM res_partner p
             RIGHT JOIN (
                SELECT l.partner_id as partner_id, SUM(l.debit) as debit, SUM(l.credit) as credit
                FROM account_move_line l
                LEFT JOIN account_account a ON (a.id = l.account_id)
                    LEFT JOIN res_partner p ON (l.partner_id = p.id)
                    WHERE a.reconcile IS TRUE
                    AND l.reconcile_id IS NULL
                    AND (p.last_reconciliation_date IS NULL OR l.date > p.last_reconciliation_date)
                    AND l.state <> 'draft'
                    GROUP BY l.partner_id
                ) AS s ON (p.id = s.partner_id)
                WHERE debit > 0 AND credit > 0
                ORDER BY p.last_reconciliation_date LIMIT 1 OFFSET %s""", (offset,)
            )
        return cr.fetchone()

    def reconcile_partial(self, cr, uid, ids, type='auto', context=None):
        merges = []
        unmerge = []
        total = 0.0
        merges_rec = []

        company_list = []
        if context is None:
            context = {}

        for line in self.browse(cr, uid, ids, context=context):
            if company_list and not line.company_id.id in company_list:
                raise osv.except_osv(_('Warning !'), _('To reconcile the entries company should be the same for all entries'))
            company_list.append(line.company_id.id)

        for line in self.browse(cr, uid, ids, context):
            if line.reconcile_id:
                raise osv.except_osv(_('Warning'), _('Already Reconciled!'))
            if line.reconcile_partial_id:
                for line2 in line.reconcile_partial_id.line_partial_ids:
                    if not line2.reconcile_id:
                        if line2.id not in merges:
                            merges.append(line2.id)
                        total += (line2.debit or 0.0) - (line2.credit or 0.0)
                merges_rec.append(line.reconcile_partial_id.id)
            else:
                unmerge.append(line.id)
                total += (line.debit or 0.0) - (line.credit or 0.0)

        if not total:
            res = self.reconcile(cr, uid, merges+unmerge, context=context)
            return res
        r_id = self.pool.get('account.move.reconcile').create(cr, uid, {
            'type': type,
            'line_partial_ids': map(lambda x: (4,x,False), merges+unmerge)
        })
        self.pool.get('account.move.reconcile').reconcile_partial_check(cr, uid, [r_id] + merges_rec, context=context)
        return True

    def reconcile(self, cr, uid, ids, type='auto', writeoff_acc_id=False, writeoff_period_id=False, writeoff_journal_id=False, context=None):
        lines = self.browse(cr, uid, ids, context=context)
        unrec_lines = filter(lambda x: not x['reconcile_id'], lines)
        credit = debit = 0.0
        currency = 0.0
        account_id = False
        partner_id = False
        if context is None:
            context = {}

        company_list = []
        for line in self.browse(cr, uid, ids, context=context):
            if company_list and not line.company_id.id in company_list:
                raise osv.except_osv(_('Warning !'), _('To reconcile the entries company should be the same for all entries'))
            company_list.append(line.company_id.id)

        for line in unrec_lines:
            if line.state <> 'valid':
                raise osv.except_osv(_('Error'),
                        _('Entry "%s" is not valid !') % line.name)
            credit += line['credit']
            debit += line['debit']
            currency += line['amount_currency'] or 0.0
            account_id = line['account_id']['id']
            partner_id = (line['partner_id'] and line['partner_id']['id']) or False
        writeoff = debit - credit

        # Ifdate_p in context => take this date
        if context.has_key('date_p') and context['date_p']:
            date=context['date_p']
        else:
            date = time.strftime('%Y-%m-%d')

        cr.execute('SELECT account_id, reconcile_id '\
                   'FROM account_move_line '\
                   'WHERE id IN %s '\
                   'GROUP BY account_id,reconcile_id',
                   (tuple(ids),))
        r = cr.fetchall()
        #TODO: move this check to a constraint in the account_move_reconcile object
        if (len(r) != 1) and not context.get('fy_closing', False):
            raise osv.except_osv(_('Error'), _('Entries are not of the same account or already reconciled ! '))
        if not unrec_lines:
            raise osv.except_osv(_('Error'), _('Entry is already reconciled'))
        account = self.pool.get('account.account').browse(cr, uid, account_id, context=context)
        if not context.get('fy_closing', False) and not account.reconcile:
            raise osv.except_osv(_('Error'), _('The account is not defined to be reconciled !'))
        if r[0][1] != None:
            raise osv.except_osv(_('Error'), _('Some entries are already reconciled !'))

        if (not self.pool.get('res.currency').is_zero(cr, uid, account.company_id.currency_id, writeoff)) or \
           (account.currency_id and (not self.pool.get('res.currency').is_zero(cr, uid, account.currency_id, currency))):
            if not writeoff_acc_id:
                raise osv.except_osv(_('Warning'), _('You have to provide an account for the write off entry !'))
            if writeoff > 0:
                debit = writeoff
                credit = 0.0
                self_credit = writeoff
                self_debit = 0.0
            else:
                debit = 0.0
                credit = -writeoff
                self_credit = 0.0
                self_debit = -writeoff

            # If comment exist in context, take it
            if 'comment' in context and context['comment']:
                libelle=context['comment']
            else:
                libelle='Write-Off'

            writeoff_lines = [
                (0, 0, {
                    'name':libelle,
                    'debit':self_debit,
                    'credit':self_credit,
                    'account_id':account_id,
                    'date':date,
                    'partner_id':partner_id,
                    'currency_id': account.currency_id.id or False,
                    'amount_currency': account.currency_id.id and -currency or 0.0
                }),
                (0, 0, {
                    'name':libelle,
                    'debit':debit,
                    'credit':credit,
                    'account_id':writeoff_acc_id,
                    'analytic_account_id': context.get('analytic_id', False),
                    'date':date,
                    'partner_id':partner_id
                })
            ]

            writeoff_move_id = self.pool.get('account.move').create(cr, uid, {
                'period_id': writeoff_period_id,
                'journal_id': writeoff_journal_id,
                'date':date,
                'state': 'draft',
                'line_id': writeoff_lines
            })

            writeoff_line_ids = self.search(cr, uid, [('move_id', '=', writeoff_move_id), ('account_id', '=', account_id)])
            ids += writeoff_line_ids

        r_id = self.pool.get('account.move.reconcile').create(cr, uid, {
            #'name': date,
            'type': type,
            'line_id': map(lambda x: (4,x,False), ids),
            'line_partial_ids': map(lambda x: (3,x,False), ids)
        })
        wf_service = netsvc.LocalService("workflow")
        # the id of the move.reconcile is written in the move.line (self) by the create method above
        # because of the way the line_id are defined: (4, x, False)
        for id in ids:
            wf_service.trg_trigger(uid, 'account.move.line', id, cr)

        if lines and lines[0]:
            partner_id = lines[0].partner_id and lines[0].partner_id.id or False
            if partner_id and context and context.get('stop_reconcile', False):
                self.pool.get('res.partner').write(cr, uid, [partner_id], {'last_reconciliation_date': time.strftime('%Y-%m-%d %H:%M:%S')})
        return r_id

    def view_header_get(self, cr, user, view_id, view_type, context):
        context = self.convert_to_period(cr, user, context)
        if context.get('account_id', False):
            cr.execute('select code from account_account where id=%s', (context['account_id'],))
            res = cr.fetchone()
            res = _('Entries: ')+ (res[0] or '')
            return res
        if (not context.get('journal_id', False)) or (not context.get('period_id', False)):
            return False
        cr.execute('select code from account_journal where id=%s', (context['journal_id'],))
        j = cr.fetchone()[0] or ''
        cr.execute('select code from account_period where id=%s', (context['period_id'],))
        p = cr.fetchone()[0] or ''
        if j or p:
            return j+(p and (':'+p) or '')
        return False

    def onchange_date(self, cr, user, ids, date, context={}):
        """
        Returns a dict that contains new values and context
        @param cr: A database cursor
        @param user: ID of the user currently logged in
        @param date: latest value from user input for field date
        @param args: other arguments
        @param context: context arguments, like lang, time zone
        @return: Returns a dict which contains new values, and context
        """
        res = {}
        period_pool = self.pool.get('account.period')
        pids = period_pool.search(cr, user, [('date_start','<=',date), ('date_stop','>=',date)])
        if pids:
            res.update({
                'period_id':pids[0]
            })
            context.update({
                'period_id':pids[0]
            })
        return {
            'value':res,
            'context':context,
        }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context={}, toolbar=False, submenu=False):
        journal_pool = self.pool.get('account.journal')

        result = super(osv.osv, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar=toolbar, submenu=submenu)
        if view_type != 'tree':
            #Remove the toolbar from the form view
            if view_type == 'form':
                if result.get('toolbar', False):
                    result['toolbar']['action'] = []

            #Restrict the list of journal view in search view
            if view_type == 'search':
                journal_list = journal_pool.name_search(cr, uid, '', [], context=context)
                result['fields']['journal_id']['selection'] = journal_list
            return result

        if context.get('view_mode', False):
            return result

        fld = []
        fields = {}
        flds = []
        title = "Accounting Entries" #self.view_header_get(cr, uid, view_id, view_type, context)
        xml = '''<?xml version="1.0"?>\n<tree string="%s" editable="top" refresh="5" on_write="on_create_write" colors="red:state==\'draft\';black:state==\'valid\'">\n\t''' % (title)

        ids = journal_pool.search(cr, uid, [])
        journals = journal_pool.browse(cr, uid, ids)
        all_journal = [None]
        common_fields = {}
        total = len(journals)
        for journal in journals:
            all_journal.append(journal.id)
            for field in journal.view_id.columns_id:
                if not field.field in fields:
                    fields[field.field] = [journal.id]
                    fld.append((field.field, field.sequence))
                    flds.append(field.field)
                    common_fields[field.field] = 1
                else:
                    fields.get(field.field).append(journal.id)
                    common_fields[field.field] = common_fields[field.field] + 1
        fld.append(('period_id', 3))
        fld.append(('journal_id', 10))
        flds.append('period_id')
        flds.append('journal_id')
        fields['period_id'] = all_journal
        fields['journal_id'] = all_journal
        from operator import itemgetter
        fld = sorted(fld, key=itemgetter(1))

        widths = {
            'statement_id': 50,
            'state': 60,
            'tax_code_id': 50,
            'move_id': 40,
        }

        for field_it in fld:
            field = field_it[0]
            if common_fields.get(field) == total:
                fields.get(field).append(None)

#            if field=='state':
#                state = 'colors="red:state==\'draft\'"'

            attrs = []
            if field == 'debit':
                attrs.append('sum="Total debit"')

            elif field == 'credit':
                attrs.append('sum="Total credit"')

            elif field == 'move_id':
                attrs.append('required="False"')

            elif field == 'account_tax_id':
                attrs.append('domain="[(\'parent_id\',\'=\',False)]"')
                attrs.append("context=\"{'journal_id':journal_id}\"")

            elif field == 'account_id' and journal.id:
                attrs.append('domain="[(\'journal_id\', \'=\', '+str(journal.id)+'),(\'type\',\'&lt;&gt;\',\'view\'), (\'type\',\'&lt;&gt;\',\'closed\')]" on_change="onchange_account_id(account_id, partner_id)"')

            elif field == 'partner_id':
                attrs.append('on_change="onchange_partner_id(move_id, partner_id, account_id, debit, credit, date, journal_id)"')

            elif field == 'journal_id':
                attrs.append("context=\"{'journal_id':journal_id}\"")

            elif field == 'statement_id':
                attrs.append("domain=\"[('state','!=','confirm'),('journal_id.type','=','bank')]\"")

            elif field == 'date':
                attrs.append('on_change="onchange_date(date)"')

            if field in ('amount_currency', 'currency_id'):
                attrs.append('on_change="onchange_currency(account_id, amount_currency,currency_id, date, journal_id)"')
                attrs.append('''attrs="{'readonly':[('state','=','valid')]}"''')

            if field in widths:
                attrs.append('width="'+str(widths[field])+'"')
            attrs.append("invisible=\"context.get('visible_id') not in %s\"" % (fields.get(field)))
            xml += '''<field name="%s" %s/>\n''' % (field,' '.join(attrs))

        xml += '''</tree>'''
        result['arch'] = xml
        result['fields'] = self.fields_get(cr, uid, flds, context)
        return result

    def _check_moves(self, cr, uid, context):
        # use the first move ever created for this journal and period
        cr.execute('select id, state, name from account_move where journal_id=%s and period_id=%s order by id limit 1', (context['journal_id'],context['period_id']))
        res = cr.fetchone()
        if res:
            if res[1] != 'draft':
                raise osv.except_osv(_('UserError'),
                       _('The account move (%s) for centralisation ' \
                                'has been confirmed!') % res[2])
        return res

    def _remove_move_reconcile(self, cr, uid, move_ids=[], context=None):
        # Function remove move rencocile ids related with moves
        obj_move_line = self.pool.get('account.move.line')
        obj_move_rec = self.pool.get('account.move.reconcile')
        unlink_ids = []
        if not move_ids:
            return True
        recs = obj_move_line.read(cr, uid, move_ids, ['reconcile_id','reconcile_partial_id'])
        full_recs = filter(lambda x: x['reconcile_id'], recs)
        rec_ids = [rec['reconcile_id'][0] for rec in full_recs]
        part_recs = filter(lambda x: x['reconcile_partial_id'], recs)
        part_rec_ids = [rec['reconcile_partial_id'][0] for rec in part_recs]
        unlink_ids += rec_ids
        unlink_ids += part_rec_ids
        if unlink_ids:
            obj_move_rec.unlink(cr, uid, unlink_ids)
        return True

    def unlink(self, cr, uid, ids, context={}, check=True):
        self._update_check(cr, uid, ids, context)
        result = False
        for line in self.browse(cr, uid, ids, context):
            context['journal_id']=line.journal_id.id
            context['period_id']=line.period_id.id
            result = super(account_move_line, self).unlink(cr, uid, [line.id], context=context)
            if check:
                self.pool.get('account.move').validate(cr, uid, [line.move_id.id], context=context)
        return result

    def _check_date(self, cr, uid, vals, context=None, check=True):
        if context is None:
            context = {}
        journal_id = False
        if 'date' in vals.keys():
            if 'journal_id' in vals and 'journal_id' not in context:
                journal_id = vals['journal_id']
            if 'period_id' in vals and 'period_id' not in context:
                period_id = vals['period_id']
            elif 'journal_id' not in context and 'move_id' in vals:
                if vals.get('move_id', False):
                    m = self.pool.get('account.move').browse(cr, uid, vals['move_id'])
                    journal_id = m.journal_id.id
                    period_id = m.period_id.id
            else:
                journal_id = context.get('journal_id',False)
                period_id = context.get('period_id',False)
            if journal_id:
                journal = self.pool.get('account.journal').browse(cr, uid, [journal_id])[0]
                if journal.allow_date and period_id:
                    period = self.pool.get('account.period').browse(cr, uid, [period_id])[0]
                    if not time.strptime(vals['date'][:10],'%Y-%m-%d')>=time.strptime(period.date_start,'%Y-%m-%d') or not time.strptime(vals['date'][:10],'%Y-%m-%d')<=time.strptime(period.date_stop,'%Y-%m-%d'):
                        raise osv.except_osv(_('Error'),_('The date of your Journal Entry is not in the defined period!'))
        else:
            return True

    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        if context is None:
            context={}
        if vals.get('account_tax_id', False):
            raise osv.except_osv(_('Unable to change tax !'), _('You can not change the tax, you should remove and recreate lines !'))
        self._check_date(cr, uid, vals, context, check)
        account_obj = self.pool.get('account.account')
        if ('account_id' in vals) and not account_obj.read(cr, uid, vals['account_id'], ['active'])['active']:
            raise osv.except_osv(_('Bad account!'), _('You can not use an inactive account!'))
        if update_check:
            if ('account_id' in vals) or ('journal_id' in vals) or ('period_id' in vals) or ('move_id' in vals) or ('debit' in vals) or ('credit' in vals) or ('date' in vals):
                self._update_check(cr, uid, ids, context)

        todo_date = None
        if vals.get('date', False):
            todo_date = vals['date']
            del vals['date']

        for line in self.browse(cr, uid, ids,context=context):
            ctx = context.copy()
            if ('journal_id' not in ctx):
                if line.move_id:
                   ctx['journal_id'] = line.move_id.journal_id.id
                else:
                    ctx['journal_id'] = line.journal_id.id
            if ('period_id' not in ctx):
                if line.move_id:
                    ctx['period_id'] = line.move_id.period_id.id
                else:
                    ctx['period_id'] = line.period_id.id
            #Check for centralisation
            journal = self.pool.get('account.journal').browse(cr, uid, ctx['journal_id'], context=ctx)
            if journal.centralisation:
                self._check_moves(cr, uid, context=ctx)

        result = super(account_move_line, self).write(cr, uid, ids, vals, context)

        if check:
            done = []
            for line in self.browse(cr, uid, ids):
                if line.move_id.id not in done:
                    done.append(line.move_id.id)
                    self.pool.get('account.move').validate(cr, uid, [line.move_id.id], context)
                    if todo_date:
                        self.pool.get('account.move').write(cr, uid, [line.move_id.id], {'date': todo_date}, context=context)
        return result

    def _update_journal_check(self, cr, uid, journal_id, period_id, context={}):
        cr.execute('select state from account_journal_period where journal_id=%s and period_id=%s', (journal_id, period_id))
        result = cr.fetchall()
        for (state,) in result:
            if state=='done':
                raise osv.except_osv(_('Error !'), _('You can not add/modify entries in a closed journal.'))
        if not result:
            journal = self.pool.get('account.journal').browse(cr, uid, journal_id, context)
            period = self.pool.get('account.period').browse(cr, uid, period_id, context)
            self.pool.get('account.journal.period').create(cr, uid, {
                'name': (journal.code or journal.name)+':'+(period.name or ''),
                'journal_id': journal.id,
                'period_id': period.id
            })
        return True

    def _update_check(self, cr, uid, ids, context={}):
        done = {}
        for line in self.browse(cr, uid, ids, context):
            if line.move_id.state<>'draft':
                raise osv.except_osv(_('Error !'), _('You can not do this modification on a confirmed entry ! Please note that you can just change some non important fields !'))
            if line.reconcile_id:
                raise osv.except_osv(_('Error !'), _('You can not do this modification on a reconciled entry ! Please note that you can just change some non important fields !'))
            t = (line.journal_id.id, line.period_id.id)
            if t not in done:
                self._update_journal_check(cr, uid, line.journal_id.id, line.period_id.id, context)
                done[t] = True
        return True

    def create(self, cr, uid, vals, context=None, check=True):
        account_obj = self.pool.get('account.account')
        tax_obj=self.pool.get('account.tax')
        if context is None:
            context = {}
        self._check_date(cr, uid, vals, context, check)
        if ('account_id' in vals) and not account_obj.read(cr, uid, vals['account_id'], ['active'])['active']:
            raise osv.except_osv(_('Bad account!'), _('You can not use an inactive account!'))
        if 'journal_id' in vals:
            context['journal_id'] = vals['journal_id']
        if 'period_id' in vals:
            context['period_id'] = vals['period_id']
        if ('journal_id' not in context) and ('move_id' in vals) and vals['move_id']:
            m = self.pool.get('account.move').browse(cr, uid, vals['move_id'])
            context['journal_id'] = m.journal_id.id
            context['period_id'] = m.period_id.id

        self._update_journal_check(cr, uid, context['journal_id'], context['period_id'], context)
        move_id = vals.get('move_id', False)
        journal = self.pool.get('account.journal').browse(cr, uid, context['journal_id'])
        is_new_move = False
        if not move_id:
            if journal.centralisation:
                #Check for centralisation
                res = self._check_moves(cr, uid, context)
                if res:
                    vals['move_id'] = res[0]

            if not vals.get('move_id', False):
                if journal.sequence_id:
                    #name = self.pool.get('ir.sequence').get_id(cr, uid, journal.sequence_id.id)
                    v = {
                        'date': vals.get('date', time.strftime('%Y-%m-%d')),
                        'period_id': context['period_id'],
                        'journal_id': context['journal_id']
                    }
                    move_id = self.pool.get('account.move').create(cr, uid, v, context)
                    vals['move_id'] = move_id
                else:
                    raise osv.except_osv(_('No piece number !'), _('Can not create an automatic sequence for this piece !\n\nPut a sequence in the journal definition for automatic numbering or create a sequence manually for this piece.'))
            is_new_move = True

        ok = not (journal.type_control_ids or journal.account_control_ids)
        if ('account_id' in vals):
            account = account_obj.browse(cr, uid, vals['account_id'])
            if journal.type_control_ids:
                type = account.user_type
                for t in journal.type_control_ids:
                    if type.code == t.code:
                        ok = True
                        break
            if journal.account_control_ids and not ok:
                for a in journal.account_control_ids:
                    if a.id == vals['account_id']:
                        ok = True
                        break

            # Automatically convert in the account's secondary currency if there is one and
            # the provided values were not already multi-currency
            if account.currency_id and 'amount_currency' not in vals and account.currency_id.id != account.company_id.currency_id.id:
                vals['currency_id'] = account.currency_id.id
                cur_obj = self.pool.get('res.currency')
                ctx = {}
                if 'date' in vals:
                    ctx['date'] = vals['date']
                vals['amount_currency'] = cur_obj.compute(cr, uid, account.company_id.currency_id.id,
                    account.currency_id.id, vals.get('debit', 0.0)-vals.get('credit', 0.0),
                    context=ctx)
        if not ok:
            raise osv.except_osv(_('Bad account !'), _('You can not use this general account in this journal !'))

        if vals.get('analytic_account_id',False):
            if journal.analytic_journal_id:
                vals['analytic_lines'] = [(0,0, {
                        'name': vals['name'],
                        'date': vals.get('date', time.strftime('%Y-%m-%d')),
                        'account_id': vals.get('analytic_account_id', False),
                        'unit_amount': vals.get('quantity', 1.0),
                        'amount': vals.get('debit', 0.0) or vals.get('credit', 0.0),
                        'general_account_id': vals.get('account_id', False),
                        'journal_id': journal.analytic_journal_id.id,
                        'ref': vals.get('ref', False),
                        'user_id': uid
                    })]

        result = super(osv.osv, self).create(cr, uid, vals, context)
        # CREATE Taxes
        if vals.get('account_tax_id', False):
            tax_id = tax_obj.browse(cr, uid, vals['account_tax_id'])
            total = vals['debit'] - vals['credit']
            if journal.refund_journal:
                base_code = 'ref_base_code_id'
                tax_code = 'ref_tax_code_id'
                account_id = 'account_paid_id'
                base_sign = 'ref_base_sign'
                tax_sign = 'ref_tax_sign'
            else:
                base_code = 'base_code_id'
                tax_code = 'tax_code_id'
                account_id = 'account_collected_id'
                base_sign = 'base_sign'
                tax_sign = 'tax_sign'

            tmp_cnt = 0
            for tax in tax_obj.compute_all(cr, uid, [tax_id], total, 1.00).get('taxes'):
                #create the base movement
                if tmp_cnt == 0:
                    if tax[base_code]:
                        tmp_cnt += 1
                        self.write(cr, uid,[result], {
                            'tax_code_id': tax[base_code],
                            'tax_amount': tax[base_sign] * abs(total)
                        })
                else:
                    data = {
                        'move_id': vals['move_id'],
                        'journal_id': vals['journal_id'],
                        'period_id': vals['period_id'],
                        'name': tools.ustr(vals['name'] or '') + ' ' + tools.ustr(tax['name'] or ''),
                        'date': vals['date'],
                        'partner_id': vals.get('partner_id',False),
                        'ref': vals.get('ref',False),
                        'account_tax_id': False,
                        'tax_code_id': tax[base_code],
                        'tax_amount': tax[base_sign] * abs(total),
                        'account_id': vals['account_id'],
                        'credit': 0.0,
                        'debit': 0.0,
                    }
                    if data['tax_code_id']:
                        self.create(cr, uid, data, context)

                #create the VAT movement
                data = {
                    'move_id': vals['move_id'],
                    'journal_id': vals['journal_id'],
                    'period_id': vals['period_id'],
                    'name': tools.ustr(vals['name'] or '') + ' ' + tools.ustr(tax['name'] or ''),
                    'date': vals['date'],
                    'partner_id': vals.get('partner_id',False),
                    'ref': vals.get('ref',False),
                    'account_tax_id': False,
                    'tax_code_id': tax[tax_code],
                    'tax_amount': tax[tax_sign] * abs(tax['amount']),
                    'account_id': tax[account_id] or vals['account_id'],
                    'credit': tax['amount']<0 and -tax['amount'] or 0.0,
                    'debit': tax['amount']>0 and tax['amount'] or 0.0,
                }
                if data['tax_code_id']:
                    self.create(cr, uid, data, context)
            del vals['account_tax_id']

        if check and ((not context.get('no_store_function')) or journal.entry_posted):
            tmp = self.pool.get('account.move').validate(cr, uid, [vals['move_id']], context)
            if journal.entry_posted and tmp:
                rs = self.pool.get('account.move').button_validate(cr,uid, [vals['move_id']],context)
        return result
account_move_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

