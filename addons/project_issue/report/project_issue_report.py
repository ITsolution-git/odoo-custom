from osv import fields,osv
import tools
from crm import crm

AVAILABLE_STATES = [
    ('draft','Draft'),
    ('open','Open'),
    ('cancel', 'Cancelled'),
    ('done', 'Closed'),
    ('pending','Pending')
]
class project_issue_report(osv.osv):
    _name = "project.issue.report"
    _auto = False

    def _get_data(self, cr, uid, ids, field_name, arg, context=None):
        if context is None:
            context = {}
        """ @param cr: the current row, from the database cursor,
            @param uid: the current users ID for security checks,
            @param ids: List of case and section Datas IDs
            @param context: A standard dictionary for contextual values """

        res = {}
        avg_ans = 0.0

        for case in self.browse(cr, uid, ids, context):
            if field_name != 'avg_answers':
                state = field_name[5:]
                cr.execute("select count(*) from crm_opportunity where \
                    section_id =%s and state='%s'"%(case.section_id.id, state))
                state_cases = cr.fetchone()[0]
                perc_state = (state_cases / float(case.nbr)) * 100

                res[case.id] = perc_state
            else:
                model_name = self._name.split('report.')
                if len(model_name) < 2:
                    res[case.id] = 0.0
                else:
                    model_name = model_name[1]

                    cr.execute("select count(*) from crm_case_log l, ir_model m \
                         where l.model_id=m.id and m.model = '%s'" , model_name)
                    logs = cr.fetchone()[0]

                    avg_ans = logs / case.nbr
                    res[case.id] = avg_ans

        return res

    _columns = {
        'name': fields.char('Year', size=64, required=False, readonly=True),
        'user_id':fields.many2one('res.users', 'Responsible', readonly=True),
        'user_id2':fields.many2one('res.users', 'Assigned To', readonly=True),
        'section_id':fields.many2one('crm.case.section', 'Section', readonly=True),
        'state': fields.selection(AVAILABLE_STATES, 'State', size=16, readonly=True),
        'avg_answers': fields.function(_get_data, string='Avg. Answers', method=True, type="integer"),
        'perc_done': fields.function(_get_data, string='%Done', method=True, type="float"),
        'perc_cancel': fields.function(_get_data, string='%Cancel', method=True, type="float"),
        'month':fields.selection([('01', 'January'), ('02', 'February'), \
                                  ('03', 'March'), ('04', 'April'),\
                                  ('05', 'May'), ('06', 'June'), \
                                  ('07', 'July'), ('08', 'August'),\
                                  ('09', 'September'), ('10', 'October'),\
                                  ('11', 'November'), ('12', 'December')], 'Month', readonly=True),
        'company_id': fields.many2one('res.company', 'Company', readonly=True),
        'day': fields.char('Day', size=128, readonly=True),
        'opening_date': fields.date('Opening Date', readonly=True),
        'creation_date': fields.date('Creation Date', readonly=True),
        'date_closed': fields.date('Closed Date', readonly=True),
        'categ_id': fields.many2one('crm.case.categ', 'Category', domain="[('section_id','=',section_id),('object_id.model', '=', 'project.issue')]"),
        'stage_id': fields.many2one ('crm.case.stage', 'Stage', domain="[('object_id.model', '=', 'project.issue')]"),
        'nbr': fields.integer('# of Issues', readonly=True),
        'working_hours_open': fields.float('# Working Open Hours', readonly=True),
        'working_hours_close': fields.float('# Working Closing Hours', readonly=True),
        'delay_open': fields.float('Avg opening Delay', digits=(16,2), readonly=True, group_operator="avg",
                                       help="Number of Days to close the project issue"),
        'delay_close': fields.float('Avg Closing Delay', digits=(16,2), readonly=True, group_operator="avg",
                                       help="Number of Days to close the project issue"),
        'company_id' : fields.many2one('res.company', 'Company'),
        'priority': fields.selection(crm.AVAILABLE_PRIORITIES, 'Priority'),
        'project_id':fields.many2one('project.project', 'Project',readonly=True),
        'type_id': fields.many2one('crm.case.resource.type', 'Version', domain="[('object_id.model', '=', 'project.issue')]"),
        'user_id2losed': fields.date('Close Date', readonly=True),
        'assigned_to' : fields.many2one('res.users', 'Assigned to',readonly=True),
        'partner_id': fields.many2one('res.partner','Partner',domain="[('object_id.model', '=', 'project.issue')]"),
        'canal_id': fields.many2one('res.partner.canal', 'Channel',readonly=True),
        'task_id': fields.many2one('project.task', 'Task',domain="[('object_id.model', '=', 'project.issue')]" ),
        'email': fields.integer('# Emails', size=128, readonly=True),
    }

    def init(self, cr):
        tools.drop_view_if_exists(cr, 'project_issue_report')
        cr.execute("""
            CREATE OR REPLACE VIEW project_issue_report AS (
                SELECT
                    c.id as id,
                    to_char(c.create_date, 'YYYY') as name,
                    to_char(c.create_date, 'MM') as month,
                    to_char(c.create_date, 'YYYY-MM-DD') as day,
                    to_char(c.date_open, 'YYYY-MM-DD') as opening_date,
                    to_char(c.create_date, 'YYYY-MM-DD') as creation_date,
                    c.state,
                    c.user_id,
                    c.working_hours_open,
                    c.working_hours_close,
                    c.section_id,
                    c.categ_id,
                    c.stage_id,
                    to_char(c.date_closed, 'YYYY-mm-dd') as date_closed,
                    c.company_id as company_id,
                    c.priority as priority,
                    c.project_id as project_id,
                    c.type_id as type_id,
                    1 as nbr,
                    c.assigned_to,
                    c.partner_id,
                    c.canal_id,
                    c.task_id,
                    date_trunc('day',c.create_date) as create_date,
                    extract('epoch' from (c.date_open-c.create_date))/(3600*24) as  delay_open,
                    extract('epoch' from (c.date_closed-c.create_date))/(3600*24) as  delay_close,
                    (SELECT count(id) FROM mailgate_message WHERE model='project.issue' AND res_id=c.id) AS email
                FROM
                    project_issue c
                WHERE c.categ_id IN (select res_id from ir_model_data WHERE model = 'crm.case.categ' and name='bug_categ')
            )""")
project_issue_report()



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
