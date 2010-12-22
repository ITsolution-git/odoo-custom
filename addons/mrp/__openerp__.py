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
    "name" : "Manufacturing Resource Planning",
    "version" : "1.1",
    "author" : "OpenERP SA",
    "website" : "http://www.openerp.com",
    "category" : "Generic Modules/Production",
    "depends" : ["procurement", "stock", "resource", "purchase", "product","process"],
    "description": """
    This is the base module to manage the manufacturing process in OpenERP.

    Features:
    * Make to Stock / Make to Order (by line)
    * Multi-level BoMs, no limit
    * Multi-level routing, no limit
    * Routing and work center integrated with analytic accounting
    * Scheduler computation periodically / Just In Time module
    * Multi-pos, multi-warehouse
    * Different reordering policies
    * Cost method by product: standard price, average price
    * Easy analysis of troubles or needs
    * Very flexible
    * Allows to browse Bill of Materials in complete structure
        that include child and phantom BoMs
    It supports complete integration and planification of stockable goods,
    consumable of services. Services are completely integrated with the rest
    of the software. For instance, you can set up a sub-contracting service
    in a BoM to automatically purchase on order the assembly of your production.

    Reports provided by this module:
    * Bill of Material structure and components
    * Load forecast on workcenters
    * Print a production order
    * Stock forecasts
    Dashboard provided by this module::
    * List of next production orders
    * List of deliveries (out picking)
    * Graph of work center load
    * List of procurement in exception
    """,
    'init_xml': [],
    'update_xml': [
        'security/mrp_security.xml',
        'security/ir.model.access.csv',
        'mrp_workflow.xml',
        'mrp_data.xml',
        'wizard/mrp_product_produce_view.xml',
        'wizard/change_production_qty_view.xml',
        'wizard/mrp_price_view.xml',
        'wizard/mrp_workcenter_load_view.xml',
        'wizard/mrp_change_standard_price_view.xml',
        'mrp_view.xml',
        'mrp_report.xml',
        'company_view.xml',
        'process/stockable_product_process.xml',
        'process/service_product_process.xml',
        'process/procurement_process.xml',
        'mrp_installer.xml',
        'report/mrp_report_view.xml',
        'report/mrp_production_order_view.xml',
        'board_manufacturing_view.xml',


    ],
    'demo_xml': [
         'mrp_demo.xml',
    ],
    'test': [
         'test/mrp_procurement.yml',
         'test/mrp_packs.yml',
         'test/mrp_phantom_bom.yml',
         'test/mrp_production_order.yml',
         'test/mrp_report.yml',

    ],
    'installable': True,
    'active': False,
    'certificate': '0032052481373',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
