# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


{
    'name': 'Report Creator',
    'version': '1.0',
    'category': 'Generic Modules/Base',
    'description': """This modules allows you to create any statistic
report on several object. It's a SQL query builder and browser
for and users.

After installing the module, it adds a menu to define custom report in
the "Dashboard" menu.
""",
    'author': 'Tiny & Axelor',
    'website': '',
    'depends': ['base', 'board'],
    'init_xml': [],
    'update_xml': [
        'security/ir.model.access.csv',
        'base_report_creator_wizard.xml',
        'base_report_creator_view.xml'
    ],
    'demo_xml': [],
    'installable': True,
    'active': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
