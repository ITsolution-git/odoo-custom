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

from openerp.osv import osv, fields
from tools.translate import _

class note_stage(osv.osv):
    """ Category of Note """
    _name = "note.stage"
    _description = "Note Stage"
    _columns = {
        'name': fields.char('Category Name', size=64, required=True),
        'sequence': fields.integer('Sequence', help="Used to order the note stages"),
        'user_id': fields.many2one('res.users', 'Owner', help="Owner of the note stage.", required=True, readonly=True),
        'fold': fields.boolean('Folded'),
    }
    _order = 'sequence asc'
    _defaults = {
        'fold': 0,
        'user_id': lambda self, cr, uid, ctx: uid,
        'sequence' : 1,
    }

class note_note(osv.osv):
    """ Note """
    _name = 'note.note'
    _inherit = ['mail.thread','pad.common']
    _pad_fields = ['note_pad']
    _description = "Note"

    def _set_note_first_line(self, cr, uid, id, name, value, args, context=None):
        return self.write(cr, uid, [id], {'note': value}, context=context)

    def _get_note_first_line(self, cr, uid, ids, name, args, context=None):
        res = {}
        for note in self.browse(cr, uid, ids, context=context):
            res[note.id] = (note.note or '').strip().split('\n')[0]
        return res

    def _get_default_stage_id(self,cr,uid,context=None):
        ids = self.pool.get('note.stage').search(cr,uid,[('user_id','=',uid)])
        return ids and ids[0] or False

    def _read_group_stage_ids(self, cr, uid, ids, domain, read_group_order=None, access_rights_uid=None, context=None):
        access_rights_uid = access_rights_uid or uid
        stage_obj = self.pool.get('note.stage')

        # only show stage groups not folded and owned by user
        search_domain = [('fold', '=', False),('user_id', '=', uid)]

        stage_ids = stage_obj._search(cr, uid, search_domain, order=self._order, access_rights_uid=access_rights_uid, context=context)
        result = stage_obj.name_get(cr, access_rights_uid, stage_ids, context=context)

        fold = {}
        for stage in stage_obj.browse(cr, access_rights_uid, stage_ids, context=context):
            fold[stage.id] = stage.fold or False
        return result, fold

    _columns = {
        'name': fields.function(_get_note_first_line, fnct_inv=_set_note_first_line, string='Note Summary', type="text"),
        'note': fields.text('Pad Content'),
        'note_pad_url': fields.char('Pad Url', size=250),
        'sequence': fields.integer('Sequence'),
        'stage_id': fields.many2one('note.stage', 'Stage'),
        'active': fields.boolean('Active'),
        'color': fields.integer('Color Index'),
        # to be replaced by message_follower_ids
        'follower_ids': fields.many2many('res.users', 'mail_subscription', 'res_id', 'user_id', 'Followers')
    }

    _defaults = {
        'active' : 1,
        'stage_id' : _get_default_stage_id,
        'note_pad_url': lambda self, cr, uid, context: self.pad_generate_url(cr, uid, context),
    }
    _order = 'sequence asc'
    _group_by_full = {
        'stage_id' : _read_group_stage_ids,
    }
