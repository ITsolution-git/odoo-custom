# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2013-Today OpenERP SA (<http://www.openerp.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp import SUPERUSER_ID
from openerp.addons.web import http
from openerp.addons.web.http import request
from openerp.addons.website.models import website


class sale_quote(http.Controller):
    def _get_partner_user(self, order_id):
        order_pool = request.registry.get('sale.order')
        user_pool = request.registry.get('res.users')
        partner = order_pool.browse(request.cr, SUPERUSER_ID, order_id, context=request.context).partner_id.id
        if partner:
            user = user_pool.search(request.cr, SUPERUSER_ID, [('partner_id', '=', partner)])[0]
        return user

    @website.route(["/quote/<int:order_id>/<token>"], type='http', auth="public")
    def view(self, order_id, token, **post):
        # use SUPERUSER_ID allow to access/view order for public user
        order = request.registry.get('sale.order').browse(request.cr, SUPERUSER_ID, order_id)
        assert token == order.access_token, 'Access denied, wrong token!'
        values = {
            'quotation': order,
        }
        return request.website.render('website_sale_quote.so_quotation', values)

    @website.route(['/quote/<int:order_id>/<token>/accept'], type='http', auth="public")
    def accept(self, order_id, token, **post):
        order = request.registry.get('sale.order').browse(request.cr, SUPERUSER_ID, order_id)
        assert token == order.access_token, 'Access denied, wrong token!'
        request.registry.get('sale.order').write(request.cr, self._get_partner_user(order_id), [order_id], {'state': 'manual'})
        return request.redirect("/quote/%s/%s" % (order_id, token))

    def decline(self, order_id):
        return request.registry.get('sale.order').write(request.cr, self._get_partner_user(order_id), [order_id], {'state': 'cancel'})

    @website.route(['/quote/<int:order_id>/<token>/post'], type='http', auth="public")
    def post(self, order_id, token, **post):
        # use SUPERUSER_ID allow to access/view order for public user
        order = request.registry.get('sale.order').browse(request.cr, SUPERUSER_ID, order_id)
        assert token == order.access_token, 'Access denied, wrong token!'

        if post.get('new_message'):
            request.session.body = post.get('new_message')
        if post.get('decline_message'):
            self.decline(order_id)
            request.session.body = post.get('decline_message')
        if 'body' in request.session and request.session.body:
            request.registry.get('sale.order').message_post(request.cr, self._get_partner_user(order_id), order_id,
                    body=request.session.body,
                    type='comment',
                    subtype='mt_comment',
                )
            request.session.body = False
        return request.redirect("/quote/%s/%s#chat" % (order_id, self._get_token(order_id)))

    @website.route(['/quote/update_line'], type='json', auth="public")
    def update(self, line_id=None, remove=False, unlink=False, order_id=None, **post):
        if unlink:
            return request.registry.get('sale.order.line').unlink(request.cr, SUPERUSER_ID, [int(line_id)], context=request.context)
        val = self._update_order_line(line_id=int(line_id), number=(remove and -1 or 1))
        order = request.registry.get('sale.order').browse(request.cr, SUPERUSER_ID, order_id)
        return [str(val), str(order.amount_total)]

    def _update_order_line(self, line_id, number):
        order_line_obj = request.registry.get('sale.order.line')
        order_line_val = order_line_obj.read(request.cr, SUPERUSER_ID, [line_id], [], context=request.context)[0]
        quantity = order_line_val['product_uom_qty'] + number
        order_line_obj.write(request.cr, SUPERUSER_ID, [line_id], {'product_uom_qty': (quantity)}, context=request.context)
        return quantity

    @website.route(["/template/<model('sale.quote.template'):quote>"], type='http', auth="public")
    def template_view(self, quote=None, **post):
        quote = request.registry.get('sale.quote.template').browse(request.cr, request.uid, quote.id)
        values = {
            'template': quote,
        }
        return request.website.render('website_sale_quote.so_template', values)
