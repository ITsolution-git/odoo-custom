# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import time
from report import report_sxw


class pos_sales_user(report_sxw.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(pos_sales_user, self).__init__(cr, uid, name, context)
        self.total = 0.0
        self.localcontext.update({
                'time': time,
                'get_data':self._get_data,

                })

    def _get_data(self,form):
        dt1 = form['date_start'] + ' 00:00:00'
        dt2 = form['date_end'] + ' 23:59:59'
        data={}
        self.cr.execute("select po.name as pos,po.date_order,ru.name as user,po.state,rc.name " \
                        "from pos_order as po,res_users as ru,res_company as rc " \
                        "where po.date_order >= %s and po.date_order <= %s " \
                        "and po.company_id=rc.id and po.user_id=ru.id and po.user_id in %s " \
                            ,(dt1,dt2,tuple(form['user_id'][0][-1])))

        data = self.cr.dictfetchall()
        return data

report_sxw.report_sxw('report.pos.sales.user', 'pos.order', 'addons/point_of_sale/report/pos_sales_user.rml', parser=pos_sales_user)








