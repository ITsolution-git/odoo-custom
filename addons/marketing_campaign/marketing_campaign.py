# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 OpenERP SA (<http://openerp.com>).
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
import base64
from datetime import datetime
from dateutil.relativedelta import relativedelta

from osv import fields, osv
import netsvc
import tools

_intervalTypes = {
    'hours': lambda interval: relativedelta(hours=interval),
    'days': lambda interval: relativedelta(days=interval),
    'months': lambda interval: relativedelta(months=interval),
    'years': lambda interval: relativedelta(years=interval),
}

class marketing_campaign(osv.osv):
    _name = "marketing.campaign"
    _description = "Marketing Campaign"

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'object_id': fields.many2one('ir.model', 'Object', required=True,
                                      help="Choose the Object on which you want \
this campaign to be run"),
        'mode':fields.selection([('test', 'Test Directly'),
                                ('test_realtime', 'Test in Realtime'),
                                ('manual', 'With Manual Confirmation'),
                                ('active', 'Normal')],
                                 'Mode', required=True, help= \
"""Test - It creates and process all the workitems directly (without waiting for the delay on transitions) but do not send emails or produce reports.
Test in Realtime - It creates and process all the workitems directly but do not send emails or produce reports.
With Manual Confirmation - the campaigns runs normally, but the user has to validate all workitem manually.
Normal - the campaign runs normally and automatically sends all emails and reports"""),
        'state': fields.selection([('draft', 'Draft'),
                                   ('running', 'Running'),
                                   ('done', 'Done'),
                                   ('cancelled', 'Cancelled'),],
                                   'State',),
        'activity_ids': fields.one2many('marketing.campaign.activity',
                                       'campaign_id', 'Activities'),
        'fixed_cost': fields.float('Fixed Cost', help="The fixed cost is cost\
you required for the campaign"),
    }
    _defaults = {
        'state': lambda *a: 'draft',
        'mode': lambda *a: 'test',
    }

    def state_running_set(self, cr, uid, ids, *args):
        campaign = self.browse(cr, uid, ids[0])
        if not campaign.activity_ids :
            raise osv.except_osv("Error", "There is no activitity in the campaign")
        act_ids = [ act_id.id for act_id in campaign.activity_ids]
        act_ids  = self.pool.get('marketing.campaign.activity').search(cr, uid,
                                [('id', 'in', act_ids), ('start', '=', True)])
        if not act_ids :
            raise osv.except_osv("Error", "There is no starting activitity in the campaign")
        self.write(cr, uid, ids, {'state': 'running'})
        return True

    def state_done_set(self, cr, uid, ids, *args):
        segment_ids = self.pool.get('marketing.campaign.segment').search(cr, uid,
                                            [('campaign_id', 'in', ids),
                                            ('state', '=', 'running')])
        if segment_ids :
            raise osv.except_osv("Error", "Campaign cannot be marked as done before all segments are done")
        self.write(cr, uid, ids, {'state': 'done'})
        return True

    def state_cancel_set(self, cr, uid, ids, *args):
        self.write(cr, uid, ids, {'state': 'cancelled'})
        return True
marketing_campaign()

class marketing_campaign_segment(osv.osv):
    _name = "marketing.campaign.segment"
    _description = "Campaign Segment"

    _columns = {
        'name': fields.char('Name', size=64,required=True),
        'campaign_id': fields.many2one('marketing.campaign', 'Campaign',
                                                required=True),
        'object_id': fields.related('campaign_id','object_id',
                                      type='many2one', relation='ir.model',
                                      string='Object'),
        'ir_filter_id': fields.many2one('ir.filters', 'Filter', help=""),
        'sync_last_date': fields.datetime('Date'),
        'sync_mode': fields.selection([('create_date', 'Create'),
                                      ('write_date', 'Write')],
                                      'Mode'),
        'state': fields.selection([('draft', 'Draft'),
                                   ('running', 'Running'),
                                   ('done', 'Done'),
                                   ('cancelled', 'Cancelled')],
                                   'State',),
        'date_run': fields.datetime('Running'),
        'date_done': fields.datetime('Done'),
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'sync_mode': lambda *a: 'create_date',
    }

    def state_running_set(self, cr, uid, ids, *args):
        segment = self.browse(cr, uid, ids[0])
        curr_date = time.strftime('%Y-%m-%d %H:%M:%S')
        vals = {'state': 'running'}
        if not segment.date_run:
            vals['date_run'] = time.strftime('%Y-%m-%d %H:%M:%S')
        self.write(cr, uid, ids, vals)
        return True

    def state_done_set(self, cr, uid, ids, *args):
        wi_ids = self.pool.get("marketing.campaign.workitem").search(cr, uid,
                                [('state', '=', 'todo'), ('segment_id', 'in', ids)])
        self.pool.get("marketing.campaign.workitem").write(cr, uid, wi_ids, {'state':'cancelled'})
        self.write(cr, uid, ids, {'state': 'done','date_done': time.strftime('%Y-%m-%d %H:%M:%S')})
        return True

    def state_cancel_set(self, cr, uid, ids, *args):
        wi_ids = self.pool.get("marketing.campaign.workitem").search(cr, uid,
                                [('state', '=', 'todo'), ('segment_id', 'in', ids)])
        self.pool.get("marketing.campaign.workitem").write(cr, uid, wi_ids, {'state':'cancelled'})
        self.write(cr, uid, ids, {'state': 'cancelled','date_done': time.strftime('%Y-%m-%d %H:%M:%S')})
        return True

    def synchroniz(self, cr, uid, ids, *args):
        self.process_segment(cr, uid, ids)
        return True
    
    def process_segment(self, cr, uid, segment_ids=None, context={}):
        if not segment_ids:
            segment_ids = self.search(cr, uid, [('state', '=', 'running')], context=context)

        action_date = time.strftime('%Y-%m-%d %H:%M:%S')
        for segment in self.browse(cr, uid, segment_ids, context=context):
            act_ids = self.pool.get('marketing.campaign.activity').search(cr,
                  uid, [('start', '=', True), ('campaign_id', '=', segment.campaign_id.id)])

            model_obj = self.pool.get(segment.object_id.model)
            criteria = []
            if segment.sync_last_date:
                criteria += [(segment.sync_mode, '>', segment.sync_last_date)]
            if segment.ir_filter_id:
                criteria += segment.ir_filter_id.domain
            object_ids = model_obj.search(cr, uid, criteria)

            for o_ids in  model_obj.browse(cr, uid, object_ids, context=context) :
                for act_id in act_ids:
                    wi_vals = {
                        'segment_id': segment.id,
                        'activity_id': act_id,
                        'date': action_date,
                        'partner_id': o_ids.partner_id and o_ids.partner_id.id or False,
                        'state': 'todo',
                        'res_id': o_ids.id
                    }
                    self.pool.get('marketing.campaign.workitem').create(cr, uid, wi_vals)
            self.write(cr, uid, segment.id, {'sync_last_date':action_date})
        return True

marketing_campaign_segment()

class marketing_campaign_activity(osv.osv):
    _name = "marketing.campaign.activity"
    _description = "Campaign Activity"
    _actions_type = [('email', 'E-mail'), ('paper', 'Paper'), ('action', 'Action'),
                        ('subcampaign', 'Sub-Campaign')]
    _columns = {
        'name': fields.char('Name', size=128, required=True),
        'campaign_id': fields.many2one('marketing.campaign', 'Campaign',
                                            required = True, ondelete='cascade'),
        'object_id': fields.related('campaign_id','object_id',
                                      type='many2one', relation='ir.model',
                                      string='Object'),
        'start': fields.boolean('Start',help= "This activity is launched when the campaign starts."),
        'condition': fields.char('Condition', size=256, required=True,
                                 help="Python condition to know if the activity can be launched"),
        'type': fields.selection([('email', 'E-mail'),
                                  ('paper', 'Paper'),
                                  ('action', 'Action'),
                                  ('subcampaign', 'Sub-Campaign')],
                                  'Type', required=True,
                                  help="Describe type of action to be performed on the Activity.Eg : Send email,Send paper.."),
        'email_template_id': fields.many2one('email.template','Email Template'),
        'report_id': fields.many2one('ir.actions.report.xml', 'Reports', ),
        'report_directory_id': fields.many2one('document.directory','Directory',
                                help="Folder is used to store the generated reports"),
        'server_action_id': fields.many2one('ir.actions.server', string='Action',
                                help= "Describes the action name.\n"
                                "eg:On which object which action to be taken on basis of which condition"),
        'to_ids': fields.one2many('marketing.campaign.transition',
                                            'activity_from_id',
                                            'Next Activities'),
        'from_ids': fields.one2many('marketing.campaign.transition',
                                            'activity_to_id',
                                            'Previous Activities'),
        'subcampaign_id': fields.many2one('marketing.campaign', 'Sub-Campaign'),
        'subcampaign_segment_id': fields.many2one('marketing.campaign.segment',
                                                   'Sub Campaign Segment'),
        'variable_cost': fields.float('Variable Cost'),
        'revenue': fields.float('Revenue')
    }

    _defaults = {
        'type': lambda *a: 'email',
        'condition': lambda *a: 'True',
        'object_id' : lambda obj, cr, uid, context  : context.get('object_id',False),
    }
    def __init__(self, *args):
        self._actions = {'paper' : self.process_wi_report,
                    'email' : self.process_wi_email,
                    'server_action' : self.process_wi_action,
            }        
        return super(marketing_campaign_activity, self).__init__(*args)

    def search(self, cr, uid, args, offset=0, limit=None, order=None,
                                        context=None, count=False):
        if context == None:
            context = {}
        if 'segment_id' in context  and context['segment_id']:
            segment_obj = self.pool.get('marketing.campaign.segment').browse(cr,
                                                    uid, context['segment_id'])
            act_ids = []
            for activity in segment_obj.campaign_id.activity_ids:
                act_ids.append(activity.id)
            return act_ids
        return super(marketing_campaign_activity, self).search(cr, uid, args,
                                           offset, limit, order, context, count)

    def process_wi_report(self, cr, uid, activity, workitem):
        service = netsvc.LocalService('report.%s'%activity.report_id.report_name)
        (report_data, format) = service.create(cr, uid, [], {}, {})
        attach_vals = {
                'name': '%s_%s_%s'%(activity.report_id.report_name,
                                    activity.name,workitem.partner_id.name),
                'datas_fname': '%s.%s'%(activity.report_id.report_name,
                                            activity.report_id.report_type),
                'parent_id': activity.report_directory_id.id,
                'datas': base64.encodestring(report_data),
                'file_type': format
                }
        self.pool.get('ir.attachment').create(cr, uid, attach_vals)
        return True

    def process_wi_email(self, cr, uid, activity, workitem):
        template = activity.email_template_id
        accounts = template.enforce_from_account
        if not template.enforce_from_account:
            return {'error_msg'  : "There is no account defined for the email"}
        if not workitem.partner_id.email:
            return {'error_msg'  : "There is no email defined for the partner"}
        vals = {
            'email_from': tools.ustr(accounts.name) + "<" + tools.ustr(accounts.email_id) + ">",
            'email_to': workitem.partner_id.email,
            'subject': template.def_subject,
            'body_text': template.def_body_text,
            'body_html': template.def_body_html,
            'account_id':accounts.id,
            'state':'na',
            'mail_type':'multipart/alternative' #Options:'multipart/mixed','multipart/alternative','text/plain','text/html'
        }
#            if accounts.use_sign:
#                signature = self.pool.get('res.users').read(cr, uid, uid, ['signature'], context)['signature']
#                if signature:
#                    vals['pem_body_text'] = tools.ustr(vals['pem_body_text'] or '') + signature
#                    vals['pem_body_html'] = tools.ustr(vals['pem_body_html'] or '') + signature

        #Create partly the mail and later update attachments
        mail_id = self.pool.get('email_template.mailbox').create(cr, uid, vals, context)
        return True
        
    def process_wi_action(self, cr, uid, activity, workitem):
        context = {}
        server_obj = self.pool.get('ir.actions.server')
        server_obj.run(cr, uid, [activity.server_action_id.id], context)    
        return True
                

    def process(self, cr, uid, act_id, wi_id, context={}):
        activity = self.browse(cr, uid, act_id)
        workitem_obj = self.pool.get('marketing.campaign.workitem')
        workitem = workitem_obj.browse(cr, uid, wi_id)
        self._actions[activity.type](cr, uid, activity, workitem)
        return True

marketing_campaign_activity()

class marketing_campaign_transition(osv.osv):
    _name = "marketing.campaign.transition"
    _description = "Campaign Transition"
    _rec_name = "interval_type"

    _columns = {
        'activity_from_id': fields.many2one('marketing.campaign.activity',
                                                             'Source Activity'),
        'activity_to_id': fields.many2one('marketing.campaign.activity',
                                                        'Destination Activity'),
        'interval_nbr': fields.integer('Interval No.'),
        'interval_type': fields.selection([('hours', 'Hours'), ('days', 'Days'),
                                           ('months', 'Months'),
                                            ('years','Years')],'Interval Type')
        }

    def default_get(self, cr, uid, fields, context={}):
        value = super(marketing_campaign_transition, self).default_get(cr, uid,
                                                                fields, context)
        if context.has_key('type_id'):
            value[context['type_id']] = context['activity_id']
        return value

marketing_campaign_transition()

class marketing_campaign_workitem(osv.osv):
    _name = "marketing.campaign.workitem"
    _description = "Campaign Workitem"

    def _res_name_get(self, cr, uid, ids, field_name, arg, context=None):
        res = {}
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.res_id:
                try:
                    res[obj.id] = self.pool.get(obj.object_id.model).name_get(cr, uid, [obj.res_id], context=context)[0][1]
                except:
                    res[obj.id] = '/'
            else:
                res[obj.id] = '/'
        return res

    _columns = {
        'segment_id': fields.many2one('marketing.campaign.segment', 'Segment',
             required=True),
        'activity_id': fields.many2one('marketing.campaign.activity','Activity',
             required=True),
        'campaign_id': fields.related('segment_id', 'campaign_id',
             type='many2one', relation='marketing.campaign', string='Campaign', readonly=True),
        'object_id': fields.related('segment_id', 'campaign_id', 'object_id',
             type='many2one', relation='ir.model', string='Object'),
        'res_id': fields.integer('Resource ID'),
        'res_name': fields.function(_res_name_get, method=True, string='Resource Name', type="char", size=64),
        'date': fields.datetime('Execution Date'),
        'partner_id': fields.many2one('res.partner', 'Partner',required=True),
        'state': fields.selection([('todo', 'ToDo'), ('inprogress', 'In Progress'),
                                   ('exception', 'Exception'), ('done', 'Done'),
                                   ('cancelled', 'Cancelled')], 'State'),

        'error_msg' : fields.text('Error Message')
    }
    _defaults = {
        'state': lambda *a: 'todo',
    }

    def process_chain(self, cr, uid, workitem_id, context={}):
        workitem = self.browse(cr, uid, workitem_id)
        for mct_id in workitem.activity_id.to_ids:
            launch_date = time.strftime('%Y-%m-%d %H:%M:%S')
            if mct_id.interval_type and mct_id.interval_nbr :
                launch_date = (datetime.now() + _intervalTypes[ \
                                mct_id.interval_type](mct_id.interval_nbr) \
                                ).strftime('%Y-%m-%d %H:%M:%S')
            workitem_vals = {
                'segment_id': workitem.segment_id.id,
                'activity_id': mct_id.activity_to_id.id,
                'date': launch_date,
                'partner_id': workitem.partner_id.id,
                'res_id': workitem.res_id,
                'state': 'todo',
            }
            self.create(cr, uid, workitem_vals)
        return True

    def button_cancel(self, cr, uid, workitem_ids, context={}):
        for wi in self.browse(cr, uid, workitem_ids):
            if wi.state in ('todo','exception'):
                self.write(cr, uid, [wi.id], {'state':'cancelled'}, context=context)
        return True

    def process(self, cr, uid, workitem_ids, context={}):
        for wi in self.browse(cr, uid, workitem_ids):
            if wi.state == 'todo':
                eval_context = {
                    'pool': self.pool,
                    'cr': cr,
                    'uid': uid,
                    'wi': wi,
                    'object': wi.activity_id,
                    'transition': wi.activity_id.to_ids
                }
                expr = eval(str(wi.activity_id.condition), eval_context)
                if expr:
                    try :
                        if wi.campaign_id.mode in ('manual','active'):
                            self.pool.get('marketing.campaign.activity').process(
                                cr, uid, wi.activity_id.id, wi.id, context)
                        self.write(cr, uid, wi.id, {'state': 'done'})
                        self.process_chain(cr, uid, wi.id, context)
                    except Exception,e:
                        self.write(cr, uid, wi.id, {'state': 'exception'})
                else :
                    self.write(cr, uid, wi.id, {'state': 'cancelled'})

        return True

    def process_all(self, cr, uid, context={}):
        camp_obj = self.pool.get('marketing.campaign')
        camp_ids = camp_obj.search(cr, uid, [('state','=','running')], context=context)
        for camp in camp_obj.browse(cr, uid, camp_ids, context=context):
            if camp.mode in ('test_realtime','active'):
                workitem_ids = self.search(cr, uid, [('state', '=', 'todo'),
                        ('date','<=', time.strftime('%Y-%m-%d %H:%M:%S'))])
            elif camp.mode == 'test':
                workitem_ids = self.search(cr, uid, [('state', '=', 'todo')])
            else:
                # manual states are not processed automatically
                pass
        if workitem_ids:
            self.process(cr, uid, workitem_ids, context)

marketing_campaign_workitem()

class email_template(osv.osv):
    _inherit = "email.template"
    _defaults = {
        'object_name': lambda obj, cr, uid, context: context.get('object_id',False),
    }
email_template()

class report_xml(osv.osv):
    _inherit = 'ir.actions.report.xml'
    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        if not context:
            context = {}
        if context and 'object_id' in context and context['object_id']:
            model = self.pool.get('ir.model').browse(cr, uid,
                                                    context['object_id']).model
            args.append(('model', '=', model))
        return super(report_xml, self).search(cr, uid, args, offset, limit, order, context, count)

report_xml()

