# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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

from openerp import tools

from datetime import datetime
from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp.tools import html2plaintext

AVAILABLE_PRIORITIES = [
    ('', ''),
    ('5', 'Not Good'),
    ('4', 'On Average'),
    ('3', 'Good'),
    ('2', 'Very Good'),
    ('1', 'Excellent')
]

class hr_recruitment_source(osv.osv):
    """ Sources of HR Recruitment """
    _name = "hr.recruitment.source"
    _description = "Source of Applicants"
    _columns = {
        'name': fields.char('Source Name', size=64, required=True, translate=True),
    }

class hr_recruitment_stage(osv.osv):
    """ Stage of HR Recruitment """
    _name = "hr.recruitment.stage"
    _description = "Stage of Recruitment"
    _order = 'sequence'
    _columns = {
        'name': fields.char('Name', size=64, required=True, translate=True),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying a list of stages."),
        'department_id':fields.many2one('hr.department', 'Specific to a Department', help="Stages of the recruitment process may be different per department. If this stage is common to all departments, keep this field empty."),
        'fold': fields.boolean('Hide in views if empty', help="This stage is not visible, for example in status bar or kanban view, when there are no records in that stage to display."),
        'requirements': fields.text('Requirements'),
    }
    _defaults = {
        'sequence': 1,
        'fold': False,
    }

class hr_recruitment_degree(osv.osv):
    """ Degree of HR Recruitment """
    _name = "hr.recruitment.degree"
    _description = "Degree of Recruitment"
    _columns = {
        'name': fields.char('Name', size=64, required=True, translate=True),
        'sequence': fields.integer('Sequence', help="Gives the sequence order when displaying a list of degrees."),
    }
    _defaults = {
        'sequence': 1,
    }
    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The name of the Degree of Recruitment must be unique!')
    ]

class hr_applicant(osv.Model):
    _name = "hr.applicant"
    _description = "Applicant"
    _order = "id desc"
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _track = {
        'stage_id': {
            'hr_recruitment.mt_applicant_new': lambda self, cr, uid, obj, ctx=None: obj.stage_id and obj.stage_id.sequence == 1,
            'hr_recruitment.mt_applicant_stage_changed': lambda self, cr, uid, obj, ctx=None: obj.stage_id and obj.stage_id.sequence != 1,
        },
    }

    def _get_default_department_id(self, cr, uid, context=None):
        """ Gives default department by checking if present in the context """
        return (self._resolve_department_id_from_context(cr, uid, context=context) or False)

    def _get_default_stage_id(self, cr, uid, context=None):
        """ Gives default stage_id """
        department_id = self._get_default_department_id(cr, uid, context=context)
        return self.stage_find(cr, uid, [], department_id, [('sequence', '=', '1')], context=context)

    def _resolve_department_id_from_context(self, cr, uid, context=None):
        """ Returns ID of department based on the value of 'default_department_id'
            context key, or None if it cannot be resolved to a single
            department.
        """
        if context is None:
            context = {}
        if type(context.get('default_department_id')) in (int, long):
            return context.get('default_department_id')
        if isinstance(context.get('default_department_id'), basestring):
            department_name = context['default_department_id']
            department_ids = self.pool.get('hr.department').name_search(cr, uid, name=department_name, context=context)
            if len(department_ids) == 1:
                return int(department_ids[0][0])
        return None

    def _read_group_stage_ids(self, cr, uid, ids, domain, read_group_order=None, access_rights_uid=None, context=None):
        access_rights_uid = access_rights_uid or uid
        stage_obj = self.pool.get('hr.recruitment.stage')
        order = stage_obj._order
        # lame hack to allow reverting search, should just work in the trivial case
        if read_group_order == 'stage_id desc':
            order = "%s desc" % order
        # retrieve section_id from the context and write the domain
        # - ('id', 'in', 'ids'): add columns that should be present
        # - OR ('department_id', '=', False), ('fold', '=', False): add default columns that are not folded
        # - OR ('department_id', 'in', department_id), ('fold', '=', False) if department_id: add department columns that are not folded
        department_id = self._resolve_department_id_from_context(cr, uid, context=context)
        search_domain = []
        if department_id:
            search_domain += ['|', ('department_id', '=', department_id)]
        search_domain += ['|', ('id', 'in', ids), ('department_id', '=', False)]
        stage_ids = stage_obj._search(cr, uid, search_domain, order=order, access_rights_uid=access_rights_uid, context=context)
        result = stage_obj.name_get(cr, access_rights_uid, stage_ids, context=context)
        # restore order of the search
        result.sort(lambda x,y: cmp(stage_ids.index(x[0]), stage_ids.index(y[0])))

        fold = {}
        for stage in stage_obj.browse(cr, access_rights_uid, stage_ids, context=context):
            fold[stage.id] = stage.fold or False
        return result, fold

    def _compute_day(self, cr, uid, ids, fields, args, context=None):
        """
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of Openday’s IDs
        @return: difference between current date and log date
        @param context: A standard dictionary for contextual values
        """
        res = {}
        for issue in self.browse(cr, uid, ids, context=context):
            for field in fields:
                res[issue.id] = {}
                duration = 0
                ans = False
                hours = 0

                if field in ['day_open']:
                    if issue.date_open:
                        date_create = datetime.strptime(issue.create_date, "%Y-%m-%d %H:%M:%S")
                        date_open = datetime.strptime(issue.date_open, "%Y-%m-%d %H:%M:%S")
                        ans = date_open - date_create

                elif field in ['day_close']:
                    if issue.date_closed:
                        date_create = datetime.strptime(issue.create_date, "%Y-%m-%d %H:%M:%S")
                        date_close = datetime.strptime(issue.date_closed, "%Y-%m-%d %H:%M:%S")
                        ans = date_close - date_create
                if ans:
                    duration = float(ans.days)
                    res[issue.id][field] = abs(float(duration))
        return res

    _columns = {
        'name': fields.char('Subject', size=128, required=True),
        'active': fields.boolean('Active', help="If the active field is set to false, it will allow you to hide the case without removing it."),
        'description': fields.text('Description'),
        'email_from': fields.char('Email', size=128, help="These people will receive email."),
        'email_cc': fields.text('Watchers Emails', size=252, help="These email addresses will be added to the CC field of all inbound and outbound emails for this record before being sent. Separate multiple email addresses with a comma"),
        'probability': fields.float('Probability'),
        'partner_id': fields.many2one('res.partner', 'Contact'),
        'create_date': fields.datetime('Creation Date', readonly=True, select=True),
        'write_date': fields.datetime('Update Date', readonly=True),
        'stage_id': fields.many2one ('hr.recruitment.stage', 'Stage', track_visibility='onchange',
                        domain="['|', ('department_id', '=', department_id), ('department_id', '=', False)]"),
        'categ_ids': fields.many2many('hr.applicant_category', string='Tags'),
        'company_id': fields.many2one('res.company', 'Company'),
        'user_id': fields.many2one('res.users', 'Responsible', track_visibility='onchange'),
        'date_closed': fields.datetime('Closed', readonly=True, select=True),
        'date_open': fields.datetime('Assigned', readonly=True, select=True),
        'date_last_stage_update': fields.datetime('Last Stage Update', select=True),
        'date_action': fields.date('Next Action Date'),
        'title_action': fields.char('Next Action', size=64),
        'priority': fields.selection(AVAILABLE_PRIORITIES, 'Appreciation'),
        'job_id': fields.many2one('hr.job', 'Applied Job'),
        'salary_proposed_extra': fields.char('Proposed Salary Extra', size=100, help="Salary Proposed by the Organisation, extra advantages"),
        'salary_expected_extra': fields.char('Expected Salary Extra', size=100, help="Salary Expected by Applicant, extra advantages"),
        'salary_proposed': fields.float('Proposed Salary', help="Salary Proposed by the Organisation"),
        'salary_expected': fields.float('Expected Salary', help="Salary Expected by Applicant"),
        'availability': fields.integer('Availability'),
        'partner_name': fields.char("Applicant's Name", size=64),
        'partner_phone': fields.char('Phone', size=32),
        'partner_mobile': fields.char('Mobile', size=32),
        'type_id': fields.many2one('hr.recruitment.degree', 'Degree'),
        'department_id': fields.many2one('hr.department', 'Department'),
        'survey': fields.related('job_id', 'survey_id', type='many2one', relation='survey', string='Survey'),
        'response': fields.integer("Response"),
        'reference': fields.char('Referred By', size=128),
        'source_id': fields.many2one('hr.recruitment.source', 'Source'),
        'day_open': fields.function(_compute_day, string='Days to Open', \
                                multi='day_open', type="float", store=True),
        'day_close': fields.function(_compute_day, string='Days to Close', \
                                multi='day_close', type="float", store=True),
        'color': fields.integer('Color Index'),
        'emp_id': fields.many2one('hr.employee', string='Employee',
            help='Employee linked to the applicant.'),
        'user_email': fields.related('user_id', 'email', type='char', string='User Email', readonly=True),
    }

    _defaults = {
        'active': lambda *a: 1,
        'user_id': lambda s, cr, uid, c: uid,
        'stage_id': lambda s, cr, uid, c: s._get_default_stage_id(cr, uid, c),
        'department_id': lambda s, cr, uid, c: s._get_default_department_id(cr, uid, c),
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'hr.applicant', context=c),
        'color': 0,
        'date_last_stage_update': fields.datetime.now(),
    }

    _group_by_full = {
        'stage_id': _read_group_stage_ids
    }

    def onchange_job(self, cr, uid, ids, job_id=False, context=None):
        if job_id:
            job_record = self.pool.get('hr.job').browse(cr, uid, job_id, context=context)
            if job_record and job_record.department_id:
                return {'value': {'department_id': job_record.department_id.id}}
        return {}

    def onchange_department_id(self, cr, uid, ids, department_id=False, stage_id=False, context=None):
        if not stage_id:
            stage_id = self.stage_find(cr, uid, [], department_id, [('sequence', '=', '1')], context=context)
        return {'value': {'stage_id': stage_id}}

    def onchange_partner_id(self, cr, uid, ids, partner_id, context=None):
        data = {'partner_phone': False,
                'partner_mobile': False,
                'email_from': False}
        if partner_id:
            addr = self.pool.get('res.partner').browse(cr, uid, partner_id, context)
            data.update({'partner_phone': addr.phone,
                        'partner_mobile': addr.mobile,
                        'email_from': addr.email})
        return {'value': data}

    def stage_find(self, cr, uid, cases, section_id, domain=[], order='sequence', context=None):
        """ Override of the base.stage method
            Parameter of the stage search taken from the lead:
            - department_id: if set, stages must belong to this section or
              be a default case
        """
        if isinstance(cases, (int, long)):
            cases = self.browse(cr, uid, cases, context=context)
        # collect all section_ids
        department_ids = []
        if section_id:
            department_ids.append(section_id)
        for case in cases:
            if case.department_id:
                department_ids.append(case.department_id.id)
        # OR all section_ids and OR with case_default
        search_domain = []
        if department_ids:
            search_domain += ['|', ('department_id', 'in', department_ids)]
        search_domain.append(('department_id', '=', False))
        # AND with the domain in parameter
        search_domain += list(domain)
        # perform search, return the first found
        stage_ids = self.pool.get('hr.recruitment.stage').search(cr, uid, search_domain, order=order, context=context)
        if stage_ids:
            return stage_ids[0]
        return False

    def action_makeMeeting(self, cr, uid, ids, context=None):
        """ This opens Meeting's calendar view to schedule meeting on current applicant
            @return: Dictionary value for created Meeting view
        """
        applicant = self.browse(cr, uid, ids[0], context)
        category = self.pool.get('ir.model.data').get_object(cr, uid, 'hr_recruitment', 'categ_meet_interview', context)
        res = self.pool.get('ir.actions.act_window').for_xml_id(cr, uid, 'base_calendar', 'action_crm_meeting', context)
        res['context'] = {
            'default_partner_ids': applicant.partner_id and [applicant.partner_id.id] or False,
            'default_user_id': uid,
            'default_name': applicant.name,
            'default_categ_ids': category and [category.id] or False,
        }
        return res

    def action_print_survey(self, cr, uid, ids, context=None):
        """
        If response is available then print this response otherwise print survey form(print template of the survey).

        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of Survey IDs
        @param context: A standard dictionary for contextual values
        @return: Dictionary value for print survey form.
        """
        if context is None:
            context = {}
        record = self.browse(cr, uid, ids, context=context)
        record = record and record[0]
        context.update({'survey_id': record.survey.id, 'response_id': [record.response], 'response_no': 0, })
        value = self.pool.get("survey").action_print_survey(cr, uid, ids, context=context)
        return value

    def message_get_suggested_recipients(self, cr, uid, ids, context=None):
        recipients = super(hr_applicant, self).message_get_suggested_recipients(cr, uid, ids, context=context)
        for applicant in self.browse(cr, uid, ids, context=context):
            if applicant.partner_id:
                self._message_add_suggested_recipient(cr, uid, recipients, applicant, partner=applicant.partner_id, reason=_('Contact'))
            elif applicant.email_from:
                self._message_add_suggested_recipient(cr, uid, recipients, applicant, email=applicant.email_from, reason=_('Contact Email'))
        return recipients

    def message_new(self, cr, uid, msg, custom_values=None, context=None):
        """ Overrides mail_thread message_new that is called by the mailgateway
            through message_process.
            This override updates the document according to the email.
        """
        if custom_values is None: custom_values = {}
        val = msg.get('from').split('<')[0]
        desc = html2plaintext(msg.get('body')) if msg.get('body') else ''
        defaults = {
            'name':  msg.get('subject') or _("No Subject"),
            'description': desc,
            'partner_name':val,
            'email_from': msg.get('from'),
            'email_cc': msg.get('cc'),
            'user_id': False,
            'partner_id': msg.get('author_id', False),
        }
        if msg.get('priority'):
            defaults['priority'] = msg.get('priority')
        defaults.update(custom_values)
        return super(hr_applicant,self).message_new(cr, uid, msg, custom_values=defaults, context=context)

    def message_update(self, cr, uid, ids, msg, update_vals=None, context=None):
        """ Override mail_thread message_update that is called by the mailgateway
            through message_process.
            This method updates the document according to the email.
        """
        if isinstance(ids, (str, int, long)):
            ids = [ids]
        if update_vals is None:
            update_vals = {}

        update_vals.update({
            'email_from': msg.get('from'),
            'email_cc': msg.get('cc'),
        })
        if msg.get('priority'):
            update_vals['priority'] = msg.get('priority')

        maps = {
            'cost': 'planned_cost',
            'revenue': 'planned_revenue',
            'probability': 'probability',
        }
        for line in msg.get('body', '').split('\n'):
            line = line.strip()
            res = tools.command_re.match(line)
            if res and maps.get(res.group(1).lower(), False):
                key = maps.get(res.group(1).lower())
                update_vals[key] = res.group(2).lower()

        return super(hr_applicant, self).message_update(cr, uid, ids, msg, update_vals=update_vals, context=context)

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if vals.get('department_id') and not context.get('default_department_id'):
            context['default_department_id'] = vals.get('department_id')

        obj_id = super(hr_applicant, self).create(cr, uid, vals, context=context)
        applicant = self.browse(cr, uid, obj_id, context=context)
        if applicant.job_id:
            self.pool.get('hr.job').message_post(cr, uid, [applicant.job_id.id], body=_('Applicant <b>created</b>'), subtype="hr_recruitment.mt_job_new_applicant", context=context)
        return obj_id

    def write(self, cr, uid, ids, vals, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        # stage change: update date_last_stage_update
        if 'stage_id' in vals:
            vals['date_last_stage_update'] = fields.datetime.now()
        # user_id change: update date_start
        if vals.get('user_id'):
            vals['date_start'] = fields.datetime.now()

        return super(hr_applicant, self).write(cr, uid, ids, vals, context=context)

    def create_employee_from_applicant(self, cr, uid, ids, context=None):
        """ Create an hr.employee from the hr.applicants """
        if context is None:
            context = {}
        hr_employee = self.pool.get('hr.employee')
        model_data = self.pool.get('ir.model.data')
        act_window = self.pool.get('ir.actions.act_window')
        emp_id = False
        for applicant in self.browse(cr, uid, ids, context=context):
            address_id = contact_name = False
            if applicant.partner_id:
                address_id = self.pool.get('res.partner').address_get(cr, uid, [applicant.partner_id.id], ['contact'])['contact']
                contact_name = self.pool.get('res.partner').name_get(cr, uid, [applicant.partner_id.id])[0][1]
            if applicant.job_id and (applicant.partner_name or contact_name):
                applicant.job_id.write({'no_of_recruitment': applicant.job_id.no_of_recruitment - 1})
                emp_id = hr_employee.create(cr, uid, {'name': applicant.partner_name or contact_name,
                                                     'job_id': applicant.job_id.id,
                                                     'address_home_id': address_id,
                                                     'department_id': applicant.department_id.id
                                                     })
                self.write(cr, uid, [applicant.id], {'emp_id': emp_id}, context=context)
            else:
                raise osv.except_osv(_('Warning!'), _('You must define an Applied Job and a Contact Name for this applicant.'))

        action_model, action_id = model_data.get_object_reference(cr, uid, 'hr', 'open_view_employee_list')
        dict_act_window = act_window.read(cr, uid, action_id, [])
        if emp_id:
            dict_act_window['res_id'] = emp_id
        dict_act_window['view_mode'] = 'form,tree'
        return dict_act_window

    def set_priority(self, cr, uid, ids, priority, *args):
        """Set applicant priority
        """
        return self.write(cr, uid, ids, {'priority': priority})

    def set_high_priority(self, cr, uid, ids, *args):
        """Set applicant priority to high
        """
        return self.set_priority(cr, uid, ids, '1')

    def set_normal_priority(self, cr, uid, ids, *args):
        """Set applicant priority to normal
        """
        return self.set_priority(cr, uid, ids, '3')

    def get_empty_list_help(self, cr, uid, help, context=None):
        context['empty_list_help_model'] = 'hr.job'
        context['empty_list_help_id'] = context.get('default_job_id', None)
        context['empty_list_help_document_name'] = _("job applicants")
        return super(hr_applicant, self).get_empty_list_help(cr, uid, help, context=context)


class hr_job(osv.osv):
    _inherit = "hr.job"
    _name = "hr.job"
    _inherits = {'mail.alias': 'alias_id'}
    _columns = {
        'survey_id': fields.many2one('survey', 'Interview Form', help="Choose an interview form for this job position and you will be able to print/answer this interview from all applicants who apply for this job"),
        'alias_id': fields.many2one('mail.alias', 'Alias', ondelete="cascade", required=True,
                                    help="Email alias for this job position. New emails will automatically "
                                         "create new applicants for this job position."),
    }

    def _auto_init(self, cr, context=None):
        """Installation hook to create aliases for all jobs and avoid constraint errors."""
        return self.pool.get('mail.alias').migrate_to_alias(cr, self._name, self._table, super(hr_job, self)._auto_init,
            'hr.applicant', self._columns['alias_id'], 'name', alias_prefix='job+', alias_defaults={'job_id': 'id'}, context=context)

    def create(self, cr, uid, vals, context=None):
        alias_context = dict(context, alias_model_name='hr.applicant', alias_parent_model_name=self._name)
        job_id = super(hr_job, self).create(cr, uid, vals, context=alias_context)
        job = self.browse(cr, uid, job_id, context=context)
        self.pool.get('mail.alias').write(cr, uid, [job.alias_id.id], {'alias_parent_thread_id': job_id, "alias_defaults": {'job_id': job_id}}, context)
        return job_id

    def unlink(self, cr, uid, ids, context=None):
        # Cascade-delete mail aliases as well, as they should not exist without the job position.
        mail_alias = self.pool.get('mail.alias')
        alias_ids = [job.alias_id.id for job in self.browse(cr, uid, ids, context=context) if job.alias_id]
        res = super(hr_job, self).unlink(cr, uid, ids, context=context)
        mail_alias.unlink(cr, uid, alias_ids, context=context)
        return res

    def action_print_survey(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        datas = {}
        record = self.browse(cr, uid, ids, context=context)[0]
        if record.survey_id:
            datas['ids'] = [record.survey_id.id]
        datas['model'] = 'survey.print'
        context.update({'response_id': [0], 'response_no': 0})
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'survey.form',
            'datas': datas,
            'context': context,
            'nodestroy': True,
        }


class applicant_category(osv.osv):
    """ Category of applicant """
    _name = "hr.applicant_category"
    _description = "Category of applicant"
    _columns = {
        'name': fields.char('Name', size=64, required=True, translate=True),
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
