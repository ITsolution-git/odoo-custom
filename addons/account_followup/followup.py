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

from osv import fields, osv

class followup(osv.osv):
    _name = 'account_followup.followup'
    _description = 'Follow-Ups'
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'description': fields.text('Description'),
        'followup_line': fields.one2many('account_followup.followup.line', 'followup_id', 'Follow-Up'),
        'company_id': fields.many2one('res.company', 'Company'),
    }
followup()

class followup_line(osv.osv):
    _name = 'account_followup.followup.line'
    _description = 'Follow-Ups Criteria'
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'sequence': fields.integer('Sequence'),
        'delay': fields.integer('Days of delay'),
        'start': fields.selection([('days','Net Days'),('end_of_month','End of Month')], 'Type of Term', size=64, required=True),
        'followup_id': fields.many2one('account_followup.followup', 'Follow Ups', required=True, ondelete="cascade"),
        'description': fields.text('Printed Message', translate=True),
    }
followup_line()

class account_move_line(osv.osv):
    _name = 'account.move.line'
    _inherit = 'account.move.line'
    _columns = {
        'followup_line_id': fields.many2one('account_followup.followup.line', 'Follow-up Level'),
        'followup_date': fields.date('Latest Follow-up'),
    }
account_move_line()


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

