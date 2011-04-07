# -*- encoding: utf-8 -*-
##############################################################################
#
#   Copyright (C) 2010-2011 BAAMTU SARL (<http://www.baamtu.sn>). All Rights Reserved
#    $Id$
#   contact: leadsn@baamtu.com
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
    "name" : "OHADA - The accounting chart ",
    "version" : "1.0",
    "author" : "Baamtu Senegal",
    "category" : "Localisation/Account Charts",
    "description": """This module implements the accounting chart for OHADA area.
    It allows any company or association to manage its financial accounting.
    """,
    "website": "http://www.baamtu.com",
    "depends" : ["account", "base_vat"],
    "demo_xml" : [],
    "init_xml":[],
    "update_xml" : ["l10n_syscohada_data.xml","l10n_syscohada_wizard.xml"],
    "active": False,
    "installable": True
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
