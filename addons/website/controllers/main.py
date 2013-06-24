# -*- coding: utf-8 -*-

import openerp
from openerp.addons.web import http
from openerp.addons.web.http import request

class Website(openerp.addons.web.controllers.main.Home):

    @http.route('/', type='http', auth="db")
    def index(self, **kw):
        with open(openerp.addons.get_module_resource('website', 'views', 'homepage.html'), 'rb') as f:
            return f.read()

    @http.route('/admin', type='http', auth="none")
    def admin(self, *args, **kw):
        return super(Website, self).index(*args, **kw)


# vim:expandtab:tabstop=4:softtabstop=4:shiftwidth=4:
