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

""" Models registries.

"""
import logging
import threading

import openerp.sql_db
import openerp.osv.orm
import openerp.cron
import openerp.tools
import openerp.modules.db
import openerp.tools.config

_logger = logging.getLogger(__name__)

class Registry(object):
    """ Model registry for a particular database.

    The registry is essentially a mapping between model names and model
    instances. There is one registry instance per database.

    """

    def __init__(self, db_name):
        self.models = {} # model name/model instance mapping
        self._sql_error = {}
        self._store_function = {}
        self._init = True
        self._init_parent = {}
        self.db_name = db_name
        self.db = openerp.sql_db.db_connect(db_name)

        # Inter-process signaling (used only when openerp.multi_process is True):
        # The `base_registry_signaling` sequence indicates the whole registry
        # must be reloaded.
        # The `base_cache_signaling sequence` indicates all caches must be
        # invalidated (i.e. cleared).
        self.base_registry_signaling_sequence = 1
        self.base_cache_signaling_sequence = 1

        # Flag indicating if at least one model cache has been cleared.
        # Useful only in a multi-process context.
        self._any_cache_cleared = False

        cr = self.db.cursor()
        has_unaccent = openerp.modules.db.has_unaccent(cr)
        if openerp.tools.config['unaccent'] and not has_unaccent:
            _logger.warning("The option --unaccent was given but no unaccent() function was found in database.")
        self.has_unaccent = openerp.tools.config['unaccent'] and has_unaccent
        cr.close()

    def do_parent_store(self, cr):
        for o in self._init_parent:
            self.get(o)._parent_store_compute(cr)
        self._init = False

    def obj_list(self):
        """ Return the list of model names in this registry."""
        return self.models.keys()

    def add(self, model_name, model):
        """ Add or replace a model in the registry."""
        self.models[model_name] = model

    def get(self, model_name):
        """ Return a model for a given name or None if it doesn't exist."""
        return self.models.get(model_name)

    def __getitem__(self, model_name):
        """ Return a model for a given name or raise KeyError if it doesn't exist."""
        return self.models[model_name]

    def load(self, cr, module):
        """ Load a given module in the registry.

        At the Python level, the modules are already loaded, but not yet on a
        per-registry level. This method populates a registry with the given
        modules, i.e. it instanciates all the classes of a the given module
        and registers them in the registry.

        """

        res = []

        # Instantiate registered classes (via the MetaModel automatic discovery
        # or via explicit constructor call), and add them to the pool.
        for cls in openerp.osv.orm.MetaModel.module_to_models.get(module.name, []):
            res.append(cls.create_instance(self, cr))

        return res

    def schedule_cron_jobs(self):
        """ Make the cron thread care about this registry/database jobs.
        This will initiate the cron thread to check for any pending jobs for
        this registry/database as soon as possible. Then it will continuously
        monitor the ir.cron model for future jobs. See openerp.cron for
        details.
        """
        openerp.cron.schedule_wakeup(openerp.cron.WAKE_UP_NOW, self.db.dbname)

    def clear_caches(self):
        """ Clear the caches
        This clears the caches associated to methods decorated with
        ``tools.ormcache`` or ``tools.ormcache_multi`` for all the models.
        """
        for model in self.models.itervalues():
            model.clear_caches()
        # Special case for ir_ui_menu which does not use openerp.tools.ormcache.
        ir_ui_menu = self.models.get('ir.ui.menu')
        if ir_ui_menu:
            ir_ui_menu.clear_cache()


    # Useful only in a multi-process context.
    def reset_any_cache_cleared(self):
        self._any_cache_cleared = False

    # Useful only in a multi-process context.
    def any_cache_cleared(self):
        return self._any_cache_cleared

class RegistryManager(object):
    """ Model registries manager.

        The manager is responsible for creation and deletion of model
        registries (essentially database connection/model registry pairs).

    """
    # Mapping between db name and model registry.
    # Accessed through the methods below.
    registries = {}
    registries_lock = threading.RLock()

    @classmethod
    def get(cls, db_name, force_demo=False, status=None, update_module=False,
            pooljobs=True):
        """ Return a registry for a given database name."""
        try:
            return cls.registries[db_name]
        except KeyError:
            return cls.new(db_name, force_demo, status,
                           update_module, pooljobs)

    @classmethod
    def new(cls, db_name, force_demo=False, status=None,
            update_module=False, pooljobs=True):
        """ Create and return a new registry for a given database name.

        The (possibly) previous registry for that database name is discarded.

        """
        import openerp.modules
        with cls.registries_lock:
            registry = Registry(db_name)

            # Initializing a registry will call general code which will in turn
            # call registries.get (this object) to obtain the registry being
            # initialized. Make it available in the registries dictionary then
            # remove it if an exception is raised.
            cls.delete(db_name)
            cls.registries[db_name] = registry
            try:
                # This should be a method on Registry
                openerp.modules.load_modules(registry.db, force_demo, status, update_module)
            except Exception:
                del cls.registries[db_name]
                raise

            cr = registry.db.cursor()
            try:
                registry.do_parent_store(cr)
                registry.get('ir.actions.report.xml').register_all(cr)
                cr.commit()
            finally:
                cr.close()

        if pooljobs:
            registry.schedule_cron_jobs()

        return registry

    @classmethod
    def delete(cls, db_name):
        """Delete the registry linked to a given database.

        This also cleans the associated caches. For good measure this also
        cancels the associated cron job. But please note that the cron job can
        be running and take some time before ending, and that you should not
        remove a registry if it can still be used by some thread. So it might
        be necessary to call yourself openerp.cron.Agent.cancel(db_name) and
        and join (i.e. wait for) the thread.
        """
        with cls.registries_lock:
            if db_name in cls.registries:
                cls.registries[db_name].clear_caches()
                del cls.registries[db_name]
                openerp.cron.cancel(db_name)


    @classmethod
    def delete_all(cls):
        """Delete all the registries. """
        with cls.registries_lock:
            for db_name in cls.registries.keys():
                cls.delete(db_name)

    @classmethod
    def clear_caches(cls, db_name):
        """Clear caches

        This clears the caches associated to methods decorated with
        ``tools.ormcache`` or ``tools.ormcache_multi`` for all the models
        of the given database name.

        This method is given to spare you a ``RegistryManager.get(db_name)``
        that would loads the given database if it was not already loaded.
        """
        with cls.registries_lock:
            if db_name in cls.registries:
                cls.registries[db_name].clear_caches()

    @classmethod
    def check_registry_signaling(cls, db_name):
        if openerp.multi_process and db_name in cls.registries:
            # Check if the model registry must be reloaded (e.g. after the
            # database has been updated by another process).
            registry = cls.get(db_name, pooljobs=False)
            cr = registry.db.cursor()
            registry_reloaded = False
            try:
                cr.execute('SELECT last_value FROM base_registry_signaling')
                r = cr.fetchone()[0]
                if registry.base_registry_signaling_sequence != r:
                    _logger.info("Reloading the model registry after database signaling.")
                    # Don't run the cron in the Gunicorn worker.
                    registry = cls.new(db_name, pooljobs=False)
                    registry.base_registry_signaling_sequence = r
                    registry_reloaded = True
            finally:
                cr.close()

            # Check if the model caches must be invalidated (e.g. after a write
            # occured on another process). Don't clear right after a registry
            # has been reload.
            cr = openerp.sql_db.db_connect(db_name).cursor()
            try:
                cr.execute('SELECT last_value FROM base_cache_signaling')
                r = cr.fetchone()[0]
                if registry.base_cache_signaling_sequence != r and not registry_reloaded:
                    _logger.info("Invalidating all model caches after database signaling.")
                    registry.base_cache_signaling_sequence = r
                    registry.clear_caches()
                    registry.reset_any_cache_cleared()
            finally:
                cr.close()

    @classmethod
    def signal_caches_change(cls, db_name):
        if openerp.multi_process and db_name in cls.registries:
            # Check the registries if any cache has been cleared and signal it
            # through the database to other processes.
            registry = cls.get(db_name, pooljobs=False)
            if registry.any_cache_cleared():
                _logger.info("At least one model cache has been cleare, signaling through the database.")
                cr = registry.db.cursor()
                r = 1
                try:
                    pass
                    cr.execute("select nextval('base_cache_signaling')")
                    r = cr.fetchone()[0]
                finally:
                    cr.close()
                registry.base_cache_signaling_sequence = r
                registry.reset_any_cache_cleared()

    @classmethod
    def signal_registry_change(cls, db_name):
        if openerp.multi_process and db_name in cls.registries:
            registry = cls.get(db_name, pooljobs=False)
            cr = registry.db.cursor()
            r = 1
            try:
                cr.execute("select nextval('base_registry_signaling')")
                r = cr.fetchone()[0]
            finally:
                cr.close()
            registry.base_registry_signaling_sequence = r

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
