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
from os.path import join as opj
import tools

class l10n_installer(osv.osv_memory):
    _inherit = 'account.installer'
    _columns = {
        'company_type':fields.selection([('partnership_private_company', 'Partnership/Private Firm'),
                                         ('public_company', 'Public Firm')], 'Company Type', required=True),        
    }

    _defaults = {
        'company_type': 'public_company',
    }
    
    def execute_simple(self, cr, uid, ids, context=None):
        res = super(l10n_installer, self).execute_simple(cr, uid, ids, context=context)
        if context is None:
            context = {}
        for res in self.read(cr, uid, ids, context=context):
            if res['charts'] =='l10n_in' and res['company_type']=='public_company':
                path = tools.file_open(opj('l10n_in', 'l10n_in_public_firm_chart.xml'))
                tools.convert_xml_import(cr, 'l10n_in', path, {}, 'init', True, None)
                path.close() 
            if res['charts'] =='l10n_in' and res['company_type']=='partnership_private_company':
                path = tools.file_open(opj('l10n_in', 'l10n_in_partnership_private_chart.xml'))
                tools.convert_xml_import(cr, 'l10n_in', path, {}, 'init', True, None)
                path.close()  
        return res

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
