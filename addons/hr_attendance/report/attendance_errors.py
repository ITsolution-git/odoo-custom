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

class attendance_print(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(attendance_print, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'time': time,
            'lst': self._lst,
            'total': self._lst_total,
        })

    def _sign(self, dt):
        if abs(dt.days)>1:
            format = '%d day'+(((abs(dt.days)>=2) and 's') or '')+' %H:%M:%S'
        else:
            format = '%H:%M:%S'
        if dt.seconds<0:
            return dt.strftime('- '+format)
        else:
            return dt.strftime(format)

    def _lst(self, employee_id, dt_from, dt_to, max, *args):
        self.cr.execute('select name as date, create_date, action, create_date-name as delay from hr_attendance where employee_id=%s and name<=%s and name>=%s and action in (%s,%s) order by name', (employee_id, dt_to, dt_from, 'sign_in', 'sign_out'))
        res = self.cr.dictfetchall()
        for r in res:
            if r['action']=='sign_out':
                r['delay'] = - r['delay']
            temp = r['delay'].seconds
            r['delay'] = self._sign(r['delay'])
            if abs(temp) < max*60:
                r['delay2'] = r['delay']
            else:
                r['delay2'] = '/'
        return res

    def _lst_total(self, employee_id, dt_from, dt_to, max, *args):
        self.cr.execute('select name as date, create_date, action, create_date-name as delay from hr_attendance where employee_id=%s and name<=%s and name>=%s and action in (%s,%s)', (employee_id, dt_to, dt_from, 'sign_in', 'sign_out'))
        res = self.cr.dictfetchall()
        if not res:
            return ('/','/')
        total = 0
        total2 = 0
        for r in res:
            if r['action']=='sign_out':
                r['delay'] = - r['delay']
            total += r['delay']
            if abs(r['delay'].seconds) < max*60:
                total2 += r['delay']

        return (self._sign(total),total2 and self._sign(total2))

report_sxw.report_sxw('report.hr.attendance.error', 'hr.employee', 'addons/hr_attendance/report/attendance_errors.rml',parser=attendance_print, header=2)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

