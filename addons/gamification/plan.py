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

from openerp.osv import fields, osv

from templates import TemplateHelper

from datetime import date, datetime, timedelta
import calendar


def start_end_date_for_period(period):
    """Return the start and end date for a goal period based on today

    :return (start_date, end_date), datetime.date objects, False if the period is
    not defined or unknown"""
    today = date.today()
    if period == 'daily':
        start_date = today
        end_date = start_date # ? + timedelta(days=1)
    elif period == 'weekly':
        delta = timedelta(days=today.weekday())
        start_date = today - delta
        end_date = start_date + timedelta(days=7)
    elif period == 'monthly':
        month_range = calendar.monthrange(today.year, today.month)
        start_date = today.replace(day=1)
        end_date = today.replace(day=month_range[1])
    elif period == 'yearly':
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
    else: # period == 'once':
        start_date = False  # for manual goal, start each time
        end_date = False

    return (start_date, end_date)


class gamification_goal_plan(osv.Model):
    """Gamification goal plan

    Set of predifined goals to be able to automate goal settings or
    quickly apply several goals manually to a group of users

    If 'user_ids' is defined and 'period' is different than 'one', the set will
    be assigned to the users for each period (eg: every 1st of each month if
    'monthly' is selected)
    """

    _name = 'gamification.goal.plan'
    _description = 'Gamification goal plan'
    _inherit = 'mail.thread'

    def _get_next_report_date(self, cr, uid, ids, field_name, arg, context=None):
        """Return the next report date based on the last report date and report
        period. Return a string in isoformat."""
        res = {}
        for plan in self.browse(cr, uid, ids, context):
            last = datetime.strptime(plan.last_report_date, '%Y-%m-%d').date()
            if plan.report_message_frequency == 'daily':
                res[plan.id] = last + timedelta(days=1).isoformat()
            elif plan.report_message_frequency == 'weekly':
                res[plan.id] = last + timedelta(days=7).isoformat()
            elif plan.report_message_frequency == 'monthly':
                month_range = calendar.monthrange(last.year, last.month)
                res[plan.id] = last.replace(day=month_range[1]) + timedelta(days=1).isoformat()
            elif plan.report_message_frequency == 'yearly':
                res[plan.id] = last.replace(year=last.year + 1).isoformat()
            else:  # frequency == 'once':
                res[plan.id] = False

        return res

    _columns = {
        'name': fields.char('Plan Name', required=True, translate=True),
        'user_ids': fields.many2many('res.users',
            string='Users',
            help="List of users to which the goal will be set"),
        'manager_id': fields.many2one('res.users', required=True,
            string='Manager', help="The user that will be able to access the user goals and modify the plan."),
        'planline_ids': fields.one2many('gamification.goal.planline',
            'plan_id',
            string='Planline',
            help="list of goals that will be set",
            required=True),
        'autojoin_group_id': fields.many2one('res.groups',
            string='Auto-join Group',
            help='Group of users whose members will automatically be added to the users'),
        'period': fields.selection([
                ('once', 'No Periodicity'),
                ('daily', 'Daily'),
                ('weekly', 'Weekly'),
                ('monthly', 'Monthly'),
                ('yearly', 'Yearly')
            ],
            string='Periodicity',
            help='Period of automatic goal assigment. If none is selected, should be launched manually.',
            required=True),
        'start_date': fields.date('Starting Date', help="The day a new plan will be automatically started. The start and end dates for goals are still defined by the periodicity (eg: weekly goals run from Monday to Sunday)."),
        'state': fields.selection([
                ('draft', 'Draft'),
                ('inprogress', 'In progress'),
                ('done', 'Done'),
            ],
            string='State',
            required=True),
        'visibility_mode': fields.selection([
                ('board','Leader board'),
                ('progressbar','Personal progressbar')
            ],
            string="Visibility",
            help='How are displayed the results, shared or in a single progressbar',
            required=True),
        'report_message_frequency': fields.selection([
                ('never','Never'),
                ('onchange','On change'),
                ('daily','Daily'),
                ('weekly','Weekly'),
                ('monthly','Monthly'),
                ('yearly', 'Yearly')
            ],
            string="Report Frequency",
            required=True),
        'report_message_group_id': fields.many2one('mail.group',
            string='Send a copy to',
            help='Group that will receive a copy of the report in addition to the user'),
        'report_header': fields.text('Report Header'),
        'remind_update_delay': fields.integer('Remind delay',
            help="The number of days after which the user assigned to a manual goal will be reminded. Never reminded if no value or zero is specified."),
        'last_report_date': fields.date('Last Report Date'),
        'next_report_date': fields.function(_get_next_report_date,
            type='date',
            string='Next Report Date'),
        }

    _defaults = {
        'period': 'once',
        'state': 'draft',
        'visibility_mode' : 'progressbar',
        'report_message_frequency' : 'onchange',
        'last_report_date' : fields.date.today,
        'start_date' : fields.date.today,
        'manager_id' : lambda s, cr, uid, c: uid,
    }

    def _check_nonzero_planline(self, cr, uid, ids, context=None):
        """checks that there is at least one planline set"""
        for plan in self.browse(cr, uid, ids, context):
            if len(plan.planline_ids) < 1:
                return False
        return True

    def _check_nonzero_users(self, cr, uid, ids, context=None):
        """checks that there is at least one user set"""
        for plan in self.browse(cr, uid, ids, context):
            if len(plan.user_ids) < 1 and plan.state != 'draft':
                return False
        return True

    _constraints = [
        (_check_nonzero_planline, "At least one planline is required to create a goal plan", ['planline_ids']),
        (_check_nonzero_users, "At least one user is required to create a non-draft goal plan", ['user_ids']),
    ]

    def write(self, cr, uid, ids, vals, context=None):
        """Overwrite the write method to add the user of groups"""
        context = context or {}
        if not ids:
            return True

        write_res = super(gamification_goal_plan, self).write(cr, uid, ids, vals, context=context)

        # add users when change the group auto-subscription
        if 'autojoin_group_id' in vals:
            new_group = self.pool.get('res.groups').browse(cr, uid, vals['autojoin_group_id'], context=context)
            if new_group:
                self.plan_subscribe_users(cr, uid, ids, [user.id for user in new_group.users], context=context)

        # add the selected manager to the goal_manager group
        if 'manager_id' in vals:
            group_ref = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'gamification', 'group_goal_manager')
            self.pool.get('res.users').write(cr, uid, [vals['manager_id']], {'groups_id': [(4, group_ref[1])]}, context=context)

        return write_res


    def _cron_update(self, cr, uid, context=None, ids=False):
        """Daily cron check.

        Start planned plans (in draft and with start_date = today)
        Create the goals for planlines not linked to goals (eg: modified the 
            plan to add planlines)
        Update every goal running"""
        if not context: context = {}

        # start planned plans
        planned_plan_ids = self.search(cr, uid, [
            ('state', '=', 'draft'),
            ('start_date', '=', fields.date.today())])
        self.action_start(cr, uid, planned_plan_ids, context=context)

        if not ids:
            ids = self.search(cr, uid, [('state', '=', 'inprogress')])

        goal_obj = self.pool.get('gamification.goal')
        # we use yesterday to update the goals that just ended
        yesterday = date.today() - timedelta(days=1)
        # TOCHECK conflict with date rule in goal update() function
        goal_ids = goal_obj.search(cr, uid, [
            '&',
                ('state', 'not in', ('draft', 'canceled')),
                '|',
                    ('end_date', '>=', yesterday.isoformat()),
                    ('end_date', '=', False)
        ], context=context)
        goal_obj.update(cr, uid, goal_ids, context=context)

        return self._update_all(cr, uid, ids, context=context)

    def _update_all(self, cr, uid, ids, context=None):
        """Update the plans and related goals

        :param list(int) ids: the ids of the plans to update, if False will
        update only plans in progress."""
        if not context: context = {}
        goal_obj = self.pool.get('gamification.goal')

        self.generate_goals_from_plan(cr, uid, ids, context=context)

        for plan in self.browse(cr, uid, ids, context=context):
            # goals closed but still opened at the last report date
            closed_goals_to_report = goal_obj.search(cr, uid, [
                ('plan_id', '=', plan.id),
                ('start_date', '>=', plan.last_report_date),
                ('end_date', '<=', plan.last_report_date)
            ])

            if len(closed_goals_to_report) > 0:
                # some goals need a final report
                self.report_progress(cr, uid, plan, subset_goal_ids=closed_goals_to_report, context=context)
                self.write(cr, uid, plan.id, {'last_report_date': fields.date.today}, context=context)

            if fields.date.today() == plan.next_report_date:
                self.report_progress(cr, uid, plan, context=context)
                self.write(cr, uid, plan.id, {'last_report_date': fields.date.today}, context=context)


    def action_start(self, cr, uid, ids, context=None):
        """Start a draft goal plan

        Change the state of the plan to in progress"""
        # subscribe users if autojoin group
        for plan in self.browse(cr, uid, ids, context=context):
            if plan.autojoin_group_id:
                self.plan_subscribe_users(cr, uid, ids, [user.id for user in plan.autojoin_group_id.users], context=context)

        self.write(cr, uid, ids, {'state': 'inprogress'}, context=context)
        return self.generate_goals_from_plan(cr, uid, ids, context=context)

    def action_check(self, cr, uid, ids, context=None):
        """Check a goal plan

        Create goals that haven't been created yet (eg: if added users of planlines)
        Recompute the current value for each goal related"""
        return self._update_all(cr, uid, ids=ids, context=context)


    def action_close(self, cr, uid, ids, context=None):
        """Close a plan in progress

        Change the state of the plan to in done
        Does NOT close the related goals, this is handled by the goal itself"""
        return self.write(cr, uid, ids, {'state': 'done'}, context=context)

    def action_reset(self, cr, uid, ids, context=None):
        """Reset a closed goal plan

        Change the state of the plan to in progress
        Closing a plan does not affect the goals so neither does reset"""
        return self.write(cr, uid, ids, {'state': 'inprogress'}, context=context)

    def action_cancel(self, cr, uid, ids, context=None):
        """Cancel a plan in progress

        Change the state of the plan to draft
        Cancel the related goals"""
        self.write(cr, uid, ids, {'state': 'draft'}, context=context)
        goal_ids = self.pool.get('gamification.goal').search(cr, uid, [('plan_id', 'in', ids)], context=context)
        self.pool.get('gamification.goal').write(cr, uid, goal_ids, {'state': 'canceled'}, context=context)

        return True

    def action_show_related_goals(self, cr, uid, ids, context=None):
        """ This opens goal view with a restriction to the list of goals from this plan only
            @return: the goal view
        """
        # get ids of related goals 
        goal_obj = self.pool.get('gamification.goal')
        related_goal_ids = []
        goal_ids = goal_obj.search(cr, uid, [('plan_id', 'in', ids)], context=context)
        for plan in self.browse(cr, uid, ids, context=context):
            for planline in plan.planline_ids:
                goal_ids = goal_obj.search(cr, uid, [('planline_id', '=', planline.id)], context=context)
                related_goal_ids.extend(goal_ids)
        
        # process the new view
        if context is None:
            context = {}
        res = self.pool.get('ir.actions.act_window').for_xml_id(cr, uid ,'gamification','goals_from_plan_act', context=context)
        res['context'] = context
        res['context'].update({
            'default_id': related_goal_ids
        })
        res['domain'] = [('id','in', related_goal_ids)]
        return res

    def action_report_progress(self, cr, uid, ids, context=None):
        """Manual report of a goal, does not influence automatic report frequency"""
        for plan in self.browse(cr, uid, ids, context):
            self.report_progress(cr, uid, plan, context=context)
        return True

    def generate_goals_from_plan(self, cr, uid, ids, context=None):
        """Generate the list of goals linked to a plan.

        If goals already exist for this planline, the planline is skipped. This
        can be called after each change in the user or planline list.
        :param list(int) ids: the list of plan concerned"""

        for plan in self.browse(cr, uid, ids, context):
            (start_date, end_date) = start_end_date_for_period(plan.period)

            for planline in plan.planline_ids:
                for user in plan.user_ids:

                    goal_obj = self.pool.get('gamification.goal')
                    domain = [('planline_id', '=', planline.id), ('user_id', '=', user.id)]
                    if start_date:
                        domain.append(('start_date', '=', start_date))

                    # goal already existing for this planline ?
                    if len(goal_obj.search(cr, uid, domain, context=context)) > 0:

                        # resume canceled goals
                        domain.append(('state', '=', 'canceled'))
                        canceled_goal_ids = goal_obj.search(cr, uid, domain, context=context)
                        goal_obj.write(cr, uid, canceled_goal_ids, {'state': 'inprogress'}, context=context)
                        goal_obj.update(cr, uid, canceled_goal_ids, context=context)

                        # skip to next user
                        continue

                    values = {
                        'type_id': planline.type_id.id,
                        'planline_id': planline.id,
                        'user_id': user.id,
                        'target_goal': planline.target_goal,
                        'state': 'inprogress',
                    }

                    if start_date:
                        values['start_date'] = start_date.isoformat()
                    if end_date:
                        values['end_date'] = end_date.isoformat()

                    if planline.plan_id.remind_update_delay:
                        values['remind_update_delay'] = planline.plan_id.remind_update_delay

                    new_goal_id = goal_obj.create(cr, uid, values, context)

                    goal_obj.update(cr, uid, [new_goal_id], context=context)

        return True

    def plan_subscribe_users(self, cr, uid, ids, new_user_ids, context=None):
        """ Add the following users to plans

        :param ids: ids of plans to which the users will be added
        :param new_user_ids: ids of the users to add"""

        for plan in self.browse(cr, uid, ids, context):
            subscription = [user.id for user in plan.user_ids]
            subscription.extend(new_user_ids)
            # remove duplicates
            unified_subscription = list(set(subscription))

            self.write(cr, uid, ids, {'user_ids': [(4, user) for user in unified_subscription]}, context=context)
        return True

    def report_progress(self, cr, uid, plan, context=None, users=False, subset_goal_ids=False):
        """Post report about the progress of the goals

        :param plan: the plan object that need to be reported
        :param users: the list(res.users) of users that are concerned by
          the report. If False, will send the report to every user concerned
          (goal users and group that receive a copy). Only used for plan with
          a visibility mode set to 'personal'.
        :param goal_ids: the list(int) of goal ids linked to the plan for
          the report. If not specified, use the goals for the current plan
          period. This parameter can be used to produce report for previous plan
          periods.
        :param subset_goal_ids: a list(int) of goal ids to restrict the report
        """

        context = context or {}
        goal_obj = self.pool.get('gamification.goal')
        template_env = TemplateHelper()

        (start_date, end_date) = start_end_date_for_period(plan.period)

        if plan.visibility_mode == 'board':
            # generate a shared report
            planlines_boards = []

            for planline in plan.planline_ids:

                domain = [
                    ('planline_id', '=', planline.id),
                    ('state', 'in', ('inprogress', 'inprogress_update',
                                     'reached', 'failed')),
                ]

                if subset_goal_ids:
                    goal_ids = goal_obj.search(cr, uid, domain, context=context)
                    common_goal_ids = [goal for goal in goal_ids if goal in subset_goal_ids]
                else:
                    # if no subset goals, use the dates for restriction
                    if start_date:
                        domain.append(('start_date', '=', start_date.isoformat()))
                    if end_date:
                        domain.append(('end_date', '=', end_date.isoformat()))
                    common_goal_ids = goal_obj.search(cr, uid, domain, context=context)

                board_goals = []
                for goal in goal_obj.browse(cr, uid, common_goal_ids, context=context):
                    board_goals.append({
                        'user': goal.user_id,
                        'current':goal.current,
                        'target_goal':goal.target_goal,
                        'completeness':goal.completeness,
                    })

                # most complete first, current if same percentage (eg: if several 100%)
                sorted_board = enumerate(sorted(board_goals, key=lambda k: (k['completeness'], k['current']), reverse=True))
                planlines_boards.append({'goal_type': planline.type_id.name, 'board_goals': sorted_board})

            body_html = template_env.get_template('group_progress.mako').render({'object': plan, 'planlines_boards': planlines_boards})

            self.message_post(cr, uid, plan.id,
                body=body_html,
                partner_ids=[(6, 0, [user.partner_id.id for user in plan.user_ids])],
                context=context,
                subtype='mail.mt_comment')
            if plan.report_message_group_id:
                self.pool.get('mail.group').message_post(cr, uid, plan.report_message_group_id.id,
                    body=body_html,
                    context=context,
                    subtype='mail.mt_comment')

        else:
            # generate individual reports
            for user in users or plan.user_ids:
                domain = [
                    ('plan_id', '=', plan.id),
                    ('user_id', '=', user.id),
                    ('state', 'in', ('inprogress', 'inprogress_update',
                                     'reached', 'failed')),
                ]
                if subset_goal_ids:
                    # use the domain for safety, don't want irrelevant report if wrong argument
                    goal_ids = goal_obj.search(cr, uid, domain, context=context)
                    related_goal_ids = [goal for goal in goal_ids if goal in subset_goal_ids]
                else:
                    # if no subset goals, use the dates for restriction
                    if start_date:
                        domain.append(('start_date', '=', start_date.isoformat()))
                    if end_date:
                        domain.append(('end_date', '=', end_date.isoformat()))
                related_goal_ids = goal_obj.search(cr, uid, domain, context=context)

                if len(related_goal_ids) == 0:
                    continue

                variables = {
                    'object': plan,
                    'user': user,
                    'goals': goal_obj.browse(cr, uid, related_goal_ids, context=context)
                }
                body_html = template_env.get_template('personal_progress.mako').render(variables)

                self.message_post(cr, uid, plan.id,
                                  body=body_html,
                                  partner_ids=[(4, user.partner_id.id)],
                                  context=context,
                                  subtype='mail.mt_comment')
                if plan.report_message_group_id:
                    self.pool.get('mail.group').message_post(cr, uid, plan.report_message_group_id.id,
                                                             body=body_html,
                                                             context=context,
                                                             subtype='mail.mt_comment')
        return True


class gamification_goal_planline(osv.Model):
    """Gamification goal planline

    Predifined goal for 'gamification_goal_plan'
    These are generic list of goals with only the target goal defined
    Should only be created for the gamification_goal_plan object
    """

    _name = 'gamification.goal.planline'
    _description = 'Gamification generic goal for plan'
    _order = "sequence_type"

    def _get_planline_types(self, cr, uid, ids, context=None):
        """Return the ids of planline items related to the gamification.goal.type
        objects in 'ids (used to update the value of 'sequence_type')'"""

        result = {}
        for goal_type in self.pool.get('gamification.goal.type').browse(cr, uid, ids, context=context):
            domain = [('type_id', '=', goal_type.id)]
            planline_ids = self.pool.get('gamification.goal.planline').search(cr, uid, domain, context=context)
            for p_id in planline_ids:
                result[p_id] = True
        return result.keys()

    _columns = {
        'plan_id': fields.many2one('gamification.goal.plan',
            string='Plan',
            ondelete="cascade"),
        'type_id': fields.many2one('gamification.goal.type',
            string='Goal Type',
            required=True,
            ondelete="cascade"),
        'target_goal': fields.float('Target Value to Reach',
            required=True),
        'sequence_type': fields.related('type_id', 'sequence',
            type='integer',
            string='Sequence',
            readonly=True,
            store={
                'gamification.goal.type': (_get_planline_types, ['sequence'], 10),
                }),
    }
