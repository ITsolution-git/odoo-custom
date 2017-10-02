# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo
from odoo import api, fields, models, tools, SUPERUSER_ID, _
from odoo.exceptions import MissingError, UserError, ValidationError, AccessError
from odoo.tools.safe_eval import safe_eval, test_python_expr
from odoo.tools import pycompat
from odoo.http import request

from collections import defaultdict
import datetime
import dateutil
import logging
import time

from pytz import timezone

_logger = logging.getLogger(__name__)


class IrActions(models.Model):
    _name = 'ir.actions.actions'
    _table = 'ir_actions'
    _order = 'name'

    name = fields.Char(required=True)
    type = fields.Char(string='Action Type', required=True)
    xml_id = fields.Char(compute='_compute_xml_id', string="External ID")
    help = fields.Html(string='Action Description',
                       help='Optional help text for the users with a description of the target view, such as its usage and purpose.',
                       translate=True)
    binding_model_id = fields.Many2one('ir.model', ondelete='cascade',
                                       help="Setting a value makes this action available in the sidebar for the given model.")
    binding_type = fields.Selection([('action', 'Action'),
                                     ('report', 'Report')],
                                    required=True, default='action')

    def _compute_xml_id(self):
        res = self.get_external_id()
        for record in self:
            record.xml_id = res.get(record.id)

    @api.model
    def create(self, vals):
        res = super(IrActions, self).create(vals)
        # self.get_bindings() depends on action records
        self.clear_caches()
        return res

    @api.multi
    def write(self, vals):
        res = super(IrActions, self).write(vals)
        # self.get_bindings() depends on action records
        self.clear_caches()
        return res

    @api.multi
    def unlink(self):
        """unlink ir.action.todo which are related to actions which will be deleted.
           NOTE: ondelete cascade will not work on ir.actions.actions so we will need to do it manually."""
        todos = self.env['ir.actions.todo'].search([('action_id', 'in', self.ids)])
        todos.unlink()
        res = super(IrActions, self).unlink()
        # self.get_bindings() depends on action records
        self.clear_caches()
        return res

    @api.model
    def _get_eval_context(self, action=None):
        """ evaluation context to pass to safe_eval """
        return {
            'uid': self._uid,
            'user': self.env.user,
            'time': time,
            'datetime': datetime,
            'dateutil': dateutil,
            'timezone': timezone,
        }

    @api.model
    @tools.ormcache('frozenset(self.env.user.groups_id.ids)', 'model_name')
    def get_bindings(self, model_name):
        """ Retrieve the list of actions bound to the given model.

           :return: a dict mapping binding types to a list of dict describing
                    actions, where the latter is given by calling the method
                    ``read`` on the action record.
        """
        cr = self.env.cr
        query = """ SELECT a.id, a.type, a.binding_type
                    FROM ir_actions a, ir_model m
                    WHERE a.binding_model_id=m.id AND m.model=%s
                    ORDER BY a.id """
        cr.execute(query, [model_name])

        # discard unauthorized actions, and read action definitions
        result = defaultdict(list)
        user_groups = self.env.user.groups_id
        for action_id, action_model, binding_type in cr.fetchall():
            try:
                action = self.env[action_model].browse(action_id)
                action_groups = getattr(action, 'groups_id', ())
                if action_groups and not action_groups & user_groups:
                    # the user may not perform this action
                    continue
                result[binding_type].append(action.read()[0])
            except (AccessError, MissingError):
                continue

        return result


class IrActionsActWindow(models.Model):
    _name = 'ir.actions.act_window'
    _table = 'ir_act_window'
    _inherit = 'ir.actions.actions'
    _sequence = 'ir_actions_id_seq'
    _order = 'name'

    @api.constrains('res_model', 'src_model')
    def _check_model(self):
        for action in self:
            if action.res_model not in self.env:
                raise ValidationError(_('Invalid model name %r in action definition.') % action.res_model)
            if action.src_model and action.src_model not in self.env:
                raise ValidationError(_('Invalid model name %r in action definition.') % action.src_model)

    @api.depends('view_ids.view_mode', 'view_mode', 'view_id.type')
    def _compute_views(self):
        """ Compute an ordered list of the specific view modes that should be
            enabled when displaying the result of this action, along with the
            ID of the specific view to use for each mode, if any were required.

            This function hides the logic of determining the precedence between
            the view_modes string, the view_ids o2m, and the view_id m2o that
            can be set on the action.
        """
        for act in self:
            act.views = [(view.view_id.id, view.view_mode) for view in act.view_ids]
            got_modes = [view.view_mode for view in act.view_ids]
            all_modes = act.view_mode.split(',')
            missing_modes = [mode for mode in all_modes if mode not in got_modes]
            if missing_modes:
                if act.view_id.type in missing_modes:
                    # reorder missing modes to put view_id first if present
                    missing_modes.remove(act.view_id.type)
                    act.views.append((act.view_id.id, act.view_id.type))
                act.views.extend([(False, mode) for mode in missing_modes])

    @api.depends('res_model', 'search_view_id')
    def _compute_search_view(self):
        for act in self:
            fvg = self.env[act.res_model].fields_view_get(act.search_view_id.id, 'search')
            act.search_view = str(fvg)

    name = fields.Char(string='Action Name', translate=True)
    type = fields.Char(default="ir.actions.act_window")
    view_id = fields.Many2one('ir.ui.view', string='View Ref.', ondelete='set null')
    domain = fields.Char(string='Domain Value',
                         help="Optional domain filtering of the destination data, as a Python expression")
    context = fields.Char(string='Context Value', default={}, required=True,
                          help="Context dictionary as Python expression, empty by default (Default: {})")
    res_id = fields.Integer(string='Record ID', help="Database ID of record to open in form view, when ``view_mode`` is set to 'form' only")
    res_model = fields.Char(string='Destination Model', required=True,
                            help="Model name of the object to open in the view window")
    src_model = fields.Char(string='Source Model',
                            help="Optional model name of the objects on which this action should be visible")
    target = fields.Selection([('current', 'Current Window'), ('new', 'New Window'), ('inline', 'Inline Edit'), ('fullscreen', 'Full Screen'), ('main', 'Main action of Current Window')], default="current", string='Target Window')
    view_mode = fields.Char(required=True, default='tree,form',
                            help="Comma-separated list of allowed view modes, such as 'form', 'tree', 'calendar', etc. (Default: tree,form)")
    view_type = fields.Selection([('tree', 'Tree'), ('form', 'Form')], default="form", string='View Type', required=True,
                                 help="View type: Tree type to use for the tree view, set to 'tree' for a hierarchical tree view, or 'form' for a regular list view")
    usage = fields.Char(string='Action Usage',
                        help="Used to filter menu and home actions from the user form.")
    view_ids = fields.One2many('ir.actions.act_window.view', 'act_window_id', string='Views')
    views = fields.Binary(compute='_compute_views',
                          help="This function field computes the ordered list of views that should be enabled " \
                               "when displaying the result of an action, federating view mode, views and " \
                               "reference view. The result is returned as an ordered list of pairs (view_id,view_mode).")
    limit = fields.Integer(default=80, help='Default limit for the list view')
    groups_id = fields.Many2many('res.groups', 'ir_act_window_group_rel',
                                 'act_id', 'gid', string='Groups')
    search_view_id = fields.Many2one('ir.ui.view', string='Search View Ref.')
    filter = fields.Boolean()
    auto_search = fields.Boolean(default=True)
    search_view = fields.Text(compute='_compute_search_view')
    multi = fields.Boolean(string='Restrict to lists', help="If checked and the action is bound to a model, it will only appear in the More menu on list views")

    @api.multi
    def read(self, fields=None, load='_classic_read'):
        """ call the method get_empty_list_help of the model and set the window action help message
        """
        result = super(IrActionsActWindow, self).read(fields, load=load)
        if not fields or 'help' in fields:
            for values in result:
                model = values.get('res_model')
                if model in self.env:
                    values['help'] = self.env[model].get_empty_list_help(values.get('help', ""))
        return result

    @api.model
    def for_xml_id(self, module, xml_id):
        """ Returns the act_window object created for the provided xml_id

        :param module: the module the act_window originates in
        :param xml_id: the namespace-less id of the action (the @id
                       attribute from the XML file)
        :return: A read() view of the ir.actions.act_window
        """
        record = self.env.ref("%s.%s" % (module, xml_id))
        return record.read()[0]

    @api.model
    def create(self, vals):
        self.clear_caches()
        return super(IrActionsActWindow, self).create(vals)

    @api.multi
    def unlink(self):
        self.clear_caches()
        return super(IrActionsActWindow, self).unlink()

    @api.multi
    def exists(self):
        ids = self._existing()
        existing = self.filtered(lambda rec: rec.id in ids)
        if len(existing) < len(self):
            # mark missing records in cache with a failed value
            exc = MissingError(_("Record does not exist or has been deleted."))
            for record in (self - existing):
                record._cache.set_failed(self._fields, exc)
        return existing

    @api.model
    @tools.ormcache()
    def _existing(self):
        self._cr.execute("SELECT id FROM %s" % self._table)
        return set(row[0] for row in self._cr.fetchall())


VIEW_TYPES = [
    ('tree', 'Tree'),
    ('form', 'Form'),
    ('graph', 'Graph'),
    ('pivot', 'Pivot'),
    ('calendar', 'Calendar'),
    ('gantt', 'Gantt'),
    ('kanban', 'Kanban'),
]

class IrActionsActWindowView(models.Model):
    _name = 'ir.actions.act_window.view'
    _table = 'ir_act_window_view'
    _rec_name = 'view_id'
    _order = 'sequence'

    sequence = fields.Integer()
    view_id = fields.Many2one('ir.ui.view', string='View')
    view_mode = fields.Selection(VIEW_TYPES, string='View Type', required=True)
    act_window_id = fields.Many2one('ir.actions.act_window', string='Action', ondelete='cascade')
    multi = fields.Boolean(string='On Multiple Doc.', help="If set to true, the action will not be displayed on the right toolbar of a form view.")

    @api.model_cr_context
    def _auto_init(self):
        res = super(IrActionsActWindowView, self)._auto_init()
        tools.create_unique_index(self._cr, 'act_window_view_unique_mode_per_action',
                                  self._table, ['act_window_id', 'view_mode'])
        return res


class IrActionsActWindowclose(models.Model):
    _name = 'ir.actions.act_window_close'
    _inherit = 'ir.actions.actions'
    _table = 'ir_actions'

    type = fields.Char(default='ir.actions.act_window_close')


class IrActionsActUrl(models.Model):
    _name = 'ir.actions.act_url'
    _table = 'ir_act_url'
    _inherit = 'ir.actions.actions'
    _sequence = 'ir_actions_id_seq'
    _order = 'name'

    name = fields.Char(string='Action Name', translate=True)
    type = fields.Char(default='ir.actions.act_url')
    url = fields.Text(string='Action URL', required=True)
    target = fields.Selection([('new', 'New Window'), ('self', 'This Window')],
                              string='Action Target', default='new', required=True)


class IrActionsServer(models.Model):
    """ Server actions model. Server action work on a base model and offer various
    type of actions that can be executed automatically, for example using base
    action rules, of manually, by adding the action in the 'More' contextual
    menu.

    Since Odoo 8.0 a button 'Create Menu Action' button is available on the
    action form view. It creates an entry in the More menu of the base model.
    This allows to create server actions and run them in mass mode easily through
    the interface.

    The available actions are :

    - 'Execute Python Code': a block of python code that will be executed
    - 'Run a Client Action': choose a client action to launch
    - 'Create or Copy a new Record': create a new record with new values, or
      copy an existing record in your database
    - 'Write on a Record': update the values of a record
    - 'Execute several actions': define an action that triggers several other
      server actions
    """
    _name = 'ir.actions.server'
    _table = 'ir_act_server'
    _inherit = 'ir.actions.actions'
    _sequence = 'ir_actions_id_seq'
    _order = 'sequence,name'

    DEFAULT_PYTHON_CODE = """# Available variables:
#  - env: Odoo Environment on which the action is triggered
#  - model: Odoo Model of the record on which the action is triggered; is a void recordset
#  - record: record on which the action is triggered; may be be void
#  - records: recordset of all records on which the action is triggered in multi-mode; may be void
#  - time, datetime, dateutil, timezone: useful Python libraries
#  - log: log(message, level='info'): logging function to record debug information in ir.logging table
#  - Warning: Warning Exception to use with raise
# To return an action, assign: action = {...}\n\n\n\n"""

    @api.model
    def _select_objects(self):
        records = self.env['ir.model'].search([])
        return [(record.model, record.name) for record in records] + [('', '')]

    name = fields.Char(string='Action Name', translate=True)
    type = fields.Char(default='ir.actions.server')
    usage = fields.Selection([
        ('ir_actions_server', 'Server Action'),
        ('ir_cron', 'Scheduled Action')], string='Usage',
        default='ir_actions_server', required=True)
    state = fields.Selection([
        ('code', 'Execute Python Code'),
        ('object_create', 'Create a new Record'),
        ('object_write', 'Update the Record'),
        ('multi', 'Execute several actions')], string='Action To Do',
        default='object_write', required=True,
        help="Type of server action. The following values are available:\n"
             "- 'Execute Python Code': a block of python code that will be executed\n"
             "- 'Create or Copy a new Record': create a new record with new values, or copy an existing record in your database\n"
             "- 'Write on a Record': update the values of a record\n"
             "- 'Execute several actions': define an action that triggers several other server actions\n"
             "- 'Add Followers': add followers to a record (available in Discuss)\n"
             "- 'Send Email': automatically send an email (available in email_template)")
    # Generic
    sequence = fields.Integer(default=5,
                              help="When dealing with multiple actions, the execution order is "
                                   "based on the sequence. Low number means high priority.")
    model_id = fields.Many2one('ir.model', string='Model', required=True, ondelete='cascade',
                               help="Model on which the server action runs.")
    model_name = fields.Char(related='model_id.model', readonly=True, store=True)
    # Python code
    code = fields.Text(string='Python Code', groups='base.group_system',
                       default=DEFAULT_PYTHON_CODE,
                       help="Write Python code that the action will execute. Some variables are "
                            "available for use; help about pyhon expression is given in the help tab.")
    # Multi
    child_ids = fields.Many2many('ir.actions.server', 'rel_server_actions', 'server_id', 'action_id',
                                 string='Child Actions', help='Child server actions that will be executed. Note that the last return returned action value will be used as global return value.')
    # Create
    crud_model_id = fields.Many2one('ir.model', string='Create/Write Target Model',
                                    oldname='srcmodel_id', help="Model for record creation / update. Set this field only to specify a different model than the base model.")
    crud_model_name = fields.Char(related='crud_model_id.name', readonly=True)
    link_field_id = fields.Many2one('ir.model.fields', string='Link using field',
                                    help="Provide the field used to link the newly created record"
                                         "on the record on used by the server action.")
    fields_lines = fields.One2many('ir.server.object.lines', 'server_id', string='Value Mapping', copy=True)

    @api.constrains('code')
    def _check_python_code(self):
        for action in self.sudo().filtered('code'):
            msg = test_python_expr(expr=action.code.strip(), mode="exec")
            if msg:
                raise ValidationError(msg)

    @api.constrains('child_ids')
    def _check_recursion(self):
        if not self._check_m2m_recursion('child_ids'):
            raise ValidationError(_('Recursion found in child server actions'))

    @api.onchange('crud_model_id')
    def _onchange_crud_model_id(self):
        self.link_field_id = False
        self.crud_model_name = self.crud_model_id.model

    @api.onchange('model_id')
    def _onchange_model_id(self):
        self.model_name = self.model_id.model

    @api.multi
    def create_action(self):
        """ Create a contextual action for each server action. """
        for action in self:
            action.write({'binding_model_id': action.model_id.id,
                          'binding_type': 'action'})
        return True

    @api.multi
    def unlink_action(self):
        """ Remove the contextual actions created for the server actions. """
        self.check_access_rights('write', raise_exception=True)
        self.filtered('binding_model_id').write({'binding_model_id': False})
        return True

    @api.model
    def run_action_code_multi(self, action, eval_context=None):
        safe_eval(action.sudo().code.strip(), eval_context, mode="exec", nocopy=True)  # nocopy allows to return 'action'
        if 'action' in eval_context:
            return eval_context['action']

    @api.model
    def run_action_multi(self, action, eval_context=None):
        res = False
        for act in action.child_ids:
            result = act.run()
            if result:
                res = result
        return res

    @api.model
    def run_action_object_write(self, action, eval_context=None):
        """ Write server action.

         - 1. evaluate the value mapping
         - 2. depending on the write configuration:

          - `current`: id = active_id
          - `other`: id = from reference object
          - `expression`: id = from expression evaluation
        """
        res = {}
        for exp in action.fields_lines:
            res[exp.col1.name] = exp.eval_value(eval_context=eval_context)[exp.id]

        self.env[action.model_id.model].browse(self._context.get('active_id')).write(res)

    @api.model
    def run_action_object_create(self, action, eval_context=None):
        """ Create and Copy server action.

         - 1. evaluate the value mapping
         - 2. depending on the write configuration:

          - `new`: new record in the base model
          - `copy_current`: copy the current record (id = active_id) + gives custom values
          - `new_other`: new record in target model
          - `copy_other`: copy the current record (id from reference object)
            + gives custom values
        """
        res = {}
        for exp in action.fields_lines:
            res[exp.col1.name] = exp.eval_value(eval_context=eval_context)[exp.id]

        res = self.env[action.crud_model_id.model].create(res)

        if action.link_field_id:
            record = self.env[action.model_id.model].browse(self._context.get('active_id'))
            record.write({action.link_field_id.name: res.id})

    @api.model
    def _get_eval_context(self, action=None):
        """ Prepare the context used when evaluating python code, like the
        python formulas or code server actions.

        :param action: the current server action
        :type action: browse record
        :returns: dict -- evaluation context given to (safe_)safe_eval """
        def log(message, level="info"):
            with self.pool.cursor() as cr:
                cr.execute("""
                    INSERT INTO ir_logging(create_date, create_uid, type, dbname, name, level, message, path, line, func)
                    VALUES (NOW() at time zone 'UTC', %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (self.env.uid, 'server', self._cr.dbname, __name__, level, message, "action", action.id, action.name))

        eval_context = super(IrActionsServer, self)._get_eval_context(action=action)
        model_name = action.model_id.sudo().model
        model = self.env[model_name]
        record = None
        records = None
        if self._context.get('active_model') == model_name and self._context.get('active_id'):
            record = model.browse(self._context['active_id'])
        if self._context.get('active_model') == model_name and self._context.get('active_ids'):
            records = model.browse(self._context['active_ids'])
        if self._context.get('onchange_self'):
            record = self._context['onchange_self']
        eval_context.update({
            # orm
            'env': self.env,
            'model': model,
            # Exceptions
            'Warning': odoo.exceptions.Warning,
            # record
            'record': record,
            'records': records,
            # helpers
            'log': log,
        })
        return eval_context

    @api.multi
    def run(self):
        """ Runs the server action. For each server action, the
        run_action_<STATE> method is called. This allows easy overriding
        of the server actions.

        :param dict context: context should contain following keys

                             - active_id: id of the current object (single mode)
                             - active_model: current model that should equal the action's model

                             The following keys are optional:

                             - active_ids: ids of the current records (mass mode). If active_ids
                               and active_id are present, active_ids is given precedence.

        :return: an action_id to be executed, or False is finished correctly without
                 return action
        """
        res = False
        for action in self:
            eval_context = self._get_eval_context(action)
            if hasattr(self, 'run_action_%s_multi' % action.state):
                # call the multi method
                run_self = self.with_context(eval_context['env'].context)
                func = getattr(run_self, 'run_action_%s_multi' % action.state)
                res = func(action, eval_context=eval_context)

            elif hasattr(self, 'run_action_%s' % action.state):
                active_id = self._context.get('active_id')
                active_ids = self._context.get('active_ids', [active_id] if active_id else [])
                for active_id in active_ids:
                    # run context dedicated to a particular active_id
                    run_self = self.with_context(active_ids=[active_id], active_id=active_id)
                    eval_context["env"].context = run_self._context
                    # call the single method related to the action: run_action_<STATE>
                    func = getattr(run_self, 'run_action_%s' % action.state)
                    res = func(action, eval_context=eval_context)
        return res

    @api.model
    def _run_actions(self, ids):
        """
            Run server actions with given ids.
            Allow crons to run specific server actions
        """
        return self.browse(ids).run()


class IrServerObjectLines(models.Model):
    _name = 'ir.server.object.lines'
    _description = 'Server Action value mapping'
    _sequence = 'ir_actions_id_seq'

    server_id = fields.Many2one('ir.actions.server', string='Related Server Action', ondelete='cascade')
    col1 = fields.Many2one('ir.model.fields', string='Field', required=True)
    value = fields.Text(required=True, help="Expression containing a value specification. \n"
                                            "When Formula type is selected, this field may be a Python expression "
                                            " that can use the same values as for the code field on the server action.\n"
                                            "If Value type is selected, the value will be used directly without evaluation.")
    type = fields.Selection([('value', 'Value'), ('equation', 'Python expression')], 'Evaluation Type', default='value', required=True, change_default=True)

    @api.multi
    def eval_value(self, eval_context=None):
        result = dict.fromkeys(self.ids, False)
        for line in self:
            expr = line.value
            if line.type == 'equation':
                expr = safe_eval(line.value, eval_context)
            elif line.col1.ttype in ['many2one', 'integer']:
                try:
                    expr = int(line.value)
                except Exception:
                    pass
            result[line.id] = expr
        return result


class IrActionsTodo(models.Model):
    """
    Configuration Wizards
    """
    _name = 'ir.actions.todo'
    _description = "Configuration Wizards"
    _order = "sequence, id"

    action_id = fields.Many2one('ir.actions.actions', string='Action', required=True, index=True)
    sequence = fields.Integer(default=10)
    state = fields.Selection([('open', 'To Do'), ('done', 'Done')], string='Status', default='open', required=True)
    name = fields.Char()

    @api.model
    def create(self, vals):
        todo = super(IrActionsTodo, self).create(vals)
        if todo.state == "open":
            todo.ensure_one_open_todo()
        return todo

    def write(self, vals):
        res = super(IrActionsTodo, self).write(vals)
        if vals.get('state', '') == 'open':
            for todo in self:
                todo.ensure_one_open_todo()
        return res

    def ensure_one_open_todo(self):
        open_todo = self.search(['&', ('state', '=', 'open'), ('id', '!=', self.id)])
        if open_todo:
            open_todo.write({'state': 'done'})

    @api.multi
    def name_get(self):
        return [(record.id, record.action_id.name) for record in self]

    @api.multi
    def unlink(self):
        if self:
            try:
                todo_open_menu = self.env.ref('base.open_menu')
                # don't remove base.open_menu todo but set its original action
                if todo_open_menu in self:
                    todo_open_menu.action_id = self.env.ref('base.action_client_base_menu').id
                    self -= todo_open_menu
            except ValueError:
                pass
        return super(IrActionsTodo, self).unlink()

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        if name:
            actions = self.search([('action_id', operator, name)] + args, limit=limit)
            return actions.name_get()
        return super(IrActionsTodo, self).name_search(name, args=args, operator=operator, limit=limit)

    @api.multi
    def action_launch(self, context=None):
        """ Launch Action of Wizard"""
        self.ensure_one()

        self.write({'state': 'done'})

        # Load action
        action = self.env[self.action_id.type].browse(self.action_id.id)

        result = action.read()[0]
        if action._name != 'ir.actions.act_window':
            return result
        result.setdefault('context', '{}')

        # Open a specific record when res_id is provided in the context
        ctx = safe_eval(result['context'], {'user': self.env.user})
        if ctx.get('res_id'):
            result['res_id'] = ctx.pop('res_id')

        # disable log for automatic wizards
        ctx['disable_log'] = True

        result['context'] = ctx

        return result

    @api.multi
    def action_open(self):
        """ Sets configuration wizard in TODO state"""
        return self.write({'state': 'open'})


class IrActionsActClient(models.Model):
    _name = 'ir.actions.client'
    _inherit = 'ir.actions.actions'
    _table = 'ir_act_client'
    _sequence = 'ir_actions_id_seq'
    _order = 'name'

    name = fields.Char(string='Action Name', translate=True)
    type = fields.Char(default='ir.actions.client')

    tag = fields.Char(string='Client action tag', required=True,
                      help="An arbitrary string, interpreted by the client"
                           " according to its own needs and wishes. There "
                           "is no central tag repository across clients.")
    target = fields.Selection([('current', 'Current Window'), ('new', 'New Window'), ('fullscreen', 'Full Screen'), ('main', 'Main action of Current Window')], default="current", string='Target Window')
    res_model = fields.Char(string='Destination Model', help="Optional model, mostly used for needactions.")
    context = fields.Char(string='Context Value', default="{}", required=True, help="Context dictionary as Python expression, empty by default (Default: {})")
    params = fields.Binary(compute='_compute_params', inverse='_inverse_params', string='Supplementary arguments',
                           help="Arguments sent to the client along with"
                                "the view tag")
    params_store = fields.Binary(string='Params storage', readonly=True)

    @api.depends('params_store')
    def _compute_params(self):
        self_bin = self.with_context(bin_size=False, bin_size_params_store=False)
        for record, record_bin in pycompat.izip(self, self_bin):
            record.params = record_bin.params_store and safe_eval(record_bin.params_store, {'uid': self._uid})

    def _inverse_params(self):
        for record in self:
            params = record.params
            record.params_store = repr(params) if isinstance(params, dict) else params
