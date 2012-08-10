# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from osv import fields, osv

class document_page_create_menu(osv.osv_memory):
    """ Create Menu """
    _name = "document.page.create.menu"
    _description = "Wizard Create Menu"

    _columns = {
        'menu_parent_id': fields.many2one('ir.ui.menu', 'Parent Menu', required=True),
    }

    def document_page_menu_create(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        obj_page = self.pool.get('document.page')
        obj_view = self.pool.get('ir.ui.view')
        obj_menu = self.pool.get('ir.ui.menu')
        obj_action = self.pool.get('ir.actions.act_window')
        page_id = context.get('active_id', False)
        if not page_id:
            return {}

        datas = self.browse(cr, uid, ids, context=context)
        data = False
        if datas:
            data = datas[0]
        if not data:
            return {}
        value = {
            'name': 'Document Page',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'document.page',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'inline',
            'nodestroy': True,
        }
        page = obj_page.browse(cr, uid, page_id, context=context)
        value['domain'] = "[('parent_id','=',%d)]" % (page.id)
        value['res_id'] = page.id

        action_id = obj_action.create(cr, uid, value)
        menu_id = obj_menu.create(cr, uid, {
                        'name': page.name,
                        'parent_id':data.menu_parent_id.id,
                        'icon': 'STOCK_DIALOG_QUESTION',
                        'action': 'ir.actions.act_window,'+ str(action_id),
                        }, context)
        obj_page.write(cr, uid, [page_id], {'menu_id':menu_id})
        return {'type': 'ir.actions.act_window_close'}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
