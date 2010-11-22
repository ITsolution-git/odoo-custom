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

class product_product(osv.osv):
    _inherit = 'product.product'

    def _pricelist_calculate(self, cr, uid, ids, name, arg, context=None):
        result = {}
        pricelist_obj = self.pool.get('product.pricelist')
        if context is None:
            context = {}
        if name == 'pricelist_purchase':
            pricelist_ids = pricelist_obj.search(cr, uid, [('type', '=', 'purchase')])
        else:
            pricelist_ids = pricelist_obj.search(cr, uid, [('type', '=', 'sale')])
        pricelist_browse = pricelist_obj.browse(cr, uid, pricelist_ids, context=context)
        for product in self.browse(cr, uid, ids, context=context):
            result[product.id] = ""
            for pricelist in pricelist_browse:
                for version in pricelist.version_id:
                    cr.execute("""select min_quantity from product_pricelist_item where price_version_id = %s""", [version.id])
                    items_lines = cr.fetchall()
                    for line in items_lines:
                        qty = line[0]
                        try:
                            prices = pricelist_obj.price_get(cr, uid, [pricelist.id], product.id, qty, partner=None, context=None)
                            price = prices.get(pricelist.id) or 0.0
                        except:
                            price = 0.0
                        result[product.id] += "%s (%.2f) : %.2f\n" % (pricelist.name, qty or 0.0, price)
                        break
                    break
        return result

    _columns = {
        'pricelist_sale':fields.function(
            _pricelist_calculate,
            method=True,
            string='Sale Pricelists',
            store=True,
            type="text"),
        'pricelist_purchase':fields.function(
            _pricelist_calculate,
            method=True,
            string='Purchase Pricelists',
            store=True,
            type="text"),
    }

product_product()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: