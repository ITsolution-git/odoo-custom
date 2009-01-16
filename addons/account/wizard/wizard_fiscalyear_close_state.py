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

import wizard
import osv
import pooler
from tools.translate import _

_transaction_form = '''<?xml version="1.0"?>
<form string=" Close states of Fiscal year and periods">
    <field name="fy_id"/>
    <field name="fy2_id"/>
    <separator string="Are you sure you want to close the states of fiscal year and its period?" colspan="4"/>
    <field name="sure"/>
</form>'''

_transaction_fields = {
    'fy_id': {'string':'Fiscal Year to close', 'type':'many2one', 'relation': 'account.fiscalyear','required':True, 'domain':[('state','=','draft')]},
    'fy2_id': {'string':'New Fiscal Year', 'type':'many2one', 'relation': 'account.fiscalyear', 'domain':[('state','=','draft')], 'required':True},
    'sure': {'string':'Check this box', 'type':'boolean'},
}

def _data_save(self, cr, uid, data, context):
    if not data['form']['sure']:
        raise wizard.except_wizard(_('UserError'), _('Closing of states cancelled, please check the box !'))
    pool = pooler.get_pool(cr.dbname)

    fy_id = data['form']['fy_id']
    new_fyear = pool.get('account.fiscalyear').browse(cr, uid, data['form']['fy2_id'])
    start_jp = new_fyear.start_journal_period_id

    cr.execute('UPDATE account_journal_period ' \
            'SET state = %s ' \
            'WHERE period_id IN (SELECT id FROM account_period WHERE fiscalyear_id = %s)',
            ('done',fy_id))
    cr.execute('UPDATE account_period SET state = %s ' \
            'WHERE fiscalyear_id = %s', ('done',fy_id))
    cr.execute('UPDATE account_fiscalyear ' \
            'SET state = %s, end_journal_period_id = %s ' \
            'WHERE id = %s', ('done', start_jp and start_jp.id or None, fy_id))
    return {}

class wiz_journal_close_state(wizard.interface):
    states = {
        'init': {
            'actions': [],
            'result': {'type': 'form', 'arch':_transaction_form, 'fields':_transaction_fields, 'state':[('end','Cancel'),('close','Close states')]}
        },
        'close': {
            'actions': [_data_save],
            'result': {'type': 'state', 'state':'end'}
        }
    }
wiz_journal_close_state('account.fiscalyear.close.state')


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

