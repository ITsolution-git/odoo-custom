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
import time

def _action_open_window(self, cr, uid, data, context): 
    domain=[]
    from_date= data['form']['from_date']
    to_date=data['form']['to_date']
    if from_date and to_date:
        domain=[('date','>=',from_date),('date','<=',to_date)]
    elif from_date:
        domain=[('date','>=',from_date)]
    elif to_date:
        domain=[('date','<=',to_date)]
    return {
        'name': 'Analytic Entries',
        'view_type': 'form',
        "view_mode": 'tree,form',
        'res_model': 'account.analytic.line',
        'type': 'ir.actions.act_window',
        'domain': domain}


class account_analytic_line(wizard.interface):
    form1 = '''<?xml version="1.0"?>
    <form string="View Account Analytic Lines">
        <separator string="Account Analytic Lines Analysis" colspan="4"/>
        <field name="from_date"/>
        <newline/>
        <field name="to_date"/>
        <newline/>
        <label string=""/>
        <label string="(Keep empty to open the current situation)" align="0.0" colspan="3"/>
    </form>'''
    form1_fields = {
             'from_date': {
                'string': 'From',
                'type': 'date',
        },
             'to_date': {
                'string': 'To',
                'type': 'date',
        },
    }

    states = {
      'init': {
            'actions': [],
            'result': {'type': 'form', 'arch':form1, 'fields':form1_fields, 'state': [('end', 'Cancel','gtk-cancel'),('open', 'Open Entries','gtk-ok')]}
        },
    'open': {
            'actions': [],
            'result': {'type': 'action', 'action': _action_open_window, 'state':'end'}
        }
    }
account_analytic_line('account.analytic.line')
