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

pool_dic = {}

def get_db_and_pool(db_name, force_demo=False, status=None, update_module=False, pooljobs=True):
    if not status:
        status={}

    db = get_db_only(db_name)

    if db_name in pool_dic:
        pool = pool_dic[db_name]
    else:
        import addons
        import osv.osv
        pool = osv.osv.osv_pool()
        pool_dic[db_name] = pool

        try:
            addons.load_modules(db, force_demo, status, update_module)
        except Exception:
            del pool_dic[db_name]
            raise

        cr = db.cursor()
        try:
            pool.init_set(cr, False)
            pool.get('ir.actions.report.xml').register_all(cr)
            cr.commit()
        finally:
            cr.close()

        if pooljobs:
            pool.get('ir.cron').restart(db.dbname)
    return db, pool


def restart_pool(db_name, force_demo=False, status=None, update_module=False):
    if db_name in pool_dic:
        del pool_dic[db_name]
    return get_db_and_pool(db_name, force_demo, status, update_module=update_module)


def get_db_only(db_name):
    # ATTENTION:
    # do not put this import outside this function
    # sql_db must not be loaded before the logger is initialized.
    # sql_db import psycopg2.tool which create a default logger if there is not.
    # this resulting of having the logs outputed twice...
    import sql_db
    db = sql_db.db_connect(db_name)
    return db


def get_db(db_name):
    return get_db_and_pool(db_name)[0]


def get_pool(db_name, force_demo=False, status=None, update_module=False):
    pool = get_db_and_pool(db_name, force_demo, status, update_module)[1]
    return pool

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
