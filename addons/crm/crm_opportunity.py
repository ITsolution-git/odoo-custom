#-*- coding: utf-8 -*-
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

import time
import re
import os

import mx.DateTime
import base64

from tools.translate import _

import tools
from osv import fields,osv,orm
from osv.orm import except_orm

AVAILABLE_PRIORITIES = [
    ('5','Lowest'),
    ('4','Low'),
    ('3','Normal'),
    ('2','High'),
    ('1','Highest')
]

def _links_get(self, cr, uid, context={}):
    obj = self.pool.get('res.request.link')
    ids = obj.search(cr, uid, [])
    res = obj.read(cr, uid, ids, ['object', 'name'], context)
    return [(r['object'], r['name']) for r in res]

class crm_opportunity_categ(osv.osv):
    _name = "crm.opportunity.categ"
    _description = "Opportunity Categories"
    _columns = {
            'name': fields.char('Category Name', size=64, required=True),
            'probability': fields.float('Probability (%)', required=True),
            'section_id': fields.many2one('crm.case.section', 'Case Section'),
    }
    _defaults = {
        'probability': lambda *args: 0.0
    }
crm_opportunity_categ()

class crm_opportunity(osv.osv):
    _name = "crm.opportunity"
    _description = "Opportunity Cases"
    _order = "id desc"
    _inherit = 'crm.case'  
    _columns = {        
        'stage_id': fields.many2one ('crm.case.stage', 'Stage', domain="[('section_id','=',section_id)]"),
        'categ_id': fields.many2one('crm.opportunity.categ', 'Category', domain="[('section_id','=',section_id)]"),
        'category2_id': fields.many2one('crm.case.category2', 'Category Name', domain="[('section_id','=',section_id)]"),
        'priority': fields.selection(AVAILABLE_PRIORITIES, 'Priority'),
        'probability': fields.float('Probability (%)'),
        'planned_revenue': fields.float('Planned Revenue'),
        'planned_cost': fields.float('Planned Costs'),
        'canal_id': fields.many2one('res.partner.canal', 'Channel',help="The channels represent the different communication modes available with the customer." \
                                                                        " With each commercial opportunity, you can indicate the canall which is this opportunity source."),
        'som': fields.many2one('res.partner.som', 'State of Mind', help="The minds states allow to define a value scale which represents" \
                                                                   "the partner mentality in relation to our services.The scale has" \
                                                                   "to be created with a factor for each level from 0 (Very dissatisfied) to 10 (Extremely satisfied)."),
        'ref' : fields.reference('Reference', selection=_links_get, size=128),
        'ref2' : fields.reference('Reference 2', selection=_links_get, size=128),
        'date_closed': fields.datetime('Closed', readonly=True),
        'lead_id':fields.many2one ('crm.lead', 'Lead'),
    }

    def msg_new(self, cr, uid, msg):        
        mailgate_obj = self.pool.get('mail.gateway')
        msg_body = mailgate_obj.msg_body_get(msg)
        data = {
            'name': msg['Subject'],            
            'email_from': msg['From'],
            'email_cc': msg['Cc'],            
            'user_id': False,
            'description': msg_body['body'],
            'history_line': [(0, 0, {'description': msg_body['body'], 'email': msg['From'] })],
        }
        res = mailgate_obj.partner_get(cr, uid, msg['From'])
        if res:
            data.update(res)
        res = self.create(cr, uid, data)        
        return res

crm_opportunity()


class crm_opportunity_assign_wizard(osv.osv_memory):
    _name = 'crm.opportunity.assign_wizard'

    _columns = {
        'section_id': fields.many2one('crm.case.section', 'Section'),
        'user_id': fields.many2one('res.users', 'Responsible'),
    }

    def _get_default_section(self, cr, uid, context):
        case_id = context.get('active_id',False)
        if not case_id:
            return False
        case_obj = self.pool.get('crm.opportunity')
        case = case_obj.read(cr, uid, case_id, ['state','section_id'])
        if case['state'] in ('done'):
            raise osv.except_osv(_('Error !'), _('You can not assign Closed Case.'))
        return case['section_id']


    _defaults = {
        'section_id': _get_default_section
    }
    def action_create(self, cr, uid, ids, context=None):
        case_obj = self.pool.get('crm.opportunity')
        case_id = context.get('active_id',[])
        res = self.read(cr, uid, ids)[0]
        case = case_obj.browse(cr, uid, case_id)
        if case.state in ('done'):
            raise osv.except_osv(_('Error !'), _('You can not assign Closed Case.'))
        new_case_id = case_obj.copy(cr, uid, case_id, default=
                                            {
                                                'section_id':res.get('section_id',False),
                                                'user_id':res.get('user_id',False),
                                                'case_id' : case.id
                                            }, context=context)            
        case_obj.case_close(cr, uid, [case_id])

        data_obj = self.pool.get('ir.model.data')
        result = data_obj._get_id(cr, uid, 'crm', 'view_crm_case_opportunities_filter')
        search_view = data_obj.read(cr, uid, result, ['res_id'])
        value = {            
            'name': _('Opportunity'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'crm.opportunity',
            'res_id': int(new_case_id),            
            'type': 'ir.actions.act_window', 
            'search_view_id': search_view['res_id']            
        }
        return value

crm_opportunity_assign_wizard()
