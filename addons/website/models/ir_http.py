# -*- coding: utf-8 -*-
import datetime
import hashlib
import logging
import re
import traceback
import werkzeug
import werkzeug.routing

import openerp
from openerp.addons.base import ir
from openerp.addons.base.ir import ir_qweb
from openerp.addons.website.models.website import slug
from openerp.http import request
from openerp.osv import orm

logger = logging.getLogger(__name__)

class RequestUID(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)

class ir_http(orm.AbstractModel):
    _inherit = 'ir.http'

    rerouting_limit = 10

    def _get_converters(self):
        return dict(
            super(ir_http, self)._get_converters(),
            model=ModelConverter,
            page=PageConverter,
        )

    def _dispatch(self):
        first_pass = not hasattr(request, 'website')
        request.website = None
        func = None
        try:
            func, arguments = self._find_handler()
            request.website_enabled = func.routing.get('website', False)
        except werkzeug.exceptions.NotFound:
            # either we have a language prefixed route, either a real 404
            # in all cases, website processes them
            request.website_enabled = True

        if request.website_enabled:
            if func:
                self._authenticate(func.routing['auth'])
            else:
                self._auth_method_public()
            request.website = request.registry['website'].get_current_website(request.cr, request.uid, context=request.context)
            if first_pass:
                request.lang = request.website.default_lang_code
            request.context['lang'] = request.lang
            request.website.preprocess_request(request)
            if not func:
                path = request.httprequest.path.split('/')
                langs = [lg[0] for lg in request.website.get_languages()]
                if path[1] in langs:
                    request.lang = request.context['lang'] = path.pop(1)
                    path = '/'.join(path) or '/'
                    return self.reroute(path)
                return self._handle_exception(code=404)
        return super(ir_http, self)._dispatch()

    def reroute(self, path):
        if not hasattr(request, 'rerouting'):
            request.rerouting = []
        if path in request.rerouting:
            raise Exception("Rerouting loop is forbidden")
        request.rerouting.append(path)
        if len(request.rerouting) > self.rerouting_limit:
            raise Exception("Rerouting limit exceeded")
        request.httprequest.environ['PATH_INFO'] = path
        # void werkzeug cached_property. TODO: find a proper way to do this
        for key in ('path', 'full_path', 'url', 'base_url'):
            request.httprequest.__dict__.pop(key, None)

        return self._dispatch()

    def _postprocess_args(self, arguments, rule):
        if not getattr(request, 'website_enabled', False):
            return super(ir_http, self)._postprocess_args(arguments, rule)

        for arg, val in arguments.items():
            # Replace uid placeholder by the current request.uid
            if isinstance(val, orm.browse_record) and isinstance(val._uid, RequestUID):
                val._uid = request.uid
        try:
            _, path = rule.build(arguments)
            assert path is not None
        except Exception:
            return self._handle_exception(werkzeug.exceptions.NotFound())

        generated_path = werkzeug.url_unquote_plus(path)
        current_path = werkzeug.url_unquote_plus(request.httprequest.path)
        if generated_path != current_path:
            if request.lang != request.website.default_lang_code:
                path = '/' + request.lang + path
            return werkzeug.utils.redirect(path)

    def _serve_attachment(self):
        domain = [('type', '=', 'binary'), ('url', '=', request.httprequest.path)]
        attach = self.pool['ir.attachment'].search_read(request.cr, openerp.SUPERUSER_ID, domain, ['__last_update', 'datas', 'mimetype'], context=request.context)
        if attach:
            wdate = attach[0]['__last_update']
            datas = attach[0]['datas']
            response = werkzeug.wrappers.Response()
            server_format = openerp.tools.misc.DEFAULT_SERVER_DATETIME_FORMAT
            try:
                response.last_modified = datetime.datetime.strptime(wdate, server_format + '.%f')
            except ValueError:
                # just in case we have a timestamp without microseconds
                response.last_modified = datetime.datetime.strptime(wdate, server_format)

            response.set_etag(hashlib.sha1(datas).hexdigest())
            response.make_conditional(request.httprequest)

            if response.status_code == 304:
                return response

            response.mimetype = attach[0]['mimetype']
            response.set_data(datas.decode('base64'))
            return response

    def _handle_exception(self, exception=None, code=500):
        if isinstance(exception, werkzeug.exceptions.HTTPException) and hasattr(exception, 'response') and exception.response:
            return exception.response

        attach = self._serve_attachment()
        if attach:
            return attach

        if getattr(request, 'website_enabled', False) and request.website:
            values = dict(
                exception=exception,
                traceback=traceback.format_exc(exception),
            )
            if exception:
                code = getattr(exception, 'code', code)
                if isinstance(exception, ir_qweb.QWebException):
                    values.update(qweb_exception=exception)
                    if isinstance(exception.qweb.get('cause'), openerp.exceptions.AccessError):
                        code = 403
            if code == 500:
                logger.error("500 Internal Server Error:\n\n%s", values['traceback'])
                if 'qweb_exception' in values:
                    view = request.registry.get("ir.ui.view")
                    views = view._views_get(request.cr, request.uid, exception.qweb['template'], request.context)
                    to_reset = [v for v in views if v.model_data_id.noupdate is True]
                    values['views'] = to_reset
            elif code == 403:
                logger.warn("403 Forbidden:\n\n%s", values['traceback'])

            values.update(
                status_message=werkzeug.http.HTTP_STATUS_CODES[code],
                status_code=code,
            )

            if not request.uid:
                self._auth_method_public()

            try:
                html = request.website._render('website.%s' % code, values)
            except Exception:
                html = request.website._render('website.http_error', values)
            return werkzeug.wrappers.Response(html, status=code, content_type='text/html;charset=utf-8')

        return super(ir_http, self)._handle_exception(exception)

class ModelConverter(ir.ir_http.ModelConverter):
    def __init__(self, url_map, model=False):
        super(ModelConverter, self).__init__(url_map, model)
        self.regex = r'(?:[A-Za-z0-9-_]+?-)?(\d+)(?=$|/)'

    def to_url(self, value):
        return slug(value)

    def to_python(self, value):
        m = re.match(self.regex, value)
        _uid = RequestUID(value=value, match=m, converter=self)
        return request.registry[self.model].browse(
            request.cr, _uid, int(m.group(1)), context=request.context)

    def generate(self, cr, uid, query=None, context=None):
        return request.registry[self.model].name_search(
            cr, uid, name=query or '', context=context)

class PageConverter(werkzeug.routing.PathConverter):
    """ Only point of this converter is to bundle pages enumeration logic

    Sads got: no way to get the view's human-readable name even if one exists
    """
    def generate(self, cr, uid, query=None, context=None):
        View = request.registry['ir.ui.view']
        views = View.search_read(
            cr, uid, [['page', '=', True]],
            fields=[], order='name', context=context)
        xids = View.get_external_id(
            cr, uid, [view['id'] for view in views], context=context)

        for view in views:
            xid = xids[view['id']]
            if xid and (not query or query.lower() in xid.lower()):
                yield xid
