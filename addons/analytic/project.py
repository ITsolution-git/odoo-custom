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
import operator

from osv import fields, osv
import decimal_precision as dp

#
# Object definition
#

class account_analytic_account(osv.osv):
    _name = 'account.analytic.account'
    _description = 'Analytic Account'

    def _compute_currency_for_level_tree(self, cr, uid, ids, ids2, res, context={}):
        # Handle multi-currency on each level of analytic account
        # This is a refactoring of _balance_calc computation
        cr.execute("SELECT a.id, r.currency_id FROM account_analytic_account a INNER JOIN res_company r ON (a.company_id = r.id) where a.id IN %s" , (tuple(ids2),))
        currency= dict(cr.fetchall())
        res_currency= self.pool.get('res.currency')
        for id in ids:
            if id not in ids2:
                continue
            for child in self.search(cr, uid, [('parent_id', 'child_of', [id])]):
                if child != id:
                    res.setdefault(id, 0.0)
                    if  currency[child]!=currency[id]:
                        res[id] += res_currency.compute(cr, uid, currency[child], currency[id], res.get(child, 0.0), context=context)
                    else:
                        res[id] += res.get(child, 0.0)

        cur_obj = res_currency.browse(cr,uid,currency.values(),context)
        cur_obj = dict([(o.id, o) for o in cur_obj])
        for id in ids:
            if id in ids2:
                res[id] = res_currency.round(cr,uid,cur_obj[currency[id]],res.get(id,0.0))

        return dict([(i, res[i]) for i in ids ])


    def _credit_calc(self, cr, uid, ids, name, arg, context={}):
        res = {}
        parent_ids = tuple(self.search(cr, uid, [('parent_id', 'child_of', ids)]))
        for i in ids:
            res.setdefault(i,0.0)

        if not parent_ids:
            return res

        where_date = ''
        if context.get('from_date',False):
            where_date += " AND l.date >= '" + context['from_date'] + "'"
        if context.get('to_date',False):
            where_date += " AND l.date <= '" + context['to_date'] + "'"
        cr.execute("SELECT a.id, COALESCE(SUM(l.amount_currency),0) FROM account_analytic_account a LEFT JOIN account_analytic_line l ON (a.id=l.account_id "+where_date+") WHERE l.amount_currency<0 and a.id IN %s GROUP BY a.id",(tuple(parent_ids),))
        r = dict(cr.fetchall())
        return self._compute_currency_for_level_tree(cr, uid, ids, parent_ids, r, context)

    def _debit_calc(self, cr, uid, ids, name, arg, context={}):
        res = {}
        parent_ids = tuple(self.search(cr, uid, [('parent_id', 'child_of', ids)]))
        for i in ids:
            res.setdefault(i,0.0)

        if not parent_ids:
            return res

        where_date = ''
        if context.get('from_date',False):
            where_date += " AND l.date >= '" + context['from_date'] + "'"
        if context.get('to_date',False):
            where_date += " AND l.date <= '" + context['to_date'] + "'"
        cr.execute("SELECT a.id, COALESCE(SUM(l.amount_currency),0) FROM account_analytic_account a LEFT JOIN account_analytic_line l ON (a.id=l.account_id "+where_date+") WHERE l.amount_currency>0 and a.id IN %s GROUP BY a.id" ,(tuple(parent_ids),))
        r= dict(cr.fetchall())
        return self._compute_currency_for_level_tree(cr, uid, ids, parent_ids, r, context)

    def _balance_calc(self, cr, uid, ids, name, arg, context={}):
        res = {}
        parent_ids = tuple(self.search(cr, uid, [('parent_id', 'child_of', ids)]))
        for i in ids:
            res.setdefault(i,0.0)

        if not parent_ids:
            return res

        where_date = ''
        if context.get('from_date',False):
            where_date += " AND l.date >= '" + context['from_date'] + "'"
        if context.get('to_date',False):
            where_date += " AND l.date <= '" + context['to_date'] + "'"
        cr.execute("SELECT a.id, COALESCE(SUM(l.amount_currency),0) FROM account_analytic_account a LEFT JOIN account_analytic_line l ON (a.id=l.account_id "+where_date+") WHERE a.id IN %s GROUP BY a.id",(tuple(parent_ids),))

        for account_id, sum in cr.fetchall():
            res[account_id] = sum

        return self._compute_currency_for_level_tree(cr, uid, ids, parent_ids, res, context)

    def _quantity_calc(self, cr, uid, ids, name, arg, context={}):
        #XXX must convert into one uom
        res = {}
        parent_ids = tuple(self.search(cr, uid, [('parent_id', 'child_of', ids)]))

        for i in ids:
            res.setdefault(i,0.0)

        if not parent_ids:
            return res

        where_date = ''
        if context.get('from_date',False):
            where_date += " AND l.date >= '" + context['from_date'] + "'"
        if context.get('to_date',False):
            where_date += " AND l.date <= '" + context['to_date'] + "'"

        cr.execute('SELECT a.id, COALESCE(SUM(l.unit_amount), 0) \
                FROM account_analytic_account a \
                    LEFT JOIN account_analytic_line l ON (a.id = l.account_id ' + where_date + ') \
                WHERE a.id IN %s GROUP BY a.id',(tuple(parent_ids),))

        for account_id, sum in cr.fetchall():
            res[account_id] = sum

        for id in ids:
            if id not in parent_ids:
                continue
            for child in self.search(cr, uid, [('parent_id', 'child_of', [id])]):
                if child != id:
                    res.setdefault(id, 0.0)
                    res[id] += res.get(child, 0.0)
        return dict([(i, res[i]) for i in ids])

    def name_get(self, cr, uid, ids, context={}):
        if not len(ids):
            return []
        reads = self.read(cr, uid, ids, ['name','parent_id'], context)
        res = []
        for record in reads:
            name = record['name']
            if record['parent_id']:
                name = record['parent_id'][1]+' / '+name
            res.append((record['id'], name))
        return res

    def _complete_name_calc(self, cr, uid, ids, prop, unknow_none, unknow_dict):
        res = self.name_get(cr, uid, ids)
        return dict(res)

    def _get_company_currency(self, cr, uid, ids, field_name, arg, context={}):
        result = {}
        for rec in self.browse(cr, uid, ids, context):
            result[rec.id] = (rec.company_id.currency_id.id,rec.company_id.currency_id.code) or False
        return result

    def _get_account_currency(self, cr, uid, ids, field_name, arg, context={}):
        result=self._get_company_currency(cr, uid, ids, field_name, arg, context={})
        return result

    _columns = {
        'name' : fields.char('Account Name', size=128, required=True),
        'complete_name': fields.function(_complete_name_calc, method=True, type='char', string='Full Account Name'),
        'code' : fields.char('Account Code', size=24),
        'type': fields.selection([('view','View'), ('normal','Normal')], 'Account Type'),
        'description' : fields.text('Description'),
        'parent_id': fields.many2one('account.analytic.account', 'Parent Analytic Account', select=2),
        'child_ids': fields.one2many('account.analytic.account', 'parent_id', 'Child Accounts'),
        'line_ids': fields.one2many('account.analytic.line', 'account_id', 'Analytic Entries'),
        'balance' : fields.function(_balance_calc, method=True, type='float', string='Balance',store=True),
        'debit' : fields.function(_debit_calc, method=True, type='float', string='Debit',store=True),
        'credit' : fields.function(_credit_calc, method=True, type='float', string='Credit',store=True),
        'quantity': fields.function(_quantity_calc, method=True, type='float', string='Quantity',store=True),
        'quantity_max': fields.float('Maximum Quantity', help='Sets the higher limit of quantity of hours.'),
        'partner_id' : fields.many2one('res.partner', 'Associated Partner'),
        'contact_id' : fields.many2one('res.partner.address', 'Contact'),
        'user_id' : fields.many2one('res.users', 'Account Manager'),
        'date_start': fields.date('Date Start'),
        'date': fields.date('Date End'),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'company_currency_id': fields.function(_get_company_currency, method=True, type='many2one', relation='res.currency', string='Currency'),
        'state': fields.selection([('draft','Draft'),('open','Open'), ('pending','Pending'),('cancelled', 'Cancelled'),('close','Closed'),('template', 'Template')], 'State', required=True,readonly=True,
                                  help='* When an account is created its in \'Draft\' state.\
                                  \n* If any associated partner is there, it can be in \'Open\' state.\
                                  \n* If any pending balance is there it can be in \'Pending\'. \
                                  \n* And finally when all the transactions are over, it can be in \'Close\' state. \
                                  \n* The project can be in either if the states \'Template\' and \'Running\'.\n If it is template then we can make projects based on the template projects. If its in \'Running\' state it is a normal project.\
                                 \n If it is to be reviewed then the state is \'Pending\'.\n When the project is completed the state is set to \'Done\'.'),
       'currency_id': fields.function(_get_account_currency, method=True, type='many2one', relation='res.currency', string='Account currency', store=True),
    }

    def _default_company(self, cr, uid, context={}):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if user.company_id:
            return user.company_id.id
        return self.pool.get('res.company').search(cr, uid, [('parent_id', '=', False)])[0]
    _defaults = {
        'type' : lambda *a : 'normal',
        'company_id': _default_company,
        'state' : lambda *a : 'open',
        'user_id' : lambda self,cr,uid,ctx : uid,
        'partner_id': lambda self,cr, uid, ctx: ctx.get('partner_id', False),
        'contact_id': lambda self,cr, uid, ctx: ctx.get('contact_id', False),
		'date_start': lambda *a: time.strftime('%Y-%m-%d')
    }

    def check_recursion(self, cr, uid, ids, parent=None):
        return super(account_analytic_account, self).check_recursion(cr, uid, ids, parent=parent)

    _order = 'parent_id desc,code'
    _constraints = [
        (check_recursion, 'Error! You can not create recursive analytic accounts.', ['parent_id'])
    ]

    def create(self, cr, uid, vals, context=None):
        parent_id = vals.get('parent_id', 0)
        if ('code' not in vals or not vals['code']) and not parent_id:
            vals['code'] = self.pool.get('ir.sequence').get(cr, uid, 'account.analytic.account')
        return super(account_analytic_account, self).create(cr, uid, vals, context=context)

    def copy(self, cr, uid, id, default=None, context={}):
        if not default:
            default = {}
        default['code'] = False
        default['line_ids'] = []
        return super(account_analytic_account, self).copy(cr, uid, id, default, context=context)


    def on_change_parent(self, cr, uid, id, parent_id):
        if not parent_id:
            return {}
        parent = self.read(cr, uid, [parent_id], ['partner_id','code'])[0]
        childs = self.search(cr, uid, [('parent_id', '=', parent_id)])
        numchild = len(childs)
        if parent['partner_id']:
            partner = parent['partner_id'][0]
        else:
            partner = False
        res = {'value' : {}}
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
    def _amount_currency(self, cr, uid, ids, field_name, arg, context={}):
        result = {}
        for rec in self.browse(cr, uid, ids, context):
            cmp_cur_id=rec.company_id.currency_id.id
            aa_cur_id=rec.account_id.currency_id.id
            # Always provide the amount in currency
            if cmp_cur_id != aa_cur_id:
                cur_obj = self.pool.get('res.currency')
                ctx = {}
                if rec.date and rec.amount:
                    ctx['date'] = rec.date
                    result[rec.id] = cur_obj.compute(cr, uid, rec.company_id.currency_id.id,
                        rec.account_id.currency_id.id, rec.amount,
                        context=ctx)
            else:
                result[rec.id]=rec.amount
        return result
        
    def _get_account_currency(self, cr, uid, ids, field_name, arg, context={}):
        result = {}
        for rec in self.browse(cr, uid, ids, context):
            # Always provide second currency
            result[rec.id] = (rec.account_id.currency_id.id,rec.account_id.currency_id.code)
        return result
    def _get_account_line(self, cr, uid, ids, context={}):
        aac_ids = {}
        for acc in self.pool.get('account.analytic.account').browse(cr, uid, ids):
            aac_ids[acc.id] = True
        aal_ids = []
        if aac_ids:
            aal_ids = self.pool.get('account.analytic.line').search(cr, uid, [('account_id','in',aac_ids.keys())], context=context)
        return aal_ids

    _columns = {
        'name' : fields.char('Description', size=256, required=True),
        'date' : fields.date('Date', required=True),
        'amount' : fields.float('Amount', required=True, help='Calculated by multiplying the quantity and the price given in the Product\'s cost price.'),
        'unit_amount' : fields.float('Quantity', help='Specifies the amount of quantity to count.'),
        'account_id' : fields.many2one('account.analytic.account', 'Analytic Account', required=True, ondelete='cascade', select=True),
        'user_id' : fields.many2one('res.users', 'User',),
        'company_id': fields.many2one('res.company','Company',required=True),
        'currency_id': fields.function(_get_account_currency, method=True, type='many2one', relation='res.currency', string='Account currency',
                store={
                    'account.analytic.account': (_get_account_line, ['company_id'], 50),
                    'account.analytic.line': (lambda self,cr,uid,ids,c={}: ids, ['amount','unit_amount'],10),
                },
                help="The related account currency if not equal to the company one."),
        'amount_currency': fields.function(_amount_currency, method=True, digits_compute= dp.get_precision('Account'), string='Amount currency',
                store={
                    'account.analytic.account': (_get_account_line, ['company_id'], 50),
                    'account.analytic.line': (lambda self,cr,uid,ids,c={}: ids, ['amount','unit_amount'],10),
                },
                help="The amount expressed in the related account currency if not equal to the company one."),

    }
    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.analytic.line', context=c),
    }
    _order = 'date'
account_analytic_line()


