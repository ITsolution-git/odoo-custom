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

from osv import osv,fields

class sale_order(osv.osv):
    _inherit = 'sale.order'

    _columns = {
        'section_id': fields.many2one('crm.case.section', 'Sales Team'),
        'categ_ids': fields.many2many('crm.case.categ', 'sale_order_category_rel', 'order_id', 'category_id', 'Categories', \
            domain="['|',('section_id','=',section_id),('section_id','=',False), ('object_id.model', '=', 'crm.lead')]")
    }

def create(self, cr, uid, vals, context=None):
        order =  super(sale_order, self).create(cr, uid, vals, context=context)
        record = self.browse(cr, uid, order, context=context)
        if record.section_id:
            followers = [follow.id for follow in record.section_id.message_follower_ids]
            self.message_subscribe(cr, uid, [record.id],followers, context=context)
        if order:
            self.create_send_note(cr, uid, [order], context=context)
        return order

sale_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
