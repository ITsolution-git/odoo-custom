# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2005-2006 CamptoCamp
# Copyright (c) 2006-2010 OpenERP S.A
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

import time

from report import report_sxw
from common_report_header import common_report_header
import rml_parse
import pooler

class general_ledger(rml_parse.rml_parse, common_report_header):
    _name = 'report.account.general.ledger'

    def set_context(self, objects, data, ids, report_type=None):
        new_ids = ids
        self.query = data['form']['query_line']
        if (data['model'] == 'ir.ui.menu'):
            new_ids = [data['form']['chart_account_id']]
        self.sortby = data['form']['sortby']
        objects = self.pool.get('account.account').browse(self.cr, self.uid, new_ids)
        super(general_ledger, self).set_context(objects, data, new_ids, report_type=report_type)

    def __init__(self, cr, uid, name, context=None):
        if context is None:
            context = {}
        super(general_ledger, self).__init__(cr, uid, name, context=context)
        self.query = ""
        self.tot_currency = 0.0
        self.period_sql = ""
        self.sold_accounts = {}
        self.sortby = 'sort_date'
        self.localcontext.update( {
            'time': time,
            'lines': self.lines,
            'sum_debit_account': self._sum_debit_account,
            'sum_credit_account': self._sum_credit_account,
            'sum_balance_account': self._sum_balance_account,
            'get_children_accounts': self.get_children_accounts,
            'sum_currency_amount_account': self._sum_currency_amount_account,
            'get_fiscalyear': self._get_fiscalyear,
            'get_journal': self._get_journal,
            'get_account': self._get_account,
            'get_start_period': self.get_start_period,
            'get_end_period': self.get_end_period,
            'get_filter': self._get_filter,
            'get_sortby': self._get_sortby
        })
        self.context = context

    def get_children_accounts(self, account, form):
        res = []
        ids_acc = self.pool.get('account.account')._get_children_and_consol(self.cr, self.uid, account.id)
        for child_account in self.pool.get('account.account').browse(self.cr, self.uid, ids_acc):
            sql = """
                SELECT count(id)
                FROM account_move_line l
                WHERE %s AND l.account_id = %%s
            """ % (self.query)
            self.cr.execute(sql, (child_account.id,))
            num_entry = self.cr.fetchone()[0] or 0
            sold_account = self._sum_balance_account(child_account,form)
            self.sold_accounts[child_account.id] = sold_account
            if form['display_account'] == 'mouvement':
                if child_account.type != 'view' and num_entry <> 0 :
                    res.append(child_account)
            elif form['display_account'] == 'balance':
                if child_account.type != 'view' and num_entry <> 0 :
                    if ( sold_account <> 0.0):
                        res.append(child_account)
            else:
                res.append(child_account)
        if not len(res):
            return [account]
        return res

    def lines(self, account, form):
        """ Return all the account_move_line of account with their account code counterparts """
        # First compute all counterpart strings for every move_id where this account appear.
        # Currently, the counterpart info is used only in landscape mode
        sql = """
            SELECT m1.move_id,
            array_to_string(ARRAY(SELECT DISTINCT a.code FROM account_move_line m2 LEFT JOIN account_account a ON (m2.account_id=a.id) WHERE m2.move_id = m1.move_id AND m2.account_id<>%%s), ', ') AS counterpart
            FROM (SELECT move_id FROM account_move_line l WHERE %s AND l.account_id = %%s GROUP BY move_id) m1
        """ % self.query
        self.cr.execute(sql, (account.id, account.id))
        counterpart_res = self.cr.dictfetchall()
        counterpart_accounts = {}
        for i in counterpart_res:
            counterpart_accounts[i['move_id']]=i['counterpart']
        del counterpart_res

        # Then select all account_move_line of this account
        if self.sortby == 'sort_journal_partner':
            sql_sort='j.code, p.name'
        else:
            sql_sort='l.date'
        sql = """
            SELECT l.id as lid, l.date as ldate, j.code as lcode, l.amount_currency,l.ref as lref, l.name as lname, COALESCE(l.debit,0) AS debit, COALESCE(l.credit,0) AS credit, l.period_id as lperiod_id, l.partner_id as lpartner_id,
            m.name AS move_name, m.id AS mmove_id,
            c.code AS currency_code,
            i.id AS invoice_id, i.type AS invoice_type, i.number AS invoice_number,
            p.name AS partner_name
            FROM account_move_line l
            LEFT JOIN account_move m on (l.move_id=m.id)
            LEFT JOIN res_currency c on (l.currency_id=c.id)
            LEFT JOIN res_partner p on (l.partner_id=p.id)
            LEFT JOIN account_invoice i on (m.id =i.move_id)
            JOIN account_journal j on (l.journal_id=j.id)
            WHERE %s AND l.account_id = %%s ORDER by %s
        """ % (self.query, sql_sort)
        self.cr.execute(sql, (account.id,))
        res_lines = self.cr.dictfetchall()
        res_init = []
        if res_lines and form['initial_balance']:
            #FIXME: replace the label of lname with a string translatable
            sql = """
                SELECT 0 AS lid, '' AS ldate, '' as lcode, COALESCE(SUM(l.amount_currency),0.0) as amount_currency, '' as lref, 'Initial Balance' as lname, COALESCE(SUM(l.debit),0.0) AS debit, COALESCE(SUM(l.credit),0.0) AS credit, '' AS lperiod_id, '' AS lpartner_id,
                '' AS move_name, '' AS mmove_id,
                '' AS currency_code,
                '' AS invoice_id, '' AS invoice_type, '' AS invoice_number,
                '' AS partner_name
                FROM account_move_line l
                LEFT JOIN account_move m on (l.move_id=m.id)
                LEFT JOIN res_currency c on (l.currency_id=c.id)
                LEFT JOIN res_partner p on (l.partner_id=p.id)
                LEFT JOIN account_invoice i on (m.id =i.move_id)
                JOIN account_journal j on (l.journal_id=j.id)
                WHERE %s AND l.account_id = %%s
            """ %(form['initial_bal_query'])

            self.cr.execute(sql, (account.id,))
            res_init = self.cr.dictfetchall()
        res = res_init + res_lines
        account_sum = 0.0
        inv_types = { 'out_invoice': 'CI', 'in_invoice': 'SI', 'out_refund': 'OR', 'in_refund': 'SR', }
        for l in res:
            l['move'] = l['move_name']
            if l['invoice_id']:
                l['lref'] = '%s: %s'%(inv_types[l['invoice_type']], l['invoice_number'])
            l['partner'] = l['partner_name'] or ''
            account_sum += l['debit'] - l['credit']
            l['progress'] = account_sum
            l['line_corresp'] = l['mmove_id'] == '' and ' ' or counterpart_accounts[l['mmove_id']]
            # Modification of amount Currency
            if l['credit'] > 0:
                if l['amount_currency'] != None:
                    l['amount_currency'] = abs(l['amount_currency']) * -1
            if l['amount_currency'] != None:
                self.tot_currency = self.tot_currency + l['amount_currency']
        return res

    def _sum_debit_account(self, account, form):
        self.cr.execute("SELECT sum(debit) "\
                "FROM account_move_line l "\
                "WHERE l.account_id = %s AND %s "%(account.id, self.query))
        sum_debit = self.cr.fetchone()[0] or 0.0
        if form.get('initial_balance', False):
            self.cr.execute("SELECT sum(debit) "\
                    "FROM account_move_line l "\
                    "WHERE l.account_id = %s AND %s "%(account.id, form['initial_bal_query']))
            # Add initial balance to the result
            sum_debit += self.cr.fetchone()[0] or 0.0
        return sum_debit

    def _sum_credit_account(self, account, form):
        self.cr.execute("SELECT sum(credit) "\
                "FROM account_move_line l "\
                "WHERE l.account_id = %s AND %s "%(account.id, self.query))
        sum_credit = self.cr.fetchone()[0] or 0.0
        if form.get('initial_balance', False):
            self.cr.execute("SELECT sum(credit) "\
                    "FROM account_move_line l "\
                    "WHERE l.account_id = %s AND %s "%(account.id, form['initial_bal_query']))
            # Add initial balance to the result
            sum_credit += self.cr.fetchone()[0] or 0.0
        return sum_credit

    def _sum_balance_account(self, account, form):
        self.cr.execute("SELECT (sum(debit) - sum(credit)) as tot_balance "\
                "FROM account_move_line l "\
                "WHERE l.account_id = %s AND %s"%(account.id, self.query))
        sum_balance = self.cr.fetchone()[0] or 0.0
        if form.get('initial_balance', False):
            self.cr.execute("SELECT (sum(debit) - sum(credit)) as tot_balance "\
                    "FROM account_move_line l "\
                    "WHERE l.account_id = %s AND %s "%(account.id, form['initial_bal_query']))
            # Add initial balance to the result
            sum_balance += self.cr.fetchone()[0] or 0.0
        return sum_balance

    def _sum_currency_amount_account(self, account, form):
        #FIXME: not working
        self.cr.execute("SELECT sum(l.amount_currency) as tot_currency "\
                "FROM account_move_line l "\
                "WHERE l.account_id = %s AND %s"%(account.id, self.query))
        sum_currency = self.cr.fetchone()[0] or 0.0
        if form.get('initial_balance', False):
            self.cr.execute("SELECT sum(l.amount_currency) as tot_currency "\
                    "FROM account_move_line l "\
                    "WHERE l.account_id = %s AND %s "%(account.id, form['initial_bal_query']))
            # Add initial balance to the result
            sum_currency += self.cr.fetchone()[0] or 0.0
        return str(sum_currency)

report_sxw.report_sxw('report.account.general.ledger', 'account.account', 'addons/account/report/general_ledger.rml', parser=general_ledger, header='internal')
report_sxw.report_sxw('report.account.general.ledger_landscape', 'account.account', 'addons/account/report/general_ledger_landscape.rml', parser=general_ledger, header='internal')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
