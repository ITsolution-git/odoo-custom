{
    'name': 'Anonymous portal',
    'description': """
Allow anonymous to Access Portal.
=================================
 """,
    'author': 'OpenERP SA',
    'version': '1.0',
    'category': 'Hidden',
    'website': 'http://www.openerp.com',
    'installable': True,
    'depends': ['portal', 'auth_anonymous'],
    'data': [
        'security/ir.model.access.csv',
        'portal_anonymous_data.xml',
    ],
}
