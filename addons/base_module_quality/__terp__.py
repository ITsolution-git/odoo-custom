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
    'name': 'Base module quality',
    'version': '1.0',
    'category': 'Tiny Specific Modules/Base module quality',
    'description': """This module's aim is to check the quality of other modules.

    It defines a wizard on the list of modules in OpenERP, which allow you to evaluate them on different criteria such as: the respect of OpenERP coding standards, the speed efficiency...

    This module also provides generic framework to define your own quality test. For further info, coders may take a look into base_module_quality\README.txt
""",
    'author': 'Tiny',
    'depends': ['base'],
    'init_xml': [],
    'update_xml': ['base_module_quality_wizard.xml', 'security/ir.model.access.csv'],
    'installable': True,
    'active': False,
    'certificate': '75119475677',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
