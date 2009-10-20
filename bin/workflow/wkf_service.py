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

import wkf_logs
import workitem
import instance

import netsvc
import pooler

class workflow_service(netsvc.Service):
    def __init__(self, name='workflow', audience='*'):
        netsvc.Service.__init__(self, name, audience)
        self.exportMethod(self.trg_write)
        self.exportMethod(self.trg_delete)
        self.exportMethod(self.trg_create)
        self.exportMethod(self.trg_validate)
        self.exportMethod(self.trg_redirect)
        self.exportMethod(self.trg_trigger)
        self.exportMethod(self.clear_cache)
        self.wkf_on_create_cache={}

    def clear_cache(self, cr, uid):
        self.wkf_on_create_cache[cr.dbname]={}

    def trg_write(self, uid, res_type, res_id, cr):
        ident = (uid,res_type,res_id)
        cr.execute('select id from wkf_instance where res_id=%s and res_type=%s and state=%s', (res_id or None,res_type or None, 'active'))
        for (id,) in cr.fetchall():
            instance.update(cr, id, ident)

    def trg_trigger(self, uid, res_type, res_id, cr):
        cr.execute('select instance_id from wkf_triggers where res_id=%s and model=%s', (res_id,res_type))
        res = cr.fetchall()
        for (instance_id,) in res:
            cr.execute('select %s,res_type,res_id from wkf_instance where id=%s', (uid, instance_id,))
            ident = cr.fetchone()
            instance.update(cr, instance_id, ident)

    def trg_delete(self, uid, res_type, res_id, cr):
        ident = (uid,res_type,res_id)
        instance.delete(cr, ident)

    def trg_create(self, uid, res_type, res_id, cr):
        ident = (uid,res_type,res_id)
        self.wkf_on_create_cache.setdefault(cr.dbname, {})
        if res_type in self.wkf_on_create_cache[cr.dbname]:
            wkf_ids = self.wkf_on_create_cache[cr.dbname][res_type]
        else:
            cr.execute('select id from wkf where osv=%s and on_create=True', (res_type,))
            wkf_ids = cr.fetchall()
            self.wkf_on_create_cache[cr.dbname][res_type] = wkf_ids
        for (wkf_id,) in wkf_ids:
            instance.create(cr, ident, wkf_id)

    def trg_validate(self, uid, res_type, res_id, signal, cr):
        result = False
        ident = (uid,res_type,res_id)
        # ids of all active workflow instances for a corresponding resource (id, model_nam)
        cr.execute('select id from wkf_instance where res_id=%s and res_type=%s and state=%s', (res_id, res_type, 'active'))
        for (id,) in cr.fetchall():
            res2 = instance.validate(cr, id, ident, signal)
            result = result or res2
        return result

    # make all workitems which are waiting for a (subflow) workflow instance
    # for the old resource point to the (first active) workflow instance for
    # the new resource
    def trg_redirect(self, uid, res_type, res_id, new_rid, cr):
        # get ids of wkf instances for the old resource (res_id)
#CHECKME: shouldn't we get only active instances?
        cr.execute('select id, wkf_id from wkf_instance where res_id=%s and res_type=%s', (res_id, res_type))
        for old_inst_id, wkf_id in cr.fetchall():
            # first active instance for new resource (new_rid), using same wkf
            cr.execute(
                'SELECT id '\
                'FROM wkf_instance '\
                'WHERE res_id=%s AND res_type=%s AND wkf_id=%s AND state=%s', 
                (new_rid, res_type, wkf_id, 'active'))
            new_id = cr.fetchone()
            if new_id:
                # select all workitems which "wait" for the old instance
                cr.execute('select id from wkf_workitem where subflow_id=%s', (old_inst_id,))
                for (item_id,) in cr.fetchall():
                    # redirect all those workitems to the wkf instance of the new resource
                    cr.execute('update wkf_workitem set subflow_id=%s where id=%s', (new_id[0], item_id))
workflow_service()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

