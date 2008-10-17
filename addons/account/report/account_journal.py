# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2004-2008 TINY SPRL. (http://tiny.be) All Rights Reserved.
#
# $Id$
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################


import time
from report import report_sxw

#
# Use period and Journal for selection or resources
#
class journal_print(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(journal_print, self).__init__(cr, uid, name, context)
        self.localcontext.update( {
            'time': time,
            'lines': self.lines,
            'sum_debit': self._sum_debit,
            'sum_credit': self._sum_credit
        })

    def lines(self, period_id, journal_id, *args):
        self.cr.execute('update account_journal_period set state=%s where journal_id=%d and period_id=%d and state=%s', ('printed',journal_id,period_id,'draft'))
        self.cr.commit()
        self.cr.execute('select id from account_move_line where period_id=%d and journal_id=%d and state<>\'draft\' order by date,id', (period_id, journal_id))
        ids = map(lambda x: x[0], self.cr.fetchall())
        return self.pool.get('account.move.line').browse(self.cr, self.uid, ids)

    def _sum_debit(self, period_id, journal_id):
        self.cr.execute('select sum(debit) from account_move_line where period_id=%d and journal_id=%d and state<>\'draft\'', (period_id, journal_id))
        return self.cr.fetchone()[0] or 0.0

    def _sum_credit(self, period_id, journal_id):
        self.cr.execute('select sum(credit) from account_move_line where period_id=%d and journal_id=%d and state<>\'draft\'', (period_id, journal_id))
        return self.cr.fetchone()[0] or 0.0
report_sxw.report_sxw('report.account.journal.period.print', 'account.journal.period', 'addons/account/report/account_journal.rml', parser=journal_print,header=False)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

