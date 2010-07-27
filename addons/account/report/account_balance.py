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

from report import report_sxw
from common_report_header import common_report_header

class account_balance(report_sxw.rml_parse, common_report_header):
    _name = 'report.account.account.balance'

    def set_context(self, objects, data, ids, report_type=None):
        new_ids = ids
        if (data['model'] == 'ir.ui.menu'):
            new_ids = 'chart_account_id' in data['form'] and [data['form']['chart_account_id']] or []
            objects = self.pool.get('account.account').browse(self.cr, self.uid, new_ids)
        self.query_get_clause = data['form']['query_line'] or ''
        return super(account_balance, self).set_context(objects, data, new_ids, report_type=report_type)

    def __init__(self, cr, uid, name, context=None):
        super(account_balance, self).__init__(cr, uid, name, context=context)
        self.sum_debit = 0.00
        self.sum_credit = 0.00
        self.date_lst = []
        self.date_lst_string = ''
        self.localcontext.update({
            'time': time,
            'lines': self.lines,
            'sum_debit': self._sum_debit,
            'sum_credit': self._sum_credit,
            'get_fiscalyear':self._get_fiscalyear,
            'get_filter': self._get_filter,
            'get_start_period': self.get_start_period,
            'get_end_period': self.get_end_period ,
            'get_account': self._get_account,
            'get_journal': self._get_journal,
            'get_start_date':self._get_start_date,
            'get_end_date':self._get_end_date,
        })
        self.context = context

    def _add_header(self, node, header=1):
        if header == 0:
            self.rml_header = ""
        return True

    def lines(self, form, ids=[], done=None, level=1):
        obj_account = self.pool.get('account.account')
        if not ids:
            ids = self.ids
        if not ids:
            return []
        if not done:
            done={}

        res = {}
        result_acc = []
        ctx = self.context.copy()

        ctx['fiscalyear'] = form['fiscalyear_id']
        if form['filter'] == 'filter_period':
            ctx['periods'] = form['periods']
        elif form['filter'] == 'filter_date':
            ctx['date_from'] = form['date_from']
            ctx['date_to'] =  form['date_to']
#        accounts = obj_account.browse(self.cr, self.uid, ids, ctx)
#        def cmp_code(x, y):
#            return cmp(x.code, y.code)
#        accounts.sort(cmp_code)

        child_ids = obj_account._get_children_and_consol(self.cr, self.uid, ids, ctx)
        if child_ids:
            ids = child_ids
        accounts = obj_account.read(self.cr, self.uid, ids, ['type','code','name','debit','credit','balance','parent_id'], ctx)
        for account in accounts:
            if account['id'] in done:
                continue
            done[account['id']] = 1
            res = {
                    'id' : account['id'],
                    'type' : account['type'],
                    'code': account['code'],
                    'name': account['name'],
                    'level': level,
                    'debit': account['debit'],
                    'credit': account['credit'],
                    'balance': account['balance'],
                   # 'leef': not bool(account['child_id']),
                    'parent_id':account['parent_id'],
                    'bal_type':'',
                }
            self.sum_debit += account['debit']
            self.sum_credit += account['credit']
#            if account.child_id:
#                def _check_rec(account):
#                    if not account.child_id:
#                        return bool(account.credit or account.debit)
#                    for c in account.child_id:
#                        if not _check_rec(c) or _check_rec(c):
#                            return True
#                    return False
#                if not _check_rec(account) :
#                    continue
            if account['parent_id']:
#                acc = obj_account.read(self.cr, self.uid, [ account['parent_id'][0] ] ,['name'], ctx)
                for r in result_acc:
                    if r['id'] == account['parent_id'][0]:
                        res['level'] = r['level'] + 1
                        break
            if form['display_account'] == 'bal_movement':
                if res['credit'] > 0 or res['debit'] > 0 or res['balance'] > 0 :
                    result_acc.append(res)
            elif form['display_account'] == 'bal_solde':
                if  res['balance'] != 0:
                    result_acc.append(res)
            else:
                result_acc.append(res)
#            if account.child_id:
#                acc_id = [acc.id for acc in account.child_id]
#                lst_string = ''
#                lst_string = '\'' + '\',\''.join(map(str,acc_id)) + '\''
#                self.cr.execute("select code,id from account_account where id IN (%s)"%(lst_string))
#                a_id = self.cr.fetchall()
#                a_id.sort()
#                ids2 = [x[1] for x in a_id]
#
#                result_acc += self.lines(form, ids2, done, level+1)
        return result_acc

report_sxw.report_sxw('report.account.account.balance', 'account.account', 'addons/account/report/account_balance.rml', parser=account_balance, header="internal")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: