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
    'name': 'Customer Portal Feedback',
    'version': '0.1',
    'category': 'Tools',
    'complexity': "easy",
    'description': """
    This module add the menu if claim and portal_customer is install.
    """,
    'author': 'OpenERP SA',
    'depends': ['survey','portal_customer'],
    'update_xml': [
        'portal_customer_feedback_view.xml',
        "security/ir.model.access.csv",
    ],
    'installable': True,
    'auto_install':True,
    'category':'Hidden',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
