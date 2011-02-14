# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
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
    'name': 'Add the Timesheet support for Issue Management in Project Management',
    'version': '1.0',
    'category': 'Generic Modules/CRM & SRM',
    'description': """
                    This module adds the Timesheet support for the Issues/Bugs Management in Project
                """,
    'author': 'OpenERP SA',
    'website': 'http://www.openerp.com',
    'depends': [
        'project_issue',
        'hr_timesheet_sheet',
    ],
    'init_xml': [
    ],
    'update_xml': [
        'project_issue_sheet_view.xml',
        'security/ir.model.access.csv',
    ],
    'demo_xml': [
    ],
    'installable': True,
    'active': False,
    'certificate' : '00856032058128997037',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
