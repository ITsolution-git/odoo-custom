##############################################################################
#
# Copyright (c) 2005-2006 TINY SPRL. (http://tiny.be) All Rights Reserved.
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

import pooler
import time
import re

import datetime
from report import report_sxw

class third_party_ledger(report_sxw.rml_parse):
	def __init__(self, cr, uid, name, context):
		self.date_lst = []
		self.date_lst_string = ''
		super(third_party_ledger, self).__init__(cr, uid, name, context)
		self.localcontext.update( {
			'time': time,
			'lines': self.lines,
			'sum_debit_partner': self._sum_debit_partner,
			'sum_credit_partner': self._sum_credit_partner,
			'sum_debit': self._sum_debit,
			'sum_credit': self._sum_credit,
			'get_company': self._get_company,
			'get_currency': self._get_currency,
			'comma_me' : self.comma_me,
		})
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
	def transform_period_into_date_array(self,data):
		## Get All Period Date
		if not data['form']['periods'][0][2] :
			periods_id =  self.pool.get('account.period').search(self.cr, self.uid, [('fiscalyear_id','=',data['form']['fiscalyear'])])
		else:
			periods_id = data['form']['periods'][0][2]
		date_array = [] 
		for period_id in periods_id:
			period_obj = self.pool.get('account.period').browse(self.cr, self.uid, period_id)
			date_array = date_array + self.date_range(period_obj.date_start,period_obj.date_stop)
		self.date_lst = date_array
		self.date_lst.sort()
			
	def transform_date_into_date_array(self,data):
		return_array = self.date_range(data['form']['date1'],data['form']['date2'])
		self.date_lst = return_array
		self.date_lst.sort()

	def comma_me(self,amount):
		if  type(amount) is float :
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
	def special_map(self):
		string_map = ''
		for date_string in self.date_lst:
			string_map = date_string + ','
		return string_map
	
	def preprocess(self, objects, data, ids):
		PARTNER_REQUEST = ''
		if (data['model'] == 'res.partner'):
			print"data['model']",data['model']
			## Si on imprime depuis les partenaires
			if ids:
				PARTNER_REQUEST =  "AND line.partner_id IN (" + ','.join(map(str, ids)) + ")"
		# Transformation des date
		#
		#
		if data['form'].has_key('fiscalyear'): 
			self.transform_period_into_date_array(data)
		else:
			self.transform_date_into_date_array(data)
		##
		self.date_lst_string = '\'' + '\',\''.join(map(str,self.date_lst)) + '\''
		#
		#new_ids = [id for (id,) in self.cr.fetchall()]
		if data['form']['result_selection'] == 'supplier':
			ACCOUNT_TYPE = "AND a.type='payable' "
		elif data['form']['result_selection'] == 'customer':
			ACCOUNT_TYPE = "AND a.type='receivable' "
		elif data['form']['result_selection'] == 'all':
			ACCOUNT_TYPE = "AND (a.type='receivable' OR a.type='payable') "

		self.cr.execute(
			"SELECT a.id " \
			"FROM account_account a " \
			"LEFT JOIN account_account_type t " \
				"ON (a.type=t.code) " \
			"WHERE t.partner_account=TRUE " \
				"AND a.company_id = %d " \
				" " + ACCOUNT_TYPE + " " \
				"AND a.active", (data['form']['company_id'],))
		self.account_ids = ','.join([str(a) for (a,) in self.cr.fetchall()])
		account_move_line_obj = pooler.get_pool(self.cr.dbname).get('account.move.line')
		partner_to_use = []
		if data['form']['soldeinit'] :
			self.cr.execute(
				"SELECT DISTINCT line.partner_id " \
				"FROM account_move_line AS line, account_account AS account " \
				"WHERE line.partner_id IS NOT NULL " \
					"AND line.account_id = account.id " \
					"AND line.date < %s " \
					"AND line.reconcile_id IS NULL " \
#					"AND line.account_id IN (" + self.account_ids + ") " \
					" " + PARTNER_REQUEST + " " \
					"AND account.company_id = %d " \
					"AND account.active " ,
				(self.date_lst[len(self.date_lst)-1],data['form']['company_id']))
		else:
			self.cr.execute(
				"SELECT DISTINCT line.partner_id " \
				"FROM account_move_line AS line, account_account AS account " \
				"WHERE line.partner_id IS NOT NULL " \
					"AND line.account_id = account.id " \
					"AND line.date IN (" + self.date_lst_string + ") " \
#					"AND line.account_id IN (" + self.account_ids + ") " \
					" " + PARTNER_REQUEST + " " \
					"AND account.company_id = %d " \
					"AND account.active " ,
				(data['form']['company_id']))
		res = self.cr.dictfetchall()
		for res_line in res:
		    partner_to_use.append(res_line['partner_id'])
		res = self.cr.dictfetchall()
		
		for res_line in res:
			    partner_to_use.append(res_line['partner_id'])
		new_ids = partner_to_use
		self.partner_ids = ','.join(map(str, new_ids))
		objects = self.pool.get('res.partner').browse(self.cr, self.uid, new_ids)
		super(third_party_ledger, self).preprocess(objects, data, new_ids)

	def lines(self, partner,data):
		account_move_line_obj = pooler.get_pool(self.cr.dbname).get('account.move.line')
		full_account = []
		if data['form']['reconcil'] :
			RECONCILE_TAG = " "
		else:
			RECONCILE_TAG = "AND l.reconcile_id IS NULL"
		if data['form']['soldeinit'] :
			self.cr.execute(
					"SELECT l.id,l.date,j.code, l.ref, l.name, l.debit, l.credit " \
					"FROM account_move_line l " \
					"LEFT JOIN account_journal j " \
						"ON (l.journal_id = j.id) " \
					"WHERE l.partner_id = %d " \
						"AND l.account_id IN (" + self.account_ids + ") " \
						"AND l.date < %s " \
						"AND l.reconcile_id IS NULL "
					"ORDER BY l.id",
					(partner.id, self.date_lst[0]))
			res = self.cr.dictfetchall()
			sum = 0.0
			for r in res:
				sum = r['debit'] - r['credit']
				r['progress'] = sum
				full_account.append(r)
			
		self.cr.execute(
				"SELECT l.id,l.date,j.code, l.ref, l.name, l.debit, l.credit " \
				"FROM account_move_line l " \
				"LEFT JOIN account_journal j " \
					"ON (l.journal_id = j.id) " \
				"WHERE l.partner_id = %d " \
					"AND l.account_id IN (" + self.account_ids + ") " \
					"AND l.date IN (" + self.date_lst_string + ") " \
					" " + RECONCILE_TAG + " "\
					"ORDER BY l.id",
					(partner.id,))
		res = self.cr.dictfetchall()
		sum = 0.0
		for r in res:
			sum = r['debit'] - r['credit']
			r['progress'] = sum
			full_account.append(r)
		
		return full_account

	def _sum_debit_partner(self, partner,data):
		account_move_line_obj = pooler.get_pool(self.cr.dbname).get('account.move.line')
		result_tmp = 0.0
		if data['form']['reconcil'] :
			RECONCILE_TAG = " "
		else:
			RECONCILE_TAG = "AND reconcile_id IS NULL"
		if data['form']['soldeinit'] :
			self.cr.execute(
				"SELECT sum(debit) " \
				"FROM account_move_line " \
				"WHERE partner_id = %d " \
					"AND account_id IN (" + self.account_ids + ") " \
					"AND reconcile_id IS NULL " \
					"AND date < %s " ,
				(partner.id, self.date_lst[0],))
			contemp = self.cr.fetchone()
			if contemp != None:
				result_tmp = contemp[0] or 0.0
			else:
				result_tmp = result_tmp + 0.0
			

		self.cr.execute(
				"SELECT sum(debit) " \
				"FROM account_move_line " \
				"WHERE partner_id = %d " \
					"AND account_id IN (" + self.account_ids + ") " \
					" " + RECONCILE_TAG + " " \
					"AND date IN (" + self.date_lst_string + ") " ,
				(partner.id,))
		
		contemp = self.cr.fetchone()	
		if contemp != None:
			result_tmp = contemp[0] or 0.0
		else:
			result_tmp = result_tmp + 0.0
		return result_tmp
		
	def _sum_credit_partner(self, partner,data):
		account_move_line_obj = pooler.get_pool(self.cr.dbname).get('account.move.line')
		result_tmp = 0.0
		if data['form']['reconcil'] :
			RECONCILE_TAG = " "
		else:
			RECONCILE_TAG = "AND reconcile_id IS NULL"
		if data['form']['soldeinit'] :
			self.cr.execute(
					"SELECT sum(credit) " \
					"FROM account_move_line " \
					"WHERE partner_id=%d " \
						"AND account_id IN (" + self.account_ids + ") " \
						"AND reconcile_id IS NULL " \
						"AND date < %s " ,
					(partner.id,self.date_lst[0],))
			contemp = self.cr.fetchone()
			if contemp != None:
				result_tmp = contemp[0] or 0.0
			else:
				result_tmp = result_tmp + 0.0
				
		self.cr.execute(
				"SELECT sum(credit) " \
				"FROM account_move_line " \
				"WHERE partner_id=%d " \
					"AND account_id IN (" + self.account_ids + ") " \
					" " + RECONCILE_TAG + " " \
					"AND date IN (" + self.date_lst_string + ") " ,
				(partner.id,))

		contemp = self.cr.fetchone()	
		if contemp != None:
			result_tmp = contemp[0] or 0.0
		else:
			result_tmp = result_tmp + 0.0
		return result_tmp
		
	def _sum_debit(self,data):
		if not self.ids:
			return 0.0
		account_move_line_obj = pooler.get_pool(self.cr.dbname).get('account.move.line')
		result_tmp = 0.0
		if data['form']['reconcil'] :
			RECONCILE_TAG = " "
		else:
			RECONCILE_TAG = "AND reconcile_id IS NULL"
		if data['form']['soldeinit'] :
			self.cr.execute(
					"SELECT sum(debit) " \
					"FROM account_move_line " \
					"WHERE partner_id IN (" + self.partner_ids + ") " \
						"AND account_id IN (" + self.account_ids + ") " \
						"AND reconcile_id IS NULL " \
						"AND date < %s " ,
					(self.date_lst[0],))
			contemp = self.cr.fetchone()
			if contemp != None:
				result_tmp = contemp[0] or 0.0
			else:
				result_tmp = result_tmp + 0.0

		self.cr.execute(
				"SELECT sum(debit) " \
				"FROM account_move_line " \
				"WHERE partner_id IN (" + self.partner_ids + ") " \
					"AND account_id IN (" + self.account_ids + ") " \
					" " + RECONCILE_TAG + " " \
					"AND date IN (" + self.date_lst_string + ") " 
				)

		contemp = self.cr.fetchone()	
		if contemp != None:
			result_tmp = contemp[0] or 0.0
		else:
			result_tmp = result_tmp + 0.0
		
		return result_tmp
		
		
	def _sum_credit(self,data):
		if not self.ids:
			return 0.0
		account_move_line_obj = pooler.get_pool(self.cr.dbname).get('account.move.line')
		result_tmp = 0.0
		if data['form']['reconcil'] :
			RECONCILE_TAG = " "
		else:
			RECONCILE_TAG = "AND reconcile_id IS NULL"
		if data['form']['soldeinit'] :
			self.cr.execute(
					"SELECT sum(credit) " \
					"FROM account_move_line " \
					"WHERE partner_id IN (" + self.partner_ids + ") " \
						"AND account_id IN (" + self.account_ids + ") " \
						"AND reconcile_id IS NULL " \
						"AND date < %s " ,
					(self.date_lst[0],))
			contemp = self.cr.fetchone()
			if contemp != None:
				result_tmp = contemp[0] or 0.0
			else:
				result_tmp = result_tmp + 0.0
		self.cr.execute(
				"SELECT sum(credit) " \
				"FROM account_move_line " \
				"WHERE partner_id IN (" + self.partner_ids + ") " \
					"AND account_id IN (" + self.account_ids + ") " \
					" " + RECONCILE_TAG + " " \
					"AND date IN (" + self.date_lst_string + ") " 
				)
		contemp = self.cr.fetchone()	
		if contemp != None:
			result_tmp = contemp[0] or 0.0
		else:
			result_tmp = result_tmp + 0.0
		
		return result_tmp

	def _get_company(self, form):
		return pooler.get_pool(self.cr.dbname).get('res.company').browse(self.cr, self.uid, form['company_id']).name

	def _get_currency(self, form):
		return pooler.get_pool(self.cr.dbname).get('res.company').browse(self.cr, self.uid, form['company_id']).currency_id.name
	
report_sxw.report_sxw('report.account.third_party_ledger', 'res.partner',
		'addons/account/third_party_ledger.rml',parser=third_party_ledger,
		header=2)

