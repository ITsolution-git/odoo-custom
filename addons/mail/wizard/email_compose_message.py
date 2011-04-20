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

class email_compose_message(osv.osv_memory):
    _name = 'email.compose.message'
    _inherit = 'email.message.common'
    _description = 'This is the wizard for Compose E-mail'

    def default_get(self, cr, uid, fields, context=None):
        if context is None:
            context = {}
        result = super(email_compose_message, self).default_get(cr, uid, fields, context=context)
        vals = {}
        if context.get('email_model') and context.get('email_res_id'):
            vals = self.get_value(cr, uid, context.get('email_model'), context.get('email_res_id'), context)
        elif context.get('message_id', False):
            vals = self.get_message_data(cr, uid, int(context.get('message_id', False)), context)
        else:
            result['model'] = context.get('email_model', False)

        if not vals:
            return result

        if 'subject' in fields:
            result.update({'subject' : vals.get('name','')})

        if 'email_to' in fields:
            result.update({'email_to' : vals.get('email_to','')})

        if 'email_from' in fields:
            result.update({'email_from' : vals.get('email_from','')})

        if 'body' in fields:
            result.update({'body' : vals.get('description','')})

        if 'model' in fields:
            result.update({'model' : vals.get('model','')})

        if 'email_cc' in fields:
            result.update({'email_cc' : vals.get('email_cc','')})

        if 'email_bcc' in fields:
            result.update({'email_bcc' : vals.get('email_bcc','')})

        if 'res_id' in fields:
            result.update({'res_id' : vals.get('res_id',0)})

        if 'reply_to' in fields:
            result['reply_to'] = vals.get('reply_to','')

        if 'message_id' in fields:
            result['message_id'] =  vals.get('message_id','')

        if 'attachment_ids' in fields:
            result['attachment_ids'] = vals.get('attachment_ids',[])

        if 'user_id' in fields:
            result['user_id'] = vals.get('user_id',False)

        if 'references' in fields:
            result['references'] = vals.get('references',False)

        if 'sub_type' in fields:
            result['sub_type'] = vals.get('sub_type',False)

        if 'headers' in fields:
            result['headers'] = vals.get('headers',False)

        if 'priority' in fields:
            result['priority'] = vals.get('priority',False)

        if 'debug' in fields:
            result['debug'] = vals.get('debug',False)

        return result

    def _get_records(self, cr, uid, context=None):
        """
        Return Records of particular  Model
        """
        if context is None:
            context = {}
        record_ids = []
        model_pool = False
        if context.get('message_id'):
            message_pool = self.pool.get('email.message')
            message_data = message_pool.browse(cr, uid, int(context.get('message_id')), context)
            model_pool =  self.pool.get(message_data.model)
            record_ids = [message_data.res_id]
        elif context.get('email_model',False):
            model =  context.get('email_model')
            model_pool =  self.pool.get(model)
            record_ids = context.get('email_res_id') and [context.get('email_res_id')] or []
            if not record_ids:
                record_ids = model_pool.search(cr, uid, [])
        if model_pool:
            return model_pool.name_get(cr, uid, record_ids, context)
        return []

    _columns = {
        'attachment_ids': fields.many2many('ir.attachment','email_message_send_attachment_rel', 'wizard_id', 'attachment_id', 'Attachments'),
        'debug':fields.boolean('Debug', readonly=True),
        'res_id':fields.selection(_get_records, 'Referred Document'),
    }

    def get_value(self, cr, uid, model, res_id, context=None):
        return {}

    def get_message_data(self, cr, uid, message_id, context=None):
        if context is None:
            context = {}
        result = {}
        message_pool = self.pool.get('email.message')
        if message_id:
            message_data = message_pool.browse(cr, uid, message_id, context)
            subject = tools.ustr(message_data and message_data.subject or '')
            if context.get('mail','') == 'reply':
                subject = "Re :- " + subject

            description =  message_data and message_data.body  or ''
            message_body = False
            if context.get('mail','') == 'reply':
                header = '-------- Original Message --------'
                sender = 'From: %s'  % tools.ustr(message_data.email_from or '')
                email_to = 'To: %s' %  tools.ustr(message_data.email_to or '')
                sentdate = 'Date: %s' % message_data.date
                desc = '\n > \t %s' % tools.ustr(description.replace('\n', "\n > \t") or '')
                description = '\n'.join([header, sender, email_to, sentdate, desc])

            result.update({
                    'body' : description,
                    'subject' : subject,
                    'message_id' :  message_data and message_data.message_id or False,
                    'attachment_ids' : message_data and message_pool.read(cr, uid, message_id, ['attachment_ids'])['attachment_ids'] or [],
                    'res_id' : message_data and message_data.res_id or False,
                    'email_from' : message_data and message_data.email_to or False,
                    'email_to' : message_data and message_data.email_from or False,
                    'email_cc' : message_data and message_data.email_cc or False,
                    'email_bcc' : message_data and message_data.email_bcc or False,
                    'reply_to' : message_data and message_data.reply_to or False,
                    'model' : message_data and message_data.model or False,
                    'user_id' : message_data and message_data.user_id and message_data.user_id.id or False,
                    'references' : message_data and message_data.references and tools.ustr(message_data.references) or False,
                    'sub_type' : message_data and message_data.sub_type or False,
                    'headers' : message_data and message_data.headers or False,
                    'priority' : message_data and message_data.priority or False,
                    'debug': message_data and message_data.debug or False
                })

        return result

    def on_change_referred_doc(self, cr, uid, ids, model, resource_id, context=None):
        if context is None:
            context = {}
        if context.get('mail') == 'reply':
            return {'value':{}}
        result = {}
        if resource_id and model:
            vals = self.get_value(cr, uid, model, resource_id, context)
            if vals:
                result.update({
                            'email_from':  vals.get('email_from',''),
                            'email_to':  vals.get('email_to',''),
                            'subject':  vals.get('name',''),
                            'body':  vals.get('description',''),
                            'email_cc':  vals.get('email_cc',''),
                            'email_bcc':  vals.get('email_bcc',''),
                            'reply_to':  vals.get('reply_to',''),
                        })
        return {'value': result}


    def save_to_drafts(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        email_id = self.save_to_mailbox(cr, uid, ids, context=context)
        self.pool.get('email.message').write(cr, uid, email_id, {'state': 'outgoing'}, context)
        return {'type': 'ir.actions.act_window_close'}

    def send_mail(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        email_id = self.save_to_mailbox(cr, uid, ids, context)
        return {'type': 'ir.actions.act_window_close'}

    def save_to_mailbox(self, cr, uid, ids, context=None):
        email_ids = []
        email_message_pool = self.pool.get('email.message')
        attachment = {}
        for mail in self.browse(cr, uid, ids, context=context):
            for attach in mail.attachment_ids:
                attachment[attach.datas_fname] = attach.datas
            references = False
            message_id = False
            if context.get('mail',False) == 'reply' and  mail.message_id:
                references = mail.references and mail.references + "," + mail.message_id or mail.message_id
            else:
                message_id = mail.message_id
            email_id = email_message_pool.schedule_with_attach(cr, uid, mail.email_from, mail.email_to, mail.subject, mail.body,
                    model=mail.model, email_cc=mail.email_cc, email_bcc=mail.email_bcc, reply_to=mail.reply_to,
                    attach=attachment, message_id=message_id, references=references, openobject_id=int(mail.res_id), debug=mail.debug,
                    subtype=mail.sub_type, x_headers=mail.headers, priority=mail.priority, smtp_server_id=mail.smtp_server_id and mail.smtp_server_id.id, context=context)
            email_ids.append(email_id)
        return email_ids

email_compose_message()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
