# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2010-Today OpenERP S.A. (<http://www.openerp.com>).
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

{
    'name': 'Social Networking',
    'version': '1.0',
    'category':'Social Network',
    "sequence": 2,
    'description': """
A bussiness oriented Social Networking stands with message storage,
queuing and  feeds.     
===================================================================

This Social Networking service that enables its users to send and read 
text-based posts via feeds,and its provide a unified social network 
abstraction that all other applications can use,also it used as a email
subsystem.

The main features are:
    
    * Trouble free application.
    * Hassle free user communication via feeds menu.
    * And also it relies on the global Outgoing Mail Servers configured
      in the , Administration menu for delivering outgoing mail.
    * Includes queuing mechanism with automated configurable
      scheduler-based processing
    * Provides an API for sending messages and archiving them,
      grouped by conversation,
    * Any OpenERP document can act as a conversation topic, provided
      it includes the necessary support for handling incoming emails
      (see the ``mail.thread`` class for more details). 
    * Includes a generic email composition assistant, that can turn
      into a mass-mailing assistant, and is capable of interpreting
      simple *placeholder expressions* that will be replaced with
      dynamic data when each email is actually sent.
      This generic assistant is easily extensible to provide advanced
      features (see ``email_template`` for example, which adds email
      templating features to this assistant)

    """,
    'author': 'OpenERP SA',
    'website': 'http://www.openerp.com',
    'depends': ['base', 'base_tools'],
    'data': [
        'wizard/mail_compose_message_view.xml',
        'mail_message_view.xml',
        'mail_subscription_view.xml',
        'mail_thread_view.xml',
        'mail_group_view.xml',
        'res_partner_view.xml',
        'security/mail_security.xml',
        'security/ir.model.access.csv',
        'mail_data.xml',
        'mail_group_data.xml',
        'res_users_view.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application':True,
    'certificate': '001056784984222247309',
    'images': [
        'images/customer_history.jpeg',
        'images/messages_form.jpeg',
        'images/messages_list.jpeg',
        'static/src/img/email_icong.png',
        'static/src/img/_al.png',
        'static/src/img/_pincky.png',
        'static/src/img/feeds.png',
        'static/src/img/feeds-hover.png',
        'static/src/img/groupdefault.png',
    ],
    'css': [
        'static/src/css/mail.css',
        'static/src/css/mail_group.css',
    ],
    'js': [
        'static/src/js/mail.js',
    ],
    'qweb': [
        'static/src/xml/mail.xml',
    ],
    'demo': [
        'mail_demo.xml',
    ],
    
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
