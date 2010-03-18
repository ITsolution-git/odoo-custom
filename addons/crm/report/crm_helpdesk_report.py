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

from osv import fields,osv
import tools


class crm_helpdesk_report(osv.osv):
    """ Helpdesk report after Sales Services """

    _name = "crm.helpdesk.report"
    _description = "Helpdesk report after Sales Services"
    _auto = False
    _inherit = "crm.case.report"

    _columns = {
        'delay_close': fields.char('Delay to close', size=20, readonly=True),
        'partner_id': fields.many2one('res.partner', 'Partner' , readonly=True),
        'company_id': fields.many2one('res.company', 'Company', readonly=True),
        'date_deadline': fields.date('Deadline'),
        'priority': fields.selection([('5', 'Lowest'), ('4', 'Low'), \
                    ('3', 'Normal'), ('2', 'High'), ('1', 'Highest')], 'Priority'),
    }

    def init(self, cr):

        """@param cr: the current row, from the database cursor
           Display Deadline ,Responsible user, partner ,Department """

        tools.drop_view_if_exists(cr, 'crm_helpdesk_report')
        cr.execute("""
            create or replace view crm_helpdesk_report as (
                select
                    min(c.id) as id,
                    to_char(c.create_date, 'YYYY') as name,
                    to_char(c.create_date, 'MM') as month,
                    c.state,
                    c.user_id,
                    c.section_id,
                    c.partner_id,
                    c.company_id,
                    c.priority,
                    c.date_deadline,
                    count(*) as nbr,
                    0 as avg_answers,
                    0.0 as perc_done,
                    0.0 as perc_cancel,
                    to_char(avg(date_closed-c.create_date), 'DD"d" HH24:MI:SS') as delay_close
                from
                    crm_helpdesk c
                group by to_char(c.create_date, 'YYYY'), to_char(c.create_date, 'MM'),\
                     c.state, c.user_id,c.section_id,c.priority,\
                      c.partner_id,c.company_id,c.date_deadline
            )""")

crm_helpdesk_report()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
