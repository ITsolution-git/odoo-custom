# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2008 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import time

from osv import fields,osv
from osv import orm
import netsvc
from tools.translate import _

class purchase_requisition(osv.osv):
    _name = "purchase.requisition"
    _description="Purchase Requisition"
    _columns = {
        'name': fields.char('Requisition Reference', size=32,required=True),
        'origin': fields.char('Origin', size=32),
        'date_start': fields.datetime('Requisition Date'),
        'date_end': fields.datetime('Requisition Deadline'),
        'user_id': fields.many2one('res.users', 'Responsible'),
        'exclusive': fields.selection([('exclusive','Purchase Tender (exclusive)'),('multiple','Multiple Requisitions')],'Requisition Type', required=True, help="Purchase Tender (exclusive):On the confirmation of a purchase order, it cancels the remaining purchase order.Multiple Requisitions:It allows to have multiple purchase orders.On confirmation of a purchase order it does not cancel the remaining orders"""),
        'description': fields.text('Description'),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'purchase_ids' : fields.one2many('purchase.order','requisition_id','Purchase Orders',states={'done': [('readonly', True)]}),
        'line_ids' : fields.one2many('purchase.requisition.line','requisition_id','Products to Purchase',states={'done': [('readonly', True)]}),
        'state': fields.selection([('draft','Draft'),('in_progress','In Progress'),('cancel','Cancelled'),('done','Done')], 'State', required=True)
    }
    _defaults = {
        'date_start': time.strftime('%Y-%m-%d %H:%M:%S'),
        'state': 'draft',
        'exclusive': 'multiple',
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'purchase.requisition', context=c),
        'user_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr, uid, uid, c).id ,
        'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'purchase.order.requisition'),
    }

    def tender_cancel(self, cr, uid, ids, context=None):
        purchase_order_obj = self.pool.get('purchase.order')
        for purchase in self.browse(cr, uid, ids):
            for purchase_id in purchase.purchase_ids:
                if str(purchase_id.state) in('draft','wait'):
                    purchase_order_obj.action_cancel(cr,uid,[purchase_id.id])
        self.write(cr, uid, ids, {'state': 'cancel'})
        for (id,name) in self.name_get(cr, uid, ids):
                    message = _('Tender') + " '" + name + "' "+ _("is cancelled")
                    self.log(cr, uid, id, message)
        return True

    def tender_in_progress(self, cr, uid, ids, context=None):
        for quotations in self.browse(cr, uid, ids):
            if not quotations.purchase_ids:
                raise osv.except_osv(_('Purchase order required'),('You should have atleast one purchase order line defined for this tender'))
        self.write(cr, uid, ids, {'state':'in_progress'} ,context=context)
        for (id,name) in self.name_get(cr, uid, ids):
                    message = _('Tender') + " '" + name + "' "+ _(" is In Progress")
                    self.log(cr, uid, id, message)
        return True

    def tender_reset(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'draft'})
        for (id,name) in self.name_get(cr, uid, ids):
                    message = _('Tender') + " '" + name + "' "+ _("is in draft state")
                    self.log(cr, uid, id, message)
        return True

    def tender_done(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'done', 'date_end':time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
        for (id,name) in self.name_get(cr, uid, ids):
                    message = _('Tender') + " '" + name + "' "+ _("is done")
                    self.log(cr, uid, id, message)
        return True

purchase_requisition()

class purchase_requisition_line(osv.osv):

    _name = "purchase.requisition.line"
    _description="Purchase Requisition Line"
    _rec_name = 'product_id'

    _columns = {
        'product_id': fields.many2one('product.product', 'Product' ),
        'product_uom_id': fields.many2one('product.uom', 'Product UoM'),
        'product_qty': fields.float('Quantity', digits=(16,2)),
        'requisition_id' : fields.many2one('purchase.requisition','Purchase Requisition', ondelete='cascade'),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'requisition_id' : fields.many2one('purchase.requisition','Purchase Requisition', ondelete='cascade')
    }

    def onchange_product_id(self, cr, uid, ids, product_id,product_uom_id, context=None):
        """ Changes UoM and name if product_id changes.
        @param name: Name of the field
        @param product_id: Changed product_id
        @return:  Dictionary of changed values
        """
        value = {'product_uom_id': ''}
        if product_id:
            prod = self.pool.get('product.product').browse(cr, uid, [product_id])[0]
            value = {'product_uom_id': prod.uom_id.id,'product_qty':1.0}
        return {'value': value}

    _defaults = {
        'company_id': lambda self, cr, uid, c: self.pool.get('res.company')._company_default_get(cr, uid, 'purchase.requisition.line', context=c),
                }
purchase_requisition_line()

class purchase_order(osv.osv):
    _inherit = "purchase.order"
    _columns = {
        'requisition_id' : fields.many2one('purchase.requisition','Purchase Requisition')
    }
    def wkf_confirm_order(self, cr, uid, ids, context={}):
        res = super(purchase_order, self).wkf_confirm_order(cr, uid, ids, context)
        for po in self.browse(cr, uid, ids, context):
            if po.requisition_id and (po.requisition_id.exclusive=='exclusive'):
                for order in po.requisition_id.purchase_ids:
                    if order.id<>po.id:
                        wf_service = netsvc.LocalService("workflow")
                        wf_service.trg_validate(uid, 'purchase.order', order.id, 'purchase_cancel', cr)
                    self.pool.get('purchase.requisition').write(cr, uid, [po.requisition_id.id], {'state':'done','date_end':time.strftime('%Y-%m-%d %H:%M:%S')})
        return res

purchase_order()

class product_product(osv.osv):
    _inherit = 'product.product'

    _columns = {
        'purchase_requisition': fields.boolean('Purchase Requisition', help="Check this box so that requisitions generates purchase requisitions instead of directly requests for quotations.")
    }
    _defaults = {
        'purchase_requisition': False
    }

product_product()

class procurement_order(osv.osv):

    _inherit = 'procurement.order'

    def make_po(self, cr, uid, ids, context=None):
        sequence_obj = self.pool.get('ir.sequence')
        res = super(procurement_order, self).make_po(cr, uid, ids, context=context)
        for proc_id, po_id in res.items():
            procurement = self.browse(cr, uid, proc_id)
            if procurement.product_id.purchase_requisition:
                self.pool.get('purchase.requisition').create(cr, uid, {
                    'name': sequence_obj.get(cr, uid, 'purchase.order.requisition'),
                    'origin': procurement.name,
                    'date_end': procurement.date_planned,
                    'line_ids': [(0,0,{
                        'product_id': procurement.product_id.id,
                        'product_uom_id': procurement.product_uom.id,
                        'product_qty': procurement.product_qty

                    })],
                    'purchase_ids': [(6,0,[po_id])]
                })
        return res

procurement_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: