{
    'name': "Demonstration of web/javascript tests",
    'category': 'Hidden',
    'description': """ 
        OpenERP Web demo of a test suite.
        =======================
        Holds the examples used in the testing documentation.
    """,
    'depends': ['web'],
    'js': ['static/src/js/demo.js'],
    'test': ['static/test/demo.js'],
    'qweb': ['static/src/xml/demo.xml'],
}
