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

class res_company(osv.osv):
    _inherit = 'res.company'
    _columns = {
        'project_time_mode_id': fields.many2one('product.uom', 'Project Time Unit',
            help='This will set the unit of measure used in projects and tasks.\n' \
"If you use the timesheet linked to projects (project_timesheet module), don't " \
"forget to setup the right unit of measure in your employees.",
        ),
    }
    
    def write(self, cr, uid, ids,vals, context={}):
        task_ids=self.pool.get('project.task').search(cr, uid, [('state','in',['open', 'pending'])])
        if ('project_time_mode_id' in vals) and task_ids:
            raise osv.except_osv(_('Error !'), _('You cannot modify Project Time Unit as there are open or pending tasks created with current time unit.'))
        return super(res_company,self).write(cr, uid, ids, vals, context=context)

res_company()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
