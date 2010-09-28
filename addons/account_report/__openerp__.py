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
    'name': 'Reporting for accounting',
    'version': '1.1',
    'category': 'Generic Modules/Accounting',
    'description': """Financial and accounting reporting
    Fiscal statements
    Indicators
    Adds a dashboard for accountant that include  Indicators reporting.
    """,
    'author': 'OpenERP SA',
    'website': 'http://www.openerp.com',
    'depends': ['account'],
    'init_xml': [],
    'update_xml': [
        'security/ir.model.access.csv',
        'account_view.xml',
        'account_report.xml',
        'account_wizard.xml',
        'wizard/account_report_print_indicators_view.xml',
        'wizard/account_report_print_indicators_with_pdf_view.xml',
        'board_account_report_view.xml',
    ],
    'demo_xml': ['account_report_demo.xml'],
    'test': ['test/account_report.yml'],
    'installable': True,
    'active': False,
    'certificate': '0050976406925',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
