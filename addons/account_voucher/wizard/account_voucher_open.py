# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from osv import fields, osv
from tools.translate import _
import tools

class account_voucher_open(osv.osv_memory):
    _name = "account.voucher.open"
    _description = "Account Voucher"
    
    def _get_period(self, cr, uid, context={}):
        """
        Return  default account period value
        """
        ids = self.pool.get('account.period').find(cr, uid, context=context)
        period_id = False
        if len(ids):
            period_id = ids[0]
        return period_id

    def _get_journal(self, cr, uid, context={}):
        """
        Return journal based on the journal type
        """
        journal_id = False
        
        journal_pool = self.pool.get('account.journal')
        if context.get('journal_type', False):
            jids = journal_pool.search(cr, uid, [('type','=', context.get('journal_type'))])
            journal_id = jids[0]
        return journal_id
    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Returns views and fields for current model where view will depend on {view_type}.
        @param cr: A database cursor
        @param user: ID of the user currently logged in
        @param view_id: list of fields, which required to read signatures
        @param view_type: defines a view type. it can be one of (form, tree, graph, calender, gantt, search, mdx)
        @param context: context arguments, like lang, time zone
        @param toolbar: contains a list of reports, wizards, and links related to current model
        
        @return: Returns a dict that contains definition for fields, views, and toolbars
        """
        res = super(account_voucher_open, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)

        if not view_id:
            return res

        period_pool = self.pool.get('account.period')
        journal_pool = self.pool.get('account.journal')
        
        journal_id = self._get_journal(cr, uid, context)
        period_id = self._get_period(cr, uid, context)

        journal = False
        if journal_id:
            journal = journal_pool.read(cr, uid, [journal_id], ['name'])[0]['name']
        else:
            journal = "All"

        period = False
        if period_id:
            period = period_pool.browse(cr, uid, [period_id], ['name'])[0]['name']
        
        menu = self.pool.get('ir.ui.menu').browse(cr, uid, context.get('active_id'))
        name = menu.name

        view = """<?xml version="1.0" encoding="utf-8"?>
        <form string="Standard entries">
            <separator string="Open %s !" colspan="4"/>
            <group colspan="4" >
                <label width="300" string="Journal : %s"/>
                <newline/>
                <label width="300" string="Period :  %s"/>
            </group>
            <group colspan="4" col="4">
                <label string ="" colspan="2"/>
                <button icon="terp-gtk-go-back-rtl" string="Ok" name="action_open_window" type="object"/>
            </group>
        </form>""" % (str(name), str(journal), str(period))
        
        res.update({
            'arch':view
        })
        return res
    
    def action_open_window(self, cr, uid, ids, context=None):
        """
        This function Open action move line window on given period and  Journal/Payment Mode
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: account move journal’s ID or list of IDs
        @return: dictionary of Open action move line window on given period and  Journal/Payment Mode
        """
        
        period_pool = self.pool.get('account.journal.period')
        data_pool = self.pool.get('ir.model.data')
        journal_pool = self.pool.get('account.journal')
        
        if context is None:
            context = {}
        
        journal_id = self._get_journal(cr, uid, context)
        period_id = self._get_period(cr, uid, context)
        
        menu = self.pool.get('ir.ui.menu').browse(cr, uid, context.get('active_id'))
        name = menu.name
        
        result = data_pool._get_id(cr, uid, 'account_voucher', 'view_voucher_filter_new')
        res_id = data_pool.browse(cr, uid, result, context=context).res_id
        
        res = {
            'domain':menu.action.domain,
            'name': name,
            'view_type': 'form',
            'view_mode': 'tree,graph,form',
            'res_model': 'account.voucher',
            'view_id': False,
            'context': "{'journal_id': %d, 'search_default_journal_id':%d, 'search_default_period_id':%d}" % (journal_id, journal_id, period_id),
            'type': 'ir.actions.act_window',
            'search_view_id': res_id
        }
        return res
    
account_voucher_open()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
