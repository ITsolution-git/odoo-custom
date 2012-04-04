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

class general_configuration(osv.osv_memory):
    _name = 'general.configuration'
    _inherit = 'res.config.settings'
    
    _columns = {
        'module_base_report_designer': fields.boolean('Customise your OpenERP Report with OpenOffice',
                           help ="""It installs the base_report_designer module."""),
        'module_report_webkit': fields.boolean('Design OpenERP report in HTML',
                           help ="""It installs the report_webkit module."""),
        'module_report_webkit_sample': fields.boolean('Samples of HTML report design',
                           help ="""It installs the report_webkit_sample module."""),
    }

general_configuration()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: