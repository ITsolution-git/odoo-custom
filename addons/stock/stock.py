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

from datetime import date, datetime
from dateutil import relativedelta

import time

from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp import tools
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp import SUPERUSER_ID
import openerp.addons.decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)


#----------------------------------------------------------
# Incoterms
#----------------------------------------------------------
class stock_incoterms(osv.osv):
    _name = "stock.incoterms"
    _description = "Incoterms"
    _columns = {
        'name': fields.char('Name', size=64, required=True, help="Incoterms are series of sales terms. They are used to divide transaction costs and responsibilities between buyer and seller and reflect state-of-the-art transportation practices."),
        'code': fields.char('Code', size=3, required=True, help="Incoterm Standard Code"),
        'active': fields.boolean('Active', help="By unchecking the active field, you may hide an INCOTERM you will not use."),
    }
    _defaults = {
        'active': True,
    }

#----------------------------------------------------------
# Stock Location
#----------------------------------------------------------

class stock_location(osv.osv):
    _name = "stock.location"
    _description = "Inventory Locations"
    _parent_name = "location_id"
    _parent_store = True
    _parent_order = 'name'
    _order = 'parent_left'
    def name_get(self, cr, uid, ids, context=None):
        res = self._complete_name(cr, uid, ids, 'complete_name', None, context=context)
        return res.items() 

    def _complete_name(self, cr, uid, ids, name, args, context=None):
        """ Forms complete name of location from parent location to child location.
        @return: Dictionary of values
        """
        res = {}
        for m in self.browse(cr, uid, ids, context=context):
            res[m.id] = m.name
            parent = m.location_id
            while parent:
                res[m.id] = parent.name + ' / ' + res[m.id]
                parent = parent.location_id
        return res

    def _get_sublocations(self, cr, uid, ids, context=None):
        """ return all sublocations of the given stock locations (included) """
        if context is None:
            context = {}
        context_with_inactive = context.copy()
        context_with_inactive['active_test']=False
        return self.search(cr, uid, [('id', 'child_of', ids)], context=context_with_inactive)

    _columns = {
        'name': fields.char('Location Name', size=64, required=True, translate=True),
        'active': fields.boolean('Active', help="By unchecking the active field, you may hide a location without deleting it."),
        'usage': fields.selection([('supplier', 'Supplier Location'), ('view', 'View'), ('internal', 'Internal Location'), ('customer', 'Customer Location'), ('inventory', 'Inventory'), ('procurement', 'Procurement'), ('production', 'Production'), ('transit', 'Transit Location for Inter-Companies Transfers')], 'Location Type', required=True,
                 help="""* Supplier Location: Virtual location representing the source location for products coming from your suppliers
                       \n* View: Virtual location used to create a hierarchical structures for your warehouse, aggregating its child locations ; can't directly contain products
                       \n* Internal Location: Physical locations inside your own warehouses,
                       \n* Customer Location: Virtual location representing the destination location for products sent to your customers
                       \n* Inventory: Virtual location serving as counterpart for inventory operations used to correct stock levels (Physical inventories)
                       \n* Procurement: Virtual location serving as temporary counterpart for procurement operations when the source (supplier or production) is not known yet. This location should be empty when the procurement scheduler has finished running.
                       \n* Production: Virtual counterpart location for production operations: this location consumes the raw material and produces finished products
                      """, select = True),

        'complete_name': fields.function(_complete_name, type='char', string="Location Name",
                            store={'stock.location': (_get_sublocations, ['name', 'location_id', 'active'], 10)}),
        'location_id': fields.many2one('stock.location', 'Parent Location', select=True, ondelete='cascade'),
        'child_ids': fields.one2many('stock.location', 'location_id', 'Contains'),

        'partner_id': fields.many2one('res.partner', 'Owner', help="Owner of the location if not internal"),

        'comment': fields.text('Additional Information'),
        'posx': fields.integer('Corridor (X)', help="Optional localization details, for information purpose only"),
        'posy': fields.integer('Shelves (Y)', help="Optional localization details, for information purpose only"),
        'posz': fields.integer('Height (Z)', help="Optional localization details, for information purpose only"),

        'parent_left': fields.integer('Left Parent', select=1),
        'parent_right': fields.integer('Right Parent', select=1),

        'company_id': fields.many2one('res.company', 'Company', select=1, help='Let this field empty if this location is shared between all companies'),
        'scrap_location': fields.boolean('Scrap Location', help='Check this box to allow using this location to put scrapped/damaged goods.'),
        'removal_strategy_ids': fields.one2many('product.removal', 'location_id', 'Removal Strategies'),
        'putaway_strategy_ids': fields.one2many('product.putaway', 'location_id', 'Put Away Strategies'),
    }
    _defaults = {
        'active': True,
        'usage': 'internal',
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.location', context=c),
        'posx': 0,
        'posy': 0,
        'posz': 0,
        'scrap_location': False,
    }
    
    def get_putaway_strategy(self, cr, uid, location, product, context=None):
        pa = self.pool.get('product.putaway')
        categ = product.categ_id
        categs = [categ.id, False]
        while categ.parent_id:
            categ = categ.parent_id
            categs.append(categ.id)

        result = pa.search(cr,uid, [
            ('location_id', '=', location.id),
            ('product_categ_id', 'in', categs)
        ], context=context)
        if result:
            return pa.browse(cr, uid, result[0], context=context)
   
    def get_removal_strategy(self, cr, uid, location, product, context=None):
        pr = self.pool.get('product.removal')
        categ = product.categ_id
        categs = [categ.id, False]
        while categ.parent_id:
            categ = categ.parent_id
            categs.append(categ.id)

        result = pr.search(cr,uid, [
            ('location_id', '=', location.id),
            ('product_categ_id', 'in', categs)
        ], context=context)
        if result:
            return pr.browse(cr, uid, result[0], context=context).method


#----------------------------------------------------------
# Routes
#----------------------------------------------------------

class stock_location_route(osv.osv):
    _name = 'stock.location.route'
    _description = "Inventory Routes"
    _order = 'sequence'

    _columns = {
        'name': fields.char('Route Name', required=True),
        'sequence': fields.integer('Sequence'),
        'pull_ids': fields.one2many('procurement.rule', 'route_id', 'Pull Rules'),
        'active': fields.boolean('Active', help="If the active field is set to False, it will allow you to hide the route without removing it."),
        'push_ids': fields.one2many('stock.location.path', 'route_id', 'Push Rules'),
        'product_selectable': fields.boolean('Selectable on Product'),
        'product_categ_selectable': fields.boolean('Selectable on Product Category'),
        'warehouse_selectable': fields.boolean('Selectable on Warehouse'),
        'supplied_wh_id': fields.many2one('stock.warehouse', 'Supplied Warehouse'),
        'supplier_wh_id': fields.many2one('stock.warehouse', 'Supplier Warehouse'),
    }

    _defaults = {
        'sequence': lambda self, cr, uid, ctx: 0,
        'active': True,
        'product_selectable': True,
    }



#----------------------------------------------------------
# Quants
#----------------------------------------------------------

class stock_quant(osv.osv):
    """
    Quants are the smallest unit of stock physical instances
    """
    _name = "stock.quant"
    _description = "Quants"

    def _get_quant_name(self, cr, uid, ids, name, args, context=None):
        """ Forms complete name of location from parent location to child location.
        @return: Dictionary of values
        """
        res = {}
        for q in self.browse(cr, uid, ids, context=context):

            res[q.id] = q.product_id.code or ''
            if q.lot_id:
                res[q.id] = q.lot_id.name 
            res[q.id] += ': '+  str(q.qty) + q.product_id.uom_id.name
        return res

    _columns = {
        'name': fields.function(_get_quant_name, type='char', string='Identifier'),
        'product_id': fields.many2one('product.product', 'Product', required=True),
        'location_id': fields.many2one('stock.location', 'Location', required=True),
        'qty': fields.float('Quantity', required=True, help="Quantity of products in this quant, in the default unit of measure of the product"),
        'package_id': fields.many2one('stock.quant.package', string='Package', help="The package containing this quant"),
        'packaging_type_id': fields.related('package_id', 'packaging_id', type='many2one', relation='product.packaging', string='Type of packaging', store=True),
        'reservation_id': fields.many2one('stock.move', 'Reserved for Move', help="The move the quant is reserved for"),
        'reservation_op_id': fields.many2one('stock.pack.operation', 'Reserved for Pack Operation', help="The operation the quant is reserved for"),
        'lot_id': fields.many2one('stock.production.lot', 'Lot'),
        'cost': fields.float('Unit Cost'),
        'owner_id': fields.many2one('res.partner', 'Owner', help="This is the owner of the quant"),

        'create_date': fields.datetime('Creation Date'),
        'in_date': fields.datetime('Incoming Date'),

        'history_ids': fields.many2many('stock.move', 'stock_quant_move_rel', 'quant_id', 'move_id', 'Moves', help='Moves that operate(d) on this quant'),
        'company_id': fields.many2one('res.company', 'Company', help="The company to which the quants belong", required=True),

        # Used for negative quants to reconcile after compensated by a new positive one
        'propagated_from_id': fields.many2one('stock.quant', 'Linked Quant', help='The negative quant this is coming from'),
        'negative_dest_location_id': fields.many2one('stock.location', 'Destination Location', help='Technical field used to record the destination location of a move that created a negative quant'),
    }

    _defaults = {
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.quant', context=c),
    }

    def quants_reserve(self, cr, uid, quants, move, context=None):
        toreserve = []
        for quant,qty in quants:
            if not quant: continue
            self._quant_split(cr, uid, quant, qty, context=context)
            toreserve.append(quant.id)
        return self.write(cr, SUPERUSER_ID, toreserve, {'reservation_id': move.id}, context=context)

    # add location_dest_id in parameters (False=use the destination of the move)
    def quants_move(self, cr, uid, quants, move, lot_id = False, owner_id = False, package_id = False, context=None):
        for quant, qty in quants:
            #quant may be a browse record or None
            quant_record = self.move_single_quant(cr, uid, quant, qty, move, lot_id = lot_id, package_id = package_id, context=context)
            #quant_record is the quant newly created or already split
            self._quant_reconcile_negative(cr, uid, quant_record, context=context)


    def check_preferred_location(self, cr, uid, move, context=None):
        if move.putaway_ids and move.putaway_ids[0]:
            #Take only first suggestion for the moment
            return move.putaway_ids[0].location_id
        return move.location_dest_id

    def move_single_quant(self, cr, uid, quant, qty, move, lot_id = False, owner_id = False, package_id = False, context=None):
        if not quant:
            quant = self._quant_create(cr, uid, qty, move, lot_id = lot_id, owner_id = owner_id, package_id = package_id, context = context)
        else:
            self._quant_split(cr, uid, quant, qty, context=context)
        # FP Note: improve this using preferred locations
        location_to = self.check_preferred_location(cr, uid, move, context=context)
        self.write(cr, SUPERUSER_ID, [quant.id], {
            'location_id': location_to.id,
            #'reservation_id': move.move_dest_id and move.move_dest_id.id or False,
            'history_ids': [(4, move.id)]
        })
        quant.refresh()
        return quant

    def quants_get_prefered_domain(self, cr, uid, location, product, qty, domain=None, prefered_domain=False, fallback_domain=False, restrict_lot_id=False, restrict_partner_id=False, context=None):
        if prefered_domain and fallback_domain:
            if domain is None:
                domain = []
            quants = self.quants_get(cr, uid, location, product, qty, domain=domain + prefered_domain, context=context)
            res_qty = qty
            for quant in quants:
                if quant[0]:
                    res_qty -= quant[1]
            if res_qty > 0:
                #try to replace the last tuple (None, res_qty) with something that wasn't chosen at first because of the prefered order
                quants.pop()
                unprefered_quants = self.quants_get(cr, uid, location, product, res_qty, domain=domain + fallback_domain, context=context)
                for quant in unprefered_quants:
                    quants.append(quant)
            return quants
        return self.quants_get(cr, uid, location, product, qty, domain=domain, restrict_lot_id=restrict_lot_id, restrict_partner_id=restrict_partner_id, context=context)

    def quants_get(self, cr, uid, location, product, qty, domain=None, restrict_lot_id=False, restrict_partner_id=False, context=None):
        """
        Use the removal strategies of product to search for the correct quants
        If you inherit, put the super at the end of your method.

        :location: browse record of the parent location in which the quants have to be found
        :product: browse record of the product to find
        :qty in UoM of product
        :lot_id NOT USED YET !
        """
        result = []
        domain = domain or [('qty', '>', 0.0)]
        if restrict_partner_id:
            domain += [('owner_id', '=', restrict_partner_id)]
        if restrict_lot_id:
            domain += [('lot_id', '=', restrict_lot_id)]
        if location:
            removal_strategy = self.pool.get('stock.location').get_removal_strategy(cr, uid, location, product, context=context) or 'fifo'
            if removal_strategy == 'fifo':
                result += self._quants_get_fifo(cr, uid, location, product, qty, domain, context=context)
            elif removal_strategy == 'lifo':
                result += self._quants_get_lifo(cr, uid, location, product, qty, domain, context=context)
            else:
                raise osv.except_osv(_('Error!'), _('Removal strategy %s not implemented.' % (removal_strategy,)))
        return result

    #
    # Create a quant in the destination location
    # Create a negative quant in the source location if it's an internal location
    #
    def _quant_create(self, cr, uid, qty, move, lot_id=False, owner_id=False, package_id = False, force_location=False, context=None):
        # FP Note: TODO: compute the right price according to the move, with currency convert
        # QTY is normally already converted to main product's UoM
        if context is None:
            context = {}
        price_unit = self.pool.get('stock.move').get_price_unit(cr, uid, move, context=context)
        location = force_location or move.location_dest_id
        vals = {
            'product_id': move.product_id.id,
            'location_id': location.id,
            'qty': qty,
            'cost': price_unit,
            'history_ids': [(4, move.id)],
            'in_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'company_id': move.company_id.id,
            'lot_id': lot_id,
            'owner_id': owner_id,
        }

        if move.location_id.usage == 'internal':
            #if we were trying to move something from an internal location and reach here (quant creation),
            #it means that a negative quant has to be created as well.
            negative_vals = vals.copy()
            negative_vals['location_id'] = move.location_id.id
            negative_vals['qty'] = -qty
            negative_vals['cost'] = price_unit
            negative_vals['negative_dest_location_id'] = move.location_dest_id.id
            negative_vals['package_id'] = package_id
            negative_quant_id = self.create(cr, SUPERUSER_ID, negative_vals, context=context)
            vals.update({'propagated_from_id': negative_quant_id})

        #create the quant as superuser, because we want to restrict the creation of quant manually: they should always use this method to create quants
        quant_id = self.create(cr, SUPERUSER_ID, vals, context=context)
        return self.browse(cr, uid, quant_id, context=context)

    def _quant_split(self, cr, uid, quant, qty, context=None):
        context = context or {}
        if (quant.qty > 0 and quant.qty <= qty) or (quant.qty <= 0 and quant.qty >= qty):
            return False
        new_quant = self.copy(cr, SUPERUSER_ID, quant.id, default={'qty': quant.qty - qty}, context=context)
        self.write(cr, SUPERUSER_ID, quant.id, {'qty': qty}, context=context)
        quant.refresh()
        return self.browse(cr, uid, new_quant, context=context)

    def _get_latest_move(self, cr, uid, quant, context=None):
        move = False
        for m in quant.history_ids:
            if not move or m.date > move.date:
                move = m
        return move

    #def _reconcile_single_negative_quant(self, cr, uid, to_solve_quant, quant, quant_neg, qty, context=None):
    #    move = self._get_latest_move(cr, uid, to_solve_quant, context=context)
    #    remaining_solving_quant = self._quant_split(cr, uid, quant, qty, context=context)
    #    remaining_to_solve_quant = self._quant_split(cr, uid, to_solve_quant, qty, context=context)
    #    remaining_neg_quant = self._quant_split(cr, uid, quant_neg, -qty, context=context)
    #    #if the reconciliation was not complete, we need to link together the remaining parts
    #    if remaining_to_solve_quant and remaining_neg_quant:
    #        self.write(cr, uid, remaining_to_solve_quant.id, {'propagated_from_id': remaining_neg_quant.id}, context=context)
    #    #delete the reconciled quants, as it is replaced by the solving quant
    #    if remaining_neg_quant:
    #        otherquant_ids = self.search(cr, uid, [('propagated_from_id', '=', quant_neg.id)], context=context)
    #        self.write(cr, uid, otherquant_ids, {'propagated_from_id': remaining_neg_quant.id}, context=context)
    #    self.unlink(cr, SUPERUSER_ID, [quant_neg.id, to_solve_quant.id], context=context)
    #    #call move_single_quant to ensure recursivity if necessary and do the stock valuation
    #    self.move_single_quant(cr, uid, quant, qty, move, context=context)
    #    return remaining_solving_quant, remaining_to_solve_quant

    def _quants_merge(self, cr, uid, solved_quant_ids, solving_quant, context=None):
        path = []
        for move in solving_quant.history_ids:
            path.append((4, move.id))
        self.write(cr, SUPERUSER_ID, solved_quant_ids, {'history_ids': path}, context=context)

    def _quant_reconcile_negative(self, cr, uid, quant, context=None):
        """
            When new quant arrive in a location, try to reconcile it with
            negative quants. If it's possible, apply the cost of the new
            quant to the conter-part of the negative quant.
        """
        if quant.location_id.usage != 'internal':
            return False
        solving_quant = quant
        dom = [('qty', '<', 0)]
        dom += [('lot_id', '=', quant.lot_id and quant.lot_id.id or False)]
        dom += [('owner_id', '=', quant.owner_id and quant.owner_id.id or False)]
        dom += [('package_id', '=', quant.package_id and quant.package_id.id or False)]
        quants = self.quants_get(cr, uid, quant.location_id, quant.product_id, quant.qty, [('qty', '<', '0')], context=context)
        for quant_neg, qty in quants:
            if not quant_neg:
                continue
            to_solve_quant_ids = self.search(cr, uid, [('propagated_from_id', '=', quant_neg.id)], context=context)
            if not to_solve_quant_ids:
                continue
            solving_qty = qty
            solved_quant_ids = []
            for to_solve_quant in self.browse(cr, uid, to_solve_quant_ids, context=context):
                if solving_qty <= 0:
                    continue
                solved_quant_ids.append(to_solve_quant.id)
                self._quant_split(cr, uid, to_solve_quant, min(solving_qty, to_solve_quant.qty), context=context)
                solving_qty -= min(solving_qty, to_solve_quant.qty)
            remaining_solving_quant = self._quant_split(cr, uid, solving_quant, qty, context=context)
            remaining_neg_quant = self._quant_split(cr, uid, quant_neg, -qty, context=context)
            #if the reconciliation was not complete, we need to link together the remaining parts
            if remaining_neg_quant:
                remaining_to_solve_quant_ids = self.search(cr, uid, [('propagated_from_id', '=', quant_neg.id), ('id', 'not in', solved_quant_ids)], context=context)
                if remaining_to_solve_quant_ids:
                    self.write(cr, SUPERUSER_ID, remaining_to_solve_quant_ids, {'propagated_from_id': remaining_neg_quant.id}, context=context)
            #delete the reconciled quants, as it is replaced by the solved quants
            self.unlink(cr, SUPERUSER_ID, [quant_neg.id], context=context)
            #price update + accounting entries adjustments
            self._price_update(cr, uid, solved_quant_ids, solving_quant.cost, context=context)
            #merge history (and cost?)
            self._quants_merge(cr, uid, solved_quant_ids, solving_quant, context=context)
            self.unlink(cr, SUPERUSER_ID, [solving_quant.id], context=context)
            solving_quant = remaining_solving_quant

            #solving_quant, dummy = self._reconcile_single_negative_quant(cr, uid, to_solve_quant, solving_quant, quant_neg, qty, context=context)

    def _price_update(self, cr, uid, ids, newprice, context=None):
        self.write(cr, SUPERUSER_ID, ids, {'cost': newprice}, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        #We want to trigger the move with nothing on reserved_quant_ids for the store of the remaining quantity
        if 'reservation_id' in vals:
            reservation_ids = self.browse(cr, uid, ids, context=context)
            moves_to_warn = set()
            for reser in reservation_ids:
                if reser.reservation_id:
                    moves_to_warn.add(reser.reservation_id.id)
            self.pool.get('stock.move').write(cr, uid, list(moves_to_warn), {'reserved_quant_ids': []}, context=context)
        return super(stock_quant, self).write(cr, SUPERUSER_ID, ids, vals, context=context)

    def quants_unreserve(self, cr, uid, move, context=None):
        #cr.execute('update stock_quant set reservation_id=NULL where reservation_id=%s', (move.id,))
        #need write for related store of remaining qty
        related_quants = [x.id for x in move.reserved_quant_ids]
        self.write(cr, SUPERUSER_ID, related_quants, {'reservation_id': False, 'reservation_op_id': False}, context=context)
        return True

    #
    # Implementation of removal strategies
    # If it can not reserve, it will return a tuple (None, qty)
    #
    def _quants_get_order(self, cr, uid, location, product, quantity, domain=[], orderby='in_date', context=None):
        domain += location and [('location_id', 'child_of', location.id)] or []
        domain += [('product_id', '=', product.id)] + domain
        res = []
        offset = 0
        while quantity > 0:
            quants = self.search(cr, uid, domain, order=orderby, limit=10, offset=offset, context=context)
            if not quants:
                res.append((None, quantity))
                break
            for quant in self.browse(cr, uid, quants, context=context):
                if quantity >= abs(quant.qty):
                    res += [(quant, abs(quant.qty))]
                    quantity -= abs(quant.qty)
                elif quantity != 0:
                    res += [(quant, quantity)]
                    quantity = 0
                    break
            offset += 10
        return res

    def _quants_get_fifo(self, cr, uid, location, product, quantity, domain=[], context=None):
        order = 'in_date'
        return self._quants_get_order(cr, uid, location, product, quantity, domain, order, context=context)

    def _quants_get_lifo(self, cr, uid, location, product, quantity, domain=[], context=None):
        order = 'in_date desc'
        return self._quants_get_order(cr, uid, location, product, quantity, domain, order, context=context)

    # Return the company owning the location if any
    def _location_owner(self, cr, uid, quant, location, context=None):
        return location and (location.usage == 'internal') and location.company_id or False

    def _check_location(self, cr, uid, ids, context=None):
        for record in self.browse(cr, uid, ids, context=context):
            if record.location_id.usage == 'view':
                raise osv.except_osv(_('Error'), _('You cannot move product %s to a location of type view %s.')% (record.product_id.name, record.location_id.name))
        return True

    _constraints = [
        (_check_location, 'You cannot move products to a location of the type view.', ['location_id'])
    ]


#----------------------------------------------------------
# Stock Picking
#----------------------------------------------------------

class stock_picking(osv.osv):
    _name = "stock.picking"
    _inherit = ['mail.thread']
    _description = "Picking List"
    _order = "priority desc, date desc, id desc"

    def _set_min_date(self, cr, uid, id, field, value, arg, context=None):
        move_obj = self.pool.get("stock.move")
        if value:
            move_ids = [move.id for move in self.browse(cr, uid, id, context=context).move_lines]
            move_obj.write(cr, uid, move_ids, {'date_expected': value}, context=context)

    def get_min_max_date(self, cr, uid, ids, field_name, arg, context=None):
        """ Finds minimum and maximum dates for picking.
        @return: Dictionary of values
        """
        res = {}
        for id in ids:
            res[id] = {'min_date': False, 'max_date': False}
        if not ids:
            return res
        cr.execute("""select
                picking_id,
                min(date_expected),
                max(date_expected)
            from
                stock_move
            where
                picking_id IN %s
            group by
                picking_id""",(tuple(ids),))
        for pick, dt1, dt2 in cr.fetchall():
            res[pick]['min_date'] = dt1
            res[pick]['max_date'] = dt2
        return res

    def create(self, cr, user, vals, context=None):
        context = context or {}
        if ('name' not in vals) or (vals.get('name') in ('/', False)):
            ptype_id = vals.get('picking_type_id', context.get('default_picking_type_id', False))
            sequence_id = self.pool.get('stock.picking.type').browse(cr, user, ptype_id, context=context).sequence_id.id
            vals['name'] = self.pool.get('ir.sequence').get_id(cr, user, sequence_id, 'id', context=context)
                
        return super(stock_picking, self).create(cr, user, vals, context)

    # The state of a picking depends on the state of its related stock.move
    # draft: the picking has no line or any one of the lines is draft
    # done, draft, cancel: all lines are done / draft / cancel
    # confirmed, auto, assigned depends on move_type (all at once or direct)
    def _state_get(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for pick in self.browse(cr, uid, ids, context=context):
            if (not pick.move_lines) or any([x.state == 'draft' for x in pick.move_lines]):
                res[pick.id] = 'draft'
                continue
            if all([x.state == 'cancel' for x in pick.move_lines]):
                res[pick.id] = 'cancel'
                continue
            if all([x.state in ('cancel','done') for x in pick.move_lines]):
                res[pick.id] = 'done'
                continue

            order = {'confirmed':0, 'waiting':1, 'assigned':2}
            order_inv = dict(zip(order.values(),order.keys()))
            lst = [order[x.state] for x in pick.move_lines if x.state not in ('cancel','done')]
            if pick.move_lines == 'one':
                res[pick.id] = order_inv[min(lst)]
            else:
                res[pick.id] = order_inv[max(lst)]
        return res

    def _get_pickings(self, cr, uid, ids, context=None):
        res = set()
        for move in self.browse(cr, uid, ids, context=context):
            if move.picking_id:
                res.add(move.picking_id.id)
        return list(res)

    def _get_pack_operation_exist(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for pick in self.browse(cr, uid, ids, context=context):
            res[pick.id] = False
            if pick.pack_operation_ids:
                res[pick.id] = True
        return res

    def _get_quant_reserved_exist(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for pick in self.browse(cr, uid, ids, context=context):            
            res[pick.id] = False
            for move in pick.move_lines:
                if move.reserved_quant_ids:
                    res[pick.id] = True
                    continue      
        return res

    def action_assign_owner(self, cr, uid, ids, context=None):
        for picking in self.browse(cr, uid, ids, context=context):
            packop_ids = [op.id for op in picking.pack_operation_ids] 
            self.pool.get('stock.pack.operation').write(cr, uid, packop_ids, {'owner_id': picking.owner_id.id}, context=context)

    _columns = {
        'name': fields.char('Reference', size=64, select=True, states={'done':[('readonly', True)], 'cancel':[('readonly',True)]}),
        'origin': fields.char('Source Document', size=64, states={'done':[('readonly', True)], 'cancel':[('readonly',True)]}, help="Reference of the document", select=True),
        'backorder_id': fields.many2one('stock.picking', 'Back Order of', states={'done':[('readonly', True)], 'cancel':[('readonly',True)]}, help="If this shipment was split, then this field links to the shipment which contains the already processed part.", select=True),
        'note': fields.text('Notes', states={'done':[('readonly', True)], 'cancel':[('readonly',True)]}),
        'move_type': fields.selection([('direct', 'Partial'), ('one', 'All at once')], 'Delivery Method', required=True, states={'done':[('readonly', True)], 'cancel':[('readonly',True)]}, help="It specifies goods to be deliver partially or all at once"),
        'state': fields.function(_state_get, type="selection", store = {
            'stock.picking': (lambda self, cr, uid, ids, ctx: ids, ['move_type', 'move_lines'], 20),
            'stock.move': (_get_pickings, ['state', 'picking_id'], 20)}, selection = [
            ('draft', 'Draft'),
            ('cancel', 'Cancelled'),
            ('waiting', 'Waiting Another Operation'),
            ('confirmed', 'Waiting Availability'),
            ('assigned', 'Ready to Transfer'),
            ('done', 'Transferred'),
            ], string='Status', readonly=True, select=True, track_visibility='onchange', help="""
            * Draft: not confirmed yet and will not be scheduled until confirmed\n
            * Waiting Another Operation: waiting for another move to proceed before it becomes automatically available (e.g. in Make-To-Order flows)\n
            * Waiting Availability: still waiting for the availability of products\n
            * Ready to Transfer: products reserved, simply waiting for confirmation.\n
            * Transferred: has been processed, can't be modified or cancelled anymore\n
            * Cancelled: has been cancelled, can't be confirmed anymore"""
        ),
        'priority': fields.selection([('0', 'Low'), ('1', 'Normal'), ('2', 'High')], string='Priority', required=True),
        'min_date': fields.function(get_min_max_date, multi="min_max_date", fnct_inv=_set_min_date,
                 store={'stock.move': (_get_pickings, ['state', 'date_expected'], 20)}, type='datetime', string='Scheduled Date', select=1, help="Scheduled time for the first part of the shipment to be processed"),
        'max_date': fields.function(get_min_max_date, multi="min_max_date",
                 store={'stock.move': (_get_pickings, ['state', 'date_expected'], 20)}, type='datetime', string='Max. Expected Date', select=2, help="Scheduled time for the last part of the shipment to be processed"),
        'date': fields.datetime('Commitment Date', help="Date promised for the completion of the transfer order, usually set the time of the order and revised later on.", select=True, states={'done':[('readonly', True)], 'cancel':[('readonly',True)]}),
        'date_done': fields.datetime('Date of Transfer', help="Date of Completion", states={'done':[('readonly', True)], 'cancel':[('readonly',True)]}),
        'move_lines': fields.one2many('stock.move', 'picking_id', 'Internal Moves', states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}),
        'quant_reserved_exist': fields.function(_get_quant_reserved_exist, type='boolean', string='Quant already reserved ?', help='technical field used to know if there is already at least one quant reserved on moves of a given picking'),
        'partner_id': fields.many2one('res.partner', 'Partner', states={'done':[('readonly', True)], 'cancel':[('readonly',True)]}),
        'company_id': fields.many2one('res.company', 'Company', required=True, select=True, states={'done':[('readonly', True)], 'cancel':[('readonly',True)]}),
        'pack_operation_ids': fields.one2many('stock.pack.operation', 'picking_id', string='Related Packing Operations'),
        'pack_operation_exist': fields.function(_get_pack_operation_exist, type='boolean', string='Pack Operation Exists?', help='technical field for attrs in view'),
        'picking_type_id': fields.many2one('stock.picking.type', 'Picking Type', required=True),

        'owner_id': fields.many2one('res.partner', 'Owner', help="Default Owner"),
        # Used to search on pickings
        'product_id': fields.related('move_lines', 'product_id', type='many2one', relation='product.product', string='Product'),#?
        'location_id': fields.related('move_lines', 'location_id', type='many2one', relation='stock.location', string='Location', readonly=True),
        'location_dest_id': fields.related('move_lines', 'location_dest_id', type='many2one', relation='stock.location', string='Destination Location', readonly=True),
        'group_id': fields.related('move_lines', 'group_id', type='many2one', relation='procurement.group', string='Procurement Group', readonly=True, 
              store={
                  'stock.picking': (lambda self, cr, uid, ids, ctx: ids, ['move_lines'], 10),
                  'stock.move': (_get_pickings, ['group_id', 'picking_id'], 10),
              }),
    }

    _defaults = {
        'name': lambda self, cr, uid, context: '/',
        'state': 'draft',
        'move_type': 'one',
        'priority' : '1', #normal
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.picking', context=c)
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)', 'Reference must be unique per company!'),
    ]

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        picking_obj = self.browse(cr, uid, id, context=context)
        if ('name' not in default) or (picking_obj.name == '/'):
            default['name'] = '/'
        if not default.get('backorder_id'):
            default['backorder_id'] = False
        return super(stock_picking, self).copy(cr, uid, id, default, context)

    def action_confirm(self, cr, uid, ids, context=None):
        todo = []
        todo_force_assign = []
        for picking in self.browse(cr, uid, ids, context=context):
            if picking.picking_type_id.auto_force_assign:
                todo_force_assign.append(picking.id)
            for r in picking.move_lines:
                if r.state == 'draft':
                    todo.append(r.id)
        if len(todo):
            self.pool.get('stock.move').action_confirm(cr, uid, todo, context=context)

        if todo_force_assign:
            self.force_assign(cr, uid, todo_force_assign, context=context)
        return True

    def action_assign(self, cr, uid, ids, *args):
        """ Changes state of picking to available if all moves are confirmed.
        @return: True
        """
        for pick in self.browse(cr, uid, ids):
            if pick.state == 'draft':
                self.action_confirm(cr, uid, [pick.id])
            move_ids = [x.id for x in pick.move_lines if x.state == 'confirmed']
            if not move_ids:
                raise osv.except_osv(_('Warning!'), _('No product available.'))
            self.pool.get('stock.move').action_assign(cr, uid, move_ids)
        return True

    def force_assign(self, cr, uid, ids, context=None):
        """ Changes state of picking to available if moves are confirmed or waiting.
        @return: True
        """
        for pick in self.browse(cr, uid, ids, context=context):
            move_ids = [x.id for x in pick.move_lines if x.state in ['confirmed', 'waiting']]
            self.pool.get('stock.move').force_assign(cr, uid, move_ids, context=context)
        return True

    def cancel_assign(self, cr, uid, ids, *args):
        """ Cancels picking and moves.
        @return: True
        """
        for pick in self.browse(cr, uid, ids):
            move_ids = [x.id for x in pick.move_lines]
            self.pool.get('stock.move').cancel_assign(cr, uid, move_ids)
        return True

    def action_cancel(self, cr, uid, ids, context=None):
        for pick in self.browse(cr, uid, ids, context=context):
            ids2 = [move.id for move in pick.move_lines]
            self.pool.get('stock.move').action_cancel(cr, uid, ids2, context)
        return True

    def action_done(self, cr, uid, ids, context=None):
        """Changes picking state to done by processing the Stock Moves of the Picking

        Normally that happens when the button "Done" is pressed on a Picking view.
        @return: True
        """
        for pick in self.browse(cr, uid, ids, context=context):
            todo = []
            for move in pick.move_lines:
                if move.state == 'draft':
                    self.pool.get('stock.move').action_confirm(cr, uid, [move.id],
                        context=context)
                    todo.append(move.id)
                elif move.state in ('assigned','confirmed'):
                    todo.append(move.id)
            if len(todo):
                self.pool.get('stock.move').action_done(cr, uid, todo, context=context)
        return True

    def unlink(self, cr, uid, ids, context=None):
        move_obj = self.pool.get('stock.move')
        context = context or {}
        for pick in self.browse(cr, uid, ids, context=context):
            ids2 = [move.id for move in pick.move_lines]
            move_obj.action_cancel(cr, uid, ids2, context=context)
            move_obj.unlink(cr, uid, ids2, context=context)
        return super(stock_picking, self).unlink(cr, uid, ids, context=context)

    # Methods for partial pickings

    def _create_backorder(self, cr, uid, picking, backorder_moves=[], context=None):
        """
            Move all non-done lines into a new backorder picking
        """
        if not backorder_moves:
            backorder_moves = picking.move_lines
        backorder_move_ids = [x.id for x in backorder_moves if x.state not in ('done','cancel')]
        if 'do_only_split' in context and context['do_only_split']:
            backorder_move_ids = [x.id for x in backorder_moves if x.id not in context['split']]

        if backorder_move_ids:
            backorder_id = self.copy(cr, uid, picking.id, {
                'name': '/',
                'move_lines': [],
                'pack_operation_ids': [],
                'backorder_id': picking.id,
            })
            back_order_name = self.browse(cr, uid, backorder_id, context=context).name
            self.message_post(cr, uid, picking.id, body=_("Back order <em>%s</em> <b>created</b>.") % (back_order_name), context=context)
            move_obj = self.pool.get("stock.move")
            move_obj.write(cr, uid, backorder_move_ids, {'picking_id': backorder_id}, context=context)
            self.pool.get("stock.picking").action_confirm(cr, uid, [picking.id], context=context)
            self.action_confirm(cr, uid, [backorder_id], context=context)
            return backorder_id
        return False

    def do_prepare_partial(self, cr, uid, picking_ids, context=None):
        context = context or {}
        pack_operation_obj = self.pool.get('stock.pack.operation')
        pack_obj = self.pool.get("stock.quant.package")
        quant_obj = self.pool.get("stock.quant")
        for picking in self.browse(cr, uid, picking_ids, context=context):
            for move in picking.move_lines:
                if move.state != 'assigned': continue
                #Check which of the reserved quants are entirely in packages (can be in separate method)
                packages = list(set([x.package_id for x in move.reserved_quant_ids if x.package_id]))
                done_packages = []
                for pack in packages:
                    cont = True
                    good_pack = False
                    test_pack = pack
                    while cont:
                        quants = pack_obj.get_content(cr, uid, [test_pack.id], context=context)
                        if all([x.reservation_id.id  == move.id for x in quant_obj.browse(cr, uid, quants, context=context) if x.reservation_id]):
                            good_pack = test_pack.id
                            if test_pack.parent_id:
                                test_pack = test_pack.parent_id
                            else:
                                cont = False
                        else:
                            cont = False
                    if good_pack:
                        done_packages.append(good_pack)
                done_packages = list(set(done_packages))

                #Create package operations
                reserved = set([x.id for x in move.reserved_quant_ids])
                remaining_qty = move.product_qty
                for pack in pack_obj.browse(cr, uid, done_packages, context=context):
                    quantl = pack_obj.get_content(cr, uid, [pack.id], context=context)
                    for quant in quant_obj.browse(cr, uid, quantl, context=context):
                        remaining_qty -= quant.qty
                    quants = set(pack_obj.get_content(cr, uid, [pack.id], context=context))
                    reserved -= quants
                    pack_operation_obj.create(cr, uid, {
                        'picking_id': picking.id,
                        'package_id': pack.id,
                        'product_qty': 1.0, 
                    }, context=context)
                
                yet_to_reserve = list(reserved)
                #Create operations based on quants
                for quant in quant_obj.browse(cr, uid, yet_to_reserve, context=context):
                    qty = min(quant.qty, move.product_qty)
                    remaining_qty -= qty
                    pack_operation_obj.create(cr, uid, {
                        'picking_id': picking.id,
                        'product_qty': qty,
                        'quant_id': quant.id,
                        'product_id': quant.product_id.id,
                        'lot_id': quant.lot_id and quant.lot_id.id or False,
                        'product_uom_id': quant.product_id.uom_id.id,
                        'owner_id': quant.owner_id and quant.owner_id.id or False,
                        'cost': quant.cost,
                        'package_id': quant.package_id and quant.package_id.id or False,
                    }, context=context)
                if remaining_qty > 0:
                    pack_operation_obj.create(cr, uid, {
                        'picking_id': picking.id,
                        'product_qty': remaining_qty,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_id.uom_id.id,
                        'cost': move.product_id.standard_price,
                    }, context=context)


    def do_rereserve(self, cr, uid, picking_ids, context=None):
        '''
            Needed for parameter create
        '''
        self.rereserve(cr, uid, picking_ids, context=context)

    def do_unreserve(self,cr,uid,picking_ids, context=None):
        """
          Will remove all quants for picking in picking_ids
        """
        ids_to_free = []
        quant_obj = self.pool.get("stock.quant")
        for picking in self.browse(cr, uid, picking_ids, context=context):
            for move in picking.move_lines:
                ids_to_free += [quant.id for quant in move.reserved_quant_ids]
        if ids_to_free:
            quant_obj.write(cr, SUPERUSER_ID, ids_to_free, {'reservation_id' : False, 'reservation_op_id': False }, context = context)

    def _reserve_quants_ops_move(self, cr, uid, ops, move, qty, create=False, context=None):
        """
          Will return the quantity that could not be reserved
        """
        quant_obj = self.pool.get("stock.quant")
        op_obj = self.pool.get("stock.pack.operation")
        if create and move.location_id.usage != 'internal':
            # Create quants
            quant = quant_obj._quant_create(cr, uid, qty, move, lot_id=ops.lot_id and ops.lot_id.id or False, owner_id=ops.owner_id and ops.owner_id.id or False, context=context)
            #TODO: location_id -> force location?
            quant.write({'reservation_op_id': ops.id, 'location_id': move.location_id.id})
            quant_obj.quants_reserve(cr, uid, [(quant, qty)], move, context=context)
            return 0
        else:
            #Quants get
            #prefered_order = "reservation_id IS NOT NULL" #TODO: reservation_id as such might work
            dom = op_obj._get_domain(cr, uid, ops, context=context)
            dom = dom + [('reservation_id', 'not in', [x.id for x in move.picking_id.move_lines])]
            quants = quant_obj.quants_get_prefered_domain(cr, uid, move.location_id, move.product_id, qty, domain=dom, prefered_domain=[('reservation_id', '=', False)], fallback_domain=[('reservation_id', '!=', False)], context=context)
            res_qty = qty
            for quant in quants:
                if quant[0]:  # If quant can be reserved
                    res_qty -= quant[1]
            quant_obj.quants_reserve(cr, uid, quants, move, context=context)
            quant_obj.write(cr, SUPERUSER_ID, [x[0].id for x in quants if x[0]], {'reservation_op_id': ops.id}, context=context)
            return res_qty

    def rereserve(self, cr, uid, picking_ids, create=False, context=None):
        """
            This will unreserve all products and reserve the quants from the operations again
            :return: Tuple (res, res2, resneg)
                res: dictionary of ops with quantity that could not be processed matching ops and moves
                res2: dictionary of moves with quantity that could not be processed matching ops and moves
                resneg: the negative quants to be created: resneg[move][ops] gives negative quant to be created
            tuple of dictionary with quantities of quant operation and product that can not be matched between ops and moves
            and dictionary with remaining values on moves
        """
        quant_obj = self.pool.get("stock.quant")
        pack_obj = self.pool.get("stock.quant.package")
        res = {} # Qty still to do from ops
        res2 = {} #what is left from moves
        resneg= {} #Number of negative quants to create for move/op
        for picking in self.browse(cr, uid, picking_ids, context=context):
            products_moves = {}
            # unreserve everything and initialize res2
            for move in picking.move_lines:
                quant_obj.quants_unreserve(cr, uid, move, context=context)
                res2[move.id] = move.product_qty
                resneg[move.id] = {}
                if move.state == 'assigned':
                    products_moves.setdefault(move.product_id.id, []).append(move)
                
                
            # Resort pack_operation_ids such that package transfers happen first and then the most specific operations from the product
            
            orderedpackops = picking.pack_operation_ids
            orderedpackops.sort(key = lambda x: ((x.package_id and not x.product_id) and -3 or 0) + (x.package_id and -1 or 0) + (x.lot_id and -1 or 0))

            for ops in orderedpackops:
                #If a product is specified in the ops, search for appropriate quants
                if ops.product_id:
                    # Match with moves
                    move_ids = ops.product_id.id in products_moves and filter(lambda x: res2[x.id] > 0, products_moves[ops.product_id.id]) or []
                    qty_to_do = ops.product_qty
                    while qty_to_do > 0 and move_ids:
                        move = move_ids.pop()
                        if res2[move.id] > qty_to_do: 
                            qty = qty_to_do
                            qty_to_do = 0
                        else:
                            qty = res2[move.id]
                            qty_to_do -= res2[move.id]
                        neg_qty = self._reserve_quants_ops_move(cr, uid, ops, move, qty, create=create, context=context)
                        if neg_qty > 0:
                            resneg[move.id].setdefault(ops.id, 0)
                            resneg [move.id][ops.id] += neg_qty
                        res2[move.id] -= qty
                    res[ops.id] = {}
                    res[ops.id][ops.product_id.id] = qty_to_do
                # In case only a package is specified, take all the quants from the package
                elif ops.package_id:
                    quants = quant_obj.browse(cr, uid, pack_obj.get_content(cr, uid, [ops.package_id.id], context=context))
                    quants = [x for x in quants if x.qty > 0] #Negative quants should not be moved
                    for quant in quants:
                        # Match with moves
                        move_ids = quant.product_id.id in products_moves and filter(lambda x: res2[x.id] > 0, products_moves[quant.product_id.id]) or []
                        qty_to_do = quant.qty
                        while qty_to_do > 0 and move_ids:
                            move = move_ids.pop()
                            if res2[move.id] > qty_to_do:
                                qty = qty_to_do
                                qty_to_do = 0.0
                            else:
                                qty = res2[move.id]
                                qty_to_do -= res2[move.id]
                            quant_obj.quants_reserve(cr, uid, [(quant, qty)], move, context=context)
                            quant_obj.write(cr, uid, [quant.id], {'reservation_op_id': ops.id}, context=context)
                            res2[move.id] -= qty
                        res.setdefault(ops.id, {}).setdefault(quant.product_id.id, 0.0)
                        res[ops.id][quant.product_id.id] += qty_to_do
        return (res, res2, resneg)


    def do_partial(self, cr, uid, picking_ids, context=None):
        """
            If no pack operation, we do simple action_done of the picking
            Otherwise, do the pack operations
        """
        if not context:
            context={}
        stock_move_obj = self.pool.get('stock.move')
        for picking in self.browse(cr, uid, picking_ids, context=context):
            if not picking.pack_operation_ids:
                self.action_done(cr, uid, [picking.id], context=context)
                continue
            else:
                # Rereserve quants
                # TODO: quants could have been created already in Supplier, so create parameter could disappear
                res = self.rereserve(cr, uid, [picking.id], create = True, context = context) #This time, quants need to be created 
                resneg = res[2]
                orig_moves = picking.move_lines
                orig_qtys = {}
                for orig in orig_moves:
                    orig_qtys[orig.id] = orig.product_qty
                #Add moves that operations need extra
                extra_moves = []
                for ops in res[0].keys():
                    for prod in res[0][ops].keys():
                        product = self.pool.get('product.product').browse(cr, uid, prod, context=context)
                        qty = res[0][ops][prod]
                        if qty > 0:
                            #Create moves for products too many on operation
                            move_id = stock_move_obj.create(cr, uid, {
                                            'name': product.name,
                                            'product_id': product.id,
                                            'product_uom_qty': qty,
                                            'product_uom': product.uom_id.id,
                                            'location_id': picking.location_id.id,
                                            'location_dest_id': picking.location_dest_id.id,
                                            'picking_id': picking.id,
                                            'picking_type_id': picking.picking_type_id.id,
                                            'group_id': picking.group_id.id,
                                        }, context=context)
                            stock_move_obj.action_confirm(cr, uid, [move_id], context=context)
                            move = stock_move_obj.browse(cr, uid, move_id, context=context)
                            ops_rec = self.pool.get("stock.pack.operation").browse(cr, uid, ops, context=context)
                            resneg[move_id] = {}
                            resneg[move_id][ops] = self._reserve_quants_ops_move(cr, uid, ops_rec, move, qty, create=True, context=context)
                            extra_moves.append(move_id)
                res2 = res[1]
                #Backorder
                for move in res2.keys():
                    if res2[move] > 0:
                        mov = stock_move_obj.browse(cr, uid, move, context=context)
                        new_move = stock_move_obj.split(cr, uid, mov, res2[move], context=context)
                        #Assign move as it was assigned before
                        stock_move_obj.action_assign(cr, uid, [new_move])
                todo = []
                orig_moves = [x for x in orig_moves if res[1][x.id] < orig_qtys[x.id]]
                for move in orig_moves + stock_move_obj.browse(cr, uid, extra_moves, context=context):
                    if move.state == 'draft':
                        self.pool.get('stock.move').action_confirm(cr, uid, [move.id], context=context)
                        todo.append(move.id)
                    elif move.state in ('assigned','confirmed'):
                        todo.append(move.id)
                if len(todo) and not ('do_only_split' in context and context['do_only_split']):
                    self.pool.get('stock.move').action_done(cr, uid, todo, negatives = resneg, context=context)
                elif 'do_only_split' in context and context['do_only_split']:
                    context.update({'split': [x.id for x in orig_moves] + extra_moves})
            picking.refresh()
            self._create_backorder(cr, uid, picking, context=context)
        return True

    def do_split(self, cr, uid, picking_ids, context=None):
        """
            just split the picking without making it 'done'
        """
        if context is None:
            context = {}
        ctx = context.copy()
        ctx['do_only_split'] = True
        self.do_partial(cr, uid, picking_ids, context=ctx)
        return True

    # Methods for the barcode UI

    def get_picking_for_packing_ui(self, cr, uid, context=None):
        return self.search(cr, uid, [('state', 'in', ('confirmed', 'assigned')), ('picking_type_id', '=', context.get('default_picking_type_id'))], context=context)

    def action_done_from_packing_ui(self, cr, uid, picking_id, only_split_lines=False, context=None):
        self.do_partial(cr, uid, picking_id, only_split_lines, context=context)
        #return id of next picking to work on
        return self.get_picking_for_packing_ui(cr, uid, context=context)

    def action_pack(self, cr, uid, picking_ids, context=None):
        stock_operation_obj = self.pool.get('stock.pack.operation')
        package_obj = self.pool.get('stock.quant.package')
        for picking_id in picking_ids:
            operation_ids = stock_operation_obj.search(cr, uid, [('picking_id', '=', picking_id), ('result_package_id', '=', False)], context=context)
            if operation_ids:
                package_id = package_obj.create(cr, uid, {}, context=context)
                stock_operation_obj.write(cr, uid, operation_ids, {'result_package_id': package_id}, context=context)
        return True

    def _deal_with_quants(self, cr, uid, picking_id, quant_ids, context=None):
        stock_operation_obj = self.pool.get('stock.pack.operation')
        todo_on_moves = []
        todo_on_operations = []
        for quant in self.pool.get('stock.quant').browse(cr, uid, quant_ids, context=context):
            tmp_moves, tmp_operations = stock_operation_obj._search_and_increment(cr, uid, picking_id, ('quant_id', '=', quant.id), context=context)
            todo_on_moves += tmp_moves
            todo_on_operations += tmp_operations
        return todo_on_moves, todo_on_operations

    def get_barcode_and_return_todo_stuff(self, cr, uid, picking_id, barcode_str, context=None):
        '''This function is called each time there barcode scanner reads an input'''
        #TODO: better error messages handling => why not real raised errors
        quant_obj = self.pool.get('stock.quant')
        package_obj = self.pool.get('stock.quant.package')
        product_obj = self.pool.get('product.product')
        stock_operation_obj = self.pool.get('stock.pack.operation')
        error_msg = ''
        todo_on_moves = []
        todo_on_operations = []
        #check if the barcode correspond to a product
        matching_product_ids = product_obj.search(cr, uid, [('ean13', '=', barcode_str)], context=context)
        if matching_product_ids:
            todo_on_moves, todo_on_operations = stock_operation_obj._search_and_increment(cr, uid, picking_id, ('product_id', '=', matching_product_ids[0]), context=context)

        #check if the barcode correspond to a quant
        matching_quant_ids = quant_obj.search(cr, uid, [('name', '=', barcode_str)], context=context)  # TODO need the location clause
        if matching_quant_ids:
            todo_on_moves, todo_on_operations = self._deal_with_quants(cr, uid, picking_id, [matching_quant_ids[0]], context=context)

        #check if the barcode correspond to a package
        matching_package_ids = package_obj.search(cr, uid, [('name', '=', barcode_str)], context=context)
        if matching_package_ids:
            included_package_ids = package_obj.search(cr, uid, [('parent_id', 'child_of', matching_package_ids[0])], context=context)
            included_quant_ids = quant_obj.search(cr, uid, [('package_id', 'in', included_package_ids)], context=context)
            todo_on_moves, todo_on_operations = self._deal_with_quants(cr, uid, picking_id, included_quant_ids, context=context)
        #write remaining qty on stock.move, to ease the treatment server side
        for todo in todo_on_moves:
            if todo[0] == 1:
                self.pool.get('stock.move').write(cr, uid, todo[1], todo[2], context=context)
            elif todo[0] == 0:
                self.pool.get('stock.move').create(cr, uid, todo[2], context=context)
        return {'warnings': error_msg, 'moves_to_update': todo_on_moves, 'operations_to_update': todo_on_operations}


class stock_production_lot(osv.osv):
    _name = 'stock.production.lot'
    _inherit = ['mail.thread']
    _description = 'Lot/Serial'
    _columns = {
        'name': fields.char('Serial Number', size=64, required=True, help="Unique Serial Number"),
        'ref': fields.char('Internal Reference', size=256, help="Internal reference number in case it differs from the manufacturer's serial number"),
        'product_id': fields.many2one('product.product', 'Product', required=True, domain=[('type', '<>', 'service')]),
        'quant_ids': fields.one2many('stock.quant', 'lot_id', 'Quants'),
        'create_date': fields.datetime('Creation Date'),
    }
    _defaults = {
        'name': lambda x, y, z, c: x.pool.get('ir.sequence').get(y, z, 'stock.lot.serial'),
        'product_id': lambda x, y, z, c: c.get('product_id', False),
    }
    _sql_constraints = [
        ('name_ref_uniq', 'unique (name, ref)', 'The combination of Serial Number and internal reference must be unique !'),
    ]
    def name_get(self, cr, uid, ids, context=None):
        res = []
        for lot in self.browse(cr, uid, ids, context=context):
            name = lot.name
#             if lot.partner_id:
#                 name += ' (' + lot.partner_id.name + ')'
            res.append((lot.id, name))
        return res



# ----------------------------------------------------
# Move
# ----------------------------------------------------

class stock_move(osv.osv):
    _name = "stock.move"
    _description = "Stock Move"
    _order = 'date_expected desc, id'
    _log_create = False

    def get_price_unit(self, cr, uid, move, context=None):
        """ Returns the unit price to store on the quant """
        return move.price_unit or move.product_id.standard_price

    def name_get(self, cr, uid, ids, context=None):
        res = []
        for line in self.browse(cr, uid, ids, context=context):
            name = line.location_id.name + ' > ' + line.location_dest_id.name
            if line.product_id.code:
                name = line.product_id.code + ': ' + name
            if line.picking_id.origin:
                name = line.picking_id.origin + '/ ' + name
            res.append((line.id, name))
        return res

    # FP Note: put this on quants, with the auto creation algo
    # def _check_tracking(self, cr, uid, ids, context=None):
    #     """ Checks if serial number is assigned to stock move or not.
    #     @return: True or False
    #     """
    #     for move in self.browse(cr, uid, ids, context=context):
    #         if not move.lot_id and \
    #            (move.state == 'done' and \
    #            ( \
    #                (move.product_id.track_production and move.location_id.usage == 'production') or \
    #                (move.product_id.track_production and move.location_dest_id.usage == 'production') or \
    #                (move.product_id.track_incoming and move.location_id.usage == 'supplier') or \
    #                (move.product_id.track_outgoing and move.location_dest_id.usage == 'customer') or \
    #                (move.product_id.track_incoming and move.location_id.usage == 'inventory') \
    #            )):
    #             return False
    #     return True

    def _quantity_normalize(self, cr, uid, ids, name, args, context=None):
        uom_obj = self.pool.get('product.uom')
        res = {}
        for m in self.browse(cr, uid, ids, context=context):
            res[m.id] = uom_obj._compute_qty_obj(cr, uid, m.product_uom, m.product_uom_qty, m.product_id.uom_id, round=False)
        return res

#     def _get_remaining_qty(self, cr, uid, ids, field_name, args, context=None):
#         #TODO: this function assumes that there aren't several stock move in the same picking with the same product. what should we do in that case?
#         #TODO take care of the quant on stock moves too
#         res = dict.fromkeys(ids, False)
#         for move in self.browse(cr, uid, ids, context=context):
#             res[move.id] = move.product_qty
#             if move.picking_id:
#                 for op in move.picking_id.pack_operation_ids:
#                     if op.product_id == move.product_id or (op.quant_id and op.quant_id.product_id == move.product_id):
#                         res[move.id] -= op.product_qty
#                     if op.package_id:
#                         #find the product qty recursively
#                         res[move.id] -= self.pool.get('stock.quant.package')._get_product_total_qty(cr, uid, op.package_id, move.product_id.id, context=context)
#         return res

    def _get_remaining_qty(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for move in self.browse(cr, uid, ids, context=context):
            res[move.id] = move.product_qty
            for quant in move.reserved_quant_ids:
                res[move.id] -= quant.qty
        return res

    def _get_lot_ids(self, cr, uid, ids, field_name, args, context=None):
        res = dict.fromkeys(ids, False)
        for move in self.browse(cr, uid, ids, context=context):
            if move.state == 'done':
                res[move.id] = [q.id for q in move.quant_ids]
            else:
                res[move.id] = [q.id for q in move.reserved_quant_ids]
        return res

    def _get_product_availability(self, cr, uid, ids, field_name, args, context=None):
        quant_obj = self.pool.get('stock.quant')
        res = dict.fromkeys(ids, False)
        for move in self.browse(cr, uid, ids, context=context):
            if move.state == 'done':
                res[move.id] = move.product_qty
            else:
                sublocation_ids = self.pool.get('stock.location').search(cr, uid, [('id', 'child_of', [move.location_id.id])], context=context)
                quant_ids = quant_obj.search(cr, uid, [('location_id', 'in', sublocation_ids), ('product_id', '=', move.product_id.id), ('reservation_id', '=', False)], context=context)
                availability = 0
                for quant in quant_obj.browse(cr, uid, quant_ids, context=context):
                    availability += quant.qty
                res[move.id] = min(move.product_qty, availability)
        return res


    def _get_move(self, cr, uid, ids, context=None):
        res = set()
        for quant in self.browse(cr, uid, ids, context=context):
            if quant.reservation_id:
                res.add(quant.reservation_id.id)
        return list(res)




    _columns = {
        'name': fields.char('Description', required=True, select=True),
        'priority': fields.selection([('0', 'Not urgent'), ('1', 'Urgent')], 'Priority'),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'date': fields.datetime('Date', required=True, select=True, help="Move date: scheduled date until move is done, then date of actual move processing", states={'done': [('readonly', True)]}),
        'date_expected': fields.datetime('Scheduled Date', states={'done': [('readonly', True)]},required=True, select=True, help="Scheduled date for the processing of this move"),
        'product_id': fields.many2one('product.product', 'Product', required=True, select=True, domain=[('type','<>','service')],states={'done': [('readonly', True)]}),
        # TODO: improve store to add dependency on product UoM
        'product_qty': fields.function(_quantity_normalize, type='float', store=True, string='Quantity',
            digits_compute=dp.get_precision('Product Unit of Measure'),
            help='Quantity in the default UoM of the product'),
        'product_uom_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'),
            required=True,states={'done': [('readonly', True)]},
            help="This is the quantity of products from an inventory "
                "point of view. For moves in the state 'done', this is the "
                "quantity of products that were actually moved. For other "
                "moves, this is the quantity of product that is planned to "
                "be moved. Lowering this quantity does not generate a "
                "backorder. Changing this quantity on assigned moves affects "
                "the product reservation, and should be done with care."
        ),
        'product_uom': fields.many2one('product.uom', 'Unit of Measure', required=True,states={'done': [('readonly', True)]}),
        'product_uos_qty': fields.float('Quantity (UOS)', digits_compute=dp.get_precision('Product Unit of Measure'), states={'done': [('readonly', True)]}),
        'product_uos': fields.many2one('product.uom', 'Product UOS', states={'done': [('readonly', True)]}),

        'product_packaging': fields.many2one('product.packaging', 'Prefered Packaging', help="It specifies attributes of packaging like type, quantity of packaging,etc."),

        'location_id': fields.many2one('stock.location', 'Source Location', required=True, select=True,states={'done': [('readonly', True)]}, help="Sets a location if you produce at a fixed location. This can be a partner location if you subcontract the manufacturing operations."),
        'location_dest_id': fields.many2one('stock.location', 'Destination Location', required=True,states={'done': [('readonly', True)]}, select=True, help="Location where the system will stock the finished products."),

        # FP Note: should we remove this?
        'partner_id': fields.many2one('res.partner', 'Destination Address ', states={'done': [('readonly', True)]}, help="Optional address where goods are to be delivered, specifically used for allotment"),


        'move_dest_id': fields.many2one('stock.move', 'Destination Move', help="Optional: next stock move when chaining them", select=True),
        'move_orig_ids': fields.one2many('stock.move', 'move_dest_id', 'Original Move', help="Optional: previous stock move when chaining them", select=True),

        'picking_id': fields.many2one('stock.picking', 'Reference', select=True, states={'done': [('readonly', True)]}),
        'picking_priority': fields.related('picking_id','priority', type='selection', selection=[('0','Low'),('1','Normal'),('2','High')], string='Picking Priority'),
        'note': fields.text('Notes'),
        'state': fields.selection([('draft', 'New'),
                                   ('cancel', 'Cancelled'),
                                   ('waiting', 'Waiting Another Move'),
                                   ('confirmed', 'Waiting Availability'),
                                   ('assigned', 'Available'),
                                   ('done', 'Done'),
                                   ], 'Status', readonly=True, select=True,
                 help= "* New: When the stock move is created and not yet confirmed.\n"\
                       "* Waiting Another Move: This state can be seen when a move is waiting for another one, for example in a chained flow.\n"\
                       "* Waiting Availability: This state is reached when the procurement resolution is not straight forward. It may need the scheduler to run, a component to me manufactured...\n"\
                       "* Available: When products are reserved, it is set to \'Available\'.\n"\
                       "* Done: When the shipment is processed, the state is \'Done\'."),

        'price_unit': fields.float('Unit Price', help="Technical field used to record the product cost set by the user during a picking confirmation (when average price costing method is used). Value given in company currency and in product uom."),  # as it's a technical field, we intentionally don't provide the digits attribute

        'company_id': fields.many2one('res.company', 'Company', required=True, select=True),
        'backorder_id': fields.related('picking_id','backorder_id',type='many2one', relation="stock.picking", string="Back Order of", select=True),
        'origin': fields.char("Source"),
        'procure_method': fields.selection([('make_to_stock','Make to Stock'),('make_to_order','Make to Order')], 'Procurement Method', required=True, help="Make to Stock: When needed, the product is taken from the stock or we wait for replenishment. \nMake to Order: When needed, the product is purchased or produced."),

        # used for colors in tree views:
        'scrapped': fields.related('location_dest_id','scrap_location',type='boolean',relation='stock.location',string='Scrapped', readonly=True),

        'quant_ids': fields.many2many('stock.quant',  'stock_quant_move_rel', 'move_id', 'quant_id', 'Quants'),
        'reserved_quant_ids': fields.one2many('stock.quant', 'reservation_id', 'Reserved quants'),
        'remaining_qty': fields.function(_get_remaining_qty, type='float', string='Remaining Quantity', 
                                         digits_compute=dp.get_precision('Product Unit of Measure'), states={'done': [('readonly', True)]},
                                         store = {'stock.move': (lambda self, cr, uid, ids, c={}: ids , ['product_uom_qty', 'product_uom', 'reserved_quant_ids'], 20), 
                                                  'stock.quant': (_get_move, ['reservation_id'], 10)}),
        'procurement_id': fields.many2one('procurement.order', 'Procurement'),
        'group_id': fields.many2one('procurement.group', 'Procurement Group'),
        'rule_id': fields.many2one('procurement.rule', 'Procurement Rule'),
        'propagate': fields.boolean('Propagate cancel and split', help='If checked, when this move is cancelled, cancel the linked move too'),
        'picking_type_id': fields.many2one('stock.picking.type', 'Picking Type'),
        'inventory_id': fields.many2one('stock.inventory', 'Inventory'),
        'lot_ids': fields.function(_get_lot_ids, type='many2many', relation='stock.quant', string='Lots'),
        'origin_returned_move_id': fields.many2one('stock.move', 'Origin return move', help='move that created the return move'),
        'returned_move_ids': fields.one2many('stock.move', 'origin_returned_move_id', 'All returned moves', help='Optional: all returned moves created from this move'),
        'availability': fields.function(_get_product_availability, type='float', string='Availability'),
        'restrict_lot_id': fields.many2one('stock.production.lot', 'Lot', help="Technical field used to depict a restriction on the lot of quants to consider when marking this move as 'done'"),
        'restrict_partner_id': fields.many2one('res.partner', 'Owner ', help="Technical field used to depict a restriction on the ownership of quants to consider when marking this move as 'done'"),
        'putaway_ids': fields.one2many('stock.move.putaway', 'move_id', 'Put Away Suggestions'), 
        'route_ids': fields.many2many('stock.location.route', 'stock_location_route_move', 'move_id', 'route_id', 'Destination route', help="Preferred route to be followed by the procurement order"),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse', help="Technical field depicting the warehouse to consider for the route selection on the next procurement (if any)."),
    }

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default['move_orig_ids'] = []
        default['quant_ids'] = []
        default['reserved_quant_ids'] = []
        default['returned_move_ids'] = []
        default['origin_returned_move_id'] = False
        default['state'] = 'draft'
        return super(stock_move, self).copy(cr, uid, id, default, context)

    def _default_location_destination(self, cr, uid, context=None):
        context = context or {}
        if context.get('default_picking_type_id', False):
            pick_type = self.pool.get('stock.picking.type').browse(cr, uid, context['default_picking_type_id'], context=context)
            return pick_type.default_location_dest_id and pick_type.default_location_dest_id.id or False
        return False

    def _default_location_source(self, cr, uid, context=None):
        context = context or {}
        if context.get('default_picking_type_id', False):
            pick_type = self.pool.get('stock.picking.type').browse(cr, uid, context['default_picking_type_id'], context=context)
            return pick_type.default_location_src_id and pick_type.default_location_src_id.id or False
        return False

    def _default_destination_address(self, cr, uid, context=None):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        return user.company_id.partner_id.id

    _defaults = {
        'location_id': _default_location_source,
        'location_dest_id': _default_location_destination,
        'partner_id': _default_destination_address,
        'state': 'draft',
        'priority': '1',
        'product_qty': 1.0,
        'product_uom_qty': 1.0,
        'scrapped': False,
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.move', context=c),
        'date_expected': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'procure_method': 'make_to_stock',
        'propagate': True,
    }

    def _prepare_procurement_from_move(self, cr, uid, move, context=None):
        origin = (move.group_id and (move.group_id.name+":") or "") +  (move.rule_id and move.rule_id.name or "/")
        return  {
            'name': move.rule_id and move.rule_id.name or "/",
            'origin': origin,
            'company_id': move.company_id and move.company_id.id or False,
            'date_planned': move.date,
            'product_id': move.product_id.id,
            'product_qty': move.product_qty,
            'product_uom': move.product_uom.id,
            'product_uos_qty': (move.product_uos and move.product_uos_qty) or move.product_qty,
            'product_uos': (move.product_uos and move.product_uos.id) or move.product_uom.id,
            'location_id': move.location_id.id,
            'move_dest_id': move.id,
            'group_id': move.group_id and move.group_id.id or False,
            'route_ids' : [(4, x.id) for x in move.route_ids],
            'warehouse_id': move.warehouse_id and move.warehouse_id.id or False,
        }

    def _push_apply(self, cr, uid, moves, context):
        push_obj = self.pool.get("stock.location.path")
        for move in moves:
            if not move.move_dest_id:
                routes = [x.id for x in move.product_id.route_ids + move.product_id.categ_id.total_route_ids]
                routes = routes or [x.id for x in move.route_ids]  
                if routes:
                    domain = [('route_id', 'in', routes), ('location_from_id', '=', move.location_dest_id.id)]
                    if move.warehouse_id:
                        domain += [('warehouse_id', '=', move.warehouse_id.id)]
                    rules = push_obj.search(cr, uid, domain, context=context)
                    if rules:
                        rule = push_obj.browse(cr, uid, rules[0], context=context)
                        push_obj._apply(cr, uid, rule, move, context=context)
        return True

    # Create the stock.move.putaway records
    def _putaway_apply(self,cr, uid, ids, context=None):
        moveputaway_obj = self.pool.get('stock.move.putaway')
        for move in self.browse(cr, uid, ids, context=context):
            putaway = self.pool.get('stock.location').get_putaway_strategy(cr, uid, move.location_dest_id, move.product_id, context=context)
            if putaway:
                # Should call different methods here in later versions
                # TODO: take care of lots
                if putaway.method == 'fixed' and putaway.location_spec_id:
                    moveputaway_obj.create(cr, SUPERUSER_ID, {'move_id': move.id,
                                                     'location_id': putaway.location_spec_id.id,
                                                     'quantity': move.product_uom_qty}, context=context)
        return True
    
    def _create_procurement(self, cr, uid, move, context=None):
        """
            This will create a procurement order
        """
        proc_obj = self.pool.get("procurement.order")
        return proc_obj.create(cr, uid, self._prepare_procurement_from_move(cr, uid, move, context=context))

    # Check that we do not modify a stock.move which is done
    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        frozen_fields = set(['product_qty', 'product_uom', 'product_uos_qty', 'product_uos', 'location_id', 'location_dest_id', 'product_id'])
        for move in self.browse(cr, uid, ids, context=context):
            if move.state == 'done':
                if frozen_fields.intersection(vals):
                    raise osv.except_osv(_('Operation Forbidden!'),
                        _('Quantities, Units of Measure, Products and Locations cannot be modified on stock moves that have already been processed (except by the Administrator).'))
        result = super(stock_move, self).write(cr, uid, ids, vals, context=context)
        return result

    def onchange_quantity(self, cr, uid, ids, product_id, product_qty,
                          product_uom, product_uos):
        """ On change of product quantity finds UoM and UoS quantities
        @param product_id: Product id
        @param product_qty: Changed Quantity of product
        @param product_uom: Unit of measure of product
        @param product_uos: Unit of sale of product
        @return: Dictionary of values
        """
        result = {
            'product_uos_qty': 0.00
        }
        warning = {}

        if (not product_id) or (product_qty <=0.0):
            result['product_qty'] = 0.0
            return {'value': result}

        product_obj = self.pool.get('product.product')
        uos_coeff = product_obj.read(cr, uid, product_id, ['uos_coeff'])

        # Warn if the quantity was decreased
        if ids:
            for move in self.read(cr, uid, ids, ['product_qty']):
                if product_qty < move['product_qty']:
                    warning.update({
                       'title': _('Information'),
                       'message': _("By changing this quantity here, you accept the "
                                "new quantity as complete: OpenERP will not "
                                "automatically generate a back order.") })
                break

        if product_uos and product_uom and (product_uom != product_uos):
            result['product_uos_qty'] = product_qty * uos_coeff['uos_coeff']
        else:
            result['product_uos_qty'] = product_qty

        return {'value': result, 'warning': warning}

    def onchange_uos_quantity(self, cr, uid, ids, product_id, product_uos_qty,
                          product_uos, product_uom):
        """ On change of product quantity finds UoM and UoS quantities
        @param product_id: Product id
        @param product_uos_qty: Changed UoS Quantity of product
        @param product_uom: Unit of measure of product
        @param product_uos: Unit of sale of product
        @return: Dictionary of values
        """
        result = {
            'product_uom_qty': 0.00
        }
        warning = {}

        if (not product_id) or (product_uos_qty <=0.0):
            result['product_uos_qty'] = 0.0
            return {'value': result}

        product_obj = self.pool.get('product.product')
        uos_coeff = product_obj.read(cr, uid, product_id, ['uos_coeff'])

        # Warn if the quantity was decreased
        for move in self.read(cr, uid, ids, ['product_uos_qty']):
            if product_uos_qty < move['product_uos_qty']:
                warning.update({
                   'title': _('Warning: No Back Order'),
                   'message': _("By changing the quantity here, you accept the "
                                "new quantity as complete: OpenERP will not "
                                "automatically generate a Back Order.") })
                break

        if product_uos and product_uom and (product_uom != product_uos):
            result['product_uom_qty'] = product_uos_qty / uos_coeff['uos_coeff']
        else:
            result['product_uom_qty'] = product_uos_qty
        return {'value': result, 'warning': warning}

    def onchange_product_id(self, cr, uid, ids, prod_id=False, loc_id=False,
                            loc_dest_id=False, partner_id=False):
        """ On change of product id, if finds UoM, UoS, quantity and UoS quantity.
        @param prod_id: Changed Product id
        @param loc_id: Source location id
        @param loc_dest_id: Destination location id
        @param partner_id: Address id of partner
        @return: Dictionary of values
        """
        if not prod_id:
            return {}
        user = self.pool.get('res.users').browse(cr, uid, uid)
        lang = user and user.lang or False
        if partner_id:
            addr_rec = self.pool.get('res.partner').browse(cr, uid, partner_id)
            if addr_rec:
                lang = addr_rec and addr_rec.lang or False
        ctx = {'lang': lang}

        product = self.pool.get('product.product').browse(cr, uid, [prod_id], context=ctx)[0]
        uos_id  = product.uos_id and product.uos_id.id or False
        result = {
            'product_uom': product.uom_id.id,
            'product_uos': uos_id,
            'product_uom_qty': 1.00,
            'product_uos_qty' : self.pool.get('stock.move').onchange_quantity(cr, uid, ids, prod_id, 1.00, product.uom_id.id, uos_id)['value']['product_uos_qty'],
        }
        if not ids:
            result['name'] = product.partner_ref
        if loc_id:
            result['location_id'] = loc_id
        if loc_dest_id:
            result['location_dest_id'] = loc_dest_id
        return {'value': result}

    def _picking_assign(self, cr, uid, move, context=None):
        if move.picking_id or not move.picking_type_id:
            return False
        context = context or {}
        pick_obj = self.pool.get("stock.picking")
        picks = []
        group = move.group_id and move.group_id.id or False
        picks = pick_obj.search(cr, uid, [
                ('group_id', '=', group),
                ('location_id', '=', move.location_id.id),
                ('location_dest_id', '=', move.location_dest_id.id),
                ('state', 'in', ['draft', 'confirmed', 'waiting'])], context=context)
        if picks:
            pick = picks[0]
        else:
            values = {
                'origin': move.origin,
                'company_id': move.company_id and move.company_id.id or False,
                'move_type': move.group_id and move.group_id.move_type or 'one',
                'partner_id': move.group_id and move.group_id.partner_id and move.group_id.partner_id.id or False,
                'date_done': move.date_expected,
                'picking_type_id': move.picking_type_id and move.picking_type_id.id or False,
            }
            pick = pick_obj.create(cr, uid, values, context=context)
        move.write({'picking_id': pick})
        return True

    def onchange_date(self, cr, uid, ids, date, date_expected, context=None):
        """ On change of Scheduled Date gives a Move date.
        @param date_expected: Scheduled Date
        @param date: Move Date
        @return: Move Date
        """
        if not date_expected:
            date_expected = time.strftime('%Y-%m-%d %H:%M:%S')
        return {'value':{'date': date_expected}}

    def action_confirm(self, cr, uid, ids, context=None):
        """ Confirms stock move or put it in waiting if it's linked to another move.
        @return: List of ids.
        """
        states = {
            'confirmed': [],
            'waiting': []
        }
        for move in self.browse(cr, uid, ids, context=context):
            state = 'confirmed'
            for m in move.move_orig_ids:
                if m.state not in ('done', 'cancel'):
                    state = 'waiting'
            states[state].append(move.id)
            self._picking_assign(cr, uid, move, context=context)

        for state, write_ids in states.items():
            if len(write_ids):
                self.write(cr, uid, write_ids, {'state': state})
                if state == 'confirmed':
                    for move in self.browse(cr, uid, write_ids, context=context):
                        if move.procure_method == 'make_to_order':
                            self._create_procurement(cr, uid, move, context=context)
        moves = self.browse(cr, uid, ids, context=context)
        self._push_apply(cr, uid, moves, context=context)
        return True

    def force_assign(self, cr, uid, ids, context=None):
        """ Changes the state to assigned.
        @return: True
        """
        done = self.action_assign(cr, uid, ids, context=context)
        self.write(cr, uid, list(set(ids) - set(done)), {'state': 'assigned'})
        return True


    def cancel_assign(self, cr, uid, ids, context=None):
        """ Changes the state to confirmed.
        @return: True
        """
        return self.write(cr, uid, ids, {'state': 'confirmed'})

    def action_assign(self, cr, uid, ids, context=None):
        """ Checks the product type and accordingly writes the state.
        @return: No. of moves done
        """
        context = context or {}
        quant_obj = self.pool.get("stock.quant")
        done = []
        for move in self.browse(cr, uid, ids, context=context):
            if move.state not in ('confirmed', 'waiting'):
                continue
            if move.product_id.type == 'consu':
                done.append(move.id)
                continue
            else:
                qty = move.product_qty
                dp = []
                for m2 in move.move_orig_ids:
                    for q in m2.quant_ids:
                        dp.append(str(q.id))
                        qty -= q.qty
                domain = ['|', ('reservation_id', '=', False), ('reservation_id', '=', move.id), ('qty', '>', 0)]
                prefered_domain = dp and [('id', 'not in', dp)] or []
                fallback_domain = dp and [('id', 'in', dp)] or []
                quants = quant_obj.quants_get_prefered_domain(cr, uid, move.location_id, move.product_id, qty, domain=domain, prefered_domain=prefered_domain, fallback_domain=fallback_domain, restrict_lot_id=move.restrict_lot_id.id, restrict_partner_id=move.restrict_partner_id.id, context=context)
                #Will only reserve physical quants, no negative
                quant_obj.quants_reserve(cr, uid, quants, move, context=context)
                # the total quantity is provided by existing quants
                if all(map(lambda x:x[0], quants)):
                    done.append(move.id)
        self.write(cr, uid, done, {'state': 'assigned'})
        self._putaway_apply(cr, uid, ids, context=context)        
        return done


    #
    # Cancel move => cancel others move and pickings
    #
    def action_cancel(self, cr, uid, ids, context=None):
        """ Cancels the moves and if all moves are cancelled it cancels the picking.
        @return: True
        """
        procurement_obj = self.pool.get('procurement.order')
        context = context or {}
        for move in self.browse(cr, uid, ids, context=context):
            if move.state == 'done':
                raise osv.except_osv(_('Operation Forbidden!'),
                        _('You cannot cancel a stock move that has been set to \'Done\'.'))
            if move.reserved_quant_ids:
                self.pool.get("stock.quant").quants_unreserve(cr, uid, move, context=context)
            if context.get('cancel_procurement'):
                if move.propagate:
                    procurement_ids = procurement_obj.search(cr, uid, [('move_dest_id', '=', move.id)], context=context)
                    procurement_obj.cancel(cr, uid, procurement_ids, context=context)
            elif move.move_dest_id:
                #cancel chained moves
                if move.propagate:
                    self.action_cancel(cr, uid, [move.move_dest_id.id], context=context)
                elif move.move_dest_id.state == 'waiting':
                    self.write(cr, uid, [move.move_dest_id.id], {'state': 'confirmed'})
        return self.write(cr, uid, ids, {'state': 'cancel', 'move_dest_id': False})

    #def _get_quants_from_pack(self, cr, uid, ids, context=None):
    #    """
    #    Suppose for the moment we don't have any packaging
    #    """
    #    res = {}
    #    for move in self.browse(cr, uid, ids, context=context):
    #        #Split according to pack wizard if necessary
    #        res[move.id] = [x.id for x in move.reserved_quant_ids]
    #    return res

    def action_done(self, cr, uid, ids, negatives = False, context=None):
        """ Makes the move done and if all moves are done, it will finish the picking.
        If quants are not assigned yet, it should assign them
        Putaway strategies should be applied
        @return:
        """
        context = context or {}
        quant_obj = self.pool.get("stock.quant")
        ops_obj = self.pool.get("stock.pack.operation")
        pack_obj = self.pool.get("stock.quant.package")
        todo = [move.id for move in self.browse(cr, uid, ids, context=context) if move.state == "draft"]
        if todo:
            self.action_confirm(cr, uid, todo, context=context)

        pickings = set()
        procurement_ids = []
        for move in self.browse(cr, uid, ids, context=context):
#             if negatives and negatives[move.id]:
#                 for ops in negatives[move.id].keys():
#                 quants_to_move = [(None, negatives[move.id, x) for x in negatives]
#                 quant_obj.quants_move(cr, uid, quants_to_move, move, context=context)

            if move.picking_id:
                pickings.add(move.picking_id.id)
            qty = move.product_qty

            # for qty, location_id in move_id.prefered_location_ids:
            #    quants = quant_obj.quants_get(cr, uid, move.location_id, move.product_id, qty, context=context)
            #    quant_obj.quants_move(cr, uid, quants, move, location_dest_id, context=context)
            # should replace the above 2 lines
            dom = [('qty', '>', 0)]
            prefered_domain = [('reservation_id', '=', move.id)]
            fallback_domain = [('reservation_id', '=', False)]
            if move.picking_id and move.picking_id.pack_operation_ids:
                quants = quant_obj.quants_get_prefered_domain(cr, uid, move.location_id, move.product_id, qty - move.remaining_qty, domain=dom, prefered_domain=prefered_domain, fallback_domain=fallback_domain, context=context)
                quant_obj.quants_move(cr, uid, quants, move, context=context)
                if negatives and move.id in negatives:
                    for negative_op in negatives[move.id].keys():
                        ops = ops_obj.browse(cr, uid, negative_op, context=context)
                        negatives[move.id][negative_op] = quant_obj.quants_move(cr, uid, [(None, negatives[move.id][negative_op])], move, 
                                                                                lot_id = ops.lot_id and ops.lot_id.id or False, 
                                                                                owner_id = ops.owner_id and ops.owner_id.id or False, 
                                                                                package_id = ops.package_id and ops.package_id.id or False, context=context)
                #Packing:
                reserved_ops = list(set([x.reservation_op_id.id for x in move.reserved_quant_ids]))
                for ops in ops_obj.browse(cr, uid, reserved_ops, context=context):
                    if ops.product_id:
                        quant_obj.write(cr, uid, [x.id for x in ops.reserved_quant_ids], {'package_id': ops.result_package_id and ops.result_package_id.id or False}, context=context)
                    else:
                        pack_obj.write(cr, uid, [ops.package_id.id], {'parent_id': ops.result_package_id and ops.result_package_id.id or False}, context=context)
            else:
                quants = quant_obj.quants_get_prefered_domain(cr, uid, move.location_id, move.product_id, qty, domain=dom, prefered_domain=prefered_domain, fallback_domain=fallback_domain, context=context)
                #Will move all quants_get and as such create negative quants
                quant_obj.quants_move(cr, uid, quants, move, context=context)
            quant_obj.quants_unreserve(cr, uid, move, context=context)

            #Check moves that were pushed
            if move.move_dest_id.state in ('waiting', 'confirmed'):
                other_upstream_move_ids = self.search(cr, uid, [('id', '!=', move.id), ('state', 'not in', ['done', 'cancel']),
                                            ('move_dest_id', '=', move.move_dest_id.id)], context=context)
                #If no other moves for the move that got pushed:
                if not other_upstream_move_ids and move.move_dest_id.state in ('waiting', 'confirmed'):
                    self.action_assign(cr, uid, [move.move_dest_id.id], context=context)
            if move.procurement_id:
                procurement_ids.append(move.procurement_id.id)
        self.write(cr, uid, ids, {'state': 'done', 'date': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)}, context=context)
        self.pool.get('procurement.order').check(cr, uid, procurement_ids, context=context)
        return True

    def unlink(self, cr, uid, ids, context=None):
        context = context or {}
        for move in self.browse(cr, uid, ids, context=context):
            if move.state not in ('draft', 'cancel'):
                raise osv.except_osv(_('User Error!'), _('You can only delete draft moves.'))
        return super(stock_move, self).unlink(cr, uid, ids, context=context)

    def action_scrap(self, cr, uid, ids, quantity, location_id, context=None):
        """ Move the scrap/damaged product into scrap location
        @param cr: the database cursor
        @param uid: the user id
        @param ids: ids of stock move object to be scrapped
        @param quantity : specify scrap qty
        @param location_id : specify scrap location
        @param context: context arguments
        @return: Scraped lines
        """
        #quantity should in MOVE UOM
        if quantity <= 0:
            raise osv.except_osv(_('Warning!'), _('Please provide a positive quantity to scrap.'))
        res = []
        for move in self.browse(cr, uid, ids, context=context):
            source_location = move.location_id
            if move.state == 'done':
                source_location = move.location_dest_id
            #Previously used to prevent scraping from virtual location but not necessary anymore
            #if source_location.usage != 'internal':
                #restrict to scrap from a virtual location because it's meaningless and it may introduce errors in stock ('creating' new products from nowhere)
                #raise osv.except_osv(_('Error!'), _('Forbidden operation: it is not allowed to scrap products from a virtual location.'))
            move_qty = move.product_qty
            uos_qty = quantity / move_qty * move.product_uos_qty
            default_val = {
                'location_id': source_location.id,
                'product_uom_qty': quantity,
                'product_uos_qty': uos_qty,
                'state': move.state,
                'scrapped': True,
                'location_dest_id': location_id,
                #TODO lot_id is now on quant and not on move, need to do something for this
                #'lot_id': move.lot_id.id,
            }
            new_move = self.copy(cr, uid, move.id, default_val)

            res += [new_move]
            product_obj = self.pool.get('product.product')
            for product in product_obj.browse(cr, uid, [move.product_id.id], context=context):
                if move.picking_id:
                    uom = product.uom_id.name if product.uom_id else ''
                    message = _("%s %s %s has been <b>moved to</b> scrap.") % (quantity, uom, product.name)
                    move.picking_id.message_post(body=message)

        self.action_done(cr, uid, res, context=context)
        return res

    def action_consume(self, cr, uid, ids, quantity, location_id=False, context=None):
        """ Consumed product with specific quatity from specific source location
        @param cr: the database cursor
        @param uid: the user id
        @param ids: ids of stock move object to be consumed
        @param quantity : specify consume quantity
        @param location_id : specify source location
        @param context: context arguments
        @return: Consumed lines
        """
        #quantity should in MOVE UOM
        if context is None:
            context = {}
        if quantity <= 0:
            raise osv.except_osv(_('Warning!'), _('Please provide proper quantity.'))
        res = []
        for move in self.browse(cr, uid, ids, context=context):
            move_qty = move.product_qty
            if move_qty <= 0:
                raise osv.except_osv(_('Error!'), _('Cannot consume a move with negative or zero quantity.'))
            quantity_rest = move.product_qty
            quantity_rest -= quantity
            uos_qty_rest = quantity_rest / move_qty * move.product_uos_qty
            if quantity_rest <= 0:
                quantity_rest = 0
                uos_qty_rest = 0
                quantity = move.product_qty

            uos_qty = quantity / move_qty * move.product_uos_qty
            if quantity_rest > 0:
                default_val = {
                    'product_uom_qty': quantity,
                    'product_uos_qty': uos_qty,
                    'state': move.state,
                    'location_id': location_id or move.location_id.id,
                }
                current_move = self.copy(cr, uid, move.id, default_val)
                res += [current_move]
                update_val = {}
                update_val['product_uom_qty'] = quantity_rest
                update_val['product_uos_qty'] = uos_qty_rest
                self.write(cr, uid, [move.id], update_val)

            else:
                quantity_rest = quantity
                uos_qty_rest =  uos_qty
                res += [move.id]
                update_val = {
                        'product_uom_qty' : quantity_rest,
                        'product_uos_qty' : uos_qty_rest,
                        'location_id': location_id or move.location_id.id,
                }
                self.write(cr, uid, [move.id], update_val)

        self.action_done(cr, uid, res, context=context)
        return res



    def split(self, cr, uid, move, qty, context=None):
        """ 
            Splits qty from move move into a new move
        """
        if move.product_qty==qty:
            return move.id
        if (move.product_qty < qty) or (qty==0):
            return False

        uom_obj = self.pool.get('product.uom')
        context = context or {}

        uom_qty = uom_obj._compute_qty(cr, uid, move.product_id.uom_id.id, qty, move.product_uom.id)
        uos_qty = uom_qty * move.product_uos_qty / move.product_uom_qty

        if move.state in ('done', 'cancel'):
            raise osv.except_osv(_('Error'), _('You cannot split a move done'))

        defaults = {
            'product_uom_qty': uom_qty,
            'product_uos_qty': uos_qty,
            'state': move.state,
            'move_dest_id': False,
            'reserved_quant_ids': []
        }
        new_move = self.copy(cr, uid, move.id, defaults)

        self.write(cr, uid, [move.id], {
            'product_uom_qty': move.product_uom_qty - uom_qty,
            'product_uos_qty': move.product_uos_qty - uos_qty,
#             'reserved_quant_ids': [(6,0,[])]  SHOULD NOT CHANGE as it has been reserved already
        }, context=context)
        
        if move.move_dest_id and move.propagate:
            new_move_prop = self.split(cr, uid, move.move_dest_id, qty, context=context)
            self.write(cr, uid, [new_move], {'move_dest_id': new_move_prop}, context=context)
            
        self.action_confirm(cr, uid, [new_move], context=context)
        return new_move

class stock_inventory(osv.osv):
    _name = "stock.inventory"
    _description = "Inventory"

    def _get_move_ids_exist(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for inv in self.browse(cr, uid, ids, context=context):
            res[inv.id] = False
            if inv.move_ids:
                res[inv.id] = True
        return res

    _columns = {
        'name': fields.char('Inventory Reference', size=64, required=True, readonly=True, states={'draft': [('readonly', False)]}, help="Inventory Name."),
        'date': fields.datetime('Inventory Date', required=True, readonly=True, states={'draft': [('readonly', False)]}, help="Inventory Create Date."),
        'date_done': fields.datetime('Date done', help="Inventory Validation Date."),
        'line_ids': fields.one2many('stock.inventory.line', 'inventory_id', 'Inventories', readonly=False, states={'done': [('readonly', True)]}, help="Inventory Lines."),
        'move_ids': fields.one2many('stock.move', 'inventory_id', 'Created Moves', help="Inventory Moves."),
        'state': fields.selection([('draft', 'Draft'), ('cancel', 'Cancelled'), ('confirm', 'In Progress'), ('done', 'Validated')], 'Status', readonly=True, select=True),
        'company_id': fields.many2one('res.company', 'Company', required=True, select=True, readonly=True, states={'draft': [('readonly', False)]}),
        'location_id': fields.many2one('stock.location', 'Location', required=True),
        'product_id': fields.many2one('product.product', 'Product', readonly=True, states={'draft': [('readonly', False)]}, help="Specify Product to focus your inventory on a particular Product."),
        'package_id': fields.many2one('stock.quant.package', 'Pack', readonly=True, states={'draft': [('readonly', False)]}, help="Specify Pack to focus your inventory on a particular Pack."),
        'partner_id': fields.many2one('res.partner', 'Owner', readonly=True, states={'draft': [('readonly', False)]}, help="Specify Owner to focus your inventory on a particular Owner."),
        'lot_id': fields.many2one('stock.production.lot', 'Lot/Serial Number', readonly=True, states={'draft': [('readonly', False)]}, help="Specify Lot/Serial Number to focus your inventory on a particular Lot/Serial Number."),
        'move_ids_exist': fields.function(_get_move_ids_exist, type='boolean', string=' Stock Move Exists?', help='technical field for attrs in view'),
        'filter': fields.selection([('product', 'Product'), ('owner', 'Owner'), ('product_owner','Product & Owner'), ('lot','Lot/Serial Number'), ('pack','Pack'), ('none', 'None')], 'Selection Filter'),
    }

    def _default_stock_location(self, cr, uid, context=None):
        try:
            warehouse = self.pool.get('ir.model.data').get_object(cr, uid, 'stock', 'warehouse0')            
            return warehouse.lot_stock_id.id
        except:
            return False

    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'state': 'draft',
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.inventory', context=c),
        'location_id': _default_stock_location,
    }

    def set_checked_qty(self , cr ,uid ,ids ,context=None):
        inventory = self.browse(cr, uid, ids[0], context=context)
        line_ids = [line.id for line in inventory.line_ids]
        self.pool.get('stock.inventory.line').write(cr, uid, line_ids, {'product_qty': 0})
        return True

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}
        default = default.copy()
        default.update({'move_ids': [], 'date_done': False})
        return super(stock_inventory, self).copy(cr, uid, id, default, context=context)

    def _inventory_line_hook(self, cr, uid, inventory_line, move_vals):
        """ Creates a stock move from an inventory line
        @param inventory_line:
        @param move_vals:
        @return:
        """
        return self.pool.get('stock.move').create(cr, uid, move_vals)

    def action_done(self, cr, uid, ids, context=None):
        """ Finish the inventory
        @return: True
        """
        if context is None:
            context = {}
        move_obj = self.pool.get('stock.move')
        for inv in self.browse(cr, uid, ids, context=context):
            if not inv.move_ids:
                self.action_check(cr, uid, [inv.id], context=context)
            inv.refresh()
            #the action_done on stock_move has to be done in 2 steps:
            #first, we start moving the products from stock to inventory loss
            move_obj.action_done(cr, uid, [x.id for x in inv.move_ids if x.location_id.usage == 'internal'], context=context)
            #then, we move from inventory loss. This 2 steps process is needed because some moved quant may need to be put again in stock
            move_obj.action_done(cr, uid, [x.id for x in inv.move_ids if x.location_id.usage != 'internal'], context=context)
            self.write(cr, uid, [inv.id], {'state': 'done', 'date_done': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
        return True

    def _create_stock_move(self, cr, uid, inventory, todo_line, context=None):
        stock_move_obj = self.pool.get('stock.move')
        product_obj = self.pool.get('product.product')
        inventory_location_id = product_obj.browse(cr, uid, todo_line['product_id'], context=context).property_stock_inventory.id
        vals = {
            'name': _('INV:') + (inventory.name or ''),
            'product_id': todo_line['product_id'],
            'product_uom': todo_line['product_uom_id'],
            'date': inventory.date,
            'company_id': inventory.company_id.id,
            'inventory_id': inventory.id,
            'state': 'assigned',
            'restrict_lot_id': todo_line.get('prod_lot_id'),
            'restrict_partner_id': todo_line.get('partner_id'),
         }

        if todo_line['product_qty'] < 0:
            #found more than expected
            vals['location_id'] = inventory_location_id
            vals['location_dest_id'] = todo_line['location_id']
            vals['product_uom_qty'] = -todo_line['product_qty']
        else:
            #found less than expected
            vals['location_id'] = todo_line['location_id']
            vals['location_dest_id'] = inventory_location_id
            vals['product_uom_qty'] = todo_line['product_qty']
        return stock_move_obj.create(cr, uid, vals, context=context)

    def action_check(self, cr, uid, ids, context=None):
        """ Checks the inventory and computes the stock move to do
        @return: True
        """
        inventory_line_obj = self.pool.get('stock.inventory.line')
        stock_move_obj = self.pool.get('stock.move')
        for inventory in self.browse(cr, uid, ids, context=context):
            #first remove the existing stock moves linked to this inventory
            move_ids = [move.id for move in inventory.move_ids]
            stock_move_obj.unlink(cr, uid, move_ids, context=context)
            #compute what should be in the inventory lines
            theorical_lines = self._get_inventory_lines(cr, uid, inventory, context=context)
            for line in inventory.line_ids:
                #compare the inventory lines to the theorical ones and store the diff in theorical_lines
                inventory_line_obj._resolve_inventory_line(cr, uid, line, theorical_lines, context=context)
            #each theorical_lines where product_qty is not 0 is a difference for which we need to create a stock move
            for todo_line in theorical_lines:
                if todo_line['product_qty'] != 0:
                    self._create_stock_move(cr, uid, inventory, todo_line, context=context)

    def action_cancel_draft(self, cr, uid, ids, context=None):
        """ Cancels the stock move and change inventory state to draft.
        @return: True
        """
        for inv in self.browse(cr, uid, ids, context=context):
            self.pool.get('stock.move').action_cancel(cr, uid, [x.id for x in inv.move_ids], context=context)
            self.write(cr, uid, [inv.id], {'state': 'draft'}, context=context)
        return True

    def action_cancel_inventory(self, cr, uid, ids, context=None):
        #TODO test
        self.action_cancel_draft(cr, uid, ids, context=context)

    def prepare_inventory(self, cr, uid, ids, context=None):
        inventory_line_obj = self.pool.get('stock.inventory.line')
        for inventory in self.browse(cr, uid, ids, context=context):
            #clean the existing inventory lines before redoing an inventory proposal
            line_ids = [line.id for line in inventory.line_ids]
            inventory_line_obj.unlink(cr, uid, line_ids, context=context)
            #compute the inventory lines and create them
            vals = self._get_inventory_lines(cr, uid, inventory, context=context)
            for product_line in vals:
                inventory_line_obj.create(cr, uid, product_line, context=context)
        return self.write(cr, uid, ids, {'state': 'confirm'})

    def _get_inventory_lines(self, cr, uid, inventory, context=None):
        location_obj = self.pool.get('stock.location')
        product_obj = self.pool.get('product.product')
        location_ids = location_obj.search(cr, uid, [('id', 'child_of', [inventory.location_id.id])], context=context)
        domain = ' location_id in %s'
        args = (tuple(location_ids),)
        if inventory.partner_id:
            domain += ' and owner_id = %s'
            args += (inventory.partner_id.id,)
        if inventory.lot_id:
            domain += ' and lot_id = %s'
            args += (inventory.lot_id.id,)
        if inventory.product_id:
            domain += 'and product_id = %s'
            args += (inventory.product_id.id,)
        if inventory.package_id:
            domain += ' and package_id = %s'
            args += (inventory.package_id.id,)
        cr.execute('''
           SELECT product_id, sum(qty) as product_qty, location_id, lot_id as prod_lot_id, package_id, owner_id as partner_id
           FROM stock_quant WHERE''' + domain + '''
           GROUP BY product_id, location_id, lot_id, package_id, partner_id
        ''', args)
        vals = []
        for product_line in cr.dictfetchall():
            #replace the None the dictionary by False, because falsy values are tested later on
            for key, value in product_line.items():
                if value == None:
                    product_line[key] = False
            product_line['inventory_id'] = inventory.id
            product_line['th_qty'] = product_line['product_qty']
            if product_line['product_id']:
                product_line['product_uom_id'] = product_obj.browse(cr, uid, product_line['product_id'], context=context).uom_id.id
            vals.append(product_line)
        return vals

class stock_inventory_line(osv.osv):
    _name = "stock.inventory.line"
    _description = "Inventory Line"
    _rec_name = "inventory_id"
    _columns = {
        'inventory_id': fields.many2one('stock.inventory', 'Inventory', ondelete='cascade', select=True),
        'location_id': fields.many2one('stock.location', 'Location', required=True, select=True),
        'product_id': fields.many2one('product.product', 'Product', required=True, select=True),
        'package_id': fields.many2one('stock.quant.package', 'Pack', select=True),
        'product_uom_id': fields.many2one('product.uom', 'Product Unit of Measure', required=True),
        'product_qty': fields.float('Checked Quantity', digits_compute=dp.get_precision('Product Unit of Measure')),
        'company_id': fields.related('inventory_id', 'company_id', type='many2one', relation='res.company', string='Company', store=True, select=True, readonly=True),
        'prod_lot_id': fields.many2one('stock.production.lot', 'Serial Number', domain="[('product_id','=',product_id)]"),
        'state': fields.related('inventory_id', 'state', type='char', string='Status', readonly=True),
        'th_qty': fields.float('Theoretical Quantity', readonly=True),
        'partner_id': fields.many2one('res.partner', 'Owner'),
    }

    _defaults = {
        'product_qty': 1,
    }

    def _resolve_inventory_line(self, cr, uid, inventory_line, theorical_lines, context=None):
        #TODO : package_id management !
        found = False
        uom_obj = self.pool.get('product.uom')
        for th_line in theorical_lines:
            #We try to match the inventory line with a theorical line with same product, lot, location and owner
            if th_line['location_id'] == inventory_line.location_id.id and th_line['product_id'] == inventory_line.product_id.id and th_line['prod_lot_id'] == inventory_line.prod_lot_id.id and th_line['partner_id'] == inventory_line.partner_id.id:
                uom_reference = inventory_line.product_id.uom_id
                real_qty = uom_obj._compute_qty_obj(cr, uid, inventory_line.product_uom_id, inventory_line.product_qty, uom_reference)
                th_line['product_qty'] -= real_qty
                found = True
                break
        #if it was still not found, we add it to the theorical lines so that it will create a stock move for it
        if not found:
            vals = {
                'inventory_id': inventory_line.inventory_id.id,
                'location_id': inventory_line.location_id.id,
                'product_id': inventory_line.product_id.id,
                'product_uom_id': inventory_line.product_id.uom_id.id,
                'product_qty': -inventory_line.product_qty,
                'prod_lot_id': inventory_line.prod_lot_id.id,
                'partner_id': inventory_line.partner_id.id,
            }
            theorical_lines.append(vals)

    def on_change_product_id(self, cr, uid, ids, location_id, product, uom=False, owner_id=False, lot_id=False, package_id=False, context=None):
        """ Changes UoM and name if product_id changes.
        @param location_id: Location id
        @param product: Changed product_id
        @param uom: UoM product
        @return:  Dictionary of changed values
        """
        context = context or {}
        if not product:
            return {'value': {'product_qty': 0.0, 'product_uom_id': False}}
        uom_obj = self.pool.get('product.uom')
        ctx=context.copy()
        ctx['location'] = location_id
        ctx['lot_id'] = lot_id
        ctx['owner_id'] = owner_id
        ctx['package_id'] = package_id
        obj_product = self.pool.get('product.product').browse(cr, uid, product, context=ctx)
        th_qty = obj_product.qty_available
        if uom and uom != obj_product.uom_id.id:
            uom_record = uom_obj.browse(cr, uid, uom, context=context)
            th_qty = uom_obj._compute_qty_obj(cr, uid, obj_product.uom_id, th_qty, uom_record)
        return {'value': {'th_qty': th_qty, 'product_uom_id': uom or obj_product.uom_id.id}}


#----------------------------------------------------------
# Stock Warehouse
#----------------------------------------------------------
class stock_warehouse(osv.osv):
    _name = "stock.warehouse"
    _description = "Warehouse"
    
    
    def show_field_default_wh_resupply(self,cr,uid,ids,name,args,context=None):
        res = {}
        for wh in self.browse(cr,uid,ids,context=context):            
            res[wh.id] = (len(wh.resupply_wh_ids) > 0)
        return res
    
    def init_filtre_default_resupply_wh_id(self,cr,uid,ids,name,args,context=None):
        res = {}        
        for wh in self.browse(cr,uid,ids,context=context):            
            wh_res = []
            for resupply_id in wh.resupply_wh_ids:
                wh_res += [resupply_id.id]            
            res[wh.id] = [wh_res]
        return res
    
    _columns = {
        'name': fields.char('Name', size=128, required=True, select=True),
        'company_id': fields.many2one('res.company', 'Company', required=True, select=True),
        'partner_id': fields.many2one('res.partner', 'Address'),
        'view_location_id': fields.many2one('stock.location', 'View Location', required=True, domain=[('usage', '=', 'view')]),
        'lot_stock_id': fields.many2one('stock.location', 'Location Stock', required=True, domain=[('usage', '=', 'internal')]),
        'code': fields.char('Short Name', size=5, required=True, help="Short name used to identify your warehouse"),
        'route_ids': fields.many2many('stock.location.route', 'stock_route_warehouse', 'warehouse_id', 'route_id', 'Routes', domain="[('warehouse_selectable', '=', True)]", help='Defaults routes through the warehouse'),
        'reception_steps': fields.selection([
            ('one_step', 'Receive goods directly in stock (1 step)'),
            ('two_steps', 'Unload in input location then go to stock (2 steps)'),
            ('three_steps', 'Unload in input location, go through a quality control before being admitted in stock (3 steps)')], 'Incoming Shipments', required=True),
        'delivery_steps': fields.selection([
            ('ship_only', 'Ship directly from stock (Ship only)'),
            ('pick_ship', 'Bring goods to output location before shipping (Pick + Ship)'),
            ('pick_pack_ship', 'Make packages into a dedicated location, then bring them to the output location for shipping (Pick + Pack + Ship)')], 'Outgoing Shippings', required=True),
        'wh_input_stock_loc_id': fields.many2one('stock.location', 'Input Location'),
        'wh_qc_stock_loc_id': fields.many2one('stock.location', 'Quality Control Location'),
        'wh_output_stock_loc_id': fields.many2one('stock.location', 'Output Location'),
        'wh_pack_stock_loc_id': fields.many2one('stock.location', 'Packing Location'),
        'mto_pull_id': fields.many2one('procurement.rule', 'MTO rule'),
        'pick_type_id': fields.many2one('stock.picking.type', 'Pick Type'),
        'pack_type_id': fields.many2one('stock.picking.type', 'Pack Type'),
        'out_type_id': fields.many2one('stock.picking.type', 'Out Type'),
        'in_type_id': fields.many2one('stock.picking.type', 'In Type'),
        'int_type_id': fields.many2one('stock.picking.type', 'Internal Type'),
        'crossdock_route_id': fields.many2one('stock.location.route', 'Crossdock Route'),
        'reception_route_id': fields.many2one('stock.location.route', 'Reception Route'),
        'delivery_route_id': fields.many2one('stock.location.route', 'Delivery Route'),
        'resupply_from_wh': fields.boolean('Resupply From Other Warehouses'),
        'resupply_wh_ids': fields.many2many('stock.warehouse', 'stock_wh_resupply_table', 'supplied_wh_id', 'supplier_wh_id', 'Resupply Warehouses'),
        'resupply_route_ids': fields.one2many('stock.location.route', 'supplied_wh_id', 'Resupply Routes'),
        'default_resupply_wh_id': fields.many2one('stock.warehouse', 'Default Resupply Warehouse', domain="[('id','in',resupply_init_filter)]"),
        'show_default_resupply_wh_id': fields.function(show_field_default_wh_resupply,type='boolean',string="Show field default_resupply_wh_id"),
        'resupply_init_filter' : fields.function(init_filtre_default_resupply_wh_id, type='many2one', string='test',relation='stock.warehouse'),
    }

    def onchange_filtre_default_resupply_wh_id(self, cr, uid, ids, resupply_wh_ids,default_resupply_wh_id, context=None):
        resupply_wh_ids = [x['id'] for x in (self.resolve_2many_commands(cr, uid, 'resupply_wh_ids',resupply_wh_ids, ['id']))]
        print(default_resupply_wh_id,resupply_wh_ids)
        
        retval = {'show_default_resupply_wh_id' :  len(resupply_wh_ids)>0 }
        warning = {}
        
        if (default_resupply_wh_id and default_resupply_wh_id not in resupply_wh_ids):            
            retval['default_resupply_wh_id'] = False
            warning = { 
                       'title': 'Information', 
                       'message': 'Default resupply warehouse has been changed because old default value is not in this list !'
                       }        
        return {
                'value': retval,
                'domain':{ 'default_resupply_wh_id':[('id','in',resupply_wh_ids)] },
                'warning': warning
               }

    def _get_inter_wh_location(self, cr, uid, warehouse, context=None):
        ''' returns a tuple made of the browse record of customer location and the browse record of supplier location'''
        data_obj = self.pool.get('ir.model.data')
        try:
            inter_wh_loc = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_inter_wh')[1]
        except:
            inter_wh_loc = False
        return inter_wh_loc

    def _get_all_products_to_resupply(self, cr, uid, warehouse, context=None):
        return self.pool.get('product.product').search(cr, uid, [], context=context)

    def _assign_route_on_products(self, cr, uid, warehouse, inter_wh_route_id, context=None):
        product_ids = self._get_all_products_to_resupply(cr, uid, warehouse, context=context)
        self.pool.get('product.product').write(cr, uid, product_ids, {'route_ids': [(4, inter_wh_route_id)]}, context=context)

    def _get_inter_wh_route(self, cr, uid, warehouse, wh, context=None):
        return {
            'name': _('%s: Supply Product from %s') % (warehouse.name, wh.name),
            'warehouse_selectable': False,
            'product_selectable': True,
            'product_categ_selectable': True,
            'supplied_wh_id': warehouse.id,
            'supplier_wh_id': wh.id,
        }

    def _create_resupply_routes(self, cr, uid, warehouse, supplier_warehouses, default_resupply_wh, context=None):
        location_obj = self.pool.get('stock.location')
        route_obj = self.pool.get('stock.location.route')
        pull_obj = self.pool.get('procurement.rule')
        #create route selectable on the product to resupply the warehouse from another one
        inter_wh_location_id = self._get_inter_wh_location(cr, uid, warehouse, context=context)
        if inter_wh_location_id:
            input_loc = warehouse.wh_input_stock_loc_id
            if warehouse.reception_steps == 'one_step':
                input_loc = warehouse.lot_stock_id
            inter_wh_location = location_obj.browse(cr, uid, inter_wh_location_id, context=context)
            for wh in supplier_warehouses:
                output_loc = wh.wh_output_stock_loc_id
                if wh.delivery_steps == 'ship_only':
                    output_loc = wh.lot_stock_id
                inter_wh_route_vals = self._get_inter_wh_route(cr, uid, warehouse, wh, context=context)
                inter_wh_route_id = route_obj.create(cr, uid, vals=inter_wh_route_vals, context=context)
                values = [(output_loc, inter_wh_location, wh.out_type_id.id), (inter_wh_location, input_loc, warehouse.in_type_id.id)]
                dummy, pull_rules_list = self._get_push_pull_rules(cr, uid, warehouse, True, values, inter_wh_route_id, context=context)
                for pull_rule in pull_rules_list:
                    pull_obj.create(cr, uid, vals=pull_rule, context=context)
                #if the warehouse is also set as default resupply method, assign this route automatically to all product
                if default_resupply_wh and default_resupply_wh.id == wh.id:
                    self._assign_route_on_products(cr, uid, warehouse, inter_wh_route_id, context=context)

    def _default_stock_id(self, cr, uid, context=None):
        #lot_input_stock = self.pool.get('ir.model.data').get_object(cr, uid, 'stock', 'stock_location_stock')
        try:
            warehouse = self.pool.get('ir.model.data').get_object(cr, uid, 'stock', 'warehouse0')            
            return warehouse.lot_stock_id.id
        except:
            return False

    _defaults = {
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.inventory', context=c),
        'lot_stock_id': _default_stock_id,
        'reception_steps': 'one_step',
        'delivery_steps': 'ship_only',
    }
    _sql_constraints = [
        ('warehouse_name_uniq', 'unique(name, company_id)', 'The name of the warehouse must be unique per company!'),
        ('warehouse_code_uniq', 'unique(code, company_id)', 'The code of the warehouse must be unique per company !'),
    ]

    def _get_partner_locations(self, cr, uid, ids, context=None):
        ''' returns a tuple made of the browse record of customer location and the browse record of supplier location'''
        data_obj = self.pool.get('ir.model.data')
        location_obj = self.pool.get('stock.location')
        try:
            customer_loc = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_customers')[1]
            supplier_loc = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_suppliers')[1]
        except:
            customer_loc = location_obj.search(cr, uid, [('usage', '=', 'customer')], context=context)
            customer_loc = customer_loc and customer_loc[0] or False
            supplier_loc = location_obj.search(cr, uid, [('usage', '=', 'supplier')], context=context)
            supplier_loc = supplier_loc and supplier_loc[0] or False
        if not (customer_loc and supplier_loc):
            raise osv.except_osv(_('Error!'), _('Can\'t find any customer or supplier location.'))
        return location_obj.browse(cr, uid, [customer_loc, supplier_loc], context=context)

    def switch_location(self, cr, uid, ids, warehouse, new_reception_step=False, new_delivery_step=False, context=None):
        location_obj = self.pool.get('stock.location')

        new_reception_step = new_reception_step or warehouse.reception_steps
        new_delivery_step = new_delivery_step or warehouse.delivery_steps
        if warehouse.reception_steps != new_reception_step:
            location_obj.write(cr, uid, [warehouse.wh_input_stock_loc_id.id, warehouse.wh_qc_stock_loc_id.id], {'active': False}, context=context)
            if new_reception_step != 'one_step':
                location_obj.write(cr, uid, warehouse.wh_input_stock_loc_id.id, {'active': True}, context=context)
            if new_reception_step == 'three_steps':
                location_obj.write(cr, uid, warehouse.wh_qc_stock_loc_id.id, {'active': True}, context=context)

        if warehouse.delivery_steps != new_delivery_step:
            location_obj.write(cr, uid, [warehouse.wh_output_stock_loc_id.id, warehouse.wh_pack_stock_loc_id.id], {'active': False}, context=context)
            if new_delivery_step != 'ship_only':
                location_obj.write(cr, uid, warehouse.wh_output_stock_loc_id.id, {'active': True}, context=context)
            if new_delivery_step == 'pick_pack_ship':
                location_obj.write(cr, uid, warehouse.wh_pack_stock_loc_id.id, {'active': True}, context=context)
        return True

    def _get_reception_delivery_route(self, cr, uid, warehouse, route_name, context=None):
        return {
            'name': self._format_routename(cr, uid, warehouse, route_name, context=context),
            'product_categ_selectable': True,
            'product_selectable': False,
            'sequence': 10,
        }

    def _get_push_pull_rules(self, cr, uid, warehouse, active, values, new_route_id, context=None):
        first_rule = True
        push_rules_list = []
        pull_rules_list = []
        for from_loc, dest_loc, pick_type_id in values:
            push_rules_list.append({
                'name': self._format_rulename(cr, uid, warehouse, from_loc, dest_loc, context=context),
                'location_from_id': from_loc.id,
                'location_dest_id': dest_loc.id,
                'route_id': new_route_id,
                'auto': 'manual',
                'picking_type_id': pick_type_id,
                'active': active,
                'warehouse_id': warehouse.id,
            })
            pull_rules_list.append({
                'name': self._format_rulename(cr, uid, warehouse, from_loc, dest_loc, context=context),
                'location_src_id': from_loc.id,
                'location_id': dest_loc.id,
                'route_id': new_route_id,
                'action': 'move',
                'picking_type_id': pick_type_id,
                'procure_method': first_rule is True and 'make_to_stock' or 'make_to_order',
                'active': active,
                'warehouse_id': warehouse.id,
            })
            first_rule = False
        return push_rules_list, pull_rules_list

    def _get_mto_pull_rule(self, cr, uid, warehouse, values, context=None):
        data_obj = self.pool.get('ir.model.data')
        try:
            mto_route_id = data_obj.get_object_reference(cr, uid, 'stock', 'route_warehouse0_mto')[1]
        except:
            mto_route_id = route_obj.search(cr, uid, [('name', 'like', _('MTO'))], context=context)
            mto_route_id = mto_route_id and mto_route_id[0] or False
        if not mto_route_id:
            raise osv.except_osv(_('Error!'), _('Can\'t find any generic MTO route.'))

        from_loc, dest_loc, pick_type_id = values[0]
        return {
            'name': self._format_rulename(cr, uid, warehouse, from_loc, dest_loc, context=context) + _(' MTO'),
            'location_src_id': from_loc.id,
            'location_id': dest_loc.id,
            'route_id': mto_route_id,
            'action': 'move',
            'picking_type_id': pick_type_id,
            'procure_method': 'make_to_order',
            'active': True,
            'warehouse_id': warehouse.id,
        }

    def _get_crossdock_route(self, cr, uid, warehouse, route_name, context=None):
        return {
            'name': self._format_routename(cr, uid, warehouse, route_name, context=context),
            'warehouse_selectable': False,
            'product_selectable': True,
            'product_categ_selectable': True,
            'active': warehouse.delivery_steps != 'ship_only' and warehouse.reception_steps != 'one_step',
            'sequence': 20,
        }

    def create_routes(self, cr, uid, ids, warehouse, context=None):
        wh_route_ids = []
        route_obj = self.pool.get('stock.location.route')
        pull_obj = self.pool.get('procurement.rule')
        push_obj = self.pool.get('stock.location.path')
        routes_dict = self.get_routes_dict(cr, uid, ids, warehouse, context=context)
        #create reception route and rules
        route_name, values = routes_dict[warehouse.reception_steps]
        route_vals = self._get_reception_delivery_route(cr, uid, warehouse, route_name, context=context)
        reception_route_id = route_obj.create(cr, uid, route_vals, context=context)
        wh_route_ids.append((4, reception_route_id))
        push_rules_list, pull_rules_list = self._get_push_pull_rules(cr, uid, warehouse, True, values, reception_route_id, context=context)
        #create the push/pull rules
        for push_rule in push_rules_list:
            push_obj.create(cr, uid, vals=push_rule, context=context)
        for pull_rule in pull_rules_list:
            #all pull rules in reception route are mto, because we don't won't to wait for the scheduler to trigger an orderpoint on input location
            pull_rule['procure_method'] = 'make_to_order'
            pull_obj.create(cr, uid, vals=pull_rule, context=context)

        #create MTS route and pull rules for delivery a specific route MTO to be set on the product
        route_name, values = routes_dict[warehouse.delivery_steps]
        route_vals = self._get_reception_delivery_route(cr, uid, warehouse, route_name, context=context)
        #create the route and its pull rules
        delivery_route_id = route_obj.create(cr, uid, route_vals, context=context)
        wh_route_ids.append((4, delivery_route_id))
        dummy, pull_rules_list = self._get_push_pull_rules(cr, uid, warehouse, True, values, delivery_route_id, context=context)
        for pull_rule in pull_rules_list:
            pull_obj.create(cr, uid, vals=pull_rule, context=context)
        #create MTO pull rule and link it to the generic MTO route
        mto_pull_vals = self._get_mto_pull_rule(cr, uid, warehouse, values, context=context)
        mto_pull_id = pull_obj.create(cr, uid, mto_pull_vals, context=context)

        #create a route for cross dock operations, that can be set on products and product categories
        route_name, values = routes_dict['crossdock']
        crossdock_route_vals = self._get_crossdock_route(cr, uid, warehouse, route_name, context=context)
        crossdock_route_id = route_obj.create(cr, uid, vals=crossdock_route_vals, context=context)
        wh_route_ids.append((4, crossdock_route_id))
        dummy, pull_rules_list = self._get_push_pull_rules(cr, uid, warehouse, warehouse.delivery_steps != 'ship_only' and warehouse.reception_steps != 'one_step', values, crossdock_route_id, context=context)
        for pull_rule in pull_rules_list:
            pull_obj.create(cr, uid, vals=pull_rule, context=context)

        #create route selectable on the product to resupply the warehouse from another one
        self._create_resupply_routes(cr, uid, warehouse, warehouse.resupply_wh_ids, warehouse.default_resupply_wh_id, context=context)

        #return routes and mto pull rule for warehouse
        return {
            'route_ids': wh_route_ids,
            'mto_pull_id': mto_pull_id,
            'reception_route_id': reception_route_id,
            'delivery_route_id': delivery_route_id,
            'crossdock_route_id': crossdock_route_id,
        }

    def change_route(self, cr, uid, ids, warehouse, new_reception_step=False, new_delivery_step=False, context=None):
        picking_type_obj = self.pool.get('stock.picking.type')
        pull_obj = self.pool.get('procurement.rule')
        push_obj = self.pool.get('stock.location.path')
        route_obj = self.pool.get('stock.location.route')
        new_reception_step = new_reception_step or warehouse.reception_steps
        new_delivery_step = new_delivery_step or warehouse.delivery_steps

        #change the default source and destination location and (de)activate picking types
        input_loc = warehouse.wh_input_stock_loc_id
        if new_reception_step == 'one_step':
            input_loc = warehouse.lot_stock_id
        output_loc = warehouse.wh_output_stock_loc_id
        if new_delivery_step == 'ship_only':
            output_loc = warehouse.lot_stock_id
        picking_type_obj.write(cr, uid, warehouse.in_type_id.id, {'default_location_dest_id': input_loc.id}, context=context)
        picking_type_obj.write(cr, uid, warehouse.out_type_id.id, {'default_location_src_id': output_loc.id}, context=context)
        picking_type_obj.write(cr, uid, warehouse.int_type_id.id, {'active': new_reception_step != 'one_step'}, context=context)
        picking_type_obj.write(cr, uid, warehouse.pick_type_id.id, {'active': new_delivery_step != 'ship_only'}, context=context)
        picking_type_obj.write(cr, uid, warehouse.pack_type_id.id, {'active': new_delivery_step == 'pick_pack_ship'}, context=context)

        routes_dict = self.get_routes_dict(cr, uid, ids, warehouse, context=context)
        #update delivery route and rules: unlink the existing rules of the warehouse delivery route and recreate it
        pull_obj.unlink(cr, uid, [pu.id for pu in warehouse.delivery_route_id.pull_ids], context=context)
        route_name, values = routes_dict[new_delivery_step]
        route_obj.write(cr, uid, warehouse.delivery_route_id.id, {'name': self._format_routename(cr, uid, warehouse, route_name, context=context)}, context=context)
        dummy, pull_rules_list = self._get_push_pull_rules(cr, uid, warehouse, True, values, warehouse.delivery_route_id.id, context=context)
        #create the pull rules
        for pull_rule in pull_rules_list:
            pull_obj.create(cr, uid, vals=pull_rule, context=context)

        #update reception route and rules: unlink the existing rules of the warehouse reception route and recreate it
        pull_obj.unlink(cr, uid, [pu.id for pu in warehouse.reception_route_id.pull_ids], context=context)
        push_obj.unlink(cr, uid, [pu.id for pu in warehouse.reception_route_id.push_ids], context=context)
        route_name, values = routes_dict[new_reception_step]
        route_obj.write(cr, uid, warehouse.reception_route_id.id, {'name': self._format_routename(cr, uid, warehouse, route_name, context=context)}, context=context)
        push_rules_list, pull_rules_list = self._get_push_pull_rules(cr, uid, warehouse, True, values, warehouse.reception_route_id.id, context=context)
        #create the push/pull rules
        for push_rule in push_rules_list:
            push_obj.create(cr, uid, vals=push_rule, context=context)
        for pull_rule in pull_rules_list:
            pull_obj.create(cr, uid, vals=pull_rule, context=context)

        route_obj.write(cr, uid, warehouse.crossdock_route_id.id, {'active': new_reception_step != 'one_step' and new_delivery_step != 'ship_only'}, context=context)

        #change MTO rule
        dummy, values = routes_dict[new_delivery_step]
        mto_pull_vals = self._get_mto_pull_rule(cr, uid, warehouse, values, context=context)
        pull_obj.write(cr, uid, warehouse.mto_pull_id.id, mto_pull_vals, context=context)
        return True

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if vals is None:
            vals = {}
        data_obj = self.pool.get('ir.model.data')
        seq_obj = self.pool.get('ir.sequence')
        picking_type_obj = self.pool.get('stock.picking.type')
        location_obj = self.pool.get('stock.location')

        #create view location for warehouse
        wh_loc_id = location_obj.create(cr, uid, {
                'name': _(vals.get('name')),
                'usage': 'view',
                'location_id': data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_locations')[1]
            }, context=context)
        vals['view_location_id'] = wh_loc_id
        #create all location
        reception_steps = vals.get('reception_steps', False)
        delivery_steps = vals.get('delivery_steps', False)
        context_with_inactive = context.copy()
        context_with_inactive['active_test'] = False
        sub_locations = [
            {'name': _('Stock'), 'active': True, 'field': 'lot_stock_id'},
            {'name': _('Input'), 'active': reception_steps != 'one_step', 'field': 'wh_input_stock_loc_id'},
            {'name': _('Quality Control'), 'active': reception_steps == 'three_steps', 'field': 'wh_qc_stock_loc_id'},
            {'name': _('Output'), 'active': delivery_steps != 'ship_only', 'field': 'wh_output_stock_loc_id'},
            {'name': _('Packing Zone'), 'active': delivery_steps == 'pick_pack_ship', 'field': 'wh_pack_stock_loc_id'},
        ]
        for values in sub_locations:
            location_id = location_obj.create(cr, uid, {
                'name': values['name'],
                'usage': 'internal',
                'location_id': wh_loc_id,
                'active': values['active'],
            }, context=context_with_inactive)
            vals[values['field']] = location_id

        #create new sequences
        in_seq_id = seq_obj.create(cr, SUPERUSER_ID, values={'name': vals.get('name', '') + _(' Sequence in'), 'prefix': vals.get('code', '') + '\IN\\', 'padding': 5}, context=context)
        out_seq_id = seq_obj.create(cr, SUPERUSER_ID, values={'name': vals.get('name', '') + _(' Sequence out'), 'prefix': vals.get('code', '') + '\OUT\\', 'padding': 5}, context=context)
        pack_seq_id = seq_obj.create(cr, SUPERUSER_ID, values={'name': vals.get('name', '') + _(' Sequence packing'), 'prefix': vals.get('code', '') + '\PACK\\', 'padding': 5}, context=context)
        pick_seq_id = seq_obj.create(cr, SUPERUSER_ID, values={'name': vals.get('name', '') + _(' Sequence picking'), 'prefix': vals.get('code', '') + '\PICK\\', 'padding': 5}, context=context)
        int_seq_id = seq_obj.create(cr, SUPERUSER_ID, values={'name': vals.get('name', '') + _(' Sequence internal'), 'prefix': vals.get('code', '') + '\INT\\', 'padding': 5}, context=context)

        #create WH
        new_id = super(stock_warehouse, self).create(cr, uid, vals=vals, context=context)

        warehouse = self.browse(cr, uid, new_id, context=context)
        wh_stock_loc = warehouse.lot_stock_id
        wh_input_stock_loc = warehouse.wh_input_stock_loc_id
        wh_output_stock_loc = warehouse.wh_output_stock_loc_id
        wh_pack_stock_loc = warehouse.wh_pack_stock_loc_id

        #fetch customer and supplier locations, for references
        customer_loc, supplier_loc = self._get_partner_locations(cr, uid, new_id, context=context)

        #create in, out, internal picking types for warehouse
        input_loc = wh_input_stock_loc
        if warehouse.reception_steps == 'one_step':
            input_loc = wh_stock_loc
        output_loc = wh_output_stock_loc
        if warehouse.delivery_steps == 'ship_only':
            output_loc = wh_stock_loc

        #choose the next available color for the picking types of this warehouse
        all_used_colors = self.pool.get('stock.picking.type').search_read(cr, uid, [('warehouse_id', '!=', False), ('color', '!=', False)], ['color'], order='color')
        not_used_colors = list(set(range(1, 10)) - set([x['color'] for x in all_used_colors]))
        color = not_used_colors and not_used_colors[0] or 1

        in_type_id = picking_type_obj.create(cr, uid, vals={
            'name': _('Receptions'),
            'warehouse_id': new_id,
            'code_id': 'incoming',
            'auto_force_assign': True,
            'sequence_id': in_seq_id,
            'default_location_src_id': supplier_loc.id,
            'default_location_dest_id': input_loc.id,
            'color': color}, context=context)
        out_type_id = picking_type_obj.create(cr, uid, vals={
            'name': _('Delivery Orders'),
            'warehouse_id': new_id,
            'code_id': 'outgoing',
            'sequence_id': out_seq_id,
            'delivery': True,
            'default_location_src_id': output_loc.id,
            'default_location_dest_id': customer_loc.id,
            'color': color}, context=context)
        int_type_id = picking_type_obj.create(cr, uid, vals={
            'name': _('Internal Transfers'),
            'warehouse_id': new_id,
            'code_id': 'internal',
            'sequence_id': int_seq_id,
            'default_location_src_id': wh_stock_loc.id,
            'default_location_dest_id': wh_stock_loc.id,
            'active': reception_steps != 'one_step',
            'pack': False,
            'color': color}, context=context)
        pack_type_id = picking_type_obj.create(cr, uid, vals={
            'name': _('Pack'),
            'warehouse_id': new_id,
            'code_id': 'internal',
            'sequence_id': pack_seq_id,
            'default_location_src_id': wh_pack_stock_loc.id,
            'default_location_dest_id': output_loc.id,
            'active': delivery_steps == 'pick_pack_ship',
            'pack': True,
            'color': color}, context=context)
        pick_type_id = picking_type_obj.create(cr, uid, vals={
            'name': _('Pick'),
            'warehouse_id': new_id,
            'code_id': 'internal',
            'sequence_id': pick_seq_id,
            'default_location_src_id': wh_stock_loc.id,
            'default_location_dest_id': wh_pack_stock_loc.id,
            'active': delivery_steps != 'ship_only',
            'pack': False,
            'color': color}, context=context)

        #write picking types on WH
        vals = {
            'in_type_id': in_type_id,
            'out_type_id': out_type_id,
            'pack_type_id': pack_type_id,
            'pick_type_id': pick_type_id,
            'int_type_id': int_type_id,
        }
        super(stock_warehouse, self).write(cr, uid, new_id, vals=vals, context=context)
        warehouse.refresh()

        #create routes and push/pull rules
        new_objects_dict = self.create_routes(cr, uid, new_id, warehouse, context=context)
        self.write(cr, uid, warehouse.id, new_objects_dict, context=context)
        return new_id

    def _format_rulename(self, cr, uid, obj, from_loc, dest_loc, context=None):
        return obj.name + ': ' + from_loc.name + ' -> ' + dest_loc.name

    def _format_routename(self, cr, uid, obj, name, context=None):
        return obj.name + ': ' + name

    def get_routes_dict(self, cr, uid, ids, warehouse, context=None):
        #fetch customer and supplier locations, for references
        customer_loc, supplier_loc = self._get_partner_locations(cr, uid, ids, context=context)

        return {
            'one_step': (_('Reception in 1 step'), []),
            'two_steps': (_('Reception in 2 steps'), [(warehouse.wh_input_stock_loc_id, warehouse.lot_stock_id, warehouse.int_type_id.id)]),
            'three_steps': (_('Reception in 3 steps'), [(warehouse.wh_input_stock_loc_id, warehouse.wh_qc_stock_loc_id, warehouse.int_type_id.id), (warehouse.wh_qc_stock_loc_id, warehouse.lot_stock_id, warehouse.int_type_id.id)]),
            'crossdock': (_('Cross-Dock'), [(warehouse.wh_input_stock_loc_id, warehouse.wh_output_stock_loc_id, warehouse.int_type_id.id), (warehouse.wh_output_stock_loc_id, customer_loc, warehouse.out_type_id.id)]),
            'ship_only': (_('Ship Only'), [(warehouse.lot_stock_id, customer_loc, warehouse.out_type_id.id)]),
            'pick_ship': (_('Pick + Ship'), [(warehouse.lot_stock_id, warehouse.wh_output_stock_loc_id, warehouse.pick_type_id.id), (warehouse.wh_output_stock_loc_id, customer_loc, warehouse.out_type_id.id)]),
            'pick_pack_ship': (_('Pick + Pack + Ship'), [(warehouse.lot_stock_id, warehouse.wh_pack_stock_loc_id, warehouse.int_type_id.id), (warehouse.wh_pack_stock_loc_id, warehouse.wh_output_stock_loc_id, warehouse.pack_type_id.id), (warehouse.wh_output_stock_loc_id, customer_loc, warehouse.out_type_id.id)]),
        }

    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        seq_obj = self.pool.get('ir.sequence')
        location_obj = self.pool.get('stock.location')
        route_obj = self.pool.get('stock.location.route')
        warehouse_obj = self.pool.get('stock.warehouse')
        pull_obj = self.pool.get('procurement.rule')
        push_obj = self.pool.get('stock.location.path')

        context_with_inactive = context.copy()
        context_with_inactive['active_test'] = False
        for warehouse in self.browse(cr, uid, ids, context=context_with_inactive):
            #first of all, check if we need to delete and recreate route
            if vals.get('reception_steps') or vals.get('delivery_steps'):
                #activate and deactivate location according to reception and delivery option
                self.switch_location(cr, uid, warehouse.id, warehouse, vals.get('reception_steps', False), vals.get('delivery_steps', False), context=context)
                # switch between route
                self.change_route(cr, uid, ids, warehouse, vals.get('reception_steps', False), vals.get('delivery_steps', False), context=context_with_inactive)
            if vals.get('code') or vals.get('name'):
                name = warehouse.name
                #rename sequence
                if vals.get('name'):
                    name = vals.get('name')
                    #rename location
                    location_id = warehouse.lot_stock_id.location_id.id
                    location_obj.write(cr, uid, location_id, {'name': name}, context=context_with_inactive)
                    #rename route and push-pull rules
                    for route in warehouse.route_ids:
                        route_obj.write(cr, uid, route.id, {'name': route.name.replace(warehouse.name, name, 1)}, context=context_with_inactive)
                        for pull in route.pull_ids:
                            pull_obj.write(cr, uid, pull.id, {'name': pull.name.replace(warehouse.name, name, 1)}, context=context_with_inactive)
                        for push in route.push_ids:
                            push_obj.write(cr, uid, push.id, {'name': pull.name.replace(warehouse.name, name, 1)}, context=context_with_inactive)
                    #change the mto pull rule name
                    pull_obj.write(cr, uid, warehouse.mto_pull_id.id, {'name': warehouse.mto_pull_id.name.replace(warehouse.name, name, 1)}, context=context_with_inactive)
                seq_obj.write(cr, uid, warehouse.in_type_id.sequence_id.id, {'name': name + _(' Sequence in'), 'prefix': vals.get('code', warehouse.code) + '\IN\\'}, context=context)
                seq_obj.write(cr, uid, warehouse.out_type_id.sequence_id.id, {'name': name + _(' Sequence out'), 'prefix': vals.get('code', warehouse.code) + '\OUT\\'}, context=context)
                seq_obj.write(cr, uid, warehouse.pack_type_id.sequence_id.id, {'name': name + _(' Sequence packing'), 'prefix': vals.get('code', warehouse.code) + '\PACK\\'}, context=context)
                seq_obj.write(cr, uid, warehouse.pick_type_id.sequence_id.id, {'name': name + _(' Sequence picking'), 'prefix': vals.get('code', warehouse.code) + '\PICK\\'}, context=context)
                seq_obj.write(cr, uid, warehouse.int_type_id.sequence_id.id, {'name': name + _(' Sequence internal'), 'prefix': vals.get('code', warehouse.code) + '\INT\\'}, context=context)

        if vals.get('resupply_wh_ids') and not vals.get('resupply_route_ids'):
            for cmd in vals.get('resupply_wh_ids'):
                if cmd[0] == 6:
                    new_ids = set(cmd[2])
                    old_ids = set([wh.id for wh in warehouse.resupply_wh_ids])
                    to_add_wh_ids = new_ids - old_ids
                    supplier_warehouses = warehouse_obj.browse(cr, uid, list(to_add_wh_ids), context=context)
                    self._create_resupply_routes(cr, uid, warehouse, supplier_warehouses, warehouse.default_resupply_wh_id, context=context)
                    to_remove_wh_ids = old_ids - new_ids
                    to_remove_route_ids = route_obj.search(cr, uid, [('supplied_wh_id', '=', warehouse.id), ('supplier_wh_id', 'in', list(to_remove_wh_ids))], context=context)
                    route_obj.unlink(cr, uid, to_remove_route_ids, context=context)
                else:
                    #not implemented
                    pass
        if 'default_resupply_wh_id' in vals:
            if warehouse.default_resupply_wh_id:
                to_remove_route_ids = route_obj.search(cr, uid, [('supplied_wh_id', '=', warehouse.id), ('supplier_wh_id', '=', warehouse.default_resupply_wh_id.id)], context=context)
                route_obj.unlink(cr, uid, to_remove_route_ids, context=context)
                self._create_resupply_routes(cr, uid, warehouse, [warehouse.default_resupply_wh_id], False, context=context)
            if vals.get('default_resupply_wh_id'):
                to_remove_route_ids = route_obj.search(cr, uid, [('supplied_wh_id', '=', warehouse.id), ('supplier_wh_id', '=', vals.get('default_resupply_wh_id'))], context=context)
                route_obj.unlink(cr, uid, to_remove_route_ids, context=context)
                def_supplier_wh = warehouse_obj.browse(cr, uid, vals['default_resupply_wh_id'], context=context)
                self._create_resupply_routes(cr, uid, warehouse, [def_supplier_wh], def_supplier_wh, context=context)

        return super(stock_warehouse, self).write(cr, uid, ids, vals=vals, context=context)

    def unlink(self, cr, uid, ids, context=None):
        #TODO try to delete location and route and if not possible, put them in inactive
        return super(stock_warehouse, self).unlink(cr, uid, ids, context=context)

    def get_all_routes_for_wh(self, cr, uid, warehouse, context=None):
        all_routes = []        
        all_routes += [warehouse.crossdock_route_id.id]
        all_routes += [warehouse.reception_route_id.id]
        all_routes += [warehouse.delivery_route_id.id]
        all_routes += [warehouse.mto_pull_id.route_id.id]
        all_routes += [route.id for route in warehouse.resupply_route_ids]
        all_routes += [route.id for route in warehouse.route_ids]
        return all_routes

    def view_all_routes_for_wh(self, cr, uid, ids, context=None):
        all_routes = []
        for wh in self.browse(cr, uid, ids, context=context):
            all_routes += self.get_all_routes_for_wh(cr, uid, wh, context=context)
                        
        res_id = ids and ids[0] or False
        domain = [('id', 'in', all_routes)]
        return {
            'name': _('Warehouse\'s Routes'),
            'domain': domain,
            'res_model': 'stock.location.route',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'tree,form',
            'view_type': 'form',
            'limit': 20
        }

class stock_location_path(osv.osv):
    _name = "stock.location.path"
    _description = "Pushed Flows"
    _order = "name"

    def _get_route(self, cr, uid, ids, context=None):
        #WARNING TODO route_id is not required, so a field related seems a bad idea >-< 
        if context is None:
            context = {}
        result = {}
        if context is None:
            context = {}
        context_with_inactive = context.copy()
        context_with_inactive['active_test']=False
        for route in self.pool.get('stock.location.route').browse(cr, uid, ids, context=context_with_inactive):
            for push_rule in route.push_ids:
                result[push_rule.id] = True
        return result.keys()

    _columns = {
        'name': fields.char('Operation Name', size=64, required=True),
        'company_id': fields.many2one('res.company', 'Company'),
        'route_id': fields.many2one('stock.location.route', 'Route'),
        'location_from_id': fields.many2one('stock.location', 'Source Location', ondelete='cascade', select=1, required=True),
        'location_dest_id': fields.many2one('stock.location', 'Destination Location', ondelete='cascade', select=1, required=True),
        'delay': fields.integer('Delay (days)', help="Number of days to do this transition"),
        'invoice_state': fields.selection([
            ("invoiced", "Invoiced"),
            ("2binvoiced", "To Be Invoiced"),
            ("none", "Not Applicable")], "Invoice Status",
            required=True,), 
        'picking_type_id': fields.many2one('stock.picking.type', 'Type of the new Operation', required=True, help="This is the picking type associated with the different pickings"), 
        'auto': fields.selection(
            [('auto','Automatic Move'), ('manual','Manual Operation'),('transparent','Automatic No Step Added')],
            'Automatic Move',
            required=True, select=1,
            help="This is used to define paths the product has to follow within the location tree.\n" \
                "The 'Automatic Move' value will create a stock move after the current one that will be "\
                "validated automatically. With 'Manual Operation', the stock move has to be validated "\
                "by a worker. With 'Automatic No Step Added', the location is replaced in the original move."
            ),
        'propagate': fields.boolean('Propagate cancel and split', help='If checked, when the previous move is cancelled or split, the move generated by this move will too'),
        'active': fields.related('route_id', 'active', type='boolean', string='Active', store={
                    'stock.location.route': (_get_route, ['active'], 20),
                    'stock.location.path': (lambda self, cr, uid, ids, c={}: ids, ['route_id'], 20),},
                help="If the active field is set to False, it will allow you to hide the rule without removing it." ),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse'),
    }
    _defaults = {
        'auto': 'auto',
        'delay': 1,
        'invoice_state': 'none',
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'procurement.order', context=c),
        'propagate': True,
        'active': True,
    }
    def _apply(self, cr, uid, rule, move, context=None):
        move_obj = self.pool.get('stock.move')
        newdate = (datetime.strptime(move.date, '%Y-%m-%d %H:%M:%S') + relativedelta.relativedelta(days=rule.delay or 0)).strftime('%Y-%m-%d')
        if rule.auto=='transparent':
            move_obj.write(cr, uid, [move.id], {
                'date': newdate,
                'location_dest_id': rule.location_dest_id.id
            })
            if rule.location_dest_id.id<>move.location_dest_id.id:
                move_obj._push_apply(self, cr, uid, move.id, context)
            return move.id
        else:
            move_id = move_obj.copy(cr, uid, move.id, {
                'location_id': move.location_dest_id.id,
                'location_dest_id': rule.location_dest_id.id,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'company_id': rule.company_id and rule.company_id.id or False,
                'date_expected': newdate,
                'picking_id': False,
                'picking_type_id': rule.picking_type_id and rule.picking_type_id.id or False,
                'rule_id': rule.id,
                'propagate': rule.propagate, 
                'warehouse_id': rule.warehouse_id and rule.warehouse_id.id or False,
            })
            move_obj.write(cr, uid, [move.id], {
                'move_dest_id': move_id,
            })
            move_obj.action_confirm(cr, uid, [move_id], context=None)
            return move_id

class stock_move_putaway(osv.osv):
    _name = 'stock.move.putaway'
    _description = 'Proposed Destination'
    _columns = {
        'move_id': fields.many2one('stock.move', required=True),
        'location_id': fields.many2one('stock.location', 'Location', required=True),
        'lot_id': fields.many2one('stock.production.lot', 'Lot'),
        'quantity': fields.float('Quantity', required=True),
    }



# -------------------------
# Packaging related stuff
# -------------------------

from openerp.report import report_sxw
report_sxw.report_sxw('report.stock.quant.package.barcode', 'stock.quant.package', 'addons/stock/report/picking_barcode.rml')

class stock_package(osv.osv):
    """
    These are the packages, containing quants and/or other packages
    """
    _name = "stock.quant.package"
    _description = "Physical Packages"
    _parent_name = "parent_id"
    _parent_store = True
    _parent_order = 'name'
    _order = 'parent_left'

    def name_get(self, cr, uid, ids, context=None):
        res = self._complete_name(cr, uid, ids, 'complete_name', None, context=context)
        return res.items()

    def _complete_name(self, cr, uid, ids, name, args, context=None):
        """ Forms complete name of location from parent location to child location.
        @return: Dictionary of values
        """
        res = {}
        for m in self.browse(cr, uid, ids, context=context):
            res[m.id] = m.name
            parent = m.parent_id
            while parent:
                res[m.id] = parent.name + ' / ' + res[m.id]
                parent = parent.parent_id
        return res

    def _get_packages(self, cr, uid, ids, context=None):
        """Returns packages from quants for store"""
        res = set()
        for quant in self.browse(cr, uid, ids, context=context):
            if quant.package_id:
                res.add(quant.package_id.id)
        return list(res)

    def _get_packages_to_relocate(self, cr, uid, ids, context=None):
        res = set()
        for pack in self.browse(cr, uid, ids, context=context):
            res.add(pack.id)
            if pack.parent_id:
                res.add(pack.parent_id.id)
        return list(res)

    # TODO: Problem when package is empty!
    #
    def _get_package_info(self, cr, uid, ids, name, args, context=None):
        default_company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        res = {}.fromkeys(ids, {'location_id': False, 'company_id': default_company_id})
        for pack in self.browse(cr, uid, ids, context=context):
            if pack.quant_ids:
                res[pack.id]['location_id'] = pack.quant_ids[0].location_id.id
                res[pack.id]['owner_id'] = pack.quant_ids[0].owner_id and pack.quant_ids[0].owner_id.id or False
                res[pack.id]['company_id'] = pack.quant_ids[0].company_id.id
            elif pack.children_ids:
                res[pack.id]['location_id'] = pack.children_ids[0].location_id and pack.children_ids[0].location_id.id or False
                res[pack.id]['owner_id'] = pack.children_ids[0].owner_id and pack.children_ids[0].owner_id.id or False
                res[pack.id]['company_id'] = pack.children_ids[0].company_id and pack.children_ids[0].company_id.id or False
        return res

    _columns = {
        'name': fields.char('Package Reference', size=64, select=True),
        'complete_name': fields.function(_complete_name, type='char', string="Package Name",),
        'parent_left': fields.integer('Left Parent', select=1),
        'parent_right': fields.integer('Right Parent', select=1),
        'packaging_id': fields.many2one('product.packaging', 'Type of Packaging'),
        'location_id': fields.function(_get_package_info, type='many2one', relation='stock.location', string='Location', multi="package",
                                    store={
                                       'stock.quant': (_get_packages, ['location_id'], 10),
                                       'stock.quant.package': (_get_packages_to_relocate, ['quant_ids', 'children_ids', 'parent_id'], 10),
                                    }, readonly=True),
        'quant_ids': fields.one2many('stock.quant', 'package_id', 'Bulk Content'),
        'parent_id': fields.many2one('stock.quant.package', 'Parent Package', help="The package containing this item", ondelete='restrict'),
        'children_ids': fields.one2many('stock.quant.package', 'parent_id', 'Contained Packages'),
        'company_id': fields.function(_get_package_info, type="many2one", relation='res.company', string='Company', multi="package", 
                                    store={
                                       'stock.quant': (_get_packages, ['company_id'], 10),
                                       'stock.quant.package': (_get_packages_to_relocate, ['quant_ids', 'children_ids', 'parent_id'], 10),
                                    }, readonly=True),
        'owner_id': fields.function(_get_package_info, type='many2one', relation='res.partner', string='Owner', multi="package",
                                store={
                                       'stock.quant': (_get_packages, ['owner_id'], 10),
                                       'stock.quant.package': (_get_packages_to_relocate, ['quant_ids', 'children_ids', 'parent_id'], 10),
                                    }, readonly=True),
    }
    _defaults = {
        'name': lambda self, cr, uid, context: self.pool.get('ir.sequence').get(cr, uid, 'stock.quant.package') or _('Unknown Pack')
    }
    def _check_location(self, cr, uid, ids, context=None):
        '''checks that all quants in a package are stored in the same location'''
        quant_obj = self.pool.get('stock.quant')
        for pack in self.browse(cr, uid, ids, context=context):
            parent = pack
            while parent.parent_id:
                parent = parent.parent_id
            quant_ids = self.get_content(cr, uid, [parent.id], context=context)
            quants = quant_obj.browse(cr, uid, quant_ids, context=context)
            location_id = quants and quants[0].location_id.id or False
            if not all([quant.location_id.id == location_id for quant in quants]):
                return False
        return True

    _constraints = [
        (_check_location, 'Everything inside a package should be in the same location', ['location_id']),
    ]

    def action_print(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        datas = {
            'ids': context.get('active_id') and [context.get('active_id')] or ids,
            'model': 'stock.quant.package',
            'form': self.read(cr, uid, ids)[0]
        }
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'stock.quant.package.barcode',
            'datas': datas
        }

    def unpack(self, cr, uid, ids, context=None):
        quant_obj = self.pool.get('stock.quant')
        for package in self.browse(cr, uid, ids, context=context):
            quant_ids = [quant.id for quant in package.quant_ids]
            quant_obj.write(cr, uid, quant_ids, {'package_id': package.parent_id.id or False}, context=context)
            children_package_ids = [child_package.id for child_package in package.children_ids]
            self.write(cr, uid, children_package_ids, {'parent_id': package.parent_id.id or False}, context=context)
        #delete current package since it contains nothing anymore
        self.unlink(cr, uid, ids, context=context)
        return self.pool.get('ir.actions.act_window').for_xml_id(cr, uid, 'stock', 'action_package_view', context=context)

    def get_content(self, cr, uid, ids, context=None):
        child_package_ids = self.search(cr, uid, [('id', 'child_of', ids)], context=context)
        return self.pool.get('stock.quant').search(cr, uid, [('package_id', 'in', child_package_ids)], context=context)

    def get_content_package(self, cr, uid, ids, context=None):
        quants_ids = self.get_content(cr, uid, ids, context=context)
        res = self.pool.get('ir.actions.act_window').for_xml_id(cr, uid, 'stock', 'quantsact', context=context)
        res['domain'] = [('id', 'in', quants_ids)]
        return res

    def _get_product_total_qty(self, cr, uid, package_record, product_id, context=None):
        ''' find the total of given product 'product_id' inside the given package 'package_id'''
        quant_obj = self.pool.get('stock.quant')
        all_quant_ids = self.get_content(cr, uid, [package_record.id], context=context)
        total = 0
        for quant in quant_obj.browse(cr, uid, all_quant_ids, context=context):
            if quant.product_id.id == product_id:
                total += quant.qty
        return total


class stock_pack_operation(osv.osv):
    _name = "stock.pack.operation"
    _description = "Packing Operation"

    def _get_remaining_qty(self, cr, uid, ids, context=None):
        res = {}
        for ops in self.browse(cr, uid, ids, context=context):
            qty = ops.product_qty
            for quant in ops.reserved_quant_ids:
                qty -= quant.qty
            res[ops.id] = qty
        return res

    _columns = {
        'picking_id': fields.many2one('stock.picking', 'Stock Picking', help='The stock operation where the packing has been made', required=True),
        'product_id': fields.many2one('product.product', 'Product', ondelete="CASCADE"),  # 1
        'product_uom_id': fields.many2one('product.uom', 'Product Unit of Measure'),
        'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure'), required=True),
        'package_id': fields.many2one('stock.quant.package', 'Package'),  # 2
        'quant_id': fields.many2one('stock.quant', 'Quant'),  # 3
        'lot_id': fields.many2one('stock.production.lot', 'Lot/Serial Number'), 
        'result_package_id': fields.many2one('stock.quant.package', 'Container Package', help="If set, the operations are packed into this package", required=False, ondelete='cascade'),
        'date': fields.datetime('Date', required=True),
        'owner_id': fields.many2one('res.partner', 'Owner', help="Owner of the quants"),
        #'update_cost': fields.boolean('Need cost update'),
        'cost': fields.float("Cost", help="Unit Cost for this product line"),
        'currency': fields.many2one('res.currency', string="Currency", help="Currency in which Unit cost is expressed", ondelete='CASCADE'),
        'reserved_quant_ids': fields.one2many('stock.quant', 'reservation_op_id', string='Reserved Quants', readonly=True, help='Quants reserved for this operation'),
        'remaining_qty': fields.function(_get_remaining_qty, type='float', string='Remaining Qty'),
    }

    _defaults = {
        'date': fields.date.context_today,        
    }


    def _get_domain(self, cr, uid, ops, context=None):
        '''
            Gives domain for different 
        '''
        res = []
        if ops.package_id:
            res.append(('package_id', '=', ops.package_id.id), )
        if ops.lot_id:
            res.append(('lot_id', '=', ops.lot_id.id), )
        if ops.owner_id: 
            res.append(('owner_id', '=', ops.owner_id.id), )
        else:
            res.append(('owner_id', '=', False), )
        return res

    #TODO: this function can be refactored
    def _search_and_increment(self, cr, uid, picking_id, key, context=None):
        '''Search for an operation on an existing key in a picking, if it exists increment the qty (+1) otherwise create it

        :param key: tuple directly reusable in a domain
        context can receive a key 'current_package_id' with the package to consider for this operation
        returns True

        previously: returns the update to do in stock.move one2many field of picking (adapt remaining quantities) and to the list of package in the classic one2many syntax
                 (0, 0,  { values })    link to a new record that needs to be created with the given values dictionary
                 (1, ID, { values })    update the linked record with id = ID (write *values* on it)
                 (2, ID)                remove and delete the linked record with id = ID (calls unlink on ID, that will delete the object completely, and the link to it as well)
        '''
        quant_obj = self.pool.get('stock.quant')
        if context is None:
            context = {}

        #if current_package_id is given in the context, we increase the number of items in this package
        package_clause = [('result_package_id', '=', context.get('current_package_id', False))]
        existing_operation_ids = self.search(cr, uid, [('picking_id', '=', picking_id), key] + package_clause, context=context)
        if existing_operation_ids:
            #existing operation found for the given key and picking => increment its quantity
            operation_id = existing_operation_ids[0]
            qty = self.browse(cr, uid, operation_id, context=context).product_qty + 1
            self.write(cr, uid, operation_id, {'product_qty': qty}, context=context)
        else:
            #no existing operation found for the given key and picking => create a new one
            var_name, dummy, value = key
            uom_id = False
            if var_name == 'product_id':
                uom_id = self.pool.get('product.product').browse(cr, uid, value, context=context).uom_id.id
            elif var_name == 'quant_id':
                quant = quant_obj.browse(cr, uid, value, context=context)
                uom_id = quant.product_id.uom_id.id
            values = {
                'picking_id': picking_id,
                var_name: value,
                'product_qty': 1,
                'product_uom_id': uom_id,
            }
            operation_id = self.create(cr, uid, values, context=context)
            values.update({'id': operation_id})
        return True

class stock_warehouse_orderpoint(osv.osv):
    """
    Defines Minimum stock rules.
    """
    _name = "stock.warehouse.orderpoint"
    _description = "Minimum Inventory Rule"

    def _get_draft_procurements(self, cr, uid, ids, field_name, arg, context=None):
        if context is None:
            context = {}
        result = {}
        procurement_obj = self.pool.get('procurement.order')
        for orderpoint in self.browse(cr, uid, ids, context=context):
            procurement_ids = procurement_obj.search(cr, uid, [('state', '=', 'draft'), ('product_id', '=', orderpoint.product_id.id), ('location_id', '=', orderpoint.location_id.id)])
            result[orderpoint.id] = procurement_ids
        return result

    def _check_product_uom(self, cr, uid, ids, context=None):
        '''
        Check if the UoM has the same category as the product standard UoM
        '''
        if not context:
            context = {}

        for rule in self.browse(cr, uid, ids, context=context):
            if rule.product_id.uom_id.category_id.id != rule.product_uom.category_id.id:
                return False

        return True

    _columns = {
        'name': fields.char('Name', size=32, required=True),
        'active': fields.boolean('Active', help="If the active field is set to False, it will allow you to hide the orderpoint without removing it."),
        'logic': fields.selection([('max', 'Order to Max'), ('price', 'Best price (not yet active!)')], 'Reordering Mode', required=True),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse', required=True, ondelete="cascade"),
        'location_id': fields.many2one('stock.location', 'Location', required=True, ondelete="cascade"),
        'product_id': fields.many2one('product.product', 'Product', required=True, ondelete='cascade', domain=[('type', '!=', 'service')]),
        'product_uom': fields.many2one('product.uom', 'Product Unit of Measure', required=True),
        'product_min_qty': fields.float('Minimum Quantity', required=True,
            help="When the virtual stock goes below the Min Quantity specified for this field, OpenERP generates "\
            "a procurement to bring the forecasted quantity to the Max Quantity."),
        'product_max_qty': fields.float('Maximum Quantity', required=True,
            help="When the virtual stock goes below the Min Quantity, OpenERP generates "\
            "a procurement to bring the forecasted quantity to the Quantity specified as Max Quantity."),
        'qty_multiple': fields.integer('Qty Multiple', required=True,
            help="The procurement quantity will be rounded up to this multiple."),
        'procurement_id': fields.many2one('procurement.order', 'Latest procurement', ondelete="set null"),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'procurement_draft_ids': fields.function(_get_draft_procurements, type='many2many', relation="procurement.order", \
                                string="Related Procurement Orders", help="Draft procurement of the product and location of that orderpoint"),
    }
    _defaults = {
        'active': lambda *a: 1,
        'logic': lambda *a: 'max',
        'qty_multiple': lambda *a: 1,
        'name': lambda self, cr, uid, context: self.pool.get('ir.sequence').get(cr, uid, 'stock.orderpoint') or '',
        'product_uom': lambda self, cr, uid, context: context.get('product_uom', False),
        'company_id': lambda self, cr, uid, context: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.warehouse.orderpoint', context=context)
    }
    _sql_constraints = [
        ('qty_multiple_check', 'CHECK( qty_multiple > 0 )', 'Qty Multiple must be greater than zero.'),
    ]
    _constraints = [
        (_check_product_uom, 'You have to select a product unit of measure in the same category than the default unit of measure of the product', ['product_id', 'product_uom']),
    ]

    def default_get(self, cr, uid, fields, context=None):
        res = super(stock_warehouse_orderpoint, self).default_get(cr, uid, fields, context)
        # default 'warehouse_id' and 'location_id'
        if 'warehouse_id' not in res:
            warehouse = self.pool.get('ir.model.data').get_object(cr, uid, 'stock', 'warehouse0', context)
            res['warehouse_id'] = warehouse.id
        if 'location_id' not in res:
            warehouse = self.pool.get('stock.warehouse').browse(cr, uid, res['warehouse_id'], context)
            res['location_id'] = warehouse.lot_stock_id.id
        return res

    def onchange_warehouse_id(self, cr, uid, ids, warehouse_id, context=None):
        """ Finds location id for changed warehouse.
        @param warehouse_id: Changed id of warehouse.
        @return: Dictionary of values.
        """
        if warehouse_id:
            w = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context)
            v = {'location_id': w.lot_stock_id.id}
            return {'value': v}
        return {}

    def onchange_product_id(self, cr, uid, ids, product_id, context=None):
        """ Finds UoM for changed product.
        @param product_id: Changed id of product.
        @return: Dictionary of values.
        """
        if product_id:
            prod = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            d = {'product_uom': [('category_id', '=', prod.uom_id.category_id.id)]}
            v = {'product_uom': prod.uom_id.id}
            return {'value': v, 'domain': d}
        return {'domain': {'product_uom': []}}

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.orderpoint') or '',
        })
        return super(stock_warehouse_orderpoint, self).copy(cr, uid, id, default, context=context)



class stock_picking_type(osv.osv):
    _name = "stock.picking.type"
    _description = "The picking type determines the picking view"

    def __get_bar_values(self, cr, uid, obj, domain, read_fields, value_field, groupby_field, context=None):
        """ Generic method to generate data for bar chart values using SparklineBarWidget.
            This method performs obj.read_group(cr, uid, domain, read_fields, groupby_field).

            :param obj: the target model (i.e. crm_lead)
            :param domain: the domain applied to the read_group
            :param list read_fields: the list of fields to read in the read_group
            :param str value_field: the field used to compute the value of the bar slice
            :param str groupby_field: the fields used to group

            :return list section_result: a list of dicts: [
                                                {   'value': (int) bar_column_value,
                                                    'tootip': (str) bar_column_tooltip,
                                                }
                                            ]
        """
        month_begin = date.today().replace(day=1)
        section_result = [{
                            'value': 0,
                            'tooltip': (month_begin + relativedelta.relativedelta(months=-i)).strftime('%B'),
                            } for i in range(10, -1, -1)]
        group_obj = obj.read_group(cr, uid, domain, read_fields, groupby_field, context=context)
        for group in group_obj:
            group_begin_date = datetime.strptime(group['__domain'][0][2], tools.DEFAULT_SERVER_DATE_FORMAT)
            month_delta = relativedelta.relativedelta(month_begin, group_begin_date)
            section_result[10 - (month_delta.months + 1)] = {'value': group.get(value_field, 0), 'tooltip': group_begin_date.strftime('%B')}
        return section_result

    def _get_picking_data(self, cr, uid, ids, field_name, arg, context=None):
        obj = self.pool.get('stock.picking')
        res = dict.fromkeys(ids, False)
        month_begin = date.today().replace(day=1)
        groupby_begin = (month_begin + relativedelta.relativedelta(months=-4)).strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
        groupby_end = (month_begin + relativedelta.relativedelta(months=3)).strftime(tools.DEFAULT_SERVER_DATE_FORMAT)
        for id in ids:
            created_domain = [
                ('picking_type_id', '=', id),
                ('state', 'not in', ['done', 'cancel']),
                ('date', '>=', groupby_begin),
                ('date', '<', groupby_end),
            ]
            res[id] = self.__get_bar_values(cr, uid, obj, created_domain, ['date'], 'picking_type_id_count', 'date', context=context)
        return res

    def _get_picking_count(self, cr, uid, ids, field_names, arg, context=None):
        obj = self.pool.get('stock.picking')
        domains = {
            'count_picking_draft': [('state', '=', 'draft')],
            'count_picking_waiting': [('state','=','confirmed')],
            'count_picking_ready': [('state','=','assigned')],
            'count_picking': [('state','in',('assigned','waiting','confirmed'))],
            'count_picking_late': [('min_date','<', time.strftime('%Y-%m-%d %H:%M:%S')), ('state','in',('assigned','waiting','confirmed'))],
            'count_picking_backorders': [('backorder_id','<>', False), ('state','!=','done')],
        }
        result = {}
        for field in domains:
            data = obj.read_group(cr, uid, domains[field] +
                [('state', 'not in',('done','cancel')), ('picking_type_id', 'in', ids)],
                ['picking_type_id'], ['picking_type_id'], context=context)
            count = dict(map(lambda x: (x['picking_type_id'] and x['picking_type_id'][0], x['picking_type_id_count']), data))
            for tid in ids:
                result.setdefault(tid, {})[field] = count.get(tid, 0)
        for tid in ids:
            if result[tid]['count_picking']:
                result[tid]['rate_picking_late'] = result[tid]['count_picking_late'] *100 / result[tid]['count_picking']
                result[tid]['rate_picking_backorders'] = result[tid]['count_picking_backorders'] *100 / (result[tid]['count_picking'] + result[tid]['count_picking_draft'])
            else:
                result[tid]['rate_picking_late'] = 0
                result[tid]['rate_picking_backorders'] = 0
        return result

    #TODO: not returning valus in required format to show in sparkline library,just added latest_picking_waiting need to add proper logic.
    def _get_picking_history(self, cr, uid, ids, field_names, arg, context=None):
        obj = self.pool.get('stock.picking')
        result = {}
        for id in ids:
            result[id] = {
                'latest_picking_late': [],
                'latest_picking_backorders': [],
                'latest_picking_waiting': []
            }
        for type_id in ids:
            pick_ids = obj.search(cr, uid, [('state', '=','done'), ('picking_type_id','=',type_id)], limit=12, order="date desc", context=context)
            for pick in obj.browse(cr, uid, pick_ids, context=context):
                result[type_id]['latest_picking_late'] = cmp(pick.date[:10], time.strftime('%Y-%m-%d'))
                result[type_id]['latest_picking_backorders'] = bool(pick.backorder_id)
                result[type_id]['latest_picking_waiting'] = cmp(pick.date[:10], time.strftime('%Y-%m-%d'))
        return result

    def onchange_picking_code(self, cr, uid, ids, picking_code=False):
        if not picking_code:
            return False
        
        obj_data = self.pool.get('ir.model.data')
        stock_loc = obj_data.get_object_reference(cr, uid, 'stock','stock_location_stock')[1]
        
        result = {
            'default_location_src_id': stock_loc,
            'default_location_dest_id': stock_loc,
        }
        if picking_code == 'incoming':
            result['default_location_src_id'] = obj_data.get_object_reference(cr, uid, 'stock','stock_location_suppliers')[1]
            return {'value': result}
        if picking_code == 'outgoing':
            result['default_location_dest_id'] = obj_data.get_object_reference(cr, uid, 'stock','stock_location_customers')[1]
            return {'value': result}
        else:
            return {'value': result}

    def _get_name(self, cr, uid, ids, field_names, arg, context=None):
        return dict(self.name_get(cr, uid, ids, context=context))

    def name_get(self, cr, uid, ids, context=None):
        """Overides orm name_get method to display 'Warehouse_name: PickingType_name' """
        if context is None:
            context = {}
        if not isinstance(ids, list):
            ids = [ids]
        res = []
        if not ids:
            return res
        for record in self.browse(cr, uid, ids, context=context):
            name = record.name
            if record.warehouse_id:
                name = record.warehouse_id.name + ': ' +name
            if context.get('special_shortened_wh_name'):
                if record.warehouse_id:
                    name = record.warehouse_id.name
                else:
                    name = _('Customer') + ' (' + record.name + ')'
            res.append((record.id, name))
        return res

    def _default_warehouse(self, cr, uid, context=None):
        user = self.pool.get('res.users').browse(cr, uid, uid, context)
        res = self.pool.get('stock.warehouse').search(cr, uid, [('company_id', '=', user.company_id.id)], limit=1, context=context)
        return res and res[0] or False

    _columns = {
        'name': fields.char('name', translate=True, required=True),
        'complete_name': fields.function(_get_name, type='char', string='Name'),
        'pack': fields.boolean('Prefill Pack Operations', help='This picking type needs packing interface'),
        'auto_force_assign': fields.boolean('Automatic Availability', help='This picking type does\'t need to check for the availability in source location.'),
        'color': fields.integer('Color Index'),
        'delivery': fields.boolean('Print delivery'),
        'sequence_id': fields.many2one('ir.sequence', 'Sequence', required=True),
        'default_location_src_id': fields.many2one('stock.location', 'Default Source Location'),
        'default_location_dest_id': fields.many2one('stock.location', 'Default Destination Location'),
        #TODO: change field name to "code" as it's not a many2one anymore
        'code_id': fields.selection([('incoming', 'Suppliers'), ('outgoing', 'Customers'), ('internal', 'Internal')], 'Picking type code', required=True),
        'return_picking_type_id': fields.many2one('stock.picking.type', 'Picking Type for Returns'),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse'),
        'active': fields.boolean('Active'),

        # Statistics for the kanban view
        'weekly_picking': fields.function(_get_picking_data,
            type='string',
            string='Scheduled pickings per week'),

        'count_picking_draft': fields.function(_get_picking_count,
            type='integer', multi='_get_picking_count'),
        'count_picking_ready': fields.function(_get_picking_count,
            type='integer', multi='_get_picking_count'),
        'count_picking': fields.function(_get_picking_count,
            type='integer', multi='_get_picking_count'),
        'count_picking_waiting': fields.function(_get_picking_count,
            type='integer', multi='_get_picking_count'),
        'count_picking_late': fields.function(_get_picking_count,
            type='integer', multi='_get_picking_count'),
        'count_picking_backorders': fields.function(_get_picking_count,
            type='integer', multi='_get_picking_count'),

        'rate_picking_late': fields.function(_get_picking_count,
            type='integer', multi='_get_picking_count'),
        'rate_picking_backorders': fields.function(_get_picking_count,
            type='integer', multi='_get_picking_count'),

        'latest_picking_late': fields.function(_get_picking_history,
            type='string', multi='_get_picking_history'),
        'latest_picking_backorders': fields.function(_get_picking_history,
            type='string', multi='_get_picking_history'),
        'latest_picking_waiting': fields.function(_get_picking_history,
            type='string', multi='_get_picking_history'),

    }
    _defaults = {
        'warehouse_id': _default_warehouse,
        'active': True,
    }


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
