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
import sugar
from tools.translate import _
from import_base.import_framework import *
from import_base.mapper import *
from datetime import datetime
import base64
import pprint
pp = pprint.PrettyPrinter(indent=4)

#copy old import here
class related_ref(dbmapper):
    def __init__(self, type):
        self.type = type
        
    def __call__(self, external_val):
        if external_val.get('parent_type') in self.type and external_val.get('parent_id'):
            return self.parent.xml_id_exist(external_val['parent_type'], external_val['parent_id'])
        return ''

class sugar_import(import_framework):
    TABLE_CONTACT = 'Contacts'
    TABLE_ACCOUNT = 'Accounts'
    TABLE_USER = 'Users'
    TABLE_EMPLOYEE = 'Employees'
    TABLE_RESSOURCE = "resource"
    TABLE_OPPORTUNITY = 'Opportunities'
    TABLE_LEAD = 'Leads'
    TABLE_STAGE = 'crm_stage'
    TABLE_ATTENDEE = 'calendar_attendee'
    TABLE_CALL = 'Calls'
    TABLE_MEETING = 'Meetings'
    TABLE_TASK = 'Tasks'
    TABLE_PROJECT = 'Project'
    TABLE_PROJECT_TASK = 'ProjectTask'
    TABLE_BUG = 'Bugs'
    TABLE_CASE = 'Cases'
    TABLE_NOTE = 'Notes'
    TABLE_EMAIL = 'Emails'
    TABLE_DOCUMENT = 'DocumentRevisions'
    TABLE_COMPAIGN = 'Campaigns'
    TABLE_HISTORY_ATTACHMNET = 'history_attachment'
    
    def initialize(self):
        #login
        PortType,sessionid = sugar.login(self.context.get('username',''), self.context.get('password',''), self.context.get('url',''))
        if sessionid == '-1':
            raise osv.except_osv(_('Error !'), _('Authentication error !\nBad Username or Password !'))
        self.context['port'] = PortType
        self.context['session_id'] = sessionid
        
    def get_data(self, table):
        
        return sugar.search(self.context.get('port'), self.context.get('session_id'), table)
    """
    Common import method
    """

    def get_category(self, val, model, name):
        fields = ['name', 'object_id']
        data = [name, model]
        return self.import_object(fields, data, 'crm.case.categ', 'crm_categ', name, [('object_id.model','=',model), ('name', 'ilike', name)])

    def get_job_title(self, dict, salutation):
        fields = ['shortcut', 'name', 'domain']
        if salutation:
            data = [salutation, salutation, 'Contact']
            return self.import_object(fields, data, 'res.partner.title', 'contact_title', salutation, [('shortcut', '=', salutation)])

    def get_channel_id(self, dict, val):
        fields = ['name']
        data = [val]
        return self.import_object(fields, data, 'res.partner.canal', 'crm_channel', val)
    
    def get_all_states(self, external_val, country_id):
        """Get states or create new state unless country_id is False"""
        state_code = external_val[0:3] #take the tree first char
        fields = ['country_id/id', 'name', 'code']
        data = [country_id, external_val, state_code]
        if country_id:
            return self.import_object(fields, data, 'res.country.state', 'country_state', external_val) 
        return False

    def get_all_countries(self, val):
        """Get Country, if no country match do not create anything, to avoid duplicate country code"""
        return self.mapped_id_if_exist('res.country', [('name', 'ilike', val)], 'country', val)
    
    def get_float_time(self, dict, hour, min):
        min = int(min) * 100 / 60
        return "%s.%i" % (hour, min)
    
    def get_attachment(self, val):
        File, Filename = sugar.attachment_search(self.context.get('port'), self.context.get('session_id'), self.TABLE_NOTE, val.get('id')) 
        attach_xml_id = False
        attachment_obj = self.obj.pool.get('ir.attachment')
        model_obj = self.obj.pool.get('ir.model.data')
        mailgate_obj = self.obj.pool.get('mailgate.message')
        if File:
            fields = ['name', 'datas', 'datas_fname','res_id', 'res_model']
            name = 'attachment_'+ (Filename or val.get('name'))
            datas = [Filename or val.get('name'), File, Filename, val.get('res_id'),val.get('model',False)]
            attach_xml_id = self.import_object(fields, datas, 'ir.attachment', self.TABLE_HISTORY_ATTACHMNET, name, [('res_id', '=', val.get('res_id'), ('model', '=', val.get('model')))])
        return attach_xml_id    
    
    """
    import Documents
    """
    #THIS IS A JOKE ? NOT FUNNY
    def import_document(self, val):
        filepath = '/home/openerp/Public/sugarcrm/cache/upload/'+ val.get('id')
        f = open(filepath, "r")
        datas = f.read()
        f.close()
        val['datas'] = base64.encodestring(datas)
        val['datas_fname'] = val.get('filename')
        return val   
        
    def get_document_mapping(self): 
        return { 
                'model' : 'ir.attachment',
                'dependencies' : [self.TABLE_USER],
                'hook' : self.import_document,
                'map' : {'name':'filename',
                         'description': ppconcat('description'),
                         'datas': 'datas',
                         'datas_fname': 'datas_fname',
                }
            }     
    
    """
    import Emails
    """
    
    def import_email(self, val):
        print 'import email'
        model_obj =  self.obj.pool.get('ir.model.data')
        xml_id = self.xml_id_exist(val.get('parent_type'), val.get('parent_id'))
        model_ids = model_obj.search(self.cr, self.uid, [('name', 'like', xml_id)])
        if model_ids:
            print 'model_id', xml_id, model_ids
            model = model_obj.browse(self.cr, self.uid, model_ids)[0]
            if model.model == 'res.partner':
                val['partner_id/.id'] = model.res_id
            else:    
                val['res_id'] = model.res_id
                val['model'] = model.model
        return val   
        
    def get_email_mapping(self): 
        return { 
                'model' : 'mailgate.message',
                'dependencies' : [self.TABLE_USER, self.TABLE_PROJECT, self.TABLE_PROJECT_TASK, self.TABLE_ACCOUNT, self.TABLE_CONTACT, self.TABLE_LEAD, self.TABLE_OPPORTUNITY, self.TABLE_MEETING, self.TABLE_CALL],
                'hook' : self.import_email,
                'map' : {'name':'name',
                        'date':'date_sent',
                        'email_from': 'from_addr_name',
                        'email_to': 'reply_to_addr',
                        'email_cc': 'cc_addrs_names',
                        'email_bcc': 'bcc_addrs_names',
                        'message_id': 'message_id',
                        'res_id': 'res_id',
                        'model': 'model',
                        'partner_id/.id': 'partner_id/.id',                         
                        'attachment_ids/id': self.get_attachment,
                        'user_id/id': ref(self.TABLE_USER, 'assigned_user_id'),
                        'description': ppconcat('description', 'description_html'),
                }
            } 
    
    """
    import History(Notes)
    """

    def import_history(self, val):
        model_obj =  self.obj.pool.get('ir.model.data')
        xml_id = self.xml_id_exist(val.get('parent_type'), val.get('parent_id'))
        model_ids = model_obj.search(self.cr, self.uid, [('name', 'like', xml_id)])
        if model_ids:
              model = model_obj.browse(self.cr, self.uid, model_ids)[0]
              if model.model == 'res.partner':
                    val['partner_id/.id'] = model.res_id
              else:    
                    val['res_id'] = model.res_id
                    val['model'] = model.model
        return val    
    
    def get_history_mapping(self): 
        return { 
                'model' : 'mailgate.message',
                'dependencies' : [self.TABLE_USER, self.TABLE_PROJECT, self.TABLE_PROJECT_TASK, self.TABLE_ACCOUNT, self.TABLE_CONTACT, self.TABLE_LEAD, self.TABLE_OPPORTUNITY, self.TABLE_MEETING, self.TABLE_CALL],
                'hook' : self.import_history,
                'map' : {
                      'name':'name',
                      'date': 'date_entered',
                      'user_id/id': ref(self.TABLE_USER, 'assigned_user_id'),
                      'description': ppconcat('description', 'description_html'),
                      'res_id': 'res_id',
                      'model': 'model',
                      'attachment_ids/id': self.get_attachment,
                      'partner_id/.id' : 'partner_id/.id',
                }
            }     
    
    """
    import Claims(Cases)
    """
    def get_claim_priority(self, val):
        priority_dict = {            
                'High': '2',
                'Medium': '3',
                'Low': '4'
        }
        return priority_dict.get(val.get('priority'), '')
        
    def get_contact_info_from_account(self, val):
        partner_id = self.get_mapped_id(self.TABLE_ACCOUNT, val.get('account_id'))
        partner_address_id = False
        partner_phone = False
        partner_email = False
        partner = self.obj.pool.get('res.partner').browse(self.cr, self.uid, [partner_id])[0]
        if partner.address and partner.address[0]:
            address = partner.address[0]
            partner_address_id = address.id
            partner_phone = address.phone
            partner_email = address.email
        return partner_address_id, partner_phone,partner_email
    
    def import_crm_claim(self, val):
        partner_address_id, partner_phone,partner_email =  self.get_contact_info_from_account(val)
        val['partner_address_id/.id'] = partner_address_id
        val['partner_address_id/.id'] = partner_address_id
        val['partner_phone'] = partner_phone
        val['email_from'] = partner_email
        return val
    
    def get_crm_claim_mapping(self): 
        return { 
                'model' : 'crm.claim',
                'dependencies' : [self.TABLE_USER, self.TABLE_ACCOUNT, self.TABLE_CONTACT, self.TABLE_LEAD],
                'hook' : self.import_crm_claim,
                'map' : {
                    'name': 'name',
                    'date': 'date_entered',
                    'user_id/id': ref(self.TABLE_USER, 'assigned_user_id'),
                    'description': ppconcat('description'),
                    'partner_id/id': ref(self.TABLE_ACCOUNT, 'account_id'),
                    'partner_address_id/.id': 'partner_address_id/.id',
                    'partner_phone': 'partner_phone',
                    'email_from': 'email_from',                                        
                    'priority': self.get_claim_priority,
                    'state': map_val('status', self.project_issue_state)
                }
            }    
    """
    Import Project Issue(Bugs)
    """
    project_issue_state = {
            'New' : 'draft',
            'Assigned':'open',
            'Closed': 'done',
            'Pending': 'pending',
            'Rejected': 'cancel',
    }
     
    def get_project_issue_priority(self, val):
        priority_dict = {
                'Urgent': '1',
                'High': '2',
                'Medium': '3',
                'Low': '4'
         }
        return priority_dict.get(val.get('priority'), '')     
      
    def get_bug_project_id(self, dict, val):
        fields = ['name']
        data = [val]
        return self.import_object(fields, data, 'project.project', 'project_issue', val)    
    
    def get_project_issue_mapping(self):
        return { 
                'model' : 'project.issue',
                'dependencies' : [self.TABLE_USER, self.TABLE_PROJECT, self.TABLE_PROJECT_TASK],
                'map' : {
                    'name': 'name',
                    'project_id/id': call(self.get_bug_project_id, 'sugarcrm_bugs'),
                    'categ_id/id': call(self.get_category, 'project.issue', value('type')),
                    'description': ppconcat('description', 'bug_number', 'fixed_in_release_name', 'source', 'fixed_in_release', 'work_log', 'found_in_release', 'release_name', 'resolution'),
                    'priority': self.get_project_issue_priority,
                    'state': map_val('status', self.project_issue_state)
                }
            }
    
    """
    import Project Tasks
    """
    project_task_state = {
            'Not Started': 'draft',
            'In Progress': 'open',
            'Completed': 'done',
            'Pending Input': 'pending',
            'Deferred': 'cancelled',
     }
    
    def get_project_task_priority(self, val):
      priority_dict = {
            'High': '0',
            'Medium': '2',
            'Low': '3'
        }
      return priority_dict.get(val.get('priority'), '')
    
    def get_project_task_mapping(self):
        return { 
                'model' : 'project.task',
                'dependencies' : [self.TABLE_USER, self.TABLE_PROJECT],
                'map' : {
                    'name': 'name',
                    'date_start': 'date_start',
                    'date_end': 'date_finish',
                    'progress': 'progress',
                    'project_id/id': ref(self.TABLE_PROJECT, 'project_id'),
                    'planned_hours': 'planned_hours',
                    'total_hours': 'total_hours',        
                    'priority': self.get_project_task_priority,
                    'description': ppconcat('description','milestone_flag', 'project_task_id', 'task_number'),
                    'user_id/id': ref(self.TABLE_USER, 'assigned_user_id'),
                    'partner_id/id': 'partner_id/id',
                    'contact_id/id': 'contact_id/id',
                    'state': map_val('status', self.project_task_state)
                }
            }

    """
    import Projects
    """
    project_state = {
            'Draft' : 'draft',
            'In Review': 'open',
            'Published': 'close'
     }
    def import_project_account(self, val):
        partner_id = False
        partner_invoice_id = False        
        sugar_project_account = sugar.relation_search(self.context.get('port'), self.context.get('session_id'), 'Project', module_id=val.get('id'), related_module=self.TABLE_ACCOUNT, query=None, deleted=None)
        sugar_project_contact = sugar.relation_search(self.context.get('port'), self.context.get('session_id'), 'Project', module_id=val.get('id'), related_module=self.TABLE_CONTACT, query=None, deleted=None)
        for contact_id in sugar_project_contact:
            partner_invoice_id = self.get_mapped_id(self.TABLE_CONTACT, contact_id)
        for account_id in sugar_project_account:
            partner_id = self.get_mapped_id(self.TABLE_ACCOUNT, account_id)
        return partner_id, partner_invoice_id      
           
    def import_project(self, val):
        partner_id, partner_invoice_id  = self.import_project_account(val)    
        val['partner_id/.id'] = partner_id
        val['contact_id/.id'] = partner_invoice_id
        return val
    
    def get_project_mapping(self):
        return { 
                'model' : 'project.project',
                'dependencies' : [self.TABLE_CONTACT, self.TABLE_ACCOUNT, self.TABLE_USER],
                'hook' : self.import_project,
                'map' : {
                    'name': 'name',
                    'date_start': 'estimated_start_date',
                    'date': 'estimated_end_date',
                    'user_id/id': ref(self.TABLE_USER, 'assigned_user_id'),
                    'partner_id/.id': 'partner_id/.id',
                    'contact_id/.id': 'contact_id/.id',
                    'state': map_val('status', self.project_state)
                }
            }
    
    """
    import Tasks
    """
    task_state = {
            'Completed' : 'done',
            'Not Started':'draft',
            'In Progress': 'open',
            'Pending Input': 'draft',
            'deferred': 'cancel'
        }

    def import_task(self, val):
        val['date'] = val.get('date_start') or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        val['date_deadline'] = val.get('date_due') or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        return val

    def get_task_mapping(self):
        return { 
                'model' : 'crm.meeting',
                'dependencies' : [self.TABLE_CONTACT, self.TABLE_ACCOUNT, self.TABLE_USER],
                'hook' : self.import_task,
                'map' : {
                    'name': 'name',
                    'date': 'date',
                    'date_deadline': 'date_deadline',
                    'user_id/id': ref(self.TABLE_USER, 'assigned_user_id'),
                    'categ_id/id': call(self.get_category, 'crm.meeting', const('Tasks')),
                    'partner_id/id': related_ref(self.TABLE_ACCOUNT),
                    'partner_address_id/id': ref(self.TABLE_CONTACT,'contact_id'),
                    'state': map_val('status', self.task_state)
                }
            }
       
    """
    import Calls
    """     
    call_state = {   
            'Planned' : 'open',
            'Held':'done',
            'Not Held': 'pending',
        }

    def get_calls_mapping(self):
        return { 
                'model' : 'crm.phonecall',
                'dependencies' : [self.TABLE_ACCOUNT, self.TABLE_CONTACT, self.TABLE_OPPORTUNITY, self.TABLE_LEAD],
                'map' : {
                    'name': 'name',
                    'date': 'date_start',
                    'duration': call(self.get_float_time, value('duration_hours'), value('duration_minutes')),
                    'user_id/id':  ref(self.TABLE_USER, 'assigned_user_id'),
                    'partner_id/id': related_ref(self.TABLE_ACCOUNT),
                    'partner_address_id/id': related_ref(self.TABLE_CONTACT),
                    'categ_id/id': call(self.get_category, 'crm.phonecall', value('direction')),
                    'opportunity_id/id': related_ref(self.TABLE_OPPORTUNITY),
                    'description': ppconcat('description'),   
                    'state': map_val('status', self.call_state)                      
                }
            }        
        
    """
        import meeting
    """
    meeting_state = {
            'Planned' : 'draft',
            'Held': 'open',
            'Not Held': 'draft', 
        }
#TODO    
    def get_attendee_id(self, cr, uid, module_name, module_id):
        contact_id = False
        user_id = False
        attendee_id= []
        attendee_dict = sugar.user_get_attendee_list(self.context.get('port'), self.context.get('session_id'), module_name, module_id)
        for attendee in attendee_dict:
            user_id = self.xml_id_exist(self.TABLE_USER, attendee.get('id', False))
            if user_id:
                contact_id = False
            else:    
                contact_id = self.xml_id_exist(self.TABLE_CONTACT, attendee.get('id', False))
            fields = ['user_id/id', 'email', 'partner_address_id/id']
            data = [user_id or False, attendee.get('email1'), contact_id]
            attendee_xml_id = self.import_object(fields, data, 'calendar.attendee', self.TABLE_ATTENDEE, user_id or contact_id or attendee.get('email1'), ['|',('user_id', '=', attendee.get('id')),('partner_address_id','=',attendee.get('id')),('email', '=', attendee.get('email1'))])
            attendee_id.append(attendee_xml_id)
        return ','.join(attendee_id) 
    
    def get_alarm_id(self, dict_val, val):
        alarm_dict = {
            '60': '1 minute before',
            '300': '5 minutes before',
            '600': '10 minutes before',
            '900': '15 minutes before',
            '1800':'30 minutes before',
            '3600': '1 hour before',
        }
        return self.mapped_id_if_exist('res.alarm', [('name', 'like', alarm_dict.get(val))], 'alarm', val)
    
    #TODO attendees
    def import_meeting(self, val):
        attendee_id = self.get_attendee_id(self.cr, self.uid, 'Meetings', val.get('id')) #TODO
        val['attendee_ids/id'] = attendee_id
        return val

    def get_meeting_mapping(self):
        return { 
                'model' : 'crm.meeting',
                'dependencies' : [self.TABLE_CONTACT, self.TABLE_OPPORTUNITY, self.TABLE_LEAD],
                'hook': self.import_meeting,
                'map' : {
                    'name': 'name',
                    'date': 'date_start',
                    'duration': call(self.get_float_time, value('duration_hours'), value('duration_minutes')),
                    'location': 'location',
                    'attendee_ids/id':'attendee_ids/id',
                    'alarm_id/id': call(self.get_alarm_id, value('reminder_time')),
                    'user_id/id': ref(self.TABLE_USER, 'assigned_user_id'),
                    'partner_id/id': related_ref(self.TABLE_ACCOUNT),
                    'partner_address_id/id': related_ref(self.TABLE_CONTACT),
                    'state': map_val('status', self.meeting_state)
                }
            }
    
    """
        import Opportunity
    """
    opp_state = {
            'Need Analysis' : 'New',
            'Closed Lost': 'Lost',
            'Closed Won': 'Won', 
            'Value Proposition': 'Proposition',
            'Negotiation/Review': 'Negotiation'
        }
        
    def get_opportunity_status(self, sugar_val):
        fields = ['name', 'type']
        name = 'Opportunity_' + sugar_val['sales_stage']
        data = [sugar_val['sales_stage'], 'Opportunity']
        return self.import_object(fields, data, 'crm.case.stage', self.TABLE_STAGE, name, [('type', '=', 'opportunity'), ('name', 'ilike', sugar_val['sales_stage'])])
    
    def import_opportunity_contact(self, val):
        sugar_opportunities_contact = set(sugar.relation_search(self.context.get('port'), self.context.get('session_id'), 'Opportunities', module_id=val.get('id'), related_module='Contacts', query=None, deleted=None))
            
        partner_contact_id = False 
        partner_contact_email = False       
        partner_address_obj = self.obj.pool.get('res.partner.address')
        partner_xml_id = self.name_exist(self.TABLE_ACCOUNT, val['account_name'], 'res.partner')
        
        for contact in sugar_opportunities_contact:
            address_id = self.get_mapped_id(self.TABLE_CONTACT, contact)
            if address_id:                    
                address = partner_address_obj.browse(self.cr, self.uid, address_id)
                partner_name = address.partner_id and address.partner_id.name or False
                if not partner_name: #link with partner id 
                    fields = ['partner_id/id']
                    data = [partner_xml_id]
                    self.import_object(fields, data, 'res.partner.address', self.TABLE_CONTACT, contact, self.DO_NOT_FIND_DOMAIN)
                if not partner_name or partner_name == val.get('account_name'):
                    partner_contact_id = self.xml_id_exist(self.TABLE_CONTACT, contact)
                    partner_contact_email = address.email
        return partner_contact_id, partner_contact_email

    def import_opp(self, val):    
        partner_contact_name, partner_contact_email = self.import_opportunity_contact(val)
        val['partner_address_id/id'] = partner_contact_name
        val['email_from'] = partner_contact_email
        return val
    
    def get_opp_mapping(self):
        return {
            'model' : 'crm.lead',
            'dependencies' : [self.TABLE_USER, self.TABLE_ACCOUNT, self.TABLE_CONTACT,self.TABLE_COMPAIGN],
            'hook' : self.import_opp,
            'map' :  {
                'name': 'name',
                'probability': 'probability',
                'partner_id/id': refbyname(self.TABLE_ACCOUNT, 'account_name', 'res.partner'),
                'title_action': 'next_step',
                'partner_address_id/id': 'partner_address_id/id',
                'planned_revenue': 'amount',
                'date_deadline': 'date_closed',
                'user_id/id' : ref(self.TABLE_USER, 'assigned_user_id'),
                'stage_id/id' : self.get_opportunity_status,
                'type' : const('opportunity'),
                'categ_id/id': call(self.get_category, 'crm.lead', value('opportunity_type')),
                'email_from': 'email_from',
                'state': map_val('status', self.opp_state)  , #TODO
            }
        }
        
    """
    import campaign
    """
    
    def get_compaign_mapping(self):
        return {
            'model' : 'crm.case.resource.type',
            'map' : {
                'name': 'name',
                } 
        }    
        
    """
        import lead
    """
    def get_lead_status(self, sugar_val):
        fields = ['name', 'type']
        name = 'lead_' + sugar_val.get('status', '')
        data = [sugar_val.get('status', ''), 'lead']
        return self.import_object(fields, data, 'crm.case.stage', self.TABLE_STAGE, name, [('type', '=', 'lead'), ('name', 'ilike', sugar_val.get('status', ''))])

    lead_state = {
        'New' : 'draft',
        'Assigned':'open',
        'In Progress': 'open',
        'Recycled': 'cancel',
        'Dead': 'done',
        'Converted': 'done',
    }

    
    def import_lead(self, val):
        if val.get('opportunity_id'): #if lead is converted into opp, don't import as lead
            return False
        if val.get('primary_address_country'):
            country_id = self.get_all_countries(val.get('primary_address_country'))
            val['country_id/id'] =  country_id
            val['state_id/id'] =  self.get_all_states(val.get('primary_address_state'), country_id)
        return val
    
    def get_lead_mapping(self):
        return {
            'model' : 'crm.lead',
            'dependencies' : [self.TABLE_COMPAIGN],
            'hook' : self.import_lead,
            'map' : {
                'name': concat('first_name', 'last_name'),
                'contact_name': concat('first_name', 'last_name'),
                'description': ppconcat('description', 'refered_by', 'lead_source', 'lead_source_description', 'website', 'email2', 'status_description', 'lead_source_description', 'do_not_call'),
                'partner_name': 'account_name',
                'email_from': 'email1',
                'phone': 'phone_work',
                'mobile': 'phone_mobile',
                'title/id': call(self.get_job_title, value('salutation')),
                'function':'title',
                'street': 'primary_address_street',
                'street2': 'alt_address_street',
                'zip': 'primary_address_postalcode',
                'city':'primary_address_city',
                'user_id/id' : ref(self.TABLE_USER, 'assigned_user_id'),
                'stage_id/id' : self.get_lead_status,
                'type' : const('lead'),
                'state': map_val('status', self.lead_state) ,
                'fax': 'phone_fax',
                'referred': 'refered_by',
                'optout': 'do_not_call',
                'channel_id/id': call(self.get_channel_id, value('lead_source')),
                'type_id/id': ref(self.TABLE_COMPAIGN, 'campaign_id'),
                'country_id/id': 'country_id/id',
                'state_id/id': 'state_id/id'
                } 
        }
    
    """
        import contact
    """
    def get_email(self, val):
        email_address = sugar.get_contact_by_email(self.context.get('port'), self.context.get('username'), self.context.get('password'), val.get('email1'))
        if email_address:
            return ','.join(email_address) 
    
    def import_contact(self, val):
        if val.get('primary_address_country'):
            country_id = self.get_all_countries(val.get('primary_address_country'))
            state = self.get_all_states(val.get('primary_address_state'), country_id)
            val['country_id/id'] =  country_id
            val['state_id/id'] =  state
        return val    
        
    def get_contact_mapping(self):
        return { 
            'model' : 'res.partner.address',
            'dependencies' : [self.TABLE_ACCOUNT],
            'hook' : self.import_contact,
            'map' :  {
                'name': concat('first_name', 'last_name'),
                'partner_id/id': ref(self.TABLE_ACCOUNT,'account_id'),
                'phone': 'phone_work',
                'mobile': 'phone_mobile',
                'fax': 'phone_fax',
                'function': 'title',
                'street': 'primary_address_street',
                'zip': 'primary_address_postalcode',
                'city': 'primary_address_city',
                'country_id/id': 'country_id/id',
                'state_id/id': 'state_id/id',
                'email': self.get_email,
                'type': const('contact')
            }
        }
    
    """ 
        import Account
    """
    def get_address_type(self, val, type):
        if type == 'invoice':
            type_address = 'billing'
        else:
            type_address = 'shipping'     
    
        map_partner_address = {
            'name': 'name',
            'phone': 'phone_office',
            'mobile': 'phone_mobile',
            'fax': 'phone_fax',
            'type': 'type',
            'street': type_address + '_address_street',
            'zip': type_address +'_address_postalcode',
            'city': type_address +'_address_city',
             'country_id/id': 'country_id/id',
             'type': 'type',
            }
        
        if val.get(type_address +'_address_country'):
            country_id = self.get_all_countries(val.get(type_address +'_address_country'))
            state = self.get_all_states(val.get(type_address +'_address_state'), country_id)
            val['country_id/id'] =  country_id
            val['state_id/id'] =  state
        val['type'] = type
        val['id_new'] = val['id'] + '_address_' + type
        return self.import_object_mapping(map_partner_address, val, 'res.partner.address', self.TABLE_CONTACT, val['id_new'], self.DO_NOT_FIND_DOMAIN) 
    
    def get_partner_address(self, val):
        address_id=[]
        type_dict = {'billing_address_street' : 'invoice', 'shipping_address_street' : 'delivery'}
        for key, type_value in type_dict.items():
            if val.get(key):
                id = self.get_address_type(val, type_value)
                address_id.append(id)
          
        return ','.join(address_id)
    
    def get_partner_mapping(self):
        return {
                'model' : 'res.partner',
                'dependencies' : [self.TABLE_USER],
                'map' : {
                    'name': 'name',
                    'website': 'website',
                    'user_id/id': ref(self.TABLE_USER,'assigned_user_id'),
                    'ref': 'sic_code',
                    'comment': ppconcat('description', 'employees', 'ownership', 'annual_revenue', 'rating', 'industry', 'ticker_symbol'),
                    'customer': const('1'),
                    'supplier': const('0'),
                    'address/id':'address/id', 
                    'parent_id/id_parent' : 'parent_id',
                    'address/id' : self.get_partner_address,
                }
        }

    """
        import Employee
    """
    def get_ressource(self, val):
        map_resource = { 
            'name': concat('first_name', 'last_name'),
        }        
        return self.import_object_mapping(map_resource, val, 'resource.resource', self.TABLE_RESSOURCE, val['id'], self.DO_NOT_FIND_DOMAIN)
    
    def get_job_id(self, val):
        fields = ['name']
        data = [val.get('title')]
        return self.import_object(fields, data, 'hr.job', 'hr_job', val.get('title'))

    def get_user_address(self, val):
        map_user_address = {
            'name': concat('first_name', 'last_name'),
            'city': 'address_city',
            'country_id/id': 'country_id/id',
            'state_id/id': 'state_id/id',
            'street': 'address_street',
            'zip': 'address_postalcode',
            'fax': 'fax',
            'phone': 'phone_work',
            'mobile':'phone_mobile',
            'email': 'email1'
        }
        
        if val.get('address_country'):
            country_id = self.get_all_countries(val.get('address_country'))
            state_id = self.get_all_states(val.get('address_state'), country_id)
            val['country_id/id'] =  country_id
            val['state_id/id'] =  state_id
            
        return self.import_object_mapping(map_user_address, val, 'res.partner.address', self.TABLE_CONTACT, val['id'], self.DO_NOT_FIND_DOMAIN)

    def get_employee_mapping(self):
        return {
            'model' : 'hr.employee',
            'dependencies' : [self.TABLE_USER],
            'map' : {
                'resource_id/id': self.get_ressource, 
                'name': concat('first_name', 'last_name'),
                'work_phone': 'phone_work',
                'mobile_phone':  'phone_mobile',
                'user_id/id': ref(self.TABLE_USER, 'id'), 
                'address_home_id/id': self.get_user_address,
                'notes': ppconcat('messenger_type', 'messenger_id', 'description'),
                'job_id/id': self.get_job_id,
            }
     }
    
    """
        import user
    """  
    def import_user(self, val):
        user_obj = self.obj.pool.get('res.users')
        user_ids = user_obj.search(self.cr, self.uid, [('login', '=', val.get('user_name'))])
        if user_ids: 
            val['.id'] = str(user_ids[0])
        else:
            val['password'] = 'sugarcrm' #default password for all user #TODO needed in documentation
            
        val['context_lang'] = self.context.get('lang','en_US')
        return val
    
    def get_users_department(self, val):
        dep = val.get('department')
        fields = ['name']
        data = [dep]
        if not dep:
            return False
        return self.import_object(fields, data, 'hr.department', 'hr_department_user', dep)

    def get_user_mapping(self):
        return {
            'model' : 'res.users',
            'hook' : self.import_user,
            'map' : { 
                'name': concat('first_name', 'last_name'),
                'login': 'user_name',
                'context_lang' : 'context_lang',
                'password' : 'password',
                '.id' : '.id',
                'context_department_id/id': self.get_users_department,
            }
        }

    def get_mapping(self):
        return {
            self.TABLE_USER : self.get_user_mapping(),
            self.TABLE_EMPLOYEE : self.get_employee_mapping(),
            self.TABLE_ACCOUNT : self.get_partner_mapping(),
            self.TABLE_CONTACT : self.get_contact_mapping(),
            self.TABLE_LEAD : self.get_lead_mapping(),
            self.TABLE_OPPORTUNITY : self.get_opp_mapping(),
            self.TABLE_MEETING : self.get_meeting_mapping(),
            self.TABLE_CALL : self.get_calls_mapping(),
            self.TABLE_TASK : self.get_task_mapping(),
            self.TABLE_PROJECT : self.get_project_mapping(),
            self.TABLE_PROJECT_TASK: self.get_project_task_mapping(),
            self.TABLE_BUG: self.get_project_issue_mapping(),
            self.TABLE_CASE: self.get_crm_claim_mapping(),
            self.TABLE_NOTE: self.get_history_mapping(),
            self.TABLE_EMAIL: self.get_email_mapping(),
            self.TABLE_DOCUMENT: self.get_document_mapping(),
            self.TABLE_COMPAIGN: self.get_compaign_mapping()
            
        }
    def get_email_subject(self, result):
        return "your sugarcrm data were successfully imported at %s" % self.date_ended 
    
    def get_body_header(self, result):
        return "Sugarcrm import : report of last import" 


class import_sugarcrm(osv.osv):
    """Import SugarCRM DATA"""
    
    _name = "import.sugarcrm"
    _description = __doc__
    _columns = {
               
        'username': fields.char('User Name', size=64, required=True),
        'password': fields.char('Password', size=24,required=True),
         'url' : fields.char('Service', size=264, required=True, help="Connection with Sugarcrm Using Soap Protocol Services and For that Path should be 'http://localhost/sugarcrm/soap.php' Format."),
                
        'opportunity': fields.boolean('Leads and Opportunities', help="If Opportunities are checked, SugarCRM opportunities data imported in OpenERP crm-Opportunity form"),
        'user': fields.boolean('Users', help="If Users  are checked, SugarCRM Users data imported in OpenERP Users form"),
        'contact': fields.boolean('Contacts', help="If Contacts are checked, SugarCRM Contacts data imported in OpenERP partner address form"),
        'account': fields.boolean('Accounts', help="If Accounts are checked, SugarCRM  Accounts data imported in OpenERP partners form"),
        'employee': fields.boolean('Employee', help="If Employees is checked, SugarCRM Employees data imported in OpenERP employees form"),
        'meeting': fields.boolean('Meetings', help="If Meetings is checked, SugarCRM Meetings data imported in OpenERP meetings form"),
        'call': fields.boolean('Calls', help="If Calls is checked, SugarCRM Calls data imported in OpenERP phonecalls form"),
        'claim': fields.boolean('Claims', help="If Claims is checked, SugarCRM Claims data imported in OpenERP Claims form"),
        'email': fields.boolean('Emails', help="If Emails is checked, SugarCRM Emails data imported in OpenERP Emails form"),
        'project': fields.boolean('Projects', help="If Projects is checked, SugarCRM Projects data imported in OpenERP Projects form"),
        'project_task': fields.boolean('Project Tasks', help="If Project Tasks is checked, SugarCRM Project Tasks data imported in OpenERP Project Tasks form"),
        'task': fields.boolean('Tasks', help="If Tasks is checked, SugarCRM Tasks data imported in OpenERP Meetings form"),
        'bug': fields.boolean('Bugs', help="If Bugs is checked, SugarCRM Bugs data imported in OpenERP Project Issues form"),
        'attachment': fields.boolean('Attachments', help="If Attachments is checked, SugarCRM Notes data imported in OpenERP's Related module's History with attachment"),
        'document': fields.boolean('Documents', help="If Documents is checked, SugarCRM Documents data imported in OpenERP Document Form"),
        'email_from': fields.char('Notify End Of Import To:', size=128),
        'instance_name': fields.char("Instance's Name", size=64, help="Prefix of SugarCRM id to differentiate xml_id of SugarCRM models datas come from different server."),
        
    }
    _defaults = {#to be set to true, but easier for debugging
       'opportunity': False,
       'user' : False,
       'contact' : False,
       'account' : False,
        'employee' : False,
        'meeting' : False,
        'task' : False,
        'call' : False,
        'claim' : False,    
        'email' : False, 
        'project' : False,   
        'project_task': False,     
        'bug': False,
        'document': False,
        'instance_name': 'sugarcrm',
        'email_from': 'tfr@openerp.com',
        'username' : 'tfr',
        'password' : 'a',
        'url':  "http://localhost/sugarcrm/soap.php"        
    }
    
    def get_key(self, cr, uid, ids, context=None):
        """Select Key as For which Module data we want import data."""
        if not context:
            context = {}
        key_list = []
        for current in self.browse(cr, uid, ids, context):
            context.update({'username': current.username, 'password': current.password, 'url': current.url, 'email_user': current.email_from or False, 'instance_name': current.instance_name or False})
            if current.opportunity:
                key_list.append('Leads')
                key_list.append('Opportunities')
            if current.user:
                key_list.append('Users')
            if current.contact:
                key_list.append('Contacts')
            if current.account:
                key_list.append('Accounts') 
            if current.employee:
                key_list.append('Employees')  
            if current.meeting:
                key_list.append('Meetings')
            if current.task:
                key_list.append('Tasks')
            if current.call:
                key_list.append('Calls')
            if current.claim:
                key_list.append('Cases')                
            if current.email:
                key_list.append('Emails') 
            if current.project:
                key_list.append('Project')
            if current.project_task:
                key_list.append('ProjectTask')
            if current.bug:
                key_list.append('Bugs')
            if current.attachment:
                key_list.append('Notes')     
            if current.document:
                key_list.append('DocumentRevisions')                                                  
        return key_list


    def do_import_all(self, cr, uid, *args):
        """
        scheduler Method
        """
        print 'args of schedule method', args
        context = {'username': args[4], 'password': args[5], 'url': args[3], 'instance_name': args[3]}
        print context
        imp = sugar_import(self, cr, uid, args[2], "import_sugarcrm", [args[1]], context)
        imp.set_table_list(args[0])
        imp.start()
        return True 

    def import_from_scheduler_all(self, cr, uid, ids, context=None):
        keys = self.get_key(cr, uid, ids, context)
        if not keys:
            raise osv.except_osv(_('Warning !'), _('Select Module to Import.'))
        cron_obj = self.pool.get('ir.cron')
        args = (keys,context.get('email_user'), context.get('instance_name'), context.get('url'), context.get('username'), context.get('password') )
        new_create_id = cron_obj.create(cr, uid, {'name': 'Import SugarCRM datas','interval_type': 'hours','interval_number': 1, 'numbercall': -1,'model': 'import.sugarcrm','function': 'do_import_all', 'args': args, 'active': False})
        return {
            'name': 'SugarCRM Scheduler',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'ir.cron',
            'res_id': new_create_id,
            'type': 'ir.actions.act_window',
        }

    def import_all(self, cr, uid, ids, context=None):
        
#        """Import all sugarcrm data into openerp module"""
        keys = self.get_key(cr, uid, ids, context)
        imp = sugar_import(self, cr, uid, context.get('instance_name'), "import_sugarcrm", [context.get('email_user')], context)
        imp.set_table_list(keys)
        imp.start()
        
        obj_model = self.pool.get('ir.model.data')
        model_data_ids = obj_model.search(cr,uid,[('model','=','ir.ui.view'),('name','=','import.message.form')])
        resource_id = obj_model.read(cr, uid, model_data_ids, fields=['res_id'])
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'import.message',
                'views': [(resource_id,'form')],
                'type': 'ir.actions.act_window',
                'target': 'new',
            }
        
import_sugarcrm()
