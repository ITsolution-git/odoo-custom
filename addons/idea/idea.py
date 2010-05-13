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

from osv import osv, fields

VoteValues = [('-1', 'Not Voted'), ('0', 'Very Bad'), ('25', 'Bad'), \
              ('50', 'Normal'), ('75', 'Good'), ('100', 'Very Good') ]
DefaultVoteValue = '50'

class idea_category(osv.osv):
    """ Category of Idea """

    _name = "idea.category"
    _description = "Category for an idea"

    _columns = {
        'name': fields.char('Category', size=64, required=True),
        'summary': fields.text('Summary'),
        'parent_id': fields.many2one('idea.category', 'Parent Categories', ondelete='set null'),
        'child_ids': fields.one2many('idea.category', 'parent_id', 'Child Categories')
    }
    _sql_constraints = [
        ('name', 'unique(parent_id,name)', 'The name of the category must be unique' )
    ]
    _order = 'parent_id,name asc'

idea_category()


class idea_idea(osv.osv):
    """ Idea """
    _name = 'idea.idea'
    _rec_name = 'title'

    def _vote_avg_compute(self, cr, uid, ids, name, arg, context = None):

        """ compute average for voting
         @param cr: the current row, from the database cursor,
         @param uid: the current user’s ID for security checks,
         @param ids: List of voting’s IDs
         @return: dictionay of Idea """

        if not ids:
            return {}

        sql = """SELECT i.id, avg(v.score::integer)
                   FROM idea_idea i LEFT OUTER JOIN idea_vote v ON i.id = v.idea_id
                    WHERE i.id = ANY(%s)
                    GROUP BY i.id
                """

        cr.execute(sql, (ids,))
        return dict(cr.fetchall())

    def _vote_count(self, cr, uid, ids, name, arg, context=None):

        """ count number of vote
         @param cr: the current row, from the database cursor,
         @param uid: the current user’s ID for security checks,
         @param ids: List of voting count’s IDs
         @return: dictionay of Idea """

        if not ids:
            return {}

        sql = """SELECT i.id, COUNT(1)
                   FROM idea_idea i LEFT OUTER JOIN idea_vote v ON i.id = v.idea_id
                    WHERE i.id = ANY(%s)
                    GROUP BY i.id
                """

        cr.execute(sql, (ids,))
        return dict(cr.fetchall())

    def _comment_count(self, cr, uid, ids, name, arg, context=None):

        """ count number of comment
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of comment’s IDs
        @return: dictionay of Idea """

        if not ids:
            return {}

        sql = """SELECT i.id, COUNT(1)
                   FROM idea_idea i LEFT OUTER JOIN idea_comment c ON i.id = c.idea_id
                    WHERE i.id = ANY(%s)
                    GROUP BY i.id
                """

        cr.execute(sql, (ids,))
        return dict(cr.fetchall())

    def _vote_read(self, cr, uid, ids, name, arg, context = None):

        """ Read Vote
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of vote read’s IDs """

        res = {}
        for id in ids:
            res[id] = '-1'
        vote_obj = self.pool.get('idea.vote')
        votes_ids = vote_obj.search(cr, uid, [('idea_id', 'in', ids), ('user_id', '=', uid)])
        vote_obj_id = vote_obj.browse(cr, uid, votes_ids, context)

        for vote in vote_obj_id:
            res[vote.idea_id.id] = vote.score
        return res

    def _vote_save(self, cr, uid, id, field_name, field_value, arg, context = None):

        """ save Vote
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of vote save’s IDs """

        vote_obj = self.pool.get('idea.vote')
        vote = vote_obj.search(cr, uid, [('idea_id', '=', id), ('user_id', '=', uid)])
        textual_value = str(field_value)

        if vote:
            if int(field_value) >= 0:
                vote_obj.write(cr, uid, vote, {'score': textual_value })
            else:
                vote_obj.unlink(cr, uid, vote)
        else:
            if int(field_value) >= 0:
                vote_obj.create(cr, uid, {'idea_id': id, 'user_id': uid, 'score': textual_value })

    _columns = {
        'user_id': fields.many2one('res.users', 'Creator', required=True, readonly=True),
        'title': fields.char('Idea Summary', size=64, required=True),
        'description': fields.text('Description', required=True, help='Content of the idea'),
        'comment_ids': fields.one2many('idea.comment', 'idea_id', 'Comments'),
        'create_date': fields.datetime('Creation date', readonly=True),
        'vote_ids': fields.one2many('idea.vote', 'idea_id', 'Vote'),
        'my_vote': fields.function(_vote_read, fnct_inv = _vote_save, \
                string="My Vote", method=True, type="selection", selection=VoteValues),
        'vote_avg': fields.function(_vote_avg_compute, method=True, string="Average Score", type="float"),
        'count_votes': fields.function(_vote_count, method=True, string="Count of votes", type="integer"),
        'count_comments': fields.function(_comment_count, method=True, \
                                 string="Count of comments", type="integer"),
        'category_id': fields.many2one('idea.category', 'Category', required=True),
        'state': fields.selection([('draft', 'Draft'), ('open', 'Opened'), \
                                ('close', 'Accepted'), ('cancel', 'Cancelled')], \
                                 'State', readonly=True,
                                  help='When the Idea is created the state is \'Draft\'.\n It is \
                                   opened by the user, the state is \'Opened\'.\
                                    \nIf the idea is accepted, the state is \'Accepted\'.'),
        'stat_vote_ids': fields.one2many('idea.vote.stat', 'idea_id', 'Statistics', readonly=True),
        'date': fields.date('Creation date'),
        'vote_user': fields.integer('Maximum Vote per User',
                     help="Set to one if  you require only one Vote per user"),
    }

    _defaults = {
        'user_id': lambda self,cr,uid,context: uid,
        'my_vote': lambda *a: '-1',
        'state': lambda *a: 'draft',
        'vote_user': lambda * a: 1,        
    }
    _order = 'id desc'

    def idea_cancel(self, cr, uid, ids):
        self.write(cr, uid, ids, { 'state': 'cancel' })
        return True

    def idea_open(self, cr, uid, ids):
        self.write(cr, uid, ids, { 'state': 'open' })
        return True

    def idea_close(self, cr, uid, ids):
        self.write(cr, uid, ids, { 'state': 'close' })
        return True

    def idea_draft(self, cr, uid, ids):
        self.write(cr, uid, ids, { 'state': 'draft' })
        return True
idea_idea()

class idea_comment(osv.osv):
    """ Apply Idea for Comment """

    _name = 'idea.comment'
    _description = 'Comments'
    _rec_name = 'content'

    _columns = {
        'idea_id': fields.many2one('idea.idea', 'Idea', required=True, ondelete='cascade'),
        'user_id': fields.many2one('res.users', 'User', required=True),
        'content': fields.text('Comment', required=True),
        'create_date': fields.datetime('Creation date', readonly=True),
    }
    
    _defaults = {
        'user_id': lambda self, cr, uid, context: uid
    }

    _order = 'id desc'

idea_comment()


class idea_vote(osv.osv):
    """ Apply Idea for Vote """

    _name = 'idea.vote'
    _description = 'Vote for Idea'
    _rec_name = 'score'

    _columns = {
        'user_id': fields.many2one('res.users', 'User'),
        'idea_id': fields.many2one('idea.idea', 'Idea', required=True, ondelete='cascade'),
        'score': fields.selection(VoteValues, 'Score', required=True),
    }
    _defaults = {
        'score': lambda *a: DefaultVoteValue,
    }

idea_vote()

class idea_vote_stat(osv.osv):
    """ Idea votes Statistics """

    _name = 'idea.vote.stat'
    _description = 'Idea Votes Statistics'
    _auto = False
    _rec_name = 'idea_id'

    _columns = {
        'idea_id': fields.many2one('idea.idea', 'Idea', readonly=True),
        'score': fields.selection(VoteValues, 'Score', readonly=True),
        'nbr': fields.integer('Number of Votes', readonly=True),
    }

    def init(self, cr):
        """
        initialize the sql view for the stats

        cr -- the cursor
        """
        cr.execute("""
            CREATE OR REPLACE VIEW idea_vote_stat AS (
                SELECT
                    MIN(v.id) AS id,
                    i.id AS idea_id,
                    v.score,
                    COUNT(1) AS nbr
                FROM
                    idea_vote v
                    LEFT JOIN idea_idea i ON (v.idea_id = i.id)
                GROUP BY
                    i.id, v.score, i.id )
        """)

idea_vote_stat()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

