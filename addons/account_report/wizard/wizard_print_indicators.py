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

import wizard
import pooler

form = '''<?xml version="1.0"?>
<form string="Print Indicators">
    <label string="Select the criteria based on which Indicators will be printed."/>
    <newline/>
    <field name="select_base"/>
</form>'''

fields = {
    'select_base': {'string':'Choose Criteria', 'type':'selection','selection':[('year','Based On Fiscal Years'),('periods','Based on Fiscal Periods')],'required':True,},
}

next_form = '''<?xml version="1.0"?>
<form string="Print Indicators">
    <field name="base_selection"/>
</form>'''

next_fields = {
    'base_selection': {'string':'Select Criteria', 'type':'many2many','required':True,},
}

def _load(self, cr, uid, data, context):
    data['form']['select_base'] = 'year'
    return data['form']

def _load_base(self, cr, uid, data, context):
    next_fields['base_selection']['relation']='account.fiscalyear'
    if data['form']['select_base']=='periods':
        next_fields['base_selection']['relation']='account.period'
    return data['form']

def _check_len(self, cr, uid, data, context):
    if len(data['form']['base_selection'][0][2])>12:
        raise wizard.except_wizard('User Error!',"Please select maximum 12 records to fit the page-width.")
    return data['form']

class wizard_print_indicators(wizard.interface):
    states = {
        'init': {
            'actions': [_load],
            'result': {'type': 'form', 'arch':form, 'fields':fields, 'state':[('end','Cancel'),('next','Next')]}
        },
        'next': {
            'actions': [_load_base],
            'result': {'type':'form', 'arch':next_form, 'fields':next_fields, 'state':[('end','Cancel'),('print','Print')]}
        },
        'print': {
            'actions':[_check_len],
            'result' :{'type':'print','report':'print.indicators', 'state':'end'}
        }
    }
wizard_print_indicators('print.indicators')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
