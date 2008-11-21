# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2008 Tiny SPRL (<http://tiny.be>). All Rights Reserved
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

from mx import DateTime
import time

from osv import fields, osv
from tools.translate import _

class hr_timesheet_group(osv.osv):
    _name = "hr.timesheet.group"
    _description = "Working Time"
    _columns = {
        'name' : fields.char("Group name", size=64, required=True),
        'timesheet_id' : fields.one2many('hr.timesheet', 'tgroup_id', 'Working Time'),
        'manager' : fields.many2one('res.users', 'Workgroup manager'),
    }
    #
    # TODO: improve; very slow !
    #       bug if transition to another period
    #
    def interval_get(self, cr, uid, id, dt_from, hours, byday=True):
        if not id:
            return [(dt_from,dt_from+DateTime.RelativeDateTime(hours=int(hours)*3))]
        todo = hours
        cycle = 0
        result = []
        while todo>0:
            cr.execute("select hour_from,hour_to from hr_timesheet where dayofweek='%s' and tgroup_id=%d order by hour_from", (dt_from.day_of_week,id))
            for (hour_from,hour_to) in cr.fetchall():
                h1,m1 = map(int,hour_from.split(':'))
                h2,m2 = map(int,hour_to.split(':'))
                d1 = DateTime.DateTime(dt_from.year,dt_from.month,dt_from.day,h1,m1)
                d2 = DateTime.DateTime(dt_from.year,dt_from.month,dt_from.day,h2,m2)
                if dt_from<d2:
                    date1 = max(dt_from,d1)
                    if date1+DateTime.RelativeDateTime(hours=todo)<=d2:
                        result.append((date1, date1+DateTime.RelativeDateTime(hours=todo)))
                        todo = 0
                    else:
                        todo -= (d2-date1).hours
                        result.append((date1, d2))
            dt_from = DateTime.DateTime(dt_from.year,dt_from.month,dt_from.day)+DateTime.RelativeDateTime(days=1)
            cycle+=1
            if cycle>7 and todo==hours:
                return [(dt_from,dt_from+DateTime.RelativeDateTime(hours=hours*3))]
        if byday:
            i = 1
            while i<len(result):
                if (result[i][0]-result[i-1][1]).days<1:
                    result[i-1]=(result[i-1][0],result[i][1])
                    del result[i]
                else:
                    i+=1
        return result
hr_timesheet_group()


class hr_employee_category(osv.osv):
    _name = "hr.employee.category"
    _description = "Employee Category"
    _columns = {
        'name' : fields.char("Category", size=64, required=True),
        'parent_id': fields.many2one('hr.employee.category', 'Parent category', select=True),
        'child_ids': fields.one2many('hr.employee.category', 'parent_id', 'Childs Categories')
    }
hr_employee_category()

class hr_employee(osv.osv):
    _name = "hr.employee"
    _description = "Employee"

    _columns = {
        'name' : fields.char("Employee", size=128, required=True),
        'active' : fields.boolean('Active'),
        'company_id': fields.many2one('res.company', 'Company'),
        'user_id' : fields.many2one('res.users', 'Related User'),

        'country_id' : fields.many2one('res.country', 'Nationality'),
        'birthday' : fields.date("Started on"),
        'ssnid': fields.char('SSN No', size=32),
        'sinid': fields.char('SIN No', size=32),
        'otherid': fields.char('Other ID', size=32),
        'gender': fields.selection([('',''),('male','Male'),('female','Female')], 'Gender'),
        'marital': fields.selection([('maried','Maried'),('unmaried','Unmaried'),('divorced','Divorced'),('other','Other')],'Marital Status', size=32),

        'address_id': fields.many2one('res.partner.address', 'Working Address'),
        'work_phone': fields.char('Work Phone', size=32),
        'work_email': fields.char('Work Email', size=128),
        'work_location': fields.char('Office Location', size=32),

        'notes': fields.text('Notes'),
        'parent_id': fields.many2one('hr.employee', 'Manager', select=True),
        'category_id' : fields.many2one('hr.employee.category', 'Category'),
        'child_ids': fields.one2many('hr.employee', 'parent_id','Subordinates'),
    }
    _defaults = {
        'active' : lambda *a: True,
    }
    
hr_employee()

class hr_timesheet(osv.osv):
    _name = "hr.timesheet"
    _description = "Timesheet Line"
    _columns = {
        'name' : fields.char("Name", size=64, required=True),
        'dayofweek': fields.selection([('0','Monday'),('1','Tuesday'),('2','Wednesday'),('3','Thursday'),('4','Friday'),('5','Saturday'),('6','Sunday')], 'Day of week'),
        'date_from' : fields.date('Starting date'),
        'hour_from' : fields.float('Work from', size=8, required=True),
        'hour_to' : fields.float("Work to", size=8, required=True),
        'tgroup_id' : fields.many2one("hr.timesheet.group", "Employee's timesheet group", select=True),
    }
    _order = 'dayofweek, hour_from'
hr_timesheet()


