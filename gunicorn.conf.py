# Gunicorn sample configuration file.
# See http://gunicorn.org/configure.html for more details.
#
# To run OpenERP via Gunicorn, change the appropriate
# settings below, in order to provide the parameters that
# would normally be passed in the command-line,
# (at least `bind` and `conf['addons_path']`), then execute:
#  $ gunicorn openerp:wsgi.application -c gunicorn.conf.py

import openerp

# Standard OpenERP XML-RPC port is 8069
bind = '127.0.0.1:8069'

pidfile = '.gunicorn.pid'

# Gunicorn recommends 2-4 x number_of_cpu_cores, but
# you'll want to vary this a bit to find the best for your
# particular work load.
workers = 10

# Some application-wide initialization is needed.
on_starting = openerp.wsgi.on_starting
pre_request = openerp.wsgi.pre_request
post_request = openerp.wsgi.post_request

# openerp request-response cycle can be quite long for
# big reports for example
timeout = 240

max_requests = 2000

#accesslog = '/tmp/blah.txt'

# Equivalent of --load command-line option
openerp.conf.server_wide_modules = ['web']

# internal TODO: use openerp.conf.xxx when available
conf = openerp.tools.config

# Path to the OpenERP Addons repository (comma-separated for
# multiple locations)
conf['addons_path'] = '/home/thu/repos/addons/trunk,/home/thu/repos/web/trunk/addons'

# Optional database config if not using local socket
#conf['db_name'] = 'mycompany'
#conf['db_host'] = 'localhost'
#conf['db_user'] = 'foo'
#conf['db_port'] = 5432
#conf['db_password'] = 'secret'

# OpenERP Log Level
# DEBUG=10, DEBUG_RPC=8, DEBUG_RPC_ANSWER=6, DEBUG_SQL=5, INFO=20,
# WARNING=30, ERROR=40, CRITICAL=50
# conf['log_level'] = 20

# If --static-http-enable is used, path for the static web directory
#conf['static_http_document_root'] = '/var/www'

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
