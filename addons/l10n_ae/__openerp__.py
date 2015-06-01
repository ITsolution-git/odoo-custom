# -*- encoding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Copyright (C) 2014 Tech Receptives (<http://techreceptives.com>)

{
    'name': 'U.A.E. - Accounting',
    'version': '1.0',
    'author': 'Tech Receptives',
    'website': 'http://www.techreceptives.com',
    'category': 'Localization/Account Charts',
    'description': """
United Arab Emirates accounting chart and localization.
=======================================================

    """,
    'depends': ['base', 'account'],
    'demo': [ ],
    'data': [
             'l10n_ae_chart.xml',
             'l10n_ae_wizard.xml',
    ],
    'installable': False,
}
