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

from openerp.addons.web import http
from openerp.addons.web.http import request
from openerp.addons.website import website
from openerp.tools.translate import _
from openerp.tools.safe_eval import safe_eval

import simplejson
import werkzeug


class website_mail(http.Controller):
    _category_post_per_page = 6
    _post_comment_per_page = 6

    @website.route([
        '/blog/',
        '/blog/<int:category_id>/',
        '/blog/<int:category_id>/<int:blog_post_id>/',
        '/blog/<int:category_id>/page/<int:page>/',
        '/blog/<int:category_id>/<int:blog_post_id>/page/<int:page>/',
        '/blog/tag/',
        '/blog/tag/<int:tag_id>/',
    ], type='http', auth="public")
    def blog(self, category_id=None, blog_post_id=None, tag_id=None, page=1, **post):
        """ Prepare all values to display the blog.

        :param integer category_id: id of the category currently browsed.
        :param integer tag_id: id of the tag that is currently used to filter
                               blog posts
        :param integer blog_post_id: ID of the blog post currently browsed. If not
                                     set, the user is browsing the category and
                                     a post pager is calculated. If set the user
                                     is reading the blog post and a comments pager
                                     is calculated.
        :param integer page: current page of the pager. Can be the category or
                            post pager.
        :param dict post: kwargs, may contain

         - 'unable_editor': editor control

        :return dict values: values for the templates, containing

         - 'blog_post': browse of the current post, if blog_post_id
         - 'blog_posts': list of browse records that are the posts to display
                         in a given category, if not blog_post_id
         - 'category': browse of the current category, if category_id
         - 'categories': list of browse records of categories
         - 'pager': the pager to display, posts pager in a category or comments
                    pager in a blog post
         - 'tag': current tag, if tag_id
         - 'nav_list': a dict [year][month] for archives navigation
        """
        cr, uid, context = request.cr, request.uid, request.context
        blog_post_obj = request.registry['blog.post']
        tag_obj = request.registry['blog.tag']
        category_obj = request.registry['blog.category']
        user_obj = request.registry['res.users']

        tag = None
        category = None
        blog_post = None
        blog_posts = None
        pager = None
        nav = {}

        category_ids = category_obj.search(cr, uid, [], context=context)
        categories = category_obj.browse(cr, uid, category_ids, context=context)

        if tag_id:
            tag = tag_obj.browse(cr, uid, tag_id, context=context)
        if category_id:
            category = category_obj.browse(cr, uid, category_id, context=context)

        if category and blog_post_id:
            blog_post = blog_post_obj.browse(cr, uid, blog_post_id, context=context)
            blog_message_ids = blog_post.website_message_ids
        else:
            if category and tag:
                blog_posts = [cat_post for cat_post in category.blog_post_ids
                              if tag_id in [post_tag.id for post_tag in cat_post.tag_ids]]
            elif category:
                blog_posts = category.blog_post_ids
            elif tag:
                blog_posts = tag.blog_post_ids

        if blog_posts:
            pager = request.website.pager(
                url="/blog/%s/" % category_id,
                total=len(blog_posts),
                page=page,
                step=self._category_post_per_page,
                scope=7
            )
            pager_begin = (page - 1) * self._category_post_per_page
            pager_end = page * self._category_post_per_page
            blog_posts = blog_posts[pager_begin:pager_end]

        if blog_post:
            pager = request.website.pager(
                url="/blog/%s/%s/" % (category_id, blog_post_id),
                total=len(blog_message_ids),
                page=page,
                step=self._post_comment_per_page,
                scope=7
            )
            pager_begin = (page - 1) * self._post_comment_per_page
            pager_end = page * self._post_comment_per_page
            blog_post.website_message_ids = blog_post.website_message_ids[pager_begin:pager_end]

        for group in blog_post_obj.read_group(cr, uid, [], ['name', 'create_date'], groupby="create_date", orderby="create_date asc", context=context):
            year = group['create_date'].split(" ")[1]
            if not year in nav:
                nav[year] = {'name': year, 'create_date_count': 0, 'months': []}
            nav[year]['create_date_count'] += group['create_date_count']
            nav[year]['months'].append(group)

        values = {
            'categories': categories,
            'category': category,
            'tag': tag,
            'blog_post': blog_post,
            'blog_posts': blog_posts,
            'pager': pager,
            'nav_list': nav,
            'unable_editor': post.get('unable_editor')
        }

        return request.website.render("website_blog.index", values)

    @website.route(['/blog/nav'], type='http', auth="public")
    def nav(self, **post):
        cr, uid, context = request.cr, request.uid, request.context
        blog_post_ids = request.registry['blog.post'].search(
            cr, uid, safe_eval(post.get('domain')),
            order="create_date asc",
            limit=None,
            context=context
        )
        blog_post_data = [
            {
                'id': blog_post.id,
                'name': blog_post.name,
                'website_published': blog_post.website_published,
                'category_id': blog_post.category_id and blog_post.category_id.id or False,
            }
            for blog_post in request.registry['blog.post'].browse(cr, uid, blog_post_ids, context=context)
        ]
        return simplejson.dumps(blog_post_data)

    @website.route(['/blog/<int:category_id>/<int:blog_post_id>/post'], type='http', auth="public")
    def blog_comment(self, category_id=None, blog_post_id=None, **post):
        cr, uid, context = request.cr, request.uid, request.context
        url = request.httprequest.host_url
        request.session.body = post.get('body')
        if request.context['is_public_user']:  # purpose of this ?
            return '%s/admin#action=redirect&url=%s/blog/%s/%s/post' % (url, url, category_id, blog_post_id)

        if request.session.get('body') and blog_post_id:
            request.registry['blog.post'].message_post(
                cr, uid, blog_post_id,
                body=request.session.body,
                type='comment',
                subtype='mt_comment',
                context=dict(context, mail_create_nosubcribe=True))
            request.session.body = False

        return werkzeug.utils.redirect("/blog/%s/%s/?unable_editor=1" % (category_id, blog_post_id))

    @website.route(['/blog/<int:category_id>/new'], type='http', auth="public")
    def create_blog_post(self, category_id=None, **post):
        cr, uid, context = request.cr, request.uid, request.context
        create_context = dict(context, mail_create_nosubscribe=True)
        blog_post_id = request.registry['blog.post'].create(
            request.cr, request.uid, {
                'category_id': category_id,
                'name': _("Blog title"),
                'content': '',
                'website_published': False,
            }, context=create_context)
        return werkzeug.utils.redirect("/blog/%s/%s/?unable_editor=1" % (category_id, blog_post_id))
