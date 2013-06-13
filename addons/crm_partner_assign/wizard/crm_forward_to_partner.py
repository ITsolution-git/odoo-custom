# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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


class crm_lead_forward_to_partner(osv.TransientModel):
    """ Forward info history to partners. """
    _name = 'crm.lead.forward.to.partner'

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        lead_obj = self.pool.get('crm.lead')
        partner_obj = self.pool.get('res.partner')
        email_template_obj = self.pool.get('email.template')
        base_url = self.pool.get('ir.config_parameter').get_param(cr, uid, 'web.base.url')
        try:
            template_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'crm_partner_assign', 'email_template_lead_forward_mail')[1]
        except ValueError:
            template_id = False
        res = super(crm_lead_forward_to_partner, self).default_get(cr, uid, fields, context=context)
        active_ids = context.get('active_ids')
        default_composition_mode = context.get('default_composition_mode')
        res['assignation_lines'] = []
        if template_id:
            res['body'] = email_template_obj.get_email_template(cr, uid, template_id).body_html
        if active_ids:
            lead_ids = lead_obj.browse(cr, uid, active_ids, context=context)
            if default_composition_mode == 'mass_mail':
                partner_assigned_ids = lead_obj.search_geo_partner(cr, uid, active_ids, context=context)
            else:
                partner_assigned_ids = dict((lead.id, lead.partner_assigned_id and lead.partner_assigned_id.id or False) for lead in lead_ids)
                res['partner_id'] = lead_ids[0].partner_assigned_id.id
            for lead in lead_ids:
                lead_location = []
                partner_location = []
                if lead.country_id:
                    lead_location.append(lead.country_id.name)
                if lead.city:
                    lead_location.append(lead.city)
                    partner_id = partner_assigned_ids.get(lead.id) or False
                    if partner_id:
                        partner = partner_obj.browse(cr, uid, partner_id, context=context)
                        if partner.country_id:
                            partner_location.append(partner.country_id.name)
                        if partner.city:
                            partner_location.append(partner.city)
                    res['assignation_lines'].append({'lead_id': lead.id,
                                                     'lead_location': ", ".join(lead_location),
                                                     'partner_assigned_id': partner_id,
                                                     'partner_location': ", ".join(partner_location),
                                                     'lead_link': "%s/?db=%s#id=%s&model=crm.lead" % (base_url, cr.dbname, lead.id)
                                                     })
        return res

    def action_forward(self, cr, uid, ids, context=None):
        lead_obj = self.pool.get('crm.lead')
        record = self.browse(cr, uid, ids[0], context=context)
        email_template_obj = self.pool.get('email.template')
        try:
            template_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'crm_partner_assign', 'email_template_lead_forward_mail')[1]
        except ValueError:
            raise osv.except_osv(_('Email Template Error'),
                                 _('The Forward Email Template is not in the database'))
        local_context = context.copy()
        if not (record.forward_type == 'single'):
            for lead in record.assignation_lines:
                if not lead.partner_assigned_id:
                    raise osv.except_osv(_('Assignation Error'),
                                         _('Some leads have not been assigned to any partner so assign partners manualy'))
        partners_leads = {}
        for lead in record.assignation_lines:
            lead_details = {
                'lead_link': lead.lead_link,
                'lead_id': lead.lead_id,
            }
            partner = record.forward_type == 'single' and record.partner_id or lead.partner_assigned_id
            partner_leads = partners_leads.get(partner.id)
            if partner_leads:
                partner_leads['leads'].append(lead_details)
            else:
                partners_leads[partner.id] = {'partner': partner, 'leads': [lead_details]}
        for partner_id, partner_leads in partners_leads.items():
            local_context['partner_id'] = partner_leads['partner']
            local_context['partner_leads'] = partner_leads['leads']
            email_template_obj.send_mail(cr, uid, template_id, ids[0], context=local_context)
            lead_ids = [lead['lead_id'].id for lead in partner_leads['leads']]
            lead_obj.write(cr, uid, lead_ids, {'partner_assigned_id': partner_id, 'user_id': partner_leads['partner'].user_id.id})
            self.pool.get('crm.lead').message_subscribe(cr, uid, lead_ids, [partner_id], context=context)
        return True

    def get_portal_url(self, cr, uid, ids, context=None):
        portal_link = "%s/?db=%s" % (self.pool.get('ir.config_parameter').get_param(cr, uid, 'web.base.url'), cr.dbname)
        return portal_link

    _columns = {
        'forward_type': fields.selection([('single', 'a single partner: manual selection of partner'), ('assigned', "several partners: automatic assignation, using GPS coordinates and partner's grades"), ], 'Forward selected leads to'),
        'partner_id': fields.many2one('res.partner', 'Forward Leads To'),
        'assignation_lines': fields.one2many('crm.lead.assignation', 'forward_id', 'Partner Assignation'),
        'show_mail': fields.boolean('Show the email will be sent'),
        'body': fields.html('Contents', help='Automatically sanitized HTML contents'),
    }

    _defaults = {
        'forward_type': 'single',
    }


class crm_lead_assignation (osv.TransientModel):
    _name = 'crm.lead.assignation'
    _columns = {
        'forward_id': fields.many2one('crm.lead.forward.to.partner', 'Partner Assignation'),
        'lead_id': fields.many2one('crm.lead', 'Lead'),
        'lead_location': fields.char('Lead Location', size=128),
        'partner_assigned_id': fields.many2one('res.partner', 'Assigned Partner'),
        'partner_location': fields.char('Partner Location', size=128),
        'lead_link': fields.char('Lead  Single Links', size=128),
    }

    def on_change_lead_id(self, cr, uid, ids, lead_id, context=None):
        if not context:
            context = {}
        if not lead_id:
            return {'value': {'lead_location': False}}
        lead = self.pool.get('crm.lead').browse(cr, uid, lead_id, context=context)
        lead_location = []
        if lead.country_id:
            lead_location.append(lead.country_id.name)
        if lead.city:
            lead_location.append(lead.city)
        return {'value': {'lead_location': ", ".join(lead_location)}}

    def on_change_partner_assigned_id(self, cr, uid, ids, partner_assigned_id, context=None):
        if not context:
            context = {}
        if not partner_assigned_id:
            return {'value': {'lead_location': False}}
        partner = self.pool.get('res.partner').browse(cr, uid, partner_assigned_id, context=context)
        partner_location = []
        if partner.country_id:
            partner_location.append(partner.country_id.name)
        if partner.city:
            partner_location.append(partner.city)
        return {'value': {'partner_location': ", ".join(partner_location)}}

# # vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
