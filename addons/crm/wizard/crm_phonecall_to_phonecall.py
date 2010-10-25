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

from osv import osv, fields
from tools.translate import _

class crm_phonecall2phonecall(osv.osv_memory):
    """ Converts Phonecall to Phonecall"""

    _name = 'crm.phonecall2phonecall'
    _description = 'Phonecall To Phonecall'

    def action_cancel(self, cr, uid, ids, context=None):
        """
        Closes Phonecall to Phonecall form
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of Phonecall to Phonecall's IDs
        @param context: A standard dictionary for contextual values
        """
        return {'type':'ir.actions.act_window_close'}

    def action_apply(self, cr, uid, ids, context=None):
        """
        This converts Phonecall to Phonecall and opens Phonecall view
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of Phonecall to Phonecall IDs
        @param context: A standard dictionary for contextual values

        @return : Dictionary value for created Opportunity form
        """
        res = {}
        record_id = context and context.get('active_id', False) or False
        phonecall_obj = self.pool.get('crm.phonecall')

        if record_id:
            data_obj = self.pool.get('ir.model.data')

            # Get Phonecall views
            result = data_obj._get_id(cr, uid, 'crm', 'view_crm_case_phonecalls_filter')
            res = data_obj.read(cr, uid, result, ['res_id'])
            id2 = data_obj._get_id(cr, uid, 'crm', 'crm_case_phone_form_view')
            id3 = data_obj._get_id(cr, uid, 'crm', 'crm_case_phone_tree_view')
            if id2:
                id2 = data_obj.browse(cr, uid, id2, context=context).res_id
            if id3:
                id3 = data_obj.browse(cr, uid, id3, context=context).res_id

            phonecall = phonecall_obj.browse(cr, uid, record_id, context=context)

            for this in self.browse(cr, uid, ids, context=context):
                values = {
                        'name': this.name,
                        'user_id': this.user_id and this.user_id.id,
                        'categ_id': this.categ_id.id,
                        'section_id': this.section_id.id or (phonecall.section_id and phonecall.section_id.id),
                        'description': phonecall.description or '',
                        'partner_id': phonecall.partner_id.id,
                        'partner_address_id': phonecall.partner_address_id.id,
                        'partner_mobile': phonecall.partner_mobile or False,
                        'priority': phonecall.priority,
                        'partner_phone': phonecall.partner_phone or False,
                        'date': this.date
                          }
                phonecall_id = phonecall_obj.create(cr, uid, values, context=context)
            
            res = {
                'name': _('Phone Call'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'crm.phonecall',
                'view_id': False,
                'views': [(id2, 'form'), (id3, 'tree'), (False, 'calendar'), (False, 'graph')],
                'type': 'ir.actions.act_window',
                'res_id': phonecall_id, 
                'domain': [('id', '=', phonecall_id)], 
                'search_view_id': res['res_id']
                }
        return res

    _columns = {
                'name' : fields.char('Call summary', size=64, required=True, select=1),
                'user_id' : fields.many2one('res.users',"Assign To"),
                'categ_id': fields.many2one('crm.case.categ', 'Category', required=True, \
                        domain="['|',('section_id','=',False),('section_id','=',section_id),\
                        ('object_id.model', '=', 'crm.phonecall')]"), 
                'date': fields.datetime('Date', required=True),
                'section_id':fields.many2one('crm.case.section','Sales Team'),
                }

    def default_get(self, cr, uid, fields, context=None):
        """
        This function gets default values
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param fields: List of fields for default value
        @param context: A standard dictionary for contextual values

        @return : default values of fields.
        """
        res = super(crm_phonecall2phonecall, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        
        if record_id:
            phonecall = self.pool.get('crm.phonecall').browse(cr, uid, record_id, context=context)

            categ_id = False
            data_obj = self.pool.get('ir.model.data')
            res_id = data_obj._get_id(cr, uid, 'crm', 'categ_phone2')
            if res_id:
                categ_id = data_obj.browse(cr, uid, res_id, context=context).res_id

            if 'name' in fields:
                res.update({'name': phonecall.name})
            if 'user_id' in fields:
                res.update({'user_id': phonecall.user_id and phonecall.user_id.id or False})
            if 'date' in fields:
                res.update({'date': phonecall.date})
            if 'section_id' in fields:
                res.update({'section_id': phonecall.section_id and phonecall.section_id.id or False})
            if 'categ_id' in fields:
                res.update({'categ_id': categ_id})
        return res

crm_phonecall2phonecall()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
