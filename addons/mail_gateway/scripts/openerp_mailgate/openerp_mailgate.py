#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2010-TODAY OpenERP S.A. (http://www.openerp.com)
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
###########################################################################################

from email.header import decode_header
import email as EMAIL
import logging
import optparse
import sys
import xmlrpclib

class rpc_proxy(object):
    def __init__(self, uid, passwd, host='localhost', port=8069, path='object', dbname='terp'):
        self.rpc = xmlrpclib.ServerProxy('http://%s:%s/xmlrpc/%s' % (host, port, path), allow_none=True)
        self.user_id = uid
        self.passwd = passwd
        self.dbname = dbname

    def __call__(self, *request, **kwargs):
        return self.rpc.execute(self.dbname, self.user_id, self.passwd, *request, **kwargs)

class email_parser(object):
    def __init__(self, uid, password, model, email, email_default, dbname, host, port):
        self.rpc = rpc_proxy(uid, password, host=host, port=port, dbname=dbname)
        try:
            self.model_id = int(model)
            self.model = str(model)
        except:
            self.model_id = self.rpc('ir.model', 'search', [('model', '=', model)])[0]
            self.model = str(model)
        self.email = email
        self.email_default = email_default
        self.canal_id = False
        
        

    def parse(self, message):
        try:
            res_id = self.rpc('email.server.tools', 'process_email', self.model, message)
        except Exception, e:
            res_id = False

#    Reply mail
        if res_id:
            self.rpc('email.server.tools', 'email_send', self.model, res_id, message, self.email_default)
        
        return res_id

if __name__ == '__main__':
    parser = optparse.OptionParser(usage='usage: %prog [options]', version='%prog v1.0')
    group = optparse.OptionGroup(parser, "Note", 
        "This program parse a mail from standard input and communicate  with the Open ERP server")
    parser.add_option_group(group)
    parser.add_option("-u", "--user", dest="userid", help="ID of the user in Open ERP", default=1, type='int')
    parser.add_option("-p", "--password", dest="password", help="Password of the user in Open ERP", default='admin')
    parser.add_option("-e", "--email", dest="email", help="Email address used in the From field of outgoing messages")
    parser.add_option("-o", "--model", dest="model", help="Name or ID of crm model", default="crm.lead")
    parser.add_option("-m", "--default", dest="default", help="Default eMail in case of any trouble.", default=None)
    parser.add_option("-d", "--dbname", dest="dbname", help="Database name (default: terp)", default='terp')
    parser.add_option("--host", dest="host", help="Hostname of the Open ERP Server", default="localhost")
    parser.add_option("--port", dest="port", help="Port of the Open ERP Server", default="8069")

    (options, args) = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
    
    parser = email_parser(options.userid, options.password, options.model, options.email, options.default, dbname=options.dbname, host=options.host, port=options.port)
    msg_txt = sys.stdin.read()

    parser.parse(msg_txt)
 
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
