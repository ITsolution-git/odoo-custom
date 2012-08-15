import logging

import urllib
import urllib2
import simplejson

import openerp

from openerp.osv import osv, fields

_logger = logging.getLogger(__name__)

class res_users(osv.Model):
    _inherit = 'res.users'

    _columns = {
        'oauth_provider': fields.many2one('auth.oauth.provider','OAuth Provider'),
        'oauth_uid': fields.char('OAuth User ID', help="Oauth Provider user_id"),
        'oauth_access_token': fields.char('OAuth Token', readonly=True),
    }

    def auth_oauth_rpc(self, cr, uid, endpoint, access_token, context=None):
        params = urllib.urlencode({'access_token':access_token})
        url = endpoint + '?' + params
        f = urllib2.urlopen(url)
        response = f.read()
        return simplejson.loads(response)

    def auth_oauth_fetch_user_validation(self, cr, uid, access_token, context=None):
        endpoint = 'https://www.googleapis.com/oauth2/v1/tokeninfo'
        return self.auth_oauth_rpc(cr, uid, endpoint, access_token)

    def auth_oauth_fetch_user_data(self, cr, uid, access_token, context=None):
        endpoint = 'https://www.googleapis.com/oauth2/v1/userinfo'
        return self.auth_oauth_rpc(cr, uid, endpoint, access_token)

    def auth_oauth(self, cr, uid, config, params, context=None):
        # Advice by Google (to avoid Confused Deputy Problem)
        # if validation.audience != OUR_CLIENT_ID:
        #   abort()
        # else:
        #   continue with the process
        access_token = params.get('access_token')
        validation = self.auth_oauth_fetch_user_validation(cr, uid, access_token, context=context)
        if validation.get("error"):
            raise openerp.exceptions.AccessDenied

        login = validation['email']
        oauth_uid = validation['user_id']
        name = self.auth_oauth_fetch_user_data(cr, uid, access_token)['name']
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
                'oauth_provider': 'Google',
                'oauth_uid': oauth_uid,
                'oauth_access_token': access_token,
                'active': True,
            }
            self.auth_signup_create(cr, uid, new_user)
        return credentials

    def check(self, db, uid, passwd):
        try:
            return super(res_users, self).check(db, uid, passwd)
        except openerp.exceptions.AccesDenied:
            if not passwd:
                raise
            try:
                registry = openerp.modules.registry.RegistryManager.get(db)
                cr = registry.db.cursor()
                cr.execute('''SELECT COUNT(1)
                                FROM res_users
                               WHERE id=%s
                                 AND oauth_access_token=%s
                                 AND active=%s''',
                            (int(uid), passwd, True))
                if not cr.fetchone()[0]:
                    raise
                self._uid_cache.setdefault(db, {})[uid] = passwd
            finally:
                cr.close()

#
