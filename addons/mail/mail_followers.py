# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2009-today OpenERP SA (<http://www.openerp.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################

from osv import osv
from osv import fields

class mail_followers(osv.Model):
    """ mail_followers holds the data related to the follow mechanism inside
        OpenERP. Partners can choose to follow documents (records) of any kind
        that inherits from mail.thread. Following documents allow to receive
        notifications for new messages.
        A subscription is characterized by:
            :param: res_model: model of the followed objects
            :param: res_id: ID of resource (may be 0 for every objects)
    """
    _name = 'mail.followers'
    _rec_name = 'partner_id'
    _log_access = False
    _description = 'Document Followers'
    _columns = {
        'res_model': fields.char('Related Document Model', size=128,
                        required=True, select=1,
                        help='Model of the followed resource'),
        'res_id': fields.integer('Related Document ID', select=1,
                        help='Id of the followed resource'),
        'partner_id': fields.many2one('res.partner', string='Related Partner',
                        ondelete='cascade', required=True, select=1),
    }


class mail_notification(osv.Model):
    """ Class holding notifications pushed to partners. Followers and partners
        added in 'contacts to notify' receive notifications. """
    _name = 'mail.notification'
    _rec_name = 'partner_id'
    _log_access = False
    _description = 'Notifications'

    _columns = {
        'partner_id': fields.many2one('res.partner', string='Contact',
                        ondelete='cascade', required=True, select=1),
        'read': fields.boolean('Read'),
    }

    _defaults = {
        'read': False,
    }

    def create(self, cr, uid, vals, context=None):
        """ Override of create to check that we can not create a notification
            for a message the user can not read. """
        if self.pool.get('mail.message').check_access_rights(cr, uid, 'read'):
            return super(mail_notification, self).create(cr, uid, vals, context=context)
        return False

    def notify(self, cr, uid, partner_ids, msg_id, context=None):
        """ Send by email the notification depending on the user preferences """
        context = context or {}
        # mail_noemail (do not send email) or no partner_ids: do not send, return
        if context.get('mail_noemail') or not partner_ids:
            return True

        mail_mail_obj = self.pool.get('mail.mail')
        msg_obj = self.pool.get('mail.message')
        msg = msg_obj.browse(cr, uid, msg_id, context=context)

        towrite = {
            'mail_message_id': msg.id,
            'email_to': [],
            'user_signature': True,
            'auto_delete': True,
        }

        for partner in self.pool.get('res.partner').browse(cr, uid, partner_ids, context=context):
            # Do not send an email to the writer
            if partner.user_id.id == uid:
                continue
            # Partner does not want to receive any emails
            if partner.notification_email_send=='none' or not partner.email:
                continue
            # Partner want to receive only emails and comments
            if partner.notification_email_send=='comment' and msg.type not in ('email','comment'):
                continue

            if partner.email not in towrite['email_to']:
                towrite['email_to'].append(partner.email)
        towrite['email_to'] = ', '.join(towrite['email_to'])

        email_notif_id = mail_mail_obj.create(cr, uid, towrite, context=context)
        mail_mail_obj.send(cr, uid, [email_notif_id], context=context)
        return True
