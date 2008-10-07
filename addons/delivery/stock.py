# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2004-2008 Tiny SPRL (http://tiny.be) All Rights Reserved.
#
# $Id$
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
###############################################################################

import netsvc
from osv import fields,osv
from tools.translate import _

# Overloaded stock_picking to manage carriers :
class stock_picking(osv.osv):
    _name = "stock.picking"
    _description = "Picking list"
    _inherit = 'stock.picking'
    _columns = {
        'carrier_id':fields.many2one("delivery.carrier","Carrier"),
        'volume': fields.float('Volume'),
        'weight': fields.float('Weight'),
    }

    def action_invoice_create(self, cursor, user, ids, journal_id=False,
            group=False, type='out_invoice', context=None):
        invoice_obj = self.pool.get('account.invoice')
        picking_obj = self.pool.get('stock.picking')
        carrier_obj = self.pool.get('delivery.carrier')
        grid_obj = self.pool.get('delivery.grid')
        invoice_line_obj = self.pool.get('account.invoice.line')

        result = super(stock_picking, self).action_invoice_create(cursor, user,
                ids, journal_id=journal_id, group=group, type=type,
                context=context)

        picking_ids = result.keys()
        invoice_ids = result.values()

        invoices = {}
        for invoice in invoice_obj.browse(cursor, user, invoice_ids,
                context=context):
            invoices[invoice.id] = invoice

        for picking in picking_obj.browse(cursor, user, picking_ids,
                context=context):
            if not picking.carrier_id:
                continue
            grid_id = carrier_obj.grid_get(cursor, user, [picking.carrier_id.id],
                    picking.address_id.id, context=context)
            if not grid_id:
                raise osv.except_osv(_('Warning'),
                        _('The carrier %s (id: %d) has no delivery grid!') \
                                % (picking.carrier_id.name,
                                    picking.carrier_id.id))
            invoice = invoices[result[picking.id]]
            price = grid_obj.get_price_from_picking(cursor, user, grid_id,
                    invoice.amount_untaxed, picking.weight, picking.volume,
                    context=context)
            account_id = picking.carrier_id.product_id.product_tmpl_id\
                    .property_account_income.id
            if not account_id:
                account_id = picking.carrier_id.product_id.categ_id\
                        .property_account_income_categ.id

            taxes = self.pool.get('account.tax').browse(cursor, user,
                    [x.id for x in picking.carrier_id.product_id.taxes_id])
            taxep = None
            partner_id=picking.address_id.partner_id and picking.address_id.partner_id.id or False
            if partner_id:
                taxep_id = self.pool.get('res.partner').property_get(cursor, user,partner_id,property_pref=['property_account_tax']).get('property_account_tax',False)
                if taxep_id:
					taxep=self.pool.get('account.tax').browse(cursor, user,taxep_id)                
            if not taxep or not taxep.id:
                taxes_ids = [x.id for x in picking.carrier_id.product_id.taxes_id]
            else:
                res5 = [taxep.id]
                for t in taxes:
                    if not t.tax_group==taxep.tax_group:
                        res5.append(t.id)
                taxes_ids = res5


            invoice_line_obj.create(cursor, user, {
                'name': picking.carrier_id.name,
                'invoice_id': invoice.id,
                'uos_id': picking.carrier_id.product_id.uos_id.id,
                'product_id': picking.carrier_id.product_id.id,
                'account_id': account_id,
                'price_unit': price,
                'quantity': 1,
                'invoice_line_tax_id': [(6, 0,taxes_ids)],
            })
        return result

stock_picking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

