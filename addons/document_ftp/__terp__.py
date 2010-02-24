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
    'name': 'Integrated FTP Server with Document Management System',
    'version': '1.99',
    'category': 'Generic Modules/Others',
    'description': """This is a support FTP Interface with document management system:    
""",
    'author': 'Tiny',
    'website': 'http://www.openerp.com',
    'depends': ['base', 'document'],
    'init_xml': [],
    'update_xml': [
        'document_ftp_view.xml',
        'security/ir.model.access.csv'
    ],
    'demo_xml': [],
    'installable': True,
    'active': False,
    'certificate': None,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
