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

#
# OSV: Objects Services
#

import sys
import inspect
import orm
import openerp.netsvc as netsvc
import openerp.pooler as pooler
import openerp.sql_db as sql_db
import copy
import logging
from psycopg2 import IntegrityError, errorcodes
from openerp.tools.func import wraps
from openerp.tools.translate import translate

# Mapping between openerp module names and their osv classes.
module_class_list = {}

class except_osv(Exception):
    def __init__(self, name, value, exc_type='warning'):
        self.name = name
        self.exc_type = exc_type
        self.value = value
        self.args = (exc_type, name)


class object_proxy(netsvc.Service):
    def __init__(self):
        self.logger = logging.getLogger('web-services')
        netsvc.Service.__init__(self, 'object_proxy', audience='')
        self.exportMethod(self.exec_workflow)
        self.exportMethod(self.execute)

    def check(f):
        @wraps(f)
        def wrapper(self, dbname, *args, **kwargs):
            """ Wraps around OSV functions and normalises a few exceptions
            """

            def tr(src, ttype):
                # We try to do the same as the _(), but without the frame
                # inspection, since we aready are wrapping an osv function
                # trans_obj = self.get('ir.translation') cannot work yet :(
                ctx = {}
                if not kwargs:
                    if args and isinstance(args[-1], dict):
                        ctx = args[-1]
                elif isinstance(kwargs, dict):
                    ctx = kwargs.get('context', {})

                uid = 1
                if args and isinstance(args[0], (long, int)):
                    uid = args[0]

                lang = ctx and ctx.get('lang')
                if not (lang or hasattr(src, '__call__')):
                    return src

                # We open a *new* cursor here, one reason is that failed SQL
                # queries (as in IntegrityError) will invalidate the current one.
                cr = False
                
                if hasattr(src, '__call__'):
                    # callable. We need to find the right parameters to call
                    # the  orm._sql_message(self, cr, uid, ids, context) function,
                    # or we skip..
                    # our signature is f(osv_pool, dbname [,uid, obj, method, args])
                    try:
                        if args and len(args) > 1:
                            obj = self.get(args[1])
                            if len(args) > 3 and isinstance(args[3], (long, int, list)):
                                ids = args[3]
                            else:
                                ids = []
                        cr = sql_db.db_connect(db_name).cursor()
                        return src(obj, cr, uid, ids, context=(ctx or {}))
                    except Exception:
                        pass
                    finally:
                        if cr: cr.close()
                   
                    return False # so that the original SQL error will
                                 # be returned, it is the best we have.

                try:
                    cr = sql_db.db_connect(db_name).cursor()
                    res = translate(cr, name=False, source_type=ttype,
                                    lang=lang, source=src)
                    if res:
                        return res
                    else:
                        return src
                finally:
                    if cr: cr.close()

            def _(src):
                return tr(src, 'code')

            try:
                if not pooler.get_pool(dbname)._ready:
                    raise except_osv('Database not ready', 'Currently, this database is not fully loaded and can not be used.')
                return f(self, dbname, *args, **kwargs)
            except orm.except_orm, inst:
                if inst.name == 'AccessError':
                    self.logger.debug("AccessError", exc_info=True)
                self.abortResponse(1, inst.name, 'warning', inst.value)
            except except_osv, inst:
                self.abortResponse(1, inst.name, inst.exc_type, inst.value)
            except IntegrityError, inst:
                osv_pool = pooler.get_pool(dbname)
                for key in osv_pool._sql_error.keys():
                    if key in inst[0]:
                        self.abortResponse(1, _('Constraint Error'), 'warning',
                                        tr(osv_pool._sql_error[key], 'sql_constraint') or inst[0])
                if inst.pgcode in (errorcodes.NOT_NULL_VIOLATION, errorcodes.FOREIGN_KEY_VIOLATION, errorcodes.RESTRICT_VIOLATION):
                    msg = _('The operation cannot be completed, probably due to the following:\n- deletion: you may be trying to delete a record while other records still reference it\n- creation/update: a mandatory field is not correctly set')
                    self.logger.debug("IntegrityError", exc_info=True)
                    try:
                        errortxt = inst.pgerror.replace('«','"').replace('»','"')
                        if '"public".' in errortxt:
                            context = errortxt.split('"public".')[1]
                            model_name = table = context.split('"')[1]
                        else:
                            last_quote_end = errortxt.rfind('"')
                            last_quote_begin = errortxt.rfind('"', 0, last_quote_end)
                            model_name = table = errortxt[last_quote_begin+1:last_quote_end].strip()
                        model = table.replace("_",".")
                        model_obj = osv_pool.get(model)
                        if model_obj:
                            model_name = model_obj._description or model_obj._name
                        msg += _('\n\n[object with reference: %s - %s]') % (model_name, model)
                    except Exception:
                        pass
                    self.abortResponse(1, _('Integrity Error'), 'warning', msg)
                else:
                    self.abortResponse(1, _('Integrity Error'), 'warning', inst[0])
            except Exception:
                self.logger.exception("Uncaught exception")
                raise

        return wrapper

    def execute_cr(self, cr, uid, obj, method, *args, **kw):
        object = pooler.get_pool(cr.dbname).get(obj)
        if not object:
            raise except_osv('Object Error', 'Object %s doesn\'t exist' % str(obj))
        return getattr(object, method)(cr, uid, *args, **kw)

    @check
    def execute(self, db, uid, obj, method, *args, **kw):
        cr = pooler.get_db(db).cursor()
        try:
            try:
                if method.startswith('_'):
                    raise except_osv('Access Denied', 'Private methods (such as %s) cannot be called remotely.' % (method,))
                res = self.execute_cr(cr, uid, obj, method, *args, **kw)
                if res is None:
                    self.logger.warning('The method %s of the object %s can not return `None` !', method, obj)
                cr.commit()
            except Exception:
                cr.rollback()
                raise
        finally:
            cr.close()
        return res

    def exec_workflow_cr(self, cr, uid, obj, method, *args):
        wf_service = netsvc.LocalService("workflow")
        return wf_service.trg_validate(uid, obj, args[0], method, cr)

    @check
    def exec_workflow(self, db, uid, obj, method, *args):
        cr = pooler.get_db(db).cursor()
        try:
            try:
                res = self.exec_workflow_cr(cr, uid, obj, method, *args)
                cr.commit()
            except Exception:
                cr.rollback()
                raise
        finally:
            cr.close()
        return res


class osv_pool(object):
    """ Model registry for a particular database.

    The registry is essentially a mapping between model names and model
    instances. There is one registry instance per database.

    """

    def __init__(self):
        self._ready = False
        self.obj_pool = {} # model name/model instance mapping
        self._sql_error = {}
        self._store_function = {}
        self._init = True
        self._init_parent = {}

    def init_set(self, cr, mode):
        different = mode != self._init
        if different:
            if mode:
                self._init_parent = {}
            if not mode:
                for o in self._init_parent:
                    self.get(o)._parent_store_compute(cr)
            self._init = mode

        self._ready = True
        return different

    def obj_list(self):
        """ Return the list of model names in this registry."""
        return self.obj_pool.keys()

    def add(self, model_name, model):
        """ Add or replace a model in the registry."""
        self.obj_pool[model_name] = model

    def get(self, name):
        """ Return a model for a given name or None if it doesn't exist."""
        return self.obj_pool.get(name)

    #TODO: pass a list of modules to load
    def instanciate(self, module, cr):
        """ Instanciate all the classes of a given module for a particular db."""

        res = []

        # instanciate classes registered through their constructor
        for klass in module_class_list.get(module, []):
            res.append(klass.createInstance(self, module, cr))

        return res

class osv_base(object):
    """ Base class for openerp models.

    OpenERP models are created by inheriting from this class (although
    not directly; more specifically by inheriting from osv or
    osv_memory). The constructor is called once, usually directly
    after the class definition, e.g.:

        class user(osv):
            ...
        user()

    The system will later instanciate the class once per database (on
    which the class' module is installed).

    """

    def __init__(self, pool, cr):
        """ Initialize a model and make it part of the given registry."""
        pool.add(self._name, self)
        self.pool = pool
        super(osv_base, self).__init__(cr)

    def __new__(cls):
        """ Register this model.

        This doesn't create an instance but simply register the model
        as being part of the module where it is defined.

        TODO make it possible to not even have to call the constructor
        to be registered.

        """

        # Set the module name (e.g. base, sale, accounting, ...) on the class.
        module = cls.__module__.split('.')[0]
        if not hasattr(cls, '_module'):
            cls._module = module

        # Remember which models to instanciate for this module.
        module_class_list.setdefault(cls._module, []).append(cls)

        # Since we don't return an instance here, the __init__
        # method won't be called.
        return None

    #
    # Goal: try to apply inheritance at the instanciation level and
    #       put objects in the pool var
    #
    @classmethod
    def makeInstance(cls, pool, module, cr, attributes):
        parent_names = getattr(cls, '_inherit', None)
        if parent_names:
            if isinstance(parent_names, (str, unicode)):
                name = cls._name or parent_names
                parent_names = [parent_names]
            else:
                name = cls._name

            if not name:
                raise TypeError('_name is mandatory in case of multiple inheritance')

            for parent_name in ((type(parent_names)==list) and parent_names or [parent_names]):
                parent_class = pool.get(parent_name).__class__
                assert pool.get(parent_name), "parent class %s does not exist in module %s !" % (parent_name, module)
                nattr = {}
                for s in attributes:
                    new = copy.copy(getattr(pool.get(parent_name), s))
                    if s == '_columns':
                        # Don't _inherit custom fields.
                        for c in new.keys():
                            if new[c].manual:
                                del new[c]
                    if hasattr(new, 'update'):
                        new.update(cls.__dict__.get(s, {}))
                    elif s=='_constraints':
                        for c in cls.__dict__.get(s, []):
                            exist = False
                            for c2 in range(len(new)):
                                 #For _constraints, we should check field and methods as well
                                 if new[c2][2]==c[2] and (new[c2][0] == c[0] \
                                        or getattr(new[c2][0],'__name__', True) == \
                                            getattr(c[0],'__name__', False)):
                                    # If new class defines a constraint with
                                    # same function name, we let it override
                                    # the old one.
                                    new[c2] = c
                                    exist = True
                                    break
                            if not exist:
                                new.append(c)
                    else:
                        new.extend(cls.__dict__.get(s, []))
                    nattr[s] = new
                cls = type(name, (cls, parent_class), nattr)
        obj = object.__new__(cls)
        obj.__init__(pool, cr)
        return obj


class osv_memory(osv_base, orm.orm_memory):

    @classmethod
    def createInstance(cls, pool, module, cr):
        return cls.makeInstance(pool, module, cr, ['_columns', '_defaults'])


class osv(osv_base, orm.orm):

    @classmethod
    def createInstance(cls, pool, module, cr):
        return cls.makeInstance(pool, module, cr, ['_columns', '_defaults',
            '_inherits', '_constraints', '_sql_constraints'])


def start_object_proxy():
    object_proxy()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

