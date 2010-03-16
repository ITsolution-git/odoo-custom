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
from osv import fields, osv

class idea_post_vote(osv.osv_memory):
    
    _name = "idea.post.vote"
    _description = "Post vote"
    _columns = {
                'vote': fields.selection([('-1', 'Not Voted'), 
                                          ('0', 'Very Bad'), 
                                          ('25', 'Bad'), 
                                          ('50', 'Normal'), 
                                          ('75', 'Good'), 
                                          ('100', 'Very Good') ], 'Post Vote', required=True)
                }
    
    def do_vote(self, cr, uid, ids, context):
        """
        Create idea vote.
        @param cr: the current row, from the database cursor,
        @param uid: the current user’s ID for security checks,
        @param ids: List of Idea Post vote’s IDs.
        @return: Dictionary {}
        """
        vote_obj = self.pool.get('idea.vote')
        for data in self.read(cr, uid, ids):
            score = str(data['vote'])
            dic = {'idea_id': context['active_id'], 'user_id': uid, 'score': score }
            vote = vote_obj.create(cr, uid, dic)
            return {}

idea_post_vote()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

