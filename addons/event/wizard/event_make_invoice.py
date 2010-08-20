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

class event_make_invoice(osv.osv_memory):
    """
    Make Invoices
    """
    _name = "event.make.invoice"
    _description = "Event Make Invoice"
    _columns = {

        'grouped': fields.boolean('Group the invoices'),
        'invoice_date':fields.date('Invoice Date'),
         }

    def view_init(self, cr, uid, fields, context=None):
        """
        This function checks for precondition before wizard executes
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param fields: List of fields for default value
        @param context: A standard dictionary for contextual values
        """
        obj_event_reg = self.pool.get('event.registration')
        data = context and context.get('active_ids', [])

        for event_reg in obj_event_reg.browse(cr, uid, data, context=context):
            if event_reg.state == 'draft':
                     raise osv.except_osv(_('Warning !'),
                        _("Invoice cannot be created if the registration is in draft state."))
            if event_reg.state == 'done':
                     raise osv.except_osv(_('Warning !'),
                        _("Invoice cannot be created if the registration is in done state."))

            if (not event_reg.tobe_invoiced):
                    raise osv.except_osv(_('Warning !'),
                        _("Registration is set as Cannot be invoiced"))

            if not event_reg.event_id.product_id:
                    raise osv.except_osv(_('Warning !'),
                        _("Event related doesn't have any product defined"))
            if not event_reg.partner_invoice_id:
                   raise osv.except_osv(_('Warning !'),
                        _("Registration doesn't have any partner to invoice."))

    def default_get(self, cr, uid, fields_list, context=None):
        res = super(event_make_invoice, self).default_get(cr, uid, fields_list, context)
        return res

    def make_invoice(self, cr, uid, ids, context={}):

        reg_obj = self.pool.get('event.registration')
        newinv = []

        for data in self.browse(cr, uid, ids):
            res = reg_obj.action_invoice_create(cr, uid, context.get(('active_ids'),[]), data.grouped, date_inv = data.invoice_date)

        mod_obj =self.pool.get('ir.model.data')
        result = mod_obj._get_id(cr, uid, 'account', 'view_account_invoice_filter')

        id = mod_obj.read(cr, uid, result, ['res_id'])

        return {
            'domain': "[('id','in',%s)]" % res,
            'name': 'Invoices',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.invoice',
            'view_id': False,
            'context': "{'type':'out_refund'}",
            'type': 'ir.actions.act_window',
            'search_view_id': id['id']
        }

event_make_invoice()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
