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

# import ast
import base64
import logging
import tools

from osv import osv
from osv import fields
from tools.translate import _

_logger = logging.getLogger(__name__)

class mail_mail(osv.Model):
    """ Model holding RFC2822 email messages to send. This model also provides
        facilities to queue and send new email messages.  """
    _name = 'mail.mail'
    _description = 'Outgoing Mails'
    _inherits = {'mail.message': 'mail_message_id'}
    _order = 'id desc'

    _columns = {
        'mail_message_id': fields.many2one('mail.message', 'Message', required=True, ondelete='cascade'),
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
        'references': fields.text('References', help='Message references, such as identifiers of previous messages', readonly=1),
        'email_from': fields.char('From', help='Message sender, taken from user preferences.'),
        'email_to': fields.text('To', help='Message recipients'),
        'email_cc': fields.char('Cc', help='Carbon copy message recipients'),
        'reply_to': fields.char('Reply-To', help='Preferred response address for the message'),
        'body_html': fields.text('Rich-text Contents', help="Rich-text/HTML message"),

        # Auto-detected based on create() - if 'mail_message_id' was passed then this mail is a notification
        # and during unlink() we will cascade delete the parent and its attachments 
        'notification': fields.boolean('Is Notification') 
    }

    def _get_default_from(self, cr, uid, context=None):
        cur = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if not cur.alias_domain:
            raise osv.except_osv(_('Invalid Action!'), _('Unable to send email, set an alias domain in your server settings.'))
        return cur.alias_name + '@' + cur.alias_domain

    _defaults = {
        'state': 'outgoing',
        'email_from': lambda self, cr, uid, ctx=None: self._get_default_from(cr, uid, ctx),
    }

    def create(self, cr, uid, values, context=None):
        if 'notification' not in values and values.get('mail_message_id'):
            values['notification'] = True
        return super(mail_mail,self).create(cr, uid, values, context=context)

    def unlink(self, cr, uid, ids, context=None):
        # cascade-delete the parent message for all mails that are not created for a notification
        ids_to_cascade = self.search(cr, uid, [('notification','=',False),('id','in',ids)])
        parent_msg_ids = [m.mail_message_id.id for m in self.browse(cr, uid, ids_to_cascade, context=context)]
        res = super(mail_mail,self).unlink(cr, uid, ids, context=context)
        self.pool.get('mail.message').unlink(cr, uid, parent_msg_ids, context=context)
        return res

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

    def _postprocess_sent_message(self, cr, uid, mail, context=None):
        """Perform any post-processing necessary after sending ``mail``
        successfully, including deleting it completely along with its
        attachment if the ``auto_delete`` flag of the mail was set.
        Overridden by subclasses for extra post-processing behaviors. 

        :param browse_record mail: the mail that was just sent
        :return: True
        """
        if mail.auto_delete:
            mail.unlink()
        return True

    def _send_get_mail_subject(self, cr, uid, mail, force=False, context=None):
        """ if void and related document: '<Author> posted on <Resource>'
            :param mail: mail.mail browse_record """
        if force or (not mail.subject and mail.model and mail.res_id):
            return '%s posted on %s' % (mail.author_id.name, mail.record_name)
        return mail.subject

    def send(self, cr, uid, ids, auto_commit=False, context=None):
        """ Sends the selected emails immediately, ignoring their current
            state (mails that have already been sent should not be passed
            unless they should actually be re-sent).
            Emails successfully delivered are marked as 'sent', and those
            that fail to be deliver are marked as 'exception', and the
            corresponding error mail is output in the server logs.

            :param bool auto_commit: whether to force a commit of the mail status
                after sending each mail (meant only for scheduler processing);
                should never be True during normal transactions (default: False)
            :return: True
        """
        ir_mail_server = self.pool.get('ir.mail_server')
        for mail in self.browse(cr, uid, ids, context=context):
            try:
                body = mail.body_html
                subject = self._send_get_mail_subject(cr, uid, mail, context=context)

                # handle attachments
                attachments = []
                for attach in mail.attachment_ids:
                    attachments.append((attach.datas_fname, base64.b64decode(attach.datas)))

                # use only sanitized html and set its plaintexted version as alternative
                body_alternative = tools.html2plaintext(body)
                content_subtype_alternative = 'plain'

                # build an RFC2822 email.message.Message object and send it without queuing
                msg = ir_mail_server.build_email(
                    email_from = mail.email_from,
                    email_to = tools.email_split(mail.email_to),
                    subject = subject,
                    body = body,
                    body_alternative = body_alternative,
                    email_cc = tools.email_split(mail.email_cc),
                    reply_to = mail.reply_to,
                    attachments = attachments,
                    message_id = mail.message_id,
                    references = mail.references,
                    object_id = mail.res_id and ('%s-%s' % (mail.res_id, mail.model)),
                    subtype = 'html',
                    subtype_alternative = content_subtype_alternative)
                res = ir_mail_server.send_email(cr, uid, msg,
                    mail_server_id=mail.mail_server_id.id, context=context)
                if res:
                    mail.write({'state':'sent', 'message_id': res})
                else:
                    mail.write({'state':'exception'})
                mail.refresh()
                if mail.state == 'sent':
                    self._postprocess_sent_message(cr, uid, mail, context=context)
            except Exception:
                _logger.exception('failed sending mail.mail %s', mail.id)
                mail.write({'state':'exception'})

            if auto_commit == True:
                cr.commit()
        return True
