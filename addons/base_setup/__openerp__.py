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
    'name': 'Base Setup',
    'version': '1.0',
    'category': 'Generic Modules/Base',
    'description': """
    This module implements a configuration system that helps user
    to configure the system at the installation of a new database.

    It allows you to select between a list of profiles to install:
    * Minimal profile
    * Accounting only
    * Services companies
    * Manufacturing companies

    It also asks screens to help easily configure your company, the header and
    footer, the account chart to install and the language.
    """,
    'author': 'OpenERP SA',
    'website': 'http://www.openerp.com',
    'depends': ['base'],
    'init_xml': ['base_setup_data.xml'],
    'update_xml': ['security/ir.model.access.csv',
                   'base_setup_installer.xml',
                   'base_setup_todo.xml',
                   ],
    'demo_xml': ['base_setup_demo.xml'],
    'installable': True,
    'active': True,
    'certificate': '0086711085869',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
