# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Business Applications
#    Copyright (C) 2004-2012 OpenERP S.A. (<http://openerp.com>).
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

from osv import osv, fields

class hr_applicant_settings(osv.osv_memory):
    _name = 'hr.config.settings'
    _inherit = ['hr.config.settings', 'fetchmail.config.settings']

    _columns = {
        'module_document_ftp': fields.boolean('Automatic Indexation of Resumes',
            help="""Manage your CV's and motivation letter related to all applicants.
                This installs the module document_ftp."""),
        'fetchmail_applicants': fields.boolean('Create Applicants from an Email Account',
            fetchmail_model='hr.applicant', fetchmail_name='Incoming HR Applications',                                            
            help ="""Allow applicants to send their job application to an email address (jobs@mycompany.com),
                and create automatically application documents in the system."""),
        'applicants_server': fields.char('Server', size=256),
        'applicants_port': fields.integer('Port'),
        'applicants_type': fields.selection([
                ('pop', 'POP Server'),
                ('imap', 'IMAP Server'),
                ('local', 'Local Server'),
            ], 'Type'),
        'applicants_is_ssl': fields.boolean('SSL/TLS',
            help="Connections are encrypted with SSL/TLS through a dedicated port (default: IMAPS=993, POP=995)"),
        'applicants_user': fields.char('Username', size=256),
        'applicants_password': fields.char('Password', size=1024),                
    }

    _defaults = {
        'applicants_type': 'pop',
    }

