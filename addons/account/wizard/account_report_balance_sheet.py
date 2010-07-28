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

class account_bs_report(osv.osv_memory):
    """
    This wizard will provide the account balance sheet report by periods, between any two dates.
    """
    _name = 'account.bs.report'
    _inherit = "account.common.account.report"
    _description = 'Account Balance Sheet Report'

    _columns = {
        'display_type': fields.boolean("Landscape Mode"),
        'reserve_account_id': fields.many2one('account.account', 'Reserve & Surplus Account',required = True,
                                      help='This Account is used for trasfering Profit/Loss(If It is Profit : Amount will be added, Loss : Amount will be duducted.), Which is calculated from Profilt & Loss Report', domain = [('type','=','payable')]),
        }

    _defaults={
        'display_type': True,
        }

    def _print_report(self, cr, uid, ids, data, query_line, context=None):
        if context is None:
            context = {}
        data = self.pre_print_report(cr, uid, ids, data, query_line, context=context)
        data['form'].update(self.read(cr, uid, ids, ['display_type', 'reserve_account_id'])[0])
        if data['form']['display_type']:
            return {
                'type': 'ir.actions.report.xml',
                'report_name': 'account.balancesheet.horizontal',
                'datas': data,
                }
        else:
            return {
                'type': 'ir.actions.report.xml',
                'report_name': 'account.balancesheet',
                'datas': data,
                }

account_bs_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: