# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>)
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
from tools.translate import _
import tools
import netsvc
import base64
import time
#import binascii
#import email
#from email.header import decode_header
#from email.utils import parsedate
#import base64
#import re
#import logging
#import xmlrpclib

#import re
#import smtplib
#import base64
#from email import Encoders
#from email.mime.base import MIMEBase
#from email.mime.multipart import MIMEMultipart
#from email.mime.text import MIMEText
#from email.header import decode_header, Header
#from email.utils import formatdate
#import netsvc
#import datetime
#import tools
#import logging
#email_content_types = [
#    'multipart/mixed',
#    'multipart/alternative',
#    'multipart/related',
#    'text/plain',
#    'text/html'
#]

LOGGER = netsvc.Logger()
def format_date_tz(date, tz=None):
    if not date:
        return 'n/a'
    format = tools.DEFAULT_SERVER_DATETIME_FORMAT
    return tools.server_to_local_timestamp(date, format, format, tz)

class email_message_template(osv.osv_memory):
    _name = 'email.message.template'
    _columns = {
        'name':fields.text('Subject', translate=True),
        'model': fields.char('Object Name', size=128, select=1),
        'res_id': fields.integer('Resource ID', select=1),
        'date': fields.datetime('Date'),
        'user_id': fields.many2one('res.users', 'User Responsible'),
        'email_from': fields.char('From', size=128, help="Email From"),
        'email_to': fields.char('To', help="Email Recipients", size=256),
        'email_cc': fields.char('Cc', help="Carbon Copy Email Recipients", size=256),
        'email_bcc': fields.char('Bcc', help='Blind Carbon Copy Email Recipients', size=256),
        'message_id': fields.char('Message Id', size=1024, help="Message Id on Email.", select=1),
        'references': fields.text('References', help="References emails."),
        'reply_to':fields.char('Reply-To', size=250),
        'sub_type': fields.char('Sub Type', size=32),
        'headers': fields.char('x_headers',size=256),
        'priority':fields.integer('Priority'),
        'description': fields.text('Description', translate=True),
        'smtp_server_id':fields.many2one('email.smtp_server', 'SMTP Server'),
    }

    _sql_constraints = []
email_message_template()

class email_message(osv.osv):
    '''
    Email Message
    '''
    _inherit = 'email.message.template'
    _name = 'email.message'
    _description = 'Email Message'
    _order = 'date desc'

    def open_document(self, cr, uid, ids, context=None):
        """ To Open Document
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: the ID of messages
        @param context: A standard dictionary
        """
        action_data = False
        if ids:
            message_id = ids[0]
            mailgate_data = self.browse(cr, uid, message_id, context=context)
            model = mailgate_data.model
            res_id = mailgate_data.res_id

            action_pool = self.pool.get('ir.actions.act_window')
            action_ids = action_pool.search(cr, uid, [('res_model', '=', model)])
            if action_ids:
                action_data = action_pool.read(cr, uid, action_ids[0], context=context)
                action_data.update({
                    'domain' : "[('id','=',%d)]"%(res_id),
                    'nodestroy': True,
                    'context': {}
                    })
        return action_data

    def open_attachment(self, cr, uid, ids, context=None):
        """ To Open attachments
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: the ID of messages
        @param context: A standard dictionary
        """
        action_data = False
        action_pool = self.pool.get('ir.actions.act_window')
        message_pool = self.browse(cr ,uid, ids, context=context)[0]
        att_ids = [x.id for x in message_pool.attachment_ids]
        action_ids = action_pool.search(cr, uid, [('res_model', '=', 'ir.attachment')])
        if action_ids:
            action_data = action_pool.read(cr, uid, action_ids[0], context=context)
            action_data.update({
                'domain': [('id','in',att_ids)],
                'nodestroy': True
                })
        return action_data

    def truncate_data(self, cr, uid, data, context=None):
        data_list = data and data.split('\n') or []
        if len(data_list) > 3:
            res = '\n\t'.join(data_list[:3]) + '...'
        else:
            res = '\n\t'.join(data_list)
        return res

    def _get_display_text(self, cr, uid, ids, name, arg, context=None):
        if context is None:
            context = {}
        tz = context.get('tz')
        result = {}
        for message in self.browse(cr, uid, ids, context=context):
            msg_txt = ''
            if message.history:
                msg_txt += _('%s wrote on %s:\n\t') % (message.email_from or '/', format_date_tz(message.date, tz))
                if message.description:
                    msg_txt += self.truncate_data(cr, uid, message.description, context=context)
            else:
                msg_txt = _('%s on %s:\n\t') % (message.user_id.name or '/', format_date_tz(message.date, tz))
                msg_txt += message.name
            result[message.id] = msg_txt
        return result

    _columns = {
        'message': fields.text('Description'),
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'attachment_ids': fields.many2many('ir.attachment', 'message_attachment_rel', 'message_id', 'attachment_id', 'Attachments'),
        'display_text': fields.function(_get_display_text, method=True, type='text', size="512", string='Display Text'),
        'debug':fields.boolean('Debug', readonly=True),
        'history': fields.boolean('History', readonly=True),
        'folder':fields.selection([
                        ('drafts', 'Drafts'),
                        ('inbox', 'Inbox'),
                        ('outbox', 'Outbox'),
                        ('trash', 'Trash'),
                        ('sent', 'Sent Items'),
                        ], 'Folder'),
        'state':fields.selection([
                        ('draft', 'Draft'),
                        ('sending', 'Sending'),
                        ('waiting', 'Waiting'),
                        ('sent', 'Sent'),
                        ('exception', 'Exception'),
                        ], 'State', readonly=True),
    }

    _defaults = {
        'state': lambda * a: 'draft',
        'folder': lambda * a: 'outbox',
    }

    def unlink(self, cr, uid, ids, context=None):
        """
        It just changes the folder of the item to "Trash", if it is no in Trash folder yet,
        or completely deletes it if it is already in Trash.
        """
        to_update = []
        to_remove = []
        for mail in self.browse(cr, uid, ids, context=context):
            if mail.folder == 'trash':
                to_remove.append(mail.id)
            else:
                to_update.append(mail.id)
        # Changes the folder to trash
        self.write(cr, uid, to_update, {'folder': 'trash'}, context=context)
        return super(email_message, self).unlink(cr, uid, to_remove, context=context)

    def init(self, cr):
        cr.execute("""SELECT indexname
                      FROM pg_indexes
                      WHERE indexname = 'email_message_res_id_model_idx'""")
        if not cr.fetchone():
            cr.execute("""CREATE INDEX email_message_res_id_model_idx
                          ON email_message (model, res_id)""")

    def process_queue(self, cr, uid, ids, arg):
        self.process_email_queue(cr, uid, ids=ids)
        return True

    def run_mail_scheduler(self, cursor, user, context=None):
        """
        This method is called by OpenERP Scheduler
        to periodically send emails
        """
        try:
            self.process_email_queue(cursor, user, context=context)
        except Exception, e:
            LOGGER.notifyChannel(
                                 "Email Template",
                                 netsvc.LOG_ERROR,
                                 _("Error sending mail: %s") % e)

    def email_send(self, cr, uid, email_from, email_to, subject, body, model=False, email_cc=None, email_bcc=None, reply_to=False, attach=None,
            message_id=False, references=False, openobject_id=False, debug=False, subtype='plain', x_headers={}, priority='3', smtp_server_id=False, context=None):
        attachment_obj = self.pool.get('ir.attachment')
        if email_to and type(email_to) != list:
            email_to = [email_to]
        if email_cc and type(email_cc) != list:
            email_cc = [email_cc]
        if email_bcc and type(email_bcc) != list:
            email_bcc = [email_bcc]

        msg_vals = {
                'name': subject,
                'model': model or '',
                'date': time.strftime('%Y-%m-%d'),
                'user_id': uid,
                'description': body,
                'email_from': email_from,
                'email_to': email_to and ','.join(email_to) or '',
                'email_cc': email_cc and ','.join(email_cc) or '',
                'email_bcc': email_bcc and ','.join(email_bcc) or '',
                'reply_to': reply_to,
                'res_id': openobject_id,
                'message_id': message_id,
                'references': references or '',
                'sub_type': subtype or '',
                'headers': x_headers or False,
                'priority': priority,
                'debug': debug,
                'folder': 'outbox',
                'history': True,
                'smtp_server_id': smtp_server_id,
                'state': 'waiting',
            }
        email_msg_id = self.create(cr, uid, msg_vals, context)
        if attach:
            attachment_ids = []
            for attachment in attach:
                attachment_data = {
                        'name':  (subject or '') + _(' (Email Attachment)'),
                        'datas': attachment[1],
                        'datas_fname': attachment[0],
                        'description': subject or _('No Description'),
                        'res_model':'email.message',
                        'res_id': email_msg_id,
                    }
                attachment_ids.append(attachment_obj.create(cr, uid, attachment_data, context))
            self.write(cr, uid, email_msg_id,
                              { 'attachment_ids': [[6, 0, attachment_ids]] }, context)
        return email_msg_id

    def process_retry(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state':'waiting'}, context)

    def process_email_queue(self, cr, uid, ids=None, context=None):
        if ids is None:
            ids = []
        if context is None:
            context = {}
        attachment_obj = self.pool.get('ir.attachment')
        smtp_server_obj = self.pool.get('email.smtp_server')
        if not ids:
            filters = [('folder', '=', 'outbox'), ('state', '=', 'waiting')]
            if 'filters' in context:
                filters.extend(context['filters'])
            ids = self.search(cr, uid, filters, context=context)
        self.write(cr, uid, ids, {'state':'sending', 'folder':'sent'}, context)
        for message in self.browse(cr, uid, ids, context):
            try:
                attachments = []
                for attach in message.attachment_ids:
                    attachments.append((attach.datas_fname ,base64.b64decode(attach.datas)))
                smtp_server = message.smtp_server_id
                if not smtp_server:
                    smtp_ids = smtp_server_obj.search(cr, uid, [('default','=',True)])
                    if smtp_ids:
                        smtp_server = smtp_server_obj.browse(cr, uid, smtp_ids, context)[0]
                res = tools.email_send(message.email_from,
                        message.email_to and message.email_to.split(',') or [],
                        message.name, message.description,
                        email_cc=message.email_cc and message.email_cc.split(',') or [],
                        email_bcc=message.email_bcc and message.email_bcc.split(',') or [],
                        reply_to=message.reply_to,
                        attach=attachments, message_id=message.message_id, references = message.references,
                        openobject_id=message.res_id,
                        subtype=message.sub_type,
                        x_headers=message.headers and eval(message.headers) or {},
                        priority=message.priority, debug=message.debug,
                        smtp_server=smtp_server and smtp_server.smtpserver or None,
                        smtp_port=smtp_server and smtp_server.smtpport or None,
                        ssl=smtp_server and smtp_server.smtpssl or False,
                        smtp_user=smtp_server and smtp_server.smtpuname or None,
                        smtp_password=smtp_server and smtp_server.smtppass or None)
                if res:
                    self.write(cr, uid, [message.id], {'state':'sent', 'message_id': res}, context)
                else:
                    self.write(cr, uid, [message.id], {'state':'exception'}, context)
            except Exception, error:
                logger = netsvc.Logger()
                logger.notifyChannel("email-template", netsvc.LOG_ERROR, _("Sending of Mail %s failed. Probable Reason:Could not login to server\nError: %s") % (message.id, error))
                self.write(cr, uid, [message.id], {'state':'exception'}, context)
        return ids

# OLD Code.
#    def send_all_mail(self, cr, uid, ids=None, context=None):
#        if ids is None:
#            ids = []
#        if context is None:
#            context = {}
#        filters = [('folder', '=', 'outbox'), ('state', '!=', 'sending')]
#        if 'filters' in context.keys():
#            for each_filter in context['filters']:
#                filters.append(each_filter)
#        ids = self.search(cr, uid, filters, context=context)
#        self.write(cr, uid, ids, {'state':'sending'}, context)
#        self.send_this_mail(cr, uid, ids, context)
#        return True
#
#    def send_this_mail(self, cr, uid, ids=None, context=None):
#        #previous method to send email (link with email account can be found at the revision 4172 and below
#        result = True
#        attachment_pool = self.pool.get('ir.attachment')
#        for id in (ids or []):
#            try:
#                account_obj = self.pool.get('email.smtp_server')
#                values = self.read(cr, uid, id, [], context)
#                payload = {}
#                if values['attachments_ids']:
#                    for attid in values['attachments_ids']:
#                        attachment = attachment_pool.browse(cr, uid, attid, context)#,['datas_fname','datas'])
#                        payload[attachment.datas_fname] = attachment.datas
#                result = account_obj.send_email(cr, uid,
#                              [values['account_id'][0]],
#                              {'To':values.get('email_to') or u'',
#                               'CC':values.get('email_cc') or u'',
#                               'BCC':values.get('email_bcc') or u'',
#                               'Reply-To':values.get('reply_to') or u''},
#                              values['subject'] or u'',
#                              {'text':values.get('body_text') or u'', 'html':values.get('body_html') or u''},
#                              payload=payload,
#                              message_id=values['message_id'],
#                              context=context)
#                if result == True:
#                    account = account_obj.browse(cr, uid, values['account_id'][0], context=context)
#                    if account.auto_delete:
#                        self.write(cr, uid, id, {'folder': 'trash'}, context=context)
#                        self.unlink(cr, uid, [id], context=context)
#                        # Remove attachments for this mail
#                        attachment_pool.unlink(cr, uid, values['attachments_ids'], context=context)
#                    else:
#                        self.write(cr, uid, id, {'folder':'sent', 'state':'na', 'date_mail':time.strftime("%Y-%m-%d %H:%M:%S")}, context)
#                else:
#                    error = result['error_msg']
#
#            except Exception, error:
#                logger = netsvc.Logger()
#                logger.notifyChannel("email-template", netsvc.LOG_ERROR, _("Sending of Mail %s failed. Probable Reason:Could not login to server\nError: %s") % (id, error))
#            self.write(cr, uid, id, {'state':'na'}, context)
#        return result

email_message()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
