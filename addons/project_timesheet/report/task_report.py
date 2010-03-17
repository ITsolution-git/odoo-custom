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

from osv import fields,osv
import mx.DateTime
import tools

#class  task_report(osv.osv):
#    _name = "task.report"
#    _description = "Project task report"
#    _auto = False
#    _columns = {
#        'name': fields.char('Task',size=64,required=False, readonly=True),
#        'month':fields.selection([('01','January'), ('02','February'), ('03','March'), ('04','April'), ('05','May'), ('06','June'),
#                                  ('07','July'), ('08','August'), ('09','September'), ('10','October'), ('11','November'), ('12','December')],'Month',readonly=True),
#        'user_id':fields.many2one('res.users', 'User', readonly=True),
#        'task_nbr': fields.float('Task Number', readonly=True),
#        'task_hrs': fields.float('Task Hours', readonly=True),
#        'task_progress': fields.float('Task Progress', readonly=True),
#        'company_id' : fields.many2one('res.company', 'Company'),
#        'task_state': fields.selection([('draft', 'Draft'),('open', 'Open'),('pending', 'Pending'), ('cancelled', 'Cancelled'), ('done', 'Done'),('no','No Task')], 'Status', readonly=True),
#        'project_id':fields.many2one('project.project', 'Project'),
#        'year': fields.char('Year',size=64,required=False, readonly=True),
#        'date_start': fields.datetime('Starting Date',readonly=True),
#        'date_end': fields.datetime('Ending Date',readonly=True),
#        'date_deadline': fields.date('Deadline',readonly=True),
#        'type': fields.many2one('project.task.type', 'Stage'),
#        'priority' : fields.selection([('4','Very Low'), ('3','Low'), ('2','Medium'), ('1','Urgent'), ('0','Very urgent')], 'Importance'),
#        'assign_to': fields.many2one('res.users', 'Assigned to', readonly=True),
#        'remaining_hrs': fields.float('Remaining Hours', readonly=True),
#    }
#
#    def init(self, cr):
#        tools.sql.drop_view_if_exists(cr, 'task_report')
#        cr.execute('''
#            create or replace view task_report as (
#                select
#                    min(t.id) as id,
#                    to_char(t.create_date, 'YYYY') as year,
#                    to_char(t.create_date,'MM') as month,
#                    u.id as user_id,
#                    u.company_id as company_id,
#                    t.name as name,
#                    t.project_id as project_id,
#                    to_char(t.date_start,'YYYY/mm/dd') as date_start,
#                    to_char(t.date_end,'YYYY/mm/dd') as date_end,
#                    to_char(t.date_deadline,'YYYY/mm/dd') as date_deadline,
#                    t.type as type,
#                    t.priority as priority,
#                    t.user_id as assign_to,
#                    t.remaining_hours as remaining_hrs,
#                    count(t.*) as task_nbr,
#                    sum(t.planned_hours) as task_hrs,
#                    sum(t.planned_hours * (100 - t.progress) / 100) as task_progress,
#                    case when t.state is null then 'no' else t.state end as task_state
#                from
#                    res_users u
#                left join
#                    project_task t on (u.id = t.user_id)
#                where
#                    u.active
#                group by
#                    to_char(t.create_date, 'YYYY'),to_char(t.create_date,'MM'),u.id, u.company_id, t.state
#                    ,t.name,t.project_id,t.type,t.priority,
#                    t.user_id,t.remaining_hours,to_char(t.date_start,'YYYY/mm/dd'),to_char(t.date_end,'YYYY/mm/dd'),to_char(t.date_deadline,'YYYY/mm/dd')
#            )
#        ''')
#task_report()

class report_timesheet_task_user(osv.osv):
    _name = "report.timesheet.task.user"
    _auto = False
    _order = "name"

    def _get_task_hours(self, cr, uid, ids, name,args,context):
        result = {}
        for record in self.browse(cr, uid, ids,context):
            last_date = mx.DateTime.strptime(record.name, '%Y-%m-%d') + mx.DateTime.RelativeDateTime(months=1) - 1
            task_obj=self.pool.get('project.task.work')
            task_ids = task_obj.search(cr,uid,[('user_id','=',record.user_id.id),('date','>=',record.name),('date','<=',last_date.strftime('%Y-%m-%d'))])
            tsk_hrs = task_obj.read(cr,uid,task_ids,['hours','date','user_id'])
            total = 0.0
            for hrs in tsk_hrs:
                total += hrs['hours']
            result[record.id] = total
        return result

    def get_hrs_timesheet(self, cr, uid, ids, name,args,context):
        result = {}
        sum = 0.0
        for record in self.browse(cr, uid, ids, context):
            last_date = mx.DateTime.strptime(record.name, '%Y-%m-%d') + mx.DateTime.RelativeDateTime(months=1) - 1
            obj=self.pool.get('hr_timesheet_sheet.sheet.day')
            sheet_ids = obj.search(cr,uid,[('sheet_id.user_id','=',record.user_id.id),('name','>=',record.name),('name','<=',last_date.strftime('%Y-%m-%d'))])
            data_days = obj.read(cr,uid,sheet_ids,['name','sheet_id.user_id','total_attendance'])
            total = 0.0
            for day_attendance in data_days:
                total += day_attendance['total_attendance']
            result[record.id] = total
        return result

    _columns = {
        'name': fields.date('Month',readonly=True),
        'user_id': fields.many2one('res.users', 'User',readonly=True),
        'timesheet_hrs': fields.function(get_hrs_timesheet, method=True, string="Timesheet Hours"),
        'task_hrs': fields.function(_get_task_hours, method=True, string="Task Hours"),
      }


    def init(self, cr):
       cr.execute(""" create or replace view report_timesheet_task_user as (
        select
         ((r.id*12)+to_number(months.m_id,'99'))::integer as id,
               months.name as name,
               r.id as user_id
        from res_users r,
                (select to_char(p.date,'YYYY-MM-01') as name,
            to_char(p.date,'MM') as m_id
                from project_task_work p

            union
                select to_char(h.name,'YYYY-MM-01') as name,
                to_char(h.name,'MM') as m_id
                from hr_timesheet_sheet_sheet_day h) as months) """)

report_timesheet_task_user()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

