# -*- coding: utf-8 -*-
import simplejson

import openerp
from openerp.osv import osv, orm
from openerp.addons.web import http
from openerp.addons.web.controllers import main
from openerp.addons.web.http import request
import urllib
import math
import traceback
from openerp.tools.safe_eval import safe_eval

import logging
logger = logging.getLogger(__name__)


def auth_method_public():
    registry = openerp.modules.registry.RegistryManager.get(request.db)
    if not request.session.uid:
        request.uid = registry['website'].get_public_user().id
    else:
        request.uid = request.session.uid
http.auth_methods['public'] = auth_method_public


def urlplus(url, params):
    if not params:
        return url
    url += "?"
    for k,v in params.items():
        url += "%s=%s&" % (k, urllib.quote_plus(str(v)))
    return url


class website(osv.osv):
    _name = "website" # Avoid website.website convention for conciseness (for new api). Got a special authorization from xmo and rco
    _description = "Website"

    public_user = None

    def get_public_user(self):
        if not self.public_user:
            ref = request.registry['ir.model.data'].get_object_reference(request.cr, openerp.SUPERUSER_ID, 'website', 'public_user')
            self.public_user = request.registry[ref[0]].browse(request.cr, openerp.SUPERUSER_ID, ref[1])
        return self.public_user

    def get_rendering_context(self, additional_values=None):
        debug = 'debug' in request.params
        is_logged = True
        try:
            request.session.check_security()
        except: # TODO fme: check correct exception
            is_logged = False
        is_public_user = request.uid == self.get_public_user().id
        values = {
            'debug': debug,
            'is_public_user': is_public_user,
            'editable': is_logged and not is_public_user,
            'request': request,
            'registry': request.registry,
            'cr': request.cr,
            'uid': request.uid,
            'host_url': request.httprequest.host_url,
            'res_company': request.registry['res.company'].browse(request.cr, openerp.SUPERUSER_ID, 1),
            'json': simplejson,
            'snipped': {
                'kanban': self.kanban
            }
        }
        if additional_values:
            values.update(additional_values)
        return values

    def render(self, template, values={}):
        view = request.registry.get("ir.ui.view")
        context = {
            'inherit_branding': values.get('editable', False),
        }
        try:
            return view.render(request.cr, request.uid, template, values, context=context)
        # except (osv.except_osv, orm.except_orm), err:
        #     logger.error(err)
        #     values['error'] = err[1]
        #     return self.render('website.401', values)
        # except ValueError:
        #     logger.error("Website Rendering Error.\n\n%s" % (traceback.format_exc()))
        #     return self.render('website.404', values)
        except Exception:
            trace = traceback.format_exc()
            logger.error("Website Rendering Error.\n\n%s" % trace)
            if values['editable']:
                values['traceback'] = trace
                return view.render(request.cr, request.uid, 'website.500', values, context=context)
            else:
                return view.render(request.cr, request.uid, 'website.404', values, context=context)

    def pager(self, url, total, page=1, step=30, scope=5, url_args=None):
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

    def list_pages(self, cr, uid, context=None):
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

    def kanban(self, model, domain, column, content, step=None, scope=None, orderby=None):
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
        for group in model_obj.read_group(request.cr, request.uid, domain, ["id", column], groupby=column):
            obj = {}

            # browse column
            relation_id = group[column][0]
            obj['column_id'] = relation_obj.browse(request.cr, request.uid, relation_id)

            obj['kanban_url'] = kanban_url
            for k, v in pages.items():
                if k != relation_id:
                    obj['kanban_url'] += "%s-%s" % (k, v)

            # pager
            number = model_obj.search(request.cr, request.uid, group['__domain'], count=True)
            obj['page'] = pages.get(relation_id) or 1
            obj['page_count'] = int(math.ceil(float(number) / step))
            offset = (obj['page']-1) * step
            obj['page_start'] = max(obj['page'] - int(math.floor((scope-1)/2)), 1)
            obj['page_end'] = min(obj['page_start'] + (scope-1), obj['page_count'])

            # view data
            obj['domain'] = group['__domain']
            obj['model'] = model
            obj['step'] = step
            obj['orderby'] = orderby

            # browse objects
            object_ids = model_obj.search(request.cr, request.uid, group['__domain'], limit=step, offset=offset, order=orderby)
            obj['object_ids'] = model_obj.browse(request.cr, request.uid, object_ids)

            objects.append(obj)

        values = self.get_rendering_context({
            'objects': objects,
            'range': range,
            'content': content,
        })
        return self.render("website.kanban_contain", values)

    def kanban_col(self, model, domain, page, content, step, orderby):
        html = ""
        model_obj = request.registry[model]
        domain = safe_eval(domain)
        step = int(step)
        offset = (int(page)-1) * step
        object_ids = model_obj.search(request.cr, request.uid, domain, limit=step, offset=offset, order=orderby)
        object_ids = model_obj.browse(request.cr, request.uid, object_ids)
        for object_id in object_ids:
            html += self.render(content, self.get_rendering_context({'object_id': object_id}))
        return html

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
