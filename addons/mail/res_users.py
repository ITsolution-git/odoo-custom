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

from osv import osv, fields
from tools.translate import _
from lxml import etree

class res_users(osv.osv):
    """ Update of res.users class
        - add a preference about sending emails about notificatoins
        - make a new user follow itself
    """
    _name = 'res.users'
    _inherit = ['res.users', 'mail.thread']
    _inherits = {'mail.alias': 'alias_id'}
    
    _columns = {
        'notification_email_pref': fields.selection([
                        ('all', 'All feeds'),
                        ('comments', 'Only comments'),
                        ('to_me', 'Only when sent directly to me'),
                        ('none', 'Never')
                        ], 'Receive Feeds by Email', required=True,
                        help="Choose in which case you want to receive an email when you receive new feeds."),
        'alias_id': fields.many2one('mail.alias', 'Alias', ondelete="cascade", required=True, 
                                    help="This Unique Mail Box Alias of the User allows to manage the Seamless email communication between Mail Box and OpenERP," 
                                         "This Alias MailBox manage the Users email communication."),
    }
    
    _defaults = {
        'notification_email_pref': 'none',
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
    
    def create(self, cr, uid, data, context=None):
        # create default alias same as the login
        mail_alias = self.pool.get('mail.alias')
        alias_id = mail_alias.create_unique_alias(cr, uid, {'alias_name': data['login'], 'alias_model_id': self._name}, context=context)
        data.update({'alias_id': alias_id})
        user_id = super(res_users, self).create(cr, uid, data, context=context)
        mail_alias.write(cr, uid, [alias_id], {"alias_force_thread_id": user_id}, context)
        user = self.browse(cr, uid, user_id, context=context)
        # make user follow itself
        self.message_subscribe(cr, uid, [user_id], [user_id], context=context)
        # create a welcome message to broadcast
        company_name = user.company_id.name if user.company_id else 'the company'
        message = _('%s has joined %s! You may leave him/her a message to celebrate a new arrival in the company ! You can help him/her doing its first steps on OpenERP.') % (user.name, company_name)
        # TODO: clean the broadcast feature. As this is not cleany specified, temporarily remove the message broadcasting that is not buggy but not very nice.
        #self.message_broadcast(cr, uid, [user.id], 'Welcome notification', message, context=context)
        return user_id
    
    def write(self, cr, uid, ids, vals, context=None):
        # if login of user have been changed then change alias of user also.
        if vals.get('login'):
            vals['alias_name'] = vals['login']
        return super(res_users, self).write(cr, uid, ids, vals, context=context)

    def unlink(self, cr, uid, ids, context=None):
        # Cascade-delete mail aliases as well, as they should not exist without the user.
        alias_pool = self.pool.get('mail.alias')
        alias_ids = [user.alias_id.id for user in self.browse(cr, uid, ids, context=context) if user.alias_id]
        res = super(res_users, self).unlink(cr, uid, ids, context=context)
        alias_pool.unlink(cr, uid, alias_ids, context=context)
        return res
    
    def message_load_ids(self, cr, uid, ids, limit=100, offset=0, domain=[], ascent=False, root_ids=[False], context=None):
        """ Override of message_load_ids
            User discussion page :
            - messages posted on res.users, res_id = user.id
            - messages directly sent to user with @user_login
        """
        if context is None:
            context = {}
        msg_obj = self.pool.get('mail.message')
        msg_ids = []
        for user in self.browse(cr, uid, ids, context=context):
            msg_ids += msg_obj.search(cr, uid, ['|', '|', ('body_text', 'like', '@%s' % (user.login)), ('body_html', 'like', '@%s' % (user.login)), '&', ('res_id', '=', user.id), ('model', '=', self._name)] + domain,
            limit=limit, offset=offset, context=context)
        if (ascent): msg_ids = self._message_add_ancestor_ids(cr, uid, ids, msg_ids, root_ids, context=context)
        return msg_ids
