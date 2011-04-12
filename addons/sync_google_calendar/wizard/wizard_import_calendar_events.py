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
from tools.translate import _
import tools

import time
import datetime
import dateutil
from dateutil.tz import *
from dateutil.parser import *
from dateutil import parser
from pytz import timezone
import re
import urllib

try:
    import gdata
    import gdata.calendar.service
    import gdata.calendar
except ImportError:
    raise osv.except_osv(_('Google Contacts Import Error!'), _('Please install gdata-python-client from http://code.google.com/p/gdata-python-client/downloads/list'))

def _get_tinydates(self, stime, etime):
    stime = dateutil.parser.parse(stime)
    etime = dateutil.parser.parse(etime)
    try:
        au_dt = au_tz.normalize(stime.astimezone(au_tz))
        timestring = datetime.datetime(*au_dt.timetuple()[:6]).strftime('%Y-%m-%d %H:%M:%S')
        au_dt = au_tz.normalize(etime.astimezone(au_tz))
        timestring_end = datetime.datetime(*au_dt.timetuple()[:6]).strftime('%Y-%m-%d %H:%M:%S')
    except:
        timestring = datetime.datetime(*stime.timetuple()[:6]).strftime('%Y-%m-%d %H:%M:%S')
        timestring_end = datetime.datetime(*etime.timetuple()[:6]).strftime('%Y-%m-%d %H:%M:%S')
    return (timestring, timestring_end)

def _get_rules(self, datas):
    new_val = {}
    if  datas['FREQ'] == 'WEEKLY' and datas.get('BYDAY'):
        for day in datas['BYDAY'].split(','):
            new_val[day.lower()] = True
        datas.pop('BYDAY')

    if datas.get('UNTIL'):
        until = parser.parse(''.join((re.compile('\d')).findall(datas.get('UNTIL'))))
        new_val['end_date'] = until.strftime('%Y-%m-%d')
        new_val['end_type'] = 'end_date'
        datas.pop('UNTIL')
        
    if datas.get('COUNT'):
        new_val['count'] = datas.get('COUNT')
        new_val['end_type'] = 'count'
        datas.pop('COUNT')
        
    if datas.get('INTERVAL'):
        new_val['interval'] = datas.get('INTERVAL')
    else:
        new_val['interval'] = 1

    if datas.get('BYMONTHDAY'):
        new_val['day'] = datas.get('BYMONTHDAY')
        datas.pop('BYMONTHDAY')
        new_val['select1'] = 'date'

    if datas.get('BYDAY'):
        d = datas.get('BYDAY')
        if '-' in d:
            new_val['byday'] = d[:2]
            new_val['week_list'] = d[2:4].upper()
        else:
            new_val['byday'] = d[:1]
            new_val['week_list'] = d[1:3].upper()
        new_val['select1'] = 'day'

    if datas.get('BYMONTH'):
        new_val['month_list'] = datas.get('BYMONTH')
        datas.pop('bymonth')
    return new_val

def _get_repeat_status(self, str_google):
    rrule = str_google[str_google.find('FREQ'):str_google.find('\nBEGIN')]
    status = {}
    for rule in rrule.split(';'):
        status[rule.split('=')[0]] = rule.split('=')[-1:] and rule.split('=')[-1:][0] or ''
    rules = _get_rules(self, status)
    if status.get('FREQ') == 'WEEKLY':
        status.update({'rrule_type': 'weekly'})
        status.pop('FREQ')
    elif status.get('FREQ') == 'DAILY':
        status.update({'rrule_type': 'daily'})
        status.pop('FREQ')
    elif status.get('FREQ') == 'MONTHLY':
        status.update({'rrule_type': 'monthly'})
        status.pop('FREQ')
    elif status.get('FREQ') == 'YEARLY':
        status.update({'rrule_type': 'yearly'})
        status.pop('FREQ')
    status.update(rules)
    return status

def _get_repeat_dates(self, x):
    if len(x) > 4:
        if x[3].startswith('BY'):
            zone_time = x[4].split('+')[-1:][0].split(':')[0][:4]
        else:
            zone_time = x[3].split('+')[-1:][0].split(':')[0][:4]
    else:
        zone_time = x[2].split('+')[-1:][0].split(':')[0][:4]
    tz_format = zone_time[:2]+':'+zone_time[2:]
    repeat_start = x[1].split('\n')[0].split(':')[1]
    repeat_end = x[2].split('\n')[0].split(':')[1]
    o = repeat_start.split('T')
    repeat_start = str(o[0][:4]) + '-' + str(o[0][4:6]) + '-' + str(o[0][6:8])
    if len(o) == 2:
        repeat_start += ' ' + str(o[1][:2]) + ':' + str(o[1][2:4]) + ':' + str(o[1][4:6])
    else:
        repeat_start += ' ' + '00' + ':' + '00' + ':' + '00'
    p = repeat_end.split('T')
    repeat_end = str(p[0][:4]) + '-' + str(p[0][4:6]) + '-' + str(p[0][6:8])
    if len(p) == 2:
        repeat_end += ' ' + str(p[1][:2]) + ':' + str(p[1][2:4]) + ':' + str(p[1][4:6])
    else:
        repeat_end += ' ' + '00' + ':' + '00' + ':' + '00'
    return (repeat_start, repeat_end, tz_format)

class google_login(osv.osv_memory):
    _inherit = 'google.login'
    _name = 'google.login'

    def _get_next_action(self, cr, uid, context=None):
        data_obj = self.pool.get('ir.model.data')
        data_id = data_obj._get_id(cr, uid, 'sync_google_calendar', 'view_synchronize_google_calendar_import_form')
        view_id = False
        if data_id:
            view_id = data_obj.browse(cr, uid, data_id, context=context).res_id
        value = {
            'name': _('Import Events'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'synchronize.google.calendar',
            'view_id': False,
            'context': context,
            'views': [(view_id, 'form')],
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
        return value

google_login()

class synchronize_google_calendar_events(osv.osv_memory):
    _name = 'synchronize.google.calendar'
    
    def _get_calendars(self, cr, uid, context=None):
        user_obj = self.pool.get('res.users').browse(cr, uid, uid)
        google = self.pool.get('google.login')
        res = []
        try:
            gd_client = google.google_login(cr, uid, user_obj.gmail_user, user_obj.gmail_password, type='calendar')
            calendars = gd_client.GetAllCalendarsFeed()
            for cal in calendars.entry:
                res.append((cal.id.text, cal.title.text))
        except Exception, e:
            raise osv.except_osv('Error !', e.args[0].get('body'))
        res.append(('all','All Calendars'))
        return res
    
    _columns = {
        'calendar_name': fields.selection(_get_calendars, "Calendar Name", size=32),
    }
    
    _defaults = {
        'calendar_name': 'all',
    }
    
    def get_events(self, cr, uid, event_feed, context=None):
        meeting_obj = self.pool.get('crm.meeting')
        categ_obj = self.pool.get('crm.case.categ')
        model_obj = self.pool.get('ir.model.data')
        object_id = self.pool.get('ir.model').search(cr, uid, [('model', '=', 'crm.meeting')])
        meeting_ids = []
        categ_id = categ_obj.search(cr, uid, [('name','=',event_feed.title.text),('object_id','=',object_id and object_id[0]),('user_id','=',uid)])
        if not categ_id:
            categ_id.append(categ_obj.create(cr, uid, {'name': event_feed.title.text, 
                                                       'object_id': object_id and object_id[0],
                                                       'user_id': uid }))
        if 'tz' in context and context['tz']:
            time_zone = context['tz']
        else:
            time_zone = tools.get_server_timezone()
        au_tz = timezone(time_zone)
        
        for feed in event_feed.entry:
            google_id = feed.id.text
            model_data = {
                'name': google_id,
                'model': 'crm.meeting',
                'module': 'sync_google_calendar',
                'noupdate': True
            }
            vals = {
                'name': feed.title.text or '(No title)',
                'description': feed.content.text,
                'categ_id': categ_id and categ_id[0]
            }
            if feed.when:
                timestring, timestring_end = _get_tinydates(self, feed.when[0].start_time, feed.when[0].end_time)
            else:
                x = feed.recurrence.text.split(';')
                repeat_status = _get_repeat_status(self, feed.recurrence.text)
                repeat_start, repeat_end, zone_time = _get_repeat_dates(self, x)
                timestring = time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(repeat_start, "%Y-%m-%d %H:%M:%S"))
                timestring_end = time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(repeat_end, "%Y-%m-%d %H:%M:%S"))
                if repeat_status:
                    repeat_status.update({'recurrency': True})
                    vals.update(repeat_status)

            vals.update({'date': timestring, 'date_deadline': timestring_end})
            data_ids = model_obj.search(cr, uid, [('model','=','crm.meeting'), ('name','=',google_id)])
            if data_ids:
                res_id = model_obj.browse(cr, uid, data_ids[0], context=context).res_id
                meeting = meeting_obj.browse(cr, uid, res_id, context=context)
                google_updated = feed.updated.text
                utime = dateutil.parser.parse(google_updated)
                au_dt = au_tz.normalize(utime.astimezone(au_tz))
                updated_dt = datetime.datetime(*au_dt.timetuple()[:6]).strftime('%Y-%m-%d %H:%M:%S')
                if meeting.write_date < updated_dt:
                    meeting_ids.append(res_id)
                    meeting_obj.write(cr, uid, [res_id], vals, context=context)
            else:
                res_id = meeting_obj.create(cr, uid, vals, context=context)
                meeting_ids.append(res_id)
                model_data.update({'res_id': res_id})
                model_obj.create(cr, uid, model_data, context=context)
        return meeting_ids
    
    def import_calendar_events(self, cr, uid, ids, context=None):
        obj = self.browse(cr, uid, ids, context=context)[0]
        if not ids:
            return { 'type': 'ir.actions.act_window_close' }

        user_obj = self.pool.get('res.users').browse(cr, uid, uid)
        gmail_user = user_obj.gmail_user
        gamil_pwd = user_obj.gmail_password
        
        google = self.pool.get('google.login')
        gd_client = google.google_login(cr, uid, gmail_user, gamil_pwd, type='calendar')

        if not gmail_user or not gamil_pwd:
            raise osv.except_osv(_('Error'), _("Please specify the user and password !"))
        
        meetings = []
        if obj.calendar_name != 'all':
            events_query = gdata.calendar.service.CalendarEventQuery(user=urllib.unquote(obj.calendar_name.split('/')[~0]))
            events_query.start_index = 1
            events_query.max_results = 1000
            event_feed = gd_client.GetCalendarEventFeed(events_query.ToUri())
            meetings.append(self.get_events(cr, uid, event_feed, context=context))
        else:
            calendars = map(lambda x:x[0], [cal for cal in self._get_calendars(cr, uid, context) if cal[0] != 'all'])
            for cal in calendars:
                events_query = gdata.calendar.service.CalendarEventQuery(user=urllib.unquote(cal.split('/')[~0]))
                events_query.start_index = 1
                events_query.max_results = 1000
                event_feed = gd_client.GetCalendarEventFeed(events_query.ToUri())
                meetings.append(self.get_events(cr, uid, event_feed, context=context))
        
        meeting_ids = []
        for meeting in meetings:
            meeting_ids += meeting
        
        return {
            'name': _('Meetings'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'crm.meeting',
            'context': context,
            'views': [(False, 'calendar'),(False, 'tree'),(False, 'form')],
            'type': 'ir.actions.act_window',
        }
        
synchronize_google_calendar_events()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

