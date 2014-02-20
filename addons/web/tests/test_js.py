import urlparse
from openerp import sql_db, tools
from qunitsuite.suite import QUnitSuite

class WebSuite(QUnitSuite):
    def __init__(self):
        url = urlparse.urlunsplit([
            'http',
            'localhost:{port}'.format(port=tools.config['xmlrpc_port']),
            '/web/tests',
            'mod=*&source={db}&supadmin={supadmin}&password={password}'.format(
                db=tools.config['db_name'],
                supadmin=tools.config['admin_passwd'],
                password='admin'),
            ''
        ])
        super(WebSuite, self).__init__(url, 50000)

def load_tests(loader, standard_tests, _):
    standard_tests.addTest(WebSuite())
    return standard_tests
