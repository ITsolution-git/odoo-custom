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

from osv import fields, osv
from lxml import etree

from tools.translate import _

#TODO: context is a kwarg and thus should be used as 'context=context'
#TODO: remove trailing spaces and commented code

class followup(osv.osv):
    _name = 'account_followup.followup'
    _description = 'Account Follow-up'
    _rec_name = 'name'
    _columns = {
        #'name': fields.char('Name', size=64, required=True),         
        #'description': fields.text('Description'),
        'followup_line': fields.one2many('account_followup.followup.line', 'followup_id', 'Follow-up'),
        'company_id': fields.many2one('res.company', 'Company', required=True),   
        'name': fields.related('company_id', 'name', string = "Name"),
    }
    _defaults = {
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'account_followup.followup', context=c),
    }
    _sql_constraints = [('company_uniq', 'unique(company_id)', 'Only one follow-up per company is allowed')] 
    
followup()



class followup_line(osv.osv):    
    
    def _get_default_template(self, cr, uid, ids, context=None):
        dummy, templ = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_followup', 'email_template_account_followup_default')
        return templ
    
    _name = 'account_followup.followup.line'
    _description = 'Follow-up Criteria'
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying a list of follow-up lines."),
        'delay': fields.integer('Due Days', help="The number of days after the due date of the invoice to wait before sending the reminder.  Could be negative if you want to send a polite alert beforehand."),
        #'start': fields.selection([('days','Net Days'),('end_of_month','End of Month')], 'Type of Term', size=64, required=True),
        'followup_id': fields.many2one('account_followup.followup', 'Follow Ups', required=True, ondelete="cascade"),
        'description': fields.text('Printed Message', translate=True),
        'send_email':fields.boolean('Send Email', help="When processing, it will send an email"),
        'send_letter':fields.boolean('Send Letter', help="When processing, it will print a letter"),
        'manual_action':fields.boolean('Manual Action', help="When processing, it will set the manual action to be taken for that customer. "),
        'manual_action_note':fields.text('Action Text', placeholder="e.g. Give a phone call, check with others , ..."),
        'manual_action_responsible_id':fields.many2one('res.users', 'Responsible', ondelete='set null'),
        'email_template_id':fields.many2one('email.template', 'Email Template', ondelete='set null'), 
        'email_body':fields.related('email_template_id', 'body_html', type='text', string="Email Message", relation="email.template", translate="True"),
    }
    _order = 'delay'
    _sql_constraints = [('days_uniq', 'unique(followup_id, delay)', 'Days of the follow-up levels must be different')] #TODO: ADD FOR multi-company!
    _defaults = {
        'send_email': True,
        'send_letter': False,
        'manual_action':False, 
        'description': """
        Dear %(partner_name)s,

Exception made if there was a mistake of ours, it seems that the following amount stays unpaid. Please, take appropriate measures in order to carry out this payment in the next 8 days.

Would your payment have been carried out after this mail was sent, please ignore this message. Do not hesitate to contact our accounting department at (+32).10.68.94.39.

Best Regards,
""",
    'email_template_id': _get_default_template,
    }
    
    
    
    
    def on_change_template(self, cr, uid, ids, template_id, context=None):
        #result = {}
        values = {}
        if template_id:
            template  = self.pool.get('email.template').browse(cr, uid, template_id, context=context)
            values = {
                'email_body':template.body_html,                      
                }
        return {'value': values}
            
    
    
    def _check_description(self, cr, uid, ids, context=None):
        for line in self.browse(cr, uid, ids, context=context):
            if line.description:
                try:
                    line.description % {'partner_name': '', 'date':'', 'user_signature': '', 'company_name': ''}
                except:
                    return False
        return True

    _constraints = [
        (_check_description, 'Your description is invalid, use the right legend or %% if you want to use the percent character.', ['description']),
    ]

followup_line()

class account_move_line(osv.osv):
    
    
    def set_kanban_state_litigation(self, cr, uid, ids, context=None):
        for l in self.browse(cr, uid, ids, context):
            self.write(cr, uid, [l.id], {'blocked': not l.blocked})
        return False
    
    def _get_result(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for aml in self.browse(cr, uid, ids, context): 
            res[aml.id] = aml.debit - aml.credit
        return res
    
    _inherit = 'account.move.line'
    _columns = {
        'followup_line_id': fields.many2one('account_followup.followup.line', 'Follow-up Level', ondelete='restrict'), #restrict deletion of the followup line
        'followup_date': fields.date('Latest Follow-up', select=True),
        'payment_commitment':fields.text('Commitment'),
        'payment_date':fields.date('Date'),
        #'payment_note':fields.text('Payment note'),
        'payment_next_action':fields.text('Next Action'),
        'result':fields.function(_get_result, type='float', method=True, string="Balance") #TODO: what difference with the balance field on account.move.line?
    }

account_move_line()

class email_template(osv.osv):
    _inherit = 'email.template'
    
    #Adds current_date to the context.  That way it can be used in the email templates
    #TODO: need information
    def render_template(self, cr, uid, template, model, res_id, context=None):
        context['current_date'] = fields.date.context_today(cr, uid, context) #change by inheritance
        return super(email_template, self).render_template(cr, uid, template, model, res_id, context)

email_template()


class res_partner(osv.osv):


    #TODO: that was not what we decided... 
    def fields_view_get(self, cr, uid, view_id=None, view_type=None, context=None, toolbar=False, submenu=False):
        res = super(res_partner, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, 
                                                       toolbar=toolbar, submenu=submenu)
        
        if view_type == 'form' and context and 'Followupfirst' in context.keys() and context['Followupfirst'] == True:
            doc = etree.XML(res['arch'], parser=None, base_url=None)
            first_node = doc.xpath("//page[@string='Payments Follow-up']")            
            #first_node[0].getparent().append(first_node[0])            
            root = first_node[0].getparent()            
            root.insert(0, first_node[0])
            res['arch'] = etree.tostring(doc)
        return res
        

#    def _get_latest_followup_date(self, cr, uid, ids, name, arg, context=None):
#        res = {}
#        for partner in self.browse(cr, uid, ids, context): 
#            amls = partner.accountmoveline_ids      
#            res[partner.id] = max([x.followup_date for x in amls]) if len(amls) else False            
#        return res
#    
#    
    #TODO: refactor these functions: remove this one, rework _get_latest and _get_newt_followup_level_id must call _get_latest
    def _get_latest_followup_level_id(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for partner in self.browse(cr, uid, ids, context):
            level_days = False
            res[partner.id] = False
            for accountmoveline in partner.accountmoveline_ids:
                if (accountmoveline.followup_line_id != False) and (not level_days or level_days < accountmoveline.followup_line_id.delay): 
                    level_days = accountmoveline.followup_line_id.delay
                    res[partner.id] = accountmoveline.followup_line_id.id
            #res[partner.id] = max(x.followup_line_id.delay for x in amls) if len(amls) else False
        return res
    
    
    def _get_latest(self, cr, uid, ids, names, arg, context=None):
        res={}
        for partner in self.browse(cr, uid, ids, context):
            amls = partner.accountmoveline_ids
            latest_date = False
            latest_level = False
            latest_level_without_lit = False
            latest_days = False
            latest_days_without_lit = False
            for aml in amls:                
                #Give initial value
                if latest_date == False:
                    latest_date = aml.followup_date
                    if aml.followup_line_id: 
                        latest_level = aml.followup_line_id.id                    
                        latest_days = aml.followup_line_id.delay
                if not aml.blocked and latest_level_without_lit == False and aml.followup_line_id: 
                    latest_level_without_lit = aml.followup_line_id.id 
                    latest_days_without_lit = aml.followup_line_id.delay
                #If initial value < ...
                if latest_date and latest_level:
                    if aml.followup_date > latest_date:
                        latest_date = aml.followup_date
                    if aml.followup_line_id and aml.followup_line_id.delay > latest_days:
                        latest_days = aml.followup_line_id.delay
                        latest_level = aml.followup_line_id.id
                if not aml.blocked and latest_level_without_lit and aml.followup_line_id and aml.followup_line_id.delay > latest_days_without_lit:
                    latest_days_without_lit = aml.followup_line_id.delay                     
                    latest_level_without_lit = aml.followup_line_id.id
            res[partner.id] = {'latest_followup_date': latest_date,
                               'latest_followup_level_id': latest_level, 
                               'latest_followup_level_id_without_lit': latest_level_without_lit}
        return res

            #Problems company id? / Method necessary?
            #TODO: must use the company_id of the uid + refactor
    def _get_next_followup_level_id(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for partner in self.browse(cr, uid, ids, context=context):
            latest_id = self._get_latest_followup_level_id(cr, uid, [partner.id], name, arg, context)[partner.id]
            latest = latest_id and self.pool.get('account_followup.followup.line').browse(cr, uid, latest_id, context=context) or False
            delay = False
            newlevel = False
            old_delay = False
            if latest: #if latest exists
                newlevel = latest.id
                old_delay = latest.delay
            fl_ar = self.pool.get('account_followup.followup.line').search(cr, uid, [('followup_id.company_id.id','=', partner.company_id.id)])            
            for fl_obj in self.pool.get('account_followup.followup.line').browse(cr, uid, fl_ar):
                if not old_delay: 
                    if not delay or fl_obj.delay < delay: 
                        delay = fl_obj.delay
                        newlevel = fl_obj.id
                else:
                    if (not delay and (fl_obj.delay > old_delay)) or ((fl_obj.delay < delay) and (fl_obj.delay > old_delay)):
                        delay = fl_obj.delay
                        newlevel = fl_obj.id
            res[partner.id] = newlevel
        return res


#    def _get_amount_overdue(self, cr, uid, ids, name, arg, context=None):
#        #Get the total amount in the account move lines that the customer owns us
#        res={}
#        print "get amount overdue"
#        for partner in self.browse(cr, uid, ids, context):
#            res[partner.id] = 0.0
#            for aml in partner.accountmoveline_ids:        
#                res[partner.id] = res[partner.id] + aml.debit - aml.credit  #or by using function field
#        return res
#    
    #TODO: remove
    def _get_amount_due(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for partner in self.browse(cr, uid, ids, context):
            res[partner.id] = partner.credit
        return res

    #TODO: to refactor and to comment. I don't get the 'else' statements...
    def do_partner_manual_action(self, cr, uid, partner_ids, context=None): 
        #partner_ids are res.partner ids #TODO: useless comment to remove
        for partner in self.browse(cr, uid, partner_ids, context): 
            if True: #(not partner.payment_next_action_date) and (not partner.payment_next_action) and (not partner.payment_responsible_id)
                action_text= ""
                #Check action
                if partner.payment_next_action:
                    action_text = partner.payment_next_action + " + " + partner.latest_followup_level_id_without_lit.manual_action_note
                else:
                    action_text = partner.latest_followup_level_id_without_lit.manual_action_note
                #Check minimum date
                action_date = False
                if partner.payment_next_action_date:
                    action_date = min(partner.payment_next_action_date, fields.date.context_today(cr, uid, context))
                else:
                    action_date =  fields.date.context_today(cr, uid, context)
                responsible_id = False
                #Check responsible
                if partner.payment_responsible_id:
                    responsible_id = partner.payment_responsible_id.id
                else:
                    if partner.latest_followup_level_id_without_lit.manual_action_responsible_id:
                        responsible_id = partner.latest_followup_level_id_without_lit.manual_action_responsible_id.id 
                                                                    
                self.write(cr, uid, [partner.id], {'payment_next_action_date': action_date, 
                                            'payment_next_action': action_text, 
                                            'payment_responsible_id': responsible_id})
                

    def do_partner_print(self, cr, uid, partner_ids, data, context=None):
        #partner_ids are ids from special view, not from res.partner        
        #data.update({'date': context['date']})
        if not partner_ids: 
            return {}
        data['partner_ids'] = partner_ids
        datas = {
             'ids': [],
             'model': 'account_followup.followup',
             'form': data
        }
        return {
            'type': 'ir.actions.report.xml', 
            'report_name': 'account_followup.followup.print', 
            'datas': datas, 
            }

    def do_partner_mail(self, cr, uid, partner_ids, context=None):
        #partner_ids are res.partner ids
        # If not defined by latest level, it will the default template if it can find it
        mtp = self.pool.get('email.template')
        unknown_mails = 0
        for partner in self.browse(cr, uid, partner_ids, context):
            print "Email", partner.email
            if partner.email != False and partner.email != '' and partner.email != ' ':
                if partner.latest_followup_level_id_without_lit and partner.latest_followup_level_id_without_lit.send_email and partner.latest_followup_level_id_without_lit.email_template_id.id != False :                
                    mtp.send_mail(cr, uid, partner.latest_followup_level_id_without_lit.email_template_id.id, partner.id, context=context)
                else :
                    mail_template_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_followup', 'email_template_account_followup_default')
                    mtp.send_mail(cr, uid, mail_template_id[1], partner.id, context=context)
            else:
                unknown_mails = unknown_mails + 1
                action_text = _("Email not sent because of email address of partner not filled in")
                if partner.payment_next_action_date:
                    payment_action_date = min(fields.date.context_today(cr, uid, context), partner.payment_next_action_date)
                else:
                    payment_action_date = fields.date.context_today(cr, uid, context)
                if partner.payment_next_action:
                    payment_next_action = partner.payment_next_action + " + " + action_text
                else:
                    payment_next_action = action_text
                self.write(cr, uid, [partner.id], {'payment_next_action_date': payment_action_date, 
                                                   'payment_next_action': payment_next_action}, context)
        return unknown_mails

    def action_done(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids,  {'payment_next_action_date': False, 'payment_next_action':'', 'payment_responsible_id': False}, context)
    
    def do_button_print(self, cr, uid, ids, context=None):
        #TODO: assert that ids is a list of 1 element only before doing ids[0]
        self.message_post(cr, uid, [ids[0]], body=_('Printed overdue payments report'), context=context)
        datas = {
             'ids': ids,
             'model': 'res.partner',
             'form': self.read(cr, uid, ids[0], context=context)
        }
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'account.overdue',
            'datas': datas,
            'nodestroy' : True
        }
        
    
    def do_button_mail(self, cr, uid, ids, context=None):
        self.do_partner_mail(cr, uid, ids, context)
        
        
    def _get_aml_storeids(self, cr, uid, ids, context=None):
        partnerlist = []
        for aml in self.pool.get("account.move.line").browse(cr, uid, ids, context):
            if aml.partner_id.id not in partnerlist: 
                partnerlist.append(aml.partner_id.id)
        return partnerlist
#    
#    def _get_am_storeids(self, cr, uid, ids, context=None):
#        partnerlist = []
#        for am in self.pool.get("account.move").browse(cr, uid, ids, context): 
#            if am.partner_id.id not in partnerlist: 
#                partnerlist.append(am.partner_id.id)
#                print am.partner_id.id
#        return partnerlist
#    
#    def _get_rec_storeids(self, cr, uid, ids, context=None):
#        partnerlist = []
#        for rec in self.pool.get("account.move.reconcile").browse(cr, uid, ids, context): 
#            for am in self.pool.get("account.move.line").browse(cr, uid, [x.id for x in rec.line_partial_ids], context):                
#                if am.partner_id.id not in partnerlist: 
#                    partnerlist.append(am.partner_id.id)
#        return partnerlist
#    
#    
#    def _get_aml_storeids2(self, cr, uid, ids, context=None):
#        partnerlist = []
#        for aml in self.pool.get("account.move.line").browse(cr, uid, ids, context):
#            if aml.partner_id not in partnerlist: 
#                partnerlist.append(aml.partner_id.id)
#        return partnerlist
#    
    
        

    _inherit = "res.partner"
    _columns = {
        'payment_responsible_id':fields.many2one('res.users', ondelete='set null', string='Followup Responsible', help="Responsible for making sure the action happens."), #TODO find better name for field
        #'payment_followup_level_id':fields.many2one('account_followup.followup.line', 'Followup line'),
        'payment_note':fields.text('Payment Note', help="Payment Note"), 
        'payment_next_action':fields.char('Next Action', 50, 
                                    help="This is the next action to be taken by the user.  It will automatically be set when the action fields are empty and the partner gets a follow-up level that requires a manual action. "), #Just an action #TODO: size=128
        'payment_next_action_date':fields.date('Next Action Date', 
                                    help="This is when further follow-up is needed.  The date will have been set to the current date if the action fields are empty and the partner gets a follow-up level that requires a manual action. "), # next action date
        'accountmoveline_ids':fields.one2many('account.move.line', 'partner_id', domain=['&', ('reconcile_id', '=', False), '&', 
                            ('account_id.active','=', True), '&', ('account_id.type', '=', 'receivable'), ('state', '!=', 'draft')]),  #TODO: find better name
        'latest_followup_date':fields.function(_get_latest, method=True, type='date', string="Latest Follow-up Date", 
                            help="Latest date that the follow-up level of the partner was changed", 
                            store={'account.move.line': (_get_aml_storeids, ['followup_line_id', 'followup_date'], 10)},  
                            multi="latest"), 
        'latest_followup_level_id':fields.function(_get_latest, method=True, 
            type='many2one', relation='account_followup.followup.line', string="Latest Follow-up Level", 
            help="The maximum follow-up level", 
            store={'account.move.line': (_get_aml_storeids, ['followup_line_id', 'followup_date'], 10)}, 
            multi="latest"), 
        'latest_followup_level_id_without_lit':fields.function(_get_latest, method=True, 
            type='many2one', relation='account_followup.followup.line', string="Latest Follow-up Level without litigation", 
            help="The maximum follow-up level without taking into account the account move lines with litigation", 
            store={'account.move.line': (_get_aml_storeids, ['followup_line_id', 'followup_date'], 10)}, 
            multi="latest"), 
        'next_followup_level_id':fields.function(_get_next_followup_level_id, method=True, type='many2one', relation='account_followup.followup.line', 
                                                 string="Next Level", help="The next follow-up level to come when the customer still refuses to pay",   
                                                 store={'account.move.line': (_get_aml_storeids, ['followup_line_id', 'followup_date'], 10)}),
        'payment_amount_due':fields.function(_get_amount_due, method=True, type='float', store=False), #TODO: use a fields.related
        #'credit':fields.function(_get_amount_overdue, method=True, type='float', string="Amount Overdue", 
#                                                 help="Amount Overdue: The amount the customer owns us", 
#                                                 store={'account.move.line': (_get_aml_storeids, ['followup_line_id', 'followup_date', 'debit', 'credit', 'invoice', 'reconcile_partial_id'], 10),                                                  
#                                                        'account.move': (_get_am_storeids, ['ref', 'name'], 10), 
#                                                        #'account.move.reconcile': (_get_rec_storeids, ['name', 'type'], 10), 
#                                                        },                                     
#                                               ),
    }
    
res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
