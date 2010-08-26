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
import time

from osv import osv, fields

class hr_attendance_byweek(osv.osv_memory):
    _name = 'hr.attendance.week'
    _description = 'Print Week Attendance Report'
    _columns = {
        'init_date': fields.date('Starting Date', required=True),
        'end_date': fields.date('Ending Date', required=True)
    }
    _defaults = {
         'init_date': time.strftime('%Y-%m-%d'),
         'end_date': time.strftime('%Y-%m-%d'),
    }

    def print_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        datas = {
             'ids': [],
             'model': 'hr.employee',
             'form': self.read(cr, uid, ids)[0]
        }
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'hr.attendance.allweeks',
            'datas': datas,
        }
hr_attendance_byweek()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: