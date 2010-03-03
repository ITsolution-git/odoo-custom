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

import time
import re
import os
import base64
import tools
import mx.DateTime

from tools.translate import _
from osv import fields 
from osv import osv 
from osv import orm
from osv.orm import except_orm

import crm

class case(osv.osv):
    _inherit = 'crm.case'
    _columns = {
        'date_action_last': fields.datetime('Last Action', readonly=1),
        'date_action_next': fields.datetime('Next Action', readonly=1),
    }

    def remind_partner(self, cr, uid, ids, context={}, attach=False):
        return self.remind_user(cr, uid, ids, context, attach,
                destination=False)

    def remind_user(self, cr, uid, ids, context={}, attach=False, 
            destination=True):
        for case in self.browse(cr, uid, ids):
            if not case.section_id.reply_to:
                raise osv.except_osv(_('Error!'), ("Reply To is not specified in Section"))
            if not case.email_from:
                raise osv.except_osv(_('Error!'), ("Partner Email is not specified in Case"))
            if case.section_id.reply_to and case.email_from:
                src = case.email_from
                dest = case.section_id.reply_to
                body = case.email_last or case.description
                if not destination:
                    src, dest = dest, src
                    if case.user_id.signature:
                        body += '\n\n%s' % (case.user_id.signature or '')
                dest = [dest]

                attach_to_send = None

                if attach:
                    attach_ids = self.pool.get('ir.attachment').search(cr, uid, [('res_model', '=', 'crm.case'), ('res_id', '=', case.id)])
                    attach_to_send = self.pool.get('ir.attachment').read(cr, uid, attach_ids, ['datas_fname','datas'])
                    attach_to_send = map(lambda x: (x['datas_fname'], base64.decodestring(x['datas'])), attach_to_send)

                # Send an email
                flag = tools.email_send(
                    src,
                    dest,
                    "Reminder: [%s] %s" % (str(case.id), case.name, ),
                    self.format_body(body),
                    reply_to=case.section_id.reply_to,
                    openobject_id=str(case.id),
                    attach=attach_to_send
                )
                if flag:
                    raise osv.except_osv(_('Email!'),("Email Successfully Sent"))
                else:
                    raise osv.except_osv(_('Email Fail!'),("Email is not sent successfully"))
        return True    

    def _check(self, cr, uid, ids=False, context={}):
        '''
        Function called by the scheduler to process cases for date actions
        Only works on not done and cancelled cases
        '''
        cr.execute('select * from crm_case \
                where (date_action_last<%s or date_action_last is null) \
                and (date_action_next<=%s or date_action_next is null) \
                and state not in (\'cancel\',\'done\')',
                (time.strftime("%Y-%m-%d %H:%M:%S"),
                    time.strftime('%Y-%m-%d %H:%M:%S')))
        ids2 = map(lambda x: x[0], cr.fetchall() or [])        
        cases = self.browse(cr, uid, ids2, context)
        return self._action(cr, uid, cases, False, context=context)        

    def _action(self, cr, uid, cases, state_to, scrit=None, context={}):     
        if not context:
            context = {}
        context['state_to'] = state_to        
        rule_obj = self.pool.get('base.action.rule')
        model_obj = self.pool.get('ir.model')
        model_ids = model_obj.search(cr, uid, [('model','=',self._name)])        
        rule_ids = rule_obj.search(cr, uid, [('name','=',model_ids[0])])
        return rule_obj._action(cr, uid, rule_ids, cases, scrit=scrit, context=context)

    def format_body(self, body):        
        return self.pool.get('base.action.rule').format_body(body)

    def format_mail(self, obj, body):
        return self.pool.get('base.action.rule').format_mail(obj, body)
case()

class base_action_rule(osv.osv):
    _inherit = 'base.action.rule'
    _description = 'Action Rules'
    
    def do_check(self, cr, uid, action, obj, context={}):
        ok = super(base_action_rule, self).do_check(cr, uid, action, obj, context=context)
        
        if hasattr(obj, 'section_id'):
            ok = ok and (not action.trg_section_id or action.trg_section_id.id==obj.section_id.id)
        if hasattr(obj, 'categ_id'):
            ok = ok and (not action.trg_categ_id or action.trg_categ_id.id==obj.categ_id.id)
        if hasattr(obj, 'history_line'):
            ok = ok and (not action.trg_max_history or action.trg_max_history<=(len(obj.history_line)+1))
            reg_history = action.regex_history
            result_history = True
            if reg_history:
                ptrn = re.compile(str(reg_history))
                if obj.history_line:
                    _result = ptrn.search(str(obj.history_line[0].description))
                    if not _result:
                        result_history = False
            regex_h = not reg_history or result_history
            ok = ok and regex_h
        return ok

    def do_action(self, cr, uid, action, model_obj, obj, context={}):
        res = super(base_action_rule, self).do_action(cr, uid, action, model_obj, obj, context=context)         
        write = {}
        
        if action.act_section_id:
            obj.section_id = action.act_section_id
            write['section_id'] = action.act_section_id.id        
        
        if hasattr(obj, 'email_cc') and action.act_email_cc:
            if '@' in (obj.email_cc or ''):
                emails = obj.email_cc.split(",")
                if  obj.act_email_cc not in emails:# and '<'+str(action.act_email_cc)+">" not in emails:
                    write['email_cc'] = obj.email_cc+','+obj.act_email_cc
            else:
                write['email_cc'] = obj.act_email_cc
        
        model_obj.write(cr, uid, [obj.id], write, context)
        emails = []
        if hasattr(obj, 'email_from') and action.act_mail_to_partner:
            emails.append(obj.email_from)
        emails = filter(None, emails)
        if len(emails) and action.act_mail_body:
            emails = list(set(emails))
            self.email_send(cr, uid, obj, emails, action.act_mail_body)
        return True
   
    
base_action_rule()

class base_action_rule_line(osv.osv):
    _inherit = 'base.action.rule.line'

    def state_get(self, cr, uid, context={}):
        res = super(base_action_rule_line, self).state_get(cr, uid, context=context)   
        return res + [('escalate','Escalate')] + crm.AVAILABLE_STATES

    def priority_get(self, cr, uid, context={}):
        res = super(base_action_rule_line, self).priority_get(cr, uid, context=context) 
        return res + crm.AVAILABLE_PRIORITIES
    
    _columns = {        
        'trg_section_id': fields.many2one('crm.case.section', 'Section'),
        'trg_max_history': fields.integer('Maximum Communication History'),
        'trg_categ_id':  fields.many2one('crm.case.categ', 'Category'),        
        'regex_history' : fields.char('Regular Expression on Case History', size=128),
        'act_section_id': fields.many2one('crm.case.section', 'Set section to'),        
        'act_categ_id': fields.many2one('crm.case.categ', 'Set Category to'),
        'act_mail_to_partner': fields.boolean('Mail to partner',help="Check this if you want the rule to send an email to the partner."),        
    }

base_action_rule_line()
