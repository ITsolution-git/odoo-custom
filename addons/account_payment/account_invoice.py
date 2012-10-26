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

from datetime import datetime
from tools.translate import _
from osv import fields, osv

class Invoice(osv.osv):
    _inherit = 'account.invoice'

    # Forbid to cancel an invoice if the related move lines have already been
    # used in a payment order. The risk is that importing the payment line
    # in the bank statement will result in a crash cause no more move will
    # be found in the payment line
    def action_cancel(self, cr, uid, ids, *args):
        payment_line_obj = self.pool.get('payment.line')
        invoices = self.browse(cr, uid, ids)
        for inv in invoices:
            inv_mv_lines = map(lambda x: x.id, inv.move_id.line_id)
            pl_line_ids = payment_line_obj.search(cr, uid, [('move_line_id','in',inv_mv_lines)])
            if pl_line_ids:
                pay_line = payment_line_obj.browse(cr,uid,pl_line_ids)
                payment_order_name = ','.join(map(lambda x: x.order_id.reference, pay_line))
                raise osv.except_osv(_('Error!'), _("You cannot cancel an invoice which has already been imported in a payment order. Remove it from the following payment order : %s."%(payment_order_name)))
        result = super(Invoice, self).action_cancel(cr, uid, ids, *args)
        return result

    def _amount_to_pay(self, cursor, user, ids, name, args, context=None):
        '''Return the amount still to pay regarding all the payment orders'''
        if not ids:
            return {}
        res = {}
        for invoice in self.browse(cursor, user, ids, context=context):
            res[invoice.id] = 0.0
            if invoice.move_id:
                for line in invoice.move_id.line_id:
                    if not line.date_maturity or \
                            datetime.strptime(line.date_maturity, '%Y-%m-%d') \
                            < datetime.today():
                        res[invoice.id] += line.amount_to_pay
        return res

    _columns = {
        'amount_to_pay': fields.function(_amount_to_pay,
            type='float', string='Amount to be paid',
            help='The amount which should be paid at the current date\n' \
                    'minus the amount which is already in payment order'),
    }

Invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
