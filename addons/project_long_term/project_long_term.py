# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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
from lxml import etree
import mx.DateTime
import time

from tools.translate import _
from osv import fields, osv

class project_phase(osv.osv):
    _name = "project.phase"
    _description = "Project Phase"

    def _check_recursion(self, cr, uid, ids, context=None):
         if context is None:
            context = {}

         data_phase = self.browse(cr, uid, ids[0], context=context)
         prev_ids = data_phase.previous_phase_ids
         next_ids = data_phase.next_phase_ids
         # it should neither be in prev_ids nor in next_ids
         if (data_phase in prev_ids) or (data_phase in next_ids):
             return False
         ids = [id for id in prev_ids if id in next_ids]
         # both prev_ids and next_ids must be unique
         if ids:
             return False
         # unrelated project
         prev_ids = [rec.id for rec in prev_ids]
         next_ids = [rec.id for rec in next_ids]
         # iter prev_ids
         while prev_ids:
             cr.execute('SELECT distinct prv_phase_id FROM project_phase_rel WHERE next_phase_id IN %s', (tuple(prev_ids),))
             prv_phase_ids = filter(None, map(lambda x: x[0], cr.fetchall()))
             if data_phase.id in prv_phase_ids:
                 return False
             ids = [id for id in prv_phase_ids if id in next_ids]
             if ids:
                 return False
             prev_ids = prv_phase_ids
         # iter next_ids
         while next_ids:
             cr.execute('SELECT distinct next_phase_id FROM project_phase_rel WHERE prv_phase_id IN %s', (tuple(next_ids),))
             next_phase_ids = filter(None, map(lambda x: x[0], cr.fetchall()))
             if data_phase.id in next_phase_ids:
                 return False
             ids = [id for id in next_phase_ids if id in prev_ids]
             if ids:
                 return False
             next_ids = next_phase_ids
         return True

    def _check_dates(self, cr, uid, ids, context=None):
         for phase in self.read(cr, uid, ids, ['date_start', 'date_end'], context=context):
             if phase['date_start'] and phase['date_end'] and phase['date_start'] > phase['date_end']:
                 return False
         return True

    def _check_constraint_start(self, cr, uid, ids, context=None):
         phase = self.read(cr, uid, ids[0], ['date_start', 'constraint_date_start'], context=context)
         if phase['date_start'] and phase['constraint_date_start'] and phase['date_start'] < phase['constraint_date_start']:
             return False
         return True

    def _check_constraint_end(self, cr, uid, ids, context=None):
         phase = self.read(cr, uid, ids[0], ['date_end', 'constraint_date_end'], context=context)
         if phase['date_end'] and phase['constraint_date_end'] and phase['date_end'] > phase['constraint_date_end']:
             return False
         return True

    def _get_default_uom_id(self, cr, uid):
       model_data_obj = self.pool.get('ir.model.data')
       model_data_id = model_data_obj._get_id(cr, uid, 'product', 'uom_hour')
       return model_data_obj.read(cr, uid, [model_data_id], ['res_id'])[0]['res_id']

    _columns = {
        'name': fields.char("Name", size=64, required=True),
        'date_start': fields.date('Start Date', help="Starting Date of the phase", states={'done':[('readonly',True)], 'cancelled':[('readonly',True)]}),
        'date_end': fields.date('End Date', help="Ending Date of the phase", states={'done':[('readonly',True)], 'cancelled':[('readonly',True)]}),
        'constraint_date_start': fields.date('Start Date', help='force the phase to start after this date', states={'done':[('readonly',True)], 'cancelled':[('readonly',True)]}),
        'constraint_date_end': fields.date('End Date', help='force the phase to finish before this date', states={'done':[('readonly',True)], 'cancelled':[('readonly',True)]}),
        'project_id': fields.many2one('project.project', 'Project', required=True),
        'next_phase_ids': fields.many2many('project.phase', 'project_phase_rel', 'prv_phase_id', 'next_phase_id', 'Next Phases', states={'cancelled':[('readonly',True)]}),
        'previous_phase_ids': fields.many2many('project.phase', 'project_phase_rel', 'next_phase_id', 'prv_phase_id', 'Previous Phases', states={'cancelled':[('readonly',True)]}),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying a list of phases."),
        'duration': fields.float('Duration', required=True, help="By default in days", states={'done':[('readonly',True)], 'cancelled':[('readonly',True)]}),
        'product_uom': fields.many2one('product.uom', 'Duration UoM', required=True, help="UoM (Unit of Measure) is the unit of measurement for Duration", states={'done':[('readonly',True)], 'cancelled':[('readonly',True)]}),
        'task_ids': fields.one2many('project.task', 'phase_id', "Project Tasks", states={'done':[('readonly',True)], 'cancelled':[('readonly',True)]}),
        'resource_ids': fields.one2many('project.resource.allocation', 'phase_id', "Project Resources",states={'done':[('readonly',True)], 'cancelled':[('readonly',True)]}),
        'responsible_id': fields.many2one('res.users', 'Responsible', states={'done':[('readonly',True)], 'cancelled':[('readonly',True)]}),
        'state': fields.selection([('draft', 'Draft'), ('open', 'In Progress'), ('pending', 'Pending'), ('cancelled', 'Cancelled'), ('done', 'Done')], 'State', readonly=True, required=True,
                                  help='If the phase is created the state \'Draft\'.\n If the phase is started, the state becomes \'In Progress\'.\n If review is needed the phase is in \'Pending\' state.\
                                  \n If the phase is over, the states is set to \'Done\'.')
     }
    _defaults = {
        'responsible_id': lambda obj,cr,uid,context: uid,
        'state': 'draft',
        'sequence': 10,
        'product_uom': lambda self,cr,uid,c: self.pool.get('product.uom').search(cr, uid, [('name', '=', _('Day'))], context=c)[0]
    }
    _order = "name"
    _constraints = [
        (_check_recursion,'Loops in phases not allowed',['next_phase_ids', 'previous_phase_ids']),
        (_check_dates, 'Phase start-date must be lower than phase end-date.', ['date_start', 'date_end']),
        #(_check_constraint_start, 'Phase must start-after constraint start Date.', ['date_start', 'constraint_date_start']),
        #(_check_constraint_end, 'Phase must end-before constraint end Date.', ['date_end', 'constraint_date_end']),
    ]

    def onchange_project(self, cr, uid, ids, project, context=None):
        result = {}
        project_obj = self.pool.get('project.project')
        if project:
            project_id = project_obj.browse(cr, uid, project, context=context)
            if project_id.date_start:
                result['date_start'] = mx.DateTime.strptime(project_id.date_start, "%Y-%m-%d").strftime('%Y-%m-%d')
                return {'value': result}
        return {'value': {'date_start': []}}

    def _check_date_start(self, cr, uid, phase, date_end, context=None):
       if context is None:
            context = {}
       """
       Check And Compute date_end of phase if change in date_start < older time.
       """
       uom_obj = self.pool.get('product.uom')
       resource_obj = self.pool.get('resource.resource')
       cal_obj = self.pool.get('resource.calendar')
       calendar_id = phase.project_id.resource_calendar_id and phase.project_id.resource_calendar_id.id or False
       resource_id = resource_obj.search(cr, uid, [('user_id', '=', phase.responsible_id.id)])
       if resource_id:
#            cal_id = resource_obj.browse(cr, uid, resource_id[0], context=context).calendar_id.id
            res = resource_obj.read(cr, uid, resource_id, ['calendar_id'], context=context)[0]
            cal_id = res.get('calendar_id', False) and res.get('calendar_id')[0] or False
            if cal_id:
                calendar_id = cal_id
       default_uom_id = self._get_default_uom_id(cr, uid)
       avg_hours = uom_obj._compute_qty(cr, uid, phase.product_uom.id, phase.duration, default_uom_id)
       work_times = cal_obj.interval_min_get(cr, uid, calendar_id, date_end, avg_hours or 0.0, resource_id and resource_id[0] or False)
       dt_start = work_times[0][0].strftime('%Y-%m-%d')
       self.write(cr, uid, [phase.id], {'date_start': dt_start, 'date_end': date_end.strftime('%Y-%m-%d')}, context=context)

    def _check_date_end(self, cr, uid, phase, date_start, context=None):
       if context is None:
            context = {}
       """
       Check And Compute date_end of phase if change in date_end > older time.
       """
       uom_obj = self.pool.get('product.uom')
       resource_obj = self.pool.get('resource.resource')
       cal_obj = self.pool.get('resource.calendar')
       calendar_id = phase.project_id.resource_calendar_id and phase.project_id.resource_calendar_id.id or False
       resource_id = resource_obj.search(cr, uid, [('user_id', '=', phase.responsible_id.id)], context=context)
       if resource_id:
#            cal_id = resource_obj.browse(cr, uid, resource_id[0], context=context).calendar_id.id
            res = resource_obj.read(cr, uid, resource_id, ['calendar_id'], context=context)[0]
            cal_id = res.get('calendar_id', False) and res.get('calendar_id')[0] or False
            if cal_id:
                calendar_id = cal_id
       default_uom_id = self._get_default_uom_id(cr, uid)
       avg_hours = uom_obj._compute_qty(cr, uid, phase.product_uom.id, phase.duration, default_uom_id)
       work_times = cal_obj.interval_get(cr, uid, calendar_id, date_start, avg_hours or 0.0, resource_id and resource_id[0] or False)
       dt_end = work_times[-1][1].strftime('%Y-%m-%d')
       self.write(cr, uid, [phase.id], {'date_start': date_start.strftime('%Y-%m-%d'), 'date_end': dt_end}, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        resource_calendar_obj = self.pool.get('resource.calendar')
        resource_obj = self.pool.get('resource.resource')
        uom_obj = self.pool.get('product.uom')
        if context is None:
            context = {}
        if context.get('scheduler',False):
            return super(project_phase, self).write(cr, uid, ids, vals, context=context)
        # Consider calendar and efficiency if the phase is performed by a resource
        # otherwise consider the project's working calendar
        if type(ids) == int:
            ids = [ids]
        phase = self.browse(cr, uid, ids[0], context=context)
        calendar_id = phase.project_id.resource_calendar_id and phase.project_id.resource_calendar_id.id or False
        resource_id = resource_obj.search(cr, uid, [('user_id', '=', phase.responsible_id.id)],context=context)
        if resource_id:
                cal_id = resource_obj.browse(cr, uid, resource_id[0], context=context).calendar_id.id
                if cal_id:
                    calendar_id = cal_id
        default_uom_id = self._get_default_uom_id(cr, uid)
        avg_hours = uom_obj._compute_qty(cr, uid, phase.product_uom.id, phase.duration, default_uom_id)

        # Change the date_start and date_end
        # for previous and next phases respectively based on valid condition
        if vals.get('date_start', False) and vals['date_start'] < phase.date_start:
                dt_start = mx.DateTime.strptime(vals['date_start'], '%Y-%m-%d')
                work_times = resource_calendar_obj.interval_get(cr, uid, calendar_id, dt_start, avg_hours or 0.0, resource_id and resource_id[0] or False)
                if work_times:
                    vals['date_end'] = work_times[-1][1].strftime('%Y-%m-%d')
                for prv_phase in phase.previous_phase_ids:
                    self._check_date_start(cr, uid, prv_phase, dt_start, context=context)
        if vals.get('date_end', False) and vals['date_end'] > phase.date_end:
                dt_end = mx.DateTime.strptime(vals['date_end'],'%Y-%m-%d')
                work_times = resource_calendar_obj.interval_min_get(cr, uid, calendar_id, dt_end, avg_hours or 0.0, resource_id and resource_id[0] or False)
                if work_times:
                    vals['date_start'] = work_times[0][0].strftime('%Y-%m-%d')
                for next_phase in phase.next_phase_ids:
                    self._check_date_end(cr, uid, next_phase, dt_end, context=context)
        return super(project_phase, self).write(cr, uid, ids, vals, context=context)

    def set_draft(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state': 'draft'})
        return True

    def set_open(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state': 'open'})
        return True

    def set_pending(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state': 'pending'})
        return True

    def set_cancel(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state': 'cancelled'})
        return True

    def set_done(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state': 'done'})
        return True

project_phase()

class project_resource_allocation(osv.osv):
    _name = 'project.resource.allocation'
    _description = 'Project Resource Allocation'
    _rec_name = 'resource_id'
    _columns = {
        'resource_id': fields.many2one('resource.resource', 'Resource', required=True),
        'phase_id': fields.many2one('project.phase', 'Project Phase', ondelete='cascade', required=True),
        'phase_id_date_start': fields.related('phase_id', 'date_start', type='date', string='Starting Date of the phase'),
        'phase_id_date_end': fields.related('phase_id', 'date_end', type='date', string='Ending Date of the phase'),
        'useability': fields.float('Usability', help="Usability of this resource for this project phase in percentage (=50%)"),
    }
    _defaults = {
        'useability': 100,
    }

project_resource_allocation()

class project(osv.osv):
    _inherit = "project.project"
    _columns = {
        'phase_ids': fields.one2many('project.phase', 'project_id', "Project Phases"),
        'resource_calendar_id': fields.many2one('resource.calendar', 'Working Time', help="Timetable working hours to adjust the gantt diagram report", states={'close':[('readonly',True)]} ),
    }

project()

class task(osv.osv):
    _inherit = "project.task"
    _columns = {
        'phase_id': fields.many2one('project.phase', 'Project Phase'),
    }

task()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
