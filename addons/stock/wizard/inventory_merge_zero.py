# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2005-2006 TINY SPRL. (http://tiny.be) All Rights Reserved.
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
#
##############################################################################


import wizard
import pooler


_form = """<?xml version="1.0"?>
<form string="Set Stock to Zero">
    <separator colspan="4" string="Set Stocks to Zero" />
    <label string="Do you want to set stocks to zero ?"/>
</form>
"""


def do_merge(self, cr, uid, data, context):
    invent_obj = pooler.get_pool(cr.dbname).get('stock.inventory')
    invent_line_obj = pooler.get_pool(cr.dbname).get('stock.inventory.line')
    prod_obj =  pooler.get_pool(cr.dbname).get('product.product')

    if len(data['ids']) <> 1:
        raise wizard.except_wizard("Warning",
                                   "Please select one and only one inventory!")

    cr.execute('select distinct location_id from stock_inventory_line where inventory_id=%d', (data['ids'][0],))
    loc_ids = map(lambda x: x[0], cr.fetchall())
    locs = ','.join(map(lambda x: str(x), loc_ids))

    cr.execute('select distinct location_id,product_id from stock_inventory_line where inventory_id=%d', (data['ids'][0],))
    inv = cr.fetchall()

    cr.execute('select distinct product_id from stock_move where (location_dest_id in ('+locs+')) or (location_id in ('+locs+'))')
    stock = cr.fetchall()
    for s in stock:
        for loc in loc_ids:
            if (loc,s[0]) not in inv:
                p = prod_obj.browse(cr, uid, s[0])
                invent_line_obj.create(cr, uid, {
                    'inventory_id': data['ids'][0],
                    'location_id': loc,
                    'product_id': s[0],
                    'product_uom': p.uom_id.id,
                    'product_qty': 0.0,
                    })
    return {}


class merge_inventory(wizard.interface):
    states = {
        'init' : {
            'actions' : [],
            'result' : {'type' : 'form',
                    'arch' : _form,
                    'fields' : {},
                    'state' : [('end', 'Cancel'),
                               ('merge', 'Set to Zero') ]}
        },
        'merge' : {
            'actions' : [],
            'result' : {'type' : 'action',
                        'action': do_merge,
                        'state' : 'end'}
        },
    }
merge_inventory("inventory.merge.stock.zero")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

