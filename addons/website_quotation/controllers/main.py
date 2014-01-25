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
import werkzeug
import datetime

from openerp.tools.translate import _

class sale_quote(http.Controller):

    @http.route([
        "/quote/<int:order_id>",
        "/quote/<int:order_id>/<token>"
    ], type='http', auth="public", website=True)
    def view(self, order_id, token=None, message=False, **post):
        # use SUPERUSER_ID allow to access/view order for public user
        order = request.registry.get('sale.order').browse(request.cr, token and SUPERUSER_ID or request.uid, order_id)
        print order.name
        if token:
            assert token == order.access_token, 'Access denied!'
            body=_('Quotation viewed by customer')
            self.message_post(body, order_id, type='comment')
        # TODO: if not order.template_id: return to the URL of the portal view of SO
        values = {
            'quotation': order,
            'message': message,
            'new_post' : request.httprequest.session.get('new_post',False),
            'option': self._check_option_len(order),
            'date_diff': order.validity_date and (datetime.datetime.now() > datetime.datetime.strptime(order.validity_date , '%Y-%m-%d')) or False,
            'salesperson' : False if token else True
        }
        return request.website.render('website_quotation.so_quotation', values)

    def _check_option_len(self, order):
        for option in order.options:
            if not option.line_id:
                return True
        return False

    @http.route(['/quote/accept'], type='json', auth="public", website=True)
    def accept(self, order_id=None, token=None, signer=None, sign=None, **post):
        order_obj = request.registry.get('sale.order')
        order = order_obj.browse(request.cr, SUPERUSER_ID, order_id)
        assert token == order.access_token, 'Access denied, wrong token!'
        error = {}
        if not signer: error['signer'] = 'missing'
        if not sign: error['sign'] = 'missing'
        if not error:
            attachment = {
                'name': 'sign.png',
                'datas':sign,
                'datas_fname': 'sign.png',
                'res_model': 'sale.order',
                'res_id': order_id,
            }
            request.registry['ir.attachment'].create(request.cr, request.uid, attachment, context=request.context)
            order_obj.write(request.cr, request.uid, [order_id], {'signer_name':signer,'state': 'manual'})
        return [error]

    @http.route(['/quote/<int:order_id>/<token>/decline'], type='http', auth="public", website=True)
    def decline(self, order_id, token, **post):
        message = post.get('decline_message')
        request.registry.get('sale.order').write(request.cr, request.uid, [order_id], {'state': 'cancel'})
        if message:
            self.message_post(message, order_id, type='comment', subtype='mt_comment')
        return werkzeug.utils.redirect("/quote/%s/%s?message=2" % (order_id, token))

    @http.route(['/quote/<int:order_id>/<token>/post'], type='http', auth="public", website=True)
    def post(self, order_id, token, **post):
        # use SUPERUSER_ID allow to access/view order for public user
        order_obj = request.registry.get('sale.order')
        order = order_obj.browse(request.cr, SUPERUSER_ID, order_id)
        message = post.get('comment')
        assert token == order.access_token, 'Access denied, wrong token!'
        if message:
            self.message_post(message, order_id, type='comment', subtype='mt_comment')
            request.httprequest.session['new_post'] = True
        return werkzeug.utils.redirect("/quote/%s/%s?message=1" % (order_id, token))

    def message_post(self , message, order_id, type='comment', subtype=False):
        request.session.body =  message
        cr, uid, context = request.cr, request.uid, request.context
        user = request.registry['res.users'].browse(cr, SUPERUSER_ID, uid, context=context)
        if 'body' in request.session and request.session.body:
            request.registry.get('sale.order').message_post(cr, SUPERUSER_ID, order_id,
                    body=request.session.body,
                    type=type,
                    subtype=subtype,
                    author_id=user.partner_id.id,
                    context=context,
                )
            request.session.body = False
        return True

    @http.route(['/quote/update_line'], type='json', auth="public", website=True)
    def update(self, line_id=None, remove=False, unlink=False, order_id=None, token=None, **post):
        order = request.registry.get('sale.order').browse(request.cr, SUPERUSER_ID, int(order_id))
        assert token == order.access_token, 'Access denied, wrong token!'
        if unlink:
            request.registry.get('sale.order.line').unlink(request.cr, SUPERUSER_ID, [int(line_id)], context=request.context)
            return False
        val = self._update_order_line(line_id=int(line_id), number=(remove and -1 or 1))
        return [str(val), str(order.amount_total)]

    def _update_order_line(self, line_id, number):
        order_line_obj = request.registry.get('sale.order.line')
        order_line_val = order_line_obj.read(request.cr, SUPERUSER_ID, [line_id], [], context=request.context)[0]
        quantity = order_line_val['product_uom_qty'] + number
        order_line_obj.write(request.cr, SUPERUSER_ID, [line_id], {'product_uom_qty': (quantity)}, context=request.context)
        return quantity

    @http.route(["/template/<model('sale.quote.template'):quote>"], type='http', auth="user", website=True)
    def template_view(self, quote, **post):
        values = {
            'template': quote,
        }
        return request.website.render('website_quotation.so_template', values)
        

    @http.route(["/quote/add_line/<int:option_id>/<int:order_id>/<token>"], type='http', auth="public", website=True)
    def add(self, option_id, order_id, token, **post):
        vals = {}
        order = request.registry.get('sale.order').browse(request.cr, SUPERUSER_ID, order_id)
        assert token == order.access_token, 'Access denied, wrong token!'
        option_obj = request.registry.get('sale.option.line')
        option = option_obj.browse(request.cr, SUPERUSER_ID, option_id)
        vals.update({
            'price_unit': option.price_unit,
            'website_description': option.website_description,
            'name': option.name,
            'order_id': order.id,
            'product_id' : option.product_id.id,
            'product_uom_qty': option.quantity,
            'product_uom_id': option.uom_id.id,
            'discount': option.discount,
        })
        line = request.registry.get('sale.order.line').create(request.cr, SUPERUSER_ID, vals, context=request.context)
        option_obj.write(request.cr, SUPERUSER_ID, [option.id], {'line_id': line}, context=request.context)
        return werkzeug.utils.redirect("/quote/%s/%s#pricing" % (order.id, token))


