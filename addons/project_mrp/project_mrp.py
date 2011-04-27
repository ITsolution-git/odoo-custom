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
import netsvc

class project_task(osv.osv):
    _name = "project.task"
    _inherit = "project.task"
    _columns = {
        'procurement_id': fields.many2one('procurement.order', 'Procurement', ondelete='set null'),
        'sale_id': fields.many2one('sale.order','Sale Order')
    }

    def _validate_subflows(self, cr, uid, ids):
        for task in self.browse(cr, uid, ids):
            if task.procurement_id:
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'procurement.order', task.procurement_id.id, 'subflow.done', cr)

    def do_close(self, cr, uid, ids, *args, **kwargs):
        res = super(project_task, self).do_close(cr, uid, ids, *args, **kwargs)
        self._validate_subflows(cr, uid, ids)
        return res

    def do_cancel(self, cr, uid, ids, *args, **kwargs):
        res = super(project_task, self).do_cancel(cr, uid, ids, *args, **kwargs)
        self._validate_subflows(cr, uid, ids)
        return res
    
project_task()

class product_product(osv.osv):
    _inherit = "product.product"
    _columns = {
        'project_id': fields.many2one('project.project', 'Project', ondelete='set null',)
    }
product_product()

class sale_order(osv.osv):
    _inherit ='sale.order'

    def _picked_rate(self, cr, uid, ids, name, arg, context=None):
        if not ids:
            return {}
        temp = {}
        res = super(sale_order, self)._picked_rate(cr, uid, ids, name, arg, context=context)
        for id in ids:
            temp[id] = {}
            temp[id]['number_of_done'] = 0
            temp[id]['percentage'] = 0.0
            temp[id]['number_of_stockable'] = 0.0
            temp[id]['total_no_task'] = 0
            temp[id]['total'] = 0

        cr.execute('''select so.id as sale_id, t.state as task_state ,
                    t.id as task_id, count(t.id) as total
                    from project_task as t
                    left join sale_order as so on so.id = t.sale_id
                    where so.id in %s group by so.id,t.state,t.id ''',(tuple(ids),))
        sale_task_data = cr.dictfetchall()

        if not sale_task_data:
            return res
        for item in sale_task_data:
            temp[item['sale_id']]['total_no_task'] += item['total']
            if item['task_state'] == 'done':
                temp[item['sale_id']]['number_of_done'] += 1
            else: 
                pass
        for sale in self.browse(cr, uid, ids, context=None):
            # Percent of service + other' Type product
            temp[sale.id]['percentage'] = temp[sale.id]['total_no_task'] and (float(temp[sale.id]['number_of_done']) / temp[sale.id]['total_no_task']) * 100
            temp[sale.id]['number_of_stockable'] = len(sale.order_line) - temp[sale.id]['total_no_task']
            if temp[sale.id]['percentage'] == 100 and res[sale.id] == 100:
                continue
            elif temp[sale.id]['number_of_stockable'] == 0:
                res[sale.id] = (temp[sale.id]['percentage'])
            else:
                res[sale.id] = round((res[sale.id] + temp[sale.id]['percentage']) / (temp[sale.id]['number_of_stockable'] + temp[sale.id]['total_no_task']), 2)
                if res[sale.id] > 100:
                    res[sale.id] = 100
        return res

    _columns = {
                'picked_rate': fields.function(_picked_rate, method=True, string='Picked', type='float'),
               }

sale_order()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
