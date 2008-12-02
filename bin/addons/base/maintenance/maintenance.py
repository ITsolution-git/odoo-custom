# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2004-2008 TINY SPRL. (http://tiny.be) All Rights Reserved.
#
# $Id$
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

from osv import osv, fields
import pooler
import time
import math
from pprint import pprint as pp

from tools import config
import xmlrpclib

class maintenance_contract(osv.osv):
    _name = "maintenance.contract"
    _description = "Maintenance Contract"
    _columns = {
        'name' : fields.char('Contract ID', size=256, required=True, readonly=True),
        'password' : fields.char('Password', size=64, invisible=True, required=True, readonly=True),
        'date_start' : fields.date('Starting Date', readonly=True),
        'date_stop' : fields.date('Ending Date', readonly=True),
        'modules': fields.text('Covered Modules')
    }
    _defaults = {
        'password' : lambda obj,cr,uid,context={} : '',
    }

maintenance_contract()


class maintenance_contract_wizard(osv.osv_memory):
    _name = 'maintenance.contract.wizard'

    _columns = {
        'name' : fields.char('Contract ID', size=256, required=True ),
        'password' : fields.char('Password', size=64, required=True),
        'state' : fields.selection([('draft', 'Draft'),('validated', 'Validated'),('unvalidated', 'Unvalidated')], 'States'),
    }

    _defaults = {
        'state' : lambda *a: 'draft',
    }

    def action_validate(self, cr, uid, ids, context):
        if not ids:
            return False

        contract = self.read(cr, uid, ids, ['name', 'password'])[0]

        login, password, remote_db, remote_server, port = 'admin', 'admin', 'trunk', 'localhost', 8069

        rpc = xmlrpclib.ServerProxy('http://%s:%d/xmlrpc/common' % (remote_server, port))
        ruid = rpc.login(remote_db, login, password)
        rpc = xmlrpclib.ServerProxy('http://%s:%d/xmlrpc/object' % (remote_server, port))
        res = rpc.execute(remote_db, ruid, password, 
                          'maintenance.maintenance', 'get_module_for_contract', contract['name'], contract['password'])
        if res:
            self.pool.get('maintenance.contract').create(
                cr, 
                uid, {
                    'name' : contract['name'],
                    'password' : contract['password'],
                    'date_start' : res['date_from'],
                    'date_stop' : res['date_to'],
                }
            )

        return self.write(cr, uid, ids, {'state' : ('unvalidated', 'validated')[bool(res)] }, context=context)

maintenance_contract_wizard()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

