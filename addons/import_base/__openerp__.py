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
    'name': 'Framework for complex import',
    'version': '0.9',
    'category': 'Hidden/Dependency',
    'description': """
        This module provide a class import_framework to help importing 
        complex data from other software
    """,
    'author': 'OpenERP SA',
    'website': 'http://www.openerp.com',
    'depends': ['base','mail'],
    'init_xml': [],
    'update_xml': ["import_base_view.xml"],
    'demo_xml': [],
    'test': [], #TODO provide test
    'installable': True,
    'auto_install': False,
    'certificate': '00141537995453',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
