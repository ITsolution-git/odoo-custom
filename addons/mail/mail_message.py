# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2010-today OpenERP SA (<http://www.openerp.com>)
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

import ast
import base64
import dateutil.parser
import email
import logging
import re
import time
import datetime
from email.header import decode_header
from email.message import Message

from openerp import SUPERUSER_ID
from osv import osv
from osv import fields
import pytz
from tools import DEFAULT_SERVER_DATETIME_FORMAT
from tools.translate import _
import tools

_logger = logging.getLogger(__name__)

""" Some tools for parsing / creating email fields """
def decode(text):
    """Returns unicode() string conversion of the the given encoded smtp header text"""
    if text:
        text = decode_header(text.replace('\r', ''))
        return ''.join([tools.ustr(x[0], x[1]) for x in text])

def mail_tools_to_email(text):
    """Return a list of the email addresses found in ``text``"""
    if not text: return []
    return re.findall(r'([^ ,<@]+@[^> ,]+)', text)

# TODO: remove that after cleaning
def to_email(text):
    return mail_tools_to_email(text)

class mail_message_common(osv.TransientModel):
    """ Common abstract class for holding the main attributes of a 
        message object. It could be reused as parent model for any
        database model or wizard screen that needs to hold a kind of
        message.
        All internal logic should be in another model while this
        model holds the basics of a message. For example, a wizard for writing
        emails should inherit from this class and not from mail.message."""

    def get_body(self, cr, uid, ids, name, arg, context=None):
        """ get correct body version: body_html for html messages, and
            body_text for plain text messages
        """
        result = dict.fromkeys(ids, '')
        for message in self.browse(cr, uid, ids, context=context):
            if message.content_subtype == 'html':
                result[message.id] = message.body_html
            else:
                result[message.id] = message.body_text
        return result
    
    def search_body(self, cr, uid, obj, name, args, context=None):
        # will receive:
        #   - obj: mail.message object
        #   - name: 'body'
        #   - args: [('body', 'ilike', 'blah')]
        return ['|', '&', ('content_subtype', '=', 'html'), ('body_html', args[0][1], args[0][2]), ('body_text', args[0][1], args[0][2])]
    
    def get_record_name(self, cr, uid, ids, name, arg, context=None):
        result = dict.fromkeys(ids, '')
        for message in self.browse(cr, uid, ids, context=context):
            if not message.model or not message.res_id:
                continue
            result[message.id] = self.pool.get(message.model).name_get(cr, uid, [message.res_id], context=context)[0][1]
        return result

    def name_get(self, cr, uid, ids, context=None):
        # name_get may receive int id instead of an id list
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        for message in self.browse(cr, uid, ids, context=context):
            name = ''
            if message.subject:
                name = '%s: ' % (message.subject)
            if message.body_text:
                name = '%s%s ' % (name, message.body_text[0:20])
            if message.date:
                name = '%s(%s)' % (name, message.date)
            res.append((message.id, name))
        return res

    _name = 'mail.message.common'
    _rec_name = 'subject'
    _columns = {
        'subject': fields.char('Subject', size=512),
        'model': fields.char('Related Document Model', size=128, select=1),
        'res_id': fields.integer('Related Document ID', select=1),
        'record_name': fields.function(get_record_name, type='string',
            string='Message Record Name',
            help="Name get of the related document."),
        'date': fields.datetime('Date'),
        'email_from': fields.char('From', size=128, help='Message sender, taken from user preferences.'),
        'email_to': fields.char('To', size=256, help='Message recipients'),
        'email_cc': fields.char('Cc', size=256, help='Carbon copy message recipients'),
        'email_bcc': fields.char('Bcc', size=256, help='Blind carbon copy message recipients'),
        'reply_to':fields.char('Reply-To', size=256, help='Preferred response address for the message'),
        'headers': fields.text('Message Headers', readonly=1,
            help="Full message headers, e.g. SMTP session headers (usually available on inbound messages only)"),
        'message_id': fields.char('Message-Id', size=256, help='Message unique identifier', select=1, readonly=1),
        'references': fields.text('References', help='Message references, such as identifiers of previous messages', readonly=1),
        'content_subtype': fields.char('Message content subtype', size=32,
            oldname="subtype", readonly=1,
            help="Type of message, usually 'html' or 'plain', used to select "\
                  "plain-text or rich-text contents accordingly"),
        'body_text': fields.text('Text Contents', help="Plain-text version of the message"),
        'body_html': fields.text('Rich-text Contents', help="Rich-text/HTML version of the message"),
        'body': fields.function(get_body, fnct_search = search_body, type='text',
            string='Message Content', store=True,
            help="Content of the message. This content equals the body_text field "\
                 "for plain-test messages, and body_html for rich-text/HTML "\
                 "messages. This allows having one field if we want to access "\
                 "the content matching the message content_subtype."),
        'parent_id': fields.many2one('mail.message.common', 'Parent Message',
            select=True, ondelete='set null',
            help="Parent message, used for displaying as threads with hierarchy"),
    }

    _defaults = {
        'content_subtype': 'plain',
        'date': (lambda *a: fields.datetime.now()),
    }

class mail_message(osv.Model):
    """Model holding messages: system notification (replacing res.log
       notifications), comments (for OpenChatter feature) and
       RFC2822 email messages. This model also provides facilities to
       parse, queue and send new email messages. Type of messages
       are differentiated using the 'type' column. """

    _name = 'mail.message'
    _inherit = 'mail.message.common'
    _description = 'Mail Message (email, comment, notification)'
    _order = 'date desc'

    def open_document(self, cr, uid, ids, context=None):
        """ Open the message related document. Note that only the document of
            ids[0] will be opened.
            TODO: how to determine the action to use ?
        """
        action_data = False
        if not ids:
            return action_data
        msg = self.browse(cr, uid, ids[0], context=context)
        ir_act_window = self.pool.get('ir.actions.act_window')
        action_ids = ir_act_window.search(cr, uid, [('res_model', '=', msg.model)], context=context)
        if action_ids:
            action_data = ir_act_window.read(cr, uid, action_ids[0], context=context)
            action_data.update({
                    'domain' : "[('id', '=', %d)]" % (msg.res_id),
                    'nodestroy': True,
                    'context': {}
                    })
        return action_data

    def open_attachment(self, cr, uid, ids, context=None):
        """ Open the message related attachments.
            TODO: how to determine the action to use ?
        """
        action_data = False
        if not ids:
            return action_data
        action_pool = self.pool.get('ir.actions.act_window')
        messages = self.browse(cr, uid, ids, context=context)
        att_ids = [x.id for message in messages for x in message.attachment_ids]
        action_ids = action_pool.search(cr, uid, [('res_model', '=', 'ir.attachment')], context=context)
        if action_ids:
            action_data = action_pool.read(cr, uid, action_ids[0], context=context)
            action_data.update({
                'domain': [('id', 'in', att_ids)],
                'nodestroy': True
                })
        return action_data
    
    _columns = {
        'type': fields.selection([
                        ('email', 'email'),
                        ('comment', 'Comment'),
                        ('notification', 'System notification'),
                        ], 'Type',
            help="Message type: email for email message, notification for system "\
                  "message, comment for other messages such as user replies"),
        'partner_id': fields.many2one('res.partner', 'Related partner',
            help="Deprecated field. Use partner_ids instead."),
        'partner_ids': fields.many2many('res.partner',
            'mail_message_res_partner_rel',
            'message_id', 'partner_id', 'Destination partners',
            help="When sending emails through the social network composition wizard"\
                 "you may choose to send a copy of the mail to partners."),
        'user_id': fields.many2one('res.users', 'Related User', readonly=1),
        'attachment_ids': fields.many2many('ir.attachment', 'message_attachment_rel',
            'message_id', 'attachment_id', 'Attachments'),
        'mail_server_id': fields.many2one('ir.mail_server', 'Outgoing mail server', readonly=1),
        'state': fields.selection([
                        ('outgoing', 'Outgoing'),
                        ('sent', 'Sent'),
                        ('received', 'Received'),
                        ('exception', 'Delivery Failed'),
                        ('cancel', 'Cancelled'),
                        ], 'Status', readonly=True),
        'auto_delete': fields.boolean('Auto Delete',
            help="Permanently delete this email after sending it, to save space"),
        'original': fields.binary('Original', readonly=1,
            help="Original version of the message, as it was sent on the network"),
        'parent_id': fields.many2one('mail.message', 'Parent Message',
            select=True, ondelete='set null',
            help="Parent message, used for displaying as threads with hierarchy"),
        'child_ids': fields.one2many('mail.message', 'parent_id', 'Child Messages'),
    }
        
    _defaults = {
        'type': 'email',
        'state': 'received',
    }
    
    #------------------------------------------------------
    # Email api
    #------------------------------------------------------
    
    def init(self, cr):
        cr.execute("""SELECT indexname FROM pg_indexes WHERE indexname = 'mail_message_model_res_id_idx'""")
        if not cr.fetchone():
            cr.execute("""CREATE INDEX mail_message_model_res_id_idx ON mail_message (model, res_id)""")

    def check(self, cr, uid, ids, mode, context=None, values=None):
        """Restricts the access to a mail.message, according to referred model
        """
        if not ids:
            return
        res_ids = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        cr.execute('SELECT DISTINCT model, res_id FROM mail_message WHERE id = ANY (%s)', (ids,))
        for rmod, rid in cr.fetchall():
            if not (rmod and rid):
                continue
            res_ids.setdefault(rmod,set()).add(rid)
        if values:
            if 'res_model' in values and 'res_id' in values:
                res_ids.setdefault(values['res_model'],set()).add(values['res_id'])

        ima_obj = self.pool.get('ir.model.access')
        for model, mids in res_ids.items():
            # ignore mail messages that are not attached to a resource anymore when checking access rights
            # (resource was deleted but message was not)
            mids = self.pool.get(model).exists(cr, uid, mids)
            ima_obj.check(cr, uid, model, mode)
            self.pool.get(model).check_access_rule(cr, uid, mids, mode, context=context)
    
    def create(self, cr, uid, values, context=None):
        self.check(cr, uid, [], mode='create', context=context, values=values)
        return super(mail_message, self).create(cr, uid, values, context)

    def read(self, cr, uid, ids, fields_to_read=None, context=None, load='_classic_read'):
        self.check(cr, uid, ids, 'read', context=context)
        return super(mail_message, self).read(cr, uid, ids, fields_to_read, context, load)

    def copy(self, cr, uid, id, default=None, context=None):
        """Overridden to avoid duplicating fields that are unique to each email"""
        if default is None:
            default = {}
        self.check(cr, uid, [id], 'read', context=context)
        default.update(message_id=False, original=False, headers=False)
        return super(mail_message,self).copy(cr, uid, id, default=default, context=context)
    
    def write(self, cr, uid, ids, vals, context=None):
        self.check(cr, uid, ids, 'write', context=context, values=vals)
        return super(mail_message, self).write(cr, uid, ids, vals, context)

    def unlink(self, cr, uid, ids, context=None):
        self.check(cr, uid, ids, 'unlink', context=context)
        return super(mail_message, self).unlink(cr, uid, ids, context)

    def schedule_with_attach(self, cr, uid, email_from, email_to, subject, body, model=False, type='email',
                             email_cc=None, email_bcc=None, reply_to=False, partner_ids=None, attachments=None,
                             message_id=False, references=False, res_id=False, content_subtype='plain',
                             headers=None, mail_server_id=False, auto_delete=False, context=None):
        """ Schedule sending a new email message, to be sent the next time the
            mail scheduler runs, or the next time :meth:`process_email_queue` is
            called explicitly.

            :param string email_from: sender email address
            :param list email_to: list of recipient addresses (to be joined with commas) 
            :param string subject: email subject (no pre-encoding/quoting necessary)
            :param string body: email body, according to the ``content_subtype`` 
                (by default, plaintext). If html content_subtype is used, the
                message will be automatically converted to plaintext and wrapped
                in multipart/alternative.
            :param list email_cc: optional list of string values for CC header
                (to be joined with commas)
            :param list email_bcc: optional list of string values for BCC header
                (to be joined with commas)
            :param string model: optional model name of the document this mail
                is related to (this will also be used to generate a tracking id,
                used to match any response related to the same document)
            :param int res_id: optional resource identifier this mail is related
                to (this will also be used to generate a tracking id, used to
                match any response related to the same document)
            :param string reply_to: optional value of Reply-To header
            :param partner_ids: destination partner_ids
            :param string content_subtype: optional mime content_subtype for
                the text body (usually 'plain' or 'html'), must match the format
                of the ``body`` parameter. Default is 'plain', making the content
                part of the mail "text/plain".
            :param dict attachments: map of filename to filecontents, where
                filecontents is a string containing the bytes of the attachment
            :param dict headers: optional map of headers to set on the outgoing
                mail (may override the other headers, including Subject,
                Reply-To, Message-Id, etc.)
            :param int mail_server_id: optional id of the preferred outgoing
                mail server for this mail
            :param bool auto_delete: optional flag to turn on auto-deletion of
                the message after it has been successfully sent (default to False)
        """
        if context is None:
            context = {}
        if attachments is None:
            attachments = {}
        if partner_ids is None:
            partner_ids = []
        attachment_obj = self.pool.get('ir.attachment')
        for param in (email_to, email_cc, email_bcc):
            if param and not isinstance(param, list):
                param = [param]
        msg_vals = {
                'subject': subject,
                'date': fields.datetime.now(),
                'user_id': uid,
                'model': model,
                'res_id': res_id,
                'type': type,
                'body_text': body if content_subtype != 'html' else False,
                'body_html': body if content_subtype == 'html' else False,
                'email_from': email_from,
                'email_to': email_to and ','.join(email_to) or '',
                'email_cc': email_cc and ','.join(email_cc) or '',
                'email_bcc': email_bcc and ','.join(email_bcc) or '',
                'partner_ids': partner_ids,
                'reply_to': reply_to,
                'message_id': message_id,
                'references': references,
                'content_subtype': content_subtype,
                'headers': headers, # serialize the dict on the fly
                'mail_server_id': mail_server_id,
                'state': 'outgoing',
                'auto_delete': auto_delete
            }
        email_msg_id = self.create(cr, uid, msg_vals, context)
        attachment_ids = []
        for attachment in attachments:
            fname, fcontent = attachment
            attachment_data = {
                    'name': fname,
                    'datas_fname': fname,
                    'datas': fcontent and fcontent.encode('base64'),
                    'res_model': self._name,
                    'res_id': email_msg_id,
            }
            if context.has_key('default_type'):
                del context['default_type']
            attachment_ids.append(attachment_obj.create(cr, uid, attachment_data, context))
        if attachment_ids:
            self.write(cr, uid, email_msg_id, { 'attachment_ids': [(6, 0, attachment_ids)]}, context=context)
        return email_msg_id

    def mark_outgoing(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state':'outgoing'}, context=context)

    def cancel(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state':'cancel'}, context=context)

    def process_email_queue(self, cr, uid, ids=None, context=None):
        """Send immediately queued messages, committing after each
           message is sent - this is not transactional and should
           not be called during another transaction!

           :param list ids: optional list of emails ids to send. If passed
                            no search is performed, and these ids are used
                            instead.
           :param dict context: if a 'filters' key is present in context,
                                this value will be used as an additional
                                filter to further restrict the outgoing
                                messages to send (by default all 'outgoing'
                                messages are sent).
        """
        if context is None:
            context = {}
        if not ids:
            filters = ['&', ('state', '=', 'outgoing'), ('type', '=', 'email')]
            if 'filters' in context:
                filters.extend(context['filters'])
            ids = self.search(cr, uid, filters, context=context)
        res = None
        try:
            # Force auto-commit - this is meant to be called by
            # the scheduler, and we can't allow rolling back the status
            # of previously sent emails!
            res = self.send(cr, uid, ids, auto_commit=True, context=context)
        except Exception:
            _logger.exception("Failed processing mail queue")
        return res

    def parse_message(self, message, save_original=False, context=None):
        """Parses a string or email.message.Message representing an
           RFC-2822 email, and returns a generic dict holding the
           message details.

           :param message: the message to parse
           :type message: email.message.Message | string | unicode
           :param bool save_original: whether the returned dict
               should include an ``original`` entry with the base64
               encoded source of the message.
           :rtype: dict
           :return: A dict with the following structure, where each
                    field may not be present if missing in original
                    message::

                    { 'message-id': msg_id,
                      'subject': subject,
                      'from': from,
                      'to': to,
                      'cc': cc,
                      'headers' : { 'X-Mailer': mailer,
                                    #.. all X- headers...
                                  },
                      'content_subtype': msg_mime_subtype,
                      'body_text': plaintext_body
                      'body_html': html_body,
                      'attachments': [('file1', 'bytes'),
                                       ('file2', 'bytes') }
                       # ...
                       'original': source_of_email,
                    }
        """
        msg_txt = message
        if isinstance(message, str):
            msg_txt = email.message_from_string(message)

        # Warning: message_from_string doesn't always work correctly on unicode,
        # we must use utf-8 strings here :-(
        if isinstance(message, unicode):
            message = message.encode('utf-8')
            msg_txt = email.message_from_string(message)

        message_id = msg_txt.get('message-id', False)
        msg = {}

        if save_original:
            # save original, we need to be able to read the original email sometimes
            msg['original'] = message.as_string() if isinstance(message, Message) \
                                                  else message
            msg['original'] = base64.b64encode(msg['original']) # binary fields are b64

        if not message_id:
            # Very unusual situation, be we should be fault-tolerant here
            message_id = time.time()
            msg_txt['message-id'] = message_id
            _logger.info('Parsing Message without message-id, generating a random one: %s', message_id)

        msg_fields = msg_txt.keys()
        msg['id'] = message_id
        msg['message-id'] = message_id

        if 'Subject' in msg_fields:
            msg['subject'] = decode(msg_txt.get('Subject'))

        if 'Content-Type' in msg_fields:
            msg['content-type'] = msg_txt.get('Content-Type')

        if 'From' in msg_fields:
            msg['from'] = decode(msg_txt.get('From') or msg_txt.get_unixfrom())

        if 'To' in msg_fields:
            msg['to'] = decode(msg_txt.get('To'))

        if 'Delivered-To' in msg_fields:
            msg['to'] = decode(msg_txt.get('Delivered-To'))

        if 'CC' in msg_fields:
            msg['cc'] = decode(msg_txt.get('CC'))

        if 'Cc' in msg_fields:
            msg['cc'] = decode(msg_txt.get('Cc'))

        if 'Reply-To' in msg_fields:
            msg['reply'] = decode(msg_txt.get('Reply-To'))

        if 'Date' in msg_fields:
            date_hdr = decode(msg_txt.get('Date'))
            # convert from email timezone to server timezone
            date_server_datetime = dateutil.parser.parse(date_hdr).astimezone(pytz.timezone(tools.get_server_timezone()))
            date_server_datetime_str = date_server_datetime.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
            msg['date'] = date_server_datetime_str

        if 'Content-Transfer-Encoding' in msg_fields:
            msg['encoding'] = msg_txt.get('Content-Transfer-Encoding')

        if 'References' in msg_fields:
            msg['references'] = msg_txt.get('References')

        if 'In-Reply-To' in msg_fields:
            msg['in-reply-to'] = msg_txt.get('In-Reply-To')

        msg['headers'] = {}
        msg['content_subtype'] = 'plain'
        for item in msg_txt.items():
            if item[0].startswith('X-'):
                msg['headers'].update({item[0]: item[1]})
        if not msg_txt.is_multipart() or 'text/plain' in msg.get('content-type', ''):
            encoding = msg_txt.get_content_charset()
            body = msg_txt.get_payload(decode=True)
            if 'text/html' in msg.get('content-type', ''):
                msg['body_html'] =  body
                msg['content_subtype'] = 'html'
                if body:
                    body = tools.html2plaintext(body)
            msg['body_text'] = tools.ustr(body, encoding)

        attachments = []
        if msg_txt.is_multipart() or 'multipart/alternative' in msg.get('content-type', ''):
            body = ""
            if 'multipart/alternative' in msg.get('content-type', ''):
                msg['content_subtype'] = 'alternative'
            else:
                msg['content_subtype'] = 'mixed'
            for part in msg_txt.walk():
                if part.get_content_maintype() == 'multipart':
                    continue

                encoding = part.get_content_charset()
                filename = part.get_filename()
                if part.get_content_maintype()=='text':
                    content = part.get_payload(decode=True)
                    if filename:
                        attachments.append((filename, content))
                    content = tools.ustr(content, encoding)
                    if part.get_content_subtype() == 'html':
                        msg['body_html'] = content
                        msg['content_subtype'] = 'html' # html version prevails
                        body = tools.ustr(tools.html2plaintext(content))
                        body = body.replace('&#13;', '')
                    elif part.get_content_subtype() == 'plain':
                        body = content
                elif part.get_content_maintype() in ('application', 'image'):
                    if filename :
                        attachments.append((filename,part.get_payload(decode=True)))
                    else:
                        res = part.get_payload(decode=True)
                        body += tools.ustr(res, encoding)

            msg['body_text'] = body
        msg['attachments'] = attachments

        # for backwards compatibility:
        msg['body'] = msg['body_text']
        msg['sub_type'] = msg['content_subtype'] or 'plain'
        return msg

    def _postprocess_sent_message(self, cr, uid, message, context=None):
        """Perform any post-processing necessary after sending ``message``
        successfully, including deleting it completely along with its
        attachment if the ``auto_delete`` flag of the message was set.
        Overridden by subclasses for extra post-processing behaviors. 

        :param browse_record message: the message that was just sent
        :return: True
        """
        if message.auto_delete:
            self.pool.get('ir.attachment').unlink(cr, uid,
                [x.id for x in message.attachment_ids
                    if x.res_model == self._name and x.res_id == message.id],
                context=context)
            message.unlink()
        return True

    def send(self, cr, uid, ids, auto_commit=False, context=None):
        """Sends the selected emails immediately, ignoring their current
           state (mails that have already been sent should not be passed
           unless they should actually be re-sent).
           Emails successfully delivered are marked as 'sent', and those
           that fail to be deliver are marked as 'exception', and the
           corresponding error message is output in the server logs.

           :param bool auto_commit: whether to force a commit of the message
                                    status after sending each message (meant
                                    only for processing by the scheduler),
                                    should never be True during normal
                                    transactions (default: False)
           :return: True
        """
        ir_mail_server = self.pool.get('ir.mail_server')
        self.write(cr, uid, ids, {'state': 'outgoing'}, context=context)
        for message in self.browse(cr, uid, ids, context=context):
            try:
                attachments = []
                for attach in message.attachment_ids:
                    attachments.append((attach.datas_fname, base64.b64decode(attach.datas)))

                body = message.body_html if message.content_subtype == 'html' else message.body_text
                body_alternative = None
                content_subtype_alternative = None
                if message.content_subtype == 'html' and message.body_text:
                    # we have a plain text alternative prepared, pass it to 
                    # build_message instead of letting it build one
                    body_alternative = message.body_text
                    content_subtype_alternative = 'plain'

                # handle destination_partners
                partner_ids_email_to = ''
                for partner in message.partner_ids:
                    partner_ids_email_to += '%s ' % (partner.email or '')
                message_email_to = '%s %s' % (partner_ids_email_to, message.email_to or '')

                # build an RFC2822 email.message.Message object and send it
                # without queuing
                msg = ir_mail_server.build_email(
                    email_from=message.email_from,
                    email_to=mail_tools_to_email(message_email_to),
                    subject=message.subject,
                    body=body,
                    body_alternative=body_alternative,
                    email_cc=mail_tools_to_email(message.email_cc),
                    email_bcc=mail_tools_to_email(message.email_bcc),
                    reply_to=message.reply_to,
                    attachments=attachments, message_id=message.message_id,
                    references = message.references,
                    object_id=message.res_id and ('%s-%s' % (message.res_id,message.model)),
                    subtype=message.content_subtype,
                    subtype_alternative=content_subtype_alternative,
                    headers=message.headers and ast.literal_eval(message.headers))
                res = ir_mail_server.send_email(cr, uid, msg,
                                                mail_server_id=message.mail_server_id.id,
                                                context=context)
                if res:
                    message.write({'state':'sent', 'message_id': res, 'email_to': message_email_to})
                else:
                    message.write({'state':'exception', 'email_to': message_email_to})
                message.refresh()
                if message.state == 'sent':
                    self._postprocess_sent_message(cr, uid, message, context=context)
            except Exception:
                _logger.exception('failed sending mail.message %s', message.id)
                message.write({'state':'exception'})

            if auto_commit == True:
                cr.commit()
        return True



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
