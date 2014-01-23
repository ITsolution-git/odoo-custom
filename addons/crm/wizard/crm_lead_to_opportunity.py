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

from openerp.osv import fields, osv
from openerp.tools.translate import _
import re

class crm_lead2opportunity_partner(osv.osv_memory):
    _name = 'crm.lead2opportunity.partner'
    _description = 'Lead To Opportunity Partner'
    _inherit = 'crm.partner.binding'

    _columns = {
        'name': fields.selection([
                ('convert', 'Convert to opportunity'),
                ('merge', 'Merge with existing opportunities')
            ], 'Conversion Action', required=True),
        'opportunity_ids': fields.many2many('crm.lead', string='Opportunities'),
        'user_id': fields.many2one('res.users', 'Salesperson', select=True),
        'section_id': fields.many2one('crm.case.section', 'Sales Team', select=True),
    }

    def onchange_action(self, cr, uid, ids, action, context=None):
        return {'value': {'partner_id': False if action != 'exist' else self._find_matching_partner(cr, uid, context=context)}}

    def _get_duplicated_leads(self, cr, uid, partner_id, email, context=None):
        lead_obj = self.pool.get('crm.lead')
        results = []
        if partner_id:
            # Search for opportunities that have the same partner and that arent done or cancelled
            ids = lead_obj.search(cr, uid, [('partner_id', '=', partner_id), '|', ('probability', '=', False), ('probability', '<', '100')])
            for id in ids:
                results.append(id)
        email = re.findall(r'([^ ,<@]+@[^> ,]+)', email or '')
        if email:
            ids = lead_obj.search(cr, uid, [('email_from', '=ilike', email[0]), '|', ('probability', '=', False), ('probability', '<', '100')])
            for id in ids:
                results.append(id)
        return list(set(results))


    def default_get(self, cr, uid, fields, context=None):
        """
        Default get for name, opportunity_ids.
        If there is an exisitng partner link to the lead, find all existing
        opportunities links with this partner to merge all information together
        """
        lead_obj = self.pool.get('crm.lead')

        res = super(crm_lead2opportunity_partner, self).default_get(cr, uid, fields, context=context)
        if context.get('active_id'):
            tomerge = [int(context['active_id'])]

            email = False
            partner_id = res.get('partner_id')
            lead = lead_obj.browse(cr, uid, int(context['active_id']), context=context)

            #TOFIX: use mail.mail_message.to_mail
            tomerge.extend(self._get_duplicated_leads(cr, uid, partner_id, email))
            tomerge = list(set(tomerge))

            if 'action' in fields:
                res.update({'action' : partner_id and 'exist' or 'create'})
            if 'partner_id' in fields:
                res.update({'partner_id' : partner_id})
            if 'name' in fields:
                res.update({'name' : len(tomerge) >= 2 and 'merge' or 'convert'})
            if 'opportunity_ids' in fields and len(tomerge) >= 2:
                res.update({'opportunity_ids': tomerge})
            if lead.user_id:
                res.update({'user_id': lead.user_id.id})
            if lead.section_id:
                res.update({'section_id': lead.section_id.id})
        return res

    def on_change_user(self, cr, uid, ids, user_id, section_id, context=None):
        """ When changing the user, also set a section_id or restrict section id
            to the ones user_id is member of. """
        if user_id:
            if section_id:
                user_in_section = self.pool.get('crm.case.section').search(cr, uid, [('id', '=', section_id), '|', ('user_id', '=', user_id), ('member_ids', '=', user_id)], context=context, count=True)
            else:
                user_in_section = False
            if not user_in_section:
                section_id = False
                section_ids = self.pool.get('crm.case.section').search(cr, uid, ['|', ('user_id', '=', user_id), ('member_ids', '=', user_id)], context=context)
                if section_ids:
                    section_id = section_ids[0]
        return {'value': {'section_id': section_id}}

    def view_init(self, cr, uid, fields, context=None):
        """
        Check some preconditions before the wizard executes.
        """
        if context is None:
            context = {}
        lead_obj = self.pool.get('crm.lead')
        for lead in lead_obj.browse(cr, uid, context.get('active_ids', []), context=context):
            if lead.probability == 100:
                raise osv.except_osv(_("Warning!"), _("Closed/Dead leads cannot be converted into opportunities."))
        return False

    def _convert_opportunity(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        lead = self.pool.get('crm.lead')
        res = False
        lead_ids = vals.get('lead_ids', [])
        team_id = vals.get('section_id', False)
        data = self.browse(cr, uid, ids, context=context)[0]
        for lead_id in lead_ids:
            partner_id = self._create_partner(cr, uid, lead_id, data.action, data.partner_id, context=context)
            # FIXME: cannot pass user_ids as the salesman allocation only works in batch
            res = lead.convert_opportunity(cr, uid, [lead_id], partner_id, [], team_id, context=context)
        # FIXME: must perform salesman allocation in batch separately here
        user_ids = vals.get('user_ids', False)
        if user_ids:
            lead.allocate_salesman(cr, uid, lead_ids, user_ids, team_id=team_id, context=context)
        return res

    def action_apply(self, cr, uid, ids, context=None):
        """
        Convert lead to opportunity or merge lead and opportunity and open
        the freshly created opportunity view.
        """
        if context is None:
            context = {}

        w = self.browse(cr, uid, ids, context=context)[0]
        opp_ids = [o.id for o in w.opportunity_ids]
        if w.name == 'merge':
            lead_id = self.pool.get('crm.lead').merge_opportunity(cr, uid, opp_ids, w.user_id.id, w.section_id.id, context=context)
            lead_ids = [lead_id]
            lead = self.pool.get('crm.lead').read(cr, uid, lead_id, ['type'], context=context)
            if lead['type'] == "lead":
                context.update({'active_ids': lead_ids})
                self._convert_opportunity(cr, uid, ids, {'lead_ids': lead_ids, 'user_ids': [w.user_id.id], 'section_id': w.section_id.id}, context=context)
        else:
            lead_ids = context.get('active_ids', [])
            self._convert_opportunity(cr, uid, ids, {'lead_ids': lead_ids, 'user_ids': [w.user_id.id], 'section_id': w.section_id.id}, context=context)

        return self.pool.get('crm.lead').redirect_opportunity_view(cr, uid, lead_ids[0], context=context)

    def _create_partner(self, cr, uid, lead_id, action, partner_id, context=None):
        """
        Create partner based on action.
        :return dict: dictionary organized as followed: {lead_id: partner_assigned_id}
        """
        #TODO this method in only called by crm_lead2opportunity_partner
        #wizard and would probably diserve to be refactored or at least
        #moved to a better place
        if context is None:
            context = {}
        lead = self.pool.get('crm.lead')
        if action == 'each_exist_or_create':
            ctx = dict(context)
            ctx['active_id'] = lead_id
            partner_id = self._find_matching_partner(cr, uid, context=ctx)
            action = 'create'
            print partner_id
        res = lead.handle_partner_assignation(cr, uid, [lead_id], action, partner_id, context=context)
        return res.get(lead_id)

class crm_lead2opportunity_mass_convert(osv.osv_memory):
    _name = 'crm.lead2opportunity.partner.mass'
    _description = 'Mass Lead To Opportunity Partner'
    _inherit = 'crm.lead2opportunity.partner'

    _columns = {
        'user_ids':  fields.many2many('res.users', string='Salesmen'),
        'section_id': fields.many2one('crm.case.section', 'Sales Team'),
        'deduplicate': fields.boolean('Apply deduplication', help='Merge with existing leads/opportunities of each partner'),
        'action': fields.selection([
                ('each_exist_or_create', 'Use existing partner or create'),
                ('nothing', 'Do not link to a customer')
            ], 'Related Customer', required=True),
    }

    _defaults = {
        'deduplicate': True,
    }

    def default_get(self, cr, uid, fields, context=None):
        res = super(crm_lead2opportunity_mass_convert, self).default_get(cr, uid, fields, context)
        if 'partner_id' in fields:
            # avoid forcing the partner of the first lead as default
            res['partner_id'] = False
        if 'action' in fields:
            res['action'] = 'each_exist_or_create'
        if 'name' in fields:
            res['name'] = 'convert'
        if 'opportunity_ids' in fields:
            res['opportunity_ids'] = False
        return res

    def on_change_action(self, cr, uid, ids, action, context=None):
        vals = {}
        if action != 'exist':
            vals = {'value': {'partner_id': False}} 
        return vals

    def on_change_deduplicate(self, cr, uid, ids, deduplicate, context=None):
        if context is None:
            context = {}
        active_leads = self.pool['crm.lead'].browse(cr, uid, context['active_ids'], context=context)
        partner_ids = [(lead.partner_id.id, lead.partner_id and lead.partner_id.email or lead.email_from) for lead in active_leads]
        partners_duplicated_leads = {}
        for partner_id, email in partner_ids:
            duplicated_leads = self._get_duplicated_leads(cr, uid, partner_id, email)
            if len(duplicated_leads) > 1:
                partners_duplicated_leads.setdefault((partner_id, email), []).extend(duplicated_leads)
        leads_with_duplicates = []
        for lead in active_leads:
            lead_tuple = (lead.partner_id.id, lead.partner_id.email if lead.partner_id else lead.email_from)
            if len(partners_duplicated_leads.get(lead_tuple, [])) > 1:
                leads_with_duplicates.append(lead.id)
        return {'value': {'opportunity_ids': leads_with_duplicates}}


    def _convert_opportunity(self, cr, uid, ids, vals, context=None):
        """
        When "massively" (more than one at a time) converting leads to
        opportunities, check the salesteam_id and salesmen_ids and update
        the values before calling super.
        """
        if context is None:
            context = {}
        data = self.browse(cr, uid, ids, context=context)[0]
        salesteam_id = data.section_id and data.section_id.id or False
        salesmen_ids = []
        if data.user_ids:
            salesmen_ids = [x.id for x in data.user_ids]
        vals.update({'user_ids': salesmen_ids, 'section_id': salesteam_id})
        return super(crm_lead2opportunity_mass_convert, self)._convert_opportunity(cr, uid, ids, vals, context=context)

    def mass_convert(self, cr, uid, ids, context=None):
        data = self.browse(cr, uid, ids, context=context)[0]
        ctx = dict(context)
        if data.name == 'convert' and data.deduplicate:
            merged_lead_ids = []
            remaining_lead_ids = []
            for lead in data.opportunity_ids:
                duplicated_lead_ids = self._get_duplicated_leads(cr, uid, lead.partner_id.id, lead.partner_id and lead.partner_id.email or lead.email_from)
                if len(duplicated_lead_ids) > 1:
                    lead_id = self.pool.get('crm.lead').merge_opportunity(cr, uid, duplicated_lead_ids, False, False, context=context)
                    merged_lead_ids.extend(duplicated_lead_ids)
                    remaining_lead_ids.append(lead_id)
            active_ids = set(context.get('active_ids', []))
            active_ids = active_ids.difference(merged_lead_ids)
            active_ids = active_ids.union(remaining_lead_ids)
            ctx['active_ids'] = list(active_ids)
        return self.action_apply(cr, uid, ids, context=ctx)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
