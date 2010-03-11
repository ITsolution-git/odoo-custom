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
from osv import fields, osv
from tools.translate import _
import netsvc
import pooler
import time
import tools
import wizard

class auction_pay_sel(osv.osv_memory):
   
    _name = "auction.pay.sel"
    _description = "Pay Invoice"
    _columns= {
               'amount': fields.float('Amount paid', digits= (16, int(tools.config['price_accuracy'])), required=True), 
               'dest_account_id':fields.many2one('account.account', 'Payment to Account', required=True, domain= [('type', '=', 'cash')]), 
               'journal_id':fields.many2one('account.journal', 'Journal', required=True), 
               'period_id':fields.many2one('account.period', 'Period', required=True), 
               }
    
    def _pay_and_reconcile(self, cr, uid, ids, context):
        lot = self.pool.get('auction.lots').browse(cr, uid, context['active_id'], context)
        for datas in self.read(cr, uid, ids):
            account_id = datas.get('writeoff_acc_id', False)
            period_id = datas.get('period_id', False)
            journal_id = datas.get('journal_id', False)
            if lot.sel_inv_id:
                p = self.pool.get('account.invoice').pay_and_reconcile(['lot.sel_inv_id.id'], datas['amount'], datas['dest_account_id'], journal_id, account_id, period_id, journal_id, context)
        #   lots.sel_inv_id.pay_and_reconcile(cr,uid,data[id], form['amount'], form['dest_account_id'], journal_id, account_id, period_id, journal_id, context)
            return {}
    
auction_pay_sel()
