# -*- encoding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (c) 2011 CCI Connect asbl (http://www.cciconnect.be) All Rights Reserved.
#                       Philmer <philmer@cciconnect.be>
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
    "name" : "OpenERP",
    "version" : "1.0",
    "author" : "OpenERP",
    "category" : "Test accounting",
    "website": "http://www.openerp.com",
    "description": "Asserts on accounting",
    "depends" : ["account"],
    "update_xml" : [
        "account_test_view.xml",
        "account_test_report.xml",
        "security/ir.model.access.csv",
        "account_test_data.xml",
    ],
    'demo_xml': [
        "account_test_demo.xml",
    ],
    "active": False,
    "installable": True
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
