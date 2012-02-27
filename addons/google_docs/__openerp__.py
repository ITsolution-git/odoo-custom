{
    'name': 'Google Docs',
    'version': '0.1',
    'author': 'OpenERP SA',
    'website': 'http://openerp.com',
    'data': [
        'google_docs.xml'
    ],
    'installable': True,
    'auto_install': False,
    'web': True,
    'js': ['static/src/js/gdocs.js'],
    'qweb' : [
        "static/src/xml/gdocs.xml",
    ],
    'depends': ['google_base_account'],
    'description': 'Module to attach a google document to any model.'
}
