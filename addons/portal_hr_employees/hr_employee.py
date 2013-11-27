# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2011 OpenERP S.A (<http://www.openerp.com>).
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

from openerp.osv import fields, osv

class crm_contact_us(osv.TransientModel):
    """ Add employees list to the portal's contact page """
    _inherit = 'portal_crm.crm_contact_us'
    _columns = {
        'employee_ids' : fields.many2many('hr.employee', string='Employees', readonly=True),
    }

    """ Little trick to display employees in our wizard view """
    def _get_employee(self, cr, uid, context=None):
        """ Employees flagged as 'private' won't appear on the contact page """
        r = self.pool.get('hr.employee').search(cr, uid, [('visibility', '!=', 'private')], context=context)
        return r

    _defaults = {
        'employee_ids' : _get_employee,
    }

class hr_employee(osv.osv):
    _inherit = 'hr.employee'

    """
    ``visibility``: defines if the employee appears on the portal's contact page
                    - 'public' means the employee will appear for everyone (anonymous)
                    - 'private' means the employee won't appear
    """
    _columns = {
        'visibility': fields.selection([('public', 'Public'),('private', 'Private')],
            string='Visibility', help='Employee\'s visibility in the portal\'s contact page'),
        'public_info': fields.text('Public Info'),
    }
    _defaults = {
        'visibility': 'private',
    }

class calendar_attendee(osv.osv):
    _inherit = 'calendar.attendee'
    
    def create(self, cr, uid, vals, context=None):
        user_pool = self.pool.get('res.users')
        partner_id = vals.get('partner_id')
        users = user_pool.search_read(cr, uid, [('partner_id','=', partner_id)],['employee_ids'], context=context)
        for user in users:
            if user['employee_ids']:
                vals['state'] = 'accepted'
        return super(calendar_attendee, self).create(cr, uid, vals, context=context)

