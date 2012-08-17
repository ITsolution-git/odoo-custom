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
import logging
import re
import time
import xmlrpclib
from email.utils import parsedate
from email.message import Message

from osv import osv, fields
from mail_message import decode
import tools
from tools.translate import _
from tools.safe_eval import safe_eval as eval

_logger = logging.getLogger(__name__)

def decode_header(message, header, separator=' '):
    return separator.join(map(decode,message.get_all(header, [])))

class mail_thread(osv.Model):
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
       creation and update of a thread.
       
       #TODO: UPDATE WITH SUBTYPE / NEW FOLLOW MECHANISM
    '''
    _name = 'mail.thread'
    _description = 'Email Thread'
    # TODO: may be we should make it _inherit ir.needaction

    def _get_is_follower(self, cr, uid, ids, name, args, context=None):
        subobj = self.pool.get('mail.subscription')
        subids = subobj.search(cr, uid, [
            ('res_model','=',self._name),
            ('res_id', 'in', ids),
            ('user_id','=',uid)], context=context)
        result = dict.fromkeys(ids, False)
        for sub in subobj.browse(cr, uid, subids, context=context):
            result[res_id] = True
        return result

    def _get_message_data(self, cr, uid, ids, name, args, context=None):
        res = {}
        for id in ids:
            res[id] = {
                'message_unread': False,
                'message_Summary': ''
            }
        nobj = self.pool.get('mail.notification')
        notifs = nobj.search(cr, uid, [
            ('user_id','=',uid),
            ('message_id.res_id','in', ids),
            ('message_id.model','=', self._name),
            ('read','=',False)
        ], context=context)
        for notif in nobj.browse(cr, uid, nids, context=context):
            res[notif.message_id.id]['message_unread'] = True

        for thread in self.browse(cr, uid, ids, context=context):
            message_ids = thread.message_ids
            follower_ids = thread.message_follower_ids
            res[id]['message_summary'] = "<span><span class='oe_e'>9</span> %d</span> <span><span class='oe_e'>+</span> %d</span>" % (len(message_ids), len(follower_ids)),
        return res

    # FP Note: todo
    def _search_unread(self, tobj, cr, uid, obj=None, name=None, domain=None, context=None):
        return []

    _columns = {
        'message_is_follower': fields.function(_get_is_follower,
            type='boolean', string='Is a Follower'),
        'message_follower_ids': fields.one2many('mail.subscription', 'res_id',
            domain=lambda self: [('res_model','=',self._name)],
            string='Followers'),
        'message_ids': fields.one2many('mail.message', 'res_id',
            domain=lambda self: [('model','=',self._name)],
            string='Related Messages', 
            help="All messages related to the current document."),
        'message_unread': fields.function(_get_message_data, fnct_search=_search_unread, 
            string='Has Unread Messages',
            help="When checked, new messages require your attention.",
            multi="_get_message_data"),
        'message_summary': fields.function(_get_message_data, method=True,
            type='text', string='Summary', multi="_get_message_data",
            help="Holds the Chatter summary (number of messages, ...). "\
                 "This summary is directly in html format in order to "\
                 "be inserted in kanban views."),
    }

    #------------------------------------------------------
    # Automatic subscription when creating/reading
    #------------------------------------------------------

    def create(self, cr, uid, vals, context=None):
        """ Override of create to subscribe the current user
        """
        thread_id = super(mail_thread, self).create(cr, uid, vals, context=context)
        self.message_subscribe_users(cr, uid, [thread_id], [uid], context=context)
        return thread_id

    def unlink(self, cr, uid, ids, context=None):
        """Override unlink, to automatically delete messages
           that are linked with res_model and res_id, not through
           a foreign key with a 'cascade' ondelete attribute.
           Notifications will be deleted with messages
        """
        msg_obj = self.pool.get('mail.message')
        # delete messages and notifications
        msg_to_del_ids = msg_obj.search(cr, uid, [('model', '=', self._name), ('res_id', 'in', ids)], context=context)
        msg_obj.unlink(cr, uid, msg_to_del_ids, context=context)
        return super(mail_thread, self).unlink(cr, uid, ids, context=context)

    #------------------------------------------------------
    # mail.message wrappers and tools
    #------------------------------------------------------

    # FP Note: should we support attachment ? Also, this method must be on
    # the mail.message object, not on the thread.
    def message_create(self, cr, uid, thread_id, vals, context=None):
        """ OpenChatter: wrapper of mail.message create method
           - creates the mail.message
           - automatically subscribe the message writer
           - push the message to followers
        """
        context = context or {}
        message_obj = self.pool.get('mail.message')
        vals['model'] = self._name
        vals['res_id'] = thread_id
        msg_id = message_obj.create(cr, uid, vals, context=context)
        return msg_id

    def _needaction_domain_get(self, cr, uid, context={}):
        if self._needaction:
            return [('message_unread','=',True)]
        return []

    #------------------------------------------------------
    # Generic message api
    #------------------------------------------------------

    # I propose to remove this. Everyone should use message_create instead.
    def message_append(self, cr, uid, threads, subject, body_text=None, body_html=None,
                        type='email', email_date=None, parent_id=False,
                        content_subtype='plain', state=None,
                        partner_ids=None, email_from=False, email_to=False,
                        email_cc=None, reply_to=None,
                        headers=None, message_id=False, references=None,
                        attachments=None, context=None):
        """ Creates a new mail.message through message_create. The new message
            is attached to the current mail.thread, containing all the details
            passed as parameters. All attachments will be attached to the
            thread record as well as to the actual message.

            This method calls message_create that will handle management of
            subscription and notifications, and effectively create the message.

            If ``email_from`` is not set or ``type`` not set as 'email',
            a note message is created (comment or system notification),
            without the usual envelope attributes (sender, recipients, etc.).

            :param threads: list of thread ids, or list of browse_records
                representing threads to which a new message should be attached
            :param subject: subject of the message, or description of the event;
                this is totally optional as subjects are not important except
                for specific messages (blog post, job offers) or for emails
            :param body_text: plaintext contents of the mail or log message
            :param body_html: html contents of the mail or log message
            :param type: type of message: 'email', 'comment', 'notification';
                email by default
            :param email_date: email date string if different from now, in
                server timezone
            :param parent_id: id of the parent message (threaded messaging model)
            :param content_subtype: optional content_subtype of message: 'plain'
                or 'html', corresponding to the main body contents (body_text or
                body_html).
            :param state: state of message
            :param partner_ids: destination partners of the message, in addition
                to the now fully optional email_to; this method is supposed to
                received a list of ids is not None. The specific many2many
                instruction will be generated by this method.
            :param email_from: Email From / Sender address if any
            :param email_to: Email-To / Recipient address
            :param email_cc: Comma-Separated list of Carbon Copy Emails To
                addresses if any
            :param reply_to: reply_to header
            :param headers: mail headers to store
            :param message_id: optional email identifier
            :param references: optional email references
            :param dict attachments: map of attachment filenames to binary
                contents, if any.
            :param dict context: if a ``thread_model`` value is present in the
                context, its value will be used to determine the model of the
                thread to update (instead of the current model).
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
                }
                to_attach.append(ir_attachment.create(cr, uid, data_attach, context=context))
            # find related partner: partner_id column in thread object, or self is res.partner model
            partner_id = ('partner_id' in thread._columns.keys()) and (thread.partner_id and thread.partner_id.id or False) or False
            if not partner_id and thread._name == 'res.partner':
                partner_id = thread.id
            # destination partners
            if partner_ids is None:
                partner_ids = []
            mail_partner_ids = [(6, 0, partner_ids)]

            data = {
                'subject': subject,
                'body_text': body_text or thread._model._columns.get('description') and thread.description or '',
                'body_html': body_html or '',
                'parent_id': parent_id,
                'date': email_date or fields.datetime.now(),
                'type': type,
                'content_subtype': content_subtype,
                'state': state,
                'message_id': message_id,
                'partner_ids': mail_partner_ids,
                'attachment_ids': [(6, 0, to_attach)],
                'user_id': uid,
                'model' : thread._name,
                'res_id': thread.id,
                'partner_id': partner_id,
            }

            if email_from or type == 'email':
                for param in (email_to, email_cc):
                    if isinstance(param, list):
                        param = ", ".join(param)
                data.update({
                    'email_to': email_to,
                    'email_from': email_from or \
                        thread._model._columns.get('user_id') and thread.user_id and thread.user_id.user_email,
                    'email_cc': email_cc,
                    'references': references,
                    'headers': headers,
                    'reply_to': reply_to,
                    })

            new_msg_ids.append(self.message_create(cr, uid, thread.id, data, context=context))
        return new_msg_ids

    # to be removed completly
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
                            content_subtype = msg_dict.get('content_subtype'),
                            state = msg_dict.get('state'),
                            partner_ids = msg_dict.get('partner_ids'),
                            email_from = msg_dict.get('from', msg_dict.get('email_from')),
                            email_to = msg_dict.get('to', msg_dict.get('email_to')),
                            email_cc = msg_dict.get('cc', msg_dict.get('email_cc')),
                            reply_to = msg_dict.get('reply', msg_dict.get('reply_to')),
                            email_date = msg_dict.get('date'),
                            message_id = msg_dict.get('message-id', msg_dict.get('message_id')),
                            references = msg_dict.get('references')\
                                      or msg_dict.get('in-reply-to'),
                            attachments = msg_dict.get('attachments'),
                            headers = msg_dict.get('headers'),
                            context = context)

    #------------------------------------------------------
    # Message loading
    #------------------------------------------------------

    def _message_search_ancestor_ids(self, cr, uid, ids, child_ids, ancestor_ids, context=None):
        """ Given message child_ids ids, find their ancestors until ancestor_ids
            using their parent_id relationship.

            :param child_ids: the first nodes of the search
            :param ancestor_ids: list of ancestors. When the search reach an
                                 ancestor, it stops.
        """
        def _get_parent_ids(message_list, ancestor_ids, child_ids):
            """ Tool function: return the list of parent_ids of messages
                contained in message_list. Parents that are in ancestor_ids
                or in child_ids are not returned. """
            return [message['parent_id'][0] for message in message_list
                        if message['parent_id']
                        and message['parent_id'][0] not in ancestor_ids
                        and message['parent_id'][0] not in child_ids
                    ]

        message_obj = self.pool.get('mail.message')
        messages_temp = message_obj.read(cr, uid, child_ids, ['id', 'parent_id'], context=context)
        parent_ids = _get_parent_ids(messages_temp, ancestor_ids, child_ids)
        child_ids += parent_ids
        cur_iter = 0; max_iter = 100; # avoid infinite loop
        while (parent_ids and (cur_iter < max_iter)):
            cur_iter += 1
            messages_temp = message_obj.read(cr, uid, parent_ids, ['id', 'parent_id'], context=context)
            parent_ids = _get_parent_ids(messages_temp, ancestor_ids, child_ids)
            child_ids += parent_ids
        if (cur_iter > max_iter):
            _logger.warning("Possible infinite loop in _message_search_ancestor_ids. "\
                "Note that this algorithm is intended to check for cycle in "\
                "message graph, leading to a curious error. Have fun.")
        return child_ids

    def message_search_get_domain(self, cr, uid, ids, context=None):
        """ OpenChatter feature: get the domain to search the messages related
            to a document. mail.thread defines the default behavior as
            being messages with model = self._name, id in ids.
            This method should be overridden if a model has to implement a
            particular behavior.
        """
        return ['&', ('res_id', 'in', ids), ('model', '=', self._name)]

    def message_search(self, cr, uid, ids, fetch_ancestors=False, ancestor_ids=None,
                        limit=100, offset=0, domain=None, count=False, context=None):
        """ OpenChatter feature: return thread messages ids according to the
            search domain given by ``message_search_get_domain``.

            It is possible to add in the search the parent of messages by
            setting the fetch_ancestors flag to True. In that case, using
            the parent_id relationship, the method returns the id list according
            to the search domain, but then calls ``_message_search_ancestor_ids``
            that will add to the list the ancestors ids. The search is limited
            to parent messages having an id in ancestor_ids or having
            parent_id set to False.

            If ``count==True``, the number of ids is returned instead of the
            id list. The count is done by hand instead of passing it as an
            argument to the search call because we might want to perform
            a research including parent messages until some ancestor_ids.

            :param fetch_ancestors: performs an ascended search; will add
                                    to fetched msgs all their parents until
                                    ancestor_ids
            :param ancestor_ids: used when fetching ancestors
            :param domain: domain to add to the search; especially child_of
                           is interesting when dealing with threaded display.
                           Note that the added domain is anded with the
                           default domain.
            :param limit, offset, count, context: as usual
        """
        search_domain = self.message_search_get_domain(cr, uid, ids, context=context)
        if domain:
            search_domain += domain
        message_obj = self.pool.get('mail.message')
        message_res = message_obj.search(cr, uid, search_domain, limit=limit, offset=offset, count=count, context=context)
        if not count and fetch_ancestors:
            message_res += self._message_search_ancestor_ids(cr, uid, ids, message_res, ancestor_ids, context=context)
        return message_res

    def message_read(self, cr, uid, ids, fetch_ancestors=False, ancestor_ids=None,
                        limit=100, offset=0, domain=None, context=None):
        """ OpenChatter feature: read the messages related to some threads.
            This method is used mainly the Chatter widget, to directly have
            read result instead of searching then reading.

            Please see message_search for more information about the parameters.
        """
        message_ids = self.message_search(cr, uid, ids, fetch_ancestors, ancestor_ids,
            limit, offset, domain, context=context)
        messages = self.pool.get('mail.message').read(cr, uid, message_ids, context=context)

        """ Retrieve all attachments names """
        map_id_to_name = dict((attachment_id, '') for message in messages for attachment_id in message['attachment_ids'])

        ids = map_id_to_name.keys()
        names = self.pool.get('ir.attachment').name_get(cr, uid, ids, context=context)

        # convert the list of tuples into a dictionnary
        for name in names:
            map_id_to_name[name[0]] = name[1]

        # give corresponding ids and names to each message
        for msg in messages:
            msg["attachments"] = []

            for attach_id in msg["attachment_ids"]:
                msg["attachments"].append({'id': attach_id, 'name': map_id_to_name[attach_id]})

        # Set the threads as read
        self.message_mark_as_read(cr, uid, ids, context=context)
        # Sort and return the messages
        messages = sorted(messages, key=lambda d: (-d['id']))
        return messages

    def message_get_pushed_messages(self, cr, uid, ids, fetch_ancestors=False, ancestor_ids=None,
                            limit=100, offset=0, msg_search_domain=[], context=None):
        """ OpenChatter: wall: get the pushed notifications and used them
            to fetch messages to display on the wall.

            :param fetch_ancestors: performs an ascended search; will add
                                    to fetched msgs all their parents until
                                    ancestor_ids
            :param ancestor_ids: used when fetching ancestors
            :param domain: domain to add to the search; especially child_of
                           is interesting when dealing with threaded display
            :param ascent: performs an ascended search; will add to fetched msgs
                           all their parents until root_ids
            :param root_ids: for ascent search
            :return: list of mail.messages sorted by date
        """
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
        if (fetch_ancestors): msg_ids = self._message_search_ancestor_ids(cr, uid, ids, msg_ids, ancestor_ids, context=context)
        msgs = msg_obj.read(cr, uid, msg_ids, context=context)
        return msgs

    def _message_find_partners(self, cr, uid, message, headers=['From'], context=None):
        s = ', '.join([decode(message.get(h)) for h in headers])
        mails = tools.email_split(s)
        result = []
        for m in mails:
            result += self.pool.get('res.partner').search(cr, uid, [('email','ilike',m)], context=context)
        return result

    def _message_find_user_id(self, cr, uid, message, context=None):
        from_local_part = tools.email_split(decode(message.get('From')))[0]
        user_ids = self.pool.get('res.users').search(cr, uid, [('login', '=', from_local_part)], context=context)
        return user_ids[0] if user_ids else uid

    #------------------------------------------------------
    # Mail gateway
    #------------------------------------------------------
    # message_process will call either message_new or message_update.

    def message_route(self, cr, uid, message, model=None, thread_id=None,
                      custom_values=None, context=None):
        """Attempt to figure out the correct target model, thread_id,
        custom_values and user_id to use for an incoming message.
        Multiple values may be returned, if a message had multiple
        recipients matching existing mail.aliases, for example.

        The following heuristics are used, in this order:
             1. If the message replies to an existing thread_id, and
                properly contains the thread model in the 'In-Reply-To'
                header, use this model/thread_id pair, and ignore
                custom_value (not needed as no creation will take place)
             2. Look for a mail.alias entry matching the message
                recipient, and use the corresponding model, thread_id,
                custom_values and user_id.
             3. Fallback to the ``model``, ``thread_id`` and ``custom_values``
                provided.
             4. If all the above fails, raise an exception.

           :param string message: an email.message instance
           :param string model: the fallback model to use if the message
               does not match any of the currently configured mail aliases
               (may be None if a matching alias is supposed to be present)
           :type dict custom_values: optional dictionary of default field values
                to pass to ``message_new`` if a new record needs to be created.
                Ignored if the thread record already exists, and also if a
                matching mail.alias was found (aliases define their own defaults)
           :param int thread_id: optional ID of the record/thread from ``model``
               to which this mail should be attached. Only used if the message
               does not reply to an existing thread and does not match any mail alias.
           :return: list of [model, thread_id, custom_values, user_id]
        """
        assert isinstance(message, Message), 'message must be an email.message.Message at this point'
        message_id = message.get('Message-Id')

        # 1. Verify if this is a reply to an existing thread
        references = decode_header(message, 'References') or decode_header(message, 'In-Reply-To')
        ref_match = references and tools.reference_re.search(references)
        if ref_match:
            thread_id = int(ref_match.group(1))
            model = ref_match.group(2) or model
            model_pool = self.pool.get(model)
            if thread_id and model and model_pool and model_pool.exists(cr, uid, thread_id) \
                and hasattr(model_pool, 'message_update'):
                _logger.debug('Routing mail with Message-Id %s: direct reply to model: %s, thread_id: %s, custom_values: %s, uid: %s',
                              message_id, model, thread_id, custom_values, uid)
                return [(model, thread_id, custom_values, uid)]

        # 2. Look for a matching mail.alias entry
        # Delivered-To is a safe bet in most modern MTAs, but we have to fallback on To + Cc values
        # for all the odd MTAs out there, as there is no standard header for the envelope's `rcpt_to` value.
        rcpt_tos = decode_header(message, 'Delivered-To') or \
             ','.join([decode_header(message, 'To'),
                       decode_header(message, 'Cc'),
                       decode_header(message, 'Resent-To'),
                       decode_header(message, 'Resent-Cc')])
        local_parts = [e.split('@')[0] for e in tools.email_split(rcpt_tos)]
        if local_parts:
            mail_alias = self.pool.get('mail.alias')
            alias_ids = mail_alias.search(cr, uid, [('alias_name', 'in', local_parts)])
            if alias_ids:
                routes = []
                for alias in mail_alias.browse(cr, uid, alias_ids, context=context):
                    user_id = alias.alias_user_id.id
                    if not user_id:
                        user_id = self._message_find_user_id(cr, uid, message, context=context)
                    routes.append((alias.alias_model_id.model, alias.alias_force_thread_id, \
                                   eval(alias.alias_defaults), user_id))
                _logger.debug('Routing mail with Message-Id %s: direct alias match: %r', message_id, routes)
                return routes

        # 3. Fallback to the provided parameters, if they work
        model_pool = self.pool.get(model)
        if not thread_id:
            # Legacy: fallback to matching [ID] in the Subject
            match = tools.res_re.search(decode_header(message, 'Subject'))
            thread_id = match and match.group(1)
        assert thread_id and hasattr(model_pool, 'message_update') or hasattr(model_pool, 'message_new'), \
            "No possible route found for incoming message with Message-Id %s. " \
            "Create an appropriate mail.alias or force the destination model." % message_id
        if thread_id and not model_pool.exists(cr, uid, thread_id):
            _logger.warning('Received mail reply to missing document %s! Ignoring and creating new document instead for Message-Id %s',
                            thread_id, message_id)
            thread_id = None
        _logger.debug('Routing mail with Message-Id %s: fallback to model:%s, thread_id:%s, custom_values:%s, uid:%s',
                      message_id, model, thread_id, custom_values, uid)
        return [(model, thread_id, custom_values, uid)]

    def message_process(self, cr, uid, model, message, custom_values=None,
                        save_original=False, strip_attachments=False,
                        thread_id=None, context=None):
        """Process an incoming RFC2822 email message, relying on
           ``mail.message.parse()`` for the parsing operation,
           and ``message_route()`` to figure out the target model.

           Once the target model is known, its ``message_new`` method
           is called with the new message (if the thread record did not exist)
            or its ``message_update`` method (if it did). Finally,
           ``message_forward`` is called to automatically notify other
           people that should receive this message.

           :param string model: the fallback model to use if the message
               does not match any of the currently configured mail aliases
               (may be None if a matching alias is supposed to be present)
           :param message: source of the RFC2822 message
           :type message: string or xmlrpclib.Binary
           :type dict custom_values: optional dictionary of field values
                to pass to ``message_new`` if a new record needs to be created.
                Ignored if the thread record already exists, and also if a
                matching mail.alias was found (aliases define their own defaults)
           :param bool save_original: whether to keep a copy of the original
                email source attached to the message after it is imported.
           :param bool strip_attachments: whether to strip all attachments
                before processing the message, in order to save some space.
           :param int thread_id: optional ID of the record/thread from ``model``
               to which this mail should be attached. When provided, this
               overrides the automatic detection based on the message
               headers.
        """
        if context is None: context = {}

        # extract message bytes - we are forced to pass the message as binary because
        # we don't know its encoding until we parse its headers and hence can't
        # convert it to utf-8 for transport between the mailgate script and here.
        if isinstance(message, xmlrpclib.Binary):
            message = str(message.data)
        # Warning: message_from_string doesn't always work correctly on unicode,
        # we must use utf-8 strings here :-(
        if isinstance(message, unicode):
            message = message.encode('utf-8')
        msg_txt = email.message_from_string(message)
        routes = self.message_route(cr, uid, msg_txt, model,
                                    thread_id, custom_values,
                                    context=context)
        msg = self.pool.get('mail.message').parse_message(msg_txt, save_original=save_original, context=context)
        msg['state'] = 'received'
        if strip_attachments and 'attachments' in msg:
            del msg['attachments']
        for model, thread_id, custom_values, user_id in routes:
            if self._name != model:
                context.update({'thread_model': model})
            model_pool = self.pool.get(model)
            assert thread_id and hasattr(model_pool, 'message_update') or hasattr(model_pool, 'message_new'), \
                "Undeliverable mail with Message-Id %s, model %s does not accept incoming emails" % \
                    (msg['message-id'], model)
            if thread_id and hasattr(model_pool, 'message_update'):
                model_pool.message_update(cr, user_id, [thread_id], msg, context=context)
            else:
                thread_id = model_pool.message_new(cr, user_id, msg, custom_values, context=context)

        return True

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
            data['name'] = msg_dict.get('subject', '')
        if custom_values and isinstance(custom_values, dict):
            data.update(custom_values)
        res_id = model_pool.create(cr, uid, data, context=context)
        self.message_append_dict(cr, uid, [res_id], msg_dict, context=context)
        return res_id

    def message_update(self, cr, uid, ids, msg_dict, update_vals=None, context=None):
        """Called by ``message_process`` when a new message is received
           for an existing thread. The default behavior is to create a
           new mail.message in the given thread (by calling
           ``message_append_dict``)
           Additional behavior may be implemented by overriding this
           method.
           :param dict msg_dict: a map containing the email details and
                               attachments. See ``message_process`` and
                               ``mail.message.parse()`` for details.
           :param dict update_vals: a dict containing values to update records
                              given their ids; if the dict is None or is
                              void, no write operation is performed.
        """
        if update_vals:
            self.write(cr, uid, ids, update_vals, context=context)
        return self.message_append_dict(cr, uid, ids, msg_dict, context=context)

    def message_thread_followers(self, cr, uid, ids, context=None):
        """ Returns a list of email addresses of the people following
            this thread, including the sender of each mail, and the
            people who were in CC of the messages, if any.
        """
        res = {}
        if isinstance(ids, (str, int, long)):
            ids = [long(ids)]
        for thread in self.browse(cr, uid, ids, context=context):
            l = set()
            for message in thread.message_ids:
                l.add((message.user_id and message.user_id.email) or '')
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
        for res in model_pool.browse(cr, uid, thread_ids, context=context):
            if hasattr(model_pool, 'message_thread_followers'):
                followers = model_pool.message_thread_followers(cr, uid, [res.id])[res.id]
            else:
                followers = self.message_thread_followers(cr, uid, [res.id])[res.id]
            message_followers_emails = tools.email_split(','.join(filter(None, followers)))
            message_recipients = tools.email_split(','.join(filter(None,
                                                                       [decode(msg['from']),
                                                                        decode(msg['to']),
                                                                        decode(msg['cc'])])))
            forward_to = [i for i in message_followers_emails if (i and (i not in message_recipients))]
            if forward_to:
                # TODO: we need an interface for this for all types of objects, not just leads
                if model_pool._columns.get('section_id'):
                    del msg['reply-to']
                    msg['reply-to'] = res.section_id.reply_to

                smtp_from, = tools.email_split(msg['from'])
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
                      'from': from,          --> author_id
                      'to': to,              --> partner_ids
                      'cc': cc,              --> partner_ids
                      'headers' : { 'X-Mailer': mailer,  --> to remove
                                    #.. all X- headers...
                                  },
                      'content_subtype': msg_mime_subtype,  --> to remove
                      'body_text': plaintext_body           --> keep body
                      'body_html': html_body,               --> to remove
                      'attachments': [('file1', 'bytes'),
                                       ('file2', 'bytes') }
                       # ...
                       'original': source_of_email,         --> attachment document
                    }
        """
        msg_txt = message
        attachments = []
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
            msg_original = message.as_string() if isinstance(message, Message) \
                                                  else message
            attachments.append((0, 0, {
                'name':'email.eml',
                'datas': base64.b64encode(msg_original),
                'datas_fname': 'email.eml',
                'res_model': 'mail.message',
                'description': _('original email'),
            }))

        if not message_id:
            # Very unusual situation, be we should be fault-tolerant here
            message_id = time.time()
            msg_txt['message-id'] = message_id
            _logger.info('Parsing Message without message-id, generating a random one: %s', message_id)

        msg_fields = msg_txt.keys()

        msg['message_id'] = message_id

        if 'Subject' in msg_fields:
            msg['subject'] = decode(msg_txt.get('Subject'))

        #if 'Content-Type' in msg_fields:
        #    msg['content-type'] = msg_txt.get('Content-Type')

        # find author_id

        if 'From' in msg_fields:
            author_ids = self._message_find_partners(cr, uid, msg_text, ['From'], context=context)
            #decode(msg_txt.get('From') or msg_txt.get_unixfrom()) )
            if author_ids:
                msg['author_id'] = author_ids[0]

        partner_ids = self._message_find_partners(cr, uid, msg_text, ['From','To','Delivered-To','CC','Cc'], context=context)
        msg['partner_ids'] = partner_ids

        #if 'To' in msg_fields:
        #    msg['to'] = decode(msg_txt.get('To'))

        #if 'Delivered-To' in msg_fields:
        #    msg['to'] = decode(msg_txt.get('Delivered-To'))

        #if 'CC' in msg_fields:
        #    msg['cc'] = decode(msg_txt.get('CC'))

        #if 'Cc' in msg_fields:
        #    msg['cc'] = decode(msg_txt.get('Cc'))

        #if 'Reply-To' in msg_fields:
        #    msg['reply'] = decode(msg_txt.get('Reply-To'))

        # FP Note: I propose to store the current datetime rather than the email date
        #if 'Date' in msg_fields:
        #    date_hdr = decode(msg_txt.get('Date'))
        #    # convert from email timezone to server timezone
        #    date_server_datetime = dateutil.parser.parse(date_hdr).astimezone(pytz.timezone(tools.get_server_timezone()))
        #    date_server_datetime_str = date_server_datetime.strftime(DEFAULT_SERVER_DATETIME_FORMAT)
        #    msg['date'] = date_server_datetime_str

        #if 'Content-Transfer-Encoding' in msg_fields:
        #    msg['encoding'] = msg_txt.get('Content-Transfer-Encoding')

        #if 'References' in msg_fields:
        #    msg['references'] = msg_txt.get('References')

        # FP Note: todo - find parent_id
        if 'In-Reply-To' in msg_fields:
            pass

        #msg['headers'] = {}
        #msg['content_subtype'] = 'plain'
        #for item in msg_txt.items():
        #    if item[0].startswith('X-'):
        #        msg['headers'].update({item[0]: item[1]})
        if not msg_txt.is_multipart() or 'text/plain' in msg.get('content-type', ''):
            encoding = msg_txt.get_content_charset()
            body = msg_txt.get_payload(decode=True)
            if 'text/html' in msg.get('content-type', ''):
                msg['body'] =  body
        #        msg['content_subtype'] = 'html'
        #        if body:
        #            body = tools.html2plaintext(body)
        #    msg['body_text'] = tools.ustr(body, encoding)

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
                        attachments.append((0, 0, {
                            'name': filename,
                            'datas': base64.b64encode(msg_original),
                            'datas_fname': filename,
                            'res_model': 'mail.message',
                            'description': _('email attachment'),
                        }))
                    content = tools.ustr(content, encoding)
                    if part.get_content_subtype() == 'html':
                        msg['body'] = content
                        # msg['content_subtype'] = 'html' # html version prevails
                        # body = tools.ustr(tools.html2plaintext(content))
                        # body = body.replace('&#13;', '')
                    elif part.get_content_subtype() == 'plain':
                        msg['body'] = content
                elif part.get_content_maintype() in ('application', 'image'):
                    if filename:
                        attachments.append((0, 0, {
                            'name': filename,
                            'datas': part.get_payload(decode=True),
                            'datas_fname': filename,
                            'res_model': 'mail.message',
                            'description': _('email attachment'),
                        }))
                    else:
                        res = part.get_payload(decode=True)
                        msg['body'] += tools.ustr(res, encoding)

        msg['attachments'] = attachments

        # for backwards compatibility:
        # msg['body'] = msg['body_text']
        # msg['sub_type'] = msg['content_subtype'] or 'plain'
        return msg

    #------------------------------------------------------
    # Note specific
    #------------------------------------------------------

    def log(self, cr, uid, id, message, secondary=False, context=None):
        _logger.warning("log() is deprecated. As this module inherit from \
                        mail.thread, the message will be managed by this \
                        module instead of by the res.log mechanism. Please \
                        use the mail.thread OpenChatter API instead of the \
                        now deprecated res.log.")
        self.message_append_note(cr, uid, [id], 'res.log', message, context=context)

    def message_append_note(self, cr, uid, ids, subject=None, body=None, parent_id=False,
                            type='notification', content_subtype='html', context=None):
        if content_subtype == 'html':
            body_html = body
            body_text = body
        else:
            body_html = body
            body_text = body
        return self.message_append(cr, uid, ids, subject, body_html, body_text,
                                    type, parent_id=parent_id,
                                    content_subtype=content_subtype, context=context)

    #------------------------------------------------------
    # Subscription mechanism
    #------------------------------------------------------

    # FP Note: replaced by message_follower_ids
    # def message_get_followers(self, cr, uid, ids, context=None):

    def message_read_followers(self, cr, uid, ids, fields=['id', 'name', 'image_small'], context=None):
        """ Returns the current document followers as a read result. Used
            mainly for Chatter having only one method to call to have
            details about users.
        """
        user_ids = self.message_get_followers(cr, uid, ids, context=context)
        return self.pool.get('res.users').read(cr, uid, user_ids, fields=fields, context=context)

    def message_is_follower(self, cr, uid, ids, user_id = None, context=None):
        """ Check if uid or user_id (if set) is a follower to the current
            document.

            :param user_id: if set, check is done on user_id; if not set
                            check is done on uid
        """
        sub_user_id = uid if user_id is None else user_id
        if sub_user_id in self.message_get_followers(cr, uid, ids, context=context):
            return True
        return False

    def message_subscribe_users(self, cr, uid, ids, user_ids=None, context=None):
        if not user_ids: user_ids = [uid]
        partners = {}
        for user in self.pool.get('res.users').browse(cr, uid, user_ids, context=context):
            partners[user.partner_id.id] = True
        return self.message_subscribe(cr, uid, ids, partners.keys(), context=context)

    def message_subscribe(self, cr, uid, ids, partner_ids, context=None):
        """
            :param partner_ids: a list of user_ids; if not set, subscribe
                             uid instead
            :param return: new value of followers, for Chatter
        """
        obj = self.pool.get('mail.followers')
        objids = obj.search(cr, uid, [
            ('res_id', 'in', ids),
            ('res_model', '=', self._name),
            ('partner_id', 'in', partner_ids),
            ], context=context)
        followers = {}
        for follow in obj.browse(cr, uid, objids, context=context):
            followers.setdefault(follow.partner_id.id, {})[follow.res_id] = True
        create_ids = []
        for res_id in ids:
            for partner_id in partner_ids:
                if followers.get(partner_id, {}).get(res_id, False):
                    continue
                create_ids.append(obj.create(cr, uid, {
                    'res_model': self._name,
                    'res_id': res_id, 'partner_id': partner_id
                }, context=context))
        return create_ids

    def message_unsubscribe(self, cr, uid, ids, user_ids = None, context=None):
        """ Unsubscribe the user (or user_ids) from the current document.

            :param user_ids: a list of user_ids; if not set, subscribe
                             uid instead
            :param return: new value of followers, for Chatter
        """
        to_unsubscribe_uids = [uid] if user_ids is None else user_ids
        write_res = self.write(cr, uid, ids, {'message_follower_ids': self.message_unsubscribe_get_command(cr, uid, to_unsubscribe_uids, context)}, context=context)
        return [follower.id for thread in self.browse(cr, uid, ids, context=context) for follower in thread.message_follower_ids]

    def message_unsubscribe_get_command(self, cr, uid, follower_ids, context=None):
        """ Generate the many2many command to remove followers. """
        return [(3, id) for id in follower_ids]

    #------------------------------------------------------
    # Notification API
    #------------------------------------------------------

    def message_remove_pushed_notifications(self, cr, uid, ids, msg_ids, remove_childs=True, context=None):
        notif_obj = self.pool.get('mail.notification')
        msg_obj = self.pool.get('mail.message')
        if remove_childs:
            notif_msg_ids = msg_obj.search(cr, uid, [('id', 'child_of', msg_ids)], context=context)
        else:
            notif_msg_ids = msg_ids
        to_del_notif_ids = notif_obj.search(cr, uid, ['&', ('user_id', '=', uid), ('message_id', 'in', notif_msg_ids)], context=context)
        return notif_obj.unlink(cr, uid, to_del_notif_ids, context=context)

    #------------------------------------------------------
    # Thread_state
    #------------------------------------------------------

    # FP Note: this should be a invert function on message_unread field
    def message_mark_as_read(self, cr, uid, ids, context=None):
        """ Set as read. """
        notobj = self.pool.get('mail.notification')
        cr.execute('''
            update mail_notification set 
                read=true
            where
                message_id in (select id from mail_message where res_id in %s and model=%s)
                user_id = %s
        ''', (ids, self._name, uid))
        return True

