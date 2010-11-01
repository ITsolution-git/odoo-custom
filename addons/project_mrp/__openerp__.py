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
    'name': 'Procurement and Project Management integration',
    'version': '1.0',
    'category': 'Generic Modules/Projects & Services',
    'description': """
This module creates a link between procurement orders
containing "service" lines and project management tasks.

When installed, this module will automatically create a new task
for each procurement order line, when the corresponding product
meets the following characteristics:
  * Type = Service
  * Procurement method (Order fulfillment) = MTO (make to order)
  * Supply/Procurement method = Produce

The new task is created outside of any existing project, but
can be added to a project manually.

When the project task is completed or cancelled, the workflow of the corresponding
procurement line is updated accordingly.

This module is useful to be able to invoice services based on tasks
automatically created via sale orders.

""",
    'author': 'OpenERP SA',
    'website': 'http://www.openerp.com',
    'depends': ['project', 'procurement', 'sale', 'mrp_jit'],
    'init_xml': [],
    'update_xml': ['project_mrp_workflow.xml', 'process/project_mrp_process.xml', 'project_mrp_view.xml'],
    'demo_xml': [],
    'test': ['test/project_task_procurement.yml'],
    'installable': True,
    'active': False,
    'certificate': '0031976495453',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
