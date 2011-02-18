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

from osv import osv, fields
import netsvc
from tools.translate import _
import tools

class email_message_wizard_send(osv.osv_memory):
    _name = 'email.message.wizard_send'
    _inherit = 'email.message'
    _description = 'This is the wizard for send e-mail'

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        result = super(email_message_wizard_send, self).default_get(cr, uid, fields, context=context)
        message_pool = self.pool.get('email.message')

        model_pool = self.pool.get('ir.model')
        message_id = context.get('message_id', False)
        message_data = None
        if message_id:
            message_data = message_pool.browse(cr, uid, message_id, context)

        if 'template_id' in fields:
            result['template_id'] = context.get('default_template_id',False) or (message_data and message_data.template_id and message_data.template_id.id or False)

        if 'smtp_server_id' in fields:
            result['smtp_server_id'] = context.get('default_smtp_server_id',False) or (message_data and message_data.smtp_server_id and message_data.smtp_server_id.id or False)

        if 'message_id' in fields:
            result['message_id'] =  context.get('default_message_id','') or (message_data and message_data.message_id)

        if 'attachment_ids' in fields:
            result['attachment_ids'] =  context.get('default_attachment_ids',[]) or (message_data and message_pool.read(cr, uid, message_id, ['attachment_ids'])['attachment_ids'])

        if 'res_id' in fields:
            result['res_id'] =  context.get('default_res_id',0) or (message_data and message_data.res_id)

        if 'email_from' in fields:
            result['email_from'] =  context.get('default_email_from','') or (message_data and message_data.email_from)

        if 'email_to' in fields:
            result['email_to'] =  context.get('default_email_to','') or (message_data and message_data.email_to)

        if 'email_cc' in fields:
            result['email_cc'] =  context.get('default_email_cc', '') or (message_data and message_data.email_cc)

        if 'email_bcc' in fields:
            result['email_bcc'] =  context.get('default_email_bcc', '') or (message_data and message_data.email_bcc)

        if 'name' in fields:
            result['name'] = "Re : " +  tools.ustr(context.get('default_name', '') or (message_data and message_data.name))

        if 'description' in fields:
            description =  context.get('default_description', '') or (message_data and message_data.description and message_data.description or '')
            header = '-------- Original Message --------'
            sender = 'From: %s'  % tools.ustr(message_data.email_from or '')
            email_to = 'To: %s' %  tools.ustr(message_data.email_to or '')
            sentdate = 'Date: %s' % message_data.date
            desc = '\n > \t %s' % tools.ustr(description.replace('\n', "\n > \t") or '')
            original = [header, sender, email_to, sentdate, desc]
            result['description'] = '\n'.join(original)

        if 'reply_to' in fields:
            result['reply_to'] = context.get('default_reply_to', '') or (message_data and message_data.reply_to)

        if 'model' in fields:
            result['model'] = context.get('default_model', '') or (message_data and message_data.model)

        if 'user_id' in fields:
            result['user_id'] = context.get('default_user_id', False) or (message_data and message_data.user_id and message_data.user_id.id or False)

        if 'references' in fields:
            result['references'] = tools.ustr(context.get('default_references', '') or (message_data and message_data.references))

        if 'sub_type' in fields:
            result['sub_type'] = context.get('default_sub_type') or (message_data and message_data.sub_type)

        if 'headers' in fields:
            result['headers'] = context.get('default_headers', {}) or (message_data and message_data.headers)

        if 'priority' in fields:
            result['priority'] = context.get('default_priority') or (message_data and message_data.priority)

        if 'partner_id' in fields:
            result['partner_id'] = context.get('default_partner_id', False) or (message_data and message_data.partner_id and message_data.partner_id.id or False)

        if 'debug' in fields:
            result['debug'] = context.get('default_debug', False) or (message_data and message_data.debug)

        return result

    _columns = {
        'attachment_ids': fields.many2many('ir.attachment','email_message_send_attachment_rel', 'wizard_id', 'attachment_id', 'Attachments'),
    }

    def save_to_drafts(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        email_id = self.save_to_mailbox(cr, uid, ids, context=context)
        self.pool.get('email.message').write(cr, uid, email_id, {'folder':'drafts', 'state': 'draft'}, context)
        return {}

    def send_mail(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        email_id = self.save_to_mailbox(cr, uid, ids, context)
        return {}

    def save_to_mailbox(self, cr, uid, ids, context=None):
        email_ids = []
        email_message_pool = self.pool.get('email.message')
        attachment = []
        for mail in self.browse(cr, uid, ids, context=context):
            for attach in mail.attachment_ids:
                attachment.append((attach.datas_fname, attach.datas))
            email_id = email_message_pool.email_send(cr, uid, mail.email_from, mail.email_to, mail.name, mail.description,
                    model=mail.model, email_cc=mail.email_cc, email_bcc=mail.email_bcc, reply_to=mail.reply_to,
                    attach=attachment, message_id=mail.message_id, openobject_id=mail.res_id, debug=mail.debug,
                    subtype=mail.sub_type, x_headers=mail.headers, priority=mail.priority, smtp_server_id=mail.smtp_server_id and mail.smtp_server_id.id, context=context)
            email_ids.append(email_id)
        return email_ids

email_message_wizard_send()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
