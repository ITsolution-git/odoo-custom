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
    'name': 'Accounting follow-ups management',
    'version': '1.0',
    'category': 'Generic Modules/Accounting',
    'description': """
    Modules to automate letters for unpaid invoices, with multi-level recalls.

    You can define your multiple levels of recall through the menu:
        Financial Management/Configuration/Follow-Ups

    Once it's defined, you can automatically print recalls every day
    through simply clicking on the menu:
        Financial Management/Periodical Processing/Send followups

    It will generate a PDF with all the letters according the the
    different levels of recall defined. You can define different policies
    for different companies. You can send also mail to the customer.

    Note that if you want to change the followup level for a given partner/account entry, you can do it in the menu:
        Accounting/Reporting/Follow-Ups/All receivable entries

""",
    'author': 'Tiny',
    'website': 'http://www.openerp.com',
    'depends': ['account'],
    'init_xml': [],
    'update_xml': [
        'security/ir.model.access.csv',
        'wizard/account_followup_print_view.xml',
        'account_followup_report.xml',
        'account_followup_view.xml',
        'account_followup_data.xml'
    ],
    'demo_xml': ['account_followup_demo.xml'],
    'installable': True,
    'active': False,
    'certificate': '0072481076453',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
