#!/usr/bin/env python
#-*- coding:utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    mga@tinyerp.com
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

import time

from imaplib import IMAP4
from imaplib import IMAP4_SSL
from poplib import POP3
from poplib import POP3_SSL

import netsvc
from osv import osv, fields

logger = netsvc.Logger()


class email_server(osv.osv):

    _name = 'email.server'
    _description = "POP/IMAP Server"

    _columns = {
        'name':fields.char('Name', size=256, required=True, readonly=False), 
        'active':fields.boolean('Active', required=False), 
        'state':fields.selection([
            ('draft', 'Not Confirmed'), 
            ('wating', 'Waiting for Verification'), 
            ('done', 'Confirmed'), 
        ], 'State', select=True, readonly=True), 
        'server' : fields.char('Server', size=256, required=True, readonly=True, states={'draft':[('readonly', False)]}), 
        'port' : fields.integer('Port', required=True, readonly=True, states={'draft':[('readonly', False)]}), 
        'type':fields.selection([
            ('pop', 'POP Server'), 
            ('imap', 'IMAP Server'), 
        ], 'State', select=True, readonly=False), 
        'is_ssl':fields.boolean('SSL ?', required=False), 
        'attach':fields.boolean('Add Attachments ?', required=False), 
        'date': fields.date('Date', readonly=True, states={'draft':[('readonly', False)]}), 
        'user' : fields.char('User Name', size=256, required=True, readonly=True, states={'draft':[('readonly', False)]}), 
        'password' : fields.char('Password', size=1024, invisible=True, required=True, readonly=True, states={'draft':[('readonly', False)]}), 
        'note': fields.text('Description'), 
        'action_id':fields.many2one('ir.actions.server', 'Reply Email', required=False, domain="[('state','=','email')]"), 
        'object_id': fields.many2one('ir.model', "Model", required=True), 
        'priority': fields.integer('Server Priority', readonly=True, states={'draft':[('readonly', False)]}, help="Priority between 0 to 10, select define the order of Processing"), 
        'user_id':fields.many2one('res.users', 'User', required=False), 
    }
    _defaults = {
        'state': lambda *a: "draft", 
        'active': lambda *a: True, 
        'priority': lambda *a: 5, 
        'date': lambda *a: time.strftime('%Y-%m-%d'), 
        'user_id': lambda self, cr, uid, ctx: uid, 
    }

    def check_duplicate(self, cr, uid, ids):
        vals = self.read(cr, uid, ids, ['user', 'password'])[0]
        cr.execute("select count(id) from email_server where user='%s' and password='%s'" % (vals['user'], vals['password']))
        res = cr.fetchone()
        if res:
            if res[0] > 1:
                return False
        return True

    _constraints = [
        (check_duplicate, 'Warning! Can\'t have duplicate server configuration!', ['user', 'password'])
    ]

    def onchange_server_type(self, cr, uid, ids, server_type=False, ssl=False):
        port = 0
        if server_type == 'pop':
            port = ssl and 995 or 110
        elif server_type == 'imap':
            port = ssl and 993 or 143

        return {'value':{'port':port}}

    def set_draft(self, cr, uid, ids, context={}):
        self.write(cr, uid, ids , {'state':'draft'})
        return True

    def button_fetch_mail(self, cr, uid, ids, context={}):
        self.fetch_mail(cr, uid, ids)
#        sendmail_thread = threading.Thread(target=self.fetch_mail, args=(cr, uid, ids))
#        sendmail_thread.start()
        return True

    def _fetch_mails(self, cr, uid, ids=False, context={}):
        if not ids:
            ids = self.search(cr, uid, [])
        return self.fetch_mail(cr, uid, ids, context)

    def fetch_mail(self, cr, uid, ids, context={}):
        email_tool = self.pool.get('email.server.tools')
        for server in self.browse(cr, uid, ids, context):
            logger.notifyChannel('imap', netsvc.LOG_INFO, 'fetchmail start checking for new emails on %s' % (server.name))

            count = 0
            try:
                if server.type == 'imap':
                    imap_server = None
                    if server.is_ssl:
                        imap_server = IMAP4_SSL(server.server, int(server.port))
                    else:
                        imap_server = IMAP4(server.server, int(server.port))

                    imap_server.login(server.user, server.password)
                    imap_server.select()
                    result, data = imap_server.search(None, '(UNSEEN)')
                    for num in data[0].split():
                        result, data = imap_server.fetch(num, '(RFC822)')
                        res_id = email_tool.process_email(cr, uid, server.object_id.model, data[0][1], attach=server.attach, server_id=server.id, server_type=server.type, context=context)
                        if res_id and server.action_id:
                            action_pool = self.pool.get('ir.actions.server')
                            action_pool.run(cr, uid, [server.action_id.id], {'active_id': res_id, 'active_ids':[res_id]})

                            imap_server.store(num, '+FLAGS', '\\Seen')
                        count += 1
                    logger.notifyChannel('imap', netsvc.LOG_INFO, 'fetchmail fetch/process %s email(s) from %s' % (count, server.name))

                    imap_server.close()
                    imap_server.logout()
                elif server.type == 'pop':
                    pop_server = None
                    if server.is_ssl:
                        pop_server = POP3_SSL(server.server, int(server.port))
                    else:
                        pop_server = POP3(server.server, int(server.port))

                    #TODO: use this to remove only unread messages
                    #pop_server.user("recent:"+server.user)
                    pop_server.user(server.user)
                    pop_server.pass_(server.password)
                    pop_server.list()

                    (numMsgs, totalSize) = pop_server.stat()
                    for num in range(1, numMsgs + 1):
                        (header, msges, octets) = pop_server.retr(num)
                        msg = '\n'.join(msges)
                        res_id = email_tool.process_email(cr, uid, server.object_id.model, data[0][1], attach=server.attach, server_id=server.id, server_type=server.type, context=context)
                        if res_id and server.action_id:
                            action_pool = self.pool.get('ir.actions.server')
                            action_pool.run(cr, uid, [server.action_id.id], {'active_id': res_id, 'active_ids':[res_id]})

                        pop_server.dele(num)

                    pop_server.quit()

                    logger.notifyChannel('imap', netsvc.LOG_INFO, 'fetchmail fetch %s email(s) from %s' % (numMsgs, server.name))

                self.write(cr, uid, [server.id], {'state':'done'})
            except Exception, e:
                logger.notifyChannel(server.type, netsvc.LOG_WARNING, '%s' % (e))

        return True

email_server()

class mailgate_message(osv.osv):

    _inherit = "mailgate.message"

    _columns = {
        'server_id': fields.many2one('email.server', "Mail Server", readonly=True, select=True), 
        'type':fields.selection([
            ('pop', 'POP Server'), 
            ('imap', 'IMAP Server'), 
        ], 'State', select=True, readonly=True), 
    }
    _order = 'id desc'

mailgate_message()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
