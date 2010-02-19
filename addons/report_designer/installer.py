# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
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

class report_designer_installer(osv.osv_memory):
    _name = 'report_designer.installer'
    _inherit = 'res.config.installer'

    _columns = {
        # Reporting
        'base_report_designer':fields.boolean('OpenOffice Report Designer'),
        'base_report_creator':fields.boolean('Query Builder'),
        'olap':fields.boolean('Business Intelligence Report'),
        }
report_designer_installer()

