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
    'name': 'CRM Management - Reporting',
    'version': '1.0',
    'category': 'Generic Modules/CRM & SRM',
    'description': """A module that adds new reports based on CRM cases.
    Case By section, Case By category""",
    'author': 'Tiny',
    'website': 'http://www.openerp.com',
    'depends': ['crm'],
    'init_xml': [],
    'update_xml': ['security/ir.model.access.csv',
                   'report_crm_view.xml',
                   'report_crm_lead_view.xml',
                   'report_crm_claim_view.xml',
                   'report_crm_opportunity_view.xml',
                   'report_crm_phonecall_view.xml',
                   'report_crm_fundraising_view.xml'
                   ],
    'demo_xml': [],
    'installable': True, #TODO : After fixed problems , set True
    'active': False,
    'certificate': '0030422968285',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
