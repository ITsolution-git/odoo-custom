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

from osv import osv
from tools.translate import _


class pos_close_statement(osv.osv_memory):
    _name = 'pos.close.statement'
    _description = 'Close Statements'

    def close_statement(self, cr, uid, ids, context):
        """
             Close the statements
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param context: A standard dictionary
             @return : Blank Dictionary
        """
        company_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.id
        list_statement = []
        mod_obj = self.pool.get('ir.model.data')
        statement_obj = self.pool.get('account.bank.statement')
        journal_obj = self.pool.get('account.journal')
        journal_lst = journal_obj.search(cr, uid, [('company_id', '=', company_id), ('auto_cash', '=', True), ('check_dtls', '=', False)])
        journal_ids = journal_obj.browse(cr, uid, journal_lst)
        for journal in journal_ids:
            ids = statement_obj.search(cr, uid, [('state', '!=', 'confirm'), ('user_id', '=', uid), ('journal_id', '=', journal.id)])
            list_statement = ids
            statement_obj.button_confirm(cr, uid, ids, context)
#        if not list_statement:
#            return {}
        model_data_ids = mod_obj.search(cr, uid,[('model','=','ir.ui.view'),('name','=','view_bank_statement_tree')], context=context)
        resource_id = mod_obj.read(cr, uid, model_data_ids, fields=['res_id'], context=context)[0]['res_id']
        return {
                'domain': "[('id','in', list_statement)]",
                'name': 'Close Statements',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_model': 'account.bank.statement',
                'views': [(resource_id,'tree')],
                'type': 'ir.actions.act_window'
}

pos_close_statement()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

