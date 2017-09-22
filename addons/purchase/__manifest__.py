# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Purchase Management',
    'version': '1.2',
    'category': 'Purchases',
    'sequence': 60,
    'summary': 'Purchase Orders, Receipts, Vendor Bills',
    'description': "",
    'website': 'https://www.odoo.com/page/purchase',
    'depends': ['stock_account'],
    'data': [
        'security/purchase_security.xml',
        'security/ir.model.access.csv',
        'views/account_invoice_views.xml',
        'data/purchase_data.xml',
        'data/purchase_data.yml',
        'report/purchase_reports.xml',
        'views/purchase_views.xml',
        'views/stock_views.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'views/purchase_template.xml',
        'report/purchase_report_views.xml',
        'data/mail_template_data.xml',
        'views/portal_templates.xml',
        'report/purchase_order_templates.xml',
        'report/purchase_quotation_templates.xml',
    ],
    'test': [
        '../account/test/account_minimal_test.xml',
        'test/stock_valuation_account.xml',
        'test/ui/purchase_users.yml',
        'test/process/run_scheduler.yml',
        'test/fifo_price.yml',
        'test/fifo_returns.yml',
        'test/process/cancel_order.yml',
        'test/ui/duplicate_order.yml',
        'test/ui/delete_order.yml',
        'test/average_price.yml',
    ],
    'demo': [
        'data/purchase_order_demo.yml',
        'data/purchase_demo.xml',
        'data/purchase_stock_demo.yml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
