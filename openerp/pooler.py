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

""" Functions kept for backward compatibility.

    They are simple wrappers around a global RegistryManager methods.

"""

from openerp.registry.manager import RegistryManager

_Registries = None


def ensure_registries():
    global _Registries
    if _Registries is None:
        _Registries = RegistryManager()


def get_db_and_pool(db_name, force_demo=False, status=None, update_module=False, pooljobs=True):
    """Create and return a database connection and a newly initialized registry."""
    ensure_registries()
    bound_registry = _Registries.get(db_name, force_demo, status, update_module, pooljobs)
    return bound_registry.db, bound_registry.registry


def delete_pool(db_name):
    """Delete an existing registry."""
    ensure_registries()
    _Registries.delete(db_name)


def restart_pool(db_name, force_demo=False, status=None, update_module=False):
    """Delete an existing registry and return a database connection and a newly initialized registry."""
    ensure_registries()
    bound_registry = _Registries.new(db_name, force_demo, status, update_module, pooljobs)
    return bound_registry.db, bound_registry.registry


def get_db(db_name):
    """Return a database connection. The corresponding registry is initialized."""
    return get_db_and_pool(db_name)[0]


def get_pool(db_name, force_demo=False, status=None, update_module=False):
    """Return a model registry."""
    return get_db_and_pool(db_name, force_demo, status, update_module)[1]

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
