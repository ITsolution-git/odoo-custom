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
from tools.translate import _
import decimal_precision as dp
import netsvc

def _employee_get(obj, cr, uid, context=None):
    if context is None:
        context = {}
    ids = obj.pool.get('hr.employee').search(cr, uid, [('user_id', '=', uid)], context=context)
    if ids:
        return ids[0]
    return False

class hr_expense_expense(osv.osv):

    def copy(self, cr, uid, id, default=None, context=None):
        if context is None:
            context = {}
        if not default: default = {}
        default.update({'invoice_id': False, 'date_confirm': False, 'date_valid': False, 'user_valid': False})
        return super(hr_expense_expense, self).copy(cr, uid, id, default, context=context)

    def _amount(self, cr, uid, ids, field_name, arg, context=None):
        cr.execute("SELECT s.id,COALESCE(SUM(l.unit_amount*l.unit_quantity),0) AS amount FROM hr_expense_expense s LEFT OUTER JOIN hr_expense_line l ON (s.id=l.expense_id) WHERE s.id IN %s GROUP BY s.id ", (tuple(ids),))
        res = dict(cr.fetchall())
        return res

    def _get_currency(self, cr, uid, context=None):
        user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)[0]
        if user.company_id:
            return user.company_id.currency_id.id
        else:
            return self.pool.get('res.currency').search(cr, uid, [('rate','=',1.0)], context=context)[0]

    _name = "hr.expense.expense"
    _inherit = ['mail.thread']
    _description = "Expense"
    _order = "id desc"
    _columns = {
        'name': fields.char('Description', size=128, required=True),
        'id': fields.integer('Sheet ID', readonly=True),
        'date': fields.date('Date', select=True),
        'journal_id': fields.many2one('account.journal', 'Force Journal', help = "The journal used when the expense is paid."),
        'employee_id': fields.many2one('hr.employee', "Employee", required=True),
        'user_id': fields.many2one('res.users', 'User', required=True),
        'date_confirm': fields.date('Confirmation Date', select=True, help = "Date of the confirmation of the sheet expense. It's filled when the button Confirm is pressed."),
        'date_valid': fields.date('Validation Date', select=True, help = "Date of the acceptation of the sheet expense. It's filled when the button Accept is pressed."),
        'user_valid': fields.many2one('res.users', 'Validation User'),
        'account_move_id': fields.many2one('account.move', 'Ledger Posting'),
        'line_ids': fields.one2many('hr.expense.line', 'expense_id', 'Expense Lines', readonly=True, states={'draft':[('readonly',False)]} ),
        'note': fields.text('Note'),
        'amount': fields.function(_amount, string='Total Amount'),
        'voucher_id': fields.many2one('account.voucher', "Employee's Voucher"),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True),
        'department_id':fields.many2one('hr.department','Department'),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'state': fields.selection([
            ('draft', 'New'),
            ('cancelled', 'Refused'),
            ('confirm', 'Waiting Approval'),
            ('accepted', 'Approved'),
            ('invoiced', 'Invoiced'),
            ('paid', 'Reimbursed')
            ],
            'Status', readonly=True, help='When the expense request is created the status is \'Draft\'.\n It is confirmed by the user and request is sent to admin, the status is \'Waiting Confirmation\'.\
            \nIf the admin accepts it, the status is \'Accepted\'.\n If an invoice is made for the expense request, the status is \'Invoiced\'.\n If the expense is paid to user, the status is \'Reimbursed\'.'),
    }
    _defaults = {
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'hr.employee', context=c),
        'date': fields.date.context_today,
        'state': 'draft',
        'employee_id': _employee_get,
        'user_id': lambda cr, uid, id, c={}: id,
        'currency_id': _get_currency,
    }

    def onchange_employee_id(self, cr, uid, ids, employee_id, context=None):
        emp_obj = self.pool.get('hr.employee')
        department_id = False
        company_id = False
        if employee_id:
            employee = emp_obj.browse(cr, uid, employee_id, context=context)
            department_id = employee.department_id.id
            company_id = employee.company_id.id
        return {'value': {'department_id': department_id, 'company_id': company_id}}

    def expense_confirm(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {
            'state':'confirm',
            'date_confirm': time.strftime('%Y-%m-%d')
        })
        return True

    def expense_accept(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {
            'state':'accepted',
            'date_valid':time.strftime('%Y-%m-%d'),
            'user_valid': uid,
            })
        return True

    def expense_canceled(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state':'cancelled'})
        return True

    def expense_paid(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state':'paid'})
        return True

    def invoice(self, cr, uid, ids, context=None):
        mod_obj = self.pool.get('ir.model.data')
        wkf_service = netsvc.LocalService("workflow")
        
        if not ids: return []
        exp = self.browse(cr, uid, ids[0], context=context)
        
        voucher_ids = []
        for id in ids:
            wkf_service.trg_validate(uid, 'hr.expense.expense', id, 'invoice', cr)
            voucher_ids.append(self.browse(cr, uid, id, context=context).voucher_id.id)
        res = mod_obj.get_object_reference(cr, uid, 'account_voucher', 'view_purchase_receipt_form')
        res_id = res and res[1] or False
        return {
            'name': _('Purchase Receipt'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.voucher',
            'views': [(res_id, 'form')],
            'view_id': res_id,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'nodestroy': True,
            'res_id': voucher_ids and voucher_ids[0] or False,
        }
    def action_voucher_create(self, cr, uid, ids, context=None):
        res = False
        invoice_obj = self.pool.get('account.invoice')
        property_obj = self.pool.get('ir.property')
        sequence_obj = self.pool.get('ir.sequence')
        account_journal = self.pool.get('account.journal')
        voucher_obj = self.pool.get('account.voucher')
        
        for exp in self.browse(cr, uid, ids, context=None):
            company_id = exp.company_id.id
            lines = []
            total = 0.0
            for l in exp.line_ids:
                if l.product_id:
                    acc = l.product_id.product_tmpl_id.property_account_expense
                    if not acc:
                        acc = l.product_id.categ_id.property_account_expense_categ
                else:
                    acc = property_obj.get(cr, uid, 'property_account_expense_categ', 'product.category', context={'force_company': company_id})
                    if not acc:
                        raise osv.except_osv(_('Error !'), _('Please configure Default Expense account for Product purchase, `property_account_expense_categ`'))
                
                lines.append((0, False, {
                    'name': l.name,
                    'account_id': acc.id,
                    'amount': l.total_amount,
                    'type': 'dr'
                }))
                total += l.total_amount
            if not exp.employee_id.address_home_id:
                raise osv.except_osv(_('Error !'), _('The employee must have a Home address.'))
            acc = exp.employee_id.address_home_id.property_account_payable.id
            voucher = {
                'name': exp.name,
                'reference': sequence_obj.get(cr, uid, 'hr.expense.invoice'),
                'account_id': acc,
                'type': 'purchase',
                'partner_id': exp.employee_id.address_home_id.id,
                'company_id': company_id,
                'line_ids': lines,
                'amount': total
            }
            journal = False
            if exp.journal_id:
                voucher['journal_id'] = exp.journal_id.id
                journal = exp.journal_id
            else:
                journal_id = invoice_obj._get_journal(cr, uid, context={'type': 'in_invoice', 'company_id': company_id})
                if journal_id:
                    voucher['journal_id'] = journal_id
                    journal = account_journal.browse(cr, uid, journal_id)
            voucher_id = voucher_obj.create(cr, uid, voucher, context)
            aaa = self.write(cr, uid, [exp.id], {'voucher_id': voucher_id, 'state': 'invoiced'})
            res = voucher_id
        return res

hr_expense_expense()

class product_product(osv.osv):
    _inherit = "product.product"
    _columns = {
        'hr_expense_ok': fields.boolean('Can Constitute an Expense', help="Determines if the product can be visible in the list of product within a selection from an HR expense sheet line."),
    }

    def on_change_hr_expense_ok(self, cr, uid, id, hr_expense_ok):

        if not hr_expense_ok:
            return {}
        data_obj = self.pool.get('ir.model.data')
        cat_id = data_obj._get_id(cr, uid, 'hr_expense', 'cat_expense')
        categ_id = data_obj.browse(cr, uid, cat_id).res_id
        res = {'value' : {'type':'service','procure_method':'make_to_stock','supply_method':'buy','purchase_ok':True,'sale_ok' :False,'categ_id':categ_id }}
        return res

product_product()

class hr_expense_line(osv.osv):
    _name = "hr.expense.line"
    _description = "Expense Line"

    def _amount(self, cr, uid, ids, field_name, arg, context=None):
        if not ids:
            return {}
        cr.execute("SELECT l.id,COALESCE(SUM(l.unit_amount*l.unit_quantity),0) AS amount FROM hr_expense_line l WHERE id IN %s GROUP BY l.id ",(tuple(ids),))
        res = dict(cr.fetchall())
        return res

    _columns = {
        'name': fields.char('Expense Note', size=128, required=True),
        'date_value': fields.date('Date', required=True),
        'expense_id': fields.many2one('hr.expense.expense', 'Expense', ondelete='cascade', select=True),
        'total_amount': fields.function(_amount, string='Total', digits_compute=dp.get_precision('Account')),
        'unit_amount': fields.float('Unit Price', digits_compute=dp.get_precision('Account')),
        'unit_quantity': fields.float('Quantities' ),
        'product_id': fields.many2one('product.product', 'Product', domain=[('hr_expense_ok','=',True)]),
        'uom_id': fields.many2one('product.uom', 'Unit of Measure'),
        'description': fields.text('Description'),
        'analytic_account': fields.many2one('account.analytic.account','Analytic account'),
        'ref': fields.char('Reference', size=32),
        'sequence': fields.integer('Sequence', select=True, help="Gives the sequence order when displaying a list of expense lines."),
        }
    _defaults = {
        'unit_quantity': 1,
        'date_value': lambda *a: time.strftime('%Y-%m-%d'),
    }
    _order = "sequence, date_value desc"

    def onchange_product_id(self, cr, uid, ids, product_id, uom_id, employee_id, context=None):
        res = {}
        if product_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            res['name'] = product.name
            amount_unit = product.price_get('standard_price')[product.id]
            res['unit_amount'] = amount_unit
            if not uom_id:
                res['uom_id'] = product.uom_id.id
        return {'value': res}

hr_expense_line()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
