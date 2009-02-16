# -*- encoding: utf-8 -*-
#
#  journal_config.py
#  l10n_ch
#
#  Created by Nicolas Bessi based on Credric Krier contribution
#
#  Copyright (c) 2009 CamptoCamp. All rights reserved.
##############################################################################
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
from osv import fields, osv


class Journal(osv.osv):
    """Create account.journal.todo in order to add configuration wizzard"""

    _name ="account.journal.todo"
    
    
    
    def _get_journal(self, cr, uid, ctx):
        if not self.__dict__.has_key('_inner_steps') :
            self._inner_steps = 0
        ids = self.pool.get('account.journal').search(cr,uid,[])
        if self._inner_steps == 'done' :
            return False
        return ids[self._inner_steps]
        

    def _get_debit(self, cr, uid, ctx):
        if not self.__dict__.has_key('_inner_steps') :
            self._inner_steps = 0
        if self._inner_steps == 'done' :
            return False
        ids = self.pool.get('account.journal').search(cr,uid,[])
        id = self.pool.get('account.journal').browse(
            cr,
            uid,
            ids[self._inner_steps]
        ).default_debit_account_id.id
        
        return id
        
    def _get_credit(self, cr, uid, ctx):
        if not self.__dict__.has_key('_inner_steps') :
            self._inner_steps = 0
        if self._inner_steps == 'done' :
            return False
        ids = self.pool.get('account.journal').search(cr,uid,[])
        id = self.pool.get('account.journal').browse(
            cr,
            uid,
            ids[self._inner_steps]
        ).default_credit_account_id.id
        
        return id
    
        
    _columns={
        'name': fields.many2one(
            'account.journal',
            'Journal to set',
             readonly=True,
             help="the currenty edited account journal"
        ),
        'default_credit_account_id': fields.many2one(
                'account.account', 'Default Credit Account', 
                domain="[('type','!=','view')]",
                help="The Default Credit Account of the account journal"

            ),
        'default_debit_account_id': fields.many2one(
                'account.account', 
                'Default Debit Account', 
                domain="[('type','!=','view')]",
                help="The Default Debit Account of the account journal"
            ),
    }

    _defaults = {
        'name': _get_journal,
        'default_debit_account_id':_get_debit,
        'default_credit_account_id':_get_credit,
        }
    
    def on_change_debit(self, cr, uid, id, journal, account) :
        if account :
            self.pool.get('account.journal').write(
                                        cr,
                                        uid, 
                                        journal,
                                        vals={
                                            'default_debit_account_id': account,
                                        }
                                        )
    
        
        
        return {}
        
    def on_change_credit(self, cr, uid, id, journal, account) :
        if account : 
            self.pool.get('account.journal').write(
                                        cr,
                                        uid, 
                                        journal,
                                        vals={
                                            'default_credit_account_id': account,
                                        }
                                )
        return {}



    def action_cancel(self,cr,uid,ids,context=None):
        return {
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'ir.actions.configuration.wizard',
                'type': 'ir.actions.act_window',
                'target':'new',
        }   
    def action_new(self,cr,uid,ids,context={}):
        jids = self.pool.get('account.journal').search(cr, uid, [])
        if self._inner_steps < len(jids)-1 :
            self._inner_steps += 1
        else :
            print 'DONE'
            self._inner_steps = 'done'
        return {
                'view_type': 'form',
                "view_mode": 'form',
                'res_model': 'account.journal.todo',
                'view_id':self.pool.get('ir.ui.view').search(
                        cr,
                        uid,
                        [('name','=','view_account_journal_form_todo')]
                    ),
                'type': 'ir.actions.act_window',
                'target':'new',
               }
        

Journal()