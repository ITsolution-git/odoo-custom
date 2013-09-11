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

from openerp.osv import fields, osv
from openerp import netsvc
from openerp.tools.translate import _

class procurement_order(osv.osv):
    _name = "procurement.order"
    _inherit = "procurement.order"
    _columns = {
        'task_id': fields.many2one('project.task', 'Task'),
        'sale_line_id': fields.many2one('sale.order.line', 'Sales order line')
    }

    def _is_procurement_task(self, cr, uid, procurement, context=None):
        return procurement.product_id.type == 'service' and procurement.product_id.auto_create_task or False

    def _assign(self, cr, uid, procurement, context=None):
        res = super(procurement_order, self)._assign(cr, uid, procurement, context=context)
        if not res:
            #if there isn't any specific procurement.rule defined for the product, we may want to create a task
            if self._is_procurement_task(cr, uid, procurement, context=context):
                return True
        return res

    def _run(self, cr, uid, procurement, context=None):
        if self._is_procurement_task(cr, uid, procurement, context=context) and not procurement.task_id:
            #create a task for the procurement
            return self._create_service_task(cr, uid, procurement, context=context)
        return super(procurement_order, self)._run(cr, uid, procurement, context=context)

    def _check(self, cr, uid, procurement, context=None):
        if self._is_procurement_task(cr, uid, procurement, context=context) and procurement.task_id and procurement.task_id.stage_id.closed:
            return True
        return super(procurement_order, self)._check(cr, uid, procurement, context=context)

    def _convert_qty_company_hours(self, cr, uid, procurement, context=None):
        product_uom = self.pool.get('product.uom')
        company_time_uom_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.project_time_mode_id
        if procurement.product_uom.id != company_time_uom_id.id and procurement.product_uom.category_id.id == company_time_uom_id.category_id.id:
            planned_hours = product_uom._compute_qty(cr, uid, procurement.product_uom.id, procurement.product_qty, company_time_uom_id.id)
        else:
            planned_hours = procurement.product_qty
        return planned_hours

    def _get_project(self, cr, uid, procurement, context=None):
        project_project = self.pool.get('project.project')
        project = procurement.product_id.project_id
        if not project and procurement.sale_line_id:
            # find the project corresponding to the analytic account of the sales order
            account = procurement.sale_line_id.order_id.project_id
            project_ids = project_project.search(cr, uid, [('analytic_account_id', '=', account.id)])
            projects = project_project.browse(cr, uid, project_ids, context=context)
            project = projects and projects[0] or False
        return project

    def _create_service_task(self, cr, uid, procurement, context=None):
        project_task = self.pool.get('project.task')
        project = self._get_project(cr, uid, procurement, context=context)
        planned_hours = self._convert_qty_company_hours(cr, uid, procurement, context=context)
        task_id = project_task.create(cr, uid, {
            'name': '%s:%s' % (procurement.origin or '', procurement.product_id.name),
            'date_deadline': procurement.date_planned,
            'planned_hours': planned_hours,
            'remaining_hours': planned_hours,
            'partner_id': procurement.sale_line_id and procurement.sale_line_id.order_id.partner_id.id or False,
            'user_id': procurement.product_id.product_manager.id,
            'procurement_id': procurement.id,
            'description': procurement.name + '\n',
            'project_id': project and project.id or False,
            'company_id': procurement.company_id.id,
        },context=context)
        self.write(cr, uid, [procurement.id], {'task_id': task_id, 'message':_('Task created.')}, context=context)
        self.project_task_create_note(cr, uid, [procurement.id], context=context)
        return task_id

    def project_task_create_note(self, cr, uid, ids, context=None):
        for procurement in self.browse(cr, uid, ids, context=context):
            body = _("Task created")
            self.message_post(cr, uid, [procurement.id], body=body, context=context)
            if procurement.sale_line_id and procurement.sale_line_id.order_id:
                procurement.sale_line_id.order_id.message_post(body=body)



class ProjectTaskStageMrp(osv.Model):
    """ Override project.task.type model to add a 'closed' boolean field allowing
        to know that tasks in this stage are considered as closed. Indeed since
        OpenERP 8.0 status is not present on tasks anymore, only stage_id. """
    _name = 'project.task.type'
    _inherit = 'project.task.type'

    _columns = {
        'closed': fields.boolean('Close', help="Tasks in this stage are considered as closed."),
    }

    _defaults = {
        'closed': False,
    }


class project_task(osv.osv):
    _name = "project.task"
    _inherit = "project.task"
    _columns = {
        'procurement_id': fields.many2one('procurement.order', 'Procurement', ondelete='set null'),
        'sale_line_id': fields.related('procurement_id', 'sale_line_id', type='many2one', relation='sale.order.line', store=True, string='Sales Order Line'),
    }

    def _validate_subflows(self, cr, uid, ids, context=None):
        proc_obj = self.pool.get("procurement.order")
        for task in self.browse(cr, uid, ids, context=context):
            if task.procurement_id:
                proc_obj.check(cr, uid, [task.procurement_id.id], context=context)

    def write(self, cr, uid, ids, values, context=None):
        """ When closing tasks, validate subflows. """
        res = super(project_task, self).write(cr, uid, ids, values, context=context)
        if values.get('stage_id'):
            stage = self.pool.get('project.task.type').browse(cr, uid, values.get('stage_id'), context=context)
            if stage.closed:
                self._validate_subflows(cr, uid, ids, context=context)
        return res

class product_product(osv.osv):
    _inherit = "product.product"
    _columns = {
        'project_id': fields.many2one('project.project', 'Project', ondelete='set null',),
        'auto_create_task': fields.boolean('Create Task Automatically', help="Thick this option if you want to create a task automatically each time this product is sold"),
    }


class sale_order(osv.osv):
    _inherit = 'sale.order'

    def _prepare_order_line_procurement(self, cr, uid, order, line, group_id=False, context=None):
        proc_data = super(sale_order, self)._prepare_order_line_procurement(cr,
                uid, order, line, group_id = group_id, context=context)
        if not(line.product_id.type== "service" and not line.product_id.auto_create_task):
            proc_data['sale_line_id'] = line.id
        return proc_data

    def _check_create_procurement(self, cr, uid, order, line, context=None):
        create = super(sale_order, self)._check_create_procurement(cr, uid, order, line, context=context)
        if (line.product_id.type== "service" and not line.product_id.auto_create_task):
            create = True
        return create

    def _picked_rate(self, cr, uid, ids, name, arg, context=None):
        if not ids:
            return {}
        res_sale = {}
        res = super(sale_order, self)._picked_rate(cr, uid, ids, name, arg, context=context)
        cr.execute('''select sol.order_id as sale_id, stage.closed as task_closed ,
                    t.id as task_id, sum(sol.product_uom_qty) as total
                    from project_task as t
                    left join sale_order_line as sol on sol.id = t.sale_line_id
                    left join project_task_type as stage on stage.id = t.stage_id
                    where sol.order_id in %s group by sol.order_id,stage.closed,t.id ''',(tuple(ids),))
        sale_task_data = cr.dictfetchall()

        if not sale_task_data:
            return res

        for id in ids:
            res_sale[id] = {
                'number_of_done': 0,
                'total_no_task': 0,
            }
        #compute the sum of quantity for each SO
        cr.execute('''select sol.order_id as sale_id, sum(sol.product_uom_qty) as total
                    from sale_order_line sol where sol.order_id in %s group by sol.order_id''',(tuple(ids),))
        total_qtty_ref = cr.dictfetchall()
        for item in total_qtty_ref:
            res_sale[item['sale_id']]['number_of_stockable'] = item['total']

        for item in sale_task_data:
            res_sale[item['sale_id']]['total_no_task'] += item['total']
            if item['task_closed']:
                res_sale[item['sale_id']]['number_of_done'] += item['total']

        for sale in self.browse(cr, uid, ids, context=context):
            if 'number_of_stockable' in res_sale[sale.id]:
                res_sale[sale.id]['number_of_stockable'] -= res_sale[sale.id]['total_no_task']
                #adjust previously percentage because now we must also count the product of type service
                res[sale.id] = res[sale.id] * float(res_sale[sale.id]['number_of_stockable']) / (res_sale[sale.id]['number_of_stockable'] + res_sale[sale.id]['total_no_task'])
                #add the task
                res[sale.id] += res_sale[sale.id]['number_of_done'] * 100 /  (res_sale[sale.id]['number_of_stockable'] + res_sale[sale.id]['total_no_task'])
        return res

    _columns = {
        'picked_rate': fields.function(_picked_rate, method=True, string='Picked', type='float'),
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
