# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
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
    'name': 'Survey Module',
    'version': '1.0',
    'category': 'Tools',
    'description': """
    This module is used for surveing. It depends on the answers or reviews of some questions by different users.
    A survey may have multiple pages. Each page may contain multiple questions and each question may have multiple answers.
    Different users may give different answers of question and according to that survey is done. 
    Partners are also sent mails with user name and password for the invitation of the survey
    """,
    'author': 'Tiny',
    'depends': ['base'],
    'update_xml': ['survey_report.xml','survey_data.xml','survey_que_wizard.xml','survey_wizard.xml','survey_view.xml','security/ir.model.access.csv'],
    'demo_xml': ['survey_demo.xml'],
    'installable': True,
    'active': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
