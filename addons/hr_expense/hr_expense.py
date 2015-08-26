# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time

from openerp.osv import fields, osv
from openerp.tools.translate import _

import openerp.addons.decimal_precision as dp
from openerp.exceptions import UserError

def _employee_get(obj, cr, uid, context=None):
    if context is None:
        context = {}
    ids = obj.pool.get('hr.employee').search(cr, uid, [('user_id', '=', uid)], context=context)
    if ids:
        return ids[0]
    return False

class hr_expense_expense(osv.osv):

    def _amount(self, cr, uid, ids, field_name, arg, context=None):
        res= {}
        for expense in self.browse(cr, uid, ids, context=context):
            total = 0.0
            for line in expense.line_ids:
                total += line.unit_amount * line.unit_quantity
            res[expense.id] = total
        return res

    def _get_expense_from_line(self, cr, uid, ids, context=None):
        return [line.expense_id.id for line in self.pool.get('hr.expense.line').browse(cr, uid, ids, context=context)]

    def _get_currency(self, cr, uid, context=None):
        user = self.pool.get('res.users').browse(cr, uid, [uid], context=context)[0]
        return user.company_id.currency_id.id

    _name = "hr.expense.expense"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _description = "Expense"
    _order = "id desc"

    _columns = {
        'name': fields.char('Description', required=True, readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}),
        'id': fields.integer('Sheet ID', readonly=True),
        'date': fields.date('Date', select=True, readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}),
        'journal_id': fields.many2one('account.journal', 'Force Journal', help = "The journal used when the expense is done."),
        'employee_payable_account_id': fields.many2one('account.account', 'Employee Account', help="Employee payable account", domain=[('deprecated', '=', False)]),
        'employee_id': fields.many2one('hr.employee', "Employee", required=True, readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}),
        'user_id': fields.many2one('res.users', 'User', required=True),
        'date_confirm': fields.date('Confirmation Date', select=True, copy=False,
                                    help="Date of the confirmation of the sheet expense. It's filled when the button Confirm is pressed."),
        'date_valid': fields.date('Validation Date', select=True, copy=False,
                                  help="Date of the acceptation of the sheet expense. It's filled when the button Accept is pressed."),
        'user_valid': fields.many2one('res.users', 'Validation By', readonly=True, copy=False,
                                      states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}),
        'account_move_id': fields.many2one('account.move', 'Ledger Posting', copy=False, track_visibility="onchange"),
        'line_ids': fields.one2many('hr.expense.line', 'expense_id', 'Expense Lines', copy=True,
                                    readonly=True, states={'draft':[('readonly',False)]} ),
        'note': fields.text('Note'),
        'amount': fields.function(_amount, string='Total Amount', digits=0,
            store={
                'hr.expense.line': (_get_expense_from_line, ['unit_amount','unit_quantity'], 10)
            }),
        'currency_id': fields.many2one('res.currency', 'Currency', required=True, readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}),
        'department_id':fields.many2one('hr.department','Department', readonly=True, states={'draft':[('readonly',False)], 'confirm':[('readonly',False)]}),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'state': fields.selection([
            ('draft', 'New'),
            ('cancelled', 'Refused'),
            ('confirm', 'Waiting Approval'),
            ('accepted', 'Approved'),
            ('done', 'Waiting Payment'),
            ('paid', 'Paid'),
            ],
            'Status', readonly=True, track_visibility='onchange', copy=False,
            help='When the expense request is created the status is \'Draft\'.\n It is confirmed by the user and request is sent to admin, the status is \'Waiting Confirmation\'.\
            \nIf the admin accepts it, the status is \'Accepted\'.\n If the accounting entries are made for the expense request, the status is \'Waiting Payment\'.'),

    }
    _defaults = {
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'hr.employee', context=c),
        'date': fields.date.context_today,
        'state': 'draft',
        'employee_id': _employee_get,
        'user_id': lambda cr, uid, id, c={}: id,
        'currency_id': _get_currency,
    }

    def add_follower(self, cr, uid, ids, employee_id, context=None):
        employee = self.pool.get('hr.employee').browse(cr, uid, employee_id, context=context)
        if employee and employee.user_id:
            self.message_subscribe_users(cr, uid, ids, user_ids=[employee.user_id.id], context=context)

    def create(self, cr, uid, vals, context=None):
        employee_id = vals.get('employee_id', False)
        hr_expense_id = super(hr_expense_expense, self).create(cr, uid, vals, context=context)
        self.add_follower(cr, uid, [hr_expense_id], employee_id, context=context)
        return hr_expense_id

    def write(self, cr, uid, ids, vals, context=None):
        employee_id = vals.get('employee_id', False)
        hr_expense_id = super(hr_expense_expense, self).write(cr, uid, ids, vals, context=context)
        self.add_follower(cr, uid, ids, employee_id, context=context)
        return hr_expense_id

    def unlink(self, cr, uid, ids, context=None):
        for rec in self.browse(cr, uid, ids, context=context):
            if rec.state != 'draft':
                raise UserError(_('You can only delete draft expenses!'))
        return super(hr_expense_expense, self).unlink(cr, uid, ids, context)

    def onchange_currency_id(self, cr, uid, ids, currency_id=False, company_id=False, context=None):
        res =  {'value': {'journal_id': False}}
        journal_ids = self.pool.get('account.journal').search(cr, uid, [('type','=','purchase'), ('currency_id','=',currency_id), ('company_id', '=', company_id)], context=context)
        if journal_ids:
            res['value']['journal_id'] = journal_ids[0]
        return res

    def onchange_employee_id(self, cr, uid, ids, employee_id, context=None):
        emp_obj = self.pool.get('hr.employee')
        department_id = False
        employee_payable_account_id = False
        company_id = False
        if employee_id:
            employee = emp_obj.browse(cr, uid, employee_id, context=context)
            department_id = employee.department_id.id
            company_id = employee.company_id.id
            if employee.address_home_id and employee.address_home_id.property_account_payable_id:
                employee_payable_account_id = employee.address_home_id.property_account_payable_id.id
        return {'value': {'department_id': department_id, 'company_id': company_id, 'employee_payable_account_id': employee_payable_account_id}}

    def expense_confirm(self, cr, uid, ids, context=None):
        for expense in self.browse(cr, uid, ids):
            if not expense.line_ids:
                raise UserError(_('You cannot submit expense which has no expense line.'))
            if expense.employee_id and expense.employee_id.parent_id.user_id:
                self.message_subscribe_users(cr, uid, [expense.id], user_ids=[expense.employee_id.parent_id.user_id.id])
        return self.write(cr, uid, ids, {'state': 'confirm', 'date_confirm': time.strftime('%Y-%m-%d')}, context=context)

    def expense_accept(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'accepted', 'date_valid': time.strftime('%Y-%m-%d'), 'user_valid': uid}, context=context)

    def expense_canceled(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'cancelled'}, context=context)

    def _track_subtype(self, cr, uid, ids, init_values, context=None):
        record = self.browse(cr, uid, ids[0], context=context)
        if 'state' in init_values and record.state == 'accepted':
            return 'hr_expense.mt_expense_approved'
        elif 'state' in init_values and record.state == 'confirm':
            return 'hr_expense.mt_expense_confirmed'
        elif 'state' in init_values and record.state == 'cancelled':
            return 'hr_expense.mt_expense_refused'
        return super(hr_expense_expense, self)._track_subtype(cr, uid, ids, init_values, context=context)

    def _notification_group_recipients(self, cr, uid, ids, message, recipients, done_ids, group_data, context=None):
        """ Override because HR users / officers can approve / refuse expenses
        directly form their notification email. """
        group_hr_user = self.pool['ir.model.data'].xmlid_to_res_id(cr, uid, 'base.group_hr_user')
        for recipient in recipients:
            if recipient.id in done_ids:
                continue
            if recipient.user_ids and group_hr_user in recipient.user_ids[0].groups_id.ids:
                group_data['group_hr_user'] |= recipient
                done_ids.add(recipient.id)
        return super(hr_expense_expense, self)._notification_group_recipients(cr, uid, ids, message, recipients, done_ids, group_data, context=context)

    def _notification_get_recipient_groups(self, cr, uid, ids, message, recipients, context=None):
        """ Override because HR users / officers can approve / refuse expenses
        directly form their notification email. """
        res = super(hr_expense_expense, self)._notification_get_recipient_groups(cr, uid, ids, message, recipients, context=context)

        app_action = self._notification_link_helper(cr, uid, ids, 'workflow', context=context, signal='validate')
        ref_action = self._notification_link_helper(cr, uid, ids, 'workflow', context=context, signal='refuse')

        expense = self.browse(cr, uid, ids[0], context=context)
        actions = []
        if expense.state == 'confirm':
            actions.append({'url': app_action, 'title': _('Approve')})
        if expense.state in ['confirm', 'accepted']:
            actions.append({'url': ref_action, 'title': _('Refuse')})

        res['group_hr_user'] = {
            'actions': actions
        }
        return res

    def account_move_get(self, cr, uid, expense_id, context=None):
        '''
        This method prepare the creation of the account move related to the given expense.

        :param expense_id: Id of expense for which we are creating account_move.
        :return: mapping between fieldname and value of account move to create
        :rtype: dict
        '''
        journal_obj = self.pool.get('account.journal')
        expense = self.browse(cr, uid, expense_id, context=context)
        company_id = expense.company_id.id
        ref = expense.name
        journal_id = False
        if expense.journal_id:
            journal_id = expense.journal_id.id
        else:
            journal_id = journal_obj.search(cr, uid, [('type', '=', 'purchase'), ('company_id', '=', company_id)])
            if not journal_id:
                raise UserError(_("No expense journal found. Please make sure you have a journal with type 'purchase' configured."))
            journal_id = journal_id[0]

        return {
            'journal_id': journal_id,
            'date': expense.date_confirm,
            'ref': ref,
            'company_id': company_id,
        }

    def line_get_convert(self, cr, uid, x, part, date, context=None):
        partner_id  = self.pool.get('res.partner')._find_accounting_partner(part).id
        return {
            'date_maturity': x.get('date_maturity', False),
            'partner_id': partner_id,
            'name': x['name'][:64],
            'date': date,
            'debit': x['price']>0 and x['price'],
            'credit': x['price']<0 and -x['price'],
            'account_id': x['account_id'],
            'analytic_line_ids': x.get('analytic_line_ids', False),
            'amount_currency': x['price']>0 and abs(x.get('amount_currency', False)) or -abs(x.get('amount_currency', False)),
            'currency_id': x.get('currency_id', False),
            'tax_line_id': x.get('tax_line_id', False),
            'ref': x.get('ref', False),
            'quantity': x.get('quantity',1.00),
            'product_id': x.get('product_id', False),
            'product_uom_id': x.get('uom_id', False),
            'analytic_account_id': x.get('account_analytic_id', False),
        }

    def compute_expense_totals(self, cr, uid, exp, company_currency, ref, account_move_lines, context=None):
        '''
        internal method used for computation of total amount of an expense in the company currency and
        in the expense currency, given the account_move_lines that will be created. It also do some small
        transformations at these account_move_lines (for multi-currency purposes)
        
        :param account_move_lines: list of dict
        :rtype: tuple of 3 elements (a, b ,c)
            a: total in company currency
            b: total in hr.expense currency
            c: account_move_lines potentially modified
        '''
        cur_obj = self.pool.get('res.currency')
        context = dict(context or {}, date=exp.date_confirm or time.strftime('%Y-%m-%d'))
        total = 0.0
        total_currency = 0.0
        for i in account_move_lines:
            if exp.currency_id.id != company_currency:
                i['currency_id'] = exp.currency_id.id
                i['amount_currency'] = i['price']
                i['price'] = cur_obj.compute(cr, uid, exp.currency_id.id,
                        company_currency, i['price'],
                        context=context)
            else:
                i['amount_currency'] = False
                i['currency_id'] = False
            total -= i['price']
            total_currency -= i['amount_currency'] or i['price']
        return total, total_currency, account_move_lines
        
    def action_move_create(self, cr, uid, ids, context=None):
        '''
        main function that is called when trying to create the accounting entries related to an expense
        '''
        move_obj = self.pool.get('account.move')
        for exp in self.browse(cr, uid, ids, context=context):
            if not exp.employee_payable_account_id:
                raise UserError(_('No employee account payable found for the expense '))

            company_currency = exp.company_id.currency_id.id
            diff_currency_p = exp.currency_id.id != company_currency

            #create the move that will contain the accounting entries
            move_id = move_obj.create(cr, uid, self.account_move_get(cr, uid, exp.id, context=context), context=context)

            #one account.move.line per expense line (+taxes..)
            eml = self.move_line_get(cr, uid, exp.id, context=context)

            #create one more move line, a counterline for the total on payable account
            total, total_currency, eml = self.compute_expense_totals(cr, uid, exp, company_currency, exp.name, eml, context=context)

            acc = exp.employee_payable_account_id.id or False
            eml.append({
                    'type': 'dest',
                    'name': '/',
                    'price': total, 
                    'account_id': acc, 
                    'date_maturity': exp.date_confirm, 
                    'amount_currency': diff_currency_p and total_currency or False, 
                    'currency_id': diff_currency_p and exp.currency_id.id or False, 
                    'ref': exp.name
                    })

            #convert eml into an osv-valid format
            lines = map(lambda x:(0,0,self.line_get_convert(cr, uid, x, exp.employee_id.company_id.partner_id, exp.date_confirm, context=context)), eml)
            journal_id = move_obj.browse(cr, uid, move_id, context).journal_id
            # post the journal entry if 'Skip 'Draft' State for Manual Entries' is checked
            move_obj.write(cr, uid, [move_id], {'line_ids': lines}, context=context)
            self.write(cr, uid, ids, {'account_move_id': move_id, 'state': 'done'}, context=context)
            move_obj.post(cr, uid, [move_id], context=context)
        return True

    def move_line_get(self, cr, uid, expense_id, context=None):
        res = []
        tax_obj = self.pool.get('account.tax')
        if context is None:
            context = {}
        exp = self.browse(cr, uid, expense_id, context=context)

        for line in exp.line_ids:
            mres = self.move_line_get_item(cr, uid, line, context)
            if not mres:
                continue
            res.append(mres)
            
            # Use the default tax on product or account
            taxes = []
            if line.product_id:
                fposition_id = False
                fpos_obj = self.pool.get('account.fiscal.position')
                fpos = fposition_id and fpos_obj.browse(cr, uid, fposition_id, context=context) or False
                product = line.product_id
                taxes = product.supplier_taxes_id
                # If taxes are not related to the product, maybe they are in the account
                if not taxes:
                    a = product.property_account_expense_id.id or product.categ_id.property_account_expense_categ_id.id
                    a = fpos_obj.map_account(cr, uid, fpos, a)
                    taxes = a and self.pool.get('account.account').browse(cr, uid, a, context=context).tax_ids or False
            if not taxes:
                continue

            # Calculate tax lines and adjust base line
            tax_ids = [tax.id for tax in taxes]
            tax_res = tax_obj.browse(cr, uid, tax_ids, context=context).compute_all(line.unit_amount, exp.currency_id, line.unit_quantity, line.product_id, exp.user_id.partner_id)
            res[-1]['price'] = tax_res['total_excluded']
            res[-1]['tax_ids'] = tax_ids
            for tax in tax_res['taxes']:
                res.append({
                    'type': 'tax',
                    'name': tax['name'],
                    'price_unit': tax['amount'],
                    'quantity': 1,
                    'price': tax['amount'],
                    'account_id': tax['account_id'] or mres['account_id'],
                    'tax_line_id': tax['id'],
                })
        return res

    def move_line_get_item(self, cr, uid, line, context=None):
        company = line.expense_id.company_id
        property_obj = self.pool.get('ir.property')
        if line.product_id:
            acc = line.product_id.property_account_expense_id
            if not acc:
                acc = line.product_id.categ_id.property_account_expense_categ_id
            if not acc:
                raise UserError(_('No purchase account found for the product %s (or for his category), please configure one.') % (line.product_id.name))
        else:
            acc = property_obj.get(cr, uid, 'property_account_expense_categ_id', 'product.category', context={'force_company': company.id})
            if not acc:
                raise UserError(_('Please configure Default Expense account for Product purchase: `property_account_expense_categ_id`.'))
        return {
            'type':'src',
            'name': line.name.split('\n')[0][:64],
            'price_unit':line.unit_amount,
            'quantity':line.unit_quantity,
            'price':line.total_amount,
            'account_id':acc.id,
            'product_id':line.product_id.id,
            'uom_id':line.uom_id.id,
            'account_analytic_id':line.analytic_account.id,
        }

    def action_view_move(self, cr, uid, ids, context=None):
        '''
        This function returns an action that display existing account.move of given expense ids.
        '''
        assert len(ids) == 1, 'This option should only be used for a single id at a time'
        expense = self.browse(cr, uid, ids[0], context=context)
        assert expense.account_move_id
        try:
            dummy, view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account', 'view_move_form')
        except ValueError, e:
            view_id = False
        result = {
            'name': _('Expense Account Move'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': expense.account_move_id.id,
        }
        return result


class product_template(osv.osv):
    _inherit = "product.template"
    _columns = {
        'hr_expense_ok': fields.boolean('Can be Expensed', help="Specify if the product can be selected in an HR expense line."),
    }


class hr_expense_line(osv.osv):
    _name = "hr.expense.line"
    _description = "Expense Line"

    def _amount(self, cr, uid, ids, field_name, arg, context=None):
        if not ids:
            return {}
        cr.execute("SELECT l.id,COALESCE(SUM(l.unit_amount*l.unit_quantity),0) AS amount FROM hr_expense_line l WHERE id IN %s GROUP BY l.id ",(tuple(ids),))
        res = dict(cr.fetchall())
        return res

    def _get_uom_id(self, cr, uid, context=None):
        result = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'product', 'product_uom_unit')
        return result and result[1] or False

    _columns = {
        'name': fields.char('Expense Note', required=True),
        'date_value': fields.date('Date', required=True),
        'expense_id': fields.many2one('hr.expense.expense', 'Expense', ondelete='cascade', select=True),
        'total_amount': fields.function(_amount, string='Total', digits=0),
        'unit_amount': fields.float('Unit Price', digits_compute=dp.get_precision('Product Price')),
        'unit_quantity': fields.float('Quantities', digits_compute= dp.get_precision('Product Unit of Measure')),
        'product_id': fields.many2one('product.product', 'Product', domain=[('hr_expense_ok','=',True)], required=True),
        'uom_id': fields.many2one('product.uom', 'Unit of Measure', required=True),
        'description': fields.text('Description'),
        'analytic_account': fields.many2one('account.analytic.account','Analytic account'),
        'ref': fields.char('Reference'),
        'sequence': fields.integer('Sequence', select=True, help="Gives the sequence order when displaying a list of expense lines."),
        }
    _defaults = {
        'unit_quantity': 1,
        'date_value': lambda *a: time.strftime('%Y-%m-%d'),
        'uom_id': _get_uom_id,
    }
    _order = "sequence, date_value desc"

    def onchange_product_id(self, cr, uid, ids, product_id, context=None):
        res = {}
        if product_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            res['name'] = product.name
            amount_unit = product.price_get('standard_price')[product.id]
            res['unit_amount'] = amount_unit
            res['uom_id'] = product.uom_id.id
        return {'value': res}

    def onchange_uom(self, cr, uid, ids, product_id, uom_id, context=None):
        res = {'value':{}}
        if not uom_id or not product_id:
            return res
        product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
        uom = self.pool.get('product.uom').browse(cr, uid, uom_id, context=context)
        if uom.category_id.id != product.uom_id.category_id.id:
            res['warning'] = {'title': _('Warning'), 'message': _('Selected Unit of Measure does not belong to the same category as the product Unit of Measure')}
            res['value'].update({'uom_id': product.uom_id.id})
        return res


class account_move_line(osv.osv):
    _inherit = "account.move.line"

    def reconcile(self, cr, uid, ids, writeoff_acc_id=False, writeoff_journal_id=False, context=None):
        res = super(account_move_line, self).reconcile(cr, uid, ids, writeoff_acc_id=writeoff_acc_id, writeoff_journal_id=writeoff_journal_id, context=context)
        #when making a full reconciliation of account move lines 'ids', we may need to recompute the state of some hr.expense
        account_move_ids = [aml.move_id.id for aml in self.browse(cr, uid, ids, context=context)]
        expense_obj = self.pool.get('hr.expense.expense')
        currency_obj = self.pool.get('res.currency')
        if account_move_ids:
            expense_ids = expense_obj.search(cr, uid, [('account_move_id', 'in', account_move_ids)], context=context)
            for expense in expense_obj.browse(cr, uid, expense_ids, context=context):
                if expense.state == 'done':
                    #making the postulate it has to be set paid, then trying to invalidate it
                    new_status_is_paid = True
                    for aml in expense.account_move_id.line_ids:
                        if aml.account_id.internal_type == 'payable' and not currency_obj.is_zero(cr, uid, expense.company_id.currency_id, aml.amount_residual):
                            new_status_is_paid = False
                    if new_status_is_paid:
                        expense_obj.write(cr, uid, [expense.id], {'state': 'paid'}, context=context)
        return res
