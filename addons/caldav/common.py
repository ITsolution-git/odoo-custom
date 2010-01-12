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
from osv import fields, osv
from service import web_services
from tools.translate import _
import re
import time

months = {
        1:"January", 2:"February", 3:"March", 4:"April", \
        5:"May", 6:"June", 7:"July", 8:"August", 9:"September", \
        10:"October", 11:"November", 12:"December"}

def caldav_id2real_id(caldav_id = None, with_date=False):
    if caldav_id and isinstance(caldav_id, (str, unicode)):
        res = caldav_id.split('-')
        if len(res) >= 2:
            real_id = res[0]
            if with_date:
                real_date = time.strftime("%Y-%m-%d %H:%M:%S", \
                                 time.strptime(res[1], "%Y%m%d%H%M%S"))
                return (int(real_id), real_date)
            return int(real_id)
    return caldav_id and int(caldav_id) or caldav_id

def real_id2caldav_id(real_id, recurrent_date):
    if real_id and recurrent_date:
        recurrent_date = time.strftime("%Y%m%d%H%M%S", \
                         time.strptime(recurrent_date, "%Y-%m-%d %H:%M:%S"))
        return '%d-%s'%(real_id, recurrent_date)
    return real_id

def uid2openobjectid(cr, uidval, oomodel):
    __rege = re.compile(r'OpenObject-([\w|\.]+)_([0-9]+)@(\w+)$')
    wematch = __rege.match(uidval.encode('utf8'))
    if not wematch:
        return False
    else:
        model, id, dbname = wematch.groups()
        if (not model == oomodel) or (not dbname == cr.dbname):
            return False
        cr.execute('select distinct(id) from %s' % model.replace('.', '_'))
        ids = map(lambda x: str(x[0]), cr.fetchall())
        if id in ids:
            return id
        return False

def openobjectid2uid(cr, uidval, oomodel):
    value = 'OpenObject-%s_%s@%s' % (oomodel, uidval, cr.dbname)
    return value

def _links_get(self, cr, uid, context={}):
    obj = self.pool.get('res.request.link')
    ids = obj.search(cr, uid, [])
    res = obj.read(cr, uid, ids, ['object', 'name'], context)
    return [(r['object'], r['name']) for r in res]

class calendar_attendee(osv.osv):
    _name = 'calendar.attendee'
    _description = 'Attendee information'
    _rec_name = 'cutype'

    __attribute__ = {
        'cutype': {'field':'cutype', 'type':'text'}, 
        'member': {'field':'member', 'type':'text'}, 
        'role': {'field':'role', 'type':'selection'}, 
        'partstat': {'field':'state', 'type':'text'}, 
        'rsvp': {'field':'rsvp', 'type':'boolean'}, 
        'delegated-to': {'field':'delegated_to', 'type':'text'}, 
        'delegated-from': {'field':'delegated_from', 'type':'text'}, 
        'sent-by': {'field':'sent_by', 'type':'text'}, 
        'cn': {'field':'cn', 'type':'text'}, 
        'dir': {'field':'dir', 'type':'text'}, 
        'language': {'field':'language', 'type':'text'}, 
    }

    def _get_address(self, name=None, email=None):
        if name and email:
            name += ':'
        return (name or '') + (email and ('MAILTO:' + email) or '')

    def _compute_data(self, cr, uid, ids, name, arg, context):
        name = name[0]
        result = {}

        def get_delegate_data(user):
            email = user.address_id and user.address_id.email or ''
            return self._get_address(user.name, email)

        for attdata in self.browse(cr, uid, ids, context=context):
            id = attdata.id
            result[id] = {}
            if name == 'sent_by':
                if not attdata.sent_by_uid:
                    result[id][name] = ''
                    continue
                else:
                    result[id][name] =  self._get_address(attdata.sent_by_uid.name, \
                                        attdata.sent_by_uid.address_id.email)
            if name == 'cn':
                if attdata.user_id:
                    result[id][name] = self._get_address(attdata.user_id.name, attdata.email)
                elif attdata.partner_address_id:
                    result[id][name] = self._get_address(attdata.partner_id.name, attdata.email)
                else:
                    result[id][name] = self._get_address(None, attdata.email)
            if name == 'delegated_to':
                user_obj = self.pool.get('res.users')
                todata = map(get_delegate_data, attdata.del_to_user_ids)
                result[id][name] = ', '.join(todata)
            if name == 'delegated_from':
                dstring = []
                user_obj = self.pool.get('res.users')
                fromdata = map(get_delegate_data, attdata.del_from_user_ids)
                result[id][name] = ', '.join(fromdata)
            if name == 'event_date':
                if attdata.ref:
                    model, res_id = tuple(attdata.ref.split(','))
                    model_obj = self.pool.get(model)
                    obj = model_obj.read(cr, uid, res_id, ['date'])[0]
                    result[id][name] = obj['date']
            if name == 'event_end_date':
                if attdata.ref:
                    model, res_id = tuple(attdata.ref.split(','))
                    model_obj = self.pool.get(model)
                    obj = model_obj.read(cr, uid, res_id, ['date_deadline'])[0]
                    result[id][name] = obj['date_deadline']

            if name == 'sent_by_uid':
                if attdata.ref:
                    model, res_id = tuple(attdata.ref.split(','))
                    model_obj = self.pool.get(model)
                    obj = model_obj.read(cr, uid, res_id, ['user_id'])[0]
                    result[id][name] = obj['user_id']
        return result

    def _links_get(self, cr, uid, context={}):
        obj = self.pool.get('res.request.link')
        ids = obj.search(cr, uid, [])
        res = obj.read(cr, uid, ids, ['object', 'name'], context)
        return [(r['object'], r['name']) for r in res]

    def _lang_get(self, cr, uid, context={}):
        obj = self.pool.get('res.lang')
        ids = obj.search(cr, uid, [])
        res = obj.read(cr, uid, ids, ['code', 'name'], context)
        res = [((r['code']).replace('_', '-'), r['name']) for r in res]
        return res

    _columns = {
        'cutype': fields.selection([('individual', 'Individual'), \
                    ('group', 'Group'), ('resource', 'Resource'), \
                    ('room', 'Room'), ('unknown', 'Unknown') ], \
                    'User Type', help="Specify the type of calendar user"), 
        'member': fields.char('Member', size=124, 
                    help="Indicate the groups that the attendee belongs to"), 
        'role': fields.selection([('req-participant', 'Participation required'), \
                    ('chair', 'Chair Person'), \
                    ('opt-participant', 'Optional Participation'), \
                    ('non-participant', 'For information Purpose')], 'Role', \
                    help='Participation role for the calendar user'), 
        'state': fields.selection([('tentative', 'Tentative'), 
                        ('needs-action', 'Needs Action'), 
                        ('accepted', 'Accepted'), 
                        ('declined', 'Declined'), 
                        ('delegated', 'Delegated')], 'State', readonly=True, 
                        help="Status of the attendee's participation"), 
        'rsvp':  fields.boolean('Required Reply?', 
                    help="Indicats whether the favor of a reply is requested"), 
        'delegated_to': fields.function(_compute_data, method=True, \
                string='Delegated To', type="char", size=124, store=True, \
                multi='delegated_to', help="The users that the original \
request was delegated to"), 
        'del_to_user_ids': fields.many2many('res.users', 'att_del_to_user_rel', 
                                  'attendee_id', 'user_id', 'Users'), 
        'delegated_from': fields.function(_compute_data, method=True, string=\
            'Delegated From', type="char", store=True, size=124, multi='delegated_from'), 
        'del_from_user_ids': fields.many2many('res.users', 'att_del_from_user_rel', \
                                      'attendee_id', 'user_id', 'Users'), 
        'sent_by': fields.function(_compute_data, method=True, string='Sent By', type="char", multi='sent_by', store=True, size=124, help="Specify the user that is acting on behalf of the calendar user"), 
        'sent_by_uid': fields.many2one('res.users', 'Sent by User'), 
        'cn': fields.function(_compute_data, method=True, string='Common name', type="char", size=124, multi='cn', store=True), 
        'dir': fields.char('URI Reference', size=124, help="Reference to the URI that points to the directory information corresponding to the attendee."), 
        'language': fields.selection(_lang_get, 'Language', 
                                  help="To specify the language for text values in a property or property parameter."), 
        'user_id': fields.many2one('res.users', 'User'), 
        'partner_address_id': fields.many2one('res.partner.address', 'Contact'), 
        'partner_id':fields.related('partner_address_id', 'partner_id', type='many2one', relation='res.partner', string='Partner'), 
        'email': fields.char('Email', size=124), 
        'event_date' : fields.function(_compute_data, method=True, string='Event Date', type="datetime", multi='event_date'), 
        'event_end_date' : fields.function(_compute_data, method=True, string='Event End Date', type="datetime", multi='event_end_date'), 
        'ref': fields.reference('Document Ref', selection=_links_get, size=128), 
        'availability': fields.selection([('free', 'Free'), ('busy', 'Busy')], 'Free/Busy', readonly="True"), 
     }
    _defaults = {
        'state':  lambda *x: 'needs-action', 
    }

    def onchange_user_id(self, cr, uid, ids, user_id, *args, **argv):
        if not user_id:
            return {'value': {'email': ''}}
        usr_obj = self.pool.get('res.users')
        user = usr_obj.browse(cr, uid, user_id, *args)
        return {'value': {'email': user.address_id.email, 'availability':user.availability}}

    def do_tentative(self, cr, uid, ids, context=None, *args):
        self.write(cr, uid, ids, {'state': 'tentative'}, context)

    def do_accept(self, cr, uid, ids, context=None, *args):
        self.write(cr, uid, ids, {'state': 'accepted'}, context)

    def do_decline(self, cr, uid, ids, context=None, *args):
        self.write(cr, uid, ids, {'state': 'declined'}, context)

calendar_attendee()

class res_alarm(osv.osv):
    _name = 'res.alarm'
    _description = 'basic alarm information'
    _columns = {
        'name':fields.char('Name', size=256, required=True), 
        'trigger_occurs': fields.selection([('before', 'Before'), ('after', 'After')], \
                                        'Triggers', required=True), 
        'trigger_interval': fields.selection([('minutes', 'Minutes'), ('hours', 'Hours'), \
                ('days', 'Days')], 'Interval', required=True), 
        'trigger_duration':  fields.integer('Duration', required=True), 
        'trigger_related':  fields.selection([('start', 'The event starts'), ('end', \
                                       'The event ends')], 'Related to', required=True), 
        'duration': fields.integer('Duration', help="""Duration' and 'Repeat' \
are both optional, but if one occurs, so MUST the other"""), 
        'repeat': fields.integer('Repeat'), 
        'active': fields.boolean('Active', help="If the active field is set to true, it will allow you to hide the event alarm information without removing it."), 


    }
    _defaults = {
        'trigger_interval':  lambda *x: 'minutes', 
        'trigger_duration': lambda *x: 5, 
        'trigger_occurs': lambda *x: 'before', 
        'trigger_related': lambda *x: 'start', 
        'active': lambda *x: 1, 
    }

res_alarm()

class calendar_alarm(osv.osv):
    _name = 'calendar.alarm'
    _description = 'Event alarm information'
    _inherits = {'res.alarm': "alarm_id"}
    __attribute__ = {
            'action': {'field': 'action', 'type': 'text'}, 
            'description': {'field': 'name', 'type': 'text'}, 
            'summary': {'field': 'description', 'type': 'text'}, 
            'attendee': {'field': 'attendee_ids', 'type': 'text'}, 
            'trigger_related': {'field': 'trigger_related', 'type': 'text'}, 
            'trigger_duration': {'field': 'trigger_duration', 'type': 'text'}, 
            'trigger_occurs': {'field': 'trigger_occurs', 'type': 'text'}, 
            'trigger_interval': {'field': 'trigger_interval', 'type': 'text'}, 
            'duration': {'field': 'duration', 'type': 'text'}, 
            'repeat': {'field': 'repeat', 'type': 'text'}, 
            'attach': {'field': 'attach', 'type': 'text'}, 
    }

    _columns = {
            'alarm_id': fields.many2one('res.alarm', 'Basic Alarm', ondelete='cascade'), 
            'name': fields.char('Summary', size=124, help="""Contains the text to be used as the message subject for email
or contains the text to be used for display"""), 
            'action': fields.selection([('audio', 'Audio'), ('display', 'Display'), \
                    ('procedure', 'Procedure'), ('email', 'Email') ], 'Action', \
                    required=True, help="Defines the action to be invoked when an alarm is triggered"), 
            'description': fields.text('Description', help='Provides a more complete description of the calendar component, than that provided by the "SUMMARY" property'), 
            'attendee_ids': fields.many2many('calendar.attendee', 'alarm_attendee_rel', \
                                          'alarm_id', 'attendee_id', 'Attendees', readonly=True), 
            'attach': fields.binary('Attachment', help="""* Points to a sound resource, which is rendered when the alarm is triggered for audio,
* File which is intended to be sent as message attachments for email,
* Points to a procedure resource, which is invoked when the alarm is triggered for procedure."""), 
            'res_id' : fields.integer('Resource ID'), 
            'model_id': fields.many2one('ir.model', 'Model'), 
            'user_id': fields.many2one('res.users', 'Owner'), 
            'event_date' : fields.datetime('Event Date'), 
            'event_end_date' : fields.datetime('Event End Date'), 
            'trigger_date' : fields.datetime('Trigger Date', readonly="True"), 
            'state':fields.selection([
                        ('draft', 'Draft'), 
                        ('run', 'Run'), 
                        ('stop', 'Stop'), 
                        ('done', 'Done'), 
                    ], 'State', select=True, readonly=True), 
     }

    _defaults = {
        'action':  lambda *x: 'email', 
        'state' : lambda *x: 'run', 
     }

    def create(self, cr, uid, vals, context={}):
        event_date = vals.get('event_date', False)
        if event_date:
            dtstart = datetime.strptime(vals['event_date'], "%Y-%m-%d %H:%M:%S")
            if vals['trigger_interval'] == 'days':
                delta = datetime.timedelta(days=vals['trigger_duration'])
            if vals['trigger_interval'] == 'hours':
                delta = datetime.timedelta(hours=vals['trigger_duration'])
            if vals['trigger_interval'] == 'minutes':
                delta = datetime.timedelta(minutes=vals['trigger_duration'])
            trigger_date =  dtstart + (vals['trigger_occurs'] == 'after' and delta or -delta)
            vals['trigger_date'] = trigger_date
        res = super(calendar_alarm, self).create(cr, uid, vals, context)
        return res

    def do_run_scheduler(self, cr, uid, automatic=False, use_new_cursor=False, \
                       context=None):
        if not context:
            context = {}
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cr.execute("select alarm.id as id \
                    from calendar_alarm alarm \
                    where alarm.state = %s and alarm.trigger_date <= %s", ('run', current_datetime))
        res = cr.dictfetchall()
        alarm_ids = map(lambda x: x['id'], res)
        attendee_obj = self.pool.get('calendar.attendee')
        request_obj = self.pool.get('res.request')
        mail_to = []
        for alarm in self.browse(cr, uid, alarm_ids):
            if alarm.action == 'display':
                value = {
                   'name': alarm.name, 
                   'act_from': alarm.user_id.id, 
                   'act_to': alarm.user_id.id, 
                   'body': alarm.description, 
                   'trigger_date': alarm.trigger_date, 
                   'ref_doc1' :  '%s,%s' %(alarm.model_id.model, alarm.res_id)
                }
                request_id = request_obj.create(cr, uid, value)
                request_ids = [request_id]
                for attendee in alarm.attendee_ids:
                    value['act_to'] = attendee.user_id.id
                    request_id = request_obj.create(cr, uid, value)
                    request_ids.append(request_id)
                request_obj.request_send(cr, uid, request_ids)

            if alarm.action == 'email':
                sub = '[Openobject Remainder] %s' %(alarm.name)
                body = """
                Name : %s
                Date : %s
                Description : %s

                From :
                      %s
                      %s

                """ %(alarm.name, alarm.trigger_date, alarm.description, \
                    alarm.user_id.name, alarm.user_id.sign)
                mail_to = [alarm.user_id.address_id.email]
                for att in alarm.attendee_ids:
                    mail_to.append(att.user_id.address_id.email)

                tools.email_send(
                    tools.confirm['from_mail'], 
                    mail_to, 
                    sub, 
                    body
                )
            self.write(cr, uid, [alarm.id], {'state':'done'})
        return True

calendar_alarm()

class ir_attachment(osv.osv):
    _name = 'ir.attachment'
    _inherit = 'ir.attachment'

    def search_count(self, cr, user, args, context=None):
        args1 = []
        for arg in args:
            args1.append(map(lambda x:str(x).split('-')[0], arg))
        return super(ir_attachment, self).search_count(cr, user, args1, context)

    def search(self, cr, uid, args, offset=0, limit=None, order=None, 
            context=None, count=False):
        new_args = args
        for i, arg in enumerate(new_args):
            if arg[0] == 'res_id':
                new_args[i] = (arg[0], arg[1], caldav_id2real_id(arg[2]))
        return super(ir_attachment, self).search(cr, uid, new_args, offset=offset, 
                            limit=limit, order=order, 
                            context=context, count=False)
ir_attachment()

class ir_values(osv.osv):
    _inherit = 'ir.values'

    def set(self, cr, uid, key, key2, name, models, value, replace=True, \
            isobject=False, meta=False, preserve_user=False, company=False):
        new_model = []
        for data in models:
            if type(data) in (list, tuple):
                new_model.append((data[0], caldav_id2real_id(data[1])))
            else:
                new_model.append(data)
        return super(ir_values, self).set(cr, uid, key, key2, name, new_model,\
                    value, replace, isobject, meta, preserve_user, company)

    def get(self, cr, uid, key, key2, models, meta=False, context={},\
             res_id_req=False, without_user=True, key2_req=True):
        new_model = []
        for data in models:
            if type(data) in (list, tuple):
                new_model.append((data[0], caldav_id2real_id(data[1])))
            else:
                new_model.append(data)
        return super(ir_values, self).get(cr, uid, key, key2, new_model, \
                         meta, context, res_id_req, without_user, key2_req)

ir_values()

class ir_model(osv.osv):

    _inherit = 'ir.model'

    def read(self, cr, uid, ids, fields=None, context={}, 
            load='_classic_read'):
        data = super(ir_model, self).read(cr, uid, ids, fields=fields, \
                        context=context, load=load)
        if data:
            for val in data:
                val['id'] = caldav_id2real_id(val['id'])
        return data

ir_model()

class virtual_report_spool(web_services.report_spool):

    def exp_report(self, db, uid, object, ids, datas=None, context=None):
        if object == 'printscreen.list':
            return super(virtual_report_spool, self).exp_report(db, uid, \
                            object, ids, datas, context)
        new_ids = []
        for id in ids:
            new_ids.append(caldav_id2real_id(id))
        datas['id'] = caldav_id2real_id(datas['id'])
        super(virtual_report_spool, self).exp_report(db, uid, object, new_ids, datas, context)
        return super(virtual_report_spool, self).exp_report(db, uid, object, new_ids, datas, context)

virtual_report_spool()

class calendar_custom_rrule(osv.osv):
    _name = "calendar.custom.rrule"
    _description = "Custom Recurrency Rule"

    _columns = {
        'freq': fields.selection([('None', 'No Repeat'), \
                            ('secondly', 'Secondly'), \
                            ('minutely', 'Minutely'), \
                            ('hourly', 'Hourly'), \
                            ('daily', 'Daily'), \
                            ('weekly', 'Weekly'), \
                            ('monthly', 'Monthly'), \
                            ('yearly', 'Yearly')], 'Frequency', required=True), 
        'interval': fields.integer('Interval'), 
        'count': fields.integer('Count'), 
        'mo': fields.boolean('Mon'), 
        'tu': fields.boolean('Tue'), 
        'we': fields.boolean('Wed'), 
        'th': fields.boolean('Thu'), 
        'fr': fields.boolean('Fri'), 
        'sa': fields.boolean('Sat'), 
        'su': fields.boolean('Sun'), 
        'select1': fields.selection([('date', 'Date of month'), \
                            ('day', 'Day of month')], 'Option'), 
        'day': fields.integer('Date of month'), 
        'week_list': fields.selection([('MO', 'Monday'), ('TU', 'Tuesday'), \
                                   ('WE', 'Wednesday'), ('TH', 'Thursday'), \
                                   ('FR', 'Friday'), ('SA', 'Saturday'), \
                                   ('SU', 'Sunday')], 'Weekday'), 
        'byday': fields.selection([('1', 'First'), ('2', 'Second'), \
                                   ('3', 'Third'), ('4', 'Fourth'), \
                                   ('5', 'Fifth'), ('-1', 'Last')], 'By day'), 
        'month_list': fields.selection(months.items(), 'Month'), 
        'end_date': fields.date('Repeat Until')
    }

    _defaults = {
                 'freq':  lambda *x: 'daily', 
                 'select1':  lambda *x: 'date', 
                 'interval':  lambda *x: 1, 
                 }

    def compute_rule_string(self, cr, uid, datas, context=None, *args):
        weekdays = ['mo', 'tu', 'we', 'th', 'fr', 'sa', 'su']
        weekstring = ''
        monthstring = ''
        yearstring = ''

#    logic for computing rrule string

        freq = datas.get('freq')
        if freq == 'None':
            obj.write(cr, uid, [res_obj.id], {'rrule' : ''})
            return {}

        if freq == 'weekly':
            byday = map(lambda x: x.upper(), filter(lambda x: datas.get(x) and x in weekdays, datas))
            if byday:
                weekstring = ';BYDAY=' + ','.join(byday)

        elif freq == 'monthly':
            if datas.get('select1')=='date' and (datas.get('day') < 1 or datas.get('day') > 31):
                raise osv.except_osv(_('Error!'), ("Please select proper Day of month"))
            if datas.get('select1')=='day':
                monthstring = ';BYDAY=' + datas.get('byday') + datas.get('week_list')
            elif datas.get('select1')=='date':
                monthstring = ';BYMONTHDAY=' + str(datas.get('day'))

        elif freq == 'yearly':
            if datas.get('select1')=='date'  and (datas.get('day') < 1 or datas.get('day') > 31):
                raise osv.except_osv(_('Error!'), ("Please select proper Day of month"))
            bymonth = ';BYMONTH=' + str(datas.get('month_list'))
            if datas.get('select1')=='day':
                bystring = ';BYDAY=' + datas.get('byday') + datas.get('week_list')
            elif datas.get('select1')=='date':
                bystring = ';BYMONTHDAY=' + str(datas.get('day'))
            yearstring = bymonth + bystring

        if datas.get('end_date'):
            datas['end_date'] = ''.join((re.compile('\d')).findall(datas.get('end_date'))) + '235959Z'
        enddate = (datas.get('count') and (';COUNT=' +  str(datas.get('count'))) or '') +\
                             ((datas.get('end_date') and (';UNTIL=' + datas.get('end_date'))) or '')

        rrule_string = 'FREQ=' + freq.upper() +  weekstring + ';INTERVAL=' + \
                str(datas.get('interval')) + enddate + monthstring + yearstring

#        End logic
        return rrule_string

    def do_add(self, cr, uid, ids, context={}):
        datas = self.read(cr, uid, ids)[0]
        if datas.get('interval') <= 0:
            raise osv.except_osv(_('Error!'), ("Please select proper Interval"))


        if not context or not context.get('model'):
            return {}
        else:
            model = context.get('model')
        obj = self.pool.get(model)
        res_obj = obj.browse(cr, uid, context['active_id'])

        rrule_string = self.compute_rule_string(cr, uid, datas)
        obj.write(cr, uid, [res_obj.id], {'rrule' : rrule_string})
        return {}

calendar_custom_rrule()

class res_users(osv.osv):
    _inherit = 'res.users'

    def _get_user_avail(self, cr, uid, ids, context=None):
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        res = {}
        attendee_obj = self.pool.get('calendar.attendee')
        attendee_ids = attendee_obj.search(cr, uid, [
                    ('event_date', '<=', current_datetime), ('event_end_date', '<=', current_datetime), 
                    ('state', '=', 'accepted'), ('user_id', 'in', ids)
                    ])

        result = cr.dictfetchall()
        for attendee_data in attendee_obj.read(cr, uid, attendee_ids, ['user_id']):
            user_id = attendee_data['user_id']
            status = 'busy'
            res.update({user_id:status})

        #TOCHECK : Delegrated Event
        #cr.execute("SELECT user_id,'busy' FROM att_del_to_user_rel where user_id = ANY(%s)", (ids,))
        #res.update(cr.dictfetchall())
        for user_id in ids:
            if user_id not in res:
                res[user_id] = 'free'

        return res

    def _get_user_avail_fun(self, cr, uid, ids, name, args, context=None):
        return self._get_user_avail(cr, uid, ids, context=context)

    _columns = {
            'availability': fields.function(_get_user_avail_fun, type='selection', \
                    selection=[('free', 'Free'), ('busy', 'Busy')], \
                    string='Free/Busy', method=True), 
    }
res_users()

class invite_attendee_wizard(osv.osv_memory):
    _name = "caldav.invite.attendee"
    _description = "Invite Attendees"

    _columns = {
        'type': fields.selection([('internal', 'Internal User'), \
              ('external', 'External Email'), \
              ('partner', 'Partner Contacts')], 'Type', required=True), 
        'user_ids': fields.many2many('res.users', 'invite_user_rel', 
                                  'invite_id', 'user_id', 'Users'), 
        'partner_id': fields.many2one('res.partner', 'Partner'), 
        'email': fields.char('Email', size=124), 
        'contact_ids': fields.many2many('res.partner.address', 'invite_contact_rel', 
                                  'invite_id', 'contact_id', 'Contacts'), 
              }

    def do_invite(self, cr, uid, ids, context={}):
        datas = self.read(cr, uid, ids)[0]
        if not context or not context.get('model'):
            return {}
        else:
            model = context.get('model')
        obj = self.pool.get(model)
        res_obj = obj.browse(cr, uid, context['active_id'])
        type = datas.get('type')
        att_obj = self.pool.get('calendar.attendee')
        vals = {'ref': '%s,%s'%(model, caldav_id2real_id(context['active_id']))}
        if type == 'internal':
            user_obj = self.pool.get('res.users')
            for user_id in datas.get('user_ids', []):
                user = user_obj.browse(cr, uid, user_id)
                if not user.address_id.email:
                    raise osv.except_osv(_('Error!'), \
                                    ("User does not have an email Address"))
                vals.update({'user_id': user_id, 
                                     'email': user.address_id.email})
                att_id = att_obj.create(cr, uid, vals)
                obj.write(cr, uid, res_obj.id, {'attendee_ids': [(4, att_id)]})

        elif  type == 'external' and datas.get('email'):
            vals.update({'email': datas['email']})
            att_id = att_obj.create(cr, uid, vals)
            obj.write(cr, uid, res_obj.id, {'attendee_ids': [(4, att_id)]})

        elif  type == 'partner':
            add_obj = self.pool.get('res.partner.address')
            for contact in  add_obj.browse(cr, uid, datas['contact_ids']):
                vals.update({
                             'partner_address_id': contact.id, 
                             'email': contact.email})
                att_id = att_obj.create(cr, uid, vals)
                obj.write(cr, uid, res_obj.id, {'attendee_ids': [(4, att_id)]})
        return {}


    def onchange_partner_id(self, cr, uid, ids, partner_id, *args, **argv):
        if not partner_id:
            return {'value': {'contact_ids': []}}
        cr.execute('select id from res_partner_address \
                         where partner_id=%s' % (partner_id))
        contacts = map(lambda x: x[0], cr.fetchall())
        if not contacts:
            raise osv.except_osv(_('Error!'), \
                                ("Partner does not have any Contacts"))

        return {'value': {'contact_ids': contacts}}

invite_attendee_wizard()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
