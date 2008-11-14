# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2008 Tiny SPRL (<http://tiny.be>). All Rights Reserved
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
    "name" : "Base Contact",
    "version" : "1.0",
    "author" : "Tiny",
    "website" : "http://tinyerp.com",
    "category" : "Generic Modules/Base",
    "description": """
        This module allows you to manage entirely your contacts.

    It lets you define
        *contacts unrelated to a partner,
        *contacts working at several adresses (possibly for different partners),
        *contacts with possibly different functions for each of its job's addresses

    It also add new menuitems located in
        Partners \ Contacts
        Partners \ Functions


    Pay attention that this module converts the existing addresses into "addresses + contacts". It means that some fields of the addresses will be missing (like the contact name), since these are supposed to be defined in an other object.
    """,
    "depends" : ["base"],
    "init_xml" : [],
    "demo_xml" : [
        "base_contact_demo.xml"
    ],
    "update_xml" : [
        "security/ir.model.access.csv",
        'base_contact_view.xml'
    ],
    "active": False,
    "installable": True
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

