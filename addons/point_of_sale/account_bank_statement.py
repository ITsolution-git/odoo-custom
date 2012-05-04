# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2008 PC Solutions (<http://pcsol.be>). All Rights Reserved
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

from osv import fields, osv

class account_journal(osv.osv):
    _inherit = 'account.journal'
    _columns = {
        'journal_user': fields.boolean('PoS Payment Method', help="Check this box if this journal define a payment method that can be used in point of sales."),

        'opening_control': fields.boolean('Opening Control', help="If you want the journal should be control at opening, check this option"),
        'closing_control': fields.boolean('Closing Control', help="If you want the journal should be control at closing, check this option"),

    }
    _defaults = {
        'opening_control' : True,
        'closing_control' : True,
    }

account_journal()

class account_cash_statement(osv.osv):
    _inherit = 'account.bank.statement'

    #def _equal_balance(self, cr, uid, cash_id, context=None):
    #    statement = self.browse(cr, uid, cash_id, context=context)
    #    if not statement.journal_id.check_dtls:
    #        return True
    #    if statement.journal_id.check_dtls and (statement.balance_end != statement.balance_end_cash):
    #        return False
    #    else:
    #        return True

    def _get_cash_open_box_lines(self, cr, uid, context=None):
        res = super(account_cash_statement,self)._get_cash_open_box_lines(cr, uid, context)
        curr = [0.01, 0.02, 0.05, 0.10, 0.20, 0.50]
        for rs in curr:
            dct = {
                'pieces': rs,
                'number': 0
            }
            res.append(dct)
        res.sort()
        return res

    def _get_default_cash_close_box_lines(self, cr, uid, context=None):
        res = super(account_cash_statement,self)._get_default_cash_close_box_lines(cr, uid, context=context)
        curr = [0.01, 0.02, 0.05, 0.10, 0.20, 0.50]
        for rs in curr:
            dct = {
                'pieces': rs,
                'number': 0
            }
            res.append(dct)
        res.sort()
        return res

account_cash_statement()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
