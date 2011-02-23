# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
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

from osv import osv
from osv import fields
import tools
from tools.translate import _

class email_compose_message(osv.osv_memory):
    _inherit = 'email.compose.message'

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        result = super(email_compose_message, self).default_get(cr, uid, fields, context=context)
        if context.get('email_model',False) and context.get('email_model') == 'hr.evaluation.interview' and 'model' in fields:
            result['model'] = context.get('email_model','')
        return result

    def _get_records(self, cr, uid, context=None):
        """
        Return Records of particular  Model
        """
        if context is None:
            context = {}
        record_ids = []
        if context.get('email_model',False) and context.get('email_model') == 'hr.evaluation.interview':
            model_pool =  self.pool.get(context.get('email_model'))
            record_ids = model_pool.search(cr, uid, [('state','=','waiting_answer')])
            return model_pool.name_get(cr, uid, record_ids, context)
        else:
            return super(email_compose_message, self)._get_records(cr, uid, context=context)

    _columns = {
        'resource_id':fields.selection(_get_records, 'Referred Document'),
    }

    def on_change_referred_doc(self, cr, uid, ids, model, resource_id, context=None):
        if context is None:
            context = {}
        if context.get('mail') == 'reply':
            return {'value':{}}
        result = super(email_compose_message, self).on_change_referred_doc(cr, uid, ids, model, resource_id, context=context)
        value = {}
        if not result.get('value'):
            result.update({'value':{}})

        if model == 'hr.evaluation.interview' and resource_id:
            model_pool = self.pool.get(model)
            record_data = model_pool.browse(cr, uid, resource_id, context)
            if record_data.state == "waiting_answer":
                msg = _("Hello %s, \n\n Kindly post your response for '%s' survey interview. \n\n Thanks,")  %(record_data.user_to_review_id.name, record_data.survey_id.title)
                result['value'].update({'email_from': tools.config.get('email_from','')})
                result['value'].update({'email_to': record_data.user_to_review_id.work_email or False})
                result['value'].update({'name': _("Reminder to fill up Survey")})
                result['value'].update({'description': msg })
                result['value'].update({'res_id': resource_id})
        return result

email_compose_message()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
