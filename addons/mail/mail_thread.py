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

import base64
import email
from email.utils import parsedate
import logging
from mail_message import decode, to_email
from operator import itemgetter
from osv import osv, fields
import re
import time
import tools
from tools.translate import _
import xmlrpclib

_logger = logging.getLogger(__name__)

class mail_thread(osv.osv):
    '''Mixin model, meant to be inherited by any model that needs to
       act as a discussion topic on which messages can be attached.
       Public methods are prefixed with ``message_`` in order to avoid
       name collisions with methods of the models that will inherit
       from this mixin.

       ``mail.thread`` is designed to work without adding any field
       to the extended models. All functionalities and expected behavior
       are managed by mail.thread, using model name and record ids.
       A widget has been designed for the 6.1 and following version of OpenERP
       web-client. However, due to technical limitations, ``mail.thread``
       adds a simulated one2many field, to display the web widget by
       overriding the default field displayed. Using this field
       is not recommanded has it will disappeear in future version
       of OpenERP, leading to a pure mixin class.

       Inheriting classes are not required to implement any method, as the
       default implementation will work for any model. However it is common
       to override at least the ``message_new`` and ``message_update``
       methods (calling ``super``) to add model-specific behavior at
       creation and update of a thread; and ``message_get_subscribers``
       to manage more precisely the social aspect of the thread through
       the followers.
    '''
    _name = 'mail.thread'
    _description = 'Email Thread'

    def _get_message_ids(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for id in ids:
            res[id] = self.message_load_ids(cr, uid, [id], context=context)
        return res

    # OpenChatter: message_ids is a dummy field that should not be used
    _columns = {
        'message_ids': fields.function(_get_message_ids, method=True,
                        type='one2many', obj='mail.message', string='Temp messages', _fields_id = 'res_id'),
        'message_ids': fields.one2many('mail.message', 'res_id', 'Messages', domain=[('model','=',_name)]),
    }

    #------------------------------------------------------
    # Automatic subscription when creating/reading
    #------------------------------------------------------

    def create(self, cr, uid, vals, context=None):
        """Automatically subscribe the creator"""
        thread_id = super(mail_thread, self).create(cr, uid, vals, context=context);
        self.message_subscribe(cr, uid, [thread_id], [uid], context=context)
        return thread_id;

    def write(self, cr, uid, ids, vals, context=None):
        """Automatically subscribe the writer"""
        if isinstance(ids, (int, long)):
            ids = [ids]
        write_res = super(mail_thread, self).write(cr, uid, ids, vals, context=context);
        if write_res:
            self.message_subscribe(cr, uid, ids, [uid], context=context)
        return write_res;

    def unlink(self, cr, uid, ids, context=None):
        """Override unlink, to automatically delete
           - subscriptions
           - messages
           that are linked with res_model and res_id, not through
           a foreign key with a 'cascade' ondelete attribute.
           Notifications will be deleted with messages
        """
        if context is None:
            context = {}
        subscr_obj = self.pool.get('mail.subscription')
        msg_obj = self.pool.get('mail.message')
        # delete subscriptions
        subscr_to_del_ids = subscr_obj.search(cr, uid, [('res_model', '=', self._name), ('res_id', 'in', ids)], context=context)
        subscr_obj.unlink(cr, uid, subscr_to_del_ids, context=context)
        # delete notifications
        msg_to_del_ids = msg_obj.search(cr, uid, [('model', '=', self._name), ('res_id', 'in', ids)], context=context)
        msg_obj.unlink(cr, uid, msg_to_del_ids, context=context)

        return super(mail_thread, self).unlink(cr, uid, ids, context=context)

    #------------------------------------------------------
    # Generic message api
    #------------------------------------------------------

    def message_create(self, cr, uid, thread_id, vals, context=None):
        """OpenSocial: wrapper of mail.message create method
           - creates the mail.message
           - automatically subscribe the message writer
           - push the message to subscribed users
        """
        if context is None:
            context = {}
        message_obj = self.pool.get('mail.message')
        subscription_obj = self.pool.get('mail.subscription')
        notification_obj = self.pool.get('mail.notification')
        res_users_obj = self.pool.get('res.users')
        body = vals.get('body_html', '') if vals.get('subtype', 'plain') == 'html' else vals.get('body_text', '')

        # automatically subscribe the writer of the message
        if vals['user_id']:
            self.message_subscribe(cr, uid, [thread_id], [vals['user_id']], context=context)

        # get users that will get a notification pushed
        user_to_push_ids = self.message_create_get_notification_user_ids(cr, uid, [thread_id], vals, context=context)
        user_to_push_from_parse_ids = self.message_parse_users(cr, uid, [thread_id], body, context=context)

        # set email_from and email_to for comments and notifications
        if vals.get('type', False) and vals['type'] == 'comment' or vals['type'] == 'notification':
            current_user = res_users_obj.browse(cr, uid, [uid], context=context)[0]
            if not vals.get('email_from', False):
                vals['email_from'] = current_user.user_email
            if not vals.get('email_to', False):
                email_to = ''
                for user in res_users_obj.browse(cr, uid, user_to_push_ids, context=context):
                    if not user.notification_email_pref == 'all' and \
                        not (user.notification_email_pref == 'comments' and vals['type'] == 'comment') and \
                        not (user.notification_email_pref == 'to_me' and user.id in user_to_push_from_parse_ids):
                        continue
                    if not user.user_email:
                        continue
                    email_to = '%s, %s' % (email_to, user.user_email)
                email_to = email_to.lstrip(', ')
                if email_to:
                    vals['email_to'] = email_to
                    vals['state'] = 'outgoing'

        # create message
        msg_id = message_obj.create(cr, uid, vals, context=context)

        # special: if install mode, do not push demo data
        if context.get('install_mode', False):
            return True

        # push to users
        for id in user_to_push_ids:
            notification_obj.create(cr, uid, {'user_id': id, 'message_id': msg_id}, context=context)

        return msg_id

    def message_create_get_notification_user_ids(self, cr, uid, thread_ids, new_msg_vals, context=None):
        if context is None:
            context = {}

        notif_user_ids = []
        body = new_msg_vals.get('body_html', '') if new_msg_vals.get('subtype', 'plain') == 'html' else new_msg_vals.get('body_text', '')
        for thread_id in thread_ids:
            # add subscribers
            notif_user_ids += [user['id'] for user in self.message_get_subscribers(cr, uid, [thread_id], context=context)]
            # add users requested via parsing message (@login)
            notif_user_ids += self.message_parse_users(cr, uid, [thread_id], body, context=context)
            # add users requested to perform an action (need_action mechanism)
            if hasattr(self, 'get_needaction_user_ids'):
                notif_user_ids += self.get_needaction_user_ids(cr, uid, [thread_id], context=context)[thread_id]
            # add users notified of the parent messages (because: if parent message contains @login, login must receive the replies)
            if new_msg_vals.get('parent_id'):
                notif_obj = self.pool.get('mail.notification')
                parent_notif_ids = notif_obj.search(cr, uid, [('message_id', '=', new_msg_vals.get('parent_id'))], context=context)
                parent_notifs = notif_obj.read(cr, uid, parent_notif_ids, context=context)
                notif_user_ids += [parent_notif['user_id'][0] for parent_notif in parent_notifs]

        # remove duplicate entries
        notif_user_ids = list(set(notif_user_ids))
        return notif_user_ids

    def message_parse_users(self, cr, uid, ids, string, context=None):
        """Parse message content
           - if find @login -(^|\s)@((\w|@|\.)*)-: returns the related ids
             this supports login that are emails (such as @admin@lapin.net)
        """
        regex = re.compile('(^|\s)@((\w|@|\.)*)')
        login_lst = [item[1] for item in regex.findall(string)]
        if not login_lst: return []
        user_ids = self.pool.get('res.users').search(cr, uid, [('login', 'in', login_lst)], context=context)
        return user_ids

    def message_capable_models(self, cr, uid, context=None):
        ret_dict = {}
        for model_name in self.pool.obj_list():
            model = self.pool.get(model_name)
            if 'mail.thread' in getattr(model, '_inherit', []):
                ret_dict[model_name] = model._description
        return ret_dict

    def message_append(self, cr, uid, threads, subject, body_text=None, body_html=None,
                        parent_id=False, type='email', subtype='plain', state='received',
                        email_to=False, email_from=False, email_cc=None, email_bcc=None,
                        reply_to=None, email_date=None, message_id=False, references=None,
                        attachments=None, headers=None, original=None, context=None):
        """Creates a new mail.message attached to the current mail.thread,
           containing all the details passed as parameters.  All attachments
           will be attached to the thread record as well as to the actual
           message.
           If ``email_from`` is not set or ``type`` not set as 'email',
           a note message is created, without the usual envelope
           attributes (sender, recipients, etc.).
           The creation of the message is done by calling ``message_create``
           method, that will manage automatic pushing of notifications.

        :param threads: list of thread ids, or list of browse_records representing
                        threads to which a new message should be attached
        :param subject: subject of the message, or description of the event if this
                        is an *event log* entry.
        :param body_text: plaintext contents of the mail or log message
        :param body_html: html contents of the mail or log message
        :param parent_id: id of the parent message (threaded messaging model)
        :param type: optional type of message: 'email', 'comment', 'notification'
        :param subtype: optional subtype of message: 'plain' or 'html', corresponding to the main
                        body contents (body_text or body_html).
        :param state: optional state of message; 'received' by default
        :param email_to: Email-To / Recipient address
        :param email_from: Email From / Sender address if any
        :param email_cc: Comma-Separated list of Carbon Copy Emails To addresse if any
        :param email_bcc: Comma-Separated list of Blind Carbon Copy Emails To addresses if any
        :param reply_to: reply_to header
        :param email_date: email date string if different from now, in server timezone
        :param message_id: optional email identifier
        :param references: optional email references
        :param headers: mail headers to store
        :param dict attachments: map of attachment filenames to binary contents, if any.
        :param str original: optional full source of the RFC2822 email, for reference
        :param dict context: if a ``thread_model`` value is present
                             in the context, its value will be used
                             to determine the model of the thread to
                             update (instead of the current model).
        """
        if context is None:
            context = {}
        if attachments is None:
            attachments = {}

        if email_date:
            edate = parsedate(email_date)
            if edate is not None:
                email_date = time.strftime('%Y-%m-%d %H:%M:%S', edate)

        if all(isinstance(thread_id, (int, long)) for thread_id in threads):
            model = context.get('thread_model') or self._name
            model_pool = self.pool.get(model)
            threads = model_pool.browse(cr, uid, threads, context=context)

        ir_attachment = self.pool.get('ir.attachment')
        mail_message = self.pool.get('mail.message')

        new_msg_ids = []
        for thread in threads:
            to_attach = []
            for attachment in attachments:
                fname, fcontent = attachment
                if isinstance(fcontent, unicode):
                    fcontent = fcontent.encode('utf-8')
                data_attach = {
                    'name': fname,
                    'datas': base64.b64encode(str(fcontent)),
                    'datas_fname': fname,
                    'description': _('Mail attachment'),
                    'res_model': thread._name,
                    'res_id': thread.id,
                }
                to_attach.append(ir_attachment.create(cr, uid, data_attach, context=context))

            partner_id = hasattr(thread, 'partner_id') and (thread.partner_id and thread.partner_id.id or False) or False
            if not partner_id and thread._name == 'res.partner':
                partner_id = thread.id
            data = {
                'subject': subject,
                'body_text': body_text or (hasattr(thread, 'description') and thread.description or ''),
                'body_html': body_html or '',
                'parent_id': parent_id,
                'date': email_date or fields.datetime.now(),
                'type': type,
                'subtype': subtype,
                'state': state,
                'message_id': message_id,
                'attachment_ids': [(6, 0, to_attach)],
                'user_id': uid,
                'model' : thread._name,
                'res_id': thread.id,
                'partner_id': partner_id,
            }

            if email_from or type == 'email':
                for param in (email_to, email_cc, email_bcc):
                    if isinstance(param, list):
                        param = ", ".join(param)
                data.update({
                    'subject': subject or _('History'),
                    'email_to': email_to,
                    'email_from': email_from or \
                        (hasattr(thread, 'user_id') and thread.user_id and thread.user_id.user_email),
                    'email_cc': email_cc,
                    'email_bcc': email_bcc,
                    'references': references,
                    'headers': headers,
                    'reply_to': reply_to,
                    'original': original, })

            new_msg_ids.append(self.message_create(cr, uid, thread.id, data, context=context))
        return new_msg_ids

    def message_append_dict(self, cr, uid, ids, msg_dict, context=None):
        """Creates a new mail.message attached to the given threads (``ids``),
           with the contents of ``msg_dict``, by calling ``message_append``
           with the mail details. All attachments in msg_dict will be
           attached to the object record as well as to the actual
           mail message.

           :param dict msg_dict: a map containing the email details and
                                 attachments. See ``message_process()`` and
                                ``mail.message.parse()`` for details on
                                the dict structure.
           :param dict context: if a ``thread_model`` value is present
                                in the context, its value will be used
                                to determine the model of the thread to
                                update (instead of the current model).
        """
        return self.message_append(cr, uid, ids,
                            subject = msg_dict.get('subject'),
                            body_text = msg_dict.get('body_text'),
                            body_html= msg_dict.get('body_html'),
                            parent_id = msg_dict.get('parent_id', False),
                            type = msg_dict.get('type', 'email'),
                            subtype = msg_dict.get('subtype', 'plain'),
                            state = msg_dict.get('state', 'received'),
                            email_from = msg_dict.get('from', msg_dict.get('email_from')),
                            email_to = msg_dict.get('to', msg_dict.get('email_to')),
                            email_cc = msg_dict.get('cc', msg_dict.get('email_cc')),
                            email_bcc = msg_dict.get('bcc', msg_dict.get('email_bcc')),
                            reply_to = msg_dict.get('reply', msg_dict.get('reply_to')),
                            email_date = msg_dict.get('date'),
                            message_id = msg_dict.get('message-id', msg_dict.get('message_id')),
                            references = msg_dict.get('references')\
                                      or msg_dict.get('in-reply-to'),
                            attachments = msg_dict.get('attachments'),
                            headers = msg_dict.get('headers'),
                            original = msg_dict.get('original'),
                            context = context)

    # Message loading
    def _message_add_ancestor_ids(self, cr, uid, ids, child_ids, root_ids, context=None):
        """ Given message child_ids
            Find their ancestors until root ids"""
        if context is None:
            context = {}
        msg_obj = self.pool.get('mail.message')
        tmp_msgs = msg_obj.read(cr, uid, child_ids, ['id', 'parent_id'], context=context)
        parent_ids = [msg['parent_id'][0] for msg in tmp_msgs if msg['parent_id'] and msg['parent_id'][0] not in root_ids and msg['parent_id'][0] not in child_ids]
        child_ids += parent_ids
        cur_iter = 0; max_iter = 100; # avoid infinite loop
        while (parent_ids and (cur_iter < max_iter)):
            cur_iter += 1
            tmp_msgs = msg_obj.read(cr, uid, parent_ids, ['id', 'parent_id'], context=context)
            parent_ids = [msg['parent_id'][0] for msg in tmp_msgs if msg['parent_id'] and msg['parent_id'][0] not in root_ids and msg['parent_id'][0] not in child_ids]
            child_ids += parent_ids
        if (cur_iter > max_iter):
            _logger.warning("Possible infinite loop in _message_add_ancestor_ids. Note that this algorithm is intended to check for cycle in message graph.")
        return child_ids

    def message_load_ids(self, cr, uid, ids, limit=100, offset=0, domain=[], ascent=False, root_ids=[], context=None):
        """ OpenChatter feature: return thread messages ids. It searches in
            mail.messages where res_id = ids, (res_)model = current model.
            :param domain: domain to add to the search; especially child_of
                           is interesting when dealing with threaded display
            :param ascent: performs an ascended search; will add to fetched msgs
                           all their parents until root_ids
            :param root_ids: for ascent search
            :param root_ids: root_ids when performing an ascended search
        """
        if context is None:
            context = {}
        msg_obj = self.pool.get('mail.message')
        msg_ids = msg_obj.search(cr, uid, ['&', ('res_id', 'in', ids), ('model', '=', self._name)] + domain,
            limit=limit, offset=offset, context=context)
        if (ascent): msg_ids = self._message_add_ancestor_ids(cr, uid, ids, msg_ids, root_ids, context=context)
        return msg_ids

    def message_load(self, cr, uid, ids, limit=100, offset=0, domain=[], ascent=False, root_ids=[], context=None):
        """ OpenChatter feature: return thread messages
        """
        msg_ids = self.message_load_ids(cr, uid, ids, limit, offset, domain, ascent, root_ids, context=context)
        msgs = self.pool.get('mail.message').read(cr, uid, msg_ids, context=context)
        msgs = sorted(msgs, key=lambda d: (-d['id']))
        return msgs

    def get_pushed_messages(self, cr, uid, ids, limit=100, offset=0, msg_search_domain=[], ascent=False, root_ids=[], context=None):
        """ OpenChatter: wall: get messages to display (=pushed notifications)
            :param domain: domain to add to the search; especially child_of
                           is interesting when dealing with threaded display
            :param ascent: performs an ascended search; will add to fetched msgs
                           all their parents until root_ids
            :param root_ids: for ascent search
            :return list of mail.messages sorted by date
        """
        if context is None: context = {}
        notification_obj = self.pool.get('mail.notification')
        msg_obj = self.pool.get('mail.message')
        # update message search
        for arg in msg_search_domain:
            if isinstance(arg, (tuple, list)):
                arg[0] = 'message_id.' + arg[0]
        # compose final domain
        domain = [('user_id', '=', uid)] + msg_search_domain
        # get notifications
        notification_ids = notification_obj.search(cr, uid, domain, limit=limit, offset=offset, context=context)
        notifications = notification_obj.browse(cr, uid, notification_ids, context=context)
        msg_ids = [notification.message_id.id for notification in notifications]
        # get messages
        msg_ids = msg_obj.search(cr, uid, [('id', 'in', msg_ids)], context=context)
        if (ascent): msg_ids = self._message_add_ancestor_ids(cr, uid, ids, msg_ids, root_ids, context=context)
        msgs = msg_obj.read(cr, uid, msg_ids, context=context)
        return msgs


    def _get_user(self, cr, uid, alias, context):
        """
            param alias: browse record of alias.
            return: int user_id.
        """

        user_obj = self.pool.get('res.user')
        user_id = 1
        if alias.alias_user_id:
            user_id = alias_id.alias_user_id.id
        #if user_id not defined in the alias then search related user using name of Email sender
        else:
            from_email = msg.get('from')
            user_ids = user_obj.search(cr, uid, [('name','=',from_email)], context)
            if user_ids:
                user_id = user_obj.browse(cr, uid, user_ids[0], context).id
        return user_id

    def message_catchall(self, cr, uid, message, context=None):
        """
            Process incoming mail and call messsage_process using details of the mail.alias model
            else raise Exception so that mailgate script will reject the mail and
            send notification mail sender that this mailbox does not exist so your mail have been rejected.
        """

        alias_obj = self.pool.get('mail.alias')
        user_obj = self.pool.get('res.user')
        mail_message = self.pool.get('mail.compose.message')

        if isinstance(message, xmlrpclib.Binary):
            message = str(message.data)

        # Parse Message
        # Warning: message_from_string doesn't always work correctly on unicode,
        # we must use utf-8 strings here :-(
        if isinstance(message, unicode):
            message = message.encode('utf-8')
        msg_txt = email.message_from_string(message)
        msg = mail_message.parse_message(msg_txt, save_original=save_original)

        alias_name = msg.get('to')
        alias_ids = mail_alias.search(cr, uid, [('alias_name','=',alias_name)],context)
        alias_id = mail_alias.browse(cr, uid, alias_ids[0], context)
        #if alias found then call message_process method.
        if alias_id:
            user_id = self._get_user(self, cr, uid, alias_id, context)
            self.message_process(self, cr, user_id, alias_id.alias_model_id.id, message, custom_values = alias_id.alias_defaults or {}, thread_id = alias_id.alias_force_thread_id or {}, context=context)
        #if alis not found give Exception
        else:
            #_logger.warning("This mailbox does not exist so mail gate will reject this mail.")
            from_email = user_obj.browse(cr, uid, uid, context).user_email
            sub = "Mail Rejection" + msg.get('subject')
            message = "Respective mailbox does not exist so your mail have been rejected" + msg
            mail_message.send_mail(cr, uid, {'email_from': from_email,'email_to': msg.get('from'),'subject': sub, 'body_text': message}, context)

        return True

    #------------------------------------------------------
    # Email specific
    #------------------------------------------------------
    # message_process will call either message_new or message_update.

    def message_process(self, cr, uid, model, message, custom_values=None,
                        save_original=False, strip_attachments=False,
                        thread_id=None, context=None):
        """Process an incoming RFC2822 email message related to the
           given thread model, relying on ``mail.message.parse()``
           for the parsing operation, and then calling ``message_new``
           (if the thread record did not exist) or ``message_update``
           (if it did), then calling ``message_forward`` to automatically
           notify other people that should receive this message.

           :param string model: the thread model for which a new message
                                must be processed
           :param message: source of the RFC2822 mail
           :type message: string or xmlrpclib.Binary
           :type dict custom_values: optional dictionary of field values
                                    to pass to ``message_new`` if a new
                                    record needs to be created. Ignored
                                    if the thread record already exists.
           :param bool save_original: whether to keep a copy of the original
               email source attached to the message after it is imported.
           :param bool strip_attachments: whether to strip all attachments
               before processing the message, in order to save some space.
           :param int thread_id: optional ID of the record/thread from ``model``
               to which this mail should be attached. When provided, this
               overrides the automatic detection based on the message
               headers.
        """
        # extract message bytes - we are forced to pass the message as binary because
        # we don't know its encoding until we parse its headers and hence can't
        # convert it to utf-8 for transport between the mailgate script and here.
        if isinstance(message, xmlrpclib.Binary):
            message = str(message.data)

        if context is None: context = {}

        mail_message = self.pool.get('mail.message')
        model_pool = self.pool.get(model)
        if self._name != model:
            context.update({'thread_model': model})

        # Parse Message
        # Warning: message_from_string doesn't always work correctly on unicode,
        # we must use utf-8 strings here :-(
        if isinstance(message, unicode):
            message = message.encode('utf-8')
        msg_txt = email.message_from_string(message)
        msg = mail_message.parse_message(msg_txt, save_original=save_original)

        if strip_attachments and 'attachments' in msg:
            del msg['attachments']

        # Create New Record into particular model
        def create_record(msg):
            if hasattr(model_pool, 'message_new'):
                return model_pool.message_new(cr, uid, msg,
                                              custom_values,
                                              context=context)
        if not thread_id and (msg.get('references') or msg.get('in-reply-to')):
            references = msg.get('references') or msg.get('in-reply-to')
            if '\r\n' in references:
                references = references.split('\r\n')
            else:
                references = references.split(' ')
            for ref in references:
                ref = ref.strip()
                thread_id = tools.reference_re.search(ref)
                if not thread_id:
                    thread_id = tools.res_re.search(msg['subject'])
                if thread_id:
                    thread_id = int(thread_id.group(1))
                    if not model_pool.exists(cr, uid, thread_id) or \
                        not hasattr(model_pool, 'message_update'):
                            # referenced thread not found or not updatable,
                            # -> create a new one
                            thread_id = False
        if not thread_id:
            thread_id = create_record(msg)
        else:
            model_pool.message_update(cr, uid, [thread_id], msg, {}, context=context)
        #To forward the email to other followers
        self.message_forward(cr, uid, model, [thread_id], msg_txt, context=context)
        return thread_id

    def message_new(self, cr, uid, msg_dict, custom_values=None, context=None):
        """Called by ``message_process`` when a new message is received
           for a given thread model, if the message did not belong to
           an existing thread.
           The default behavior is to create a new record of the corresponding
           model (based on some very basic info extracted from the message),
           then attach the message to the newly created record
           (by calling ``message_append_dict``).
           Additional behavior may be implemented by overriding this method.

           :param dict msg_dict: a map containing the email details and
                                 attachments. See ``message_process`` and
                                ``mail.message.parse`` for details.
           :param dict custom_values: optional dictionary of additional
                                      field values to pass to create()
                                      when creating the new thread record.
                                      Be careful, these values may override
                                      any other values coming from the message.
           :param dict context: if a ``thread_model`` value is present
                                in the context, its value will be used
                                to determine the model of the record
                                to create (instead of the current model).
           :rtype: int
           :return: the id of the newly created thread object
        """
        if context is None:
            context = {}
        model = context.get('thread_model') or self._name
        model_pool = self.pool.get(model)
        fields = model_pool.fields_get(cr, uid, context=context)
        data = model_pool.default_get(cr, uid, fields, context=context)
        if 'name' in fields and not data.get('name'):
            data['name'] = msg_dict.get('from','')
        if custom_values and isinstance(custom_values, dict):
            data.update(custom_values)
        res_id = model_pool.create(cr, uid, data, context=context)
        self.message_append_dict(cr, uid, [res_id], msg_dict, context=context)
        return res_id

    def message_update(self, cr, uid, ids, msg_dict, vals={}, default_act=None, context=None):
        """Called by ``message_process`` when a new message is received
           for an existing thread. The default behavior is to create a
           new mail.message in the given thread (by calling
           ``message_append_dict``)
           Additional behavior may be implemented by overriding this
           method.

           :param dict msg_dict: a map containing the email details and
                                attachments. See ``message_process`` and
                                ``mail.message.parse()`` for details.
           :param dict context: if a ``thread_model`` value is present
                                in the context, its value will be used
                                to determine the model of the thread to
                                update (instead of the current model).
        """
        return self.message_append_dict(cr, uid, ids, msg_dict, context=context)

    def message_thread_followers(self, cr, uid, ids, context=None):
        """Returns a list of email addresses of the people following
           this thread, including the sender of each mail, and the
           people who were in CC of the messages, if any.
        """
        res = {}
        if isinstance(ids, (str, int, long)):
            ids = [long(ids)]
        for thread in self.browse(cr, uid, ids, context=context):
            l = set()
            for message in thread.message_ids:
                l.add((message.user_id and message.user_id.user_email) or '')
                l.add(message.email_from or '')
                l.add(message.email_cc or '')
            res[thread.id] = filter(None, l)
        return res

    def message_forward(self, cr, uid, model, thread_ids, msg, email_error=False, context=None):
        """Sends an email to all people following the given threads.
           The emails are forwarded immediately, not queued for sending,
           and not archived.

        :param str model: thread model
        :param list thread_ids: ids of the thread records
        :param msg: email.message.Message object to forward
        :param email_error: optional email address to notify in case
                            of any delivery error during the forward.
        :return: True
        """
        model_pool = self.pool.get(model)
        smtp_server_obj = self.pool.get('ir.mail_server')
        mail_message = self.pool.get('mail.message')
        for res in model_pool.browse(cr, uid, thread_ids, context=context):
            if hasattr(model_pool, 'message_thread_followers'):
                followers = model_pool.message_thread_followers(cr, uid, [res.id])[res.id]
            else:
                followers = self.message_thread_followers(cr, uid, [res.id])[res.id]
            message_followers_emails = to_email(','.join(filter(None, followers)))
            message_recipients = to_email(','.join(filter(None,
                                                                       [decode(msg['from']),
                                                                        decode(msg['to']),
                                                                        decode(msg['cc'])])))
            forward_to = [i for i in message_followers_emails if (i and (i not in message_recipients))]
            if forward_to:
                # TODO: we need an interface for this for all types of objects, not just leads
                if hasattr(res, 'section_id'):
                    del msg['reply-to']
                    msg['reply-to'] = res.section_id.reply_to

                smtp_from, = to_email(msg['from'])
                msg['from'] = smtp_from
                msg['to'] =  ", ".join(forward_to)
                msg['message-id'] = tools.generate_tracking_message_id(res.id)
                if not smtp_server_obj.send_email(cr, uid, msg) and email_error:
                    subj = msg['subject']
                    del msg['subject'], msg['to'], msg['cc'], msg['bcc']
                    msg['subject'] = _('[OpenERP-Forward-Failed] %s') % subj
                    msg['to'] = email_error
                    smtp_server_obj.send_email(cr, uid, msg)
        return True

    def message_partner_by_email(self, cr, uid, email, context=None):
        """Attempts to return the id of a partner address matching
           the given ``email``, and the corresponding partner id.
           Can be used by classes using the ``mail.thread`` mixin
           to lookup the partner and use it in their implementation
           of ``message_new`` to link the new record with a
           corresponding partner.
           The keys used in the returned dict are meant to map
           to usual names for relationships towards a partner
           and one of its addresses.

           :param email: email address for which a partner
                         should be searched for.
           :rtype: dict
           :return: a map of the following form::

                      { 'partner_address_id': id or False,
                        'partner_id': pid or False }
        """
        partner_pool = self.pool.get('res.partner')
        res = {'partner_id': False}
        if email:
            email = to_email(email)[0]
            contact_ids = partner_pool.search(cr, uid, [('email', '=', email)])
            if contact_ids:
                contact = partner_pool.browse(cr, uid, contact_ids[0])
                res['partner_id'] = contact.id
        return res

    # for backwards-compatibility with old scripts
    process_email = message_process

    #------------------------------------------------------
    # Note specific
    #------------------------------------------------------

    def message_broadcast(self, cr, uid, ids, subject=None, body=None, parent_id=False, type='notification', subtype='html', context=None):
        if context is None:
            context = {}
        notification_obj = self.pool.get('mail.notification')
        # write message
        msg_ids = self.message_append_note(cr, uid, ids, subject=subject, body=body, parent_id=parent_id, type=type, subtype=subtype, context=context)
        # escape if in install mode or note writing was not successfull
        if 'install_mode' in context:
            return True
        if not isinstance(msg_ids, (list)):
            return True
        # get already existing notigications
        notification_ids = notification_obj.search(cr, uid, [('message_id', 'in', msg_ids)], context=context)
        already_pushed_user_ids = map(itemgetter('user_id'), notification_obj.read(cr, uid, notification_ids, context=context))
        # get base.group_user group
        res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'base', 'group_user') or False
        group_id = res and res[1] or False
        if not group_id: return True
        group = self.pool.get('res.groups').browse(cr, uid, [group_id], context=context)[0]
        for user in group.users:
            if user.id in already_pushed_user_ids: continue
            for msg_id in msg_ids:
                notification_obj.create(cr, uid, {'user_id': user.id, 'message_id': msg_id}, context=context)
        return True

    def log(self, cr, uid, id, message, secondary=False, context=None):
        _logger.warning("log() is deprecated. Please use OpenChatter notification system instead of the res.log mechanism.")
        self.message_append_note(cr, uid, [id], 'res.log', message, context=context)

    def message_append_note(self, cr, uid, ids, subject=None, body=None, parent_id=False, type='notification', subtype='html', context=None):
        if subject is None:
            if type == 'notification':
                subject = _('System notification')
            elif type == 'comment' and not parent_id:
                subject = _('Comment')
            elif type == 'comment' and parent_id:
                subject = _('Reply')
        if subtype == 'html':
            body_html = body
            body_text = body
        else:
            body_html = body
            body_text = body
        return self.message_append(cr, uid, ids, subject, body_html=body_html, body_text=body_text, parent_id=parent_id, type=type, subtype=subtype, context=context)

    #------------------------------------------------------
    # Subscription mechanism
    #------------------------------------------------------

    def message_get_subscribers_ids(self, cr, uid, ids, context=None):
        subscr_obj = self.pool.get('mail.subscription')
        subscr_ids = subscr_obj.search(cr, uid, ['&', ('res_model', '=', self._name), ('res_id', 'in', ids)], context=context)
        subs = subscr_obj.read(cr, uid, subscr_ids, context=context)
        return [sub['user_id'][0] for sub in subs]

    def message_get_subscribers(self, cr, uid, ids, context=None):
        user_ids = self.message_get_subscribers_ids(cr, uid, ids, context=context)
        users = self.pool.get('res.users').read(cr, uid, user_ids, fields=['id', 'name', 'avatar'], context=context)
        return users

    def message_is_subscriber(self, cr, uid, ids, user_id = None, context=None):
        users = self.message_get_subscribers(cr, uid, ids, context=context)
        sub_user_id = uid if user_id is None else user_id
        if sub_user_id in [user['id'] for user in users]:
            return True
        return False

    def message_subscribe(self, cr, uid, ids, user_ids = None, context=None):
        subscription_obj = self.pool.get('mail.subscription')
        to_subscribe_uids = [uid] if user_ids is None else user_ids
        create_ids = []
        for id in ids:
            for user_id in to_subscribe_uids:
                if self.message_is_subscriber(cr, uid, [id], user_id=user_id, context=context): continue
                create_ids.append(subscription_obj.create(cr, uid, {'res_model': self._name, 'res_id': id, 'user_id': user_id}, context=context))
        return create_ids

    def message_unsubscribe(self, cr, uid, ids, user_ids = None, context=None):
        if not user_ids and not uid in self.message_get_subscribers_ids(cr, uid, ids, context=context):
            return False
        subscription_obj = self.pool.get('mail.subscription')
        to_unsubscribe_uids = [uid] if user_ids is None else user_ids
        to_delete_sub_ids = subscription_obj.search(cr, uid,
                        ['&', '&', ('res_model', '=', self._name), ('res_id', 'in', ids), ('user_id', 'in', to_unsubscribe_uids)], context=context)
        subscription_obj.unlink(cr, uid, to_delete_sub_ids, context=context)
        return True

    #------------------------------------------------------
    # Notification API
    #------------------------------------------------------

    def message_remove_pushed_notifications(self, cr, uid, ids, msg_ids, remove_childs=True, context=None):
        if context is None:
            context = {}
        notif_obj = self.pool.get('mail.notification')
        msg_obj = self.pool.get('mail.message')
        if remove_childs:
            notif_msg_ids = msg_obj.search(cr, uid, [('id', 'child_of', msg_ids)], context=context)
        else:
            notif_msg_ids = msg_ids
        to_del_notif_ids = notif_obj.search(cr, uid, ['&', ('user_id', '=', uid), ('message_id', 'in', notif_msg_ids)], context=context)
        return notif_obj.unlink(cr, uid, to_del_notif_ids, context=context)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
