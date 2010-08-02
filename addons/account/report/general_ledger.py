 # -*- coding: utf-8 -*-
 ##############################################################################
#
# Copyright (c) 2005-2006 CamptoCamp
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

import time
from report import report_sxw
import xml
import rml_parse
import pooler

class general_ledger(rml_parse.rml_parse):
    _name = 'report.account.general.ledger'

    def set_context(self, objects, data, ids, report_type = None):
        ##
        self.borne_date = self.get_min_date(data['form'])
        ##
        new_ids = []
        if (data['model'] == 'account.account'):
            new_ids = 'active_ids' in data['form']['context'] and data['form']['context']['active_ids'] or []
            #new_ids = ids
        else:
            new_ids.append(data['form']['Account_list'])

            objects = self.pool.get('account.account').browse(self.cr, self.uid, new_ids)

        super(general_ledger, self).set_context(objects, data, new_ids, report_type)

    def __init__(self, cr, uid, name, context):
        super(general_ledger, self).__init__(cr, uid, name, context=context)
        self.date_borne = {}
        self.query = ""
        self.child_ids = ""
        self.tot_currency = 0.0
        self.period_sql = ""
        self.sold_accounts = {}
        self.localcontext.update( {
            'time': time,
            'lines': self.lines,
            'sum_debit_account': self._sum_debit_account,
            'sum_credit_account': self._sum_credit_account,
            'sum_solde_account': self._sum_solde_account,
            'sum_debit': self._sum_debit,
            'sum_credit': self._sum_credit,
            'sum_solde': self._sum_solde,
            'get_children_accounts': self.get_children_accounts,
            'sum_currency_amount_account': self._sum_currency_amount_account
        })
        self.context = context

    def get_min_date(self, form):

        ## Get max born from account_fiscal year
        #
        sql = """ select min(fy.date_start) as start_date,max(fy.date_stop) as stop_date from account_fiscalyear
              As fy where fy.state <> 'close'
            """
        self.cr.execute(sql)
        res = self.cr.dictfetchall()
        borne_min = res[0]['start_date']
        borne_max = res[0]['stop_date']
        if form['state'] == 'byperiod':
            ## This function will return the most aged date
            periods = form['periods']
            #periods = form['periods'][0][2]
            if not periods:
                sql = """
                    Select min(p.date_start) as start_date,max(p.date_stop) as stop_date from account_period as p where p.fiscalyear_id = %s
                    """
                sqlargs = (form['fiscalyear'],)
            else:
                sql = """
                    Select min(p.date_start) as start_date,max(p.date_stop) as stop_date from account_period as p where p.id in %s
                    """
            sqlargs = (tuple(periods),)
            self.cr.execute(sql, sqlargs)
            res = self.cr.dictfetchall()
            borne_min = res[0]['start_date']
            borne_max = res[0]['stop_date']
        elif form['state'] == 'bydate':
            borne_min = form['date_from']
            borne_max = form['date_to']
        elif form['state'] == 'all':
            periods = form['periods']
            #periods = form['periods'][0][2]
            if not periods:
                sql =  """
                    SELECT MIN(p.date_start) AS start_date,
                           MAX(p.date_stop) AS stop_date
                    FROM account_period AS p
                    WHERE p.fiscalyear_id = %s
                        """
                sqlargs = (form['fiscalyear'],)
            else:
                sql = """
                    SELECT MIN(p.date_start) AS start_date,
                           MAX(p.date_stop) AS stop_date
                    FROM account_period AS p
                    WHERE p.id IN %s
                    """
            sqlargs = (tuple(periods),)
            self.cr.execute(sql, sqlargs)
            res = self.cr.dictfetchall()
            period_min = res[0]['start_date']
            period_max = res[0]['stop_date']
            date_min = form['date_from']
            date_max = form['date_to']
            if period_min<date_min:
                borne_min = period_min
            else :
                borne_min = date_min
            if date_max<period_max:
                borne_max = period_max
            else :
                borne_max = date_max
        elif form['state'] == 'none':
            sql = """
                    SELECT min(date) as start_date,max(date) as stop_date FROM account_move_line """
            self.cr.execute(sql)
            res = self.cr.dictfetchall()
            borne_min = res[0]['start_date']
            borne_max = res[0]['stop_date']
        self.date_borne = {
            'min_date': borne_min,
            'max_date': borne_max,
            }
        return self.date_borne

    def get_children_accounts(self, account, form):

        self.child_ids = self.pool.get('account.account').search(self.cr, self.uid,
            [('parent_id', 'child_of', self.ids)])
#
        res = []
        ctx = self.context.copy()
        ## We will make the test for period or date
        ## We will now make the test
        #
        ctx['state'] = form['context'].get('state', 'all')
        if form.has_key('fiscalyear'):
            ctx['fiscalyear'] = form['fiscalyear']
            ctx['periods'] = form['periods']
            #ctx['periods'] = form['periods'][0][2]

        else:
            ctx['date_from'] = form['date_from']
            ctx['date_to'] = form['date_to']
        ##
        #
        self.query = self.pool.get('account.move.line')._query_get(self.cr, self.uid, context=ctx)
        if account and account.child_consol_ids: # add ids of consolidated childs also of selected account
            ctx['consolidate_childs'] = True
            ctx['account_id'] = account.id
        ids_acc = self.pool.get('account.account').search(self.cr, self.uid, [('parent_id', 'child_of', [account.id])], context=ctx)
        for child_id in ids_acc:
            child_account = self.pool.get('account.account').browse(self.cr, self.uid, child_id)
            sold_account = self._sum_solde_account(child_account, form)
            self.sold_accounts[child_account.id] = sold_account
            if form['display_account'] == 'bal_mouvement':
                if child_account.type != 'view' \
                and len(self.pool.get('account.move.line').search(self.cr, self.uid,
                    [('account_id','=',child_account.id)],
                    context=ctx)) <> 0 :
                    res.append(child_account)
            elif form['display_account'] == 'bal_solde':
                if child_account.type != 'view' \
                and len(self.pool.get('account.move.line').search(self.cr, self.uid,
                    [('account_id','=',child_account.id)],
                    context=ctx)) <> 0 :
                    if ( sold_account <> 0.0):
                        res.append(child_account)
            else:
                if child_account.type != 'view' \
                and len(self.pool.get('account.move.line').search(self.cr, self.uid,
                    [('account_id','>=',child_account.id)],
                    context=ctx)) <> 0 :
                    res.append(child_account)
        ##
        if not len(res):

            return [account]
        else:
            ## We will now compute solde initiaux
            for move in res:
                SOLDEINIT = "SELECT SUM(l.debit) AS sum_debit,"\
                            "       SUM(l.credit) AS sum_credit "\
                            "FROM account_move_line l "\
                            "WHERE l.account_id = %s "\
                            "AND l.date < %s AND l.date > %s"
                self.cr.execute(SOLDEINIT, (move.id, self.borne_date['max_date'], self.borne_date['min_date']))
                resultat = self.cr.dictfetchall()
                if resultat[0] :
                    if resultat[0]['sum_debit'] == None:
                        sum_debit = 0
                    else:
                        sum_debit = resultat[0]['sum_debit']
                    if resultat[0]['sum_credit'] == None:
                        sum_credit = 0
                    else:
                        sum_credit = resultat[0]['sum_credit']

                    move.init_credit = sum_credit
                    move.init_debit = sum_debit

                else:
                    move.init_credit = 0
                    move.init_debit = 0


        return res

    def lines(self, account, form):
        """ Return all the account_move_line of account with their account code counterparts """

        # First compute all counterpart strings for every move_id where this account appear
        sql = """
            SELECT m1.move_id,
            array_to_string(ARRAY(SELECT DISTINCT a.code FROM account_move_line m2 LEFT JOIN account_account a ON (m2.account_id=a.id) WHERE m2.move_id = m1.move_id AND m2.account_id<>%%s), ', ') AS counterpart
            FROM (SELECT move_id FROM account_move_line l WHERE %s AND l.account_id = %%s AND l.date<=%%s AND l.date>=%%s  GROUP BY move_id) m1
        """ % self.query
        self.cr.execute(sql, (account.id, account.id, self.date_borne['max_date'], self.date_borne['min_date']))
        counterpart_res = self.cr.dictfetchall()
        counterpart_accounts = {}
        for i in counterpart_res:
            counterpart_accounts[i['move_id']]=i['counterpart']
        del counterpart_res

        # Then select all account_move_line of this account
        if form['sortbydate'] == 'sort_date':
            sql_sort='l.date'
        else:
            sql_sort='j.code'
        sql = """
            SELECT l.id, l.date, j.code, l.amount_currency,l.ref, l.name, COALESCE(l.debit,0) AS debit, COALESCE(l.credit,0) AS credit, l.period_id, l.partner_id,
            m.name AS move_name, m.id AS move_id,
            c.code AS currency_code,
            i.id AS invoice_id, i.type AS invoice_type, i.number AS invoice_number,
            p.name AS partner_name
            FROM account_move_line l
            LEFT JOIN account_move m on (l.move_id=m.id)
            LEFT JOIN res_currency c on (l.currency_id=c.id)
            LEFT JOIN res_partner p on (l.partner_id=p.id)
            LEFT JOIN account_invoice i on (m.id =i.move_id)
            JOIN account_journal j on (l.journal_id=j.id)
            WHERE %s AND l.account_id = %%s AND l.date<=%%s AND l.date>=%%s ORDER by %s
        """ % (self.query, sql_sort)
        self.cr.execute(sql, (account.id, self.date_borne['max_date'], self.date_borne['min_date']))
        res = self.cr.dictfetchall()
        account_sum = 0.0
        account_move_line_obj = pooler.get_pool(self.cr.dbname).get('account.move.line')
        inv_types = { 'out_invoice': 'CI', 'in_invoice': 'SI', 'out_refund': 'OR', 'in_refund': 'SR', }

        for l in res:
            l['move']=l['move_name']
            if l['invoice_id']:
                l['ref'] = '%s: %s'%(inv_types[l['invoice_type']], l['invoice_number'])
            l['partner'] = l['partner_name'] or ''
            account_sum = l['debit'] - l ['credit']
            #c = time.strptime(l['date'],"%Y-%m-%d")
            #l['date'] = time.strftime("%d-%m-%Y",c)
            l['progress'] = account_sum
            l['line_corresp'] = counterpart_accounts[l['move_id']]
            # Modification du amount Currency
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
        ## Add solde init to the result
        #
        sum_debit = self.cr.fetchone()[0] or 0.0
        if form.get('soldeinit', False):
            sum_debit += account.init_debit
        #
        ##
        return sum_debit

    def _sum_credit_account(self, account, form):

        self.cr.execute("SELECT sum(credit) "\
                "FROM account_move_line l "\
                "WHERE l.account_id = %s AND %s "%(account.id, self.query))
        ## Add solde init to the result
        #
        sum_credit = self.cr.fetchone()[0] or 0.0
        if form.get('soldeinit', False):
            sum_credit += account.init_credit
        #
        ##

        return sum_credit

    def _sum_solde_account(self, account, form):
        self.cr.execute("SELECT (sum(debit) - sum(credit)) as tot_solde "\
                "FROM account_move_line l "\
                "WHERE l.account_id = %s AND %s"%(account.id, self.query))
        sum_solde = self.cr.fetchone()[0] or 0.0
        if form.get('soldeinit', False):
            sum_solde += account.init_debit - account.init_credit

        return sum_solde

    def _sum_debit(self, form):
        if not self.ids:
            return 0.0
        self.cr.execute("SELECT sum(debit) "\
                "FROM account_move_line l "\
                "WHERE l.account_id IN %s AND "+self.query,
                        (tuple(self.child_ids),))
        sum_debit = self.cr.fetchone()[0] or 0.0
        return sum_debit

    def _sum_credit(self, form):
        if not self.ids:
            return 0.0
        self.cr.execute("SELECT sum(credit) "\
                "FROM account_move_line l "\
                "WHERE l.account_id IN %s AND "+self.query,
                        (tuple(self.child_ids),))
        ## Add solde init to the result
        #
        sum_credit = self.cr.fetchone()[0] or 0.0
        return sum_credit

    def _sum_solde(self, form):
        if not self.ids:
            return 0.0
        self.cr.execute("SELECT (sum(debit) - sum(credit)) as tot_solde "\
                "FROM account_move_line l "\
                "WHERE l.account_id IN %s AND "+self.query,
                        (tuple(self.child_ids),))
        sum_solde = self.cr.fetchone()[0] or 0.0
        return sum_solde

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

report_sxw.report_sxw('report.account.general.ledger', 'account.account', 'addons/account/report/general_ledger.rml', parser=general_ledger, header=False)
report_sxw.report_sxw('report.account.general.ledger_landscape', 'account.account', 'addons/account/report/general_ledger_landscape.rml', parser=general_ledger, header=False)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
