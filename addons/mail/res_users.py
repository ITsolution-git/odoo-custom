# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2009-Today OpenERP SA (<http://www.openerp.com>)
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

from osv import osv, fields
from openerp.modules.registry import RegistryManager
from openerp import SUPERUSER_ID
from tools.translate import _

_logger = logging.getLogger(__name__)

class res_users(osv.osv):
    """ Update of res.users class
        - add a preference about sending emails about notifications
        - make a new user follow itself
        - add a welcome message
    """
    _name = 'res.users'
    _inherit = ['res.users']
    _inherits = {'mail.alias': 'alias_id'}
    
    _columns = {
        'notification_email_pref': fields.selection([
            ('all', 'All Feeds'),
            ('to_me', 'Only send directly to me'),
            ('none', 'Never')
            ], 'Receive Feeds by Email', required=True,
            help="Choose in which case you want to receive an email when you "\
                 "receive new feeds."),
        'alias_id': fields.many2one('mail.alias', 'Alias', ondelete="cascade", required=True, 
            help="Email address internally associated with this user. Incoming "\
                 "emails will appear in the user's notifications."),
    }
    
    _defaults = {
        'notification_email_pref': 'to_me',
        'alias_domain': False, # always hide alias during creation
    }

    def __init__(self, pool, cr):
        """ Override of __init__ to add access rights on notification_email_pref
            field. Access rights are disabled by default, but allowed on
            fields defined in self.SELF_WRITEABLE_FIELDS.
        """
        init_res = super(res_users, self).__init__(pool, cr)
        # duplicate list to avoid modifying the original reference
        self.SELF_WRITEABLE_FIELDS = list(self.SELF_WRITEABLE_FIELDS)
        self.SELF_WRITEABLE_FIELDS.append('notification_email_pref')
        return init_res

    def _auto_init(self, cr, context=None):
        """Installation hook to create aliases for all users and avoid constraint errors."""
        
        # disable the unique alias_id not null constraint, to avoid spurious warning during 
        # super.auto_init. We'll reinstall it afterwards.
        self._columns['alias_id'].required = False

        super(res_users,self)._auto_init(cr, context=context)
        
        registry = RegistryManager.get(cr.dbname)
        mail_alias = registry.get('mail.alias')
        res_users_model = registry.get('res.users')
        users_no_alias = res_users_model.search(cr, SUPERUSER_ID, [('alias_id', '=', False)])
        # Use read() not browse(), to avoid prefetching uninitialized inherited fields
        for user_data in res_users_model.read(cr, SUPERUSER_ID, users_no_alias, ['login']):
            alias_id = mail_alias.create_unique_alias(cr, SUPERUSER_ID, {'alias_name': user_data['login'],
                                                                         'alias_force_id': user_data['id']},
                                                      model_name=self._name)
            res_users_model.write(cr, SUPERUSER_ID, user_data['id'], {'alias_id': alias_id})
            _logger.info('Mail alias created for user %s (uid %s)', user_data['login'], user_data['id'])

        # Finally attempt to reinstate the missing constraint
        try:
            cr.execute('ALTER TABLE res_users ALTER COLUMN alias_id SET NOT NULL')
        except Exception:
            _logger.warning("Table '%s': unable to set a NOT NULL constraint on column '%s' !\n"\
                            "If you want to have it, you should update the records and execute manually:\n"\
                            "ALTER TABLE %s ALTER COLUMN %s SET NOT NULL",
                            self._table, 'alias_id', self._table, 'alias_id')

        self._columns['alias_id'].required = True

    def create(self, cr, uid, data, context=None):
        # create default alias same as the login
        mail_alias = self.pool.get('mail.alias')
        alias_id = mail_alias.create_unique_alias(cr, uid, {'alias_name': data['login']}, model_name=self._name, context=context)
        data['alias_id'] = alias_id
        data.pop('alias_name', None) # prevent errors during copy()
        user_id = super(res_users, self).create(cr, uid, data, context=context)
        mail_alias.write(cr, SUPERUSER_ID, [alias_id], {"alias_force_thread_id": user_id}, context)

        user = self.browse(cr, uid, user_id, context=context)
        # make user follow itself
        self.message_subscribe(cr, uid, [user_id], [user_id], context=context)
        # create a welcome message
        company_name = user.company_id.name if user.company_id else _('the company')
        message = '''%s has joined %s! Welcome in OpenERP !

Your homepage is a summary of messages you received and key information about documents you follow.

The top menu bar contains all applications you installed. You can use this <i>Settings</i> menu to install more applications, activate others features or give access to new users.

To setup your preferences (name, email signature, avatar), click on the top right corner.''' % (user.name, company_name)
        self.message_append_note(cr, uid, [user_id], subject='Welcome to OpenERP', body=message, type='comment', content_subtype='html', context=context)
        return user_id
    
    def write(self, cr, uid, ids, vals, context=None):
        # User alias is sync'ed with login
        if vals.get('login'): vals['alias_name'] = vals['login']
        return super(res_users, self).write(cr, uid, ids, vals, context=context)

    def unlink(self, cr, uid, ids, context=None):
        # Cascade-delete mail aliases as well, as they should not exist without the user.
        alias_pool = self.pool.get('mail.alias')
        alias_ids = [user.alias_id.id for user in self.browse(cr, uid, ids, context=context) if user.alias_id]
        res = super(res_users, self).unlink(cr, uid, ids, context=context)
        alias_pool.unlink(cr, uid, alias_ids, context=context)
        return res
    
    def message_append(self, cr, uid, threads, subject, body_text=None, body_html=None,
                        type='email', email_date=None, parent_id=False,
                        content_subtype='plain', state=None,
                        partner_ids=None, email_from=False, email_to=False,
                        email_cc=None, email_bcc=None, reply_to=None,
                        headers=None, message_id=False, references=None,
                        attachments=None, original=None, context=None):
        """ Wrapper on message_append to redirect them to the related partner. """
        for user in self.browse(cr, uid, threads, context=context):
            user.partner_id.message_append(subject, body_text, body_html, type, email_date, parent_id,
                content_subtype, state, partner_ids, email_from, email_to, email_cc, email_bcc, reply_to,
                headers, message_id, references, attachments, original)


class res_users_mail_group(osv.osv):
    """ Update of res.groups class
        - if adding/removing users from a group, check mail.groups linked to
          this user group, and subscribe / unsubscribe them from the discussion
          group. This is done by overriding the write method.
    """
    _name = 'res.users'
    _inherit = ['res.users']

    def write(self, cr, uid, ids, vals, context=None):
        write_res = super(res_users_mail_group, self).write(cr, uid, ids, vals, context=context)
        if vals.get('groups_id'):
            # form: {'group_ids': [(3, 10), (3, 3), (4, 10), (4, 3)]} or {'group_ids': [(6, 0, [ids]}
            user_group_ids = [command[1] for command in vals['groups_id'] if command[0] == 4]
            user_group_ids += [id for command in vals['groups_id'] if command[0] == 6 for id in command[2]]
            mail_group_obj = self.pool.get('mail.group')
            mail_group_ids = mail_group_obj.search(cr, uid, [('group_ids', 'in', user_group_ids)], context=context)
            mail_group_obj.message_subscribe(cr, uid, mail_group_ids, ids, context=context)
        return write_res
        

class res_groups_mail_group(osv.osv):
    """ Update of res.groups class
        - if adding/removing users from a group, check mail.groups linked to
          this user group, and subscribe / unsubscribe them from the discussion
          group. This is done by overriding the write method.
    """
    _name = 'res.groups'
    _inherit = 'res.groups'

    def write(self, cr, uid, ids, vals, context=None):
        if vals.get('users'):
            # form: {'group_ids': [(3, 10), (3, 3), (4, 10), (4, 3)]} or {'group_ids': [(6, 0, [ids]}
            user_ids = [command[1] for command in vals['users'] if command[0] == 4]
            user_ids += [id for command in vals['users'] if command[0] == 6 for id in command[2]]
            mail_group_obj = self.pool.get('mail.group')
            mail_group_ids = mail_group_obj.search(cr, uid, [('group_ids', 'in', ids)], context=context)
            mail_group_obj.message_subscribe(cr, uid, mail_group_ids, user_ids, context=context)
        return super(res_groups_mail_group, self).write(cr, uid, ids, vals, context=context)
