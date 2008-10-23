# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2004-2008 TINY SPRL. (http://tiny.be) All Rights Reserved.
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
#
##############################################################################

from osv import fields
from osv import osv
import ir

import netsvc
import time
from mx import DateTime

#----------------------------------------------------------
# Workcenters
#----------------------------------------------------------
# capacity_hour : capacity per hour. default: 1.0.
#          Eg: If 5 concurrent operations at one time: capacity = 5 (because 5 employees)
# unit_per_cycle : how many units are produced for one cycle
#
# TODO: Work Center may be recursive ?
#
class mrp_workcenter(osv.osv):
    _name = 'mrp.workcenter'
    _description = 'Workcenter'
    _columns = {
        'name': fields.char('Workcenter Name', size=64, required=True),
        'active': fields.boolean('Active'),
        'type': fields.selection([('machine','Machine'),('hr','Human Resource'),('tool','Tool')], 'Type', required=True),
        'code': fields.char('Code', size=16),
        'timesheet_id': fields.many2one('hr.timesheet.group', 'Working Time', help="The normal working time of the workcenter."),
        'note': fields.text('Description', help="Description of the workcenter. Explain here what's a cycle according to this workcenter."),

        'capacity_per_cycle': fields.float('Capacity per Cycle', help="Number of operation this workcenter can do in parallel. If this workcenter represent a team of 5 workers, the capacity per cycle is 5."),

        'time_cycle': fields.float('Time for 1 cycle (hour)', help="Time in hours for doing one cycle."),
        'time_start': fields.float('Time before prod.', help="Time in hours for the setup."),
        'time_stop': fields.float('Time after prod.', help="Time in hours for the cleaning."),
        'time_efficiency': fields.float('Time Efficiency', help="Factor that multiplies all times expressed in the workcenter."),

        'costs_hour': fields.float('Cost per hour'),
        'costs_hour_account_id': fields.many2one('account.analytic.account', 'Hour Account', domain=[('type','<>','view')],
            help="Complete this only if you want automatic analytic accounting entries on production orders."),
        'costs_cycle': fields.float('Cost per cycle'),
        'costs_cycle_account_id': fields.many2one('account.analytic.account', 'Cycle Account', domain=[('type','<>','view')],
            help="Complete this only if you want automatic analytic accounting entries on production orders."),
        'costs_journal_id': fields.many2one('account.analytic.journal', 'Analytic Journal'),
        'costs_general_account_id': fields.many2one('account.account', 'General Account', domain=[('type','<>','view')]),
    }
    _defaults = {
        'active': lambda *a: 1,
        'type': lambda *a: 'machine',
        'time_efficiency': lambda *a: 1.0,
        'capacity_per_cycle': lambda *a: 1.0,
    }
mrp_workcenter()


class mrp_property_group(osv.osv):
    _name = 'mrp.property.group'
    _description = 'Property Group'
    _columns = {
        'name': fields.char('Property Group', size=64, required=True),
        'description': fields.text('Description'),
    }
mrp_property_group()

class mrp_property(osv.osv):
    _name = 'mrp.property'
    _description = 'Property'
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'composition': fields.selection([('min','min'),('max','max'),('plus','plus')], 'Properties composition', required=True, help="Not used in computations, for information purpose only."),
        'group_id': fields.many2one('mrp.property.group', 'Property Group', required=True),
        'description': fields.text('Description'),
    }
    _defaults = {
        'composition': lambda *a: 'min',
    }
mrp_property()

class mrp_routing(osv.osv):
    _name = 'mrp.routing'
    _description = 'Routing'
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'active': fields.boolean('Active'),
        'code': fields.char('Code', size=8),

        'note': fields.text('Description'),
        'workcenter_lines': fields.one2many('mrp.routing.workcenter', 'routing_id', 'Workcenters'),

        'location_id': fields.many2one('stock.location', 'Production Location',
            help="Keep empty if you produce at the location where the finnished products are needed." \
                "Put a location if you produce at a fixed location. This can be a partner location " \
                "if you subcontract the manufacturing operations."
        ),
    }
    _defaults = {
        'active': lambda *a: 1,
    }
mrp_routing()

class mrp_routing_workcenter(osv.osv):
    _name = 'mrp.routing.workcenter'
    _description = 'Routing workcenter usage'
    _columns = {
        'workcenter_id': fields.many2one('mrp.workcenter', 'Workcenter', required=True),
        'name': fields.char('Name', size=64, required=True),
        'sequence': fields.integer('Sequence'),
        'cycle_nbr': fields.float('Number of Cycle', required=True),
        'hour_nbr': fields.float('Number of Hours', required=True),
        'routing_id': fields.many2one('mrp.routing', 'Parent Routing', select=True),
        'note': fields.text('Description')
    }
    _defaults = {
        'cycle_nbr': lambda *a: 1.0,
        'hour_nbr': lambda *a: 0.0,
    }
mrp_routing_workcenter()

class mrp_bom(osv.osv):
    _name = 'mrp.bom'
    _description = 'Bill of Material'
    def _child_compute(self, cr, uid, ids, name, arg, context={}):
        result = {}
        for bom in self.browse(cr, uid, ids, context=context):
            result[bom.id] = map(lambda x: x.id, bom.bom_lines)
            ok = ((name=='child_complete_ids') and (bom.product_id.supply_method=='produce'))
            if bom.type=='phantom' or ok:
                sids = self.pool.get('mrp.bom').search(cr, uid, [('bom_id','=',False),('product_id','=',bom.product_id.id)])
                if sids:
                    bom2 = self.pool.get('mrp.bom').browse(cr, uid, sids[0], context=context)
                    result[bom.id] += map(lambda x: x.id, bom2.bom_lines)
        return result
    def _compute_type(self, cr, uid, ids, field_name, arg, context):
        res = dict(map(lambda x: (x,''), ids))
        for line in self.browse(cr, uid, ids):
            if line.type=='phantom' and not line.bom_id:
                res[line.id] = 'set'
                continue
            if line.bom_lines or line.type=='phantom':
                continue
            if line.product_id.supply_method=='produce':
                if line.product_id.procure_method=='make_to_stock':
                    res[line.id] = 'stock'
                else:
                    res[line.id] = 'order'
        return res
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=16),
        'active': fields.boolean('Active'),
        'type': fields.selection([('normal','Normal BoM'),('phantom','Sets / Phantom')], 'BoM Type', required=True, help="Use a phantom bill of material in lines that have a sub-bom and that have to be automatically computed in one line, without having two production orders."),

        'method': fields.function(_compute_type, string='Method', method=True, type='selection', selection=[('',''),('stock','On Stock'),('order','On Order'),('set','Set / Pack')]),

        'date_start': fields.date('Valid From', help="Validity of this BoM or component. Keep empty if it's always valid."),
        'date_stop': fields.date('Valid Until', help="Validity of this BoM or component. Keep empty if it's always valid."),
        'sequence': fields.integer('Sequence'),
        'position': fields.char('Internal Ref.', size=64, help="Reference to a position in an external plan."),
        'product_id': fields.many2one('product.product', 'Product', required=True),
        'product_uos_qty': fields.float('Product UOS Qty'),
        'product_uos': fields.many2one('product.uom', 'Product UOS'),
        'product_qty': fields.float('Product Qty', required=True),
        'product_uom': fields.many2one('product.uom', 'Product UOM', required=True),
        'product_rounding': fields.float('Product Rounding'),
        'product_efficiency': fields.float('Product Efficiency', required=True),
        'bom_lines': fields.one2many('mrp.bom', 'bom_id', 'BoM Lines'),
        'bom_id': fields.many2one('mrp.bom', 'Parent BoM', ondelete='cascade', select=True),
        'routing_id': fields.many2one('mrp.routing', 'Routing', help="The list of operations (list of workcenters) to produce the finnished product. The routing is mainly used to compute workcenter costs during operations and to plan futur loads on workcenters based on production plannification."),
        'property_ids': fields.many2many('mrp.property', 'mrp_bom_property_rel', 'bom_id','property_id', 'Properties'),
        'revision_ids': fields.one2many('mrp.bom.revision', 'bom_id', 'BoM Revisions'),
        'revision_type': fields.selection([('numeric','numeric indices'),('alpha','alphabetical indices')], 'indice type'),
        'child_ids': fields.function(_child_compute,relation='mrp.bom', method=True, string="BoM Hyerarchy", type='many2many'),
        'child_complete_ids': fields.function(_child_compute,relation='mrp.bom', method=True, string="BoM Hyerarchy", type='many2many')
    }
    _defaults = {
        'active': lambda *a: 1,
        'product_efficiency': lambda *a: 1.0,
        'product_qty': lambda *a: 1.0,
        'product_rounding': lambda *a: 1.0,
        'type': lambda *a: 'normal',
    }
    _order = "sequence"
    _sql_constraints = [
        ('bom_qty_zero', 'CHECK (product_qty>0)',  'All product quantities must be greater than 0 !'),
    ]

    def _check_recursion(self, cr, uid, ids):
        level = 500
        while len(ids):
            cr.execute('select distinct bom_id from mrp_bom where id in ('+','.join(map(str,ids))+')')
            ids = filter(None, map(lambda x:x[0], cr.fetchall()))
            if not level:
                return False
            level -= 1
        return True
    _constraints = [
        (_check_recursion, 'Error ! You can not create recursive BoM.', ['parent_id'])
    ]


    def onchange_product_id(self, cr, uid, ids, product_id, name, context={}):
        if product_id:
            prod=self.pool.get('product.product').browse(cr,uid,[product_id])[0]
            v = {'product_uom':prod.uom_id.id}
            if not name:
                v['name'] = prod.name
            return {'value': v}
        return {}

    def _bom_find(self, cr, uid, product_id, product_uom, properties = []):
        bom_result = False
        # Why searching on BoM without parent ?
        cr.execute('select id from mrp_bom where product_id=%d and bom_id is null order by sequence', (product_id,))
        ids = map(lambda x: x[0], cr.fetchall())
        max_prop = 0
        result = False
        for bom in self.pool.get('mrp.bom').browse(cr, uid, ids):
            prop = 0
            for prop_id in bom.property_ids:
                if prop_id.id in properties:
                    prop+=1
            if (prop>max_prop) or ((max_prop==0) and not result):
                result = bom.id
        return result

    def _bom_explode(self, cr, uid, bom, factor, properties, addthis=False, level=10):
        factor = factor / (bom.product_efficiency or 1.0)
        factor = rounding(factor, bom.product_rounding)
        if factor<bom.product_rounding:
            factor = bom.product_rounding
        result = []
        result2 = []
        if bom.type=='phantom' and not bom.bom_lines:
            newbom = self._bom_find(cr, uid, bom.product_id.id, bom.product_uom.id, properties)
            if newbom:
                res = self._bom_explode(cr, uid, self.browse(cr, uid, [newbom])[0], factor*bom.product_qty, properties, addthis=True, level=level+10)
                result = result + res[0]
                result2 = result2 + res[1]
            else:
                return [],[]
        else:
            if addthis and not bom.bom_lines:
                result.append(
                {
                    'name': bom.product_id.name,
                    'product_id': bom.product_id.id,
                    'product_qty': bom.product_qty * factor,
                    'product_uom': bom.product_uom.id,
                    'product_uos_qty': bom.product_uos and bom.product_uos_qty * factor or False,
                    'product_uos': bom.product_uos and bom.product_uos.id or False,
                })
            if bom.routing_id:
                for wc_use in bom.routing_id.workcenter_lines:
                    wc = wc_use.workcenter_id
                    d, m = divmod(factor, wc_use.workcenter_id.capacity_per_cycle)
                    cycle = (d + (m and 1.0 or 0.0)) * wc_use.cycle_nbr
                    result2.append({
                        'name': bom.routing_id.name,
                        'workcenter_id': wc.id,
                        'sequence': level,
                        'cycle': cycle,
                        'hour': wc_use.hour_nbr + (wc.time_start+wc.time_stop+cycle*wc.time_cycle) * (wc.time_efficiency or 1.0),
                    })
            for bom2 in bom.bom_lines:
                res = self._bom_explode(cr, uid, bom2, factor, properties, addthis=True, level=level+10)
                result = result + res[0]
                result2 = result2 + res[1]
        return result, result2

    def set_indices(self, cr, uid, ids, context = {}):
        if not ids or (ids and not ids[0]):
            return True
        res = self.read(cr, uid, ids, ['revision_ids', 'revision_type'])
        rev_ids = res[0]['revision_ids']
        idx = 1
        new_idx = []
        for rev_id in rev_ids:
            if res[0]['revision_type'] == 'numeric':
                self.pool.get('mrp.bom.revision').write(cr, uid, [rev_id], {'indice' : idx})
            else:
                self.pool.get('mrp.bom.revision').write(cr, uid, [rev_id], {'indice' : "%c"%(idx+96,)})
            idx+=1
        return True

mrp_bom()

class mrp_bom_revision(osv.osv):
    _name = 'mrp.bom.revision'
    _description = 'Bill of material revisions'
    _columns = {
        'name': fields.char('Modification name', size=64, required=True),
        'description': fields.text('Description'),
        'date': fields.date('Modification Date'),
        'indice': fields.char('Revision', size=16),
        'last_indice': fields.char('last indice', size=64),
        'author_id': fields.many2one('res.users', 'Author'),
        'bom_id': fields.many2one('mrp.bom', 'BoM', select=True),
    }

    _defaults = {
        'author_id': lambda x,y,z,c: z,
        'date': lambda *a: time.strftime('%Y-%m-%d'),
    }

mrp_bom_revision()

def rounding(f, r):
    if not r:
        return f
    return round(f / r) * r

class mrp_production(osv.osv):
    _name = 'mrp.production'
    _description = 'Production'
    _date_name  = 'date_planned'

    def _get_sale_order(self,cr,uid,ids,field_name=False):
        move_obj=self.pool.get('stock.move')
        def get_parent_move(move_id):
            move = move_obj.browse(cr,uid,move_id)
            if move.move_dest_id:
                return get_parent_move(move.move_dest_id.id)
            return move_id
        productions=self.read(cr,uid,ids,['id','move_prod_id'])
        res={}
        for production in productions:
            res[production['id']]=False
            if production.get('move_prod_id',False):
                parent_move_line=get_parent_move(production['move_prod_id'][0])
                if parent_move_line:
                    move = move_obj.browse(cr,uid,parent_move_line)
                    if field_name=='name':
                        res[production['id']]=move.sale_line_id and move.sale_line_id.order_id.name or False
                    if field_name=='client_order_ref':
                        res[production['id']]=move.sale_line_id and move.sale_line_id.order_id.client_order_ref or False
        return res

    def _sale_name_calc(self, cr, uid, ids, prop, unknow_none, unknow_dict):
        return self._get_sale_order(cr,uid,ids,field_name='name')

    def _sale_ref_calc(self, cr, uid, ids, prop, unknow_none, unknow_dict):
        return self._get_sale_order(cr,uid,ids,field_name='client_order_ref')

    _columns = {
        'name': fields.char('Reference', size=64, required=True),
        'origin': fields.char('Origin', size=64),
        'priority': fields.selection([('0','Not urgent'),('1','Normal'),('2','Urgent'),('3','Very Urgent')], 'Priority'),

        'product_id': fields.many2one('product.product', 'Product', required=True, domain=[('type','<>','service')]),
        'product_qty': fields.float('Product Qty', required=True),
        'product_uom': fields.many2one('product.uom', 'Product UOM', required=True),
        'product_uos_qty': fields.float('Product Qty'),
        'product_uos': fields.many2one('product.uom', 'Product UOM'),

        'location_src_id': fields.many2one('stock.location', 'Raw Products Location', required=True),
        'location_dest_id': fields.many2one('stock.location', 'Finnished Products Location', required=True),

        'date_planned': fields.datetime('Scheduled date', required=True, select=1),
        'date_start': fields.datetime('Start Date'),
        'date_finnished': fields.datetime('End Date'),

        'bom_id': fields.many2one('mrp.bom', 'Bill of Material', domain=[('bom_id','=',False)]),

        'picking_id': fields.many2one('stock.picking', 'Packing list', readonly=True),
        'move_prod_id': fields.many2one('stock.move', 'Move product', readonly=True),
        'move_lines': fields.many2many('stock.move', 'mrp_production_move_ids', 'production_id', 'move_id', 'Products Consummed'),

        'move_created_ids': fields.one2many('stock.move', 'production_id', 'Moves Created'),
        'product_lines': fields.one2many('mrp.production.product.line', 'production_id', 'Scheduled goods'),
        'workcenter_lines': fields.one2many('mrp.production.workcenter.line', 'production_id', 'Workcenters Utilisation'),

        'state': fields.selection([('draft','Draft'),('picking_except', 'Packing Exception'),('confirmed','Waiting Goods'),('ready','Ready to Produce'),('in_production','In Production'),('cancel','Canceled'),('done','Done')],'Status', readonly=True),
        'sale_name': fields.function(_sale_name_calc, method=True, type='char', string='Sale Name'),
        'sale_ref': fields.function(_sale_ref_calc, method=True, type='char', string='Sale Ref'),
    }
    _defaults = {
        'priority': lambda *a: '1',
        'state': lambda *a: 'draft',
        'date_planned': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'product_qty':  lambda *a: 1.0,
        'name': lambda x,y,z,c: x.pool.get('ir.sequence').get(y,z,'mrp.production') or '/',
    }
    _order = 'date_planned asc, priority desc';

    def location_id_change(self, cr, uid, ids, src, dest, context={}):
        if dest:
            return {}
        if src:
            return {'value': {'location_dest_id': src}}
        return {}

    def product_id_change(self, cr, uid, ids, product):
        if not product:
            return {}
        res = self.pool.get('product.product').read(cr, uid, [product], ['uom_id'])[0]
        uom = res['uom_id'] and res['uom_id'][0]
        result = {'product_uom':uom}
        return {'value':result}

    def action_picking_except(self, cr, uid, ids):
        self.write(cr, uid, ids, {'state':'picking_except'})
        return True

    def action_compute(self, cr, uid, ids, properties=[]):
        results = []
        for production in self.browse(cr, uid, ids):
            cr.execute('delete from mrp_production_product_line where production_id=%d', (production.id,))
            cr.execute('delete from mrp_production_workcenter_line where production_id=%d', (production.id,))
            bom_point = production.bom_id
            bom_id = production.bom_id.id
            if not bom_point:
                bom_id = self.pool.get('mrp.bom')._bom_find(cr, uid, production.product_id.id, production.product_uom.id, properties)
                if bom_id:
                    self.write(cr, uid, [production.id], {'bom_id': bom_id})
                    bom_point = self.pool.get('mrp.bom').browse(cr, uid, [bom_id])[0]

            if not bom_id:
                raise osv.except_osv('Error', "Couldn't find bill of material for product")

            #if bom_point.routing_id and bom_point.routing_id.location_id:
            #   self.write(cr, uid, [production.id], {'location_src_id': bom_point.routing_id.location_id.id})

            factor = production.product_qty * production.product_uom.factor / bom_point.product_uom.factor
            res = self.pool.get('mrp.bom')._bom_explode(cr, uid, bom_point, factor / bom_point.product_qty, properties)
            results = res[0]
            results2 = res[1]
            for line in results:
                line['production_id'] = production.id
                self.pool.get('mrp.production.product.line').create(cr, uid, line)
            for line in results2:
                line['production_id'] = production.id
                self.pool.get('mrp.production.workcenter.line').create(cr, uid, line)
        return len(results)

    def action_cancel(self, cr, uid, ids):
        for production in self.browse(cr, uid, ids):
            if production.move_created_ids:
                self.pool.get('stock.move').action_cancel(cr, uid, [x.id for x in production.move_created_ids])
            self.pool.get('stock.move').action_cancel(cr, uid, [x.id for x in production.move_lines])
        self.write(cr, uid, ids, {'state':'cancel','move_lines':[(6,0,[])]})
        return True

    #XXX: may be a bug here; lot_lines are unreserved for a few seconds;
    #     between the end of the picking list and the call to this function
    def action_ready(self, cr, uid, ids):
        self.write(cr, uid, ids, {'state':'ready'})
        for production in self.browse(cr, uid, ids):
            if production.move_prod_id:
                self.pool.get('stock.move').write(cr, uid, [production.move_prod_id.id],
                        {'location_id':production.location_dest_id.id})
        return True

    #TODO Review materials in function in_prod and prod_end.
    def action_production_end(self, cr, uid, ids):
        move_ids = []
        for production in self.browse(cr, uid, ids):
            for res in production.move_lines:
                for move in production.move_created_ids:
                    #XXX must use the orm
                    cr.execute('INSERT INTO stock_move_history_ids \
                            (parent_id, child_id) VALUES (%d,%d)',
                            (res.id, move.id))
                move_ids.append(res.id)
            if production.move_created_ids:
                #TODO There we should handle the residus move creation
                vals= {'state':'confirmed'}
                new_moves = [x.id for x in production.move_created_ids]
                self.pool.get('stock.move').write(cr, uid, new_moves, vals)
            else:
                #XXX Why is it there ? Aren't we suppose to already have a created_move ?
                source = production.product_id.product_tmpl_id.property_stock_production.id
                vals = {
                    'name':'PROD:'+production.name,
                    'date_planned': production.date_planned,
                    'product_id': production.product_id.id,
                    'product_qty': production.product_qty,
                    'product_uom': production.product_uom.id,
                    'product_uos_qty': production.product_uos and production.product_uos_qty or False,
                    'product_uos': production.product_uos and production.product_uos.id or False,
                    'location_id': source,
                    'location_dest_id': production.location_dest_id.id,
                    'move_dest_id': production.move_prod_id.id,
                    'state': 'confirmed'
                }
                new_moves = [self.pool.get('stock.move').create(cr, uid, vals)]
                self.write(cr, uid, [production.id],
                        {'move_created_ids': [(6, 'WTF', new_moves)]})
            if not production.date_finnished:
                self.write(cr, uid, [production.id],
                        {'date_finnished': time.strftime('%Y-%m-%d %H:%M:%S')})
            self.pool.get('stock.move').check_assign(cr, uid, new_moves)
            self.pool.get('stock.move').action_done(cr, uid, new_moves)
            self._costs_generate(cr, uid, production)
        self.pool.get('stock.move').action_done(cr, uid, move_ids)
        self.write(cr,  uid, ids, {'state': 'done'})
        return True

    def _costs_generate(self, cr, uid, production):
        amount = 0.0
        for wc_line in production.workcenter_lines:
            wc = wc_line.workcenter_id
            if wc.costs_journal_id and wc.costs_general_account_id:
                value = wc_line.hour * wc.costs_hour
                account = wc.costs_hour_account_id.id
                if value and account:
                    amount += value
                    self.pool.get('account.analytic.line').create(cr, uid, {
                        'name': wc_line.name+' (H)',
                        'amount': value,
                        'account_id': account,
                        'general_account_id': wc.costs_general_account_id.id,
                        'journal_id': wc.costs_journal_id.id,
                        'code': wc.code
                    } )
            if wc.costs_journal_id and wc.costs_general_account_id:
                value = wc_line.cycle * wc.costs_cycle
                account = wc.costs_cycle_account_id.id
                if value and account:
                    amount += value
                    self.pool.get('account.analytic.line').create(cr, uid, {
                        'name': wc_line.name+' (C)',
                        'amount': value,
                        'account_id': account,
                        'general_account_id': wc.costs_general_account_id.id,
                        'journal_id': wc.costs_journal_id.id,
                        'code': wc.code
                    } )
        return amount

    def action_in_production(self, cr, uid, ids):
        move_ids = []
        for production in self.browse(cr, uid, ids):
            for res in production.move_lines:
                move_ids.append(res.id)
            if not production.date_start:
                self.write(cr, uid, [production.id],
                        {'date_start': time.strftime('%Y-%m-%d %H:%M:%S')})
        self.pool.get('stock.move').action_done(cr, uid, move_ids)
        self.write(cr, uid, ids, {'state': 'in_production'})
        return True

    def test_if_product(self, cr, uid, ids):
        res = True
        for production in self.browse(cr, uid, ids):
            if not production.product_lines:
                if not self.action_compute(cr, uid, [production.id]):
                    res = False
        return res

    def _get_auto_picking(self, cr, uid, production):
        return True

    def action_confirm(self, cr, uid, ids):
        picking_id=False
        for production in self.browse(cr, uid, ids):
            if not production.product_lines:
                self.action_compute(cr, uid, [production.id])
                production = self.browse(cr, uid, [production.id])[0]
            routing_loc = None
            pick_type = 'internal'
            address_id = False
            if production.bom_id.routing_id and production.bom_id.routing_id.location_id:
                routing_loc = production.bom_id.routing_id.location_id
                if routing_loc.usage<>'internal':
                    pick_type = 'out'
                address_id = routing_loc.address_id and routing_loc.address_id.id or False
                routing_loc = routing_loc.id
            picking_id = self.pool.get('stock.picking').create(cr, uid, {
                'origin': (production.origin or '').split(':')[0] +':'+production.name,
                'type': pick_type,
                'move_type': 'one',
                'state': 'auto',
                'address_id': address_id,
                'auto_picking': self._get_auto_picking(cr, uid, production),
            })
            toconfirm = True

            source = production.product_id.product_tmpl_id.property_stock_production.id
            data = {
                'name':'PROD:'+production.name,
                'date_planned': production.date_planned,
                'product_id': production.product_id.id,
                'product_qty': production.product_qty,
                'product_uom': production.product_uom.id,
                'product_uos_qty': production.product_uos and production.product_uos_qty or False,
                'product_uos': production.product_uos and production.product_uos.id or False,
                'location_id': source,
                'location_dest_id': production.location_dest_id.id,
                'move_dest_id': production.move_prod_id.id,
                'state': 'waiting'
            }
            res_final_id = self.pool.get('stock.move').create(cr, uid, data)

            self.write(cr, uid, [production.id], {'move_created_ids': [(6, 'WTF', [res_final_id])]})
            moves = []
            for line in production.product_lines:
                move_id=False
                newdate = production.date_planned
                if line.product_id.type in ('product', 'consu'):
                    res_dest_id = self.pool.get('stock.move').create(cr, uid, {
                        'name':'PROD:'+production.name,
                        'date_planned': production.date_planned,
                        'product_id': line.product_id.id,
                        'product_qty': line.product_qty,
                        'product_uom': line.product_uom.id,
                        'product_uos_qty': line.product_uos and line.product_uos_qty or False,
                        'product_uos': line.product_uos and line.product_uos.id or False,
                        'location_id': routing_loc or production.location_src_id.id,
                        'location_dest_id': source,
                        'move_dest_id': res_final_id,
                        'state': 'waiting',
                    })
                    moves.append(res_dest_id)
                    move_id = self.pool.get('stock.move').create(cr, uid, {
                        'name':'PROD:'+production.name,
                        'picking_id':picking_id,
                        'product_id': line.product_id.id,
                        'product_qty': line.product_qty,
                        'product_uom': line.product_uom.id,
                        'product_uos_qty': line.product_uos and line.product_uos_qty or False,
                        'product_uos': line.product_uos and line.product_uos.id or False,
                        'date_planned': newdate,
                        'move_dest_id': res_dest_id,
                        'location_id': production.location_src_id.id,
                        'location_dest_id': routing_loc or production.location_src_id.id,
                        'state': 'waiting',
                    })
                proc_id = self.pool.get('mrp.procurement').create(cr, uid, {
                    'name': (production.origin or '').split(':')[0] + ':' + production.name,
                    'origin': (production.origin or '').split(':')[0] + ':' + production.name,
                    'date_planned': newdate,
                    'product_id': line.product_id.id,
                    'product_qty': line.product_qty,
                    'product_uom': line.product_uom.id,
                    'product_uos_qty': line.product_uos and line.product_qty or False,
                    'product_uos': line.product_uos and line.product_uos.id or False,
                    'location_id': production.location_src_id.id,
                    'procure_method': line.product_id.procure_method,
                    'move_id': move_id,
                })
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'mrp.procurement', proc_id, 'button_confirm', cr)
            if toconfirm:
                wf_service = netsvc.LocalService("workflow")
                wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)
            self.write(cr, uid, [production.id], {'picking_id':picking_id, 'move_lines': [(6,0,moves)], 'state':'confirmed'})
        return picking_id

    def force_production(self, cr, uid, ids, *args):
        pick_obj = self.pool.get('stock.picking')
        pick_obj.force_assign(cr, uid, [prod.picking_id.id for prod in self.browse(cr, uid, ids)])
        return True

mrp_production()


class stock_move(osv.osv):
    _name = 'stock.move'
    _inherit = 'stock.move'
    _columns = {
        'production_id': fields.many2one('mrp.production', 'Production', select=True),
    }
stock_move()

class mrp_production_workcenter_line(osv.osv):
    _name = 'mrp.production.workcenter.line'
    _description = 'Production workcenters used'
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'workcenter_id': fields.many2one('mrp.workcenter', 'Workcenter', required=True),
        'cycle': fields.float('Nbr of cycle'),
        'hour': fields.float('Nbr of hour'),
        'sequence': fields.integer('Sequence', required=True),
        'production_id': fields.many2one('mrp.production', 'Production Order', select=True),
    }
    _defaults = {
        'sequence': lambda *a: 1,
        'hour': lambda *a: 0,
        'cycle': lambda *a: 0,
    }
mrp_production_workcenter_line()

class mrp_production_product_line(osv.osv):
    _name = 'mrp.production.product.line'
    _description = 'Production scheduled products'
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'product_id': fields.many2one('product.product', 'Product', required=True),
        'product_qty': fields.float('Product Qty', required=True),
        'product_uom': fields.many2one('product.uom', 'Product UOM', required=True),
        'product_uos_qty': fields.float('Product UOS Qty'),
        'product_uos': fields.many2one('product.uom', 'Product UOS'),
        'production_id': fields.many2one('mrp.production', 'Production Order', select=True),
    }
mrp_production_product_line()

# ------------------------------------------------------------------
# Procurement
# ------------------------------------------------------------------
#
# Produce, Buy or Find products and place a move
#     then wizard for picking lists & move
#
class mrp_procurement(osv.osv):
    _name = "mrp.procurement"
    _description = "Procurement"
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'origin': fields.char('Origin', size=64),
        'priority': fields.selection([('0','Not urgent'),('1','Normal'),('2','Urgent'),('3','Very Urgent')], 'Priority', required=True),
        'date_planned': fields.datetime('Scheduled date', required=True),
        'date_close': fields.datetime('Date Closed'),
        'product_id': fields.many2one('product.product', 'Product', required=True),
        'product_qty': fields.float('Quantity', required=True),
        'product_uom': fields.many2one('product.uom', 'Product UoM', required=True),
        'product_uos_qty': fields.float('UoS Quantity'),
        'product_uos': fields.many2one('product.uom', 'Product UoS'),
        'move_id': fields.many2one('stock.move', 'Reservation', ondelete='set null'),

        'bom_id': fields.many2one('mrp.bom', 'BoM', ondelete='cascade', select=True),

        'close_move': fields.boolean('Close Move at end', required=True),
        'location_id': fields.many2one('stock.location', 'Location', required=True),
        'procure_method': fields.selection([('make_to_stock','from stock'),('make_to_order','on order')], 'Procurement Method', states={'draft':[('readonly',False)], 'confirmed':[('readonly',False)]}, readonly=True, required=True),

        'purchase_id': fields.many2one('purchase.order', 'Purchase Order'),
        'purchase_line_id': fields.many2one('purchase.order.line', 'Purchase Order Line'),

        'property_ids': fields.many2many('mrp.property', 'mrp_procurement_property_rel', 'procurement_id','property_id', 'Properties'),

        'message': fields.char('Latest error', size=64),
        'state': fields.selection([('draft','Draft'),('confirmed','Confirmed'),('exception','Exception'),('running','Running'),('cancel','Cancel'),('done','Done'),('waiting','Waiting')], 'Status')
    }
    _defaults = {
        'state': lambda *a: 'draft',
        'priority': lambda *a: '1',
        'date_planned': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'close_move': lambda *a: 0,
        'procure_method': lambda *a: 'make_to_order',
    }
    def check_product(self, cr, uid, ids):
        for procurement in self.browse(cr, uid, ids):
            if procurement.product_id.type in ('product', 'consu'):
                return True
        return False

    def check_move_cancel(self, cr, uid, ids, context={}):
        res = True
        for procurement in self.browse(cr, uid, ids, context):
            if procurement.move_id:
                if not procurement.move_id.state=='cancel':
                    res = False
        return res

    def check_move_done(self, cr, uid, ids, context={}):
        res = True
        for proc in self.browse(cr, uid, ids, context):
            if proc.move_id:
                if not proc.move_id.state=='done':
                    res = False
        return res

    #
    # This method may be overrided by objects that override mrp.procurment
    # for computing their own purpose
    #
    def _quantity_compute_get(self, cr, uid, proc, context={}):
        if proc.product_id.type=='product':
            return proc.move_id.product_uos_qty
        return False

    def _uom_compute_get(self, cr, uid, proc, context={}):
        if proc.product_id.type=='product':
            if proc.move_id.product_uos:
                return proc.move_id.product_uos.id
        return False

    #
    # Return the quantity of product shipped/produced/served, wich may be
    # different from the planned quantity
    #
    def quantity_get(self, cr, uid, id, context={}):
        proc = self.browse(cr, uid, id, context)
        result = self._quantity_compute_get(cr, uid, proc, context)
        if not result:
            result = proc.product_qty
        return result

    def uom_get(self, cr, uid, id, context=None):
        proc = self.browse(cr, uid, id, context)
        result = self._uom_compute_get(cr, uid, proc, context)
        if not result:
            result = proc.product_uom.id
        return result

    def check_waiting(self, cr, uid, ids, context=[]):
        for procurement in self.browse(cr, uid, ids, context=context):
            if procurement.move_id and procurement.move_id.state=='auto':
                return True
        return False

    def check_produce_service(self, cr, uid, procurement, context=[]):
        return True

    def check_produce_product(self, cr, uid, procurement, context=[]):
        properties = [x.id for x in procurement.property_ids]
        bom_id = self.pool.get('mrp.bom')._bom_find(cr, uid, procurement.product_id.id, procurement.product_uom.id, properties)
        if not bom_id:
            cr.execute('update mrp_procurement set message=%s where id=%d', ('No BoM defined for this product !', procurement.id))
            return False
        return True

    def check_make_to_stock(self, cr, uid, ids, context={}):
        ok = True
        for procurement in self.browse(cr, uid, ids, context=context):
            if procurement.product_id.type=='service':
                ok = ok and self._check_make_to_stock_service(cr, uid, procurement, context)
            else:
                ok = ok and self._check_make_to_stock_product(cr, uid, procurement, context)
        return ok

    def check_produce(self, cr, uid, ids, context={}):
        res = True
        user = self.pool.get('res.users').browse(cr, uid, uid)
        for procurement in self.browse(cr, uid, ids):
            if procurement.product_id.product_tmpl_id.supply_method=='buy':
                if procurement.product_id.seller_ids:
                    partner = procurement.product_id.seller_ids[0].name
                    if user.company_id and user.company_id.partner_id:
                        if partner.id == user.company_id.partner_id.id:
                            return True
                return False
            if procurement.product_id.product_tmpl_id.type=='service':
                res = res and self.check_produce_service(cr, uid, procurement, context)
            else:
                res = res and self.check_produce_product(cr, uid, procurement, context)
            if not res:
                return False
        return res

    def check_buy(self, cr, uid, ids):
        user = self.pool.get('res.users').browse(cr, uid, uid)
        for procurement in self.browse(cr, uid, ids):
            if procurement.product_id.product_tmpl_id.supply_method=='produce':
                return False
            if not procurement.product_id.seller_ids:
                cr.execute('update mrp_procurement set message=%s where id=%d', ('No supplier defined for this product !', procurement.id))
                return False
            partner = procurement.product_id.seller_ids[0].name
            if user.company_id and user.company_id.partner_id:
                if partner.id == user.company_id.partner_id.id:
                    return False
            address_id = self.pool.get('res.partner').address_get(cr, uid, [partner.id], ['delivery'])['delivery']
            if not address_id:
                cr.execute('update mrp_procurement set message=%s where id=%d', ('No address defined for the supplier', procurement.id))
                return False
        return True

    def test_cancel(self, cr, uid, ids):
        for record in self.browse(cr, uid, ids):
            if record.move_id and record.move_id.state=='cancel':
                return True
        return False

    def action_confirm(self, cr, uid, ids, context={}):
        for procurement in self.browse(cr, uid, ids):
            if procurement.product_id.type in ('product', 'consu'):
                if not procurement.move_id:
                    source = procurement.location_id.id
                    if procurement.procure_method=='make_to_order':
                        source = procurement.product_id.product_tmpl_id.property_stock_procurement.id
                    id = self.pool.get('stock.move').create(cr, uid, {
                        'name': 'PROC:'+procurement.name,
                        'location_id': source,
                        'location_dest_id': procurement.location_id.id,
                        'product_id': procurement.product_id.id,
                        'product_qty':procurement.product_qty,
                        'product_uom': procurement.product_uom.id,
                        'date_planned': procurement.date_planned,
                        'state':'confirmed',
                    })
                    self.write(cr, uid, [procurement.id], {'move_id': id, 'close_move':1})
                else:
                    # TODO: check this
                    if procurement.procure_method=='make_to_stock' and procurement.move_id.state in ('waiting',):
                        id = self.pool.get('stock.move').write(cr, uid, [procurement.move_id.id], {'state':'confirmed'})
        self.write(cr, uid, ids, {'state':'confirmed','message':''})
        return True

    def action_move_assigned(self, cr, uid, ids):
        self.write(cr, uid, ids, {'state':'running','message':'from stock: products assigned.'})
        return True

    def _check_make_to_stock_service(self, cr, uid, procurement, context={}):
        return True

    def _check_make_to_stock_product(self, cr, uid, procurement, context={}):
        ok = True
        if procurement.move_id:
            id = procurement.move_id.id
            if not (procurement.move_id.state in ('done','assigned','cancel')):
                ok = ok and self.pool.get('stock.move').action_assign(cr, uid, [id])
                cr.execute('select count(id) from stock_warehouse_orderpoint where product_id=%d', (procurement.product_id.id,))
                if not cr.fetchone()[0]:
                    cr.execute('update mrp_procurement set message=%s where id=%d', ('from stock and no minimum orderpoint rule defined', procurement.id))
        return ok

    def action_produce_assign_service(self, cr, uid, ids, context={}):
        for procurement in self.browse(cr, uid, ids):
            self.write(cr, uid, [procurement.id], {'state':'running'})
        return True

    def action_produce_assign_product(self, cr, uid, ids, context={}):
        produce_id = False
        company = self.pool.get('res.users').browse(cr, uid, uid, context).company_id
        for procurement in self.browse(cr, uid, ids):
            res_id = procurement.move_id.id
            loc_id = procurement.location_id.id
            newdate = DateTime.strptime(procurement.date_planned, '%Y-%m-%d %H:%M:%S') - DateTime.RelativeDateTime(days=procurement.product_id.product_tmpl_id.produce_delay or 0.0)
            newdate = newdate - DateTime.RelativeDateTime(days=company.manufacturing_lead)
            produce_id = self.pool.get('mrp.production').create(cr, uid, {
                'origin': procurement.origin,
                'product_id': procurement.product_id.id,
                'product_qty': procurement.product_qty,
                'product_uom': procurement.product_uom.id,
                'product_uos_qty': procurement.product_uos and procurement.product_uos_qty or False,
                'product_uos': procurement.product_uos and procurement.product_uos.id or False,
                'location_src_id': procurement.location_id.id,
                'location_dest_id': procurement.location_id.id,
                'bom_id': procurement.bom_id and procurement.bom_id.id or False,
                'date_planned': newdate,
                'move_prod_id': res_id,
            })
            self.write(cr, uid, [procurement.id], {'state':'running'})
            bom_result = self.pool.get('mrp.production').action_compute(cr, uid,
                    [produce_id], properties=[x.id for x in procurement.property_ids])
            wf_service = netsvc.LocalService("workflow")
            wf_service.trg_validate(uid, 'mrp.production', produce_id, 'button_confirm', cr)
        return produce_id

    def action_po_assign(self, cr, uid, ids, context={}):
        purchase_id = False
        company = self.pool.get('res.users').browse(cr, uid, uid, context).company_id
        for procurement in self.browse(cr, uid, ids):
            res_id = procurement.move_id.id
            partner = procurement.product_id.seller_ids[0].name
            partner_id = partner.id
            address_id = self.pool.get('res.partner').address_get(cr, uid, [partner_id], ['delivery'])['delivery']
            pricelist_id = partner.property_product_pricelist_purchase.id

            uom_id = procurement.product_id.uom_po_id.id

            qty = self.pool.get('product.uom')._compute_qty(cr, uid, procurement.product_uom.id, procurement.product_qty, uom_id)
            if procurement.product_id.seller_ids[0].qty:
                qty=max(qty,procurement.product_id.seller_ids[0].qty)

            price = self.pool.get('product.pricelist').price_get(cr, uid, [pricelist_id], procurement.product_id.id, qty, False, {'uom': uom_id})[pricelist_id]

            newdate = DateTime.strptime(procurement.date_planned, '%Y-%m-%d %H:%M:%S') - DateTime.RelativeDateTime(days=procurement.product_id.product_tmpl_id.seller_delay or 0.0)
            newdate = newdate - DateTime.RelativeDateTime(days=company.po_lead)
            context.update({'lang':partner.lang})
            product=self.pool.get('product.product').browse(cr,uid,procurement.product_id.id,context=context)

            line = {
                'name': product.name,
                'product_qty': qty,
                'product_id': procurement.product_id.id,
                'product_uom': uom_id,
                'price_unit': price,
                'date_planned': newdate.strftime('%Y-%m-%d %H:%M:%S'),
                'move_dest_id': res_id,
                'notes':product.description_purchase,
            }

            taxes_ids = procurement.product_id.product_tmpl_id.supplier_taxes_id
            self.pool.get('account.fiscal.position').map_tax(cr, uid, partner, taxes)
            line.update({
                'taxes_id':[(6,0,taxes_ids)]
            })
            purchase_id = self.pool.get('purchase.order').create(cr, uid, {
                'origin': procurement.origin,
                'partner_id': partner_id,
                'partner_address_id': address_id,
                'location_id': procurement.location_id.id,
                'pricelist_id': pricelist_id,
                'order_line': [(0,0,line)]
            })
            self.write(cr, uid, [procurement.id], {'state':'running', 'purchase_id':purchase_id})
        return purchase_id

    def action_cancel(self, cr, uid, ids):
        todo = []
        for proc in self.browse(cr, uid, ids):
            if proc.move_id:
                todo.append(proc.move_id.id)
        if len(todo):
            self.pool.get('stock.move').action_cancel(cr, uid, [proc.move_id.id])
        self.write(cr, uid, ids, {'state':'cancel'})

        wf_service = netsvc.LocalService("workflow")
        for id in ids:
            wf_service.trg_trigger(uid, 'mrp.procurement', id, cr)

        return True

    def action_check_finnished(self, cr, uid, ids):
        return True

    def action_check(self, cr, uid, ids):
        ok = False
        for procurement in self.browse(cr, uid, ids):
            if procurement.move_id.state=='assigned' or procurement.move_id.state=='done':
                self.action_done(cr, uid, [procurement.id])
                ok = True
        return ok

    def action_done(self, cr, uid, ids):
        for procurement in self.browse(cr, uid, ids):
            if procurement.move_id:
                if procurement.close_move and (procurement.move_id.state <> 'done'):
                    self.pool.get('stock.move').action_done(cr, uid, [procurement.move_id.id])
        res = self.write(cr, uid, ids, {'state':'done', 'date_close':time.strftime('%Y-%m-%d')})

        wf_service = netsvc.LocalService("workflow")
        for id in ids:
            wf_service.trg_trigger(uid, 'mrp.procurement', id, cr)
        return res
    def run_scheduler(self, cr, uid, automatic=False, use_new_cursor=False, context=None):
        '''
        use_new_cursor: False or the dbname
        '''
        if not context:
            context={}
        self._procure_confirm(cr, uid, use_new_cursor=use_new_cursor, context=context)
        self._procure_orderpoint_confirm(cr, uid, automatic=automatic,\
                use_new_cursor=use_new_cursor, context=context)
mrp_procurement()


class stock_warehouse_orderpoint(osv.osv):
    _name = "stock.warehouse.orderpoint"
    _description = "Orderpoint minimum rule"
    _columns = {
        'name': fields.char('Name', size=32, required=True),
        'active': fields.boolean('Active'),
        'logic': fields.selection([('max','Order to Max'),('price','Best price (not yet active!)')], 'Reordering Mode', required=True),
        'warehouse_id': fields.many2one('stock.warehouse', 'Warehouse', required=True),
        'location_id': fields.many2one('stock.location', 'Location', required=True),
        'product_id': fields.many2one('product.product', 'Product', required=True, domain=[('type','=','product')]),
        'product_uom': fields.many2one('product.uom', 'Product UOM', required=True ),
        'product_min_qty': fields.float('Min Quantity', required=True),
        'product_max_qty': fields.float('Max Quantity', required=True),
        'qty_multiple': fields.integer('Qty Multiple', required=True),
        'procurement_id': fields.many2one('mrp.procurement', 'Purchase Order')
    }
    _defaults = {
        'active': lambda *a: 1,
        'logic': lambda *a: 'max',
        'qty_multiple': lambda *a: 1,
        'name': lambda x,y,z,c: x.pool.get('ir.sequence').get(y,z,'mrp.warehouse.orderpoint') or '',
        'product_uom': lambda sel, cr, uid, context: context.get('product_uom', False),
    }
    def onchange_warehouse_id(self, cr, uid, ids, warehouse_id, context={}):
        if warehouse_id:
            w=self.pool.get('stock.warehouse').browse(cr,uid,warehouse_id, context)
            v = {'location_id':w.lot_stock_id.id}
            return {'value': v}
        return {}
    def onchange_product_id(self, cr, uid, ids, product_id, context={}):
        if product_id:
            prod=self.pool.get('product.product').browse(cr,uid,product_id)
            v = {'product_uom':prod.uom_id.id}
            return {'value': v}
        return {}
stock_warehouse_orderpoint()


class StockMove(osv.osv):
    _inherit = 'stock.move'
    _columns = {
        'procurements': fields.one2many('mrp.procurement', 'move_id', 'Procurements'),
    }
    def _action_explode(self, cr, uid, move, context={}):
        if move.product_id.supply_method=='produce' and move.product_id.procure_method=='make_to_order':
            bis = self.pool.get('mrp.bom').search(cr, uid, [
                ('product_id','=',move.product_id.id),
                ('bom_id','=',False),
                ('type','=','phantom')])
            if bis:
                factor = move.product_qty
                bom_point = self.pool.get('mrp.bom').browse(cr, uid, bis[0])
                res = self.pool.get('mrp.bom')._bom_explode(cr, uid, bom_point, factor, [])
                dest = move.product_id.product_tmpl_id.property_stock_production.id
                state = 'confirmed'
                if move.state=='assigned':
                    state='assigned'
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
                        'location_dest_id': dest,
                        'move_history_ids': [(6,0,[move.id])],
                        'move_history_ids2': [(6,0,[])],
                        'procurements': []
                    }
                    mid = self.pool.get('stock.move').copy(cr, uid, move.id, default=valdef)
                    prodobj = self.pool.get('product.product').browse(cr, uid, line['product_id'], context=context)
                    proc_id = self.pool.get('mrp.procurement').create(cr, uid, {
                        'name': (move.picking_id.origin or ''),
                        'origin': (move.picking_id.origin or ''),
                        'date_planned': move.date_planned,
                        'product_id': line['product_id'],
                        'product_qty': line['product_qty'],
                        'product_uom': line['product_uom'],
                        'product_uos_qty': line['product_uos'] and line['product_uos_qty'] or False,
                        'product_uos':  line['product_uos'],
                        'location_id': move.location_id.id,
                        'procure_method': prodobj.procure_method,
                        'move_id': mid,
                    })
                    wf_service = netsvc.LocalService("workflow")
                    wf_service.trg_validate(uid, 'mrp.procurement', proc_id, 'button_confirm', cr)
                self.pool.get('stock.move').write(cr, uid, [move.id], {
                    'location_id': move.location_dest_id.id,
                    'auto_validate': True,
                    'picking_id': False,
                    'location_id': dest,
                    'state': 'waiting'
                })
                for m in self.pool.get('mrp.procurement').search(cr, uid, [('move_id','=',move.id)], context):
                    wf_service = netsvc.LocalService("workflow")
                    wf_service.trg_validate(uid, 'mrp.procurement', m, 'button_wait_done', cr)
        return True
StockMove()


class StockPicking(osv.osv):
    _inherit = 'stock.picking'

    def test_finnished(self, cursor, user, ids):
        wf_service = netsvc.LocalService("workflow")
        res = super(StockPicking, self).test_finnished(cursor, user, ids)
        for picking in self.browse(cursor, user, ids):
            for move in picking.move_lines:
                if move.state == 'done' and move.procurements:
                    for procurement in move.procurements:
                        wf_service.trg_validate(user, 'mrp.procurement',
                                procurement.id, 'button_check', cursor)
        return res

    #
    # Explode picking by replacing phantom BoMs
    #
    def action_explode(self, cr, uid, picks, *args):
        for move in picks:
            self.pool.get('stock.move')._action_explode(cr, uid, move)
        return picks

StockPicking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

