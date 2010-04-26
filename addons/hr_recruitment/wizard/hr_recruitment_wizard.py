# -*- coding: utf-8 -*-
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

import time

from osv import osv, fields
from tools.translate import _

class job2phonecall(osv.osv_memory):
    _name = 'hr.recruitment.job2phonecall'
    _description = 'Schedule Phone Call'
    _columns = {
        'user_id': fields.many2one('res.users', 'Assign To'),
        'deadline': fields.datetime('Planned Date'),
        'note': fields.text('Goals'),
        'category_id': fields.many2one('crm.case.categ', 'Category', required=True),
                }

    def _date_user(self, cr, uid, context=None):
        case_obj = self.pool.get('hr.applicant')
        case = case_obj.browse(cr, uid, context['active_id'])
        return case.user_id and case.user_id.id or False

    def _date_category(self, cr, uid, context=None):
        categ_id = self.pool.get('crm.case.categ').search(cr, uid, [('name','=','Outbound')])
        return categ_id and categ_id[0] or case.categ_id and case.categ_id.id or False

    def _get_note(self, cr, uid, context=None):
        case_obj = self.pool.get('hr.applicant')
        case = case_obj.browse(cr, uid, context['active_id'])
        return case.description or ''

    _defaults = {
         'user_id': _date_user,
         'category_id': _date_category,
         'note': _get_note
                 }

    def make_phonecall(self, cr, uid, ids, context=None):
        mod_obj = self.pool.get('ir.model.data')
        job_case_obj = self.pool.get('hr.applicant')
        data_obj = self.pool.get('ir.model.data')
        phonecall_case_obj = self.pool.get('crm.phonecall')

        form = self.read(cr, uid, ids, [], context=context)[0]
#        form = data['form']
        result = mod_obj._get_id(cr, uid, 'crm', 'view_crm_case_phonecalls_filter')
        res = mod_obj.read(cr, uid, result, ['res_id'])
        # Select the view

        id2 = data_obj._get_id(cr, uid, 'crm', 'crm_case_phone_tree_view')
        id3 = data_obj._get_id(cr, uid, 'crm', 'crm_case_phone_form_view')
        if id2:
            id2 = data_obj.browse(cr, uid, id2, context=context).res_id
        if id3:
            id3 = data_obj.browse(cr, uid, id3, context=context).res_id

        for job in job_case_obj.browse(cr, uid, context['active_ids']):
            #TODO : Take other info from job
            new_phonecall_id = phonecall_case_obj.create(cr, uid, {
                        'name' : job.name,
                        'user_id' : form['user_id'],
                        'categ_id' : form['category_id'],
                        'description' : form['note'],
                        'date' : form['deadline'],
#                        'section_id' : form['section_id'],
                        'description':job.description,
                        'partner_id':job.partner_id.id,
                        'partner_address_id':job.partner_address_id.id,
                        'partner_phone':job.partner_phone,
                        'partner_mobile':job.partner_mobile,
                        'description':job.description,
                        'date':job.date,
                    }, context=context)
            new_phonecall = phonecall_case_obj.browse(cr, uid, new_phonecall_id)
            vals = {}
#            if not job.case_id:
#                vals.update({'phonecall_id' : new_phonecall.id})
            job_case_obj.write(cr, uid, [job.id], vals)
            job_case_obj.case_cancel(cr, uid, [job.id])
            phonecall_case_obj.case_open(cr, uid, [new_phonecall_id])

        value = {
            'name': _('Phone Call'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'crm.phonecall',
            'res_id' : new_phonecall_id,
            'views': [(id3,'form'),(id2,'tree'),(False,'calendar'),(False,'graph')],
            'type': 'ir.actions.act_window',
            'search_view_id': res['res_id']
        }
        return value

job2phonecall()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:>>>>>>> MERGE-SOURCE
