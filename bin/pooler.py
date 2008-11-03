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

import sql_db
import osv.osv
import tools
import addons
import netsvc

db_dic = {}
pool_dic = {}


def get_db_and_pool(db_name, force_demo=False, status=None, update_module=False):
    if not status:
        status={}
    if db_name in db_dic:
        db = db_dic[db_name]
    else:
        logger = netsvc.Logger()
        logger.notifyChannel('pooler', netsvc.LOG_INFO, 'Connecting to %s' % (db_name.lower()))
        db = sql_db.db_connect(db_name)
        db_dic[db_name] = db

    if db_name in pool_dic:
        pool = pool_dic[db_name]
    else:
        pool = osv.osv.osv_pool()
        pool_dic[db_name] = pool
        addons.load_modules(db, force_demo, status, update_module)
        cr = db.cursor()
        pool.init_set(cr, False)
        cr.commit()
        cr.close()

        if not update_module:
            import report
            report.interface.register_all(db)
            pool.get('ir.cron')._poolJobs(db.dbname)
    return db, pool


def restart_pool(db_name, force_demo=False, update_module=False):
#   del db_dic[db_name]
    del pool_dic[db_name]
    return get_db_and_pool(db_name, force_demo, update_module=update_module)


def close_db(db_name):
    if db_name in db_dic:
        db_dic[db_name].truedb.close()
        del db_dic[db_name]
    if db_name in pool_dic:
        del pool_dic[db_name]


def get_db_only(db_name):
    if db_name in db_dic:
        db = db_dic[db_name]
    else:
        db = sql_db.db_connect(db_name)
        db_dic[db_name] = db
    return db


def get_db(db_name):
#   print "get_db", db_name
    return get_db_and_pool(db_name)[0]


def get_pool(db_name, force_demo=False, status=None, update_module=False):
#   print "get_pool", db_name
    pool = get_db_and_pool(db_name, force_demo, status, update_module)[1]
#   addons.load_modules(db_name, False)
#   if not pool.obj_list():
#       pool.instanciate()
#   print "pool", pool
    return pool
#   return get_db_and_pool(db_name)[1]


def init():
    global db
#   db = get_db_only(tools.config['db_name'])
    sql_db.init()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

