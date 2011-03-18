# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2011 Tiny SPRL (<http://tiny.be>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################

from osv import osv
from osv import fields
from tools.translate import _
import tools

#import time
#import binascii
#import email
#from email.header import decode_header
#from email.utils import parsedate
#import base64
#import re
#import logging
#import xmlrpclib

#_logger = logging.getLogger('mailgate')

#import re
import smtplib
#import base64
#from email import Encoders
#from email.mime.base import MIMEBase
#from email.mime.multipart import MIMEMultipart
#from email.mime.text import MIMEText
#from email.header import decode_header, Header
#from email.utils import formatdate
#import netsvc
#import datetime
#import tools
#import logging

#EMAIL_PATTERN = re.compile(r'([^()\[\] ,<:\\>@";]+@[^()\[\] ,<:\\>@";]+)') # See RFC822

class ir_mail_server(osv.osv):
    """
    mail server
    """
    _name = "ir.mail.server"

    _columns = {
        'name': fields.char('Name',
                        size=64, required=True,
                        select=True,
                        help="The Name is used as the Sender name along with the provided From Email, \
unless it is already specified in the From Email, e.g: John Doe <john@doe.com>",
                        ),
         'email_id': fields.char('From Email',
                        size=120, required=True,
                        help="eg: 'john@doe.com' or 'John Doe <john@doe.com>'"),
        'smtp_host': fields.char('Server',
                        size=120, required=True,
                        help="Enter name of outgoing server, eg: smtp.yourdomain.com"),
        'smtp_port': fields.integer('SMTP Port',
                        size=64, required=True,
                        help="Enter port number, eg: 25 or 587"),
        'smtp_user': fields.char('User Name',
                        size=120, required=False,
                        help="Specify the username if your SMTP server requires authentication, "
                        "otherwise leave it empty."),
        'smtp_pass': fields.char('Password',
                        size=120,
                        required=False),
        'smtp_tls':fields.boolean('TLS'),
        'smtp_ssl':fields.boolean('SSL/TLS'),
        'priority': fields.integer('Priority', help=""),
    }

    _defaults = {
         'name':lambda self, cursor, user, context:self.pool.get( 'res.users'
                                                ).read(cursor, user, user, ['name'], context)['name'],
         'smtp_port': tools.config.get('smtp_port',25),
         'smtp_host': tools.config.get('smtp_server','localhost'),
         'smtp_ssl': tools.config.get('smtp_ssl',False),
         'smtp_tls': True,
         'priority': 10,
     }

    _sql_constraints = [
        (
         'email_uniq',
         'unique (email_id)',
         'Another setting already exists with this email ID !')
    ]


    def name_get(self, cr, uid, ids, context=None):
        return [(a["id"], "%s (%s)" % (a['email_id'], a['name'])) for a in self.read(cr, uid, ids, ['name', 'email_id'], context=context)]

    def test_smtp_connection(self, cr, uid, ids, context=None):
        """
        Test SMTP connection works
        """
        try:
            for smtp_server in self.browse(cr, uid, ids, context=context):
                smtp = tools.connect_smtp_server(smtp_server.smtpserver, smtp_server.smtpport,  user_name=smtp_server.smtpuname,
                                user_password=smtp_server.smtppass, ssl=smtp_server.smtpssl, tls=smtp_server.smtptls)
                try:
                    smtp.quit()
                except Exception:
                    # ignored, just a consequence of the previous exception
                    pass
        except Exception, error:
            raise osv.except_osv(
                                 _("SMTP Connection: Test failed"),
                                 _("Reason: %s") % error
                                 )

        raise osv.except_osv(_("SMTP Connection: Test Successfully!"), '')


ir_mail_server()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
