# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2009 Sharoon Thomas
#    Copyright (C) 2010-Today OpenERP SA (<http://www.openerp.com>)
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
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################

from osv import osv, fields
from tools.translate import _
import tools


class email_template_preview(osv.osv_memory):
    _inherit = "email.template"
    _name = "email_template.preview"
    _description = "Email Template Preview"
    _rec_name = "subject"

    
    def get_email_template(self, cr, uid, template_id=None, record_id=None, context=None):
        if context is None:
            context = {}
        
        template_id = context.get('template_id', False)
        record_id = context.get('src_rec_ids',[]) and context.get('src_rec_ids')[0]
        return super(email_template_preview, self).get_email_template(cr, uid, template_id, record_id, context=context)
        
    

    def _get_records(self, cr, uid, context=None):
        """
        Return Records of particular Email Template's Model  
        """
        if context is None:
            context = {}

        template_id = context.get('template_id', False)
        if not template_id:
            return []
        template_pool = self.pool.get('email.template')
        model_pool = self.pool.get('ir.model')
        template = template_pool.browse(cr, uid, int(template_id), context=context)
        template_object = template.model_id
        model =  self.pool.get(template_object.model)
        record_ids = model.search(cr, uid, [], 0, 20, 'id', context=context)
        default_id = context.get('default_res_id')
        if default_id and default_id not in record_ids:
            record_ids.insert(0, default_id)
        
        return model.name_get(cr, uid, record_ids, context)
        

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        result = super(email_template_preview, self).default_get(cr, uid, fields, context=context)

        template_pool = self.pool.get('email.template')
        template_id = context.get('template_id',False)
        if 'res_id' in fields:
            records = self._get_records(cr, uid, context=context)
            result['res_id'] = records and records[0][0] or False # select first record as a Default
        if template_id and 'model_id' in fields:
            result['model_id'] = template_pool.read(cr, uid, int(template_id), ['model_id'], context).get('model_id', False)
        return result

    _columns = {
        'res_id':fields.selection(_get_records, 'Referred Document'),
    }
    _defaults = {
    }
    def on_change_ref(self, cr, uid, ids, res_id, context=None):
        if context is None:
            context = {}
        if not res_id:
            return {}
        vals = {}
        if context == {}:
            context = self.context 

        template_pool = self.pool.get('email.template')
        template = self.get_email_template(cr, uid, context)
        model = template.model
        vals['email_to'] = self.get_template_value(cr, uid, template.email_to, model, res_id, context)
        vals['email_cc'] = self.get_template_value(cr, uid, template.email_cc, model, res_id, context)
        vals['email_bcc'] = self.get_template_value(cr, uid, template.email_bcc, model, res_id, context)
        vals['reply_to'] = self.get_template_value(cr, uid, template.reply_to, model, res_id, context)
        if template.message_id:
            vals['message_id'] = self.get_template_value(cr, uid, message_id, model, res_id, context)
        elif template.track_campaign_item:
            vals['message_id'] = tools.misc.generate_tracking_message_id(rel_model_ref)
        vals['subject'] = self.get_template_value(cr, uid, template.subject, model, res_id, context)
        vals['description'] = self.get_template_value(cr, uid, template.description, model, res_id, context)
        vals['body_html'] = self.get_template_value(cr, uid, template.body_html, model, res_id, context)
        vals['report_name'] = self.get_template_value(cr, uid, template.report_name, model, res_id, context)
        return {'value':vals}

email_template_preview()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
