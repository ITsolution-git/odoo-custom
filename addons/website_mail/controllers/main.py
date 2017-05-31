# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from hashlib import sha1
from time import time
from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import request


def object_shasign(record=False, res_model='', res_id=None, **kw):
    """ Generate a sha signature using the current time, database secret and the
    record object or the res_model and res_id parameters
        Return the sha signature and the time of generation in a tuple"""
    secret = request.env['ir.config_parameter'].sudo().get_param('database.secret')
    shasign = False
    timestamp = int(time())
    if record:
        shasign = sha1('%s%s%s%s' % (record._model, record.id, secret, timestamp)).hexdigest()
    elif res_model and res_id:
        shasign = sha1('%s%s%s%s' % (res_model, res_id, secret, timestamp)).hexdigest()
    return (shasign, timestamp)


def _message_post_helper(res_model='', res_id=None, message='', token='', token_field='token', sha_in='', sha_time=None, nosubscribe=True, **kw):
    """ Generic chatter function, allowing to write on *any* object that inherits mail.thread.
        If a token or a shasign is specified, all logged in users will be able to write a message regardless
        of access rights; if the user is the public user, the message will be posted under the name
        of the partner_id of the object (or the public user if there is no partner_id on the object).

        :param string res_model: model name of the object
        :param int res_id: id of the object
        :param string message: content of the message

        optional keywords arguments:
        :param string token: access token if the object's model uses some kind of public access
                             using tokens (usually a uuid4) to bypass access rules
        :param string token_field: name of the field that contains the token on the object (defaults to 'token')
        :param string sha_in: sha1 hash of the string composed of res_model, res_id and the dabase secret in ir.config_parameter
                               if you wish to allow public users to write on the object with some security but you don't want
                               to add a token field on the object, the sha-sign prevents public users from writing to any other
                               object that the one specified by res_model and res_id
                               to generate the shasign, you can import the function object_shasign from this file in your controller
        :param str sha_time: timestamp of sha signature generation (signatures are valid for 24h)
        :param bool nosubscribe: set False if you want the partner to be set as follower of the object when posting (default to True)

        The rest of the kwargs are passed on to message_post()
    """
    record = request.env[res_model].browse(res_id)
    author_id = request.env.user.partner_id.id if request.env.user.partner_id else False
    if token and record and token == getattr(record.sudo(), token_field, None):
        record = record.sudo()
        if request.env.user == request.env.ref('base.public_user'):
            author_id = record.partner_id.id if hasattr(record, 'partner_id') else author_id
        else:
            if not author_id:
                raise NotFound()
    elif sha_in:
        timestamp = int(sha_time)
        secret_sudo = request.env['ir.config_parameter'].sudo().get_param('database.secret')
        shasign = sha1('%s%s%s%s' % (res_model, res_id, secret_sudo, timestamp))
        if sha_in == shasign.hexdigest() and int(time()) < timestamp + 3600 * 24:
            record = record.sudo()
        else:
            raise NotFound()
    kw.pop('csrf_token', None)
    return record.with_context(mail_create_nosubscribe=nosubscribe).message_post(body=message,
                                                                                   message_type=kw.pop('message_type', "comment"),
                                                                                   subtype=kw.pop('subtype', "mt_comment"),
                                                                                   author_id=author_id,
                                                                                   **kw)


class WebsiteMail(http.Controller):

    @http.route(['/website_mail/follow'], type='json', auth="public", website=True)
    def website_message_subscribe(self, id=0, object=None, message_is_follower="on", email=False, **post):
        # TDE FIXME: check this method with new followers
        res_id = int(id)
        is_follower = message_is_follower == 'on'
        record = request.env[object].browse(res_id)

        # search partner_id
        if request.env.user != request.website.user_id:
            partner_ids = request.env.user.partner_id.ids
        else:
            # mail_thread method
            partner_ids = record.sudo()._find_partner_from_emails([email], check_followers=True)
            if not partner_ids or not partner_ids[0]:
                name = email.split('@')[0]
                partner_ids = request.env['res.partner'].sudo().create({'name': name, 'email': email}).ids
        # add or remove follower
        if is_follower:
            record.check_access_rule('read')
            record.sudo().message_unsubscribe(partner_ids)
            return False
        else:
            record.check_access_rule('read')
            # add partner to session
            request.session['partner_id'] = partner_ids[0]
            record.sudo().message_subscribe(partner_ids)
            return True

    @http.route(['/website_mail/is_follower'], type='json', auth="public", website=True)
    def is_follower(self, model, res_id, **post):
        user = request.env.user
        partner = None
        public_user = request.website.user_id
        if user != public_user:
            partner = request.env.user.partner_id
        elif request.session.get('partner_id'):
            partner = request.env['res.partner'].sudo().browse(request.session.get('partner_id'))

        values = {
            'is_user': user != public_user,
            'email': partner.email if partner else "",
            'is_follower': False,
            'alias_name': False,
        }

        record = request.env[model].sudo().browse(int(res_id))
        if record and partner:
            values['is_follower'] = bool(request.env['mail.followers'].search_count([
                ('res_model', '=', model),
                ('res_id', '=', record.id),
                ('partner_id', '=', partner.id)
            ]))
        return values

    @http.route(['/website_mail/post/json'], type='json', auth='public', website=True)
    def chatter_json(self, res_model='', res_id=None, message='', **kw):
        try:
            msg = _message_post_helper(res_model, int(res_id), message, **kw)
        except Exception:
            return False
        data = {
            'id': msg.id,
            'body': msg.body,
            'date': msg.date,
            'author': msg.author_id.name,
            'image_url': '/mail/%s/%s/avatar/%s' % (msg.model, msg.res_id, msg.author_id.id)
        }
        return data

    @http.route(['/website_mail/post/post'], type='http', methods=['POST'], auth='public', website=True)
    def chatter_post(self, res_model='', res_id=None, message='', redirect=None, **kw):
        url = request.httprequest.referrer
        if message:
            message = _message_post_helper(res_model, int(res_id), message, **kw)
            url = url + "#message-%s" % (message.id,)
        return request.redirect(url)
