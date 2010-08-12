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

import tools
from osv import fields,osv

class account_invoice_report(osv.osv):
    _name = "account.invoice.report"
    _description = "Invoices Statistics"
    _auto = False
    _rec_name = 'date'
    _columns = {
        'date': fields.date('Date', readonly=True),
        'year': fields.char('Year', size=4, readonly=True),
        'day': fields.char('Day', size=128, readonly=True),
        'month':fields.selection([('01','January'), ('02','February'), ('03','March'), ('04','April'),
            ('05','May'), ('06','June'), ('07','July'), ('08','August'), ('09','September'),
            ('10','October'), ('11','November'), ('12','December')], 'Month', readonly=True),
        'product_id':fields.many2one('product.product', 'Product', readonly=True),
        'product_qty':fields.float('Qty', readonly=True),
        'uom_name': fields.char('Default UoM', size=128, readonly=True),
        'payment_term': fields.many2one('account.payment.term', 'Payment Term', readonly=True),
        'period_id': fields.many2one('account.period', 'Force Period', domain=[('state','<>','done')], readonly=True),
        'fiscal_position': fields.many2one('account.fiscal.position', 'Fiscal Position', readonly=True),
        'currency_id': fields.many2one('res.currency', 'Currency', readonly=True),
        'categ_id': fields.many2one('product.category','Category of Product', readonly=True),
        'journal_id': fields.many2one('account.journal', 'Journal', readonly=True),
        'partner_id':fields.many2one('res.partner', 'Partner', readonly=True),
        'company_id':fields.many2one('res.company', 'Company', readonly=True),
        'user_id':fields.many2one('res.users', 'Salesman', readonly=True),
        'price_total':fields.float('Total Price', readonly=True),
        'price_average':fields.float('Average Price', readonly=True),
        'nbr':fields.integer('# of Lines', readonly=True),
        'reconciled':fields.integer('# reconciled lines', readonly=True),
        'type': fields.selection([
            ('out_invoice','Customer Invoice'),
            ('in_invoice','Supplier Invoice'),
            ('out_refund','Customer Refund'),
            ('in_refund','Supplier Refund'),
            ],'Type', readonly=True),
        'state': fields.selection([
            ('draft','Draft'),
            ('proforma','Pro-forma'),
            ('proforma2','Pro-forma'),
            ('open','Open'),
            ('paid','Done'),
            ('cancel','Cancelled')
            ], 'Invoice State', readonly=True),
        'date_due': fields.date('Due Date', readonly=True),
        'address_contact_id': fields.many2one('res.partner.address', 'Contact Address Name', readonly=True),
        'address_invoice_id': fields.many2one('res.partner.address', 'Invoice Address Name', readonly=True),
        'account_id': fields.many2one('account.account', 'Account',readonly=True),
        'partner_bank_id': fields.many2one('res.partner.bank', 'Bank Account',readonly=True),
        'residual':fields.float('Total Residual', readonly=True),
        'delay_to_pay':fields.float('Avg. Delay To Pay', readonly=True, group_operator="avg"),
    }
    _order = 'date desc'
    def init(self, cr):
        tools.drop_view_if_exists(cr, 'account_invoice_report')
        cr.execute("""
            create or replace view account_invoice_report as (
                 select min(ail.id) as id,
                    ai.date_invoice as date,
                    to_char(ai.date_invoice, 'YYYY') as year,
                    to_char(ai.date_invoice, 'MM') as month,
                    to_char(ai.date_invoice, 'YYYY-MM-DD') as day,
                    ail.product_id,
                    ai.partner_id as partner_id,
                    ai.reconciled::integer,
                    ai.payment_term as payment_term,
                    ai.period_id as period_id,
                    u.name as uom_name,
                    ai.currency_id as currency_id,
                    ai.journal_id as journal_id,
                    ai.fiscal_position as fiscal_position,
                    ai.user_id as user_id,
                    ai.company_id as company_id,
                    count(ail.*) as nbr,
                    ai.type as type,
                    ai.state,
                    pt.categ_id,
                    ai.date_due as date_due,
                    ai.address_contact_id as address_contact_id,
                    ai.address_invoice_id as address_invoice_id,
                    ai.account_id as account_id,
                    ai.partner_bank_id as partner_bank_id,
                    sum(case when ai.type in ('out_refund','in_invoice') then
                         ail.quantity * u.factor * -1
                        else
                         ail.quantity * u.factor
                        end) as product_qty,
                    sum(case when ai.type in ('out_refund','in_invoice') then
                         ail.quantity*ail.price_unit * -1
                        else
                         ail.quantity*ail.price_unit
                        end) as price_total,
                    sum(ail.quantity*ail.price_unit)/sum(ail.quantity*u.factor)*count(ail.product_id)::decimal(16,2) as price_average,
                    sum((select extract(epoch from avg(date_trunc('day',aml.date_created)-date_trunc('day',l.create_date)))/(24*60*60)::decimal(16,2)
                        from account_move_line as aml
                        left join account_invoice as a ON (a.move_id=aml.move_id)
                        left join account_invoice_line as l ON (a.id=l.invoice_id)
                        where a.id=ai.id)) as delay_to_pay,
                    (case when ai.type in ('out_refund','in_invoice') then
                      ai.residual * -1
                    else
                      ai.residual
                    end)/(select count(l.*) from account_invoice_line as l
                            left join account_invoice as a ON (a.id=l.invoice_id)
                            where a.id=ai.id) as residual
                from account_invoice_line as ail
                left join account_invoice as ai ON (ai.id=ail.invoice_id)
                left join product_template pt on (pt.id=ail.product_id)
                left join product_uom u on (u.id=ail.uos_id)
                group by ail.product_id,
                    ai.date_invoice,
                    ai.id,
                    to_char(ai.date_invoice, 'YYYY'),
                    to_char(ai.date_invoice, 'MM'),
                    to_char(ai.date_invoice, 'YYYY-MM-DD'),
                    ai.partner_id,
                    ai.reconciled,
                    ai.payment_term,
                    ai.period_id,
                    u.name,
                    ai.currency_id,
                    ai.journal_id,
                    ai.fiscal_position,
                    ai.user_id,
                    ai.company_id,
                    ai.type,
                    ai.state,
                    pt.categ_id,
                    ai.date_due,
                    ai.address_contact_id,
                    ai.address_invoice_id,
                    ai.account_id,
                    ai.partner_bank_id,
                    ai.residual
            )
        """)
account_invoice_report()
