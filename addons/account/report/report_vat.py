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

from openerp.osv import osv
from openerp.addons.web import http
from openerp.addons.web.http import request
from common_report_header import common_report_header
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO
import xlwt


class tax_report(osv.AbstractModel, common_report_header):
    _name = 'report.account.report_vat'

    def render_html(self, cr, uid, ids, data=None, context=None):
        report_obj = request.registry['report']
        self.cr, self.uid, self.context = cr, uid, context

        res = {}
        self.period_ids = []
        period_obj = self.pool.get('account.period')
        self.display_detail = data['form']['display_detail']
        res['periods'] = ''
        res['fiscalyear'] = data['form'].get('fiscalyear_id', False)

        if data['form'].get('period_from', False) and data['form'].get('period_to', False):
            self.period_ids = period_obj.build_ctx_periods(self.cr, self.uid, data['form']['period_from'], data['form']['period_to'])

        docargs = {
            'fiscalyear': self._get_fiscalyear(data),
            'account': self._get_account(data),
            'based_on': self._get_basedon(data),
            'period_from': self.get_start_period(data),
            'period_to': self.get_end_period(data),
            'taxlines': self._get_lines(self._get_basedon(data), company_id=data['form']['company_id'], cr=cr, uid=uid),
        }
        return report_obj.render(self.cr, self.uid, [], 'account.report_vat', docargs, context=context)

    def _get_basedon(self, form):
        return form['form']['based_on']

    def _get_lines(self, based_on, company_id=False, parent=False, level=0, context=None, cr=None, uid=None):
        period_list = self.period_ids
        res = self._get_codes(based_on, company_id, parent, level, period_list, cr=cr, uid=uid, context=context)
        if period_list:
            res = self._add_codes(based_on, res, period_list, context=context)
        else:
            cr.execute ("select id from account_fiscalyear")
            fy = cr.fetchall()
            cr.execute ("select id from account_period where fiscalyear_id = %s",(fy[0][0],))
            periods = cr.fetchall()
            for p in periods:
                period_list.append(p[0])
            res = self._add_codes(based_on, res, period_list, context=context)

        i = 0
        top_result = []
        while i < len(res):

            res_dict = { 'code': res[i][1].code,
                'name': res[i][1].name,
                'debit': 0,
                'credit': 0,
                'tax_amount': res[i][1].sum_period,
                'type': 1,
                'level': res[i][0],
                'pos': 0
            }

            top_result.append(res_dict)
            res_general = self._get_general(res[i][1].id, period_list, company_id, based_on, cr=cr, uid=uid, context=context)
            ind_general = 0
            while ind_general < len(res_general):
                res_general[ind_general]['type'] = 2
                res_general[ind_general]['pos'] = 0
                res_general[ind_general]['level'] = res_dict['level']
                top_result.append(res_general[ind_general])
                ind_general+=1
            i+=1
        return top_result

    def _get_general(self, tax_code_id, period_list, company_id, based_on, cr=None, uid=None, context=None):
        if not self.display_detail:
            return []
        res = []
        obj_account = self.pool.get('account.account')
        periods_ids = tuple(period_list)
        if based_on == 'payments':
            cr.execute('SELECT SUM(line.tax_amount) AS tax_amount, \
                        SUM(line.debit) AS debit, \
                        SUM(line.credit) AS credit, \
                        COUNT(*) AS count, \
                        account.id AS account_id, \
                        account.name AS name,  \
                        account.code AS code \
                    FROM account_move_line AS line, \
                        account_account AS account, \
                        account_move AS move \
                        LEFT JOIN account_invoice invoice ON \
                            (invoice.move_id = move.id) \
                    WHERE line.state<>%s \
                        AND line.tax_code_id = %s  \
                        AND line.account_id = account.id \
                        AND account.company_id = %s \
                        AND move.id = line.move_id \
                        AND line.period_id IN %s \
                        AND ((invoice.state = %s) \
                            OR (invoice.id IS NULL))  \
                    GROUP BY account.id,account.name,account.code', ('draft', tax_code_id,
                        company_id, periods_ids, 'paid',))

        else:
            cr.execute('SELECT SUM(line.tax_amount) AS tax_amount, \
                        SUM(line.debit) AS debit, \
                        SUM(line.credit) AS credit, \
                        COUNT(*) AS count, \
                        account.id AS account_id, \
                        account.name AS name,  \
                        account.code AS code \
                    FROM account_move_line AS line, \
                        account_account AS account \
                    WHERE line.state <> %s \
                        AND line.tax_code_id = %s  \
                        AND line.account_id = account.id \
                        AND account.company_id = %s \
                        AND line.period_id IN %s\
                        AND account.active \
                    GROUP BY account.id,account.name,account.code', ('draft', tax_code_id,
                        company_id, periods_ids,))
        res = cr.dictfetchall()

        i = 0
        while i<len(res):
            res[i]['account'] = obj_account.browse(cr, uid, res[i]['account_id'], context=context)
            i+=1
        return res

    def _get_codes(self, based_on, company_id, parent=False, level=0, period_list=None, cr=None, uid=None, context=None):
        obj_tc = self.pool.get('account.tax.code')
        ids = obj_tc.search(cr, uid, [('parent_id', '=', parent), ('company_id', '=', company_id)], order='sequence', context=context)
        res = []
        for code in obj_tc.browse(cr, uid, ids, {'based_on': based_on}):
            res.append(('.'*2*level, code))
            res += self._get_codes(based_on, company_id, code.id, level+1, cr=cr, uid=uid, context=context)
        return res

    def _add_codes(self, based_on, account_list=None, period_list=None, context=None):
        if account_list is None:
            account_list = []
        if period_list is None:
            period_list = []
        res = []
        obj_tc = self.pool.get('account.tax.code')
        for account in account_list:
            ids = obj_tc.search(self.cr, self.uid, [('id','=', account[1].id)], context=context)
            sum_tax_add = 0
            for period_ind in period_list:
                for code in obj_tc.browse(self.cr, self.uid, ids, {'period_id':period_ind,'based_on': based_on}):
                    sum_tax_add = sum_tax_add + code.sum_period

            code.sum_period = sum_tax_add

            res.append((account[0], code))
        return res

    def sort_result(self, accounts, context=None):
        result_accounts = []
        ind=0
        old_level=0
        while ind<len(accounts):
            #
            account_elem = accounts[ind]
            #

            #
            # we will now check if the level is lower than the previous level, in this case we will make a subtotal
            if (account_elem['level'] < old_level):
                bcl_current_level = old_level
                bcl_rup_ind = ind - 1

                while (bcl_current_level >= int(accounts[bcl_rup_ind]['level']) and bcl_rup_ind >= 0 ):
                    res_tot = {
                        'code': accounts[bcl_rup_ind]['code'],
                        'name': '',
                        'debit': 0,
                        'credit': 0,
                        'tax_amount': accounts[bcl_rup_ind]['tax_amount'],
                        'type': accounts[bcl_rup_ind]['type'],
                        'level': 0,
                        'pos': 0
                    }

                    if res_tot['type'] == 1:
                        # on change le type pour afficher le total
                        res_tot['type'] = 2
                        result_accounts.append(res_tot)
                    bcl_current_level =  accounts[bcl_rup_ind]['level']
                    bcl_rup_ind -= 1

            old_level = account_elem['level']
            result_accounts.append(account_elem)
            ind+=1

        return result_accounts


class tax_report_xls(http.Controller):

    @http.route(['/report/account.report_vat_xls'], type='http', auth='user', website=True, multilang=True)
    def report_account_tax_xls(self, **data):

        # Very ugly lines, only for the proof of concept of 'controller' report
        taxreport_obj = request.registry['report.account.report_vat']
        from openerp.addons.report.controllers.main import ReportController
        eval_params = ReportController()._eval_params

        cr, uid = request.cr, request.uid
        data = eval_params(data)
        data = {'form': data}

        taxreport_obj.render_html(cr, uid, [], data=data)
        lines = taxreport_obj._get_lines(taxreport_obj._get_basedon(data), company_id=data['form']['company_id'], cr=cr, uid=uid)

        if lines:
            xls = StringIO.StringIO()
            xls_workbook = xlwt.Workbook()
            vat_sheet = xls_workbook.add_sheet('report_vat')

            for x in range(0, len(lines)):
                for y in range(0, len(lines[0])):
                    vat_sheet.write(x, y, lines[x].values()[y])

            xls_workbook.save(xls)
            xls.seek(0)
            content = xls.read()

        response = request.make_response(content, headers=[
            ('Content-Type', 'application/vnd.ms-excel'),
            ('Content-Disposition', 'attachment; filename=report_vat.xls;')
        ])
        return response

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
