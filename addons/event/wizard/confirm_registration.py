##############################################################################
#
# Copyright (c) 2005-2006 TINY SPRL. (http://tiny.be) All Rights Reserved.
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

import time
import wizard
import ir
import pooler
from osv.osv import except_osv
from osv import fields,osv
import netsvc

ARCH = '''<?xml version="1.0"?>
<form string="Registration Confirmation">
    <label string="The event limit is reached. What do you want to do?" colspan="4"/>
</form>'''

ARCH_fields={}

def _confirm(self, cr, uid, data, context):
    registration_obj = pooler.get_pool(cr.dbname).get('event.registration')
    current_registration = registration_obj.browse(cr, uid, [data['id']])[0]

    total_confirmed = current_registration.event_id.register_current + current_registration.nb_register
    if total_confirmed <= current_registration.event_id.register_max or current_registration.event_id.register_max == 0:
        return 'confirm'
    return 'split'


def _check_confirm(self, cr, uid, data, context):
    registration_obj = pooler.get_pool(cr.dbname).get('event.registration')
    registration_obj.write(cr, uid, [data['id']], {'state':'open',})
    registration_obj._history(cr, uid, reg, 'Open', history=True)
    registration_obj.mail_user(cr,uid,[data['id']])
    return {}


class confirm_registration(wizard.interface):
    states = {
        'init' : {
            'actions' : [],
            'result' : {'type' : 'choice', 'next_state' : _confirm}
        },

        'split' : {
            'actions' : [],
            'result' : {'type' : 'form',
                    'arch' : ARCH,'fields':ARCH_fields,
                    'state' : [('end', 'Cancel'),('confirm', 'Confirm Anyway') ]}
        },

        'confirm' : {
            'actions' : [],
            'result' : {'type' : 'action', 'action': _check_confirm, 'state' : 'end'}
        },
        'end' : {
            'actions' : [],
            'result': {'type': 'state', 'state': 'end'},
        },
    }

confirm_registration('event.confirm_registration')
