# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# Main contributor: Nicolas Bessi. Camptocamp SA
# Financial contributors: Hasa SA, Open Net SA,
#                         Prisme Solutions Informatique SA, Quod SA
# Translation contributors: brain-tec AG, Agile Business Group
{
    'name': "Switzerland - Accounting",

    'description': """
Swiss localization
==================
This module defines a chart of account for Switzerland (Swiss PME/KMU 2015), taxes and enables the generation of ISR when you print an invoice or send it by mail.

An ISR will be generated if you specify the information it needs :
    - The bank account you expect to be paid on must be set, and have a valid postal reference.
    - Your invoice must have been set assigned a bank account to receive its payment
    (this can be done manually, but a default value is automatically set if you have defined a bank account).
    - You must have set the postal references of your bank.
    - Your invoice must be in EUR or CHF (as ISRs do not accept other currencies)

The generation of the ISR is automatic if you meet the previous criteria.

Here is how it works:
    - Printing the invoice will trigger the download of two files: the invoice, and its ISR
    - Clicking the 'Send by mail' button will attach two files to your draft mail : the invoice, and the corresponding ISR.
    """,
    'version': '10.0',
    'author': 'Odoo S.A',
    'category': 'Localization',

    'depends': ['account', 'l10n_multilang', 'base_iban'],

    'data': [
        'data/l10n_ch_chart_data.xml',
        'data/account_data.xml',
        'data/account_vat2011_data.xml',
        'data/account_fiscal_position_data.xml',
        'data/account_chart_template_data.yml',
        'report/isr_report.xml',
        'views/res_bank_view.xml',
        'views/account_invoice_view.xml',
        'views/account_config_settings_views.xml',
    ],

    'demo': [
        '../account/demo/account_bank_statement.yml',
        '../account/demo/account_invoice_demo.yml',
    ],
    'post_init_hook': 'load_translations',

}
