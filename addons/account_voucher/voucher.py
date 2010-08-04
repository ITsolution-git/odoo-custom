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
from osv import fields
from osv import osv
from tools.translate import _

journal2type = {
    'cash':'rec_voucher',
    'bank':'bank_rec_voucher',
    'cash':'pay_voucher',
    'sale':'journal_sale_vou',
    'purchase':'journal_pur_voucher',
    'general':'journal_voucher'
}

type2journal = {
    'rec_voucher': 'cash',
    'bank_rec_voucher': 'bank',
    'pay_voucher': 'cash',
    'bank_pay_voucher': 'bank',
    'cont_voucher': 'cash',
    'journal_sale_vou': 'sale',
    'journal_pur_voucher': 'purchase',
    'journal_voucher':'general'
}

class ir_sequence_type(osv.osv):
    _inherit = "ir.sequence.type"
    _columns = {
        'name': fields.char('Sequence Name',size=128, required=True),
        'code': fields.char('Sequence Code',size=128, required=True),
    }
ir_sequence_type()

class account_journal(osv.osv):
    _inherit = "account.journal"
    _columns = {
        'max_amount': fields.float('Verify Transaction', digits=(16, 2), help="Validate voucher entry twice before posting it, if transection amount more then entered here"),
    }
account_journal()

class account_voucher(osv.osv):

    def _get_period(self, cr, uid, context={}):
        if context.get('period_id', False):
            return context.get('period_id')

        periods = self.pool.get('account.period').find(cr, uid)
        if periods:
            return periods[0]
        else:
            return False

    def _get_type(self, cr, uid, context={}):
        vtype = context.get('type', 'bank')
        voucher_type = journal2type.get(vtype)
        return voucher_type

    def _get_reference_type(self, cursor, user, context=None):
        return [('none', 'Free Reference')]

    def _get_journal(self, cr, uid, context={}):
        journal_pool = self.pool.get('account.journal')

        if context.get('journal_id', False):
            return context.get('journal_id')

        type_inv = context.get('type', 'rec_voucher')

        ttype = type2journal.get(type_inv, type_inv)
        res = journal_pool.search(cr, uid, [('type', '=', ttype)], limit=1)

        if res:
            return res[0]
        else:
            return False

    def _get_currency(self, cr, uid, context):
        user = self.pool.get('res.users').browse(cr, uid, uid)
        if user.company_id:
            return user.company_id.currency_id.id
        else:
            return self.pool.get('res.currency').search(cr, uid, [('rate','=',1.0)])[0]

    _name = 'account.voucher'
    _description = 'Accounting Voucher'
    _order = "id desc"
    _columns = {
        'name':fields.char('Name', size=256, required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'type': fields.selection([
            ('pay_voucher','Cash Payment'),
            ('bank_pay_voucher','Bank Payment'),
            ('rec_voucher','Cash Receipt'),
            ('bank_rec_voucher','Bank Receipt'),
            ('journal_sale_vou','Journal Sale'),
            ('journal_pur_voucher','Journal Purchase'),
            ('journal_voucher','Journal Voucher'),
            ],'Entry Type', select=True , size=128, readonly=True, states={'draft':[('readonly',False)]}),
        'date':fields.date('Date', readonly=True, states={'draft':[('readonly',False)]}, help="Effective date for accounting entries"),
        'journal_id':fields.many2one('account.journal', 'Journal', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'account_id':fields.many2one('account.account', 'Account', required=True, readonly=True, states={'draft':[('readonly',False)]}, domain=[('type','<>','view')]),
        'payment_ids':fields.one2many('account.voucher.line','voucher_id','Voucher Lines', readonly=True, states={'draft':[('readonly',False)]}),
        'period_id': fields.many2one('account.period', 'Period', required=True, readonly=True, states={'posted':[('readonly',False)]}),
        'narration':fields.text('Narration', readonly=True, states={'draft':[('readonly',False)]}),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True, readonly=True, states={'draft':[('readonly',False)]}),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'state':fields.selection(
            [('draft','Draft'),
             ('proforma','Pro-forma'),
             ('posted','Posted'),
             ('recheck','Waiting for Re-checking'),
             ('cancel','Cancel'),
             ('audit','Audit Complete')
            ], 'State', readonly=True, size=32,
            help=' * The \'Draft\' state is used when a user is encoding a new and unconfirmed Voucher. \
                        \n* The \'Pro-forma\' when voucher is in Pro-forma state,voucher does not have an voucher number. \
                        \n* The \'Posted\' state is used when user create voucher,a voucher number is generated and voucher entries are created in account \
                        \n* The \'Cancelled\' state is used when user cancel voucher.'),
        'amount':fields.float('Amount', readonly=True),
        'reference': fields.char('Reference', size=64, readonly=True, states={'draft':[('readonly',False)]}, help="Bank cheque number or payorder number"),
        'reference_type': fields.selection(_get_reference_type, 'Reference Type', required=True),
        'number': fields.related('move_id', 'name', type="char", readonly=True, string='Number'),
        'move_id':fields.many2one('account.move', 'Account Entry'),
        'move_ids':fields.many2many('account.move.line', 'voucher_id', 'account_id', 'rel_account_move', 'Real Entry'),
        'partner_id':fields.many2one('res.partner', 'Partner', readonly=True, states={'draft':[('readonly',False)]})
    }

    _defaults = {
        'period_id': _get_period,
        'type': _get_type,
        'journal_id':_get_journal,
        'currency_id': _get_currency,
        'state': lambda *a: 'draft',
        'date' : lambda *a: time.strftime('%Y-%m-%d'),
        'reference_type': lambda *a: "none",
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.voucher',context=c),
    }

    def onchange_account(self, cr, uid, ids, account_id):
        if not account_id:
            return {
                'value':{'amount':False}
            }
        account = self.pool.get('account.account').browse(cr, uid, account_id)
        balance=account.balance
        return {
            'value':{'amount':balance}
        }

    def onchange_journal(self, cr, uid, ids, journal_id, type):
        if not journal_id:
            return {
                'value':{'account_id':False}
            }
        journal = self.pool.get('account.journal')

        if journal_id and (type in ('rec_voucher','bank_rec_voucher','journal_pur_voucher','journal_voucher')):
            account_id = journal.browse(cr, uid, journal_id).default_debit_account_id
            return {
                'value':{'account_id':account_id.id}
            }
        elif journal_id and (type in ('pay_voucher','bank_pay_voucher','journal_sale_vou')) :
                account_id = journal.browse(cr, uid, journal_id).default_credit_account_id
                return {
                    'value':{'account_id':account_id.id}
                }
        else:
            account_id = journal.browse(cr, uid, journal_id).default_credit_account_id
            return {
                'value':{'account_id':account_id.id}
            }

    def open_voucher(self, cr, uid, ids, context={}):
        voucher = self.pool.get('account.voucher').browse(cr, uid, ids)[0]
        total = 0
        for line in voucher.payment_ids:
            total += line.amount
        
        if total != 0:
            res = {
                'amount':total, 
                'state':'proforma'
            }
            self.write(cr, uid, ids, res)
        else:
            raise osv.except_osv(_('Invalid action !'), _('You can not post to Pro-Forma a voucher with Total amount = 0 !'))
        return True

    def proforma_voucher(self, cr, uid, ids, context={}):
        self.action_move_line_create(cr, uid, ids)
        self.write(cr, uid, ids, {'state':'posted'})
        return True
    
    def action_cancel_draft(self, cr, uid, ids, context={}):
        self.write(cr, uid, ids, {'state':'draft'})
        return True
    
    def audit_pass(self, cr, uid, ids, context={}):
        move_pool = self.pool.get('account.move')
        result = True
        audit_pass = []
        for voucher in self.browse(cr, uid, ids):
            if voucher.move_id and voucher.move_id.state == 'draft':
                result = result and move_pool.button_validate(cr, uid, [voucher.move_id.id])
            audit_pass += [voucher.id]
        
        self.write(cr, uid, audit_pass, {'state':'audit'})
        return result
        
    def cancel_voucher(self, cr, uid, ids, context={}):
        move_pool = self.pool.get('account.move')
        
        for voucher in self.browse(cr, uid, ids):
            if voucher.move_id:
                move_pool.button_cancel(cr, uid, [voucher.move_id.id])
                move_pool.unlink(cr, uid, [voucher.move_id.id])
        
        res = {
            'state':'cancel', 
            'move_id':False,
            'move_ids':[(6, 0,[])]
        }
        self.write(cr, uid, ids, res)
        return True

    def unlink(self, cr, uid, ids, context=None):
        vouchers = self.read(cr, uid, ids, ['state'])
        unlink_ids = []
        for t in vouchers:
            if t['state'] in ('draft', 'cancel'):
                unlink_ids.append(t['id'])
            else:
                raise osv.except_osv('Invalid action !', 'Cannot delete Voucher(s) which are already opened or paid !')
        return super(account_voucher, self).unlink(cr, uid, unlink_ids, context=context)

    def action_move_line_create(self, cr, uid, ids, *args):

        journal_pool = self.pool.get('account.journal')
        sequence_pool = self.pool.get('ir.sequence')
        move_pool = self.pool.get('account.move')
        move_line_pool = self.pool.get('account.move.line')
        analytic_pool = self.pool.get('account.analytic.line')
        currency_pool = self.pool.get('res.currency')
        invoice_pool = self.pool.get('account.invoice')
        
        for inv in self.browse(cr, uid, ids):
            
            if inv.move_id:
                continue

            journal = journal_pool.browse(cr, uid, inv.journal_id.id)
            if inv.type in ('journal_pur_voucher', 'journal_sale_vou'):
                if journal.invoice_sequence_id:
                    name = sequence_pool.get_id(cr, uid, journal.invoice_sequence_id.id)
                else:
                    raise osv.except_osv(_('Error !'), _('Please define invoice sequence on %s journal !' % (journal.name)))
            else:
                if journal.sequence_id:
                    name = sequence_pool.get_id(cr, uid, journal.sequence_id.id)
                else:
                    raise osv.except_osv(_('Error !'), _('Please define sequence on journal !'))
            
            ref = False
            if inv.type in ('journal_pur_voucher', 'bank_rec_voucher', 'rec_voucher'):
                ref = inv.reference
            else:
                ref = invoice_pool._convert_ref(cr, uid, name)
            
            company_currency = inv.company_id.currency_id.id
            diff_currency_p = inv.currency_id.id <> company_currency
            
            move = {
                'name':name,
                'journal_id':journal.id,
                'type':inv.type,
                'narration':inv.narration and inv.narration or inv.name,
                'date':inv.date,
                'ref':ref
            }
            
            if inv.period_id:
                move.update({
                    'period_id': inv.period_id.id
                })
            
            move_id = move_pool.create(cr, uid, move)
            
            #create the first line manually
            move_line = {
                'name': inv.name,
                'debit': False,
                'credit':False,
                'account_id': inv.account_id.id or False,
                'move_id': move_id ,
                'journal_id': inv.journal_id.id,
                'period_id': inv.period_id.id,
                'partner_id': False,
                'ref':ref,
                'date': inv.date
            }
            if diff_currency_p:
                amount_currency = currency_pool.compute(cr, uid, inv.currency_id.id, company_currency, inv.amount)
                inv.amount = amount_currency
                move_line.update({
                    'amount_currency':amount_currency,
                    'currency_id':inv.currency_id.id
                })
            
            if inv.type in ('rec_voucher', 'bank_rec_voucher', 'journal_pur_voucher', 'journal_voucher'):
                move_line['debit'] = inv.amount
            else:
                move_line['credit'] = inv.amount
            
            line_ids = []
            line_ids += [move_line_pool.create(cr, uid, move_line)]
            for line in inv.payment_ids:
                amount=0.0
                
                if inv.type in ('bank_pay_voucher', 'pay_voucher', 'journal_voucher'):
                    ref = line.ref
                    
                move_line = {
                     'name':line.name,
                     'debit':False,
                     'credit':False,
                     'account_id':line.account_id.id or False,
                     'move_id':move_id ,
                     'journal_id':inv.journal_id.id,
                     'period_id':inv.period_id.id,
                     'partner_id':line.partner_id.id or False,
                     'ref':ref,
                     'date':inv.date,
                     'analytic_account_id':False
                }
                
                if diff_currency_p:
                    amount_currency = currency_pool.compute(cr, uid, inv.currency_id.id, company_currency, line.amount)
                    line.amount = amount_currency
                    move_line.update({
                        'amount_currency':amount_currency,
                        'currency_id':inv.currency_id.id
                    })
                
                if line.account_analytic_id:
                    move_line.update({
                        'analytic_account_id':line.account_analytic_id.id
                    })
                
                if line.type == 'dr':
                    move_line.update({
                        'debit': line.amount or False
                    })
                    amount = line.amount
                    
                elif line.type == 'cr':
                    move_line.update({
                        'credit': line.amount or False
                    })
                    amount = line.amount * (-1)

                move_line_id = move_line_pool.create(cr, uid, move_line)
                line_ids += [move_line_id]
            
            rec = {
                'move_id': move_id,
                'move_ids':[(6, 0,line_ids)]
            }
            
            message = _('Voucher ') + " '" + inv.name + "' "+ _("is confirmed")
            self.log(cr, uid, inv.id, message)
            
            self.write(cr, uid, [inv.id], rec)
            
        return True

    def _convert_ref(self, cr, uid, ref):
        return (ref or '').replace('/','')

    def name_get(self, cr, uid, ids, context={}):
        if not len(ids):
            return []
        types = {
            'pay_voucher': 'CPV: ',
            'rec_voucher': 'CRV: ',
            'cont_voucher': 'CV: ',
            'bank_pay_voucher': 'BPV: ',
            'bank_rec_voucher': 'BRV: ',
            'journal_sale_vou': 'JSV: ',
            'journal_pur_voucher': 'JPV: ',
            'journal_voucher':'JV'
        }
        return [(r['id'], types[r['type']]+(r['number'] or '')+' '+(r['name'] or '')) for r in self.read(cr, uid, ids, ['type', 'number', 'name'], context, load='_classic_write')]

    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=100):
        if not args:
            args=[]
        if not context:
            context={}
        ids = []
        if name:
            ids = self.search(cr, user, [('number','=',name)]+args, limit=limit, context=context)
        if not ids:
            ids = self.search(cr, user, [('name',operator,name)]+args, limit=limit, context=context)
        return self.name_get(cr, user, ids, context)

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default.update({'state':'draft', 'number':False, 'move_id':False, 'move_ids':False, 'payment_ids':False})
        if 'date' not in default:
            default['date'] = time.strftime('%Y-%m-%d')
        return super(account_voucher, self).copy(cr, uid, id, default, context)

account_voucher()

class account_voucher_line(osv.osv):
    _name = 'account.voucher.line'
    _description = 'Voucher Line'
    _columns = {
        'voucher_id':fields.many2one('account.voucher', 'Voucher'),
        'name':fields.char('Description', size=256, required=True),
        'account_id':fields.many2one('account.account','Account', required=True, domain=[('type','<>','view')]),
        'partner_id': fields.many2one('res.partner', 'Partner', change_default=True),
        'amount':fields.float('Amount'),
        'type':fields.selection([('dr','Debit'),('cr','Credit')], 'Type'),
        'ref':fields.char('Reference', size=32),
        'account_analytic_id':  fields.many2one('account.analytic.account', 'Analytic Account')
    }
    _defaults = {
        'type': lambda *a: 'cr'
    }

    def onchange_partner(self, cr, uid, ids, partner_id, ttype ,type1, currency):
        currency_pool = self.pool.get('res.currency')
        company = self.pool.get('res.users').browse(cr, uid, uid).company_id
        
        vals = {
            'account_id': False, 
            'type': False ,
            'amount': False
        }
        
        if not partner_id:
            return {
                'value' : vals
            }
        
        partner_pool = self.pool.get('res.partner')
        account_id = False

        partner = partner_pool.browse(cr, uid, partner_id)
        balance = 0.0
        
        if type1 in ('rec_voucher', 'bank_rec_voucher', 'journal_voucher'):
            account_id = partner.property_account_receivable.id
            balance = partner.credit
            ttype = 'cr'
            
        elif type1 in ('pay_voucher', 'bank_pay_voucher', 'journal_voucher') :
            account_id = partner.property_account_payable.id
            balance = partner.debit
            ttype = 'dr'
            
        elif type1 in ('journal_sale_vou') :
            account_id = partner.property_account_receivable.id
            ttype = 'dr'
            
        elif type1 in ('journal_pur_voucher') :
            account_id = partner.property_account_payable.id
            ttype = 'cr'
        
        if company.currency_id != currency:
            balance = currency_pool.compute(cr, uid, company.currency_id.id, currency, balance)
        
        vals.update({
            'account_id': account_id, 
            'type': ttype, 
            'amount':balance
        })
        
        return {
            'value' : vals
        }
    
account_voucher_line()
