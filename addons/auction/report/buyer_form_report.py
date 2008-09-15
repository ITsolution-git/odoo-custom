# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2005 TINY SPRL. (http://tiny.be) All Rights Reserved.
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


import pooler
import time
from report import report_sxw
from osv import osv

class buyer_form_report(report_sxw.rml_parse):
    count=0
    c=0
    def __init__(self, cr, uid, name, context):
        super(buyer_form_report, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'time': time,
            'sum_taxes': self.sum_taxes,
            'buyerinfo' : self.buyer_info,
            'grand_total' : self.grand_buyer_total,
    })

    def sum_taxes(self, lot):
        amount=0.0
        taxes=[]
        if lot.author_right:
            taxes.append(lot.author_right)
        if lot.auction_id:
            taxes += lot.auction_id.buyer_costs
        tax=self.pool.get('account.tax').compute(self.cr,self.uid,taxes,lot.obj_price,1)
        for t in tax:
            amount+=t['amount']
        return amount
    def buyer_info(self):
        objects = [object for object in self.localcontext.get('objects')]
        ret_dict = {}
        ret_list = []
        for object in objects:
            partner = ret_dict.get(object.ach_uid.id,False)
            if not partner:
                ret_dict[object.ach_uid.id] = {'partner' : object.ach_uid or False,'lots':[object]}
            else:
                lots = partner.get('lots')
                lots.append(object)
#       buyer_ids=self.pool.get(auction.lots).read(cr,uid,lot)


        return ret_dict.values()

    def grand_buyer_total(self,o):
        grand_total = 0
        for oo in o:
            grand_total =grand_total + oo['obj_price'] +self.sum_taxes(oo)
        return grand_total

report_sxw.report_sxw('report.buyer_form_report', 'auction.lots', 'addons/auction/report/buyer_form_report.rml', parser=buyer_form_report)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

