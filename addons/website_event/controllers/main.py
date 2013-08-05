# -*- coding: utf-8 -*-

from openerp import SUPERUSER_ID
from openerp.addons.web import http
from openerp.addons.web.http import request
from openerp.addons.website import website
from openerp.tools.translate import _

from datetime import datetime
from dateutil.relativedelta import relativedelta
from openerp import tools
import urllib


class website_hr(http.Controller):

    @http.route(['/event'], type='http', auth="public")
    def events(self, **searches):
        event_obj = request.registry['event.event']

        searches.setdefault('date', 'all')
        searches.setdefault('type', 'all')
        searches.setdefault('country', 'all')
        
        domain_search = {}

        def sd(date):
            return date.strftime(tools.DEFAULT_SERVER_DATETIME_FORMAT)
        today = datetime.today()
        dates = [
            ['all', _('All Dates'), [(1, "=", 1)], 0],
            ['today', _('Today'), [
                ("date_begin", ">", sd(today)),
                ("date_begin", "<", sd(today + relativedelta(days=1)))],
                0],
            ['tomorrow', _('Tomorrow'), [
                ("date_begin", ">", sd(today + relativedelta(days=1))),
                ("date_begin", "<", sd(today + relativedelta(days=2)))],
                0],
            ['week', _('This Week'), [
                ("date_begin", ">=", sd(today + relativedelta(days=-today.weekday()))),
                ("date_begin", "<", sd(today  + relativedelta(days=6-today.weekday())))],
                0],
            ['nextweek', _('Next Week'), [
                ("date_begin", ">=", sd(today + relativedelta(days=7-today.weekday()))),
                ("date_begin", "<", sd(today  + relativedelta(days=13-today.weekday())))],
                0],
            ['month', _('This month'), [
                ("date_begin", ">=", sd(today.replace(day=1) + relativedelta(months=1))),
                ("date_begin", "<", sd(today.replace(day=1)  + relativedelta(months=1)))],
                0],
        ]

        # search domains
        for date in dates:
            if searches.get("date") == date[0]:
                domain_search["date"] = date[2]
        if searches.get("type", "all") != 'all':
            domain_search["type"] = [("type", "=", int(searches.get("type")))]
        if searches.get("country", "all") != 'all':
            domain_search["country"] = [("country_id", "=", int(searches.get("country")))]

        def dom_without(without):
            domain = [(1, "=", 1)]
            for key, search in domain_search.items():
                if key != without:
                    domain += search
            print domain
            return domain

        # count by domains without self search
        for date in dates:
            date[3] = event_obj.search(request.cr, request.uid, dom_without('date') + date[2], count=True)

        domain = dom_without('type')
        types = event_obj.read_group(request.cr, request.uid, domain, ["id", "type"], groupby="type", orderby="type")
        types.insert(0, {'type_count': event_obj.search(request.cr, request.uid, domain, count=True), 'type': ("all", _("All Categories"))})

        domain = dom_without('country')
        countries = event_obj.read_group(request.cr, request.uid, domain, ["id", "country_id"], groupby="country_id", orderby="country_id")
        countries.insert(0, {'country_id_count': event_obj.search(request.cr, request.uid, domain, count=True), 'country_id': ("all", _("All Countries"))})


        obj_ids = event_obj.search(request.cr, request.uid, dom_without("none"))
        values = {
            'event_ids': event_obj.browse(request.cr, request.uid, obj_ids),
            'dates': dates,
            'types': types,
            'countries': countries,
            'searches': searches,
            'search_path': "?%s" % urllib.urlencode(searches),
        }

        html = website.render("website_event.index", values)
        return html

    @http.route(['/event/<int:event_id>'], type='http', auth="public")
    def event(self, event_id=None, **post):
        return ""

    @http.route(['/event/publish'], type='http', auth="public")
    def publish(self, **post):
        obj_id = int(post['id'])
        data_obj = request.registry['event.event']

        obj = data_obj.browse(request.cr, request.uid, obj_id)
        data_obj.write(request.cr, request.uid, [obj_id], {'website_published': not obj.website_published})
        obj = data_obj.browse(request.cr, request.uid, obj_id)

        return obj.website_published and "1" or "0"
