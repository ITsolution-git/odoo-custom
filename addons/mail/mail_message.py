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

import logging
import openerp
import tools

from email.header import decode_header
from operator import itemgetter
from osv import osv, fields
from tools.translate import _

_logger = logging.getLogger(__name__)

""" Some tools for parsing / creating email fields """
def decode(text):
    """Returns unicode() string conversion of the the given encoded smtp header text"""
    if text:
        text = decode_header(text.replace('\r', ''))
        return ''.join([tools.ustr(x[0], x[1]) for x in text])


class mail_message(osv.Model):
    """ Messages model: system notification (replacing res.log notifications),
        comments (OpenChatter discussion) and incoming emails. """
    _name = 'mail.message'
    _description = 'Message'
    _inherit = ['ir.needaction_mixin']
    _order = 'id desc'

    _message_read_limit = 10
    _message_record_name_length = 18

    def _shorten_name(self, name):
        if len(name) <= (self._message_record_name_length + 3):
            return name
        return name[:self._message_record_name_length] + '...'

    def _get_record_name(self, cr, uid, ids, name, arg, context=None):
        """ Return the related document name, using get_name. """
        result = dict.fromkeys(ids, '')
        for message in self.browse(cr, uid, ids, context=context):
            if not message.model or not message.res_id:
                continue
            try:
                result[message.id] = self._shorten_name(self.pool.get(message.model).name_get(cr, uid, [message.res_id], context=context)[0][1])
            except openerp.exceptions.AccessDenied, e:
                pass
        return result

    def _get_unread(self, cr, uid, ids, name, arg, context=None):
        """ Compute if the message is unread by the current user. """
        res = dict((id, {'unread': False}) for id in ids)
        partner_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).partner_id.id
        notif_obj = self.pool.get('mail.notification')
        notif_ids = notif_obj.search(cr, uid, [
            ('partner_id', 'in', [partner_id]),
            ('message_id', 'in', ids),
            ('read', '=', False)
        ], context=context)
        for notif in notif_obj.browse(cr, uid, notif_ids, context=context):
            res[notif.message_id.id]['unread'] = True
        return res

    def _search_unread(self, cr, uid, obj, name, domain, context=None):
        """ Search for messages unread by the current user. Condition is
            inversed because we search unread message on a read column. """
        if domain[0][2]:
            read_cond = '(read = false or read is null)'
        else:
            read_cond = 'read = true'
        partner_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).partner_id.id
        cr.execute("SELECT message_id FROM mail_notification "\
                        "WHERE partner_id = %%s AND %s" % read_cond,
                    (partner_id,))
        return [('id', 'in', [r[0] for r in cr.fetchall()])]

    def name_get(self, cr, uid, ids, context=None):
        # name_get may receive int id instead of an id list
        if isinstance(ids, (int, long)):
            ids = [ids]
        res = []
        for message in self.browse(cr, uid, ids, context=context):
            name = '%s: %s' % (message.subject or '', message.body or '')
            res.append((message.id, self._shorten_name(name.lstrip(' :'))))
        return res

    _columns = {
        'type': fields.selection([
                        ('email', 'Email'),
                        ('comment', 'Comment'),
                        ('notification', 'System notification'),
                        ], 'Type',
            help="Message type: email for email message, notification for system "\
                 "message, comment for other messages such as user replies"),
        'author_id': fields.many2one('res.partner', 'Author', required=True),
        'partner_ids': fields.many2many('res.partner', 'mail_notification', 'message_id', 'partner_id', 'Recipients'),
        'attachment_ids': fields.many2many('ir.attachment', 'message_attachment_rel',
            'message_id', 'attachment_id', 'Attachments'),
        'parent_id': fields.many2one('mail.message', 'Parent Message', select=True, ondelete='set null', help="Initial thread message."),
        'child_ids': fields.one2many('mail.message', 'parent_id', 'Child Messages'),
        'model': fields.char('Related Document Model', size=128, select=1),
        'res_id': fields.integer('Related Document ID', select=1),
        'record_name': fields.function(_get_record_name, type='string',
            string='Message Record Name',
            help="Name get of the related document."),
        'notification_ids': fields.one2many('mail.notification', 'message_id', 'Notifications'),
        'subject': fields.char('Subject'),
        'date': fields.datetime('Date'),
        'message_id': fields.char('Message-Id', help='Message unique identifier', select=1, readonly=1),
        'body': fields.html('Contents', help='Automatically sanitized HTML contents'),
        'unread': fields.function(_get_unread, fnct_search=_search_unread,
            type='boolean', string='Unread',
            help='Functional field to search for unread messages linked to uid'),
        'subtype_id': fields.many2one('mail.message.subtype', 'Subtype'),
        'vote_user_ids': fields.many2many('res.users', 'mail_vote', 'message_id', 'user_id', string='Votes',
            help='Users that voted for this message'),
    }

    def _needaction_domain_get(self, cr, uid, context=None):
        if self._needaction:
            return [('unread', '=', True)]
        return []

    def _get_default_author(self, cr, uid, context=None):
        return self.pool.get('res.users').browse(cr, uid, uid, context=context).partner_id.id

    _defaults = {
        'type': 'email',
        'date': lambda *a: fields.datetime.now(),
        'author_id': lambda self, cr, uid, ctx={}: self._get_default_author(cr, uid, ctx),
        'body': '',
    }

    #------------------------------------------------------
    # Vote/Like
    #------------------------------------------------------

    def vote_toggle(self, cr, uid, ids, user_ids=None, context=None):
        ''' Toggles voting '''
        if not user_ids:
            user_ids = [uid]
        for message in self.read(cr, uid, ids, ['vote_user_ids'], context=context):
            for user_id in user_ids:
                has_voted = user_id in message.get('vote_user_ids')
                if not has_voted:
                    self.write(cr, uid, message.get('id'), {'vote_user_ids': [(4, user_id)]}, context=context)
                else:
                    self.write(cr, uid, message.get('id'), {'vote_user_ids': [(3, user_id)]}, context=context)
        return True

    #------------------------------------------------------
    # Message loading for web interface
    #------------------------------------------------------

    def _message_dict_get(self, cr, uid, msg, context=None):
        """ Return a dict representation of the message browse record. """
        has_voted = False
        vote_ids = self.pool.get('res.users').name_get(cr, uid, [user.id for user in msg.vote_user_ids], context=context)
        for vote in vote_ids:
            if vote[0] == uid:
                has_voted = True
                break
        attachment_ids = [{'id': attach[0], 'name': attach[1]} for attach in self.pool.get('ir.attachment').name_get(cr, uid, [x.id for x in msg.attachment_ids], context=context)]
        author_id = self.pool.get('res.partner').name_get(cr, uid, [msg.author_id.id], context=context)[0]
        author_user_id = self.pool.get('res.users').name_get(cr, uid, [msg.author_id.user_ids[0].id], context=context)[0]
        partner_ids = self.pool.get('res.partner').name_get(cr, uid, [x.id for x in msg.partner_ids], context=context)
        return {
            'id': msg.id,
            'type': msg.type,
            'attachment_ids': attachment_ids,
            'body': msg.body,
            'model': msg.model,
            'res_id': msg.res_id,
            'record_name': msg.record_name,
            'subject': msg.subject,
            'date': msg.date,
            'author_id': author_id,
            'author_user_id': author_user_id,
            'partner_ids': partner_ids,
            'child_ids': [],
            'vote_user_ids': vote_ids,
            'has_voted': has_voted
        }

    def message_read_tree_flatten(self, cr, uid, messages, current_level, level, context=None):
        """ Given a tree with several roots of following structure :
            [   {'id': 1, 'child_ids': [
                    {'id': 11, 'child_ids': [...] },],
                {...}   ]
            Flatten it to have a maximum number of levels, 0 being flat and
            sort messages in a level according to a key of the messages.
            Perform the flattening at leafs if above the maximum depth, then get
            back in the tree.
            :param context: ``sort_key``: key for sorting (id by default)
            :param context: ``sort_reverse``: reverser order for sorting (True by default)
        """
        def _flatten(msg_dict):
            """ from    {'id': x, 'child_ids': [{child1}, {child2}]}
                get     [{'id': x, 'child_ids': []}, {child1}, {child2}]
            """
            child_ids = msg_dict.pop('child_ids', [])
            msg_dict['child_ids'] = []
            return [msg_dict] + child_ids
            # return sorted([msg_dict] + child_ids, key=itemgetter('id'), reverse=True)
        context = context or {}
        # Depth-first flattening
        for message in messages:
            if message.get('type') == 'expandable':
                continue
            message['child_ids'] = self.message_read_tree_flatten(cr, uid, message['child_ids'], current_level + 1, level, context=context)
        # Flatten if above maximum depth
        if current_level < level:
            return_list = messages
        else:
            return_list = []
            for message in messages:
                for flat_message in _flatten(message):
                    return_list.append(flat_message)
        return sorted(return_list, key=itemgetter(context.get('sort_key', 'id')), reverse=context.get('sort_reverse', True))

    def message_read(self, cr, uid, ids=False, domain=[], thread_level=0, limit=None, context=None):
        """ If IDs are provided, fetch these records. Otherwise use the domain
            to fetch the matching records.
            After having fetched the records provided by IDs, it will fetch the
            parents to have well-formed threads.
            :return list: list of trees of messages
        """
        limit = limit or self._message_read_limit
        context = context or {}
        if not ids:
            ids = self.search(cr, uid, domain, context=context, limit=limit)
        messages = self.browse(cr, uid, ids, context=context)

        result = []
        tree = {} # key: ID, value: record
        for msg in messages:
            if len(result) < (limit - 1):
                record = self._message_dict_get(cr, uid, msg, context=context)
                if thread_level and msg.parent_id:
                    while msg.parent_id:
                        if msg.parent_id.id in tree:
                            record_parent = tree[msg.parent_id.id]
                        else:
                            record_parent = self._message_dict_get(cr, uid, msg.parent_id, context=context)
                            if msg.parent_id.parent_id:
                                tree[msg.parent_id.id] = record_parent
                        if record['id'] not in [x['id'] for x in record_parent['child_ids']]:
                            record_parent['child_ids'].append(record)
                        record = record_parent
                        msg = msg.parent_id
                if msg.id not in tree:
                    result.append(record)
                    tree[msg.id] = record
            else:
                result.append({
                    'type': 'expandable',
                    'domain': [('id', '<=', msg.id)] + domain,
                    'context': context,
                    'thread_level': thread_level,  # should be improve accodting to level of records
                    'id': -1,
                })
                break

        # Flatten the result
        if thread_level > 0:
            result = self.message_read_tree_flatten(cr, uid, result, 0, thread_level, context=context)
        return result

    #------------------------------------------------------
    # Email api
    #------------------------------------------------------

    def init(self, cr):
        cr.execute("""SELECT indexname FROM pg_indexes WHERE indexname = 'mail_message_model_res_id_idx'""")
        if not cr.fetchone():
            cr.execute("""CREATE INDEX mail_message_model_res_id_idx ON mail_message (model, res_id)""")

    def check_access_rule(self, cr, uid, ids, operation, context=None):
        """ mail.message access rule check
            - message received (a notification exists) -> ok
            - check rules of related document if exists
            - fallback on normal mail.message check """
        if isinstance(ids, (int, long)):
            ids = [ids]

        # check messages for which you have a notification
        partner_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).partner_id.id
        not_obj = self.pool.get('mail.notification')
        not_ids = not_obj.search(cr, uid, [
            ('partner_id', '=', partner_id),
            ('message_id', 'in', ids),
        ], context=context)
        notified_ids = [notification.message_id.id for notification in not_obj.browse(cr, uid, not_ids, context=context)
            if notification.message_id.id in ids]

        # check messages linked to an existing document
        model_record_ids = {}
        document_ids = []
        cr.execute('SELECT DISTINCT id, model, res_id FROM mail_message WHERE id = ANY (%s)', (ids,))
        for id, rmod, rid in cr.fetchall():
            if not (rmod and rid):
                continue
            document_ids.append(id)
            model_record_ids.setdefault(rmod, set()).add(rid)
        for model, mids in model_record_ids.items():
            model_obj = self.pool.get(model)
            mids = model_obj.exists(cr, uid, mids)
            model_obj.check_access_rights(cr, uid, operation)
            model_obj.check_access_rule(cr, uid, mids, operation, context=context)

        # fall back on classic operation for other ids
        other_ids = set(ids).difference(set(notified_ids), set(document_ids))
        super(mail_message, self).check_access_rule(cr, uid, other_ids, operation, context=None)

    def create(self, cr, uid, values, context=None):
        if not values.get('message_id') and values.get('res_id') and values.get('model'):
            values['message_id'] = tools.generate_tracking_message_id('%(model)s-%(res_id)s' % values)
        newid = super(mail_message, self).create(cr, uid, values, context)
        self.notify(cr, uid, newid, context=context)
        return newid

    def unlink(self, cr, uid, ids, context=None):
        # cascade-delete attachments that are directly attached to the message (should only happen
        # for mail.messages that act as parent for a standalone mail.mail record).
        attachments_to_delete = []
        for message in self.browse(cr, uid, ids, context=context):
            for attach in message.attachment_ids:
                if attach.res_model == self._name and attach.res_id == message.id:
                    attachments_to_delete.append(attach.id)
        if attachments_to_delete:
            self.pool.get('ir.attachment').unlink(cr, uid, attachments_to_delete, context=context)
        return super(mail_message, self).unlink(cr, uid, ids, context=context)

    def notify(self, cr, uid, newid, context=None):
        """ Add the related record followers to the destination partner_ids.
            Call mail_notification.notify to manage the email sending
        """
        followers_obj = self.pool.get("mail.followers")
        message = self.browse(cr, uid, newid, context=context)
        partners_to_notify = set([])
        # add all partner_ids of the message
        if message.partner_ids:
            partners_to_notify |= set(partner.id for partner in message.partner_ids)
        # add all followers and set add them in partner_ids
        if message.model and message.res_id:
            record = self.pool.get(message.model).browse(cr, uid, message.res_id, context=context)
            extra_notified = set(partner.id for partner in record.message_follower_ids)
            missing_notified = extra_notified - partners_to_notify
            missing_follow_ids = []
            if message.subtype_id:
                for p_id in missing_notified:
                    follow_ids = followers_obj.search(cr, uid, [('partner_id','=',p_id),('subtype_ids','in',[message.subtype_id.id]),('res_model','=',message.model),('res_id','=',message.res_id)], context=context)
                    if follow_ids and len(follow_ids):
                        missing_follow_ids.append(p_id)
                    subtype_record = self.pool.get('mail.message.subtype').browse(cr, uid, message.subtype_id.id,context=context)
                    if not subtype_record.res_model:
                        missing_follow_ids.append(p_id)
            message.write({'partner_ids': [(4, p_id) for p_id in missing_follow_ids]})
            partners_to_notify |= extra_notified
        self.pool.get('mail.notification').notify(cr, uid, list(partners_to_notify), newid, context=context)

    def copy(self, cr, uid, id, default=None, context=None):
        """Overridden to avoid duplicating fields that are unique to each email"""
        if default is None:
            default = {}
        default.update(message_id=False, headers=False)
        return super(mail_message, self).copy(cr, uid, id, default=default, context=context)

    #------------------------------------------------------
    # Tools
    #------------------------------------------------------

    def check_partners_email(self, cr, uid, partner_ids, context=None):
        """ Verify that selected partner_ids have an email_address defined.
            Otherwise throw a warning. """
        partner_wo_email_lst = []
        for partner in self.pool.get('res.partner').browse(cr, uid, partner_ids, context=context):
            if not partner.email:
                partner_wo_email_lst.append(partner)
        if not partner_wo_email_lst:
            return {}
        warning_msg = _('The following partners chosen as recipients for the email have no email address linked :')
        for partner in partner_wo_email_lst:
            warning_msg += '\n- %s' % (partner.name)
        return {'warning': {
                    'title': _('Partners email addresses not found'),
                    'message': warning_msg,
                    }
                }
