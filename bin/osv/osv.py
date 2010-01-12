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

import orm
import netsvc
import pooler
import copy
import sys

from psycopg2 import IntegrityError
from netsvc import Logger, LOG_ERROR
from tools.misc import UpdateableDict

from tools.translate import _

module_list = []
module_class_list = {}
class_pool = {}


class except_osv(Exception):
    def __init__(self, name, value, exc_type='warning'):
        self.name = name
        self.exc_type = exc_type
        self.value = value
        self.args = (exc_type, name)


from tools.func import wraps
class osv_pool(netsvc.Service):
   
    def check(f):
        @wraps(f)
        def wrapper(self, dbname, *args, **kwargs):
            try:
                if not pooler.get_pool(dbname)._ready:
                    raise except_osv('Database not ready', 'Currently, this database is not fully loaded and can not be used.')
                return f(self, dbname, *args, **kwargs)
            except orm.except_orm, inst:
                self.abortResponse(1, inst.name, 'warning', inst.value)
            except except_osv, inst:
                self.abortResponse(1, inst.name, inst.exc_type, inst.value)
            except IntegrityError, inst:
                for key in self._sql_error.keys():
                    if key in inst[0]:
                        self.abortResponse(1, _('Constraint Error'), 'warning', _(self._sql_error[key]))
                self.abortResponse(1, 'Integrity Error', 'warning', inst[0])
            except Exception, e:
                import traceback, sys
                tb_s = "".join(traceback.format_exception(*sys.exc_info()))
                logger = Logger()
                logger.notifyChannel('web-services', LOG_ERROR, tb_s)
                raise

        return wrapper


    def __init__(self):
        self._ready = False
        self.obj_pool = {}
        self.module_object_list = {}
        self.created = []
        self._sql_error = {}
        self._store_function = {}
        self._init = True
        self._init_parent = {}
        netsvc.Service.__init__(self, 'object_proxy', audience='')
        self.exportMethod(self.obj_list)
        self.exportMethod(self.exec_workflow)
        self.exportMethod(self.execute)

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
   
    def execute_cr(self, cr, uid, obj, method, *args, **kw):
        object = pooler.get_pool(cr.dbname).get(obj)
        if not object:
            raise except_osv('Object Error', 'Object %s doesn\'t exist' % str(obj))
        return getattr(object, method)(cr, uid, *args, **kw)
    
    @check
    def execute(self, db, uid, obj, method, *args, **kw):
        db, pool = pooler.get_db_and_pool(db)
        cr = db.cursor()
        try:
            try:
                res = pool.execute_cr(cr, uid, obj, method, *args, **kw)
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

    def obj_list(self):
        return self.obj_pool.keys()

    # adds a new object instance to the object pool.
    # if it already existed, the instance is replaced
    def add(self, name, obj_inst):
        if name in self.obj_pool:
            del self.obj_pool[name]
        self.obj_pool[name] = obj_inst

        module = str(obj_inst.__class__)[6:]
        module = module[:len(module)-1]
        module = module.split('.')[0][2:]
        self.module_object_list.setdefault(module, []).append(obj_inst)

    # Return None if object does not exist
    def get(self, name):
        obj = self.obj_pool.get(name, None)
        return obj

    #TODO: pass a list of modules to load
    def instanciate(self, module, cr):
        res = []
        class_list = module_class_list.get(module, [])
        for klass in class_list:
            res.append(klass.createInstance(self, module, cr))
        return res

class osv_base(object):
    def __init__(self, pool, cr):
        pool.add(self._name, self)
        self.pool = pool
        super(osv_base, self).__init__(cr)

    def __new__(cls):
        module = str(cls)[6:]
        module = module[:len(module)-1]
        module = module.split('.')[0][2:]
        if not hasattr(cls, '_module'):
            cls._module = module
        module_class_list.setdefault(cls._module, []).append(cls)
        class_pool[cls._name] = cls
        if module not in module_list:
            module_list.append(cls._module)
        return None

class osv_memory(osv_base, orm.orm_memory):
    #
    # Goal: try to apply inheritancy at the instanciation level and
    #       put objects in the pool var
    #
    def createInstance(cls, pool, module, cr):
        name = getattr(cls, '_name', cls._inherit)
        parent_names = getattr(cls, '_inherit', None)
        if parent_names:
            for parent_name in ((type(parent_names)==list) and parent_names or [parent_names]):
                parent_class = pool.get(parent_name).__class__
                assert pool.get(parent_name), "parent class %s does not exist in module %s !" % (parent_name, module)
                nattr = {}
                for s in ('_columns', '_defaults'):
                    new = copy.copy(getattr(pool.get(parent_name), s))
                    if hasattr(new, 'update'):
                        new.update(cls.__dict__.get(s, {}))
                    else:
                        new.extend(cls.__dict__.get(s, []))
                    nattr[s] = new
                name = getattr(cls, '_name', cls._inherit)
                cls = type(name, (cls, parent_class), nattr)

        obj = object.__new__(cls)
        obj.__init__(pool, cr)
        return obj
    createInstance = classmethod(createInstance)

class osv(osv_base, orm.orm):
    #
    # Goal: try to apply inheritancy at the instanciation level and
    #       put objects in the pool var
    #
    def createInstance(cls, pool, module, cr):
        parent_names = getattr(cls, '_inherit', None)
        if parent_names:
            for parent_name in ((type(parent_names)==list) and parent_names or [parent_names]):
                parent_class = pool.get(parent_name).__class__
                assert pool.get(parent_name), "parent class %s does not exist in module %s !" % (parent_name, module)
                nattr = {}
                for s in ('_columns', '_defaults', '_inherits', '_constraints', '_sql_constraints'):
                    new = copy.copy(getattr(pool.get(parent_name), s))
                    if hasattr(new, 'update'):
                        new.update(cls.__dict__.get(s, {}))
                    else:
                        if s=='_constraints':
                            for c in cls.__dict__.get(s, []):
                                exist = False
                                for c2 in range(len(new)):
                                    if new[c2][2]==c[2]:
                                        new[c2] = c
                                        exist = True
                                        break
                                if not exist:
                                    new.append(c)
                        else:
                            new.extend(cls.__dict__.get(s, []))
                    nattr[s] = new
                name = getattr(cls, '_name', cls._inherit)
                cls = type(name, (cls, parent_class), nattr)
        obj = object.__new__(cls)
        obj.__init__(pool, cr)
        return obj
    createInstance = classmethod(createInstance)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

