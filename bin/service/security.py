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

import pooler
import tools

_uid_cache = {}

def login(db, login, password):
    cr = pooler.get_db(db).cursor()
    cr.execute('select id from res_users where login=%s and password=%s and active', (login.encode('utf-8'), password.encode('utf-8')))
    res = cr.fetchone()
    cr.close()
    if res:
        return res[0]
    else:
        return False

def check_super(passwd):
    if passwd == tools.config['admin_passwd']:
        return True
    else:
        raise Exception('AccessDenied')
    
def check(db, uid, passwd):
    if _uid_cache.get(db, {}).get(uid) == passwd:
        return True
        
    cr = pooler.get_db(db).cursor()
    cr.execute('select count(*) from res_users where id=%s and password=%s', (int(uid), passwd))
    res = cr.fetchone()[0]
    cr.close()
    if not bool(res):
        raise Exception('AccessDenied')
    if res:
        if _uid_cache.has_key(db):
            ulist = _uid_cache[db]
            ulist[uid] = passwd
        else:
            _uid_cache[db] = {uid:passwd}
    return bool(res)

def access(db, uid, passwd, sec_level, ids):
    cr = pooler.get_db(db).cursor()
    cr.execute('select id from res_users where id=%s and password=%s', (uid, passwd))
    res = cr.fetchone()
    cr.close()
    if not res:
        raise Exception('Bad username or password')
    return res[0]

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

