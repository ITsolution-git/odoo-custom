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

from crm import crm
from osv import fields, osv
from tools.translate import _
import decimal_precision as dp
from crm import wizard
import time


wizard.mail_compose_message.SUPPORTED_MODELS.append('event.registration')

class event_type(osv.osv):
    """ Event Type """
    _name = 'event.type'
    _description = __doc__
    _columns = {
        'name': fields.char('Event type', size=64, required=True),
        'default_reply_to': fields.char('Default Reply-To', size=64,help="The email address of the organizer which is put in the 'Reply-To' of all emails sent automatically at event or registrations confirmation. You can also put your email address of your mail gateway if you use one." ),
        'default_email_event': fields.many2one('email.template','Event Confirmation Email', help="It will select this default confirmation event mail value when you choose this event"),
        'default_email_registration': fields.many2one('email.template','Registration Confirmation Email', help="It will select this default confirmation registration mail value when you choose this event"),
        'default_registration_min': fields.integer('Default Minimum Registration', help="It will select this default minimum value when you choose this event"),
        'default_registration_max': fields.integer('Default Maximum Registration', help="It will select this default maximum value when you choose this event"),
    }
    _defaults = {
        'default_registration_min': 0,
        'default_registration_max':0,
        }

event_type()

class event_event(osv.osv):
    """Event"""
    _name = 'event.event'
    _description = __doc__
    _order = 'date_begin'

    def name_get(self, cr, uid, ids, context=None):
        if not ids:
              return []
        res = []
        for record in self.browse(cr, uid, ids, context=context):
            date = record.date_begin.split(" ")
            date = date[0]
            registers=''
            if record.register_max !=0:
                register_max = str(record.register_max)
                register_tot = record.register_current+record.register_prospect
                register_tot = str(register_tot)
                registers = register_tot+'/'+register_max
            name = record.name+' ('+date+') '+registers
            res.append((record['id'], name))
        return res

    def _name_get_fnc(self, cr, uid, ids,prop,unknow, context=None):
        res = self.name_get(cr, uid, ids, context=context)
        return dict(res)

    def copy(self, cr, uid, id, default=None, context=None):
        """ Reset the state and the registrations while copying an event
        """
        if not default:
            default = {}
        default.update({
            'state': 'draft',
            'registration_ids': False,
        })
        return super(event_event, self).copy(cr, uid, id, default=default, context=context)

    def button_draft(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'draft'}, context=context)

    def button_cancel(self, cr, uid, ids, context=None):
        registration = self.pool.get('event.registration')
        reg_ids = registration.search(cr, uid, [('event_id','in',ids)], context=context)
        for event_reg in registration.browse(cr,uid,reg_ids,context=context):
            if event_reg.state == 'done':
                raise osv.except_osv(_('Error!'),_("You have already set a registration for this event as 'Attended'. Please reset it to draft if you want to cancel this event.") )
        registration.write(cr, uid, reg_ids, {'state': 'cancel'}, context=context)
        return self.write(cr, uid, ids, {'state': 'cancel'}, context=context)

    def button_done(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'done'}, context=context)

    def button_confirm(self, cr, uid, ids, context=None):
        """ Confirm Event and send confirmation email to all register peoples
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        #renforcing method : create a list of ids
        register_pool = self.pool.get('event.registration')
        for event in self.browse(cr, uid, ids, context=context):
            total_confirmed = event.register_current
            if total_confirmed < event.register_min or total_confirmed > event.register_max and event.register_max!=0:
                raise osv.except_osv(_('Error!'),_("The total of confirmed registration for the event '%s' does not meet the expected minimum/maximum. You should maybe reconsider those limits before going further") % (event.name))
            if event.email_confirmation_id:
                #send reminder that will confirm the event for all the people that were already confirmed
                reg_ids = register_pool.search(cr, uid, [
                               ('event_id', '=', event.id),
                               ('state', 'not in', ['draft', 'cancel'])], context=context)
                register_pool.mail_user_confirm(cr, uid, reg_ids)
        return self.write(cr, uid, ids, {'state': 'confirm'}, context=context)

    def _get_register(self, cr, uid, ids, fields, args, context=None):
        """Get Confirm or uncofirm register value.
        @param ids: List of Event registration type's id
        @param fields: List of function fields(register_current and register_prospect).
        @param context: A standard dictionary for contextual values
        @return: Dictionary of function fields value.
        """
        register_pool = self.pool.get('event.registration')
        res = {}
        for event in self.browse(cr, uid, ids, context=context):
            res[event.id] = {}
            reg_open = reg_done = reg_draft =0
            for registration in event.registration_ids:
                if registration.state == 'open':
                    reg_open += registration.nb_register
                elif registration.state == 'done':
                    reg_done += registration.nb_register
                elif registration.state == 'draft':
                    reg_draft += registration.nb_register
            for field in fields:
                number = 0
                if field == 'register_current':
                    number = reg_open
                elif field == 'register_attended':
                    number = reg_done
                elif field == 'register_prospect':
                    number = reg_draft
                res[event.id][field] = number
        return res

    _columns = {
        'name': fields.char('Name', size=64, required=True, translate=True, readonly=False, states={'done': [('readonly', True)]}),
        'user_id': fields.many2one('res.users', 'Responsible User', readonly=False, states={'done': [('readonly', True)]}),
        'type': fields.many2one('event.type', 'Type of Event', readonly=False, states={'done': [('readonly', True)]}),
        'register_max': fields.integer('Maximum Registrations', help="You can for each event define a maximum registration level. If you have too much registrations you are not able to confirm your event. (put 0 to ignore this rule )", readonly=True, states={'draft': [('readonly', False)]}),
        'register_min': fields.integer('Minimum Registrations', help="You can for each event define a minimum registration level. If you do not enough registrations you are not able to confirm your event. (put 0 to ignore this rule )", readonly=True, states={'draft': [('readonly', False)]}),
        'register_current': fields.function(_get_register, string='Confirmed Registrations', multi='register_numbers'),
        'register_prospect': fields.function(_get_register, string='Unconfirmed Registrations', multi='register_numbers'),
        'register_attended': fields.function(_get_register, string='Attended Registrations', multi='register_numbers'), 
        'registration_ids': fields.one2many('event.registration', 'event_id', 'Registrations', readonly=False, states={'done': [('readonly', True)]}),
        'date_begin': fields.datetime('Starting Date', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'date_end': fields.datetime('Closing Date', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'state': fields.selection([
            ('draft', 'Draft'),
            ('confirm', 'Confirmed'),
            ('done', 'Done'),
            ('cancel', 'Cancelled')],
            'State', readonly=True, required=True,
            help='If event is created, the state is \'Draft\'.If event is confirmed for the particular dates the state is set to \'Confirmed\'. If the event is over, the state is set to \'Done\'.If event is cancelled the state is set to \'Cancelled\'.'),
        'email_registration_id' : fields.many2one('email.template','Registration Confirmation Email'),
        'email_confirmation_id' : fields.many2one('email.template','Event Confirmation Email', help="If you set an email template, each participant will receive this email announcing the confirmation of the event."),
        'full_name' : fields.function(_name_get_fnc, type="char", string='Name'),
        'reply_to': fields.char('Reply-To Email', size=64, readonly=False, states={'done': [('readonly', True)]}, help="The email address of the organizer is likely to be put here, with the effect to be in the 'Reply-To' of the mails sent automatically at event or registrations confirmation. You can also put the email address of your mail gateway if you use one."),
        'main_speaker_id': fields.many2one('res.partner','Main Speaker', readonly=False, states={'done': [('readonly', True)]}, help="Speaker who will be giving speech at the event."),
        'speaker_ids': fields.many2many('res.partner', 'event_speaker_rel', 'speaker_id', 'partner_id', 'Other Speakers', readonly=False, states={'done': [('readonly', True)]}),
        'address_id': fields.many2one('res.partner.address','Location Address', readonly=False, states={'done': [('readonly', True)]}),
        'speaker_confirmed': fields.boolean('Speaker Confirmed',help='You can choose this checkbox for your information => ca veut rien dire ca', readonly=False, states={'done': [('readonly', True)]}),
        'country_id': fields.related('address_id', 'country_id',
                    type='many2one', relation='res.country', string='Country', readonly=False, states={'done': [('readonly', True)]}),
        'note': fields.text('Description', readonly=False, states={'done': [('readonly', True)]}),
        'company_id': fields.many2one('res.company', 'Company', required=False, change_default=True, readonly=False, states={'done': [('readonly', True)]}),
    }

    _defaults = {
        'state': 'draft',
        'company_id': lambda self,cr,uid,c: self.pool.get('res.company')._company_default_get(cr, uid, 'event.event', context=c),
        'user_id': lambda obj, cr, uid, context: uid,
    }

    def _check_closing_date(self, cr, uid, ids, context=None):
        for event in self.browse(cr, uid, ids, context=context):
            if event.date_end < event.date_begin:
                return False
        return True

    _constraints = [
        (_check_closing_date, 'Error ! Closing Date cannot be set before Beginning Date.', ['date_end']),
    ]

    def onchange_evnet_type(self, cr, uid, ids, type_event, context=None):
        if type_event:
            type_info =  self.pool.get('event.type').browse(cr,uid,type_event,context)
            dic ={
              'reply_to':type_info.default_reply_to,
              'email_registration_id':type_info.default_email_registration.id,
              'email_confirmation_id':type_info.default_email_event.id,
              'register_min':type_info.default_registration_min,
              'register_max':type_info.default_registration_max,
            }
            res = {'value':dic}
            return res
event_event()

class event_registration(osv.osv):
    """Event Registration"""
    _name= 'event.registration'
    _description = __doc__
    _inherit = ['mail.thread','res.partner.address']
    _columns = {
        'id': fields.integer('ID'),
        'origin': fields.char('Origin', size=124,readonly=True,help="Name of the sale order which create the registration"),
        'nb_register': fields.integer('Number of Participants', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'event_id': fields.many2one('event.event', 'Event', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'partner_id': fields.many2one('res.partner', 'Partner', states={'done': [('readonly', True)]}),
        'partner_address_id': fields.many2one('res.partner.address', 'Partner', states={'done': [('readonly', True)]}),
        "contact_id": fields.many2one('res.partner.address', 'Partner Contact', readonly=False, states={'done': [('readonly', True)]}),
        'create_date': fields.datetime('Creation Date' , readonly=True),
        'date_closed': fields.datetime('Attended Date', readonly=True),
        'date_open': fields.datetime('Registration Date', readonly=True),
        'reply_to': fields.related('event_id','reply_to',string='Reply-to Email', type='char', size=128, readonly=True,),
        'log_ids': fields.one2many('mail.message', 'res_id', 'Logs', domain=[('email_from', '=', False),('model','=',_name)]),
        'event_end_date': fields.related('event_id','date_end', type='datetime', string="Event End Date", readonly=True),
        'event_begin_date': fields.related('event_id', 'date_begin', type='datetime', string="Event Start Date", readonly=True),
        'user_id': fields.many2one('res.users', 'Responsible', states={'done': [('readonly', True)]}),
        'company_id': fields.related('event_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, readonly=True, states={'draft':[('readonly',False)]}),
        'state': fields.selection([('draft', 'Unconfirmed'),
                                    ('open', 'Confirmed'),
                                    ('cancel', 'Cancelled'),
                                    ('done', 'Attended')], 'State',
                                    size=16, readonly=True)
    }

    _defaults = {
        'nb_register': 1,
        'state': 'draft',
        'user_id': lambda self, cr, uid, ctx: uid,
    }
    _order = 'name, create_date desc'


    def do_draft(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state': 'draft'}, context=context)

    def registration_open(self, cr, uid, ids, context=None):
        """ Open Registration
        """
        res = self.write(cr, uid, ids, {'state': 'open'}, context=context)
        self.mail_user(cr, uid, ids)
        self.message_append(cr, uid, ids,_('State set to...'),body_text= _('Open'))
        return res

    def case_close(self, cr, uid, ids, context=None):
        """ Close Registration
        """
        if context is None:
            context = {}
        values = {'state': 'done', 'date_closed': time.strftime('%Y-%m-%d %H:%M:%S')}
        res = self.write(cr, uid, ids, values)
        self.message_append(cr, uid, ids,_('State set to...'),body_text= _('Done'))
        return res

    # event uses add_note wizard from crm, which expects case_* methods
    def case_open(self, cr, uid, ids, context):
        return self.registration_open(cr, uid, ids, context)

    # event uses add_note wizard from crm, which expects case_* methods
    def case_cancel(self, cr, uid, ids, context=None):
        """ Cancel Registration
        """
        self.message_append(cr, uid, ids,_('State set to...'),body_text= _('Cancel'))
        return self.write(cr, uid, ids, {'state': 'cancel'})

    def button_reg_close(self, cr, uid, ids, context=None):
        """This Function Close Event Registration.
        """
        return self.case_close(cr, uid, ids)

    def button_reg_cancel(self, cr, uid, ids, context=None, *args):
        return self.case_cancel(cr, uid, ids)

    def mail_user(self, cr, uid, ids, confirm=False, context=None):
        """
        Send email to user with email_template when registration is done
        """
        for registration in self.browse(cr, uid, ids, context=context):
            template_id = registration.event_id.email_registration_id.id
            if template_id:
                mail_message = self.pool.get('email.template').send_mail(cr,uid,template_id,registration.id)
        return True

    def mail_user_confirm(self, cr, uid, ids, context=None):
        """
        Send email to user when the event is done
        """
        for registration in self.browse(cr, uid, ids, context=context):
            template_id = registration.event_id.email_confirmation_id.id
            if template_id:
                mail_message = self.pool.get('email.template').send_mail(cr,uid,template_id,registration.id)
        return True

    def onchange_contact_id(self, cr, uid, ids, contact, partner, context=None):
        data ={}
        if not contact:
            return data
        addr_obj = self.pool.get('res.partner.address')
        contact_id =  addr_obj.browse(cr, uid, contact, context=context)
        data = {
            'email':contact_id.email,
            'contact_id':contact_id.id,
            'name':contact_id.name,
            'phone':contact_id.phone,
            }
        return {'value': data}

    def onchange_event(self, cr, uid, ids, event_id, context=None):
        """This function returns value of Product Name, Unit Price based on Event.
        """
        if context is None:
            context = {}
        if not event_id:
            return {}
        event_obj = self.pool.get('event.event')
        data_event =  event_obj.browse(cr, uid, event_id, context=context)
        return {'value': 
                    {'event_begin_date': data_event.date_begin,
                     'event_end_date': data_event.date_end,
                     'company_id': data_event.company_id and data_event.company_id.id or False,
                    }
               }

    def onchange_partner_id(self, cr, uid, ids, part, context=None):
        res_obj = self.pool.get('res.partner')
        data = {}
        if not part:
            return {'value': data}
        addr = res_obj.address_get(cr, uid, [part]).get('default', False)
        if addr:
            d = self.onchange_contact_id(cr, uid, ids, addr, part, context)
            data.update(d['value'])
        return {'value': data}

event_registration()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
