# -*- coding: utf-8 -*-
import functools
import simplejson

import openerp
from openerp.osv import osv, fields
from openerp.addons.web import http
from openerp.addons.web.http import request
import urllib
from urlparse import urljoin
import math
import traceback
from openerp.tools.safe_eval import safe_eval
from openerp.exceptions import AccessError, AccessDenied
import werkzeug

import logging
logger = logging.getLogger(__name__)

def route(routes, *route_args, **route_kwargs):
    def decorator(f):
        new_routes = routes if isinstance(routes, list) else [routes]
        f.multilang = route_kwargs.get('multilang', False)
        if f.multilang:
            route_kwargs.pop('multilang')
            for r in list(new_routes):
                new_routes.append('/<string(length=5):lang_code>' + r)
        @http.route(new_routes, *route_args, **route_kwargs)
        @functools.wraps(f, assigned=functools.WRAPPER_ASSIGNMENTS + ('func_name',))
        def wrap(*args, **kwargs):
            request.route_lang = kwargs.get('lang_code', None)
            if not hasattr(request, 'website'):
                request.multilang = f.multilang
                request.website = request.registry['website'].get_current()
                if request.route_lang:
                    lang_ok = [lg.code for lg in request.website.language_ids if lg.code == request.route_lang]
                    if not lang_ok:
                        return request.not_found()
                request.website.preprocess_request(*args, **kwargs)
            return f(*args, **kwargs)
        return wrap
    return decorator

def auth_method_public():
    registry = openerp.modules.registry.RegistryManager.get(request.db)
    if not request.session.uid:
        request.uid = registry['website'].get_public_user().id
    else:
        request.uid = request.session.uid
http.auth_methods['public'] = auth_method_public

def url_for(path, lang=None):
    if request:
        path = urljoin(request.httprequest.path, path)
        langs = request.context.get('langs')
        if path[0] == '/' and len(langs) > 1:
            ps = path.split('/')
            lang = lang or request.context.get('lang')
            if ps[1] in langs:
                ps[1] = lang
            else:
                ps.insert(1, lang)
            path = '/'.join(ps)
    return path

def urlplus(url, params):
    if not params:
        return url

    # can't use urlencode because it encodes to (ascii, replace) in p2
    return "%s?%s" % (url, '&'.join(
        k + '=' + urllib.quote_plus(v if isinstance(v, str) else v.encode('utf-8'))
        for k, v in params.iteritems()
    ))

class website(osv.osv):
    _name = "website" # Avoid website.website convention for conciseness (for new api). Got a special authorization from xmo and rco
    _description = "Website"
    _columns = {
        'name': fields.char('Domain'),
        'company_id': fields.many2one('res.company', string="Company"),
        'language_ids': fields.many2many('res.lang', 'website_lang_rel', 'website_id', 'lang_id', 'Languages'),
        'default_lang_id': fields.many2one('res.lang', string="Default language"),
        'social_twitter': fields.char('Twitter Account'),
        'social_facebook': fields.char('Facebook Account'),
        'social_github': fields.char('GitHub Account'),
        'social_linkedin': fields.char('LinkedIn Account'),
        'social_youtube': fields.char('Youtube Account'),
        'social_googleplus': fields.char('Google+ Account'),
    }

    public_user = None

    def get_public_user(self):
        if not self.public_user:
            ref = request.registry['ir.model.data'].get_object_reference(request.cr, openerp.SUPERUSER_ID, 'website', 'public_user')
            self.public_user = request.registry[ref[0]].browse(request.cr, openerp.SUPERUSER_ID, ref[1])
        return self.public_user

    def get_lang(self):
        website = request.registry['website'].get_current()

        if hasattr(request, 'route_lang'):
            lang = request.route_lang
        else:
            lang = request.params.get('lang', None) or request.httprequest.cookies.get('lang', None)

        if lang not in [lg.code for lg in website.language_ids]:
            lang = website.default_lang_id.code

        return lang

    def preprocess_request(self, cr, uid, ids, *args, **kwargs):
        def redirect(url):
            return werkzeug.utils.redirect(url_for(url))
        request.redirect = redirect

        is_public_user = request.uid == self.get_public_user().id
        lang = self.get_lang()
        is_master_lang = lang == request.website.default_lang_id.code
        request.context.update({
            'lang': lang,
            'lang_selected': [lg for lg in request.website.language_ids if lg.code == lang],
            'langs': [lg.code for lg in request.website.language_ids],
            'multilang': request.multilang,
            'is_public_user': is_public_user,
            'is_master_lang': is_master_lang,
            'editable': not is_public_user,
            'translatable': not is_public_user and not is_master_lang and request.multilang,
        })

    def get_current(self):
        # WIP, currently hard coded
        return self.browse(request.cr, request.uid, 1)

    def render(self, cr, uid, ids, template, values=None):
        view = request.registry.get("ir.ui.view")
        IMD = request.registry.get("ir.model.data")
        user = request.registry.get("res.users")

        qweb_context = request.context.copy()

        if values:
            qweb_context.update(values)

        qweb_context.update(
            request=request,
            registry=request.registry,
            json=simplejson,
            website=request.website,
            url_for=url_for,
            res_company=request.website.company_id,
            user_id=user.browse(cr, uid, uid),
        )

        context = request.context.copy()
        context.update(
            inherit_branding=qweb_context.setdefault('editable', False),
        )

        # check if xmlid of the template exists
        try:
            module, xmlid = template.split('.', 1)
            IMD.get_object_reference(cr, uid, module, xmlid)
        except ValueError: # catches both unpack errors and gor errors
            module, xmlid = 'website', template
            try:
                IMD.get_object_reference(cr, uid, module, xmlid)
            except ValueError:
                logger.error("Website Rendering Error.\n\n%s" % traceback.format_exc())
                return self.render(cr, uid, ids, 'website.404', qweb_context)

        try:
            return view.render(cr, uid, "%s.%s" % (module, xmlid),
                               qweb_context, context=context)
        except (AccessError, AccessDenied), err:
            logger.error(err)
            qweb_context['error'] = err[1]
            logger.warn("Website Rendering Error.\n\n%s" % traceback.format_exc())
            return self.render(cr, uid, ids, 'website.401', qweb_context)
        except Exception:
            logger.exception("Website Rendering Error.")
            qweb_context['traceback'] = traceback.format_exc()
            return view.render(
                cr, uid,
                'website.500' if qweb_context['editable'] else 'website.404',
                qweb_context, context=context)

    def pager(self, cr, uid, ids, url, total, page=1, step=30, scope=5, url_args=None):
        # Compute Pager
        page_count = int(math.ceil(float(total) / step))

        page = max(1, min(int(page), page_count))
        scope -= 1

        pmin = max(page - int(math.floor(scope/2)), 1)
        pmax = min(pmin + scope, page_count)

        if pmax - pmin < scope:
            pmin = pmax - scope if pmax - scope > 0 else 1

        def get_url(page):
            _url = "%spage/%s/" % (url, page)
            if url_args:
                _url = "%s?%s" % (_url, urllib.urlencode(url_args))
            return _url

        return {
            "page_count": page_count,
            "offset": (page - 1) * step,
            "page": {'url': get_url(page), 'num': page},
            "page_start": {'url': get_url(pmin), 'num': pmin},
            "page_end": {'url': get_url(min(pmax, page + 1)),
                         'num': min(pmax, page + 1)},
            "pages": [
                {'url': get_url(page), 'num': page}
                for page in xrange(pmin, pmax+1)
            ]
        }

    def list_pages(self, cr, uid, ids, context=None):
        """ Available pages in the website/CMS. This is mostly used for links
        generation and can be overridden by modules setting up new HTML
        controllers for dynamic pages (e.g. blog).

        By default, returns template views marked as pages.

        :returns: a list of mappings with two keys: ``name`` is the displayable
                  name of the resource (page), ``url`` is the absolute URL
                  of the same.
        :rtype: list({name: str, url: str})
        """
        View = self.pool['ir.ui.view']
        views = View.search_read(cr, uid, [['page', '=', True]],
                                 fields=['name'], order='name', context=context)
        xids = View.get_external_id(cr, uid, [view['id'] for view in views], context=context)

        return [
            {'name': view['name'], 'url': '/page/' + xids[view['id']]}
            for view in views
            if xids[view['id']]
        ]

    def kanban(self, cr, uid, ids, model, domain, column, template, step=None, scope=None, orderby=None):
        step = step and int(step) or 10
        scope = scope and int(scope) or 5
        orderby = orderby or "name"

        get_args = dict(request.httprequest.args or {})
        model_obj = request.registry[model]
        relation = model_obj._columns.get(column)._obj
        relation_obj = request.registry[relation]

        get_args.setdefault('kanban', "")
        kanban = get_args.pop('kanban')
        kanban_url = "?%s&kanban=" % urllib.urlencode(get_args)

        pages = {}
        for col in kanban.split(","):
            if col:
                col = col.split("-")
                pages[int(col[0])] = int(col[1])

        objects = []
        for group in model_obj.read_group(cr, uid, domain, ["id", column], groupby=column):
            obj = {}

            # browse column
            relation_id = group[column][0]
            obj['column_id'] = relation_obj.browse(cr, uid, relation_id)

            obj['kanban_url'] = kanban_url
            for k, v in pages.items():
                if k != relation_id:
                    obj['kanban_url'] += "%s-%s" % (k, v)

            # pager
            number = model_obj.search(cr, uid, group['__domain'], count=True)
            obj['page_count'] = int(math.ceil(float(number) / step))
            obj['page'] = pages.get(relation_id) or 1
            if obj['page'] > obj['page_count']:
                obj['page'] = obj['page_count']
            offset = (obj['page']-1) * step
            obj['page_start'] = max(obj['page'] - int(math.floor((scope-1)/2)), 1)
            obj['page_end'] = min(obj['page_start'] + (scope-1), obj['page_count'])

            # view data
            obj['domain'] = group['__domain']
            obj['model'] = model
            obj['step'] = step
            obj['orderby'] = orderby

            # browse objects
            object_ids = model_obj.search(cr, uid, group['__domain'], limit=step, offset=offset, order=orderby)
            obj['object_ids'] = model_obj.browse(cr, uid, object_ids)

            objects.append(obj)

        values = {
            'objects': objects,
            'range': range,
            'template': template,
        }
        return request.website.render("website.kanban_contain", values)

    def kanban_col(self, cr, uid, ids, model, domain, page, template, step, orderby):
        html = ""
        model_obj = request.registry[model]
        domain = safe_eval(domain)
        step = int(step)
        offset = (int(page)-1) * step
        object_ids = model_obj.search(cr, uid, domain, limit=step, offset=offset, order=orderby)
        object_ids = model_obj.browse(cr, uid, object_ids)
        for object_id in object_ids:
            html += request.website.render(template, {'object_id': object_id})
        return html

class ir_attachment(osv.osv):
    _inherit = "ir.attachment"
    def _website_url_get(self, cr, uid, ids, name, arg, context=None):
        context = context or {}
        result = {}
        for attach in self.browse(cr, uid, ids, context=context):
            if attach.type=='url':
                result[attach.id] = attach.url
            else:
                result[attach.id] = "/website/attachment/"+str(attach.id)
        return result
    _columns = {
        'website_url': fields.function(_website_url_get, string="Attachment URL", type='char')
    }

class res_partner(osv.osv):
    _inherit = "res.partner"

    def google_map_img(self, cr, uid, ids, zoom=8, width=298, height=298, context=None):
        partner = self.browse(cr, uid, ids[0], context=context)
        params = {
            'center': '%s, %s %s, %s' % (partner.street, partner.city, partner.zip, partner.country_id and partner.country_id.name_get()[0][1] or ''),
            'size': "%sx%s" % (height, width),
            'zoom': zoom,
            'sensor': 'false',
        }
        return urlplus('http://maps.googleapis.com/maps/api/staticmap' , params)

    def google_map_link(self, cr, uid, ids, zoom=8, context=None):
        partner = self.browse(cr, uid, ids[0], context=context)
        params = {
            'q': '%s, %s %s, %s' % (partner.street, partner.city, partner.zip, partner.country_id and partner.country_id.name_get()[0][1] or ''),
        }
        return urlplus('https://maps.google.be/maps' , params)

class base_language_install(osv.osv):
    _inherit = "base.language.install"
    _columns = {
        'website_ids': fields.many2many('website', string='Websites to translate'),
    }

    def lang_install(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        action = super(base_language_install, self).lang_install(cr, uid, ids, context)
        language_obj = self.browse(cr, uid, ids)[0]
        website_ids = [website.id for website in language_obj['website_ids']]
        lang_id = self.pool['res.lang'].search(cr, uid, [('code', '=', language_obj['lang'])])
        if website_ids and lang_id:
            data = {'language_ids': [(4, lang_id[0])]}
            self.pool['website'].write(cr, uid, website_ids, data)
        params = context.get('params', {})
        if 'url_return' in params:
            return {
                'url': params['url_return'].replace('[lang]', language_obj['lang']),
                'type': 'ir.actions.act_url',
                'target': 'self'
            }
        return action
