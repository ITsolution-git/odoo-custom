
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
    'name': 'Extended Module to Add CalDav feature on Meeting',
    'version': '1.1',
    'category': 'Generic Modules/CRM & SRM',
    'description': """
    New Features in Meeting:
        *  Share meeting with other calendar clients like sunbird
""",
    'author': 'OpenERP SA',
    'website': 'http://www.openerp.com',
    'depends': ['caldav', 'crm' ],
    'init_xml': [
                'crm_caldav_data.xml',
                'crm_caldav_setup.xml',
                ],

    'update_xml': ['crm_caldav_view.xml'],
    'demo_xml': [],
    'installable': True,
    'active': False,
    'certificate' : '001088048737252670109',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
