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

import time
import netsvc
from osv import fields, osv
from tools.translate import _

import mx.DateTime
from mx.DateTime import RelativeDateTime, now, DateTime, localtime

class account_move_line(osv.osv):
    _name = "account.move.line"
    _description = "Entry lines"

    def _query_get(self, cr, uid, obj='l', context={}):
        fiscalyear_obj = self.pool.get('account.fiscalyear')
        if not context.get('fiscalyear', False):
            fiscalyear_ids = fiscalyear_obj.search(cr, uid, [('state', '=', 'draft')])
            fiscalyear_clause = (','.join([str(x) for x in fiscalyear_ids])) or '0'
        else:
            fiscalyear_clause = '%s' % context['fiscalyear']
        state=context.get('state',False)
        where_move_state=''
        if state:
            if state.lower() not in ['all']:
                where_move_state= " AND "+obj+".move_id in (select id from account_move where account_move.state = '"+state+"')"

        if context.get('periods', False):
            ids = ','.join([str(x) for x in context['periods']])
            return obj+".state<>'draft' AND "+obj+".period_id in (SELECT id from account_period WHERE fiscalyear_id in (%s) AND id in (%s)) %s" % (fiscalyear_clause, ids,where_move_state)
        else:
            return obj+".state<>'draft' AND "+obj+".period_id in (SELECT id from account_period WHERE fiscalyear_id in (%s) %s)" % (fiscalyear_clause,where_move_state)

    def default_get(self, cr, uid, fields, context={}):
        data = self._default_get(cr, uid, fields, context)
        for f in data.keys():
            if f not in fields:
                del data[f]
        return data

    def _default_get(self, cr, uid, fields, context={}):
        # Compute simple values
        data = super(account_move_line, self).default_get(cr, uid, fields, context)

        # Starts: Manual entry from account.move form
        if context.get('lines',[]):

            total_new=0.00
            for i in context['lines']:
                total_new +=(i[2]['debit'] or 0.00)- (i[2]['credit'] or 0.00)
                for item in i[2]:
                        data[item]=i[2][item]
            if context['journal']:
                journal_obj=self.pool.get('account.journal').browse(cr,uid,context['journal'])
                if journal_obj.type == 'purchase':
                    if total_new>0:
                        account = journal_obj.default_credit_account_id
                    else:
                        account = journal_obj.default_debit_account_id
                else:
                    if total_new>0:
                        account = journal_obj.default_credit_account_id
                    else:
                        account = journal_obj.default_debit_account_id
                data['account_id'] = account.id
            s = -total_new
            data['debit'] = s>0  and s or 0.0
            data['credit'] = s<0  and -s or 0.0
            return data
        # Ends: Manual entry from account.move form

        if not 'move_id' in fields: #we are not in manual entry
            return data

        period_obj = self.pool.get('account.period')
        tax_obj=self.pool.get('account.tax')

        # Compute the current move
        move_id = False
        partner_id = False
        if context.get('journal_id',False) and context.get('period_id',False):
            if 'move_id' in fields:
                cr.execute('select move_id \
                    from \
                        account_move_line \
                    where \
                        journal_id=%d and period_id=%d and create_uid=%d and state=%s \
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
                        journal_id=%d and period_id=%d and create_uid=%d \
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

        for l in move.line_id:
            partner_id = partner_id or l.partner_id.id
            ref_id = ref_id or l.ref
            total += (l.debit or 0.0) - (l.credit or 0.0)
            if 'name' in fields:
               data.setdefault('name', l.name)
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

        data['account_id'] = account.id
        if account and account.tax_ids:
            for tax in self.pool.get('account.tax').compute_inv(cr,uid,[account.tax_ids[0]],total,1.00):
                total -= tax['amount']
            data['account_tax_id'] = account.tax_ids[0].id
        s = -total
        data['debit'] = s>0  and s or 0.0
        data['credit'] = s<0  and -s or 0.0
        return data

    def _on_create_write(self, cr, uid, id, context={}):
        ml = self.browse(cr, uid, id, context)
        return map(lambda x: x.id, ml.move_id.line_id)

    def _balance(self, cr, uid, ids, prop, unknow_none, unknow_dict):
        res={}
        # TODO group the foreach in sql
        for id in ids:
            cr.execute('SELECT date,account_id FROM account_move_line WHERE id=%d', (id,))
            dt, acc = cr.fetchone()
            cr.execute('SELECT SUM(debit-credit) FROM account_move_line WHERE account_id=%d AND (date<%s OR (date=%s AND id<=%d))', (acc,dt,dt,id))
            res[id] = cr.fetchone()[0]
        return res

    def _invoice(self, cursor, user, ids, name, arg, context=None):
        invoice_obj = self.pool.get('account.invoice')
        res = {}
        for line_id in ids:
            res[line_id] = False
        cursor.execute('SELECT l.id, i.id ' \
                'FROM account_move_line l, account_invoice i ' \
                'WHERE l.move_id = i.move_id ' \
                    'AND l.id in (' + ','.join([str(x) for x in ids]) + ')')
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
        if not len(ids):
            return []
        result = []
        for line in self.browse(cr, uid, ids, context):
            if line.ref:
                result.append((line.id, (line.name or '')+' ('+line.ref+')'))
            else:
                result.append((line.id, line.name))
        return result

    def _invoice_search(self, cursor, user, obj, name, args):
        if not len(args):
            return []
        invoice_obj = self.pool.get('account.invoice')

        i = 0
        while i < len(args):
            fargs = args[i][0].split('.', 1)
            if len(fargs) > 1:
                args[i] = (frags[0], 'in', invoice_obj.search(cursor, user,
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
                    qu1.append('(i.id %s %s)' % (x[1], '%d'))
                    qu2.append(x[2])
            elif x[1] == 'in':
                if len(x[2]) > 0:
                    qu1.append('(i.id in (%s))' % (','.join(['%d'] * len(x[2]))))
                    qu2 += x[2]
                else:
                    qu1.append(' (False)')
        if len(qu1):
            qu1 = ' AND' + ' AND'.join(qu1)
        else:
            qu1 = ''
        cursor.execute('SELECT l.id ' \
                'FROM account_move_line l, account_invoice i ' \
                'WHERE l.move_id = i.move_id ' + qu1, qu2)
        res = cursor.fetchall()
        if not len(res):
            return [('id', '=', '0')]
        return [('id', 'in', [x[0] for x in res])]

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'quantity': fields.float('Quantity', digits=(16,2), help="The optionnal quantity expressed by this line, eg: number of product sold. The quantity is not a legal requirement but is very usefull for some reports."),
        'debit': fields.float('Debit', digits=(16,2)),
        'credit': fields.float('Credit', digits=(16,2)),
        'account_id': fields.many2one('account.account', 'Account', required=True, ondelete="cascade", domain=[('type','<>','view'), ('type', '<>', 'closed')], select=2),
        'move_id': fields.many2one('account.move', 'Move', ondelete="cascade", states={'valid':[('readonly',True)]}, help="The move of this entry line.", select=2),

        'ref': fields.char('Ref.', size=32),
        'statement_id': fields.many2one('account.bank.statement', 'Statement', help="The bank statement used for bank reconciliation", select=1),
        'reconcile_id': fields.many2one('account.move.reconcile', 'Reconcile', readonly=True, ondelete='set null', select=2),
        'reconcile_partial_id': fields.many2one('account.move.reconcile', 'Partial Reconcile', readonly=True, ondelete='set null', select=2),
        'amount_currency': fields.float('Amount Currency', help="The amount expressed in an optionnal other currency if it is a multi-currency entry."),
        'currency_id': fields.many2one('res.currency', 'Currency', help="The optionnal other currency if it is a multi-currency entry."),

        'period_id': fields.many2one('account.period', 'Period', required=True, select=2),
        'journal_id': fields.many2one('account.journal', 'Journal', required=True, select=1),
        'blocked': fields.boolean('Litigation', help="You can check this box to mark the entry line as a litigation with the associated partner"),

        'partner_id': fields.many2one('res.partner', 'Partner Ref.'),
        'date_maturity': fields.date('Maturity date', help="This field is used for payable and receivable entries. You can put the limit date for the payment of this entry line."),
        'date': fields.date('Effective date', required=True),
        'date_created': fields.date('Creation date'),
        'analytic_lines': fields.one2many('account.analytic.line', 'move_id', 'Analytic lines'),
        'centralisation': fields.selection([('normal','Normal'),('credit','Credit Centralisation'),('debit','Debit Centralisation')], 'Centralisation', size=6),
        'balance': fields.function(_balance, method=True, string='Balance'),
        'state': fields.selection([('draft','Draft'), ('valid','Valid')], 'Status', readonly=True),
        'tax_code_id': fields.many2one('account.tax.code', 'Tax Account'),
        'tax_amount': fields.float('Tax/Base Amount', digits=(16,2), select=True),
        'invoice': fields.function(_invoice, method=True, string='Invoice',
            type='many2one', relation='account.invoice', fnct_search=_invoice_search),
        'account_tax_id':fields.many2one('account.tax', 'Tax'),
        'analytic_account_id' : fields.many2one('account.analytic.account', 'Analytic Account'),
#TODO: remove this
        'amount_taxed':fields.float("Taxed Amount",digits=(16,2)),
    }

    def _get_date(self, cr, uid, context):
        period_obj = self.pool.get('account.period')
        dt = time.strftime('%Y-%m-%d')
        if ('journal_id' in context) and ('period_id' in context):
            cr.execute('select date from account_move_line ' \
                    'where journal_id=%d and period_id=%d ' \
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
    _defaults = {
        'blocked': lambda *a: False,
        'centralisation': lambda *a: 'normal',
        'date': _get_date,
        'date_created': lambda *a: time.strftime('%Y-%m-%d'),
        'state': lambda *a: 'draft',
        'journal_id': lambda self, cr, uid, c: c.get('journal_id', False),
        'period_id': lambda self, cr, uid, c: c.get('period_id', False),
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
            cr.commit()

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

    _constraints = [
        (_check_no_view, 'You can not create move line on view account.', ['account_id']),
        (_check_no_closed, 'You can not create move line on closed account.', ['account_id']),
    ]

    #TODO: ONCHANGE_ACCOUNT_ID: set account_tax_id

    def onchange_partner_id(self, cr, uid, ids, move_id, partner_id, account_id=None, debit=0, credit=0, date=False, journal=False):
        val = {}
        val['date_maturity'] = False

        if not partner_id:
            return {'value':val}
        if not date:
            date = now().strftime('%Y-%m-%d')
        part = self.pool.get('res.partner').browse(cr, uid, partner_id)

        if part.property_payment_term and part.property_payment_term.line_ids:# Compute Maturity Date in val !
                line = part.property_payment_term.line_ids[0]
                next_date = mx.DateTime.strptime(date, '%Y-%m-%d') + RelativeDateTime(days=line.days)
                if line.condition == 'end of month':
                    next_date += RelativeDateTime(day=-1)
                next_date = next_date.strftime('%Y-%m-%d')
                val['date_maturity'] = next_date
        if not account_id:
            id1 = part.property_account_payable.id
            id2 =  part.property_account_receivable.id
            if journal:
                jt = self.pool.get('account.journal').browse(cr, uid, journal).type
                if jt=='sale':
                    val['account_id'] =  id2
                elif jt=='purchase':
                    val['account_id'] =  id1
        return {'value':val}

    #
    # type: the type if reconciliation (no logic behind this field, for info)
    #
    # writeoff; entry generated for the difference between the lines
    #

    def reconcile_partial(self, cr, uid, ids, type='auto', context={}):
        merges = []
        unmerge = []
        total = 0.0
        merges_rec = []
        for line in self.browse(cr, uid, ids, context):
            if line.reconcile_id:
                raise _('Already Reconciled')
            if line.reconcile_partial_id:
                for line2 in line.reconcile_partial_id.line_partial_ids:
                    if not line2.reconcile_id:
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

    def reconcile(self, cr, uid, ids, type='auto', writeoff_acc_id=False, writeoff_period_id=False, writeoff_journal_id=False, context={}):
        id_set = ','.join(map(str, ids))
        lines = self.browse(cr, uid, ids, context=context)
        unrec_lines = filter(lambda x: not x['reconcile_id'], lines)
        credit = debit = 0.0
        currency = 0.0
        account_id = False
        partner_id = False
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

        cr.execute('SELECT account_id, reconcile_id \
                FROM account_move_line \
                WHERE id IN ('+id_set+') \
                GROUP BY account_id,reconcile_id')
        r = cr.fetchall()
#TODO: move this check to a constraint in the account_move_reconcile object
        if len(r) != 1:
            raise osv.except_osv(_('Error'), _('Entries are not of the same account or already reconciled ! '))
        account = self.pool.get('account.account').browse(cr, uid, account_id, context=context)
        if not account.reconcile:
            raise osv.except_osv(_('Error'), _('The account is not defined to be reconcile !'))
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
            if context['comment']:
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
                    'date':date,
                    'partner_id':partner_id
                })
            ]

            name = 'Write-Off'
            if writeoff_journal_id:
                journal = self.pool.get('account.journal').browse(cr, uid, writeoff_journal_id)
                if journal.sequence_id:
                    name = self.pool.get('ir.sequence').get_id(cr, uid, journal.sequence_id.id)

            writeoff_move_id = self.pool.get('account.move').create(cr, uid, {
                'name': name,
                'period_id': writeoff_period_id,
                'journal_id': writeoff_journal_id,

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
        # the id of the move.reconcile is written in the move.line (self) by the create method above
        # because of the way the line_id are defined: (4, x, False)
        wf_service = netsvc.LocalService("workflow")
        for id in ids:
            wf_service.trg_trigger(uid, 'account.move.line', id, cr)
        return r_id

    def view_header_get(self, cr, user, view_id, view_type, context):
        if context.get('account_id', False):
            cr.execute('select code from account_account where id=%d', (context['account_id'],))
            res = cr.fetchone()
            res = _('Entries: ')+ (res[0] or '')
            return res
        if (not context.get('journal_id', False)) or (not context.get('period_id', False)):
            return False
        cr.execute('select code from account_journal where id=%d', (context['journal_id'],))
        j = cr.fetchone()[0] or ''
        cr.execute('select code from account_period where id=%d', (context['period_id'],))
        p = cr.fetchone()[0] or ''
        if j or p:
            return j+(p and (':'+p) or '')
        return False

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context={}, toolbar=False):
        result = super(osv.osv, self).fields_view_get(cr, uid, view_id,view_type,context)
        if view_type=='tree' and 'journal_id' in context:
            title = self.view_header_get(cr, uid, view_id, view_type, context)
            journal = self.pool.get('account.journal').browse(cr, uid, context['journal_id'])

            # if the journal view has a state field, color lines depending on
            # its value
            state = ''
            for field in journal.view_id.columns_id:
                if field.field=='state':
                    state = ' colors="red:state==\'draft\'"'

            #xml = '''<?xml version="1.0"?>\n<tree string="%s" editable="top" refresh="5"%s>\n\t''' % (title, state)
            xml = '''<?xml version="1.0"?>\n<tree string="%s" editable="top" refresh="5" on_write="_on_create_write"%s>\n\t''' % (title, state)
            fields = []

            widths = {
                'ref': 50,
                'statement_id': 50,
                'state': 60,
                'tax_code_id': 50,
                'move_id': 40,
            }
            for field in journal.view_id.columns_id:
                fields.append(field.field)
                attrs = []
                if field.field=='debit':
                    attrs.append('sum="Total debit"')
                elif field.field=='credit':
                    attrs.append('sum="Total credit"')
                elif field.field=='account_id' and journal.id:
                    attrs.append('domain="[(\'journal_id\', \'=\', '+str(journal.id)+'),(\'type\',\'&lt;&gt;\',\'view\'), (\'type\',\'&lt;&gt;\',\'closed\')]"')
                if field.readonly:
                    attrs.append('readonly="1"')
                if field.required:
                    attrs.append('required="1"')
                else:
                    attrs.append('required="0"')
                if field.field == 'partner_id':
                    attrs.append('on_change="onchange_partner_id(move_id,partner_id,account_id,debit,credit,((\'journal_id\' in context) and context[\'journal_id\']) or {})"')
                if field.field in widths:
                    attrs.append('width="'+str(widths[field.field])+'"')
                xml += '''<field name="%s" %s/>\n''' % (field.field,' '.join(attrs))

            xml += '''</tree>'''
            result['arch'] = xml
            result['fields'] = self.fields_get(cr, uid, fields, context)
        return result

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

    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        if not context:
            context={}
        raise_ex=False

        if ('debit' in vals and 'credit' in vals)  and not vals['debit'] and not vals['credit']:
            raise_ex=True
        if ('debit' in vals and 'credit' not in vals) and  not vals['debit']:
            raise_ex=True
        if ('credit' in vals and 'debit' not in vals) and  not vals['credit']:
            raise_ex=True

        if raise_ex:
            raise osv.except_osv(_('Wrong Accounting Entry!'), _('Both Credit and Debit cannot be zero!'))

        if ('account_id' in vals) and not account_obj.read(cr, uid, vals['account_id'], ['active'])['active']:
            raise osv.except_osv(_('Bad account!'), _('You can not use an inactive account!'))
        if update_check:
            if ('account_id' in vals) or ('journal_id' in vals) or ('period_id' in vals) or ('move_id' in vals) or ('debit' in vals) or ('credit' in vals) or ('date' in vals):
                self._update_check(cr, uid, ids, context)
        result = super(osv.osv, self).write(cr, uid, ids, vals, context)
        if check:
            done = []
            for line in self.browse(cr, uid, ids):
                if line.move_id.id not in done:
                    done.append(line.move_id.id)
                    self.pool.get('account.move').validate(cr, uid, [line.move_id.id], context)
        return result

    def _update_journal_check(self, cr, uid, journal_id, period_id, context={}):
        cr.execute('select state from account_journal_period where journal_id=%d and period_id=%d', (journal_id, period_id))
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
        if not context:
            context={}
        account_obj = self.pool.get('account.account')
        tax_obj=self.pool.get('account.tax')

        if ('account_id' in vals) and not account_obj.read(cr, uid, vals['account_id'], ['active'])['active']:
            raise osv.except_osv(_('Bad account!'), _('You can not use an inactive account!'))
        if 'journal_id' in vals and 'journal_id' not in context:
            context['journal_id'] = vals['journal_id']
        if 'period_id' in vals and 'period_id' not in context:
            context['period_id'] = vals['period_id']
        if 'journal_id' not in context and 'move_id' in vals:
            m = self.pool.get('account.move').browse(cr, uid, vals['move_id'])
            context['journal_id'] = m.journal_id.id
            context['period_id'] = m.period_id.id

        self._update_journal_check(cr, uid, context['journal_id'], context['period_id'], context)

        move_id = vals.get('move_id', False)
        journal = self.pool.get('account.journal').browse(cr, uid, context['journal_id'])
        if not move_id:
            if journal.centralisation:
                # use the first move ever created for this journal and period
                cr.execute('select id, state, name from account_move where journal_id=%d and period_id=%d order by id limit 1', (context['journal_id'],context['period_id']))
                res = cr.fetchone()
                if res:
                    if res[1] != 'draft':
                        raise osv.except_osv(_('UserError'),
                                _('The account move (%s) for centralisation ' \
                                        'has been confirmed!') % res[2])
                    vals['move_id'] = res[0]

            if not vals.get('move_id', False):
                if journal.sequence_id:
                    name = self.pool.get('ir.sequence').get_id(cr, uid, journal.sequence_id.id)
                    v = {
                        'name': name,
                        'period_id': context['period_id'],
                        'journal_id': context['journal_id']
                    }
                    move_id = self.pool.get('account.move').create(cr, uid, v, context)
                    vals['move_id'] = move_id
                else:
                    raise osv.except_osv(_('No piece number !'), _('Can not create an automatic sequence for this piece !\n\nPut a sequence in the journal definition for automatic numbering or create a sequence manually for this piece.'))

        ok = not (journal.type_control_ids or journal.account_control_ids)
        if ('account_id' in vals):
            account = account_obj.browse(cr, uid, vals['account_id'])
            if journal.type_control_ids:
                type = account.user_type
                for t in journal.type_control_ids:
                    if type==t.code:
                        ok = True
                        break
            if journal.account_control_ids and not ok:
                for a in journal.account_control_ids:
                    if a.id==vals['account_id']:
                        ok = True
                        break
            if (account.currency_id) and 'amount_currency' not in vals:
                vals['currency_id'] = account.currency_id.id
                cur_obj = self.pool.get('res.currency')
                ctx = {}
                if 'date' in vals:
                    ctx['date'] = vals['date']
                vals['amount_currency'] = cur_obj.compute(cr, uid, account.company_id.currency_id.id, account.currency_id.id, vals.get('debit', 0.0)-vals.get('credit', 0.0), context=ctx)
        if not ok:
            raise osv.except_osv(_('Bad account !'), _('You can not use this general account in this journal !'))

        result = super(osv.osv, self).create(cr, uid, vals, context)
        if 'analytic_account_id' in vals and vals['analytic_account_id']:
            if journal.analytic_journal_id:
                vals['analytic_lines'] = [(0,0, {
                        'name': vals['name'],
                        'date': vals['date'],
                        'account_id': vals['analytic_account_id'],
                        'unit_amount': vals['quantity'],
                        'amount': vals['debit'] or vals['credit'],
                        'general_account_id': vals['account_id'],
                        'journal_id': journal.analytic_journal_id.id,
                        'ref': vals['ref'],
                    })]

        # CREATE Taxes
        if 'account_tax_id' in vals and vals['account_tax_id']:
            tax_id=tax_obj.browse(cr,uid,vals['account_tax_id'])
            total = vals['credit'] or (-vals['debit'])
            for tax in tax_obj.compute(cr,uid,[tax_id],total,1.00):
                self.write(cr, uid,[result], {
                    'tax_code_id': tax['base_code_id'],
                    'tax_amount': tax['base_sign'] * total
                })
                data = {
                    'move_id': vals['move_id'],
                    'journal_id': vals['journal_id'],
                    'period_id': vals['period_id'],
                    'name': vals['name']+' '+tax['name'],
                    'date': vals['date'],
                    'partner_id': vals.get('partner_id',False),
                    'ref': vals.get('ref',False),
                    'account_tax_id': False,
                    'tax_code_id': tax['tax_code_id'],
                    'tax_amount': tax['tax_sign'] * tax['amount'],
                    'account_id': tax['account_paid_id'], # or collected ?
                    'credit': tax['amount']>0 and tax['amount'] or 0.0,
                    'debit': tax['amount']<0 and -tax['amount'] or 0.0,
                }
                self.create(cr, uid, data, context)
        if check:
            tmp = self.pool.get('account.move').validate(cr, uid, [vals['move_id']], context)
            if journal.entry_posted and tmp:
                self.pool.get('account.move').write(cr,uid, [vals['move_id']],{'state':'posted'})
        return result
account_move_line()


class account_bank_statement_reconcile(osv.osv):
    _inherit = "account.bank.statement.reconcile"
    _columns = {
        'line_ids': fields.many2many('account.move.line', 'account_bank_statement_line_rel', 'statement_id', 'line_id', 'Entries'),
    }
account_bank_statement_reconcile()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

