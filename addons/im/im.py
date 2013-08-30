# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import openerp
import openerp.tools.config
import openerp.modules.registry
import openerp.addons.web.http as http
from openerp.addons.web.http import request
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
import datetime
from openerp.osv import osv, fields
import time
import logging
import json
import select

_logger = logging.getLogger(__name__)

def listen_channel(cr, channel_name, handle_message, check_stop=(lambda: False), check_stop_timer=60.):
    """
        Begin a loop, listening on a PostgreSQL channel. This method does never terminate by default, you need to provide a check_stop
        callback to do so. This method also assume that all notifications will include a message formated using JSON (see the
        corresponding notify_channel() method).

        :param db_name: database name
        :param channel_name: the name of the PostgreSQL channel to listen
        :param handle_message: function that will be called when a message is received. It takes one argument, the message
            attached to the notification.
        :type handle_message: function (one argument)
        :param check_stop: function that will be called periodically (see the check_stop_timer argument). If it returns True
            this function will stop to watch the channel.
        :type check_stop: function (no arguments)
        :param check_stop_timer: The maximum amount of time between calls to check_stop_timer (can be shorter if messages
            are received).
    """
    try:
        conn = cr._cnx
        cr.execute("listen " + channel_name + ";")
        cr.commit();
        stopping = False
        while not stopping:
            if check_stop():
                stopping = True
                break
            if select.select([conn], [], [], check_stop_timer) == ([],[],[]):
                pass
            else:
                conn.poll()
                while conn.notifies:
                    message = json.loads(conn.notifies.pop().payload)
                    handle_message(message)
    finally:
        try:
            cr.execute("unlisten " + channel_name + ";")
            cr.commit()
        except:
            pass # can't do anything if that fails

def notify_channel(cr, channel_name, message):
    """
        Send a message through a PostgreSQL channel. The message will be formatted using JSON. This method will
        commit the given transaction because the notify command in Postgresql seems to work correctly when executed in
        a separate transaction (despite what is written in the documentation).

        :param cr: The cursor.
        :param channel_name: The name of the PostgreSQL channel.
        :param message: The message, must be JSON-compatible data.
    """
    cr.commit()
    cr.execute("notify " + channel_name + ", %s", [json.dumps(message)])
    cr.commit()

POLL_TIMER = 30
DISCONNECTION_TIMER = POLL_TIMER + 5
WATCHER_ERROR_DELAY = 10

class LongPollingController(http.Controller):

    @http.route('/longpolling/im/poll', type="json", auth="none")
    def poll(self, last=None, users_watch=None, db=None, uid=None, password=None, uuid=None):
        assert_uuid(uuid)
        if not openerp.evented:
            raise Exception("Not usable in a server not running gevent")
        from openerp.addons.im.watcher import ImWatcher
        if db is not None:
            openerp.service.security.check(db, uid, password)
        else:
            uid = request.session.uid
            db = request.session.db

        registry = openerp.modules.registry.RegistryManager.get(db)
        with registry.cursor() as cr:
            registry.get('im.user').im_connect(cr, uid, uuid=uuid, context=request.context)
            my_id = registry.get('im.user').get_my_id(cr, uid, uuid, request.context)
        num = 0
        while True:
            with registry.cursor() as cr:
                res = registry.get('im.message').get_messages(cr, uid, last, users_watch, uuid=uuid, context=request.context)
            if num >= 1 or len(res["res"]) > 0:
                return res
            last = res["last"]
            num += 1
            ImWatcher.get_watcher(res["dbname"]).stop(my_id, users_watch or [], POLL_TIMER)

    @http.route('/longpolling/im/activated', type="json", auth="none")
    def activated(self):
        return not not openerp.evented

    @http.route('/longpolling/im/gen_uuid', type="json", auth="none")
    def gen_uuid(self):
        import uuid
        return "%s" % uuid.uuid1()

def assert_uuid(uuid):
    if not isinstance(uuid, (str, unicode, type(None))) and uuid != False:
        raise Exception("%s is not a uuid" % uuid)


class im_message(osv.osv):
    _name = 'im.message'

    _order = "date desc"

    _columns = {
        'message': fields.text(string="Message", required=True),
        'from_id': fields.many2one("im.user", "From", required= True, ondelete='cascade'),
        'session_id': fields.many2one("im.session", "Session", required=True, select=True, ondelete='cascade'),
        'to_id': fields.many2many("im.user", "To"),
        'date': fields.datetime("Date", required=True, select=True),
        'technical': fields.boolean("Technical Message"),
    }

    _defaults = {
        'date': lambda *args: datetime.datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
        'technical': False,
    }
    
    def get_messages(self, cr, uid, last=None, users_watch=None, uuid=None, context=None):
        assert_uuid(uuid)
        users_watch = users_watch or []
        session_ids = session_ids or []

        # complex stuff to determine the last message to show
        users = self.pool.get("im.user")
        my_id = users.get_my_id(cr, uid, uuid, context=context)
        c_user = users.browse(cr, openerp.SUPERUSER_ID, my_id, context=context)
        if last:
            if c_user.im_last_received < last:
                users.write(cr, openerp.SUPERUSER_ID, my_id, {'im_last_received': last}, context=context)
        else:
            last = c_user.im_last_received or -1

        # how fun it is to always need to reorder results from read
        mess_ids = self.search(cr, openerp.SUPERUSER_ID, ["&", ['id', '>', last], "|", ['from_id', '=', my_id], ['to_id', 'in', [my_id]]], order="id", context=context)
        mess = self.read(cr, openerp.SUPERUSER_ID, mess_ids, ["id", "message", "from_id", "session_id", "date"], context=context)
        index = {}
        for i in xrange(len(mess)):
            index[mess[i]["id"]] = mess[i]
        mess = []
        for i in mess_ids:
            mess.append(index[i])

        if len(mess) > 0:
            last = mess[-1]["id"]
        users_status = users.read(cr, openerp.SUPERUSER_ID, users_watch, ["im_status"], context=context)
        return {"res": mess, "last": last, "dbname": cr.dbname, "users_status": users_status}

    def post(self, cr, uid, message, to_session_id, uuid=None, context=None):
        assert_uuid(uuid)
        my_id = self.pool.get('im.user').get_my_id(cr, uid, uuid)
        session = self.pool.get('im.session').browse(cr, uid, to_session_id, context)
        to_ids = [x.id for x in session.user_ids if x != my_id]
        self.create(cr, openerp.SUPERUSER_ID, {"message": message, 'from_id': my_id, 'to_id': to_ids}, context=context)
        notify_channel(cr, "im_channel", {'type': 'message', 'receivers': to_user_id})
        return False

class im_session(osv.osv):
    _name = 'im.session'
    _columns = {
        'user_ids': fields.many2many('im.user'),
    }

    # Todo: reuse existing sessions if possible
    def session_get(self, cr, uid, user_to, uuid=None, context=None):
        my_id = self.pool.get("im.user").get_my_id(cr, uid, uuid, context=context)
        session_id = None
        if user_to:
            # FP Note: does the ORM allows something better than this? == on many2many
            sids = self.search(cr, uid, [('user_ids', 'in', [user_to]), ('user_ids', 'in', [my_id])], context=context, limit=1)
            for session in self.browse(cr, uid, sids, context=context):
                if len(session.user_ids) == 2:
                    session_id = session.id
                    break
        if not session_id:
            session_id = self.create(cr, uid, {
                'user_ids': [(6, 0, (user_to, uid))]
            }, context=context)
        return self.read(cr, uid, session_id, context=context)

class im_user(osv.osv):
    _name = "im.user"

    def _im_status(self, cr, uid, ids, something, something_else, context=None):
        res = {}
        current = datetime.datetime.now()
        delta = datetime.timedelta(0, DISCONNECTION_TIMER)
        data = self.read(cr, openerp.SUPERUSER_ID, ids, ["im_last_status_update", "im_last_status"], context=context)
        for obj in data:
            last_update = datetime.datetime.strptime(obj["im_last_status_update"], DEFAULT_SERVER_DATETIME_FORMAT)
            res[obj["id"]] = obj["im_last_status"] and (last_update + delta) > current
        return res

    def search_users(self, cr, uid, text_search, fields, limit, context=None):
        my_id = self.get_my_id(cr, uid, None, context)
        found = self.search(cr, uid, [["name", "ilike", text_search], ["id", "<>", my_id], ["uuid", "=", False]], limit=limit, context=context)
        return self.read(cr, uid, found, fields, context=context)

    def im_connect(self, cr, uid, uuid=None, context=None):
        assert_uuid(uuid)
        return self._im_change_status(cr, uid, True, uuid, context)

    def im_disconnect(self, cr, uid, uuid=None, context=None):
        assert_uuid(uuid)
        return self._im_change_status(cr, uid, False, uuid, context)

    def _im_change_status(self, cr, uid, new_one, uuid=None, context=None):
        assert_uuid(uuid)
        id = self.get_my_id(cr, uid, uuid, context=context)
        current_status = self.read(cr, openerp.SUPERUSER_ID, id, ["im_status"], context=None)["im_status"]
        self.write(cr, openerp.SUPERUSER_ID, id, {"im_last_status": new_one, 
            "im_last_status_update": datetime.datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)}, context=context)
        if current_status != new_one:
            notify_channel(cr, "im_channel", {'type': 'status', 'user': id})
        return True

    def get_my_id(self, cr, uid, uuid=None, context=None):
        assert_uuid(uuid)
        if uuid:
            users = self.search(cr, openerp.SUPERUSER_ID, [["uuid", "=", uuid]], context=None)
        else:
            users = self.search(cr, openerp.SUPERUSER_ID, [["user_id", "=", uid]], context=None)
        my_id = users[0] if len(users) >= 1 else False
        if not my_id:
            my_id = self.create(cr, openerp.SUPERUSER_ID, {"user_id": uid if not uuid else False, "uuid": uuid if uuid else False}, context=context)
        return my_id

    def assign_name(self, cr, uid, uuid, name, context=None):
        assert_uuid(uuid)
        id = self.get_my_id(cr, uid, uuid, context=context)
        self.write(cr, openerp.SUPERUSER_ID, id, {"assigned_name": name}, context=context)
        return True

    def _get_name(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for record in self.browse(cr, uid, ids, context=context):
            res[record.id] = record.assigned_name
            if record.user_id:
                res[record.id] = record.user_id.name
                continue
        return res

    _columns = {
        'name': fields.function(_get_name, type='char', size=200, string="Name", store=True, readonly=True),
        'assigned_name': fields.char(string="Assigned Name", size=200, required=False),
        'image': fields.related('user_id', 'image_small', type='binary', string="Image", readonly=True),
        'user_id': fields.many2one("res.users", string="User", select=True, ondelete='cascade'),
        'uuid': fields.char(string="UUID", size=50, select=True),
        'im_last_received': fields.integer(string="Instant Messaging Last Received Message"),
        'im_last_status': fields.boolean(strint="Instant Messaging Last Status"),
        'im_last_status_update': fields.datetime(string="Instant Messaging Last Status Update"),
        'im_status': fields.function(_im_status, string="Instant Messaging Status", type='boolean'),
    }

    _defaults = {
        'im_last_received': -1,
        'im_last_status': False,
        'im_last_status_update': lambda *args: datetime.datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
    }

    _sql_constraints = [
        ('user_uniq', 'unique (user_id)', 'Only one chat user per OpenERP user.'),
        ('uuid_uniq', 'unique (uuid)', 'Chat identifier already used.'),
    ]
