# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hashlib

from datetime import datetime

from werkzeug import urls

from odoo import api, fields, models


class Users(models.Model):
    _inherit = 'res.users'

    def __init__(self, pool, cr):
        init_res = super(Users, self).__init__(pool, cr)
        type(self).SELF_WRITEABLE_FIELDS = list(
            set(
                self.SELF_WRITEABLE_FIELDS +
                ['country_id', 'city', 'website', 'website_description', 'website_published']))
        return init_res

    create_date = fields.Datetime('Create Date', readonly=True, copy=False, index=True)
    karma = fields.Integer('Karma', default=0)
    badge_ids = fields.One2many('gamification.badge.user', 'user_id', string='Badges', copy=False)
    gold_badge = fields.Integer('Gold badges count', compute="_get_user_badge_level")
    silver_badge = fields.Integer('Silver badges count', compute="_get_user_badge_level")
    bronze_badge = fields.Integer('Bronze badges count', compute="_get_user_badge_level")
    forum_waiting_posts_count = fields.Integer('Waiting post', compute="_get_user_waiting_post")

    @api.multi
    @api.depends('badge_ids')
    def _get_user_badge_level(self):
        """ Return total badge per level of users
        TDE CLEANME: shouldn't check type is forum ? """
        for user in self:
            user.gold_badge = 0
            user.silver_badge = 0
            user.bronze_badge = 0

        self.env.cr.execute("""
            SELECT bu.user_id, b.level, count(1)
            FROM gamification_badge_user bu, gamification_badge b
            WHERE bu.user_id IN %s
              AND bu.badge_id = b.id
              AND b.level IS NOT NULL
            GROUP BY bu.user_id, b.level
            ORDER BY bu.user_id;
        """, [tuple(self.ids)])

        for (user_id, level, count) in self.env.cr.fetchall():
            # levels are gold, silver, bronze but fields have _badge postfix
            self.browse(user_id)['{}_badge'.format(level)] = count

    @api.multi
    def _get_user_waiting_post(self):
        for user in self:
            Post = self.env['forum.post']
            domain = [('parent_id', '=', False), ('state', '=', 'pending'), ('create_uid', '=', user.id)]
            user.forum_waiting_posts_count = Post.search_count(domain)

    @api.model
    def _generate_forum_token(self, user_id, email):
        """Return a token for email validation. This token is valid for the day
        and is a hash based on a (secret) uuid generated by the forum module,
        the user_id, the email and currently the day (to be updated if necessary). """
        forum_uuid = self.env['ir.config_parameter'].sudo().get_param('website_forum.uuid')
        return hashlib.sha256('%s-%s-%s-%s' % (
            datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
            forum_uuid,
            user_id,
            email)).hexdigest()

    @api.one
    def send_forum_validation_email(self, forum_id=None):
        if not self.email:
            return False
        token = self._generate_forum_token(self.id, self.email)
        activation_template = self.env.ref('website_forum.validation_email')
        if activation_template:
            params = {
                'token': token,
                'id': self.id,
                'email': self.email}
            if forum_id:
                params['forum_id'] = forum_id
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            token_url = base_url + '/forum/validate_email?%s' % urls.url_encode(params)
            activation_template.sudo().with_context(token_url=token_url).send_mail(self.id, force_send=True)
        return True

    @api.one
    def process_forum_validation_token(self, token, email, forum_id=None, context=None):
        validation_token = self._generate_forum_token(self.id, email)
        if token == validation_token and self.karma == 0:
            karma = 3
            forum = None
            if forum_id:
                forum = self.env['forum.forum'].browse(forum_id)
            else:
                forum_ids = self.env['forum.forum'].search([], limit=1)
                if forum_ids:
                    forum = forum_ids[0]
            if forum:
                # karma gained: karma to ask a question and have 2 downvotes
                karma = forum.karma_ask + (-2 * forum.karma_gen_question_downvote)
            return self.write({'karma': karma})
        return False

    @api.multi
    def add_karma(self, karma):
        for user in self:
            user.karma += karma
        return True

    # Wrapper for call_kw with inherits
    @api.multi
    def open_website_url(self):
        return self.mapped('partner_id').open_website_url()
