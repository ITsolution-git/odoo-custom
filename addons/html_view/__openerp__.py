{
    "name" : "Html View",
    "version" : "1.1",
    "author" : "OpenERP SA",
    "category" : "Hidden/Test",
    "depends" : ['base'],
    "init_xml" : ['html_view.xml'],
    "demo_xml" : [],
    "description": """
This is the test module which shows HTML tag support in normal XML form view.
=============================================================================

Creates a sample form-view using HTML tags. It is visible only in OpenERP Web.
    """,
    'update_xml': ['security/ir.model.access.csv','html_view.xml',],
    'installable': True,
    'active': False,
    'certificate': '001302129363003126557',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
