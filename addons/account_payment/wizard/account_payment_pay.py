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
import time
from osv import fields, osv

class account_payment_make_payment(osv.osv_memory):
    _name = 'account.payment.make.payment'
    _description = 'Account make payment'
    _columns = {
            }

    def launch_wizard(self, cr, uid, ids, context):
        """
        Search for a wizard to launch according to the type.
        If type is manual. just confirm the order.
        """
        obj_payment_order = self.pool.get('payment.order')
        obj_model = self.pool.get('ir.model.data')
        obj_act = self.pool.get('ir.actions.act_window')
        order= obj_payment_order.browse(cr,uid,context['active_id'],context)
        t= order.mode and order.mode.type.code or 'manual'
        if t == 'manual' :
            obj_payment_order.set_done(cr,uid,context['active_id'],context)
            return {}

        gw= obj_payment_order.get_wizard(t)
        if not gw:
            obj_payment_order.set_done(cr,uid,context['active_id'],context)
            return {}

        module, wizard= gw
        result = mod_obj._get_id(cr, uid, module, wizard)
        id = mod_obj.read(cr, uid, [result], ['res_id'])[0]['res_id']
        result = act_obj.read(cr, uid, [id])[0]
        #result['context'] = str({'fiscalyear': data['form']['fiscalyear']})
        return result


account_payment_make_payment()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

