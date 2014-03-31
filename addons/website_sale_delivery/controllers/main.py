# -*- coding: utf-8 -*-
from openerp.addons.website_sale.controllers.main import Ecommerce
from openerp.addons.web import http
from openerp.addons.web.http import request
from openerp import SUPERUSER_ID


class Ecommerce(Ecommerce):

    @http.route(['/shop/payment'], type='http', auth="public", website=True, multilang=True)
    def payment(self, **post):
        cr, uid, context = request.cr, request.uid, request.context
        order = self.get_order()
        carrier_id = post.get('carrier_id')

        if order and carrier_id:
            # recompute delivery costs            
            request.registry['website']._check_carrier_quotation(cr,uid,order,carrier_id,context=context)
            return request.redirect("/shop/payment")

        res = super(Ecommerce, self).payment(**post)
        return res
