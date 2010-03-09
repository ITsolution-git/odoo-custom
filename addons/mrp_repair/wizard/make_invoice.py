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

import netsvc
from osv import osv, fields 

class make_invoice(osv.osv_memory):
    _name = 'mrp.repair.make_invoice'
    _description = 'Make Invoice'
    
    _columns = {
	       'group': fields.boolean('Group by partner invoice address'),
    }

    def make_invoices(self, cr, uid, ids, context):
        inv = self.browse(cr, uid, ids[0])
        order_obj = self.pool.get('mrp.repair')       
        newinv = order_obj.action_invoice_create(cr, uid, context['active_ids'], group=inv.group,context=context)    
            
        return {
            'domain': [('id','in', newinv.values())],
            'name': 'Invoices',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.invoice',
            'view_id': False,
            'context': "{'type':'out_invoice'}",
            'type': 'ir.actions.act_window'
        }

make_invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

