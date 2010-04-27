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


{
    'name': 'CRM Phonecalls',
    'version': '1.0',
    'category': 'Generic Modules/CRM & SRM',
    'description': """Phonecalls""",
    'author': 'Tiny',
    'website': 'http://www.openerp.com',
    'depends': ['crm'],
    'init_xml': [
         'crm_phonecall_data.xml',
    ],

    'update_xml': [
        'wizard/crm_phonecall_to_phonecall_view.xml',
        'wizard/crm_phonecall_to_partner_view.xml',
        'wizard/crm_phonecall_to_opportunity_view.xml',

        'crm_phonecall_view.xml',
        'crm_phonecall_menu.xml',

        'security/ir.model.access.csv',
        'report/crm_phonecall_report_view.xml',
    ],
    'demo_xml': [
        'crm_phonecall_demo.xml',
    ],
    'installable': True,
    'active': False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
