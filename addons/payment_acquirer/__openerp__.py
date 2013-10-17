# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013-Today OpenERP SA (<http://www.openerp.com>).
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
    'name': 'Payment acquirer',
    'category': 'Hidden',
    'summary': 'Payment acquirer, display and validate payments',
    'version': '0.1',
    'description': """Payment acquirer module, use to display payment method and validate the payments.""",
    'author': 'OpenERP SA',
    'depends': ['website', 'decimal_precision'],
    'data': [
        'views/acquirer_view.xml',
        'payment_acquirer_data.xml',
        'security/ir.model.access.csv',
        'security/ir.rule.xml',
    ],
    'installable': True,
}
