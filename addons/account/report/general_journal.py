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

import pooler
from common_report_header import common_report_header
from report import report_sxw
#
# Use period and Journal for selection or resources
#
class journal_print(report_sxw.rml_parse, common_report_header):

    def __init__(self, cr, uid, name, context=None):
        if context is None:
            context = {}
        super(journal_print, self).__init__(cr, uid, name, context=context)
        self.period_ids = []
        self.journal_ids = []
        self.localcontext.update( {
            'time': time,
            'lines': self.lines,
            'periods': self.periods,
            'sum_debit_period': self._sum_debit_period,
            'sum_credit_period': self._sum_credit_period,
            'sum_debit': self._sum_debit,
            'sum_credit': self._sum_credit,
            'get_fiscalyear': self._get_fiscalyear,
            'get_account': self._get_account,
            'get_start_period': self.get_start_period,
            'get_end_period': self.get_end_period,
            'get_sortby': self._get_sortby,
            'sum_currency_amount_account': self._sum_currency_amount_account,     
            'get_filter': self._get_filter,                                  
        })

    def set_context(self, objects, data, ids, report_type=None): # Improve move to common default?
        new_ids = ids
        self.query_get_clause = ''
        if (data['model'] == 'ir.ui.menu'):
            new_ids = 'active_ids' in data['form'] and data['form']['active_ids'] or []
            self.query_get_clause = 'AND '
            self.query_get_clause += data['form']['query_line'] or ''
            objects = self.pool.get('account.journal.period').browse(self.cr, self.uid, new_ids)
        if new_ids:
            self.cr.execute('SELECT period_id, journal_id FROM account_journal_period WHERE id IN %s', (tuple(new_ids),))
            res = self.cr.fetchall()
            self.period_ids, self.journal_ids = zip(*res)
        return super(journal_print, self).set_context(objects, data, ids, report_type)

    # returns a list of period objs
    def periods(self, journal_period_objs):
        dic = {}
        def filter_unique(o):
            key = o.period_id.id
            res = key in dic
            if not res:
                dic[key] = True
            return not res
        filtered_objs = filter(filter_unique, journal_period_objs)
        return map(lambda x: x.period_id, filtered_objs)

    def lines(self, period_id, journal_id=[]):
        if not self.journal_ids:
            return []
        self.cr.execute('SELECT j.code, j.name, l.amount_currency,c.code AS currency_code, '
                        'SUM(l.debit) AS debit, SUM(l.credit) AS credit '
                        'FROM account_move_line l '
                        'LEFT JOIN account_journal j ON (l.journal_id=j.id) '
                        'LEFT JOIN res_currency c on (l.currency_id=c.id)'
                        'WHERE period_id=%s AND journal_id IN %s '+self.query_get_clause +''
                        'GROUP BY j.id, j.code, j.name, l.amount_currency,c.code ',
                        (period_id, tuple(self.journal_ids)))

        return self.cr.dictfetchall()
    def _set_get_account_currency_code(self, account_id):
        self.cr.execute("SELECT c.code as code "\
                "FROM res_currency c,account_account as ac "\
                "WHERE ac.id = %s AND ac.currency_id = c.id"%(account_id))
        result = self.cr.fetchone()
        if result:
            self.account_currency = result[0]
        else:
            self.account_currency = False

    def _sum_currency_amount_account(self, account, form):
        self._set_get_account_currency_code(account.id)
        self.cr.execute("SELECT sum(aml.amount_currency) FROM account_move_line as aml,res_currency as rc WHERE aml.currency_id = rc.id AND aml.account_id= %s ", (account.id,))
        total = self.cr.fetchone()

        if self.account_currency:
            return_field = str(total[0]) + self.account_currency
            return return_field
        else:
            currency_total = self.tot_currency = 0.0
            return currency_total  
report_sxw.report_sxw('report.account.general.journal', 'account.journal.period', 'addons/account/report/general_journal.rml', parser=journal_print, header='internal')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: