# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013-Today OpenERP SA (<http://www.openerp.com>)
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

{
    'name': 'Mass Mailing Campaigns',
    'description': """TODO""",
    'version': '1.0',
    'author': 'OpenERP',
    'website': 'http://www.openerp.com',
    'category': 'Marketing',
    'depends': [
        'mail',
        'email_template',
        'web_kanban_gauge',
        'web_kanban_sparkline',
    ],
    'data': [
        'mail_data.xml',
        'mass_mailing_view.xml',
        'mass_mailing_demo.xml',
        'wizard/mail_compose_message_view.xml',
        'wizard/mail_mass_mailing_create_segment.xml',
        'security/ir.model.access.csv',
    ],
    'js': [],
    'qweb': [],
    'css': [
        'static/src/css/mass_mailing.css'
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
}
