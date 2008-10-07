##############################################################################
#
# Copyright (c) 2004-2008 TINY SPRL. (http://tiny.be) All Rights Reserved.
#
# $Id$
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

import xml
import copy
from operator import itemgetter
import time
import datetime
from report import report_sxw

class account_balance(report_sxw.rml_parse):
    
        _name = 'report.account.account.balance'
        def __init__(self, cr, uid, name, context):
            super(account_balance, self).__init__(cr, uid, name, context)
            self.sum_debit = 0.00
            self.sum_credit = 0.00
            self.date_lst = []
            self.date_lst_string = ''
            self.localcontext.update({
                'time': time,
                'lines': self.lines,
                'moveline':self.moveline,
                'sum_debit': self._sum_debit,
                'sum_credit': self._sum_credit,
                'get_fiscalyear':self.get_fiscalyear,
                'get_periods':self.get_periods,
            })
            self.context = context
    
        def get_fiscalyear(self, form):
            res=[]
            if form.has_key('fiscalyear'): 
                fisc_id = form['fiscalyear']
                if not (fisc_id):
                    return ''
                self.cr.execute("select name from account_fiscalyear where id = %d" %(int(fisc_id)))
                res=self.cr.fetchone()
            return res and res[0] or ''
    
        def get_periods(self, form):
            result=''
            if form.has_key('periods'): 
                period_ids = ",".join([str(x) for x in form['periods'][0][2] if x])
                self.cr.execute("select name from account_period where id in (%s)" % (period_ids))
                res=self.cr.fetchall()
                for r in res:
                    if (r == res[res.__len__()-1]):
                        result+=r[0]+". "
                    else:
                        result+=r[0]+", "
            return str(result and result[:-1]) or ''
    
        def lines(self, form, ids={}, done=None, level=1):
            if not ids:
                ids = self.ids
            if not ids:
                return []
            if not done:
                done={}
            res={}
            result_acc=[]
            ctx = self.context.copy()
            if form.has_key('fiscalyear'): 
                self.transform_period_into_date_array(form)
                ctx['fiscalyear'] = form['fiscalyear']
                ctx['periods'] = form['periods'][0][2]
            else:
                self.transform_date_into_date_array(form)
                ctx['date_from'] = form['date_from']
                ctx['date_to'] = form['date_to']
                
            accounts = self.pool.get('account.account').browse(self.cr, self.uid, ids, ctx)
            def cmp_code(x, y):
                return cmp(x.code, y.code)
            accounts.sort(cmp_code)
            for account in accounts:
                if account.id in done:
                    continue
                done[account.id] = 1     
                res = {
                        'lid' :'',
                        'date':'',
                        'jname':'',
                        'ref':'',
                        'lname':'',
                        'debit1':'',
                        'credit1':'',
                        'balance1' :'',
                        'id' : account.id,
                        'code': account.code,
                        'name': account.name,
                        'level': level,
                        'debit': account.debit,
                        'credit': account.credit,
                        'balance': account.balance,
                        'leef': not bool(account.child_id),
                        'bal_type':'',
                    }
                self.sum_debit += account.debit
                self.sum_credit += account.credit
                if not (res['credit'] or res['debit']) and not account.child_id:
                    continue
                if account.child_id:
                    def _check_rec(account):
                        if not account.child_id:
                            return bool(account.credit or account.debit)
                        for c in account.child_id:
                            if _check_rec(c):
                                return True
                        return False
                    if not _check_rec(account):
                        continue
                if form['display_account'] == 'bal_mouvement':
                    if res['credit'] <> 0 or res['debit'] <> 0 or res['balance'] <> 0:
                        result_acc.append(res)
                elif form['display_account'] == 'bal_solde':        
                    if  res['balance'] <> 0:
                        result_acc.append(res)
                else:
                    result_acc.append(res)
                res1 = self.moveline(form, account.id,res['level'])
                if res1:
                    for r in res1:
                        result_acc.append(r)
                if account.code=='0':
                    result_acc.pop(-1)
                if account.child_id:
                    ids2 = [(x.code,x.id) for x in account.child_id]
                    ids2.sort()
                    result_acc += self.lines(form, [x[1] for x in ids2], done, level+1)
            return result_acc
        
        def moveline(self,form,ids,level):
            res={}
            self.date_lst_string = '\'' + '\',\''.join(map(str,self.date_lst)) + '\''
            self.cr.execute(
                    "SELECT l.id as lid,l.date,j.code as jname, l.ref, l.name as lname, l.debit as debit1, l.credit as credit1 " \
                    "FROM account_move_line l " \
                    "LEFT JOIN account_journal j " \
                        "ON (l.journal_id = j.id) " \
                    "WHERE l.account_id = '"+str(ids)+"' " \
                    "AND l.date IN (" + self.date_lst_string + ") " \
                        "ORDER BY l.id")
            res = self.cr.dictfetchall() 
            sum = 0.0
            for r in res:
                sum = r['debit1'] - r['credit1']
                r['balance1'] = sum
                r['id'] =''
                r['code']= ''
                r['name']=''
                r['level']=level
                r['debit']=''
                r['credit']=''
                r['balance']=''
                r['leef']=''
                if sum > 0.0:
                    r['bal_type']=" Dr."
                else:
                    r['bal_type']=" Cr."
            return res or ''
        
        def date_range(self,start,end):
            start = datetime.date.fromtimestamp(time.mktime(time.strptime(start,"%Y-%m-%d")))
            end = datetime.date.fromtimestamp(time.mktime(time.strptime(end,"%Y-%m-%d")))
            full_str_date = []
        #
            r = (end+datetime.timedelta(days=1)-start).days
        #
            date_array = [start+datetime.timedelta(days=i) for i in range(r)]
            for date in date_array:
                full_str_date.append(str(date))
            return full_str_date
            
        #
        def transform_period_into_date_array(self,form):
            ## Get All Period Date
            if not form['periods'][0][2] :
                periods_id =  self.pool.get('account.period').search(self.cr, self.uid, [('fiscalyear_id','=',form['fiscalyear'])])
            else:
                periods_id = form['periods'][0][2]
            date_array = [] 
            for period_id in periods_id:
                period_obj = self.pool.get('account.period').browse(self.cr, self.uid, period_id)
                date_array = date_array + self.date_range(period_obj.date_start,period_obj.date_stop)
                
            self.date_lst = date_array
            self.date_lst.sort()
                
        def transform_date_into_date_array(self,form):
            return_array = self.date_range(form['date_from'],form['date_to'])
            self.date_lst = return_array
            self.date_lst.sort()
            
        def _sum_credit(self):
            return self.sum_credit 
    
        def _sum_debit(self):
            return self.sum_debit 
report_sxw.report_sxw('report.account.account.balance', 'account.account', 'addons/account/report/account_balance.rml', parser=account_balance, header=False)

