# -*- encoding: utf-8 -*-
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
    "name" : "Human Resources Evaluation",
    "version": "0.1",
    "author": "OpenERP SA",
    "category": "Generic Modules/Human Resources",
    "website": "http://www.openerp.com",
    "depends": ["hr",'hr_recruitment','survey'],
    "description": """
          Ability to create employees evaluation.
          An evaluation can be created by employee for subordinates,
          juniors as well as his manager.The evaluation is done under a plan
          in which various surveys can be created and it can be defined which
          level of employee hierarchy fills what and final review and evaluation
          is done by the manager.Every evaluation filled by the employees can be viewed
          in the form of.Implements a dashboard for My Current Evaluations
         """,
    "init_xml": [],
    "demo_xml": ["hr_evaluation_demo.xml",
                 ],
    "update_xml": [
        "security/ir.model.access.csv",
        "security/hr_evaluation_security.xml",
        "wizard/hr_evaluation_mail_view.xml",
        "hr_evaluation_view.xml",
        "report/hr_evaluation_report_view.xml",
        "board_hr_evaluation_view.xml"
        ],
    "test": ["test/test_hr_evaluation.yml"],
    "active": False,
    "installable": True,
    "certificate" : "00883207679172998429",
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

