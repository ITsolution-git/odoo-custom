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

import wizard
import pooler
from tools.misc import UpdateableStr

import netsvc
import time

from tools.translate import _

arch=UpdateableStr()
fields={}

def make_default(val):
    def fct(obj, cr, uid):
        return val
    return fct

def _get_returns(self, cr, uid, data, context):
    pool = pooler.get_pool(cr.dbname)
    pick_obj = pool.get('stock.picking')
    pick = pick_obj.browse(cr, uid, [data['id']])[0]
    
    if pick.state != 'done':
        raise wizard.except_wizard(_('Warning !'), _("The Packing is not completed yet!\nYou cannot return packing which is not in 'Done' state!"))
    res = {}
    
    return_history = {}
    for m_line in pick.move_lines:
        return_history[m_line.id] = 0
        for rec in m_line.move_stock_return_history:
            return_history[m_line.id] += rec.product_qty

    fields.clear()
    arch_lst=['<?xml version="1.0"?>', '<form string="%s">' % _('Return lines'), '<label string="%s" colspan="4"/>' % _('Provide the quantities of the returned products.')]
    for m in [line for line in pick.move_lines]:
        quantity = m.product_qty
        if quantity > return_history[m.id] and (quantity - return_history[m.id])>0:
            arch_lst.append('<field name="return%s"/>\n<newline/>' % (m.id,))
            fields['return%s' % m.id]={'string':m.name, 'type':'float', 'required':True, 'default':make_default(quantity - return_history[m.id])}
            res.setdefault('returns', []).append(m.id)
    
    if not res.get('returns',False):
        raise  wizard.except_wizard(_('Warning!'),_('There is no product to return!'))
    
    arch_lst.append('<field name="invoice_state"/>\n<newline/>')
    if pick.invoice_state=='invoiced':
        new_invoice_state='2binvoiced'
    else:
        new_invoice_state=pick.invoice_state
    fields['invoice_state']={'string':_('Invoice state'), 'type':'selection', 'default':make_default(new_invoice_state), 'required':True, 'selection':[('2binvoiced', _('to be invoiced')), ('none', _('None'))]}
    arch_lst.append('</form>')
    arch.string='\n'.join(arch_lst)
    return res

def _create_returns(self, cr, uid, data, context):
    pool = pooler.get_pool(cr.dbname)
    move_obj = pool.get('stock.move')
    pick_obj = pool.get('stock.picking')
    uom_obj = pool.get('product.uom')

    pick=pick_obj.browse(cr, uid, [data['id']])[0]
    new_picking=None
    date_cur=time.strftime('%Y-%m-%d %H:%M:%S')

    set_invoice_state_to_none = True
    for move in move_obj.browse(cr, uid, data['form'].get('returns',[])):
        if not new_picking:
            if pick.type=='out':
                new_type='in'
            elif pick.type=='in':
                new_type='out'
            else:
                new_type='internal'
            new_picking=pick_obj.copy(cr, uid, pick.id, {'name':'%s (return)' % pick.name,
                    'move_lines':[], 'state':'draft', 'type':new_type,
                    'date':date_cur, 'invoice_state':data['form']['invoice_state'],})
        new_location=move.location_dest_id.id
        
        new_qty = data['form']['return%s' % move.id]
        returned_qty = move.product_qty
        
        for rec in move.move_stock_return_history:
            returned_qty -= rec.product_qty
        
        if returned_qty != new_qty:
            set_invoice_state_to_none = False
            
        new_move=move_obj.copy(cr, uid, move.id, {
            'product_qty': new_qty,
            'product_uos_qty': uom_obj._compute_qty(cr, uid, move.product_uom.id,
                new_qty, move.product_uos.id),
            'picking_id':new_picking, 'state':'draft',
            'location_id':new_location, 'location_dest_id':move.location_id.id,
            'date':date_cur, 'date_planned':date_cur,})
        move_obj.write(cr, uid, [move.id], {'move_stock_return_history':[(4,new_move)]})
    
    if set_invoice_state_to_none:
        pick_obj.write(cr, uid, [pick.id], {'invoice_state':'none'})
        
    if new_picking:
        wf_service = netsvc.LocalService("workflow")
        if new_picking:
            wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_confirm', cr)
        pick_obj.force_assign(cr, uid, [new_picking], context)
    return new_picking

def _action_open_window(self, cr, uid, data, context):
    res=_create_returns(self, cr, uid, data, context)
    if not res:
        return {}
    return {
        'domain': "[('id', 'in', ["+str(res)+"])]",
        'name': 'Picking List',
        'view_type':'form',
        'view_mode':'tree,form',
        'res_model':'stock.picking',
        'view_id':False,
        'type':'ir.actions.act_window',
    }

class wizard_return_picking(wizard.interface):
    states={
        'init':{
            'actions':[_get_returns],
            'result':{'type':'form', 'arch':arch, 'fields':fields, 'state':[('end','Cancel'),('return','Return')]}
        },
        'return':{
            'actions':[],
            'result':{'type':'action', 'action':_action_open_window, 'state':'end'}
        }
    }
wizard_return_picking('stock.return.picking')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

