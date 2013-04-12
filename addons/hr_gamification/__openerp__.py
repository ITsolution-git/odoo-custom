# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2013 Tiny SPRL (<http://openerp.com>).
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
{
    'name': 'HR Gamification',
    'version': '1.0',
    'author': 'OpenERP SA',
    'category': 'HR',
    'depends': ['gamification', 'hr'],
    'description': """Use the HR ressources for the gamification process of goals.

This allow the user to send badges to employees instead of simple users.
Badge received are displayed on the user profile.""",
    'data': ['badge_view.xml'],
    'auto_install': True,
    'js': ['static/src/js/badges.js'],
}
