# -*- coding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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

from osv import fields,osv
from osv.orm import except_orm
import tools
import pytz
from tools.translate import _

class groups(osv.osv):
    _name = "res.groups"
    _order = 'name'
    _columns = {
        'name': fields.char('Group Name', size=64, required=True),
        'model_access': fields.one2many('ir.model.access', 'group_id', 'Access Controls'),
        'rule_groups': fields.many2many('ir.rule.group', 'group_rule_group_rel',
            'group_id', 'rule_group_id', 'Rules', domain="[('global', '<>', True)]"),
        'menu_access': fields.many2many('ir.ui.menu', 'ir_ui_menu_group_rel', 'gid', 'menu_id', 'Access Menu'),
        'comment' : fields.text('Comment',size=250),
    }
    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The name of the group must be unique !')
    ]
    def copy(self, cr, uid, id, default=None, context={}):
        group_name = self.read(cr, uid, [id], ['name'])[0]['name']
        default.update({'name': group_name +' (copy)'})
        return super(groups, self).copy(cr, uid, id, default, context)

    def write(self, cr, uid, ids, vals, context=None):
        if 'name' in vals:
            if vals['name'].startswith('-'):
                raise osv.except_osv(_('Error'),
                        _('The name of the group can not start with "-"'))
        res = super(groups, self).write(cr, uid, ids, vals, context=context)
        # Restart the cache on the company_get method
        self.pool.get('ir.rule').domain_get.clear_cache(cr.dbname)
        self.pool.get('ir.model.access').call_cache_clearing_methods(cr)
        return res

    def create(self, cr, uid, vals, context=None):
        if 'name' in vals:
            if vals['name'].startswith('-'):
                raise osv.except_osv(_('Error'),
                        _('The name of the group can not start with "-"'))
        gid = super(groups, self).create(cr, uid, vals, context=context)        
        if context and context.get('noadmin', False):
            pass
        else:
            # assign this new group to user_root
            user_obj = self.pool.get('res.users')
            aid = user_obj.browse(cr, 1, user_obj._get_admin_id(cr))
            if aid:
                aid.write({'groups_id': [(4, gid)]})
        return gid

    def copy(self, cr, uid, id, default={}, context={}, done_list=[], local=False):
        group = self.browse(cr, uid, id, context=context)
        default = default.copy()
        if not 'name' in default:
            default['name'] = group['name']
        default['name'] = default['name'] + _(' (copy)')
        return super(groups, self).copy(cr, uid, id, default, context=context)

groups()


class roles(osv.osv):
    _name = "res.roles"
    _columns = {
        'name': fields.char('Role Name', size=64, required=True),
        'parent_id': fields.many2one('res.roles', 'Parent', select=True),
        'child_id': fields.one2many('res.roles', 'parent_id', 'Children'),
        'users': fields.many2many('res.users', 'res_roles_users_rel', 'rid', 'uid', 'Users'),
    }
    _defaults = {
    }
    def check(self, cr, uid, ids, role_id):
        if role_id in ids:
            return True
        cr.execute('select parent_id from res_roles where id=%s', (role_id,))
        roles = cr.fetchone()[0]
        if roles:
            return self.check(cr, uid, ids, roles)
        return False
roles()

def _lang_get(self, cr, uid, context={}):
    obj = self.pool.get('res.lang')
    ids = obj.search(cr, uid, [])
    res = obj.read(cr, uid, ids, ['code', 'name'], context)
    res = [(r['code'], r['name']) for r in res]
    return res
def _tz_get(self,cr,uid, context={}):
    return [(x, x) for x in pytz.all_timezones]

def _companies_get(self,cr, uid, context={}):
    res=[]
    ids = self.pool.get('res.users').browse(cr, uid, uid, context).company_ids
    res = [(i.id,i.name) for i in ids]
    return res

class users(osv.osv):
    __admin_ids = {}
    _name = "res.users"
    
    def get_current_company(self, cr, uid):
        res=[]
        cr.execute('select company_id, res_company.name from res_users left join res_company on res_company.id = company_id where res_users.id=%s' %uid)
        res = cr.fetchall()
        return res     
    
    _columns = {
        'name': fields.char('Name', size=64, required=True, select=True),
        'login': fields.char('Login', size=64, required=True),
        'password': fields.char('Password', size=64, invisible=True, help="Keep empty if you don't want the user to be able to connect on the system."),
        'email': fields.char('E-mail', size=64, help='If an email is provided'\
                             ', the user will be sent a message welcoming him'),
        'signature': fields.text('Signature', size=64),
        'address_id': fields.many2one('res.partner.address', 'Address'),
        'active': fields.boolean('Active'),
        'action_id': fields.many2one('ir.actions.actions', 'Home Action'),
        'menu_id': fields.many2one('ir.actions.actions', 'Menu Action'),
        'groups_id': fields.many2many('res.groups', 'res_groups_users_rel', 'uid', 'gid', 'Groups'),
        'roles_id': fields.many2many('res.roles', 'res_roles_users_rel', 'uid', 'rid', 'Roles'),
        'rules_id': fields.many2many('ir.rule.group', 'user_rule_group_rel', 'user_id', 'rule_group_id', 'Rules'),
        'company_id': fields.many2one('res.company', 'Company', help="The company this user is currently working on.", required=True),
        'company_ids':fields.many2many('res.company','res_company_users_rel','user_id','cid','Accepted Companies'),
        'context_lang': fields.selection(_lang_get, 'Language', required=True),
        'context_tz': fields.selection(_tz_get,  'Timezone', size=64),
        'company': fields.selection(_companies_get,  'Company', size=64),        
    }
    def read(self,cr, uid, ids, fields=None, context=None, load='_classic_read'):
        def override_password(o):
            if 'password' in o and ( 'id' not in o or o['id'] != uid ):
                o['password'] = '********'
            return o

        result = super(users, self).read(cr, uid, ids, fields, context, load)
        canwrite = self.pool.get('ir.model.access').check(cr, uid, 'res.users', 'write', raise_exception=False)
        if not canwrite:
            if isinstance(ids, (int, float)):
                result = override_password(result)
            else:
                result = map(override_password, result)
        return result

    _sql_constraints = [
        ('login_key', 'UNIQUE (login)',  _('You can not have two users with the same login !'))
    ]

    def _get_admin_id(self, cr):
        if self.__admin_ids.get(cr.dbname) is None:
            ir_model_data_obj = self.pool.get('ir.model.data')
            mdid = ir_model_data_obj._get_id(cr, 1, 'base', 'user_root')
            self.__admin_ids[cr.dbname] = ir_model_data_obj.read(cr, 1, [mdid], ['res_id'])[0]['res_id']
        return self.__admin_ids[cr.dbname]

    def _get_action(self,cr, uid, context={}):
        ids = self.pool.get('ir.ui.menu').search(cr, uid, [('usage','=','menu')])
        return ids and ids[0] or False

    def _get_company(self,cr, uid, context={}):
        return self.pool.get('res.users').browse(cr, uid, uid, context).company_id.id

    def _get_menu(self,cr, uid, context={}):
        ids = self.pool.get('ir.actions.act_window').search(cr, uid, [('usage','=','menu')])
        return ids and ids[0] or False

    def _get_group(self,cr, uid, context={}):
        ids = self.pool.get('res.groups').search(cr, uid, [('name','=','Employee')])
        return ids or False

    _defaults = {
        'password' : lambda *a : '',
        'context_lang': lambda *args: 'en_US',
        'active' : lambda *a: True,
        'menu_id': _get_menu,
        'action_id': _get_menu,
        'company_id': _get_company,
        'groups_id': _get_group,
    }
    def company_get(self, cr, uid, uid2):
        company_id = self.pool.get('res.users').browse(cr, uid, uid2).company_id.id
        return company_id
    company_get = tools.cache()(company_get)

    def write(self, cr, uid, ids, values, *args, **argv):
        if (ids == [uid]):
            ok = True
            for k in values.keys():
                if k not in ('password','signature','action_id', 'context_lang', 'context_tz'):
                    ok=False
            if ok:
                uid = 1
        res = super(users, self).write(cr, uid, ids, values, *args, **argv)
        self.company_get.clear_cache(cr.dbname)
        # Restart the cache on the company_get method
        self.pool.get('ir.rule').domain_get.clear_cache(cr.dbname)
        self.pool.get('ir.model.access').call_cache_clearing_methods(cr)
        return res

    def unlink(self, cr, uid, ids, context=None):
        if 1 in ids:
            raise osv.except_osv(_('Can not remove root user!'), _('You can not remove the admin user as it is used internally for resources created by OpenERP (updates, module installation, ...)'))
        return super(users, self).unlink(cr, uid, ids, context=context)

    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        if not args:
            args=[]
        if not context:
            context={}
        ids = []
        if name:
            ids = self.search(cr, user, [('login','=',name)]+ args, limit=limit)
        if not ids:
            ids = self.search(cr, user, [('name',operator,name)]+ args, limit=limit)
        return self.name_get(cr, user, ids)

    def copy(self, cr, uid, id, default=None, context={}):
        login = self.read(cr, uid, [id], ['login'])[0]['login']
        default.update({'login': login+' (copy)'})
        return super(users, self).copy(cr, uid, id, default, context)

    def context_get(self, cr, uid, context=None):
        user = self.browse(cr, uid, uid, context)
        result = {}
        for k in self._columns.keys():
            if k.startswith('context_'):
                result[k[8:]] = getattr(user,k)
        return result


    def _check_company(self, cursor, user, ids):
        for user in self.browse(cursor, user, ids):
            if user.company_ids and (user.company_id.id not in map(lambda x: x.id, user.company_ids)):
                return False
        return True

    _constraints = [
        (_check_company, 'This user can not connect using this company !', ['company_id']),
    ]
users()

class config_users(osv.osv_memory):
    _name = 'res.config.users'
    _inherit = 'res.config'

    _columns = users._columns
    _defaults = users._defaults

    def user_data(self, cr, uid, new_id, context=None):
        ''' Gets the purely user part of the current config_user
        instance, without the fields inherited from res.config
        '''
        return self.read(cr, uid, new_id,
                         users._columns.keys(),
                         context=context)
    def create_user(self, cr, uid, new_id, context=None):
        ''' create a new res.user instance from the data stored
        in the current res.config.users
        '''
        self.pool.get('res.users').create(
            cr, uid, self.user_data(cr, uid, new_id, context), context)
    
    def execute(self, cr, uid, ids, context=None):
        self.create_user(cr, uid, ids[0], context=context)
        return {
            'view_type': 'form',
            "view_mode": 'form',
            'res_model': 'res.config.users',
            'view_id':self.pool.get('ir.ui.view')\
                .search(cr,uid,[('name','=','res.config.users.confirm.form')]),
            'type': 'ir.actions.act_window',
            'target':'new',
            }
config_users()

class groups2(osv.osv): ##FIXME: Is there a reason to inherit this object ?
    _inherit = 'res.groups'
    _columns = {
        'users': fields.many2many('res.users', 'res_groups_users_rel', 'gid', 'uid', 'Users'),
    }
groups2()

class res_config_view(osv.osv_memory):
    _name = 'res.config.view'
    _inherit = 'res.config'
    _columns = {
        'name':fields.char('Name', size=64),
        'view': fields.selection([('simple','Simplified'),
                                  ('extended','Extended')],
                                 'Interface', required=True ),
    }
    _defaults={
        'view':lambda *args: 'simple',
    }

    def execute(self, cr, uid, ids, context=None):
        res=self.read(cr,uid,ids)[0]
        users_obj = self.pool.get('res.users')
        group_obj=self.pool.get('res.groups')
        if 'view' in res and res['view'] and res['view']=='extended':
            group_ids=group_obj.search(cr,uid,[('name','ilike','Extended')])
            if group_ids and len(group_ids):
                users_obj.write(cr, uid, [uid],{
                                'groups_id':[(4,group_ids[0])]
                            }, context=context)
res_config_view()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

