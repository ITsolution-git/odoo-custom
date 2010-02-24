# -*- coding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
import wizard
import time
import pooler
import tools
import os
_email_form = '''<?xml version="1.0"?>
<form string="Email Gateway">
    <separator string="Fetching Emails : " />
    <field name="server" colspan="4" nolabel="1" />
 </form>'''

_email_done_form = '''<?xml version="1.0"?>
<form string="Email Gateway"> 
    <separator string="Log Detail" />
    <newline/>   
    <field name="message" colspan="4" nolabel="1"/>
 </form>'''

_email_fields = {
    'server': {'string':"Server", 'type':'text', 'readonly':True},
       }

_email_done_fields = {
    'message': {'string':"Log Detail", 'type':'text', 'readonly':True},
       }

def _default(self , cr, uid, data, context):
    pool = pooler.get_pool(cr.dbname)
    gateway_pool = pool.get('mail.gateway')
    server = []
    for mail_gateway in gateway_pool.browse(cr, uid, data['ids'], context=context):
        if mail_gateway.server_id.active:
            server.append(mail_gateway.name or '%s (%s)' % (mail_gateway.server_id.login, mail_gateway.server_id.name))
    data['form']['server'] = '\n'.join(server)
    return data['form']

def section_fetch_mail(self , cr, uid, data, context):
    pool = pooler.get_pool(cr.dbname)
    gateway_pool = pool.get('mail.gateway')
    messages = gateway_pool.fetch_mails(cr, uid, ids=data['ids'], context=context)
    data['form']['message'] = '\n'.join(messages)
    return data['form']

class wiz_mailgateway_fetch_mail(wizard.interface):
    states = {
        'init': {
            'actions': [_default],
            'result': {'type': 'form', 'arch':_email_form, 'fields':_email_fields, 'state':[('end', 'Cancel', 'gtk-cancel'), ('fetch', 'Fetch', 'gtk-execute')]}
                },
        'fetch': {
            'actions': [section_fetch_mail],
            'result': {'type': 'form', 'arch': _email_done_form,
                'fields': _email_done_fields,
                'state': (
                    ('end', 'Close'),
                )
            },
        },
    }
wiz_mailgateway_fetch_mail('mail_gateway.fetchmail')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
