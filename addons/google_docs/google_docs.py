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
from datetime import datetime

from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp import SUPERUSER_ID
from openerp.osv import fields, osv
from openerp.tools.translate import _
from urlparse import urlparse

_logger = logging.getLogger(__name__)

try:
    import gdata.docs.data
    import gdata.docs.client

    # API breakage madness in the gdata API - those guys are insane. 
    try:
        # gdata 2.0.15+
        gdata.docs.client.DocsClient.copy_resource
    except AttributeError:
        # gdata 2.0.14- : copy_resource() was copy()
        gdata.docs.client.DocsClient.copy_resource = gdata.docs.client.DocsClient.copy

    try:
        # gdata 2.0.16+
        gdata.docs.client.DocsClient.get_resource_by_id
    except AttributeError:
        try:
            # gdata 2.0.15+
            gdata.docs.client.DocsClient.get_resource_by_self_link
            def get_resource_by_id_2_0_16(self, resource_id, **kwargs):
                return self.GetResourceBySelfLink(
                    gdata.docs.client.RESOURCE_FEED_URI + ('/%s' % resource_id), **kwargs)
            gdata.docs.client.DocsClient.get_resource_by_id = get_resource_by_id_2_0_16
        except AttributeError:
            # gdata 2.0.14- : alias get_resource_by_id()
            gdata.docs.client.DocsClient.get_resource_by_id = gdata.docs.client.DocsClient.get_doc

    try:
        import atom.http_interface
        _logger.info('GData lib version `%s` detected' % atom.http_interface.USER_AGENT)
    except (ImportError, AttributeError):
        _logger.debug('GData lib version could not be detected', exc_info=True)

except ImportError:
    _logger.warning("Please install latest gdata-python-client from http://code.google.com/p/gdata-python-client/downloads/list")


class google_docs_ir_attachment(osv.osv):
    _inherit = 'ir.attachment'

    def _auth(self, cr, uid, context=None):
        '''
        Connexion with google base account
        @return client object for connexion
        '''
        #pool the google.login in google_base_account
        google_pool = self.pool.get('google.login')
        #get gmail password and login. We use default_get() instead of a create() followed by a read() on the 
        # google.login object, because it is easier. The keys 'user' and 'password' ahve to be passed in the dict
        # but the values will be replaced by the user gmail password and login.
        user_config = google_pool.default_get(cr, uid, {'user' : '' , 'password' : ''}, context=context)
        #login gmail account
        client = google_pool.google_login(user_config['user'], user_config['password'], type='docs_client', context=context)
        if not client:
            raise osv.except_osv(_('Google Docs Error!'), _("Check your google configuration in Users/Users/Synchronization tab."))
        _logger.info('Logged into google docs as %s', user_config['user'])
        return client

#    def create_empty_google_doc(self, cr, uid, res_model, res_id, context=None):
#        '''Create a new google document, empty and with a default type (txt)
#           :param res_model: the object for which the google doc is created
#           :param res_id: the Id of the object for which the google doc is created
#           :return: the ID of the google document object created
#        '''
#        #login with the base account google module
#        client = self._auth(cr, uid, context=context)
#        # create the document in google docs
#        title = "%s %s" % (context.get("name","Untitled Document."), datetime.today().strftime(DEFAULT_SERVER_DATETIME_FORMAT))
#        local_resource = gdata.docs.data.Resource(gdata.docs.data.SPREADSHEET_LABEL,title=title)
#        #create a new doc in Google Docs 
#        gdocs_resource = client.post(entry=local_resource, uri='https://docs.google.com/feeds/default/private/full/')
#        # create an ir.attachment into the db
#        self.create(cr, uid, {
#            'res_model': res_model,
#            'res_id': res_id,
#            'type': 'url',
#            'name': title,
#            'url': gdocs_resource.get_alternate_link().href,
#        }, context=context)
#        return {'resource_id': gdocs_resource.resource_id.text,
#                'title': title,
#                'url': gdocs_resource.get_alternate_link().href}

    def copy_gdoc(self, cr, uid, res_model, res_id, name_gdocs, gdoc_template_id, context=None):
        '''
        copy an existing document in google docs
           :param res_model: the object for which the google doc is created
           :param res_id: the Id of the object for which the google doc is created
           :param name_gdocs: the name of the future ir.attachment that will be created. Based on the google doc template foun.
           :param gdoc_template_id: the id of the google doc document to copy
           :return: the ID of the google document object created
        '''
        #login with the base account google module
        client = self._auth(cr, uid)
        # fetch and copy the original document
        try:
            doc = client.get_resource_by_id(gdoc_template_id)
            #copy the document you choose in the configuration
            copy_resource = client.copy_resource(doc, name_gdocs)
        except:
            raise osv.except_osv(_('Google Drive Error!'), _("Your resource id is not correct. You can find the id in the google docs URL."))
        # create an ir.attachment
        self.create(cr, uid, {
            'res_model': res_model,
            'res_id': res_id,
            'type': 'url',
            'name': name_gdocs,
            'url': copy_resource.get_alternate_link().href
        }, context=context)
        return copy_resource.resource_id.text

    def google_doc_get(self, cr, uid, res_model, ids, context=None):
        '''
        Function called by the js, when no google doc are yet associated with a record, with the aim to create one. It
        will first seek for a google.docs.config associated with the model `res_model` to find out what's the template
        of google doc to copy (this is usefull if you want to start with a non-empty document, a type or a name 
        different than the default values). If no config is associated with the `res_model`, then a blank text document
        with a default name is created.
          :param res_model: the object for which the google doc is created
          :param ids: the list of ids of the objects for which the google doc is created. This list is supposed to have
            a length of 1 element only (batch processing is not supported in the code, though nothing really prevent it)
          :return: the google document object created
        '''
        if len(ids) != 1:
            raise osv.except_osv(_('Google Drive Error!'), _("Creating google drive may only be done by one at a time."))
        res_id = ids[0]
        pool_gdoc_config = self.pool.get('google.docs.config')

        config_ids = pool_gdoc_config.search(cr, uid, [('model_id', '=', res_model)], context=context)
        config = []
        for config_id in config_ids:
            action = pool_gdoc_config.browse(cr, uid, config_id, context=context)
            if action.filter_id:
                google_doc_configs = self._filt(cr, uid, action, action.filter_id, res_id, context=context)
                if google_doc_configs: 
                    config.append(action.name)
            else:
                config.append(action.name)
        return config
    
    def _filt(self, cr, uid, action, action_filter, record_ids, context=None):
        """ filter the list record_ids that satisfy the action filter """
        records = {}
        if record_ids and action_filter:
            assert action.model_id.model == action_filter.model_id, "Filter model different from action rule model"
            model = self.pool.get(action_filter.model_id)
            domain = [('id', 'in', [record_ids])] + eval(action_filter.domain)
            ctx = dict(context or {})
            ctx.update(eval(action_filter.context))
            record_ids = model.search(cr, uid, domain, context=ctx)
        return record_ids
    
    def get_attachment(self, cr, uid, res_model, rec_name, ids, context=None):
        res_id = ids[0]
        pool_gdoc_config = self.pool.get('google.docs.config')
        config_ids = pool_gdoc_config.search(cr, uid, [('model_id', '=', res_model)], context=context)[0]
        action = pool_gdoc_config.browse(cr, uid, config_ids, context=context)
        attachment = {}
        model_fields_dic = self.pool.get(res_model).read(cr, uid, res_id, [], context=context)
        # check if a model is configured with a template
        if config_ids:
            name_gdocs = action.name_template
            try:
                name_gdocs = name_gdocs % model_fields_dic
                if name_gdocs.find('model')!=-1:
                    name_gdocs = name_gdocs.replace('model',action.model_id.name)
                if name_gdocs.find('filter')!=-1:
                    if action.filter_id:
                        name_gdocs = name_gdocs.replace('filter',action.filter_id.name)
                    else:
                        name_gdocs = name_gdocs.replace('_filter',"")
            except:
                raise osv.except_osv(_('Key Error!'), _("Your Google Doc Name Pattern's key does not found in object."))
        
        attach_ids = self.search(cr, uid, [('res_model','=',res_model),('name','=',name_gdocs),('res_id','=',res_id)])
        if not attach_ids: 
            google_template_id = action.gdocs_resource_id
            self.copy_gdoc(cr, uid, action.model_id.model, res_id, name_gdocs, google_template_id, context=context)
            attach_ids = self.search(cr, uid, [('res_model','=',res_model),('name','=',name_gdocs),('res_id','=',res_id)])
        attachments =  self.browse(cr, uid, attach_ids, context)[0]
        attachment['url'] = attachments.url
        return attachment

class config(osv.osv):
    _name = 'google.docs.config'
    _description = "Google Drive templates config"
    
    def _resource_get(self, cr, uid, ids, name, arg, context=None):
        result = {}
        for data in self.browse(cr, uid, ids, context):
            template_url = data.gdocs_template_url
            url = urlparse(template_url)
            res = url.path.split('/')
            resource = res[1]
            if res[1]== "spreadsheet":
                key = url.query.split('=')[1]
            else:
                key = res[3]
            res_id = resource + ":" + key
            result[data.id] = str(res_id)
        return result

    _columns = {
        'name' : fields.char('Name', required=True, size=1024),
        'model_id': fields.many2one('ir.model', 'Model', required=True),
        'filter_id' : fields.many2one('ir.filters', 'Filter'),
        'gdocs_template_url': fields.char('Template Url', required=True, size=1024),
        'gdocs_resource_id' : fields.function(_resource_get,type="char" ,string='Resource Id',store=True),
        'name_template': fields.char('Google Drive Name Pattern', size=64, help='Choose how the new google drive will be named, on google side. Eg. gdoc_%(field_name)s', required=True),
    }

    def onchange_model_id(self, cr, uid, ids, model_id):
         res = {'domain':{'filter_id':[]}}
         if model_id:
             model_name = self.pool.get('ir.model').read(cr, uid, model_id, ['model'])
             if model_name:
                 mod_name = model_name['model']
                 res['domain'] = {'filter_id': [('model_id', '=', mod_name)]}
         else:
             res['value'] = {'filter_id': False}
         return res

    _defaults = {
        'name_template': '%(name)s_model_filter_gdoc',
    }

config()
