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

from osv import fields
from osv import osv
import netsvc


class StockMove(osv.osv):
    _inherit = 'stock.move'
    
    _columns = {
        'production_id': fields.many2one('mrp.production', 'Production', select=True),
    }
    
    def _action_explode(self, cr, uid, move, context={}):
        """ Explodes pickings.
        @param move: Stock moves
        @return: True
        """
        bom_obj = self.pool.get('mrp.bom')
        move_obj = self.pool.get('stock.move')
        procurement_obj = self.pool.get('procurement.order')
        product_obj = self.pool.get('product.product')
        wf_service = netsvc.LocalService("workflow")
        if move.product_id.supply_method == 'produce' and move.product_id.procure_method == 'make_to_order':
            bis = bom_obj.search(cr, uid, [
                ('product_id','=',move.product_id.id),
                ('bom_id','=',False),
                ('type','=','phantom')])
            if bis:
                factor = move.product_qty
                bom_point = bom_obj.browse(cr, uid, bis[0])
                res = bom_obj._bom_explode(cr, uid, bom_point, factor, [])
                dest = move.product_id.product_tmpl_id.property_stock_production.id
                state = 'confirmed'
                if move.state == 'assigned':
                    state = 'assigned'
                for line in res[0]:                    
                    valdef = {
                        'picking_id': move.picking_id.id,
                        'product_id': line['product_id'],
                        'product_uom': line['product_uom'],
                        'product_qty': line['product_qty'],
                        'product_uos': line['product_uos'],
                        'product_uos_qty': line['product_uos_qty'],
                        'move_dest_id': move.id,
                        'state': state,
                        'name': line['name'],
                        'location_dest_id': dest,
                        'move_history_ids': [(6,0,[move.id])],
                        'move_history_ids2': [(6,0,[])],
                        'procurements': [],
                    }
                    mid = move_obj.copy(cr, uid, move.id, default=valdef)
                    prodobj = product_obj.browse(cr, uid, line['product_id'], context=context)
                    proc_id = procurement_obj.create(cr, uid, {
                        'name': (move.picking_id.origin or ''),
                        'origin': (move.picking_id.origin or ''),
                        'date_planned': move.date,
                        'product_id': line['product_id'],
                        'product_qty': line['product_qty'],
                        'product_uom': line['product_uom'],
                        'product_uos_qty': line['product_uos'] and line['product_uos_qty'] or False,
                        'product_uos':  line['product_uos'],
                        'location_id': move.location_id.id,
                        'procure_method': prodobj.procure_method,
                        'move_id': mid,
                    })
                    wf_service.trg_validate(uid, 'procurement.order', proc_id, 'button_confirm', cr)
                move_obj.write(cr, uid, [move.id], {
                    'location_id': move.location_dest_id.id,
                    'auto_validate': True,
                    'picking_id': False,
                    'state': 'waiting'
                })
                for m in procurement_obj.search(cr, uid, [('move_id','=',move.id)], context):
                    wf_service.trg_validate(uid, 'procurement.order', m, 'button_wait_done', cr)
        return True
    
    def action_consume(self, cr, uid, ids, product_qty, location_id=False, context=None): 
        """ Consumed product with specific quatity from specific source location.
        @param product_qty: Consumed product quantity
        @param location_id: Source location
        @return: Consumed lines
        """       
        res = []
        production_obj = self.pool.get('mrp.production')
        wf_service = netsvc.LocalService("workflow")
        for move in self.browse(cr, uid, ids):
            new_moves = super(StockMove, self).action_consume(cr, uid, [move.id], product_qty, location_id, context=context)
            production_ids = production_obj.search(cr, uid, [('move_lines', 'in', [move.id])])
            for prod in production_obj.browse(cr, uid, production_ids, context=context):
                if prod.state == 'confirmed':
                    production_obj.force_production(cr, uid, [prod.id])
                wf_service.trg_validate(uid, 'mrp.production', prod.id, 'button_produce', cr)
            for new_move in new_moves:
                production_obj.write(cr, uid, production_ids, {'move_lines': [(4, new_move)]})
                res.append(new_move)
        return res
    
    def action_scrap(self, cr, uid, ids, product_qty, location_id, context=None):
        """ Move the scrap/damaged product into scrap location
        @param product_qty: Scraped product quantity
        @param location_id: Scrap location
        @return: Scraped lines
        """  
        res = []
        production_obj = self.pool.get('mrp.production')
        wf_service = netsvc.LocalService("workflow")
        for move in self.browse(cr, uid, ids):
            new_moves = super(StockMove, self).action_scrap(cr, uid, [move.id], product_qty, location_id, context=context)
            production_ids = production_obj.search(cr, uid, [('move_lines', 'in', [move.id])])
            for prod_id in production_ids:
                wf_service.trg_validate(uid, 'mrp.production', prod_id, 'button_produce', cr)
            for new_move in new_moves:
                production_obj.write(cr, uid, production_ids, {'move_lines': [(4, new_move)]})
                res.append(new_move)
        return {}

StockMove()


class StockPicking(osv.osv):
    _inherit = 'stock.picking'

    #
    # Explode picking by replacing phantom BoMs
    #
    def action_explode(self, cr, uid, picks, *args):
        """ Explodes picking by replacing phantom BoMs
        @param picks: Picking ids. 
        @param *args: Arguments
        @return: Picking ids.
        """  
        move_obj = self.pool.get('stock.move')
        for move in move_obj.browse(cr, uid, picks):
            move_obj._action_explode(cr, uid, move)
        return picks

StockPicking()


class spilt_in_production_lot(osv.osv_memory):
    _inherit = "stock.move.split"
    
    def split(self, cr, uid, ids, move_ids, context=None):
        """ Splits move lines into given quantities.
        @param move_ids: Stock moves.
        @return: List of new moves.
        """  
        production_obj = self.pool.get('mrp.production')
        move_obj = self.pool.get('stock.move')  
        res = []      
        for move in move_obj.browse(cr, uid, move_ids, context=context):
            new_moves = super(spilt_in_production_lot, self).split(cr, uid, ids, move_ids, context=context)
            production_ids = production_obj.search(cr, uid, [('move_lines', 'in', [move.id])])
            for new_move in new_moves:
                production_obj.write(cr, uid, production_ids, {'move_lines': [(4, new_move)]})                
        return res
    
spilt_in_production_lot()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
