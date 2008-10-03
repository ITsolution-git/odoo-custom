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
    cr.execute('select id,name from ir_ui_view where name=%s and type=%s', ('product.margin.tree', 'tree'))
    view_res = cr.fetchone()
    return {
        'name': 'Product Margin',
        'context':{'date_start':data['form']['from_date'],'date_stop':data['form']['to_date'],'invoice_state' : data['form']['invoice_state']},
        'view_type': 'form',
        "view_mode": 'tree,form',
        'res_model':'product.product',
        'type': 'ir.actions.act_window',
        'view_id': view_res,
        }
    
    
class product_margin(wizard.interface):
    form1 = '''<?xml version="1.0"?>
    <form string="View Stock of Products">
        <separator string="Select " colspan="4"/>
        <field name="from_date"/>
        <field name="to_date"/>
        <field name="invoice_state"/>
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
         'invoice_state': {
                'string': 'Invoice State',
                'type': 'selection',
                'selection': [('paid','Paid'),('all_open','All Open'),('draft_open','Draft and Open')],
                'required': True,
                'default': lambda *a:"all_open",
        },
    }

    states = {
      'init': {
            'actions': [],
            'result': {'type': 'form', 'arch':form1, 'fields':form1_fields, 'state': [('end', 'Cancel','gtk-cancel'),('open', 'Open Margin','gtk-ok')]}
        },
    'open': {
            'actions': [],
            'result': {'type': 'action', 'action': _action_open_window, 'state':'end'}
        }
    }
product_margin('product.margin')
