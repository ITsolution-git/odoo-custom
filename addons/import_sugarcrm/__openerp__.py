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
    'name': 'SugarCRM Import',
    'version': '1.0',
    'category': 'Customer Relationship Management',
    'description': """This Module Import SugarCRM "Leads", "Opportunities", "Users", "Accounts", 
            "Contacts", "Employees", Meetings, Phonecalls, Emails, and Project, Project Tasks Data into OpenERP Module.""",
    'author': 'OpenERP SA',
    'website': 'http://www.openerp.com',
    'depends': ['import_base','crm', 'document'],
    'data': [
        "wizard/import_message_view.xml",
        "import_sugarcrm_view.xml",
        "security/ir.model.access.csv",
    ],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    'certificate': '00208948154765',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
