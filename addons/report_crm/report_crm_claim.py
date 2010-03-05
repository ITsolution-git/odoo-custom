from osv import fields,osv
import tools

class report_crm_claim(osv.osv):
    _name = "report.crm.claim"
    _auto = False
    _inherit = "report.crm.case"
    _columns = {
        'delay_close': fields.char('Delay to close', size=20, readonly=True),
        'stage_id': fields.many2one ('crm.case.stage', 'Stage', domain="[('section_id','=',section_id),('object_id.model', '=', 'crm.claim')]", readonly=True),
        'categ_id': fields.many2one('crm.case.categ', 'Category', domain="[('section_id','=',section_id),('object_id.model', '=', 'crm.claim')]"),
        'partner_id': fields.many2one('res.partner', 'Partner'), 
        'company_id': fields.many2one('res.company','Company'),  
    }
    def init(self, cr):
        tools.drop_view_if_exists(cr, 'report_crm_claim')
        cr.execute("""
            create or replace view report_crm_claim as (
                select
                    min(c.id) as id,
                    to_char(c.create_date, 'YYYY') as name,
                    to_char(c.create_date, 'MM') as month,
                    c.state,
                    c.user_id,
                    c.stage_id,
                    c.section_id,
                    c.partner_id,
                    c.company_id,
                    c.categ_id,
                    count(*) as nbr,
                    0 as avg_answers,
                    0.0 as perc_done,
                    0.0 as perc_cancel,
                    to_char(avg(date_closed-c.create_date), 'DD"d" HH24:MI:SS') as delay_close
                from
                    crm_claim c
                group by to_char(c.create_date, 'YYYY'), to_char(c.create_date, 'MM'), c.state, c.user_id,c.section_id, c.stage_id,c.categ_id,c.partner_id,c.company_id
            )""")
report_crm_claim()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
