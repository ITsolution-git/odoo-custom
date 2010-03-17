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

from osv import osv
from tools.translate import _

class crm_opportunity2meeting(osv.osv_memory):
    _name = 'crm.opportunity2meeting'
    _description = 'Opportunity To Meeting'

    def action_cancel(self, cr, uid, ids, context=None):
        """
        Closes Opportunity to Meeting form
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of Opportunity to Meeting IDs
        @param context: A standard dictionary for contextual values

        """
        return {'type': 'ir.actions.act_window_close'}

    def action_makeMeeting(self, cr, uid, ids, context=None):
        """
        This opens Meeting's calendar view to schedule meeting on current Opportunity
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of Opportunity to Meeting IDs
        @param context: A standard dictionary for contextual values

        @return : Dictionary value for created Meeting view
        """
        value = {}
        record_id = context and context.get('active_id', False) or False
        if record_id:
            opp_obj = self.pool.get('crm.opportunity')
            data_obj = self.pool.get('ir.model.data')
            
            # Get meeting views
            result = data_obj._get_id(cr, uid, 'crm', 'view_crm_case_meetings_filter')
            res = data_obj.read(cr, uid, result, ['res_id'])
            id1 = data_obj._get_id(cr, uid, 'crm', 'crm_case_calendar_view_meet')
            id2 = data_obj._get_id(cr, uid, 'crm', 'crm_case_form_view_meet')
            id3 = data_obj._get_id(cr, uid, 'crm', 'crm_case_tree_view_meet')
            if id1:
                id1 = data_obj.browse(cr, uid, id1, context=context).res_id
            if id2:
                id2 = data_obj.browse(cr, uid, id2, context=context).res_id
            if id3:
                id3 = data_obj.browse(cr, uid, id3, context=context).res_id

        for this in self.browse(cr, uid, ids, context=context):
            opp = opp_obj.browse(cr, uid, record_id, context=context)
            context = {
                        'default_opportunity_id': opp.id, 
                        'default_partner_id': opp.partner_id and opp.partner_id.id or False, 
                        'default_section_id': opp.section_id and opp.section_id.id or False, 
                        'default_email_from': opp.email_from, 
                        'default_state': 'open', 
                        'default_name': opp.name
                    }
                    
            value = {
                'name': _('Meetings'), 
                'domain' : "[('user_id','=',%s)]" % (uid), 
                'context': context, 
                'view_type': 'form', 
                'view_mode': 'calendar,form,tree', 
                'res_model': 'crm.meeting', 
                'view_id': False, 
                'views': [(id1, 'calendar'), (id2, 'form'), (id3, 'tree')], 
                'type': 'ir.actions.act_window', 
                'search_view_id': res['res_id']
                }

        return value

crm_opportunity2meeting()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
