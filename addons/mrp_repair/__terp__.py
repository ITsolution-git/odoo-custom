# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2004-2008 Tiny SPRL (http://tiny.be) All Rights Reserved.
#
# $Id$
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
###############################################################################
# -*- encoding: utf-8 -*-
{
    "name":"Products Repairs Module",
    "version":"1.0",
    "author":"Tiny",
    "description": """
            The aim is to have a complete module to manage all products repairs. The following topics 
        should be covered by this module:
           Add/remove products in the reparation

           Impact for stocks

           Invoicing (products and/or services)

           Warrenty concept

           Repair quotation report

           Notes for the technician and for the final customer

           (Link to Cases) (option)
""",    
    
    "category":"Custom",
    "depends":["sale","account"],
    "demo_xml":[],
    "update_xml":["mrp_repair_view.xml", "mrp_repair_workflow.xml", "mrp_repair_report.xml"],
    "active": False,
    "installable": True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

