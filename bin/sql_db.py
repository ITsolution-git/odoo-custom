# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
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

__all__ = ['db_connect', 'close_db']

import netsvc
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT, ISOLATION_LEVEL_READ_COMMITTED, ISOLATION_LEVEL_SERIALIZABLE
from psycopg2.psycopg1 import cursor as psycopg1cursor
from psycopg2.pool import PoolError

import psycopg2.extensions

psycopg2.extensions.register_type(psycopg2.extensions.UNICODE)

types_mapping = {
    'date': (1082,),
    'time': (1083,),
    'datetime': (1114,),
}

def unbuffer(symb, cr):
    if symb is None: return None
    return str(symb)

def undecimalize(symb, cr):
    if symb is None: return None
    return float(symb)

for name, typeoid in types_mapping.items():
    psycopg2.extensions.register_type(psycopg2.extensions.new_type(typeoid, name, lambda x, cr: x))
psycopg2.extensions.register_type(psycopg2.extensions.new_type((700, 701, 1700,), 'float', undecimalize))


import tools
from tools.func import wraps
from datetime import datetime as mdt
import threading

import re
re_from = re.compile('.* from "?([a-zA-Z_0-9]+)"? .*$');
re_into = re.compile('.* into "?([a-zA-Z_0-9]+)"? .*$');


def log(msg, lvl=netsvc.LOG_DEBUG):
    logger = netsvc.Logger()
    logger.notifyChannel('sql', lvl, msg)

class Cursor(object):
    IN_MAX = 1000

    def check(f):
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            if self.__closed:
                raise psycopg2.ProgrammingError('Unable to use the cursor after having closing it')
            return f(self, *args, **kwargs)
        return wrapper

    def __init__(self, pool, dbname, serialized=False):
        self.sql_from_log = {}
        self.sql_into_log = {}
        self.sql_log = False
        self.sql_log_count = 0

        self.__closed = True    # avoid the call of close() (by __del__) if an exception
                                # is raised by any of the following initialisations
        self._pool = pool
        self.dbname = dbname
        self._serialized = serialized
        self._cnx = pool.borrow(dsn(dbname))
        self._obj = self._cnx.cursor(cursor_factory=psycopg1cursor)
        self.__closed = False   # real initialisation value
        self.autocommit(False)

        if tools.config['log_level'] in (netsvc.LOG_DEBUG, netsvc.LOG_DEBUG_RPC):
            from inspect import stack
            self.__caller = tuple(stack()[2][1:3])

    def __del__(self):
        if not self.__closed:
            # Oops. 'self' has not been closed explicitly.
            # The cursor will be deleted by the garbage collector,
            # but the database connection is not put back into the connection
            # pool, preventing some operation on the database like dropping it.
            # This can also lead to a server overload.
            if tools.config['log_level'] in (netsvc.LOG_DEBUG, netsvc.LOG_DEBUG_RPC):
                msg = "Cursor not closed explicitly\n"  \
                      "Cursor was created at %s:%s" % self.__caller
                log(msg, netsvc.LOG_WARNING)
            self.close()

    @check
    def execute(self, query, params=None):
        if '%d' in query or '%f' in query:
            log(query, netsvc.LOG_WARNING)
            log("SQL queries mustn't contain %d or %f anymore. Use only %s", netsvc.LOG_WARNING)
            if params:
                query = query.replace('%d', '%s').replace('%f', '%s')

        if self.sql_log:
            now = mdt.now()
        
        try:
            params = params or None
            res = self._obj.execute(query, params)
        except Exception, e:
            log("bad query: %s" % self._obj.query)
            log(e)
            raise

        if self.sql_log:
            log("query: %s" % self._obj.query)
            self.sql_log_count+=1
            res_from = re_from.match(query.lower())
            if res_from:
                self.sql_from_log.setdefault(res_from.group(1), [0, 0])
                self.sql_from_log[res_from.group(1)][0] += 1
                self.sql_from_log[res_from.group(1)][1] += mdt.now() - now
            res_into = re_into.match(query.lower())
            if res_into:
                self.sql_into_log.setdefault(res_into.group(1), [0, 0])
                self.sql_into_log[res_into.group(1)][0] += 1
                self.sql_into_log[res_into.group(1)][1] += mdt.now() - now
        return res

    def print_log(self):
        if not self.sql_log:
            return

        def process(type):
            sqllogs = {'from':self.sql_from_log, 'into':self.sql_into_log}
            if not sqllogs[type]:
                return
            sqllogitems = sqllogs[type].items()
            sqllogitems.sort(key=lambda k: k[1][1])
            sum = 0
            log("SQL LOG %s:" % (type,))
            for r in sqllogitems:
                log("table: %s: %s/%s" %(r[0], str(r[1][1]), r[1][0]))
                sum+= r[1][1]
            log("SUM:%s/%d" % (sum, self.sql_log_count))
            sqllogs[type].clear()
        process('from')
        process('into')
        self.sql_log_count = 0
        self.sql_log = False

    @check
    def close(self):
        if not self._obj:
            return

        self.print_log()

        if not self._serialized:
            self.rollback() # Ensure we close the current transaction.

        self._obj.close()

        # This force the cursor to be freed, and thus, available again. It is
        # important because otherwise we can overload the server very easily
        # because of a cursor shortage (because cursors are not garbage
        # collected as fast as they should). The problem is probably due in
        # part because browse records keep a reference to the cursor.
        del self._obj
        self.__closed = True
        self._pool.give_back(self._cnx)

    @check
    def autocommit(self, on):
        offlevel = [ISOLATION_LEVEL_READ_COMMITTED, ISOLATION_LEVEL_SERIALIZABLE][bool(self._serialized)]
        self._cnx.set_isolation_level([offlevel, ISOLATION_LEVEL_AUTOCOMMIT][bool(on)])
    
    @check
    def commit(self):
        return self._cnx.commit()
    
    @check
    def rollback(self):
        return self._cnx.rollback()

    @check
    def __getattr__(self, name):
        return getattr(self._obj, name)


class ConnectionPool(object):

    def locked(fun):
        @wraps(fun)
        def _locked(self, *args, **kwargs):
            self._lock.acquire()
            try:
                return fun(self, *args, **kwargs)
            finally:
                self._lock.release()
        return _locked


    def __init__(self, maxconn=64):
        self._connections = []
        self._maxconn = max(maxconn, 1)
        self._lock = threading.Lock()
        self._logger = netsvc.Logger()

    def _log(self, msg):
        #self._logger.notifyChannel('ConnectionPool', netsvc.LOG_INFO, msg)
        pass
    def _debug(self, msg):
        #self._logger.notifyChannel('ConnectionPool', netsvc.LOG_DEBUG, msg)
        pass

    @locked
    def borrow(self, dsn):
        self._log('Borrow connection to %s' % (dsn,))

        result = None
        for i, (cnx, used) in enumerate(self._connections):
            if not used and cnx.dsn == dsn:
                self._debug('Existing connection found at index %d' % i)

                self._connections.pop(i)
                self._connections.append((cnx, True))

                result = cnx
                break
        if result:
            return result

        if len(self._connections) >= self._maxconn:
            # try to remove the older connection not used
            for i, (cnx, used) in enumerate(self._connections):
                if not used:
                    self._debug('Removing old connection at index %d: %s' % (i, cnx.dsn))
                    self._connections.pop(i)
                    break
            else:
                # note: this code is called only if the for loop has completed (no break)
                raise PoolError('Connection Pool Full')

        self._debug('Create new connection')
        result = psycopg2.connect(dsn=dsn)
        self._connections.append((result, True))
        return result

    @locked
    def give_back(self, connection):
        self._log('Give back connection to %s' % (connection.dsn,))
        for i, (cnx, used) in enumerate(self._connections):
            if cnx is connection:
                self._connections.pop(i)
                self._connections.append((cnx, False))
                break
        else:
            raise PoolError('This connection does not below to the pool')

    @locked
    def close_all(self, dsn):
        for i, (cnx, used) in tools.reverse_enumerate(self._connections):
            if cnx.dsn == dsn:
                cnx.close()
                self._connections.pop(i)


class Connection(object):
    __LOCKS = {}

    def __init__(self, pool, dbname, unique=False):
        self.dbname = dbname
        self._pool = pool
        self._unique = unique
        if unique:
            if dbname not in self.__LOCKS:
                self.__LOCKS[dbname] = threading.Lock()
            self.__LOCKS[dbname].acquire()

    def __del__(self):
        if self._unique:
            self.__LOCKS[self.dbname].release()

    def cursor(self, serialized=False):
        return Cursor(self._pool, self.dbname, serialized=serialized)

    def serialized_cursor(self):
        return self.cursor(True)


_dsn = ''
for p in ('host', 'port', 'user', 'password'):
    cfg = tools.config['db_' + p]
    if cfg:
        _dsn += '%s=%s ' % (p, cfg)

def dsn(db_name):
    return '%sdbname=%s' % (_dsn, db_name)


_Pool = ConnectionPool(int(tools.config['db_maxconn']))

def db_connect(db_name):
    unique = db_name in ['template1', 'template0']
    return Connection(_Pool, db_name, unique)

def close_db(db_name):
    _Pool.close_all(dsn(db_name))
    tools.cache.clean_caches_for_db(db_name)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

