#-*- coding: utf-8 -*-
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

from crm import crm
from datetime import datetime
from osv import fields,osv
from tools.translate import _
import binascii
import time
import tools
from crm import wizard

wizard.mail_compose_message.SUPPORTED_MODELS.append('project.issue')

class project_issue_version(osv.osv):
    _name = "project.issue.version"
    _order = "name desc"
    _columns = {
        'name': fields.char('Version Number', size=32, required=True),
        'active': fields.boolean('Active', required=False),
    }
    _defaults = {
        'active': 1,
    }
project_issue_version()

class project_issue(crm.crm_case, osv.osv):
    _name = "project.issue"
    _description = "Project Issue"
    _order = "priority, create_date desc"
    _inherit = ['mail.thread']

    def write(self, cr, uid, ids, vals, context=None):
        #Update last action date everytime the user change the stage, the state or send a new email
        logged_fields = ['type_id', 'state', 'message_ids']
        if any([field in vals for field in logged_fields]):
            vals['date_action_last'] = time.strftime('%Y-%m-%d %H:%M:%S')
        return super(project_issue, self).write(cr, uid, ids, vals, context)

    def case_open(self, cr, uid, ids, *args):
        """
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of case's Ids
        @param *args: Give Tuple Value
        """

        res = super(project_issue, self).case_open(cr, uid, ids, *args)
        for issue in self.browse(cr, uid, ids):
            if not issue.date_open:
                self.write(cr, uid, ids, {'date_open': time.strftime('%Y-%m-%d %H:%M:%S'), 'user_id' : uid})
        for (id, name) in self.name_get(cr, uid, ids):
            message = _("Issue '%s' has been opened.") % name
            self.log(cr, uid, id, message)
        return res

    def case_close(self, cr, uid, ids, *args):
        """
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of case's Ids
        @param *args: Give Tuple Value
        """

        res = super(project_issue, self).case_close(cr, uid, ids, *args)
        for (id, name) in self.name_get(cr, uid, ids):
            message = _("Issue '%s' has been closed.") % name
            self.log(cr, uid, id, message)
        return res

    def _compute_day(self, cr, uid, ids, fields, args, context=None):
        """
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of Openday’s IDs
        @return: difference between current date and log date
        @param context: A standard dictionary for contextual values
        """
        cal_obj = self.pool.get('resource.calendar')
        res_obj = self.pool.get('resource.resource')

        res = {}
        for issue in self.browse(cr, 1, ids, context=context):

            # if the working hours on the project are not defined, use default ones (8 -> 12 and 13 -> 17 * 5), represented by None
            if not issue.project_id or not issue.project_id.resource_calendar_id:
                working_hours = None
            else:
                working_hours = issue.project_id.resource_calendar_id.id

            res[issue.id] = {}
            for field in fields:
                duration = 0
                ans = False
                hours = 0

                date_create = datetime.strptime(issue.create_date, "%Y-%m-%d %H:%M:%S")
                if field in ['working_hours_open','day_open']:
                    if issue.date_open:
                        date_open = datetime.strptime(issue.date_open, "%Y-%m-%d %H:%M:%S")
                        ans = date_open - date_create
                        date_until = issue.date_open
                        #Calculating no. of working hours to open the issue
                        hours = cal_obj._interval_hours_get(cr, uid, working_hours,
                                                           date_create,
                                                           date_open,
                                                           timezone_from_uid=issue.user_id.id or uid,
                                                           exclude_leaves=False,
                                                           context=context)
                elif field in ['working_hours_close','day_close']:
                    if issue.date_closed:
                        date_close = datetime.strptime(issue.date_closed, "%Y-%m-%d %H:%M:%S")
                        date_until = issue.date_closed
                        ans = date_close - date_create
                        #Calculating no. of working hours to close the issue
                        hours = cal_obj._interval_hours_get(cr, uid, working_hours,
                               date_create,
                               date_close,
                               timezone_from_uid=issue.user_id.id or uid,
                               exclude_leaves=False,
                               context=context)
                elif field in ['days_since_creation']:
                    if issue.create_date:
                        days_since_creation = datetime.today() - datetime.strptime(issue.create_date, "%Y-%m-%d %H:%M:%S")
                        res[issue.id][field] = days_since_creation.days
                    continue

                elif field in ['inactivity_days']:
                    res[issue.id][field] = 0
                    if issue.date_action_last:
                        inactive_days = datetime.today() - datetime.strptime(issue.date_action_last, '%Y-%m-%d %H:%M:%S')
                        res[issue.id][field] = inactive_days.days
                    continue
                if ans:
                    resource_id = False
                    if issue.user_id:
                        resource_ids = res_obj.search(cr, uid, [('user_id','=',issue.user_id.id)])
                        if resource_ids and len(resource_ids):
                            resource_id = resource_ids[0]
                    duration = float(ans.days) + float(ans.seconds)/(24*3600)

                if field in ['working_hours_open','working_hours_close']:
                    res[issue.id][field] = hours
                elif field in ['day_open','day_close']:
                    res[issue.id][field] = duration

        return res

    def _get_issue_task(self, cr, uid, ids, context=None):
        issues = []
        issue_pool = self.pool.get('project.issue')
        for task in self.pool.get('project.task').browse(cr, uid, ids, context=context):
            issues += issue_pool.search(cr, uid, [('task_id','=',task.id)])
        return issues

    def _get_issue_work(self, cr, uid, ids, context=None):
        issues = []
        issue_pool = self.pool.get('project.issue')
        for work in self.pool.get('project.task.work').browse(cr, uid, ids, context=context):
            if work.task_id:
                issues += issue_pool.search(cr, uid, [('task_id','=',work.task_id.id)])
        return issues

    def _hours_get(self, cr, uid, ids, field_names, args, context=None):
        task_pool = self.pool.get('project.task')
        res = {}
        for issue in self.browse(cr, uid, ids, context=context):
            progress = 0.0
            if issue.task_id:
                progress = task_pool._hours_get(cr, uid, [issue.task_id.id], field_names, args, context=context)[issue.task_id.id]['progress']
            res[issue.id] = {'progress' : progress}
        return res

    _columns = {
        'id': fields.integer('ID', readonly=True),
        'name': fields.char('Issue', size=128, required=True),
        'active': fields.boolean('Active', required=False),
        'create_date': fields.datetime('Creation Date', readonly=True,select=True),
        'write_date': fields.datetime('Update Date', readonly=True),
        'days_since_creation': fields.function(_compute_day, string='Days since creation date', \
                                               multi='compute_day', type="integer", help="Difference in days between creation date and current date"),
        'date_deadline': fields.date('Deadline'),
        'section_id': fields.many2one('crm.case.section', 'Sales Team', \
                        select=True, help='Sales team to which Case belongs to.\
                             Define Responsible user and Email account for mail gateway.'),
        'partner_id': fields.many2one('res.partner', 'Partner', select=1),
        'partner_address_id': fields.many2one('res.partner.address', 'Partner Contact', \
                                 domain="[('partner_id','=',partner_id)]"),
        'company_id': fields.many2one('res.company', 'Company'),
        'description': fields.text('Description'),
        'state': fields.selection([('draft', 'New'), ('open', 'In Progress'), ('cancel', 'Cancelled'), ('done', 'Done'),('pending', 'Pending'), ], 'State', size=16, readonly=True,
                                  help='The state is set to \'Draft\', when a case is created.\
                                  \nIf the case is in progress the state is set to \'Open\'.\
                                  \nWhen the case is over, the state is set to \'Done\'.\
                                  \nIf the case needs to be reviewed then the state is set to \'Pending\'.'),
        'email_from': fields.char('Email', size=128, help="These people will receive email.", select=1),
        'email_cc': fields.char('Watchers Emails', size=256, help="These email addresses will be added to the CC field of all inbound and outbound emails for this record before being sent. Separate multiple email addresses with a comma"),
        'date_open': fields.datetime('Opened', readonly=True,select=True),
        # Project Issue fields
        'date_closed': fields.datetime('Closed', readonly=True,select=True),
        'date': fields.datetime('Date'),
        'channel_id': fields.many2one('crm.case.channel', 'Channel', help="Communication channel."),
        'categ_id': fields.many2one('crm.case.categ', 'Category', domain="[('object_id.model', '=', 'crm.project.bug')]"),
        'priority': fields.selection(crm.AVAILABLE_PRIORITIES, 'Priority', select=True),
        'version_id': fields.many2one('project.issue.version', 'Version'),
        'type_id': fields.many2one ('project.task.type', 'Stages', domain="[('project_ids', '=', project_id)]"),
        'project_id':fields.many2one('project.project', 'Project'),
        'duration': fields.float('Duration'),
        'task_id': fields.many2one('project.task', 'Task', domain="[('project_id','=',project_id)]"),
        'day_open': fields.function(_compute_day, string='Days to Open', \
                                multi='compute_day', type="float", store=True),
        'day_close': fields.function(_compute_day, string='Days to Close', \
                                multi='compute_day', type="float", store=True),
        'user_id': fields.many2one('res.users', 'Assigned to', required=False, select=1),
        'working_hours_open': fields.function(_compute_day, string='Working Hours to Open the Issue', \
                                multi='compute_day', type="float", store=True),
        'working_hours_close': fields.function(_compute_day, string='Working Hours to Close the Issue', \
                                multi='compute_day', type="float", store=True),
        'inactivity_days': fields.function(_compute_day, string='Days since last action', \
                                multi='compute_day', type="integer", help="Difference in days between last action and current date"),
        'color': fields.integer('Color Index'),
        'user_email': fields.related('user_id', 'user_email', type='char', string='User Email', readonly=True),
        'message_ids': fields.one2many('mail.message', 'res_id', 'Messages', domain=[('model','=',_name)]),
        'date_action_last': fields.datetime('Last Action', readonly=1),
        'date_action_next': fields.datetime('Next Action', readonly=1),
        'progress': fields.function(_hours_get, string='Progress (%)', multi='hours', group_operator="avg", help="Computed as: Time Spent / Total Time.",
            store = {
                'project.issue': (lambda self, cr, uid, ids, c={}: ids, ['task_id'], 10),
                'project.task': (_get_issue_task, ['progress'], 10),
                'project.task.work': (_get_issue_work, ['hours'], 10),
            }),
    }

    def _get_project(self, cr, uid, context=None):
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        if user.context_project_id:
            return user.context_project_id.id
        return False

    def on_change_project(self, cr, uid, ids, project_id, context=None):
        return {}


    _defaults = {
        'active': 1,
        'partner_id': crm.crm_case._get_default_partner,
        'partner_address_id': crm.crm_case._get_default_partner_address,
        'email_from': crm.crm_case._get_default_email,
        'state': 'draft',
        'section_id': crm.crm_case._get_section,
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'crm.helpdesk', context=c),
        'priority': crm.AVAILABLE_PRIORITIES[2][0],
        'project_id':_get_project,
        'categ_id' : lambda *a: False,
         }

    def set_priority(self, cr, uid, ids, priority):
        """Set lead priority
        """
        return self.write(cr, uid, ids, {'priority' : priority})

    def set_high_priority(self, cr, uid, ids, *args):
        """Set lead priority to high
        """
        return self.set_priority(cr, uid, ids, '1')

    def set_normal_priority(self, cr, uid, ids, *args):
        """Set lead priority to normal
        """
        return self.set_priority(cr, uid, ids, '3')

    def convert_issue_task(self, cr, uid, ids, context=None):
        case_obj = self.pool.get('project.issue')
        data_obj = self.pool.get('ir.model.data')
        task_obj = self.pool.get('project.task')


        if context is None:
            context = {}

        result = data_obj._get_id(cr, uid, 'project', 'view_task_search_form')
        res = data_obj.read(cr, uid, result, ['res_id'])
        id2 = data_obj._get_id(cr, uid, 'project', 'view_task_form2')
        id3 = data_obj._get_id(cr, uid, 'project', 'view_task_tree2')
        if id2:
            id2 = data_obj.browse(cr, uid, id2, context=context).res_id
        if id3:
            id3 = data_obj.browse(cr, uid, id3, context=context).res_id

        for bug in case_obj.browse(cr, uid, ids, context=context):
            new_task_id = task_obj.create(cr, uid, {
                'name': bug.name,
                'partner_id': bug.partner_id.id,
                'description':bug.description,
                'date_deadline': bug.date,
                'project_id': bug.project_id.id,
                # priority must be in ['0','1','2','3','4'], while bug.priority is in ['1','2','3','4','5']
                'priority': str(int(bug.priority) - 1),
                'user_id': bug.user_id.id,
                'planned_hours': 0.0,
            })

            vals = {
                'task_id': new_task_id,
                'state':'pending'
            }
            case_obj.write(cr, uid, [bug.id], vals)

        return  {
            'name': _('Tasks'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'project.task',
            'res_id': int(new_task_id),
            'view_id': False,
            'views': [(id2,'form'),(id3,'tree'),(False,'calendar'),(False,'graph')],
            'type': 'ir.actions.act_window',
            'search_view_id': res['res_id'],
            'nodestroy': True
        }


    def _convert(self, cr, uid, ids, xml_id, context=None):
        data_obj = self.pool.get('ir.model.data')
        id2 = data_obj._get_id(cr, uid, 'project_issue', xml_id)
        categ_id = False
        if id2:
            categ_id = data_obj.browse(cr, uid, id2, context=context).res_id
        if categ_id:
            self.write(cr, uid, ids, {'categ_id': categ_id})
        return True

    def convert_to_feature(self, cr, uid, ids, context=None):
        return self._convert(cr, uid, ids, 'feature_request_categ', context=context)

    def convert_to_bug(self, cr, uid, ids, context=None):
        return self._convert(cr, uid, ids, 'bug_categ', context=context)

    def next_type(self, cr, uid, ids, *args):
        for task in self.browse(cr, uid, ids):
            typeid = task.type_id.id
            types = map(lambda x:x.id, task.project_id.type_ids or [])
            if types:
                if not typeid:
                    self.write(cr, uid, task.id, {'type_id': types[0]})
                elif typeid and typeid in types and types.index(typeid) != len(types)-1 :
                    index = types.index(typeid)
                    self.write(cr, uid, task.id, {'type_id': types[index+1]})
        return True

    def prev_type(self, cr, uid, ids, *args):
        for task in self.browse(cr, uid, ids):
            typeid = task.type_id.id
            types = map(lambda x:x.id, task.project_id and task.project_id.type_ids or [])
            if types:
                if typeid and typeid in types:
                    index = types.index(typeid)
                    self.write(cr, uid, task.id, {'type_id': index and types[index-1] or False})
        return True

    def onchange_task_id(self, cr, uid, ids, task_id, context=None):
        result = {}
        if not task_id:
            return {'value':{}}
        task = self.pool.get('project.task').browse(cr, uid, task_id, context=context)
        return {'value':{'user_id': task.user_id.id,}}

    def case_escalate(self, cr, uid, ids, *args):
        """Escalates case to top level
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of case Ids
        @param *args: Tuple Value for additional Params
        """
        cases = self.browse(cr, uid, ids)
        for case in cases:
            data = {'state' : 'draft'}
            if case.project_id.project_escalation_id:
                data['project_id'] = case.project_id.project_escalation_id.id
                if case.project_id.project_escalation_id.user_id:
                    data['user_id'] = case.project_id.project_escalation_id.user_id.id
                if case.task_id:
                    self.pool.get('project.task').write(cr, uid, [case.task_id.id], {'project_id': data['project_id'], 'user_id': False})
            else:
                raise osv.except_osv(_('Warning !'), _('You cannot escalate this issue.\nThe relevant Project has not configured the Escalation Project!'))
            self.write(cr, uid, [case.id], data)
        self.message_append(cr, uid, cases, _('Escalate'))
        return True

    def message_new(self, cr, uid, msg, custom_values=None, context=None):
        """Automatically called when new email message arrives"""
        if context is None:
            context = {}
        subject = msg.get('subject') or _('No Title')
        body = msg.get('body_text')
        msg_from = msg.get('from')
        priority = msg.get('priority')
        vals = {
            'name': subject,
            'email_from': msg_from,
            'email_cc': msg.get('cc'),
            'description': body,
            'user_id': False,
        }
        if priority:
            vals['priority'] = priority
        vals.update(self.message_partner_by_email(cr, uid, msg_from))
        context.update({'state_to' : 'draft'})

        if custom_values and isinstance(custom_values, dict):
            vals.update(custom_values)

        res_id = self.create(cr, uid, vals, context)
        self.message_append_dict(cr, uid, [res_id], msg, context=context)
        if 'categ_id' not in vals:
            self.convert_to_bug(cr, uid, [res_id], context=context)
        return res_id

    def message_update(self, cr, uid, ids, msg, vals=None, default_act='pending', context=None):

        if vals is None:
            vals = {}

        if isinstance(ids, (str, int, long)):
            ids = [ids]

        vals.update({
            'description': msg['body_text']
        })
        if msg.get('priority', False):
            vals['priority'] = msg.get('priority')

        maps = {
            'cost': 'planned_cost',
            'revenue': 'planned_revenue',
            'probability': 'probability'
        }

        # Reassign the 'open' state to the case if this one is in pending or done
        for record in self.browse(cr, uid, ids, context=context):
            if record.state in ('pending', 'done'):
                record.write({'state' : 'open'})

        vls = { }
        for line in msg['body_text'].split('\n'):
            line = line.strip()
            res = tools.misc.command_re.match(line)
            if res and maps.get(res.group(1).lower(), False):
                key = maps.get(res.group(1).lower())
                vls[key] = res.group(2).lower()

        vals.update(vls)
        res = self.write(cr, uid, ids, vals)
        self.message_append_dict(cr, uid, ids, msg, context=context)
        return res

    def copy(self, cr, uid, id, default=None, context=None):
        issue = self.read(cr, uid, id, ['name'], context=context)
        if not default:
            default = {}
        default = default.copy()
        default['name'] = issue['name'] + _(' (copy)')
        return super(project_issue, self).copy(cr, uid, id, default=default,
                context=context)

project_issue()

class project(osv.osv):
    _inherit = "project.project"
    _columns = {
        'project_escalation_id' : fields.many2one('project.project','Project Escalation', help='If any issue is escalated from the current Project, it will be listed under the project selected here.', states={'close':[('readonly',True)], 'cancelled':[('readonly',True)]}),
        'reply_to' : fields.char('Reply-To Email Address', size=256)
    }

    def _check_escalation(self, cr, uid, ids, context=None):
         project_obj = self.browse(cr, uid, ids[0], context=context)
         if project_obj.project_escalation_id:
             if project_obj.project_escalation_id.id == project_obj.id:
                 return False
         return True

    _constraints = [
        (_check_escalation, 'Error! You cannot assign escalation to the same project!', ['project_escalation_id'])
    ]
project()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
