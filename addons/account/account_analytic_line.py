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
import tools
from tools import config

class account_analytic_line(osv.osv):
    _inherit = 'account.analytic.line'
    _description = 'Analytic Line'
    _columns = {
        'product_uom_id' : fields.many2one('product.uom', 'UoM'),
        'product_id' : fields.many2one('product.product', 'Product'),
        'general_account_id' : fields.many2one('account.account', 'General Account', required=True, ondelete='cascade'),
        'move_id' : fields.many2one('account.move.line', 'Move Line', ondelete='cascade', select=True),
        'journal_id' : fields.many2one('account.analytic.journal', 'Analytic Journal', required=True, ondelete='cascade', select=True),
        'code' : fields.char('Code', size=8),
        'ref': fields.char('Ref.', size=64),
        'currency_id': fields.related('move_id', 'currency_id', type='many2one', relation='res.currency', string='Account currency', store=True, help="The related account currency if not equal to the company one.", readonly=True),
        'amount_currency': fields.related('move_id', 'amount_currency', type='float', string='Amount currency', store=True, help="The amount expressed in the related account currency if not equal to the company one.", readonly=True),
    }

    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'account.analytic.line', context=c),
    }
    _order = 'date desc'

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        if context is None:
            context = {}
        if context.get('from_date',False):
            args.append(['date', '>=',context['from_date']])

        if context.get('to_date',False):
            args.append(['date','<=',context['to_date']])

        return super(account_analytic_line, self).search(cr, uid, args, offset, limit,
                order, context=context, count=count)

    def _check_company(self, cr, uid, ids):
        lines = self.browse(cr, uid, ids)
        for l in lines:
            if l.move_id and not l.account_id.company_id.id == l.move_id.account_id.company_id.id:
                return False
        return True
    _constraints = [
    ]

    # Compute the cost based on the price type define into company
    # property_valuation_price_type property
    def on_change_unit_amount(self, cr, uid, id, prod_id, unit_amount,company_id,
            unit=False, journal_id=False, context=None):
        if context==None:
            context={}
        uom_obj = self.pool.get('product.uom')
        product_obj = self.pool.get('product.product')
        company_obj=self.pool.get('res.company')
        analytic_journal_obj=self.pool.get('account.analytic.journal')
        product_price_type_obj = self.pool.get('product.price.type')
        if  prod_id:
            result = 0.0
            prod = product_obj.browse(cr, uid, prod_id)
            a = prod.product_tmpl_id.property_account_expense.id
            if not a:
                a = prod.categ_id.property_account_expense_categ.id
            if not a:
                raise osv.except_osv(_('Error !'),
                        _('There is no expense account defined ' \
                                'for this product: "%s" (id:%d)') % \
                                (prod.name, prod.id,))
            if not company_id:
                company_id=company_obj._company_default_get(cr, uid, 'account.analytic.line', context)
            flag = False
            # Compute based on pricetype
            pricetype=product_price_type_obj.browse(cr, uid, company_obj.browse(cr,uid,company_id).property_valuation_price_type.id)
            if journal_id:
                journal = analytic_journal_obj.browse(cr, uid, journal_id)
                if journal.type == 'sale':
                    product_price_type_ids = product_price_type_obj.search(cr, uid, [('field','=','list_price')], context)
                    if product_price_type_ids:
                        pricetype = product_price_type_obj.browse(cr, uid, product_price_type_ids, context)[0]
            # Take the company currency as the reference one
            if pricetype.field == 'list_price':
                flag = True
            amount_unit = prod.price_get(pricetype.field, context)[prod.id]
            amount = amount_unit*unit_amount or 1.0
            prec = self.pool.get('decimal.precision').precision_get(cr, uid, 'Account')
            amount = amount_unit*unit_amount or 1.0
            result = round(amount, prec)
            if not flag:
                result *= -1
            return {'value': {
                'amount': result,
                'general_account_id': a,
                }}
        return {}

    def view_header_get(self, cr, user, view_id, view_type, context):
        if context.get('account_id', False):
            # account_id in context may also be pointing to an account.account.id
            cr.execute('select name from account_analytic_account where id=%s', (context['account_id'],))
            res = cr.fetchone()
            if res:
                res = _('Entries: ')+ (res[0] or '')
            return res
        return False

account_analytic_line()

class res_partner(osv.osv):
    """ Inherits partner and adds contract information in the partner form """
    _inherit = 'res.partner'

    _columns = {
                'contract_ids': fields.one2many('account.analytic.account', \
                                                    'partner_id', 'Contracts', readonly=True),
                }

res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

