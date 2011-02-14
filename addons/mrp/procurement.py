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

from datetime import datetime
from dateutil.relativedelta import relativedelta
from osv import fields
from osv import osv
from tools.translate import _
import ir
import netsvc
import time

class procurement_order(osv.osv):
    _inherit = 'procurement.order'
    _columns = {
        'bom_id': fields.many2one('mrp.bom', 'BoM', ondelete='cascade', select=True),
        'property_ids': fields.many2many('mrp.property', 'procurement_property_rel', 'procurement_id','property_id', 'Properties'),
    }
    
    def check_produce_product(self, cr, uid, procurement, context=[]):
        """ Finds the bill of material for the product from procurement order.
        @return: True or False
        """
        properties = [x.id for x in procurement.property_ids]
        bom_id = self.pool.get('mrp.bom')._bom_find(cr, uid, procurement.product_id.id, procurement.product_uom.id, properties)
        if not bom_id:
            cr.execute('update procurement_order set message=%s where id=%s', (_('No BoM defined for this product !'), procurement.id))
            for (id, name) in self.name_get(cr, uid, procurement.id):
                message = _("Procurement '%s' has an exception: 'No BoM defined for this product !'") % name
                self.log(cr, uid, id, message)
            return False
        return True
    
    def get_phantom_bom_id(self, cr, uid, ids, context=None):
        for procurement in self.browse(cr, uid, ids, context=context):
            if procurement.move_id and procurement.move_id.product_id.supply_method=='produce' \
                 and procurement.move_id.product_id.procure_method=='make_to_order':
                    phantom_bom_id = self.pool.get('mrp.bom').search(cr, uid, [
                        ('product_id', '=', procurement.move_id.product_id.id),
                        ('bom_id', '=', False),
                        ('type', '=', 'phantom')]) 
                    return phantom_bom_id 
        return False
    
    def action_produce_assign_product(self, cr, uid, ids, context=None):
        """ This is action which call from workflow to assign production order to procurements
        @return: True
        """
        procurement_obj = self.pool.get('procurement.order')
        res = procurement_obj.make_mo(cr, uid, ids, context=context)
        res = res.values()
        return len(res) and res[0] or 0
    
    def make_mo(self, cr, uid, ids, context=None):
        """ Make Manufacturing(production) order from procurement
        @return: New created Production Orders procurement wise 
        """
        res = {}
        company = self.pool.get('res.users').browse(cr, uid, uid, context).company_id
        production_obj = self.pool.get('mrp.production')
        move_obj = self.pool.get('stock.move')
        wf_service = netsvc.LocalService("workflow")
        procurement_obj = self.pool.get('procurement.order')
        for procurement in procurement_obj.browse(cr, uid, ids, context=context):
            res_id = procurement.move_id.id
            loc_id = procurement.location_id.id
            newdate = datetime.strptime(procurement.date_planned, '%Y-%m-%d %H:%M:%S') - relativedelta(days=procurement.product_id.product_tmpl_id.produce_delay or 0.0)
            newdate = newdate - relativedelta(days=company.manufacturing_lead)
            produce_id = production_obj.create(cr, uid, {
                'origin': procurement.origin,
                'product_id': procurement.product_id.id,
                'product_qty': procurement.product_qty,
                'product_uom': procurement.product_uom.id,
                'product_uos_qty': procurement.product_uos and procurement.product_uos_qty or False,
                'product_uos': procurement.product_uos and procurement.product_uos.id or False,
                'location_src_id': procurement.location_id.id,
                'location_dest_id': procurement.location_id.id,
                'bom_id': procurement.bom_id and procurement.bom_id.id or False,
                'date_planned': newdate.strftime('%Y-%m-%d %H:%M:%S'),
                'move_prod_id': res_id,
                'company_id': procurement.company_id.id,
            })
            res[procurement.id] = produce_id
            self.write(cr, uid, [procurement.id], {'state': 'running'})
            bom_result = production_obj.action_compute(cr, uid,
                    [produce_id], properties=[x.id for x in procurement.property_ids])
            wf_service.trg_validate(uid, 'mrp.production', produce_id, 'button_confirm', cr)
            move_obj.write(cr, uid, [res_id],
                    {'location_id': procurement.location_id.id})
        return res
    
procurement_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
