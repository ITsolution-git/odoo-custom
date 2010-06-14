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
import tools

class report_event_registration(osv.osv):
    
    _name = "report.event.registration"
    _description = "Events on registrations and Events on type"
    _auto = False
    _rec_name = 'date'
    _columns = {
        'date': fields.date('Date', readonly=True),
        'year': fields.char('Year', size=4, readonly=True),
        'month':fields.selection([('01','January'), ('02','February'), ('03','March'), ('04','April'),
            ('05','May'), ('06','June'), ('07','July'), ('08','August'), ('09','September'),
            ('10','October'), ('11','November'), ('12','December')], 'Month',readonly=True),
        'day': fields.char('Day', size=128, readonly=True),        
        'event_id': fields.many2one('event.event', 'Event Related', required=True), 
        'draft_state': fields.integer(' # No of draft Registration.', size=20), 
        'confirm_state': fields.integer(' # No of Confirm Registration', size=20), 
        'register_max': fields.integer('Maximum Registrations'), 
        'nbevent': fields.integer('Number Of Events'), 
        'type': fields.many2one('event.type', 'Event Type'),
        'state': fields.selection([('draft', 'Draft'), ('confirm', 'Confirmed'), ('done', 'Done'), ('cancel', 'Cancelled')], 'State', readonly=True, required=True),
        'user_id':fields.many2one('res.users', 'Responsible', readonly=True),
    }
    _order = 'date desc'
    def init(self, cr):
        """
        initialize the sql view for the event registration
        cr -- the cursor
        """
        cr.execute("""
         create or replace view report_event_registration as (
                select
                e.id as id,
                c.event_id as event_id,
                e.date_begin as date,
                e.user_id as user_id,
                to_char(e.date_begin, 'YYYY') as year,
                to_char(e.date_begin, 'MM') as month,
                to_char(e.date_begin, 'YYYY-MM-DD') as day,
                count(t.id) as nbevent,
                t.id as type,
                (SELECT sum(c.nb_register) FROM event_registration  c  WHERE c.event_id=e.id and t.id=e.type and state in ('draft')) as draft_state,
                (SELECT sum(c.nb_register) FROM event_registration  c  WHERE c.event_id=e.id and t.id=e.type and state in ('open')) as confirm_state,
                e.register_max as register_max,
                e.state as state
                from
                event_event e
                inner join
                    event_registration c on (e.id=c.event_id)
                inner join
                    event_type t on (e.type=t.id)
               group by
                    to_char(e.date_begin, 'YYYY'),
                    to_char(e.date_begin, 'MM'),
                    t.id, e.id, e.date_begin,
                    e.register_max, e.type, e.state, c.event_id, e.user_id,
                    to_char(e.date_begin, 'YYYY-MM-DD')
                )""")

report_event_registration()
