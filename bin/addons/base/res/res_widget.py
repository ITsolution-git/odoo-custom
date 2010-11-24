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
class res_widget(osv.osv):
    _name = "res.widget"
    _rec_name = "title"
    _columns = {
        'title' : fields.char('Title', size=64, required=True, translate=True),
        'content': fields.text('Content', required=True),
    }
res_widget()

class res_widget_user(osv.osv):
    _name="res.widget.user"
    _order = "sequence"
    _columns = {
        'sequence': fields.integer('Sequence'),
        'user_id': fields.many2one('res.users','User', select=1),
        'widget_id': fields.many2one('res.widget','Widget',required=True),
    }
res_widget_user()

class res_widget_wizard(osv.osv_memory):
    _name = "res.widget.wizard"
    _description = "Add a widget for User"
    _columns = {
        'widget_id': fields.many2one("res.widget", 'Widget', required=1),
    }
    
    def add_res_widget(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wizard = self.read(cr, uid, ids)[0]
        self.pool.get('res.widget.user').create(cr, uid, {'user_id':uid, 'widget_id':wizard['widget_id']})
        return {'type': 'ir.actions.act_window_close'}
res_widget_wizard()

