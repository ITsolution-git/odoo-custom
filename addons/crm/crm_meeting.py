# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-today OpenERP SA (<http://www.openerp.com>)
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

from base_calendar import base_calendar
from crm import crm_base, crm_case
import logging
from osv import fields, osv
import tools
from tools.translate import _

class crm_lead(crm_case, osv.osv):
        """ CRM Leads """
        _name = 'crm.lead'

class crm_meeting(crm_base, osv.Model):
    """ Model for CRM meetings """
    _name = 'crm.meeting'
    _description = "Meeting"
    _order = "id desc"
    _inherit = ["calendar.event", 'ir.needaction_mixin', "mail.thread"]
    _columns = {
        # base_state required fields
        'partner_id': fields.many2one('res.partner', 'Partner', states={'done': [('readonly', True)]}),
        'section_id': fields.many2one('crm.case.section', 'Sales Team', states={'done': [('readonly', True)]}, \
                        select=True, help='Sales team to which Case belongs to.'),
        'email_from': fields.char('Email', size=128, states={'done': [('readonly', True)]}, help="These people will receive email."),
        'id': fields.integer('ID', readonly=True),
        'create_date': fields.datetime('Creation Date' , readonly=True),
        'write_date': fields.datetime('Write Date' , readonly=True),
        'date_action_last': fields.datetime('Last Action', readonly=1),
        'date_action_next': fields.datetime('Next Action', readonly=1),
        # Meeting fields
        'name': fields.char('Summary', size=124, required=True, states={'done': [('readonly', True)]}),
        'categ_id': fields.many2one('crm.case.categ', 'Meeting Type', \
                        domain="[('object_id.model', '=', 'crm.meeting')]", \
            ),
        'phonecall_id': fields.many2one ('crm.phonecall', 'Phonecall'),
        'opportunity_id': fields.many2one ('crm.lead', 'Opportunity', domain="[('type', '=', 'opportunity')]"),
        'attendee_ids': fields.many2many('calendar.attendee', 'meeting_attendee_rel',\
                                 'event_id', 'attendee_id', 'Attendees', states={'done': [('readonly', True)]}),
        'date_closed': fields.datetime('Closed', readonly=True),
        'date_deadline': fields.datetime('Deadline', states={'done': [('readonly', True)]}),
        'message_ids': fields.one2many('mail.message', 'res_id', 'Messages', domain=[('model','=',_name)]),
        'state': fields.selection([ ('draft', 'Unconfirmed'),
                                    ('open', 'Confirmed'),
                                    ('cancel', 'Cancelled'),
                                    ('done', 'Done')],
                                    string='Status', size=16, readonly=True),
    }
    _defaults = {
        'state': 'draft',
        'active': 1,
        'user_id': lambda self, cr, uid, ctx: uid,
    }

    def create(self, cr, uid, vals, context=None):
        obj_id = super(crm_meeting, self).create(cr, uid, vals, context=context)
        self.create_send_note(cr, uid, [obj_id], context=context)
        return obj_id

    def get_needaction_user_ids(self, cr, uid, ids, context=None):
        result = dict.fromkeys(ids, [])
        for obj in self.browse(cr, uid, ids, context=context):
            if (obj.state == 'draft' and obj.user_id):
                result[obj.id] = [obj.user_id.id]
        return result

    def case_open(self, cr, uid, ids, context=None):
        """ Confirms meeting """
        res = super(crm_meeting, self).case_open(cr, uid, ids, context)
        for (id, name) in self.name_get(cr, uid, ids):
            id=base_calendar.base_calendar_id2real_id(id)
        return res
    
    # ----------------------------------------
    # OpenChatter
    # ----------------------------------------

    def case_get_note_msg_prefix(self, cr, uid, id, context=None):
        return 'Meeting'

    def create_send_note(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        # update context: if come from phonecall, default state values can make the message_append_note crash
        context.pop('default_state', False)
        for meeting in self.browse(cr, uid, ids, context=context):
            # convert datetime field to a datetime, using server format, then
            # convert it to the user TZ and re-render it with %Z to add the timezone
            meeting_datetime = fields.DT.datetime.strptime(meeting.date, tools.DEFAULT_SERVER_DATETIME_FORMAT)
            meeting_date_str = fields.datetime.context_timestamp(cr, uid, meeting_datetime, context=context).strftime(tools.DATETIME_FORMATS_MAP['%+'] + " (%Z)")
            message = _("A meeting has been <b>scheduled</b> on <em>%s</em>.") % (meeting_date_str)
            if meeting.opportunity_id: # meeting can be create from phonecalls or opportunities, therefore checking for the parent
                lead = meeting.opportunity_id
                parent_message = _("Meeting linked to the opportunity <em>%s</em> has been <b>created</b> and <b>cscheduled</b> on <em>%s</em>.") % (lead.name, meeting.date)
                lead.message_append_note(_('System Notification'), message)
            elif meeting.phonecall_id:
                phonecall = meeting.phonecall_id
                parent_message = _("Meeting linked to the phonecall <em>%s</em> has been <b>created</b> and <b>cscheduled</b> on <em>%s</em>.") % (phonecall.name, meeting.date)
                phonecall.message_append_note(body=message)
            else:
                parent_message = message
            if parent_message:
                meeting.message_append_note(body=parent_message)
        return True

    def case_open_send_note(self, cr, uid, ids, context=None):
        return self.message_append_note(cr, uid, ids, body=_("Meeting has been <b>confirmed</b>."), context=context)

    def case_close_send_note(self, cr, uid, ids, context=None):
        return self.message_append_note(cr, uid, ids, body=_("Meeting has been <b>done</b>."), context=context)


class calendar_attendee(osv.osv):
    """ Calendar Attendee """

    _inherit = 'calendar.attendee'
    _description = 'Calendar Attendee'

    def _compute_data(self, cr, uid, ids, name, arg, context=None):
       """
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of compute data’s IDs
        @param context: A standard dictionary for contextual values
        """
       name = name[0]
       result = super(calendar_attendee, self)._compute_data(cr, uid, ids, name, arg, context=context)

       for attdata in self.browse(cr, uid, ids, context=context):
            id = attdata.id
            result[id] = {}
            if name == 'categ_id':
                if attdata.ref and 'categ_id' in attdata.ref._columns:
                    result[id][name] = (attdata.ref.categ_id.id, attdata.ref.categ_id.name,)
                else:
                    result[id][name] = False
       return result

    _columns = {
        'categ_id': fields.function(_compute_data, \
                        string='Event Type', type="many2one", \
                        relation="crm.case.categ", multi='categ_id'),
    }

calendar_attendee()

class res_users(osv.osv):
    _name = 'res.users'
    _inherit = 'res.users'

    def create(self, cr, uid, data, context=None):
        user_id = super(res_users, self).create(cr, uid, data, context=context)

        # add shortcut unless 'noshortcut' is True in context
        if not(context and context.get('noshortcut', False)):
            data_obj = self.pool.get('ir.model.data')
            try:
                data_id = data_obj._get_id(cr, uid, 'crm', 'ir_ui_view_sc_calendar0')
                view_id  = data_obj.browse(cr, uid, data_id, context=context).res_id
                self.pool.get('ir.ui.view_sc').copy(cr, uid, view_id, default = {
                                            'user_id': user_id}, context=context)
            except:
                # Tolerate a missing shortcut. See product/product.py for similar code.
                logging.getLogger('orm').debug('Skipped meetings shortcut for user "%s"', data.get('name','<new'))
        return user_id

res_users()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
