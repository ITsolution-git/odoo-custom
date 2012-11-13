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

import tools

from osv import osv
from osv import fields


class mail_compose_message(osv.TransientModel):
    _inherit = 'mail.compose.message'

    def _get_templates(self, cr, uid, context=None):
        if context is None:
            context = {}
        model = False
        email_template_obj = self.pool.get('email.template')
        message_id = context.get('default_parent_id', context.get('message_id', context.get('active_id')))

        if context.get('default_composition_mode') == 'reply' and message_id:
            message_data = self.pool.get('mail.message').browse(cr, uid, message_id, context=context)
            if message_data:
                model = message_data.model
        else:
            model = context.get('default_model', context.get('active_model'))

        if model:
            record_ids = email_template_obj.search(cr, uid, [('model', '=', model)], context=context)
            return email_template_obj.name_get(cr, uid, record_ids, context) + [(False, '')]
        return []

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        result = super(mail_compose_message, self).default_get(cr, uid, fields, context=context)
        result['template_id'] = context.get('default_template_id', context.get('mail.compose.template_id', False))

        # pre-render the template if any
        if result.get('use_template') and result.get('template_id'):
            onchange_res = self.onchange_use_template(cr, uid, [], result.get('use_template'), result.get('template_id'),
                result.get('composition_mode'), result.get('model'), result.get('res_id'), context=context)
            result.update(onchange_res['value'])
        return result

    _columns = {
        'use_template': fields.boolean('Use Template'),
        # incredible hack of the day: size=-1 means we want an int db column instead of an str one
        'template_id': fields.selection(_get_templates, 'Template', size=-1),
    }

    _defaults = {
        'use_template': True,
    }

    def onchange_template_id(self, cr, uid, ids, use_template, template_id, composition_mode, model, res_id, context=None):
        """ - use_template not set: return default_get
            - use_template set in mass_mailing: we cannot render, so return the template values
            - use_template set: return rendered values """
        if use_template and template_id and composition_mode == 'mass_mail':
            values = self.pool.get('email.template').read(cr, uid, template_id, ['subject', 'body_html'], context)
            values.pop('id')
        elif use_template and template_id:
            values = self.generate_email_for_composer(cr, uid, template_id, res_id, context=context)
            # transform attachments into attachment_ids
            values['attachment_ids'] = []
            ir_attach_obj = self.pool.get('ir.attachment')
            for attach_fname, attach_datas in values.pop('attachments', []):
                data_attach = {
                    'name': attach_fname,
                    'datas': attach_datas,
                    'datas_fname': attach_fname,
                    'res_model': model,
                    'res_id': res_id,
                }
                values['attachment_ids'].append(ir_attach_obj.create(cr, uid, data_attach, context=context))
        else:
            values = self.default_get(cr, uid, ['body', 'body_html', 'subject', 'partner_ids', 'attachment_ids'], context=context)

        if values.get('body_html'):
            values['body'] = values.pop('body_html')
        values.update(use_template=use_template, template_id=template_id)
        return {'value': values}

    def toggle_template(self, cr, uid, ids, context=None):
        """ hit toggle template mode button: calls onchange_use_template to
            emulate an on_change, then writes the values to update the form. """
        for record in self.browse(cr, uid, ids, context=context):
            onchange_res = self.onchange_use_template(cr, uid, ids, not record.use_template,
                record.template_id, record.composition_mode, record.model, record.res_id, context=context).get('value', {})
            # update partner_ids and attachment_ids
            onchange_res['partner_ids'] = [(4, partner_id) for partner_id in onchange_res.pop('partner_ids', [])]
            onchange_res['attachment_ids'] = [(4, attachment_id) for attachment_id in onchange_res.pop('attachment_ids', [])]
            record.write(onchange_res)
        return True

    def onchange_use_template(self, cr, uid, ids, use_template, template_id, composition_mode, model, res_id, context=None):
        """ onchange_use_template (values: True or False).  If use_template is
            False, we do as an onchange with template_id False for values """
        values = self.onchange_template_id(cr, uid, ids, use_template,
            template_id, composition_mode, model, res_id, context=context)
        # force html when using templates
        if use_template:
            values['value']['content_subtype'] = 'html'
        return values

    def save_as_template(self, cr, uid, ids, context=None):
        """ hit save as template button: current form value will be a new
            template attached to the current document. """
        email_template = self.pool.get('email.template')
        ir_model_pool = self.pool.get('ir.model')
        for record in self.browse(cr, uid, ids, context=context):
            model_ids = ir_model_pool.search(cr, uid, [('model', '=', record.model)], context=context)
            model_id = model_ids and model_ids[0] or False
            model_name = ''
            if model_id:
                model_name = ir_model_pool.browse(cr, uid, model_id, context=context).name
            template_name = "%s: %s" % (model_name, tools.ustr(record.subject))
            values = {
                'name': template_name,
                'subject': record.subject or False,
                'body_html': record.body or False,
                'model_id': model_id or False,
                'attachment_ids': [(6, 0, [att.id for att in record.attachment_ids])]
            }
            template_id = email_template.create(cr, uid, values, context=context)
            record.write({'template_id': template_id, 'use_template': True})
        return True

    #------------------------------------------------------
    # Wizard validation and send
    #------------------------------------------------------

    def generate_email_for_composer(self, cr, uid, template_id, res_id, context=None):
        """ Call email_template.generate_email(), get fields relevant for
            mail.compose.message, transform email_cc and email_to into partner_ids """
        template_values = self.pool.get('email.template').generate_email(cr, uid, template_id, res_id, context=context)
        # filter template values
        fields = ['body', 'body_html', 'subject', 'email_to', 'email_recipients', 'email_cc', 'attachments']
        values = dict((field, template_values[field]) for field in fields if template_values.get(field))
        values['body'] = values.pop('body_html', '')
        # transform email_to, email_cc into partner_ids
        values['partner_ids'] = []

        mails = tools.email_split(values.pop('email_to', '') + ' ' + values.pop('email_cc', ''))
        for mail in mails:
            partner_id = self.pool.get('res.partner').find_or_create(cr, uid, mail, context=context)
            values['partner_ids'].append(partner_id)
        partner_ids = values.pop('email_recipients', '').split(',')
        for partner_id in partner_ids:
            values['partner_ids'].append(int(partner_id))

        values['partner_ids'] = list(set(values['partner_ids']))

        return values

    def render_message(self, cr, uid, wizard, res_id, context=None):
        """ Generate an email from the template for given (model, res_id) pair.
            This method is meant to be inherited by email_template that will
            produce a more complete dictionary, with email_to, ...
        """
        # generate the composer email
        values = self.generate_email_for_composer(cr, uid, wizard.template_id, res_id, context=context)
        # get values to return
        email_dict = super(mail_compose_message, self).render_message(cr, uid, wizard, res_id, context)
        email_dict.update(values)
        return email_dict

    def render_template(self, cr, uid, template, model, res_id, context=None):
        return self.pool.get('email.template').render_template(cr, uid, template, model, res_id, context=context)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
