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
    'name': 'Getting Things Done - Time Management Module',
    'version': '1.0',
    'category': 'Generic Modules/Projects & Services',
    'description': """
This module implements all concepts defined by the Getting Things Done
methodology. This world-wide used methodology is used for personal
time management improvement.

Getting Things Done (commonly abbreviated as GTD) is an action management
method created by David Allen, and described in a book of the same name.

GTD rests on the principle that a person needs to move tasks out of the mind by
recording them externally. That way, the mind is freed from the job of
remembering everything that needs to be done, and can concentrate on actually
performing those tasks.
    """,
    'author': 'OpenERP SA',
    'depends': ['project'],
    'init_xml': [],
    'update_xml': [
        'project_gtd_data.xml',
        'project_gtd_view.xml',
        'security/ir.model.access.csv',
        'wizard/project_gtd_empty_view.xml',
        'wizard/project_gtd_fill_view.xml',
    ],
    'demo_xml': ['project_gtd_demo.xml'],
    'test':[
        'test/gtd_test.yml'
    ],
    'installable': True,
    'active': False,
    'certificate': '0043525236301',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
