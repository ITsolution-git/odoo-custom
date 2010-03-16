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

class auction_pay_buy(osv.osv_memory):
    
    def _start(self, cr, uid, context):
        rec = self.pool.get('auction.lots').browse(cr, uid, context['active_ids'], context)
        amount1 = 0.0
        for r in rec:
            amount1+= r.buyer_price
            if r.is_ok:
                raise osv.except_osv('Error !', 'Some lots of the selection are already paid.')
        return amount1
    
    def _value_buyer_id(self, cr, uid, context={}):
        """
        For default buyer id value
        @return:auction lots buyer id in buyer id field.
        """
        lots= self.pool.get('auction.lots').browse(cr, uid, context['active_ids'])
        for lot in lots:
            buyer=lot and lot.ach_uid.id or False
        return buyer
    
    def pay_and_reconcile(self, cr, uid, ids, context):
        """
            Pay and Reconcile
            
            @param cr: the current row, from the database cursor.
            @param uid: the current user’s ID for security checks.
            @param ids: the ID or list of IDs
            @param context: A standard dictionary 
            @return: 
        """        
        lot_obj = self.pool.get('auction.lots')
        bank_statement_line_obj = self.pool.get('account.bank.statement.line')
        
        for datas in self.read(cr, uid, ids):
            if not abs(datas['total'] - (datas['amount'] + datas['amount2'] + datas['amount3'])) <0.01:
                rest = datas['total']-(datas['amount'] + datas['amount2'] + datas['amount3'])
                raise osv.except_osv('Payment aborted !', 'You should pay all the total: "%.2f" are missing to accomplish the payment.' %(round(rest, 2)))
    
            lots = lot_obj.browse(cr, uid, context['active_ids'], context)
            ref_bk_s = bank_statement_line_obj
    
            for lot in lots:
                if datas['buyer_id']:
                    lot_obj.write(cr, uid, [lot.id], {'ach_uid':datas['buyer_id']})
                if not lot.auction_id:
                    raise osv.except_osv('Error !', 'No auction date for "%s": Please set one.'%(lot.name))
                lot_obj.write(cr, uid, [lot.id], {'is_ok':True})
    
            for st, stamount in [('statement_id1', 'amount'), ('statement_id2', 'amount2'), ('statement_id3', 'amount3')]:
                if datas[st]:
                    new_id = ref_bk_s.create(cr, uid, {
                        'name':'Buyer:'+ str(lot.ach_login or '')+', auction:'+ lots[0].auction_id.name, 
                        'date': time.strftime('%Y-%m-%d'), 
                        'partner_id': datas['buyer_id'] or False, 
                        'type':'customer', 
                        'statement_id': datas[st], 
                        'account_id': lot.auction_id.acc_income.id, 
                        'amount': datas[stamount]
                        })
                    for lot in lots:
                        lot_obj.write(cr, uid, [lot.id], {'statement_id':[(4, new_id)]})
            return {}
   
    _name = "auction.pay.buy"
    _description = "Pay buy"
    _columns= {
               'amount': fields.float('Amount paid', digits= (16, int(tools.config['price_accuracy']))), 
               'buyer_id':fields.many2one('res.partner', 'Buyer'), 
               'statement_id1':fields.many2one('account.bank.statement', 'Statement', required=True), 
               'amount2': fields.float('Amount paid', digits= (16, int(tools.config['price_accuracy']))), 
               'statement_id2':fields.many2one('account.bank.statement', 'Statement'), 
               'amount3': fields.float('Amount paid', digits = (16, int(tools.config['price_accuracy']))), 
               'statement_id3':fields.many2one('account.bank.statement', 'Statement'), 
               'total': fields.float('Amount paid', digits = (16, int(tools.config['price_accuracy'])), readonly =True), 
               }
    _defaults={
               'amount' : _start,
               'total' : _start,
               'buyer_id' : _value_buyer_id
               }
    
auction_pay_buy()



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

