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

{
    "name" : "Caldav task management", 
    "version" : "1.0", 
    "author" : "Tiny", 
    "category" : "Generic Modules/Others", 
    "description": """ Synchronize between Project task and Caldav Vtodo.""", 
    "depends" : ["project", "caldav"], 
    "init_xml" : [], 
    "demo_xml" : [], 
    "update_xml" : ["project_calendar_view.xml", 
                                "project_calendar_wizard.xml",
                                "security/ir.model.access.csv"], 
    "active": False, 
    "website": "http://www.openerp.com", 
    "installable": True, 
}
