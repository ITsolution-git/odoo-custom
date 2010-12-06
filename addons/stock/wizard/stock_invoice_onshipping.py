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

from tools.translate import _

class stock_invoice_onshipping(osv.osv_memory):

    def _get_journal_id(self, cr, uid, context=None):
        if context is None:
            context = {}

        model = context.get('active_model')
        if not model or model != 'stock.picking':
            return []

        model_pool = self.pool.get(model)
        acct_obj = self.pool.get('account.journal')
        res_ids = context and context.get('active_ids', [])
        vals=[]
        pick_types = list(set(map(lambda x: x.type, model_pool.browse(cr, uid, res_ids, context=context))))
        for type in pick_types:
            if type == 'out':
               value = acct_obj.search(cr, uid, [('type', 'in',('sale','sale_refund') )])
               for jr_type in acct_obj.browse(cr, uid, value, context=context):
                   t1 = jr_type.id,jr_type.name
                   vals.append(t1)

            elif type == 'in':
               value = acct_obj.search(cr, uid, [('type', 'in',('purchase','purchase_refund') )])
               for jr_type in acct_obj.browse(cr, uid, value, context=context):
                   t1 = jr_type.id,jr_type.name
                   vals.append(t1)
            else:
               value = acct_obj.search(cr, uid, [('type', 'in',('cash','bank','general','situation') )])
               for jr_type in acct_obj.browse(cr, uid, value, context=context):
                   t1 = jr_type.id,jr_type.name
                   vals.append(t1)
        return vals


    _name = "stock.invoice.onshipping"
    _description = "Stock Invoice Onshipping"


    _columns = {
        'journal_id': fields.selection(_get_journal_id, 'Destination Journal',required=True),
        'group': fields.boolean("Group by partner"),
        'invoice_date': fields.date('Invoiced date'),
    }


    def view_init(self, cr, uid, fields_list, context=None):
        if context is None:
            context = {}
        res = super(stock_invoice_onshipping, self).view_init(cr, uid, fields_list, context=context)
        pick_obj = self.pool.get('stock.picking')
        count = 0
        active_ids = context.get('active_ids',[])
        for pick in pick_obj.browse(cr, uid, active_ids, context=context):
            if pick.invoice_state != '2binvoiced':
                count += 1
        if len(active_ids) == 1 and count:
            raise osv.except_osv(_('Warning !'), _('This picking list does not require invoicing.'))
        if len(active_ids) == count:
            raise osv.except_osv(_('Warning !'), _('None of these picking lists require invoicing.'))
        return res



    def create_invoice(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        picking_pool = self.pool.get('stock.picking')
        data_pool = self.pool.get('ir.model.data')
        onshipdata_obj = self.read(cr, uid, ids[0], ['journal_id', 'group', 'invoice_date'])
        if context.get('new_picking', False):
            onshipdata_obj['id'] = onshipdata_obj.new_picking
            onshipdata_obj[ids] = onshipdata_obj.new_picking

        context['date_inv'] = onshipdata_obj['invoice_date']
        invoice_ids = []
        active_ids = context.get('active_ids', [])
        active_picking = picking_pool.browse(cr, uid, context.get('active_id',False), context=context)
        inv_type = picking_pool._get_invoice_type(active_picking)

        res = picking_pool.action_invoice_create(cr, uid, active_ids,
              journal_id = onshipdata_obj['journal_id'],
              group = onshipdata_obj['group'],
              type = None,
              context=context)
        invoice_ids += res.values()
        if not invoice_ids:
            raise osv.except_osv(_('Error'), _('No Invoices were created'))
        action_model = False
        action = {}
        if inv_type == "out_invoice":
            action_model,action_id = data_pool.get_object_reference(cr, uid, 'account', "action_invoice_tree1")
        elif inv_type == "in_invoice":
            action_model,action_id = data_pool.get_object_reference(cr, uid, 'account', "action_invoice_tree2")
        elif inv_type == "out_refund":
            action_model,action_id = data_pool.get_object_reference(cr, uid, 'account', "action_invoice_tree3")
        elif inv_type == "in_refund":
            action_model,action_id = data_pool.get_object_reference(cr, uid, 'account', "action_invoice_tree4")
        if action_model:
            action_pool = self.pool.get(action_model)
            action = action_pool.read(cr, uid, action_id, context=context)
            action['domain'] = "[('id','in', ["+','.join(map(str,invoice_ids))+"])]"
        return action

stock_invoice_onshipping()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
