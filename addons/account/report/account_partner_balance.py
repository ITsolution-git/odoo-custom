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
import re
import copy

from report import report_sxw
from common_report_header import common_report_header

class partner_balance(report_sxw.rml_parse, common_report_header):

    def __init__(self, cr, uid, name, context=None):
        if context is None:
            context = {}
        super(partner_balance, self).__init__(cr, uid, name, context=context)
        self.account_ids = []
        self.localcontext.update( {
            'time': time,
            'lines': self.lines,
            'sum_debit': self._sum_debit,
            'sum_credit': self._sum_credit,
            'sum_litige': self._sum_litige,
            'sum_sdebit': self._sum_sdebit,
            'sum_scredit': self._sum_scredit,
            'solde_debit': self._solde_balance_debit,
            'solde_credit': self._solde_balance_credit,
            'get_currency': self._get_currency,
            'comma_me' : self.comma_me,
            'get_fiscalyear': self._get_fiscalyear,
            'get_periods':self.get_periods,
            'get_journal': self._get_journal,
            'get_filter': self._get_filter,
            'get_account': self._get_account,
            'get_start_date':self._get_start_date,
            'get_end_date':self._get_end_date,
            'get_start_period': self.get_start_period,
            'get_end_period': self.get_end_period,
            'get_partners':self._get_partners,
        })
        ## Compute account list one time
    #
    # Date Management
    #

    def get_periods(self, form):
        result = ''
        if form.has_key('periods') and form['periods']:
            period_ids = form['periods']
            per_ids = self.pool.get('account.period').browse(self.cr, self.uid, form['periods'])
            for r in per_ids:
                if r == per_ids[len(per_ids)-1]:
                    result += r.name + ". "
                else:
                    result += r.name + ", "
        else:
            fy_obj = self.pool.get('account.fiscalyear').browse(self.cr, self.uid, form['fiscalyear'])
            res = fy_obj.period_ids
            len_res = len(res)
            for r in res:
                if r == res[len_res-1]:
                    result += r.name + ". "
                else:
                    result += r.name + ", "
        return str(result and result[:-1]) or 'ALL'

    def comma_me(self, amount):
        if type(amount) is float :
            amount = str('%.2f'%amount)
        else :
            amount = str(amount)
        if (amount == '0'):
             return ' '
        orig = amount
        new = re.sub("^(-?\d+)(\d{3})", "\g<1>'\g<2>", amount)
        if orig == new:
            return new
        else:
            return self.comma_me(new)

    def set_context(self, objects, data, ids, report_type=None):
        ## Compute Code
        #
        self.initial_balance = data['form'].get('initial_balance', True)
        self.query = data['form'].get('query_line', '')
        self.init_query = data['form'].get('initial_bal_query', '')
        self.result_selection = data['form'].get('result_selection')

        if (self.result_selection == 'customer' ):
            self.ACCOUNT_TYPE = ('receivable',)
        elif (self.result_selection == 'supplier'):
            self.ACCOUNT_TYPE = ('payable',)
        else:
            self.ACCOUNT_TYPE = ('payable', 'receivable')

        self.cr.execute("SELECT a.id " \
                "FROM account_account a " \
                "LEFT JOIN account_account_type t " \
                    "ON (a.type = t.code) " \
                    "WHERE a.type IN %s " \
                    "AND a.active", (self.ACCOUNT_TYPE,))
        self.account_ids = [a for (a,) in self.cr.fetchall()]
        return super(partner_balance, self).set_context(objects, data, ids, report_type=report_type)

    def lines(self, data):
        full_account = []
        result_tmp = 0.0
        self.cr.execute(
            "SELECT p.ref,l.account_id,ac.name AS account_name,ac.code AS code ,p.name, sum(debit) AS debit, sum(credit) AS credit, " \
                    "CASE WHEN sum(debit) > sum(credit) " \
                        "THEN sum(debit) - sum(credit) " \
                        "ELSE 0 " \
                    "END AS sdebit, " \
                    "CASE WHEN sum(debit) < sum(credit) " \
                        "THEN sum(credit) - sum(debit) " \
                        "ELSE 0 " \
                    "END AS scredit, " \
                    "(SELECT sum(debit-credit) " \
                        "FROM account_move_line l " \
                        "WHERE partner_id = p.id " \
                            "AND " + self.query + " " \
                            "AND blocked = TRUE " \
                    ") AS enlitige " \
            "FROM account_move_line l LEFT JOIN res_partner p ON (l.partner_id=p.id) " \
            "JOIN account_account ac ON (l.account_id = ac.id)" \
            "WHERE ac.type IN %s " \
            "AND " + self.query + "" \
            "GROUP BY p.id, p.ref, p.name,l.account_id,ac.name,ac.code " \
            "ORDER BY l.account_id,p.name",
            (self.ACCOUNT_TYPE,))
        res = self.cr.dictfetchall()

        #For include intial balance..
        if self.initial_balance:
            self.cr.execute(
                "SELECT '1' AS type, '' AS ref, l.account_id AS account_id, '' AS account_name, '' AS code, '' AS name, sum(debit) AS debit, sum(credit) AS credit, " \
                        "CASE WHEN sum(debit) > sum(credit) " \
                            "THEN sum(debit) - sum(credit) " \
                            "ELSE 0 " \
                        "END AS sdebit, " \
                        "CASE WHEN sum(debit) < sum(credit) " \
                            "THEN sum(credit) - sum(debit) " \
                            "ELSE 0 " \
                        "END AS scredit, " \
                        "(SELECT sum(debit-credit) " \
                            "FROM account_move_line l " \
                            "WHERE partner_id = p.id " \
                                " AND  " + self.init_query + " " \
                                "AND blocked = TRUE " \
                        ") AS enlitige " \
                "FROM account_move_line l LEFT JOIN res_partner p ON (l.partner_id=p.id) " \
                "JOIN account_account ac ON (l.account_id = ac.id) " \
                "WHERE ac.type IN %s " \
                "AND " + self.init_query + "" \
                "GROUP BY p.id, p.ref, p.name,l.account_id,ac.name,ac.code " \
                "ORDER BY l.account_id, p.name",
                (self.ACCOUNT_TYPE, ))
            res1 = self.cr.dictfetchall()
            final_init = {}
            res_init = {}
            debit = credit = 0
            for r in res1:
                if final_init.get(r['account_id'], False):
                    res_init = final_init[r['account_id']]
                    debit += final_init[r['account_id']]['debit']
                    credit += final_init[r['account_id']]['credit']
                    res_init['credit'] = credit
                    res_init['debit'] = debit
                    res_init['type'] = 3
                    res_init['ref'] = ''
                    res_init['code'] = ''
                    res_init['name'] = 'Initial Balance'
                    res_init['balance'] = debit - credit
                    res_init['enlitige'] = 0.0 # fix me
                    res_init['account_id'] = final_init[r['account_id']]['account_id']
                else:
                    res_init = {}
                    debit = r['debit']
                    credit = r['credit']
                    res_init['credit'] = credit
                    res_init['debit'] = debit
                    res_init['type'] = 3
                    res_init['ref'] = ''
                    res_init['code'] = ''
                    res_init['name'] = 'Initial Balance'
                    res_init['balance'] = debit - credit
                    res_init['enlitige'] = 0.0 # fix me
                    res_init['account_id'] = r['account_id']
                final_init[r['account_id']] = res_init
        for r in res:
            full_account.append(r)

        ## We will now compute Total
        subtotal_row = self._add_subtotal(full_account)
        if not self.initial_balance:
            return subtotal_row

        #If include initial balance is selected..
        subtotal = copy.deepcopy(subtotal_row)
        init_acnt = []
        for row in subtotal_row:
            if final_init and row.get('account_id', False) and not row['account_id'] in init_acnt and final_init.get(row['account_id'], False):
                subtotal.insert(subtotal.index(row), final_init[row['account_id']])
                init_acnt.append(row['account_id'])
        return subtotal

    def _add_subtotal(self, cleanarray):
        i = 0
        completearray = []
        tot_debit = 0.0
        tot_credit = 0.0
        tot_scredit = 0.0
        tot_sdebit = 0.0
        tot_enlitige = 0.0
        for r in cleanarray:
            # For the first element we always add the line
            # type = 1 is the line is the first of the account
            # type = 2 is an other line of the account
            if i==0:
                # We add the first as the header
                #
                ##
                new_header = {}
                new_header['ref'] = ''
                new_header['name'] = r['account_name']
                new_header['code'] = r['code']
                new_header['debit'] = r['credit'] #tot_credit
                new_header['credit'] = r['debit'] #tot_debit
                new_header['scredit'] = tot_scredit
                new_header['sdebit'] = tot_sdebit
                new_header['enlitige'] = tot_enlitige
                new_header['balance'] = float(tot_sdebit) - float(tot_scredit)
                new_header['type'] = 3
                ##
                completearray.append(new_header)
                #
                r['type'] = 1
                r['balance'] = float(r['sdebit']) - float(r['scredit'])

                completearray.append(r)
                #
                tot_debit = r['debit']
                tot_credit = r['credit']
                tot_scredit = r['scredit']
                tot_sdebit = r['sdebit']
                tot_enlitige = (r['enlitige'] or 0.0)
                #
            else:
                if cleanarray[i]['account_id'] <> cleanarray[i-1]['account_id']:

                    new_header['debit'] = tot_debit
                    new_header['credit'] = tot_credit
                    new_header['scredit'] = tot_scredit
                    new_header['sdebit'] = tot_sdebit
                    new_header['enlitige'] = tot_enlitige
                    new_header['balance'] = float(tot_sdebit) - float(tot_scredit)
                    new_header['type'] = 3
                    # we reset the counter
                    tot_debit = r['debit']
                    tot_credit = r['credit']
                    tot_scredit = r['scredit']
                    tot_sdebit = r['sdebit']
                    tot_enlitige = (r['enlitige'] or 0.0)
                    #
                    ##
                    new_header = {}
                    new_header['ref'] = ''
                    new_header['name'] = r['account_name']
                    new_header['code'] = r['code']
                    new_header['debit'] = tot_debit
                    new_header['credit'] = tot_credit
                    new_header['scredit'] = tot_scredit
                    new_header['sdebit'] = tot_sdebit
                    new_header['enlitige'] = tot_enlitige
                    new_header['balance'] = float(tot_sdebit) - float(tot_scredit)
                    new_header['type'] = 3
                    ##get_fiscalyear
                    ##

                    completearray.append(new_header)
                    ##
                    #
                    r['type'] = 1
                    #
                    r['balance'] = float(r['sdebit']) - float(r['scredit'])

                    completearray.append(r)

                if cleanarray[i]['account_id'] == cleanarray[i-1]['account_id']:
                    # we reset the counter

                    new_header['debit'] = tot_debit
                    new_header['credit'] = tot_credit
                    new_header['scredit'] = tot_scredit
                    new_header['sdebit'] = tot_sdebit
                    new_header['enlitige'] = tot_enlitige
                    new_header['balance'] = float(tot_sdebit) - float(tot_scredit)
                    new_header['type'] = 3

                    tot_debit = tot_debit + r['debit']
                    tot_credit = tot_credit + r['credit']
                    tot_scredit = tot_scredit + r['scredit']
                    tot_sdebit = tot_sdebit + r['sdebit']
                    tot_enlitige = tot_enlitige + (r['enlitige'] or 0.0)

                    new_header['debit'] = tot_debit
                    new_header['credit'] = tot_credit
                    new_header['scredit'] = tot_scredit
                    new_header['sdebit'] = tot_sdebit
                    new_header['enlitige'] = tot_enlitige
                    new_header['balance'] = float(tot_sdebit) - float(tot_scredit)

                    #
                    r['type'] = 2
                    #
                    r['balance'] = float(r['sdebit']) - float(r['scredit'])
                    #

                    completearray.append(r)

            i = i + 1
        return completearray

    def _sum_debit(self, data):
        if not self.ids:
            return 0.0
        temp_res = 0.0
        self.cr.execute(
                "SELECT sum(debit) " \
                "FROM account_move_line AS l " \
                "WHERE l.account_id IN %s"  \
                    "AND " + self.query + "" ,
                    (tuple(self.account_ids), ))
        temp_res = float(self.cr.fetchone()[0] or 0.0)
        if self.initial_balance:
            self.cr.execute(
                    "SELECT sum(debit) " \
                    "FROM account_move_line AS l " \
                    "WHERE l.account_id IN %s "  \
                        "AND " + self.init_query + "" ,
                        (tuple(self.account_ids), ))
            temp_res += float(self.cr.fetchone()[0] or 0.0)
        return temp_res

    def _sum_credit(self, data):
        if not self.ids:
            return 0.0
        temp_res = 0.0
        self.cr.execute(
                "SELECT sum(credit) " \
                "FROM account_move_line AS l " \
                "WHERE l.account_id IN %s" \
                    "AND " + self.query + "" ,
                    (tuple(self.account_ids),))
        temp_res = float(self.cr.fetchone()[0] or 0.0)
        if self.initial_balance:
            self.cr.execute(
                    "SELECT sum(credit) " \
                    "FROM account_move_line AS l " \
                    "WHERE l.account_id IN %s " \
                        "AND " + self.init_query + "" ,
                        (tuple(self.account_ids),))
            temp_res += float(self.cr.fetchone()[0] or 0.0)
        return temp_res

    def _sum_litige(self, data):
        if not self.ids:
            return 0.0
        temp_res = 0.0
        self.cr.execute(
                "SELECT sum(debit-credit) " \
                "FROM account_move_line AS l " \
                "WHERE l.account_id IN %s" \
                    "AND " + self.query + " " \
                    "AND l.blocked=TRUE ",
                    (tuple(self.account_ids), ))
        temp_res = float(self.cr.fetchone()[0] or 0.0)
        if self.initial_balance:
            self.cr.execute(
                    "SELECT sum(debit-credit) " \
                    "FROM account_move_line AS l " \
                    "WHERE l.account_id IN %s " \
                        "AND l.blocked=TRUE  "\
                        "AND " + self.init_query + "" ,
                        (tuple(self.account_ids), ))
            temp_res += float(self.cr.fetchone()[0] or 0.0)
        return temp_res

    def _sum_sdebit(self, data):
        if not self.ids:
            return 0.0
        result_tmp = 0.0
        a = 0.0
        self.cr.execute(
            "SELECT CASE WHEN sum(debit) > sum(credit) " \
                    "THEN sum(debit) - sum(credit) " \
                    "ELSE 0 " \
                "END " \
            "FROM account_move_line AS l " \
            "WHERE l.account_id IN %s" \
                "AND " + self.query + " " \
            "GROUP BY l.partner_id",
            (tuple(self.account_ids),))
        a = self.cr.fetchone()[0]

        if self.cr.fetchone() != None:
            result_tmp = result_tmp + (a or 0.0)
        else:
            result_tmp = 0.0
        return result_tmp

    def _sum_scredit(self, data):
        if not self.ids:
            return 0.0
        result_tmp = 0.0
        a = 0.0
        self.cr.execute(
            "SELECT CASE WHEN sum(debit) < sum(credit) " \
                    "THEN sum(credit) - sum(debit) " \
                    "ELSE 0 " \
                "END " \
            "FROM account_move_line AS l " \
            "WHERE l.account_id IN %s" \
            "AND " + self.query + " " \
            "GROUP BY l.partner_id",
            (tuple(self.account_ids), ))
        a = self.cr.fetchone()[0] or 0.0
        if self.cr.fetchone() != None:
            result_tmp = result_tmp + (a or 0.0)
        else:
            result_tmp = 0.0
        return result_tmp

    def _solde_balance_debit(self, data):
        debit, credit = self._sum_debit(data), self._sum_credit(data)
        return debit > credit and debit - credit

    def _solde_balance_credit(self, data):
        debit, credit = self._sum_debit(data), self._sum_credit(data)
        return credit > debit and credit - debit

    def _get_partners(self, data):
        if self.result_selection == 'customer':
            return 'Receivable Accounts'
        elif self.result_selection == 'supplier':
            return 'Payable Accounts'
        elif self.result_selection == 'customer_supplier':
            return 'Receivable and Payable Accounts'
        return ''

report_sxw.report_sxw('report.account.partner.balance', 'res.partner', 'account/report/account_partner_balance.rml',parser=partner_balance, header="internal")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: