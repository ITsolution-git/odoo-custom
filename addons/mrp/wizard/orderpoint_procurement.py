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

#
# Order Point Method:
#    - Order if the virtual stock of today is bellow the min of the defined order point
#

import threading
from osv import fields,osv

class procurement_compute(osv.osv_memory):
    _name = 'mrp.procurement.orderpoint.compute'
    _description = 'Automatic Order Point'
    
    _columns = {
           'automatic': fields.boolean('Automatic Orderpoint', help='If the stock of a product is under 0, it will act like an orderpoint'),     
    }

    _defaults = {
            'automatic' : lambda *a: False,
    }
    
    def _procure_calculation_orderpoint(self, cr, uid, ids, context):
        try:
            proc_obj = self.pool.get('mrp.procurement')
            for proc in self.browse(cr, uid, ids):
                proc_obj._procure_orderpoint_confirm(cr, uid, automatic=proc.automatic, use_new_cursor=cr.dbname, context=context)
        finally:
            cr.close()
        return {}
    
    def procure_calculation(self, cr, uid, ids, context):
        threaded_calculation = threading.Thread(target=self._procure_calculation_orderpoint, args=(cr, uid, ids, context))
        threaded_calculation.start()
        return {}

procurement_compute()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
