# -*- coding: utf-8 -*-

{
    'name': 'Product Email Template',
    'depends': ['account'],
    'author': 'OpenERP SA',
    'category': 'Accounting & Finance',
    'description': """
Add email templates to products to be send on invoice confirmation
==================================================================

With this module, link your products to a template to send complete information and tools to your customer.
For instance when invoicing a training, the training agenda and materials will automatically be send to your customers.'
    """,
    'website': 'http://www.openerp.com',
    'demo': [
        'data/product_demo.xml',
    ],
    'data': [
        'views/product_view.xml',
        'views/email_template_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}
