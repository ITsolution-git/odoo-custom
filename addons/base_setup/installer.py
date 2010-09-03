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
from osv import fields, osv
import netsvc

class base_setup_installer(osv.osv_memory):
    _name = 'base.setup.installer'
    _inherit = 'res.config.installer'

    _install_if = {
        ('sale','crm'): ['sale_crm'],
        ('sale','project'): ['project_mrp'],
        ('sale',):['account_accountant']
        }
    _columns = {
        # Generic modules
        'crm':fields.boolean('Customer Relationship Management',
            help="Helps you track and manage relations with customers such as"
                 " leads, requests or issues. Can automatically send "
                 "reminders, escalate requests or trigger business-specific "
                 "actions based on standard events."),
        'sale':fields.boolean('Sales Management',
            help="Helps you handle your quotations, sale orders and invoicing"
                 "."),
        'project':fields.boolean('Project Management',
            help="Helps you manage your projects and tasks by tracking them, "
                 "generating plannings, etc..."),
        'knowledge':fields.boolean('Knowledge Management',
            help="Lets you install addons geared towards sharing knowledge "
                 "with and between your employees."),
        'stock':fields.boolean('Warehouse Management',
            help="Helps you manage your stocks and stocks locations, as well "
                 "as the flow of stock between warehouses."),
        'mrp':fields.boolean('Manufacturing',
            help="Helps you manage your manufacturing processes and generate "
                 "reports on those processes."),
        'account':fields.boolean('Financial & Accounting',
            help="Helps you handle your accounting needs, as well as create "
                 "and track your budgets."),
        'purchase':fields.boolean('Purchase Management',
            help="Helps you manage your purchase-related processes such as "
                 "requests for quotations, supplier invoices, etc..."),
        'hr':fields.boolean('Human Resources',
            help="Helps you manage your human resources by encoding your employees structure, generating work sheets, tracking attendance and more"),
        'point_of_sale':fields.boolean('Point of Sales',
            help="Helps you get the most out of your points of sales with "
                 "fast sale encoding, simplified payment mode encoding, "
                 "automatic picking lists generation and more."),
        'marketing':fields.boolean('Marketing',
            help="Helps you manage your marketing campaigns step by step."),
        'profile_tools':fields.boolean('Miscellaneous Tools',
            help="Lets you install various interesting but non-essential tools "
                "like Survey, Lunch and Ideas box."),
        'report_designer':fields.boolean('Advanced Reporting',
            help="Lets you install various tools to simplify and enhance "
                 "OpenERP's report creation."),
        'thunderbird' :fields.boolean('Thunderbird'),
        # Vertical modules
        'product_expiry':fields.boolean('Food Industry',
            help="Installs a preselected set of OpenERP applications "
                "which will help you manage your industry"),
        'association':fields.boolean('Associations',
            help="Installs a preselected set of OpenERP "
                 "applications which will help you manage your association "
                 "more efficiently."),
        'auction':fields.boolean('Auction Houses',
            help="Installs a preselected set of OpenERP "
                 "applications selected to help you manage your auctions "
                 "as well as the business processes around them."),
        }
    _defaults = {
        'crm': True,
        }

    def _if_mrp(self, cr, uid, ids, context=None):
        if self.pool.get('res.users').browse(cr, uid, uid, context=context)\
               .view == 'simple':
            return ['mrp_jit']
        return None

    def _if_knowledge(self, cr, uid, ids, context=None):
        if self.pool.get('res.users').browse(cr, uid, uid, context=context)\
               .view == 'simple':
            return ['document_ftp']
        return None

    def onchange_moduleselection(self, cr, uid, ids, *args):
        closed, total = self.get_current_progress(cr, uid)

        progress = round(100. * closed / (total + len(filter(None, args))))
        if progress < 10.:
            progress = 10.
        return {'value':{'progress':progress}}
base_setup_installer()
