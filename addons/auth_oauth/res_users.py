import logging

import urllib
import urllib2
import simplejson

import openerp
from openerp.osv import osv, fields
from openerp import SUPERUSER_ID

_logger = logging.getLogger(__name__)

class res_users(osv.Model):
    _inherit = 'res.users'

    _columns = {
        'oauth_provider_id': fields.many2one('auth.oauth.provider','OAuth Provider'),
        'oauth_uid': fields.char('OAuth User ID', help="Oauth Provider user_id"),
        'oauth_access_token': fields.char('OAuth Token', readonly=True),
    }

    def auth_oauth_rpc(self, cr, uid, endpoint, access_token, context=None):
        params = urllib.urlencode({'access_token':access_token})
        url = endpoint + '?' + params
        f = urllib2.urlopen(url)
        response = f.read()
        return simplejson.loads(response)

    def auth_oauth(self, cr, uid, provider, params, context=None):
        # Advice by Google (to avoid Confused Deputy Problem)
        # if validation.audience != OUR_CLIENT_ID:
        #   abort()
        # else:
        #   continue with the process
        access_token = params.get('access_token')
        p = self.pool.get('auth.oauth.provider').browse(cr, uid, provider, context=context)

        validation = self.auth_oauth_rpc(cr, uid, p.validation_endpoint, access_token)
        if validation.get("error"):
            raise openerp.exceptions.AccessDenied
        login = validation['email']
        oauth_uid = validation['user_id']
        name = self.auth_oauth_rpc(cr, uid, p.data_endpoint, access_token)['name']

        credentials = (cr.dbname, login, access_token)
        res = self.search(cr, uid, [("oauth_uid", "=", oauth_uid)])
        if res:
            self.write(cr, uid, res[0], {'oauth_access_token':access_token})
        else:
            # New user
            new_user = {
                'name': name,
                'login': login,
                'user_email': login,
                'oauth_provider_id': 1,
                'oauth_uid': oauth_uid,
                'oauth_access_token': access_token,
                'active': True,
            }
            self.auth_signup_create(cr, uid, new_user)
        return credentials

    def check_credentials(self, cr, uid, password):
        try:
            return super(res_users, self).check_credentials(cr, uid, password)
        except openerp.exceptions.AccessDenied:
            res = self.search(cr, SUPERUSER_ID, [('id','=',uid),('oauth_access_token','=',password)])
            if not res:
                raise

#
