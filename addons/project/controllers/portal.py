# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import OrderedDict

from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import get_records_pager, CustomerPortal, pager as portal_pager

from odoo.osv.expression import OR


class CustomerPortal(CustomerPortal):

    def _prepare_portal_layout_values(self):
        values = super(CustomerPortal, self)._prepare_portal_layout_values()
        values.update({
            'project_count': request.env['project.project'].search_count([('privacy_visibility', '=', 'portal')]),
            'task_count': request.env['project.task'].search_count([('project_id.privacy_visibility', '=', 'portal')])
        })
        return values

    @http.route(['/my/projects', '/my/projects/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_projects(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        Project = request.env['project.project']
        domain = [('privacy_visibility', '=', 'portal')]

        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'create_date desc'},
            'name': {'label': _('Name'), 'order': 'name'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # archive groups - Default Group By 'create_date'
        archive_groups = self._get_archive_groups('project.project', domain)
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]
        # projects count
        project_count = Project.search_count(domain)
        # pager
        pager = portal_pager(
            url="/my/projects",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=project_count,
            page=page,
            step=self._items_per_page
        )

        # content according to pager and archive selected
        projects = Project.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_projects_history'] = projects.ids[:100]

        values.update({
            'date': date_begin,
            'date_end': date_end,
            'projects': projects,
            'page_name': 'project',
            'archive_groups': archive_groups,
            'default_url': '/my/projects',
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby
        })
        return request.render("project.portal_my_projects", values)

    @http.route(['/my/project/<int:project_id>'], type='http', auth="user", website=True)
    def portal_my_project(self, project_id=None, **kw):
        project = request.env['project.project'].browse(project_id)
        vals = {'project': project}
        history = request.session.get('my_projects_history', [])
        vals.update(get_records_pager(history, project))
        return request.render("project.portal_my_project", vals)

    @http.route(['/my/tasks', '/my/tasks/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_tasks(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, search=None, search_in='content', **kw):
        values = self._prepare_portal_layout_values()
        domain = [('project_id.privacy_visibility', '=', 'portal')]

        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'create_date desc'},
            'name': {'label': _('Title'), 'order': 'name'},
            'stage': {'label': _('Stage'), 'order': 'stage_id'},
            'update': {'label': _('Last Stage Update'), 'order': 'date_last_stage_update desc'},
        }
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
        }
        searchbar_inputs = {
            'content': {'input': 'content', 'label': _('Search <span class="nolabel"> (in Content)</span>')},
            'message': {'input': 'message', 'label': _('Search in Messages')},
            'customer': {'input': 'customer', 'label': _('Search in Customer')},
            'stage': {'input': 'stage', 'label': _('Search in Stages')},
            'all': {'input': 'all', 'label': _('Search in All')},
        }
        # extends filterby criteria with project (criteria name is the project id)
        projects = request.env['project.project'].search([('privacy_visibility', '=', 'portal')])
        for proj in projects:
            searchbar_filters.update({
                str(proj.id): {'label': proj.name, 'domain': [('project_id', '=', proj.id)]}
            })

        # default sort by value
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        # default filter by value
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']

        # archive groups - Default Group By 'create_date'
        archive_groups = self._get_archive_groups('project.task', domain)
        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        # search
        if search and search_in:
            search_domain = []
            if search_in in ('content', 'all'):
                search_domain = OR([search_domain, ['|', ('name', 'ilike', search), ('description', 'ilike', search)]])
            if search_in in ('customer', 'all'):
                search_domain = OR([search_domain, [('partner_id', 'ilike', search)]])
            if search_in in ('message', 'all'):
                search_domain = OR([search_domain, [('message_ids.body', 'ilike', search)]])
            if search_in in ('stage', 'all'):
                search_domain = OR([search_domain, [('stage_id', 'ilike', search)]])
            domain += search_domain

        # task count
        task_count = request.env['project.task'].search_count(domain)
        # pager
        pager = portal_pager(
            url="/my/tasks",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby},
            total=task_count,
            page=page,
            step=self._items_per_page
        )
        # content according to pager and archive selected
        tasks = request.env['project.task'].search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_tasks_history'] = tasks.ids[:100]

        values.update({
            'date': date_begin,
            'date_end': date_end,
            'projects': projects,
            'tasks': tasks,
            'page_name': 'task',
            'archive_groups': archive_groups,
            'default_url': '/my/tasks',
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'searchbar_inputs': searchbar_inputs,
            'search_in': search_in,
            'sortby': sortby,
            'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
            'filterby': filterby,
        })
        return request.render("project.portal_my_tasks", values)

    @http.route(['/my/task/<int:task_id>'], type='http', auth="user", website=True)
    def portal_my_task(self, task_id=None, **kw):
        task = request.env['project.task'].browse(task_id)
        vals = {
            'task': task,
            'user': request.env.user
        }
        history = request.session.get('my_tasks_history', [])
        vals.update(get_records_pager(history, task))
        return request.render("project.portal_my_task", vals)
