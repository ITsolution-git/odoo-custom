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

from osv import osv, fields
import time
from tools.translate import _


def get_journal(self, cr, uid, context):
    """
             Make the selection list of Cash Journal  .
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param context: A standard dictionary
             @return :Return the list of journal
    """

    obj = self.pool.get('account.journal')
    statement_obj = self.pool.get('account.bank.statement')
    user = self.pool.get('res.users').browse(cr, uid, uid)
    ids = obj.search(cr, uid, [('type', '=', 'cash'), ('company_id', '=', user.company_id.id)])
    obj_ids= statement_obj.search(cr, uid, [('state', '!=', 'confirm'), ('user_id', '=', uid), ('journal_id', 'in', ids)])
    res_obj = obj.read(cr, uid, ids, ['journal_id'], context)
    res_obj = [(r1['id'])for r1 in res_obj]
    res = statement_obj.read(cr, uid, obj_ids, ['journal_id'], context)
    res = [(r['journal_id']) for r in res]
    return res

class pos_box_entries(osv.osv_memory):
    _name = 'pos.box.entries'
    _description = 'Pos Box Entries'



    def _get_income_product(self, cr, uid, context):

        """
             Make the selection list of purchasing  products.
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param context: A standard dictionary
             @return :Return of operation of product
        """
        obj = self.pool.get('product.product')
        ids = obj.search(cr, uid, [('income_pdt', '=', True)])
        res = obj.read(cr, uid, ids, ['id', 'name'], context)
        res = [(r['id'],r['name']) for r in res]
        res.insert(0, ('', ''))

        return res


    _columns = {
                'name': fields.char('Description', size=32, required=True),
                'journal_id': fields.selection(get_journal, "Register", required=True),
                'product_id': fields.selection(_get_income_product, "Operation", required=True),
                'amount': fields.float('Amount', digits=(16, 2)),
                'ref': fields.char('Ref', size=32),
    }
    _defaults = {
                 'journal_id': lambda *a: 1,
                 'product_id': lambda *a: 1,
                }

    def get_in(self, cr, uid, ids, context):
        """
             Create the entry of statement in journal.
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param context: A standard dictionary
             @return :Return of operation of product
        """
        statement_obj = self.pool.get('account.bank.statement')
        product_obj = self.pool.get('product.template')
        res_obj = self.pool.get('res.users')
        product_obj = self.pool.get('product.product')
        bank_statement = self.pool.get('account.bank.statement.line')
        for data in  self.read(cr, uid, ids):
            args = {}
            curr_company = res_obj.browse(cr, uid, uid).company_id.id
            statement_id = statement_obj.search(cr, uid, [('journal_id', '=', data['journal_id']), ('company_id', '=', curr_company), ('user_id', '=', uid), ('state', '=', 'open')])
            if not statement_id:
                raise osv.except_osv(_('Error !'), _('You have to open at least one cashbox'))

            acc_id = product_obj.browse(cr, uid, data['product_id']).property_account_income
            if not acc_id:
                raise osv.except_osv(_('Error !'), _('Please check that income account is set to %s')%(product_obj.browse(cr, uid, data['product_id']).name))
            if statement_id:
                statement_id = statement_id[0]
            if not statement_id:
                statement_id = statement_obj.create(cr, uid, {'date': time.strftime('%Y-%m-%d 00:00:00'),
                                                            'journal_id': data['journal_id'],
                                                            'company_id': curr_company,
                                                            'user_id': uid,
                                                           })

            args['statement_id'] = statement_id
            args['journal_id'] = data['journal_id']
            if acc_id:
                args['account_id'] = acc_id.id
            args['amount'] = data['amount'] or 0.0
            args['ref'] = "%s" % (data['ref'] or '')
            args['name'] = "%s: %s " % (product_obj.browse(cr, uid, data['product_id']).name, data['name'].decode('utf8'))
            address_u = res_obj.browse(cr, uid, uid).address_id
            if address_u:
                partner_id = address_u.partner_id and address_u.partner_id.id or None
                args['partner_id'] = partner_id
            statement_line_id = bank_statement.create(cr, uid, args)

            return {}

pos_box_entries()

