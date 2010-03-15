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
    "name" : "Long Term Project Management",
    "version": "1.1",
    "author" : "Tiny",
    "website" : "http://www.openerp.com",
    "category" : "Generic Modules/Projects & Services",
    "depends" : ["project", "resource"],
    "description": """

        Long Term Project management module that track planning, scheduling, resources allocation.
        Mainly used with Big project management.
            - Project Phases will be maintain by Manager of the project
            - Compute Phase Scheduling: Compute start date and end date of the phases which are in draft,open and pending state of the project given.
                                        If no project given then all the draft,open and pending states phases will be taken
            - Compute Task Scheduling: This works same as the scheduler button on project.phase. It takes the project as arguement and computes all the open,draft and pending tasks
            - Schedule Tasks: All the tasks which are in draft,pending and open states are scheduled with taking the phase's start date

    """,
    "init_xml" : [],
    "demo_xml" : ["project_long_term_demo.xml"],
    "update_xml": [
        "security/ir.model.access.csv",
        "project_long_term_wizard.xml" ,
        "project_long_term_view.xml",
        "project_long_term_workflow.xml"
    ],
    'installable': True,
    'active': False,
    'certificate': None,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
