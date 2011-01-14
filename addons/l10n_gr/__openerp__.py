# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2009 P. Christeas <p_christ@hol.gr>. All Rights Reserved
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
{
    "name" : "Greece - Normal Plan",
    "version" : "0.2",
    "author" : "P. Christeas, OpenERP SA.",
    "website": "http://openerp.hellug.gr/",
    "category" : "Localisation/Account Charts",
    "description": "This is the base module to manage the accounting chart for Greece.",
    "depends" : ["base", "account", "base_iban", "base_vat", "account_chart"],
    "init_xml" : [],
    "demo_xml" : [],
    "update_xml" : [ "account_types.xml",
                    "account_chart.xml", 
                    "account_full_chart.xml",
                    "account_tax.xml",
                    "account_tax_vat.xml",
                    "l10n_gr_wizard.xml"],
    "installable": True,
    'certificate': '001146244418929008029',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

