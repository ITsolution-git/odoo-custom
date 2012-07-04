# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2010-today OpenERP SA (<http://www.openerp.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################

import datetime as DT
import io
import openerp
import openerp.tools as tools
from operator import itemgetter
from osv import osv
from osv import fields
from PIL import Image
import StringIO
import tools
from tools.translate import _
from lxml import etree

class mail_group(osv.osv):
    """
    A mail_group is a collection of users sharing messages in a discussion
    group. Group users are users that follow the mail group, using the
    subscription/follow mechanism of OpenSocial. A mail group has nothing
    in common wih res.users.group.
    Additional information on fields:
        - ``member_ids``: user member of the groups are calculated with
          ``message_get_subscribers`` method from mail.thread
        - ``member_count``: calculated with member_ids
        - ``is_subscriber``: calculated with member_ids
        
    """
    
    _description = 'Discussion group'
    _name = 'mail.group'
    _inherit = ['mail.thread']
    _inherits = {'mail.alias': 'alias_id'}
    def action_group_join(self, cr, uid, ids, context={}):
        return self.message_subscribe(cr, uid, ids, context=context);
    
    def action_group_leave(self, cr, uid, ids, context={}):
        return self.message_unsubscribe(cr, uid, ids, context=context);

    def onchange_photo(self, cr, uid, ids, value, context=None):
        if not value:
            return {'value': {'avatar_big': value, 'avatar': value} }
        return {'value': {'photo_big': value, 'photo': self._photo_resize(cr, uid, value) } }
    
    def _set_photo(self, cr, uid, id, name, value, args, context=None):
        if value:
            return self.write(cr, uid, [id], {'photo_big': value}, context=context)
        else:
            return self.write(cr, uid, [id], {'photo_big': value}, context=context)
    
    def _photo_resize(self, cr, uid, photo, width=128, height=128, context=None):
        image_stream = io.BytesIO(photo.decode('base64'))
        img = Image.open(image_stream)
        img.thumbnail((width, height), Image.ANTIALIAS)
        img_stream = StringIO.StringIO()
        img.save(img_stream, "JPEG")
        return img_stream.getvalue().encode('base64')
        
    def _get_photo(self, cr, uid, ids, name, args, context=None):
        result = dict.fromkeys(ids, False)
        for group in self.browse(cr, uid, ids, context=context):
            if group.photo_big:
                result[group.id] = self._photo_resize(cr, uid, group.photo_big, context=context)
        return result
    
    def get_member_ids(self, cr, uid, ids, field_names, args, context=None):
        if context is None:
            context = {}
        result = dict.fromkeys(ids)
        for id in ids:
            result[id] = {}
            result[id]['member_ids'] = self.message_get_subscribers_ids(cr, uid, [id], context=context)
            result[id]['member_count'] = len(result[id]['member_ids'])
            result[id]['is_subscriber'] = uid in result[id]['member_ids']
        return result
    
    def search_member_ids(self, cr, uid, obj, name, args, context=None):
        if context is None:
            context = {}
        sub_obj = self.pool.get('mail.subscription')
        sub_ids = sub_obj.search(cr, uid, ['&', ('res_model', '=', obj._name), ('user_id', '=', args[0][2])], context=context)
        subs = sub_obj.read(cr, uid, sub_ids, context=context)
        return [('id', 'in', map(itemgetter('res_id'), subs))]
    
    def get_last_month_msg_nbr(self, cr, uid, ids, name, args, context=None):
        result = {}
        message_obj = self.pool.get('mail.message')
        for id in ids:
            lower_date = (DT.datetime.now() - DT.timedelta(days=30)).strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
            result[id] = message_obj.search(cr, uid, ['&', '&', ('model', '=', self._name), ('res_id', 'in', ids), ('date', '>=', lower_date)], count=True, context=context)
        return result
    
    def _get_default_photo(self, cr, uid, context=None):
        avatar_path = openerp.modules.get_module_resource('mail', 'static/src/img', 'groupdefault.png')
        return self._photo_resize(cr, uid, open(avatar_path, 'rb').read().encode('base64'), context=context)
    
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'description': fields.text('Description'),
        'responsible_id': fields.many2one('res.users', string='Responsible',
                            ondelete='set null', required=True, select=1,
                            help="Responsible of the group that has all rights on the record."),
        'public': fields.boolean('Public', help='This group is visible by non members. Invisible groups can add members through the invite button.'),
        'photo_big': fields.binary('Full-size photo', help='Field holding the full-sized PIL-supported and base64 encoded version of the group image. The photo field is used as an interface for this field.'),
        'photo': fields.function(_get_photo, fnct_inv=_set_photo, string='Photo', type="binary",
            store = {
                'mail.group': (lambda self, cr, uid, ids, c={}: ids, ['photo_big'], 10),
            }, help='Field holding the automatically resized (128x128) PIL-supported and base64 encoded version of the group image.'),
        'member_ids': fields.function(get_member_ids, fnct_search=search_member_ids, type='many2many',
                        relation='res.users', string='Group members', multi='get_member_ids'),
        'member_count': fields.function(get_member_ids, type='integer', string='Member count', multi='get_member_ids'),
        'is_subscriber': fields.function(get_member_ids, type='boolean', string='Joined', multi='get_member_ids'),
        'last_month_msg_nbr': fields.function(get_last_month_msg_nbr, type='integer', string='Messages count for last month'),
        'alias_id': fields.many2one('mail.alias', 'Mail Alias', ondelete="cascade", required=True)
    }

    _defaults = {
        'public': True,
        'responsible_id': (lambda s, cr, uid, ctx: uid),
        'photo': _get_default_photo,
    }
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        res = super(mail_group,self).fields_view_get(cr, uid, view_id, view_type, context, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            domain = self.pool.get("ir.config_parameter").get_param(cr, uid, "mail.catchall.domain", context=context)
            if not domain:
                doc = etree.XML(res['arch'])
                alias_node = doc.xpath("//field[@name='alias_id']")[0]
                parent = alias_node.getparent()
                parent.remove(alias_node)
                res['arch'] = etree.tostring(doc)
        return res
    
    def create(self, cr, uid, vals, context=None):
        alias_pool = self.pool.get('mail.alias')
        if not vals.get('alias_id'):
            alias_id = alias_pool.create_unique_alias(cr, uid, {'alias_name': "mail_group."+vals['name'], 'alias_model_id': self._name}, context=context)
            vals.update({'alias_id': alias_id})
        res = super(mail_group, self).create(cr, uid, vals, context)
        alias_pool.write(cr, uid, [vals['alias_id']], {"alias_force_thread_id": res}, context)
        return res

