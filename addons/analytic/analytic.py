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

from osv import fields, osv
import decimal_precision as dp

class account_analytic_account(osv.osv):
    _name = 'account.analytic.account'
    _description = 'Analytic Account'

    def _compute_level_tree(self, cr, uid, ids, child_ids, res, field_names, context=None):
        def recursive_computation(account_id, res):
            account = self.browse(cr, uid, account_id)
            for son in account.child_ids:
                res = recursive_computation(son.id, res)
                for field in field_names:
                    res[account.id][field] += res[son.id][field]
            return res
        for account in self.browse(cr, uid, ids, context=context):
            if account.id not in child_ids:
                continue
            res = recursive_computation(account.id, res)
        return res

    def _debit_credit_bal_qtty(self, cr, uid, ids, name, arg, context=None):
        res = {}
        if context is None:
            context = {}
        child_ids = tuple(self.search(cr, uid, [('parent_id', 'child_of', ids)]))
        for i in child_ids:
            res[i] =  {}
            for n in name:
                res[i][n] = 0.0

        if not child_ids:
            return res

        where_date = ''
        where_clause_args = [tuple(child_ids)]  
        if context.get('from_date', False):
            where_date += " AND l.date >= %s"
            where_clause_args  += [context['from_date']]
        if context.get('to_date', False):
            where_date += " AND l.date <= %s"
            where_clause_args += [context['to_date']]
        cr.execute("""
              SELECT a.id,
                     sum(
                         CASE WHEN l.amount > 0
                         THEN l.amount 
                         ELSE 0.0
                         END
                          ) as debit,
                     sum(
                         CASE WHEN l.amount < 0
                         THEN -l.amount
                         ELSE 0.0 
                         END
                          ) as credit,
                     COALESCE(SUM(l.amount),0) AS balance,
                     COALESCE(SUM(l.unit_amount),0) AS quantity
              FROM account_analytic_account a 
                  LEFT JOIN account_analytic_line l ON (a.id = l.account_id) 
              WHERE a.id IN %s
              """ + where_date + """
              GROUP BY a.id""", where_clause_args)
        for ac_id, debit, credit, balance, quantity in cr.fetchall():
            res[ac_id] = {'debit': debit, 'credit': credit, 'balance': balance, 'quantity': quantity}
        return self._compute_level_tree(cr, uid, ids, child_ids, res, ['debit', 'credit', 'balance', 'quantity'], context)

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
            return []
        res = []
        for account in self.browse(cr, uid, ids, context=context):
            data = []
            acc = account
            while acc:
                data.insert(0, acc.name)
                acc = acc.parent_id
            data = ' / '.join(data)
            res.append((account.id, data))
        return res

    def _complete_name_calc(self, cr, uid, ids, prop, unknow_none, unknow_dict):
        res = self.name_get(cr, uid, ids)
        return dict(res)

    _columns = {
        'name': fields.char('Account Name', size=128, required=True),
        'complete_name': fields.function(_complete_name_calc, method=True, type='char', string='Full Account Name'),
        'code': fields.char('Account Code', size=24),
        'type': fields.selection([('view','View'), ('normal','Normal')], 'Account Type', help='If you select the View Type, it means you won\'t allow to create journal entries using that account.'),
        'description': fields.text('Description'),
        'parent_id': fields.many2one('account.analytic.account', 'Parent Analytic Account', select=2),
        'child_ids': fields.one2many('account.analytic.account', 'parent_id', 'Child Accounts'),
        'line_ids': fields.one2many('account.analytic.line', 'account_id', 'Analytic Entries'),
        'balance': fields.function(_debit_credit_bal_qtty, method=True, type='float', string='Balance', multi='debit_credit_bal_qtty', digits_compute=dp.get_precision('Account')),
        'debit': fields.function(_debit_credit_bal_qtty, method=True, type='float', string='Debit', multi='debit_credit_bal_qtty', digits_compute=dp.get_precision('Account')),
        'credit': fields.function(_debit_credit_bal_qtty, method=True, type='float', string='Credit', multi='debit_credit_bal_qtty', digits_compute=dp.get_precision('Account')),
        'quantity': fields.function(_debit_credit_bal_qtty, method=True, type='float', string='Quantity', multi='debit_credit_bal_qtty'),
        'quantity_max': fields.float('Maximum Quantity', help='Sets the higher limit of quantity of hours.'),
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'contact_id': fields.many2one('res.partner.address', 'Contact'),
        'user_id': fields.many2one('res.users', 'Account Manager'),
        'date_start': fields.date('Date Start'),
        'date': fields.date('Date End'),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'state': fields.selection([('draft','Draft'),('open','Open'), ('pending','Pending'),('cancelled', 'Cancelled'),('close','Closed'),('template', 'Template')], 'State', required=True,
                                  help='* When an account is created its in \'Draft\' state.\
                                  \n* If any associated partner is there, it can be in \'Open\' state.\
                                  \n* If any pending balance is there it can be in \'Pending\'. \
                                  \n* And finally when all the transactions are over, it can be in \'Close\' state. \
                                  \n* The project can be in either if the states \'Template\' and \'Running\'.\n If it is template then we can make projects based on the template projects. If its in \'Running\' state it is a normal project.\
                                 \n If it is to be reviewed then the state is \'Pending\'.\n When the project is completed the state is set to \'Done\'.'),
       'currency_id': fields.related('company_id', 'currency_id', type='many2one', relation='res.currency', string='Account currency', store=True, readonly=True),
    }

    def _default_company(self, cr, uid, context=None):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if user.company_id:
            return user.company_id.id
        return self.pool.get('res.company').search(cr, uid, [('parent_id', '=', False)])[0]

    _defaults = {
        'type': 'normal',
        'company_id': _default_company,
        'state': 'open',
        'user_id': lambda self, cr, uid, ctx: uid,
        'partner_id': lambda self, cr, uid, ctx: ctx.get('partner_id', False),
        'contact_id': lambda self, cr, uid, ctx: ctx.get('contact_id', False),
        'date_start': lambda *a: time.strftime('%Y-%m-%d')
    }

    def check_recursion(self, cr, uid, ids, parent=None):
        return super(account_analytic_account, self)._check_recursion(cr, uid, ids, parent=parent)

    _order = 'date_start desc,parent_id desc,code'
    _constraints = [
        (check_recursion, 'Error! You can not create recursive analytic accounts.', ['parent_id'])
    ]

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default['code'] = False
        default['line_ids'] = []
        return super(account_analytic_account, self).copy(cr, uid, id, default, context=context)

    def on_change_parent(self, cr, uid, id, parent_id):
        if not parent_id:
            return {}
        parent = self.read(cr, uid, [parent_id], ['partner_id','code'])[0]
        if parent['partner_id']:
            partner = parent['partner_id'][0]
        else:
            partner = False
        res = {'value': {}}
        if partner:
            res['value']['partner_id'] = partner
        return res

    def name_search(self, cr, uid, name, args=None, operator='ilike', context=None, limit=100):
        if not args:
            args=[]
        if not context:
            context={}
        account = self.search(cr, uid, [('code', '=', name)]+args, limit=limit, context=context)
        if not account:
            account = self.search(cr, uid, [('name', 'ilike', '%%%s%%' % name)]+args, limit=limit, context=context)
            newacc = account
            while newacc:
                newacc = self.search(cr, uid, [('parent_id', 'in', newacc)]+args, limit=limit, context=context)
                account+=newacc
        return self.name_get(cr, uid, account, context=context)

account_analytic_account()


class account_analytic_line(osv.osv):
    _name = 'account.analytic.line'
    _description = 'Analytic Line'

    _columns = {
        'name': fields.char('Description', size=256, required=True),
        'date': fields.date('Date', required=True, select=1),
        'amount': fields.float('Amount', required=True, help='Calculated by multiplying the quantity and the price given in the Product\'s cost price. Always expressed in the company main currency.', digits_compute=dp.get_precision('Account')),
        'unit_amount': fields.float('Quantity', help='Specifies the amount of quantity to count.'),
        'account_id': fields.many2one('account.analytic.account', 'Analytic Account', required=True, ondelete='cascade', select=True, domain=[('type','<>','view')]),
        'user_id': fields.many2one('res.users', 'User'),
        'company_id': fields.related('account_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True),

    }
    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.analytic.line', context=c),
        'amount': 0.00
    }

    _order = 'date desc'

account_analytic_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
