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
    "name": "Human Resources",
    "version": "1.1",
    "author": "OpenERP SA",
    "category": "Generic Modules/Human Resources",
    "website": "http://www.openerp.com",
    "description": """
    Module for human resource management. You can manage:
    * Employees and hierarchies : You can define your employee with User and display hierarchies
    * HR Departments
    * HR Jobs
    """,
    'author': 'OpenERP SA',
    'website': 'http://www.openerp.com',
    'depends': ['resource', 'board'],
    'init_xml': [],
    'update_xml': [
        'security/hr_security.xml',
        'security/ir.model.access.csv',
        'hr_view.xml',
        'hr_department_view.xml',
        'process/hr_process.xml',
        'hr_installer.xml',
        'hr_data.xml',
        'board_hr_view.xml',
        'board_hr_manager_view.xml',
        ],
    'demo_xml': [
        'hr_demo.xml',
        'hr_department_demo.xml',
        ],
    'test': ['test/test_hr.yml'],
    'installable': True,
    'active': False,
    'certificate': '0086710558965',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
