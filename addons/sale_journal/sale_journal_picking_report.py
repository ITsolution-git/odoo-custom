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

class report_sale_journal_invoice_type_stats(osv.osv):
    _name = "sale_journal.invoice.type.stats"
    _description = "Stats on picking by invoice method"
    _auto = False
    _columns = {
        'name': fields.char('Year',size=64,required=False, readonly=True),
        'invoice_state':fields.selection([
            ("invoiced","invoiced"),
            ("2binvoiced","to be invoiced"),
            ("none","None")
        ], "Invoice state", readonly=True),
        'state': fields.selection([
            ('draft','draft'),
            ('auto','waiting'),
            ('confirmed','confirmed'),
            ('assigned','assigned'),
            ('done','done'),
            ('cancel','cancel'),
        ], 'State', readonly=True),
        'invoice_type_id':fields.many2one('sale_journal.invoice.type', 'Invoicing method', readonly=True),
        'quantity': fields.float('Quantities', readonly=True),
        'price_total': fields.float('Total Price', readonly=True),
        'price_average': fields.float('Average Price', readonly=True),
        'count': fields.integer('# of Lines', readonly=True),
        'month':fields.selection([('01','January'), ('02','February'), ('03','March'), ('04','April'), ('05','May'), ('06','June'),
                          ('07','July'), ('08','August'), ('09','September'), ('10','October'), ('11','November'), ('12','December')],'Month',readonly=True),

    }
    _order = 'state,invoice_state,name desc'
    def init(self, cr):
        tools.drop_view_if_exists(cr, 'sale_journal_invoice_type_stats')
        cr.execute("""
            create or replace view sale_journal_invoice_type_stats as (
                select
                    min(l.id) as id,
                    to_char(s.date, 'YYYY') as name,
                    to_char(s.date, 'MM') as month,
                    s.state,
                    s.invoice_state,
                    s.invoice_type_id,
                    sum(l.product_qty) as quantity,
                    count(*) as count,
                    sum(l.product_qty*ol.price_unit*(1.0-ol.discount/100.0)) as price_total,
                    (sum(l.product_qty*ol.price_unit*(1.0-ol.discount/100.0))/sum(l.product_qty))::decimal(16,2) as price_average
                from stock_picking s
                    left join stock_move l on (s.id=l.picking_id)
                    left join sale_order_line ol on (l.sale_line_id=ol.id)
                group by s.invoice_type_id, to_char(s.date, 'YYYY'),to_char(s.date, 'MM'),s.state, s.invoice_state
                order by s.invoice_type_id, s.invoice_state, s.state
            )
        """)
report_sale_journal_invoice_type_stats()

class report_sale_journal_picking(osv.osv):
    _name = "sale_journal.picking.stats"
    _description = "Picking lists by Journal"
    _auto = False
    _columns = {
        'name': fields.char('Year',size=64,required=False, readonly=True),
        'state': fields.selection([
            ('draft','draft'),
            ('auto','waiting'),
            ('confirmed','confirmed'),
            ('assigned','assigned'),
            ('done','done'),
            ('cancel','cancel'),
        ], 'State', readonly=True),
        'journal_id':fields.many2one('sale_journal.picking.journal', 'Journal', readonly=True),
        'quantity': fields.float('Quantities', readonly=True),
        'price_total': fields.float('Total Price', readonly=True),
        'price_average': fields.float('Average Price', readonly=True),
        'count': fields.integer('# of Lines', readonly=True),
        'month':fields.selection([('01','January'), ('02','February'), ('03','March'), ('04','April'), ('05','May'), ('06','June'),
                          ('07','July'), ('08','August'), ('09','September'), ('10','October'), ('11','November'), ('12','December')],'Month',readonly=True),

    }
    _order = 'journal_id,name desc,price_total desc'
    def init(self, cr):
        tools.drop_view_if_exists(cr, 'sale_journal_picking_stats')
        cr.execute("""
            create or replace view sale_journal_picking_stats as (
                select
                    min(l.id) as id,
                    to_char(s.date, 'YYYY') as name,
                    to_char(s.date, 'MM') as month,
                    s.state,
                    s.journal_id,
                    sum(l.product_qty) as quantity,
                    count(*) as count,
                    sum(l.product_qty*ol.price_unit*(1.0-ol.discount/100.0)) as price_total,
                    (sum(l.product_qty*ol.price_unit*(1.0-ol.discount/100.0))/sum(l.product_qty))::decimal(16,2) as price_average
                from stock_picking s
                    right join stock_move l on (s.id=l.picking_id)
                    right join sale_order_line ol on (l.sale_line_id=ol.id)
                group by s.journal_id, to_char(s.date, 'YYYY'),to_char(s.date, 'MM'),s.state
            )
        """)
report_sale_journal_picking()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

