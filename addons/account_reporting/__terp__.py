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
    'name': 'Reporting of Balancesheet for accounting',
    'version': '1.0',
    'category': 'Generic Modules/Accounting',
    'description': """Financial and accounting reporting
    Balance Sheet Report""",
    'author': 'Tiny',
    'depends': ['account'],
    'init_xml': [],
    'update_xml': [   'security/ir.model.access.csv',
    'account_view.xml',
    'account_report.xml',
    'account_data.xml'],
    'demo_xml': [],
    'installable': True,
    'active': False,
    'certificate': '0010472149969149',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
