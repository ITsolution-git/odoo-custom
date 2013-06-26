##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2012 OpenERP SA (<http://www.openerp.com>).
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
import logging

from openerp import SUPERUSER_ID
from openerp.osv import fields, osv
from openerp.tools.translate import _
from urlparse import urlparse

from httplib2 import Http
import urllib
import json

_logger = logging.getLogger(__name__)


class config(osv.osv):
    _name = 'google.drive.config'
    _description = "Google Drive templates config"

    def get_google_doc_name(self, cr, uid, ids, res_id, tamplate_id, context=None):
        pool_model = self.pool.get("ir.model")
        res = {}
        for config in self.browse(cr, SUPERUSER_ID, ids, context=context):
            res_model = config.model_id
            model_ids = pool_model.search(cr, uid, [('model', '=', res_model)])
            if not model_ids:
                continue
            model = pool_model.browse(cr, uid, model_ids[0], context=context)
            model_name = model.name
            filter_name = config.filter_id and config.filter_id.name or False
            record = self.pool.get(res_model).read(cr, uid, res_id, [], context=context)
            record.update({'model': model_name, 'filter': filter_name})
            name_gdocs = config.name_template or "%(name)s_%(model)s_%(filter)s_gdrive"
            try:
                name_gdocs = name_gdocs % record
            except:
                raise osv.except_osv(_('Key Error!'), _("Your Google Doc Name Pattern's key does not found in object."))

            attach_pool = self.pool.get("ir.attachment")
            attach_ids = attach_pool.search(cr, uid, [('res_model', '=', res_model), ('name', '=', name_gdocs), ('res_id', '=', res_id)])
            url = False
            if attach_ids:
                attachment = attach_pool.browse(cr, uid, attach_ids[0], context)
                url = attachment.url
            else:
                url = self.copy_doc(cr, uid, ids, res_id, tamplate_id, name_gdocs, res_model, context)
            res[config.id] = {'url': url}
        return res

    def copy_doc(self, cr, uid, ids, res_id, tamplate_id, name_gdocs, res_model, context=None):
        ir_config = self.pool['ir.config_parameter']
        google_drive_client_id = ir_config.get_param(cr, SUPERUSER_ID, 'google_drive_client_id')
        google_drive_client_secret = ir_config.get_param(cr, SUPERUSER_ID, 'google_drive_client_secret')
        google_drive_refresh_token = ir_config.get_param(cr, SUPERUSER_ID, 'google_drive_refresh_token')
        google_web_base_url = ir_config.get_param(cr, SUPERUSER_ID, 'web.base.url')

        #For Getting New Access Token With help of old Refresh Token
        headers = {"Content-type": "application/x-www-form-urlencoded"}
        data = dict(client_id=google_drive_client_id,
                    refresh_token=google_drive_refresh_token,
                    client_secret=google_drive_client_secret,
                    grant_type="refresh_token")
        data = urllib.urlencode(data)
        resp, content = Http().request("https://accounts.google.com/o/oauth2/token", "POST", data, headers)
        content = json.loads(content)

        # Copy template in to drive with help of new access token
        if 'access_token' in content:
            request_url = "https://www.googleapis.com/drive/v2/files/%s?fields=parents/id&access_token=%s" % (tamplate_id, content['access_token'])
            resp, parents = Http().request(request_url, "GET")
            parents_dict = json.loads(parents)

            headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
            record_url = "Click on link to open Record in OpenERP\n %s/?db=%s#id=%s&model=%s" % (google_web_base_url, cr.dbname, res_id, res_model)
            data = {"title": name_gdocs, "description": record_url, "parents": parents_dict['parents']}
            request_url = "https://www.googleapis.com/drive/v2/files/%s/copy?access_token=%s" % (tamplate_id, content['access_token'])
            resp, content = Http().request(request_url, "POST", json.dumps(data), headers)
            content = json.loads(content)
            res = False
            if 'alternateLink' in content.keys():
                attach_pool = self.pool.get("ir.attachment")
                attach_vals = {'res_model': res_model, 'name': name_gdocs, 'res_id': res_id, 'type': 'url', 'url': content['alternateLink']}
                attach_pool.create(cr, uid, attach_vals)
                res = content['alternateLink']
        else:
            raise self.pool.get('res.config.settings').get_config_warning(cr, _("You haven't configured 'Authorization Code' generated from google, Please generate and configure it in %(menu:base_setup.menu_general_configuration)s."), context=context)
        return res

    def get_google_drive_config(self, cr, uid, res_model, res_id, context=None):
        '''
        Function called by the js, when no google doc are yet associated with a record, with the aim to create one. It
        will first seek for a google.docs.config associated with the model `res_model` to find out what's the template
        of google doc to copy (this is usefull if you want to start with a non-empty document, a type or a name
        different than the default values). If no config is associated with the `res_model`, then a blank text document
        with a default name is created.
          :param res_model: the object for which the google doc is created
          :param ids: the list of ids of the objects for which the google doc is created. This list is supposed to have
            a length of 1 element only (batch processing is not supported in the code, though nothing really prevent it)
          :return: the config id and config name
        '''
        if not res_id:
            raise osv.except_osv(_('Google Drive Error!'), _("Creating google drive may only be done by one at a time."))
        # check if a model is configured with a template
        config_ids = self.search(cr, uid, [('model_id', '=', res_model)], context=context)
        configs = []
        for config in self.browse(cr, SUPERUSER_ID, config_ids, context=context):
            if config.filter_id:
                if (config.filter_id.user_id and config.filter_id.user_id.id != uid):
                    #Private
                    continue
                google_doc_configs = self._filter(cr, uid, config, config.filter_id, res_id, context=context)
                if google_doc_configs:
                    configs.append({'id': config.id, 'name': config.name})
            else:
                configs.append({'id': config.id, 'name': config.name})
        return configs

    def _filter(self, cr, uid, action, action_filter, record_ids, context=None):
        """ filter the list record_ids that satisfy the action filter """
        if record_ids and action_filter:
            if not action.model_id == action_filter.model_id:
                raise osv.except_osv(_('Warning!'), _("Something went wrong with the configuration of attachments with google drive.Please contact your Administrator to fix the problem."))
            model = self.pool.get(action_filter.model_id)
            domain = [('id', 'in', [record_ids])] + eval(action_filter.domain)
            ctx = dict(context or {})
            ctx.update(eval(action_filter.context))
            record_ids = model.search(cr, uid, domain, context=ctx)
        return record_ids

    def _list_all_models(self, cr, uid, context=None):
        cr.execute("SELECT model, name from ir_model order by name")
        return cr.fetchall()

    def _resource_get(self, cr, uid, ids, name, arg, context=None):
        result = {}
        for data in self.browse(cr, uid, ids, context):
            template_url = data.google_drive_template_url
            try:
                url = urlparse(template_url)
                res = url.path.split('/')
                if res[1] == "spreadsheet":
                    key = url.query.split('=')[1]
                else:
                    key = res[3]
                result[data.id] = str(key)
            except:
                raise osv.except_osv(_('Incorrect URL!'), _("Please enter a valid URL."))
        return result

    def _client_id_get(self, cr, uid, ids, name, arg, context=None):
        result = {}
        for config_id in ids:
            config = self.pool['ir.config_parameter']
            result[config_id] = config.get_param(cr, SUPERUSER_ID, 'google_drive_client_id')
        return result

    _columns = {
        'name': fields.char('Template Name', required=True, size=1024),
        'model_id': fields.selection(_list_all_models, 'Model', required=True),
        'filter_id': fields.many2one('ir.filters', 'Filter'),
        'google_drive_template_url': fields.char('Template URL', required=True, size=1024),
        'google_drive_resource_id': fields.function(_resource_get, type="char", string='Resource Id'),
        'google_drive_client_id': fields.function(_client_id_get, type="char", string='Google Client '),
        'name_template': fields.char('Google Drive Name Pattern', size=64, help='Choose how the new google drive will be named, on google side. Eg. gdoc_%(field_name)s', required=True),
    }

    def onchange_model_id(self, cr, uid, ids, model_id, context=None):
        res = {'domain': {'filter_id': []}}
        if model_id:
            res['domain'] = {'filter_id': [('model_id', '=', model_id)]}
        else:
            res['value'] = {'filter_id': False}
        return res

    _defaults = {
        'name_template': '%(name)s_%(model)s_%(filter)s_gdrive',
    }

    def _check_model_id(self, cr, uid, ids, context=None):
        config_id = self.browse(cr, uid, ids[0], context=context)
        if config_id.filter_id.id and config_id.model_id != config_id.filter_id.model_id:
            return False
        return True

    _constraints = [
        (_check_model_id, 'Model of selected filter is not matching with model of current template.', ['model_id', 'filter_id']),
    ]

config()


class base_config_settings(osv.osv):
    _inherit = "base.config.settings"

    _columns = {
        'google_drive_authorization_code': fields.char('Authorization Code', size=124),
        'google_drive_uri': fields.char('URI', readonly=True, help="The URL to generate the authorization code from Google"),
    }
    _defaults = {
        'google_drive_uri': lambda s, cr, uid, c: s._get_google_token_uri(cr, uid, 'drive', context=c),
    }
