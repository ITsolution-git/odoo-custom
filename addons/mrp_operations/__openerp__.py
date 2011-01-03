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


{
    'name': 'Work Center Production start end workflow',
    'version': '1.0',
    'category': 'Generic Modules/Production',
    'description': """
     This module adds state, date_start,date_stop in production order operation lines
     (in the "Work Centers" tab)
     State: draft, confirm, done, cancel
     When finishing/confirming,cancelling production orders set all state lines to the according state
     Create menus:
         Production Management > All Operations
         Production Management > All Operations > Operations To Do (state="confirm")
     Which is a view on "Work Centers" lines in production order,
     editable tree

    Add buttons in the form view of production order under workcenter tab:
    * start (set state to confirm), set date_start
    * done (set state to done), set date_stop
    * set to draft (set state to draft)
    * cancel set state to cancel

    When the production order becomes "ready to produce", operations must
    become 'confirmed'. When the production order is done, all operations
    must become done.

    The field delay is the delay(stop date - start date).
    So that we can compare the theoretic delay and real delay.

    """,
    'author': 'OpenERP SA',
    'website': 'http://www.openerp.com',
    'depends': ['mrp'],
    'init_xml': [],
    'update_xml': [
        'security/ir.model.access.csv',
        'mrp_operations_workflow.xml',
        'mrp_operations_view.xml',
        'mrp_operations_report.xml',
        'report/mrp_workorder_analysis_view.xml',
        'process/mrp_operation_process.xml'
    ],
    'demo_xml': ['mrp_operation_data.xml'],
    'test': ['test/mrp_operations.yml', 'test/mrp_operations_report.yml'],
    'installable': True,
    'active': False,
    'certificate': '0056233813133',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
