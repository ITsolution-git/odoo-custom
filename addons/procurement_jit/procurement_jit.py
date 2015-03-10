# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2013 Tiny SPRL (<http://tiny.be>).
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


from openerp.osv import osv

class procurement_order(osv.osv):
    _inherit = "procurement.order"

    def create(self, cr, uid, vals, context=None):
        context = context or {}
        procurement_id = super(procurement_order, self).create(cr, uid, vals, context=context)
        if not context.get('procurement_autorun_defer'):
            self.run(cr, uid, [procurement_id], context=context)
            self.check(cr, uid, [procurement_id], context=context)
        return procurement_id

    def run(self, cr, uid, ids, context=None):
        context = context or {}
        context['procurement_autorun_defer'] = True
        res = super(procurement_order, self).run(cr, uid, ids, context=context)

        procurement_ids = self.search(cr, uid, [('move_dest_id.procurement_id', 'in', ids)], order='id', context=context)

        if procurement_ids:
            return self.run(cr, uid, procurement_ids, context=context)
        return res
