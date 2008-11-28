# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2008 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    "name":"Products Repairs Module",
    "version":"1.0",
    "author":"Tiny",
    "description": """
           The aim is to have a complete module to manage all products repairs. The following topics should be covered by this module:
           * Add/remove products in the reparation
           * Impact for stocks
           * Invoicing (products and/or services)
           * Warrenty concept
           * Repair quotation report
           * Notes for the technician and for the final customer           
""",    
    
    "category":"Custom",
    "depends":["base","sale","account"],
    "demo_xml":[],
    "update_xml":["mrp_repair_sequence.xml","mrp_repair_wizard.xml", "mrp_repair_view.xml", "mrp_repair_workflow.xml", "mrp_repair_report.xml"],
    "active": False,
    "installable": True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

