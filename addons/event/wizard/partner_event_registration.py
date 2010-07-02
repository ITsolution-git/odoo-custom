# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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

import wizard
import netsvc
import tools
from osv import fields, osv
from tools.translate import _


class partner_event_registration(osv.osv_memory):
    """  event Registration """

    _name = "partner.event.registration"
    _description = __doc__
    _order = 'event_id'

    _columns = {
        'event_id': fields.many2one('event.event', 'Event'),
        'event_type': fields.many2one('event.type', 'Type', readonly=True),
        'unit_price': fields.float('Cost', readonly=True),
        'currency_id': fields.many2one('res.currency', 'Currency', readonly=True),
        'start_date': fields.datetime('Start date', required=True, help="Beginning Date of Event", readonly=True), 
        'end_date': fields.datetime('Closing date', required=True, help="Closing Date of Event", readonly=True), 
        'nb_register': fields.integer('Number of Registration'),
    }
    _defaults = {
        'nb_register': 1, 
    }

    def open_registration(self, cr, uid, ids, context=None):
        value = {}
        res_obj = self.pool.get('res.partner')
        record_ids = context and context.get('active_ids', []) or []
        addr = res_obj.address_get(cr, uid, record_ids)
        contact_id = False
        if addr.has_key('default'):
                job_ids = self.pool.get('res.partner.job').search(cr, uid, [('address_id', '=', addr['default'])])
                if job_ids:
                    contact_id = self.pool.get('res.partner.job').browse(cr, uid, job_ids[0]).contact_id.id
         
        event_obj = self.pool.get('event.event')
        reg_obj = self.pool.get('event.registration')
        mod_obj = self.pool.get('ir.model.data')
        result = mod_obj._get_id(cr, uid, 'event', 'view_registration_search')
        res = mod_obj.read(cr, uid, result, ['res_id'])

        data_obj = self.pool.get('ir.model.data')
        # Select the view
        id2 = data_obj._get_id(cr, uid, 'event', 'view_event_registration_form')
        id3 = data_obj._get_id(cr, uid, 'event', 'view_event_registration_tree')
        if id2:
            id2 = data_obj.browse(cr, uid, id2, context=context).res_id
        if id3:
            id3 = data_obj.browse(cr, uid, id3, context=context).res_id

        for current in self.browse(cr, uid, ids, context=context):
            for reg in reg_obj.browse(cr, uid, record_ids, context=context):
                new_case = reg_obj.create(cr, uid, {
                        'name' : 'Registration',
                        'event_id' : current.event_id and current.event_id.id or False,
                        'unit_price' : current.event_id.unit_price,
                        'currency_id' : current.event_id.currency_id and current.event_id.currency_id.id or False,
                        'partner_id' : record_ids[0],
                        'partner_invoice_id' :  record_ids[0] or False,
                        'event_product': current.event_id.product_id.name,
                        'contact_id': contact_id,
                        'nb_register': current.nb_register,
 
                }, context=context)

            value = {
                'name': _('Event Registration'),
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_model': 'event.registration',
                'res_id' : new_case,
                'views': [(id2, 'form'), (id3, 'tree'), (False, 'calendar'), (False, 'graph')],
                'type': 'ir.actions.act_window',
                'search_view_id': res['res_id']
            }
        return value
    
    def name_get(self, cr, uid, ids, context=None):
        """Overrides orm name_get method
        @param ids: List of partner_event_register ids
        """
        if not context:
            context = {}
        
        res = []
        if not ids:
            return res
        reads = self.read(cr, uid, ids, ['event_type', 'event_id'], context)
        for record in reads:
            event_id = record['event_id'][1]
            if record['event_type']:
                event_id = record['event_type'][1] + ' on ' + event_id
            res.append((record['id'], event_id))
        return res
    
    def onchange_event_id(self, cr, uid, ids, event_id, context={}):
        res = {}    
        if event_id:   
            obj_event = self.pool.get('event.event')
            event = obj_event.browse(cr, uid, event_id)
            res['value'] = {
                          'event_type': event.type and event.type.id or False,
                          'start_date': event.date_begin,
                          'end_date': event.date_end,
                          'unit_price': event.unit_price,
                          'currency_id': event.currency_id and event.currency_id.id or False
                           }
        return res
    
partner_event_registration()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

