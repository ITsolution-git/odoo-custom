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
from caldav import calendar

class project_task(osv.osv):
    _name = "project.task"
    _inherit = ["calendar.todo", "project.task"]
    _columns = {
        'write_date': fields.datetime('Write Date'),
        'create_date': fields.datetime('Create Date'),
        'attendee_ids': fields.many2many('calendar.attendee', \
                                         'task_attendee_rel', 'task_id', 'attendee_id', 'Attendees'),
        'state': fields.selection([('draft', 'Draft'),('open', 'In Progress'),('pending', 'Pending'), ('cancelled', 'Cancelled'), ('done', 'Done')], 'State', readonly=True, required=True,
                                  help='If the task is created the state is \'Draft\'.\n If the task is started, the state becomes \'In Progress\'.\n If review is needed the task is in \'Pending\' state.\
                                  \n If the task is over, the states is set to \'Done\'.'),
    }
    _defaults = {
        'state': 'draft',
    }

    def import_cal(self, cr, uid, data, data_id=None, context=None):
        todo_obj = self.pool.get('basic.calendar.todo')
        vals = todo_obj.import_cal(cr, uid, data, context=context)
        return self.check_import(cr, uid, vals, context=context)

    def check_import(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        ids = []
        for val in vals:
            obj_tm = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.project_time_mode_id
            if not val.get('planned_hours', False):
                # 'Computes duration' in days
                plan = 0.0
                if val.get('date') and  val.get('date_deadline'):
                    start = datetime.strptime(val['date'], '%Y-%m-%d %H:%M:%S')
                    end = datetime.strptime(val['date_deadline'], '%Y-%m-%d %H:%M:%S')
                    diff = end - start
                    plan = (diff.seconds/float(86400) + diff.days) * obj_tm.factor
                val['planned_hours'] = plan
            else:
                # Converts timedelta into hours
                hours = (val['planned_hours'].seconds / float(3600)) + \
                                        (val['planned_hours'].days * 24)
                val['planned_hours'] = hours
            exists, r_id = calendar.uid2openobjectid(cr, val['id'], self._name, val.get('recurrent_id'))
            val.pop('id')
            if exists:
                self.write(cr, uid, [exists], val)
                ids.append(exists)
            else:
                task_id = self.create(cr, uid, val)
                ids.append(task_id)
        return ids

    def export_cal(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        task_datas = self.read(cr, uid, ids, [], context ={'read': True})
        tasks = []
        for task in task_datas:
            if task.get('planned_hours', None) and task.get('date_deadline', None):
                task.pop('planned_hours')
            tasks.append(task)
        todo_obj = self.pool.get('basic.calendar.todo')
        ical = todo_obj.export_cal(cr, uid, tasks, context={'model': self._name})
        calendar_val = ical.serialize()
        return calendar_val.replace('"', '').strip()

project_task()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
