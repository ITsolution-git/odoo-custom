import common
import controllers
import common.dispatch

try:
    import openerp
    import os
    import tempfile
    print "embedded mode"
    class Options(object):
        pass
    o = Options()
    o.dbfilter = '.*'
    o.session_storage = os.path.join(tempfile.gettempdir(), "oe-sessions")
    o.addons_path = os.path.dirname(os.path.dirname(__file__))
    o.serve_static = True
    o.server_host = '127.0.0.1'
    o.server_port = 8069

    app = common.dispatch.Root(o)
    #import openerp.wsgi
    openerp.wsgi.register_wsgi_handler(app)

except ImportError:
    print "standalone mode"

# TODO
# if we detect that we are imported from the openerp server register common.Root() as a wsgi entry point

