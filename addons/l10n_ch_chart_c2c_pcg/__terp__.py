# -*- encoding: utf-8 -*-
# Copyright (c) 2008 CamptoCamp SA
#
#  __init__.py
#
#  Created by Vincent Renaville on 12.02.09.
#  Copyright (c) 2009 CamptoCamp. All rights reserved.
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

{
    "name" : "Suisse - Plan comptable general pour PME STERCHI",
    "version" : "1.0",
    "depends" : [
					"account",
                    "account_chart",
					"l10n_ch"
                ],
    "author" : "Camptocamp",
    "description": "Swiws account chart that add also tax template definition",
    "website" : "camptocamp.com",
    "category" : "Localisation/Account Charts",
    "init_xml" : [
					'account.xml',
					'vat.xml'
				],
    "demo_xml" : [ ],
    "update_xml" : [
						'wizard.xml',
						'tax_template_view.xml',
						'security/ir.model.access.csv',
					],

    "active": False,
    "installable": True
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
