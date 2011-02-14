# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2009 Sharoon Thomas
#    Copyright (C) 2010-2010 OpenERP SA (<http://www.openerp.com>)
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
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################

{
    "name" : "Email Template for OpenERP",
    "version" : "0.7 RC",
    "author" : "Openlabs",
    "website" : "http://openerp.com",
    "category" : "Added functionality",
    "depends" : ['marketing', 'base_tools'],
    "description": """
    Email Template is extraction of Power Email basically just to send the emails.
    """,
    "init_xml": ['email_template_scheduler_data.xml'],
    "update_xml": [
        'security/email_template_security.xml',
        'email_template_workflow.xml',
        'email_template_account_view.xml',
        'email_template_view.xml',
        'email_template_mailbox_view.xml',
        'wizard/email_template_send_wizard_view.xml',
        'security/ir.model.access.csv'
    ],
    "installable": True,
    "active": False,
    "certificate" : "00817073628967384349",
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
