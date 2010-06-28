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

import time

from report import report_sxw

#
# Use period and Journal for selection or resources
#
class journal_print(report_sxw.rml_parse):

    def set_context(self, objects, data, ids, report_type = None):
        new_ids = ids
        if (data['model'] == 'ir.ui.menu'):
            new_ids = 'active_ids' in data['form'] and data['form']['active_ids'] or []
        objects = self.pool.get('account.journal.period').browse(self.cr, self.uid, new_ids)
        import pdb
        pdb.set_trace()
        super(journal_print, self).set_context(objects, data, new_ids, report_type)

    def __init__(self, cr, uid, name, context={}):
        super(journal_print, self).__init__(cr, uid, name, context=context)
        self.localcontext.update( {
            'time': time,
            'lines': self.lines,
            'sum_debit': self._sum_debit,
            'sum_credit': self._sum_credit
        })

    def lines(self, period_id, journal_id, sort_selection='date', *args):
        obj_jperiod = self.pool.get('account.journal.period')
        obj_mline = self.pool.get('account.move.line')
        if type(period_id) == type([]):
            ids_final = []
            for journal in journal_id:
                for period in period_id:
                    ids_journal_period = obj_jperiod.search(self.cr, self.uid, [('journal_id','=',journal), ('period_id','=',period)])
                    if ids_journal_period:
                        self.cr.execute('update account_journal_period set state=%s where journal_id=%s and period_id=%s and state=%s', ('printed',journal,period,'draft'))
                        self.cr.commit()
                        self.cr.execute('select id from account_move_line where period_id=%s and journal_id=%s and state<>\'draft\' order by ('+ sort_selection +'),id', (period, journal))
                        ids = map(lambda x: x[0], self.cr.fetchall())
                        ids_final.append(ids)
            line_ids = []
            for line_id in ids_final:
                a = obj_mline.browse(self.cr, self.uid, line_id)
                line_ids.append(a)
            return line_ids
        self.cr.execute('update account_journal_period set state=%s where journal_id=%s and period_id=%s and state=%s', ('printed',journal_id,period_id,'draft'))
        self.cr.commit()
        self.cr.execute('select id from account_move_line where period_id=%s and journal_id=%s and state<>\'draft\' order by date,id', (period_id, journal_id))
        ids = map(lambda x: x[0], self.cr.fetchall())
        return obj_mline.browse(self.cr, self.uid, ids)

    def _sum_debit(self, period_id, journal_id):
        self.cr.execute('select sum(debit) from account_move_line where period_id=%s and journal_id=%s and state<>\'draft\'', (period_id, journal_id))
        return self.cr.fetchone()[0] or 0.0

    def _sum_credit(self, period_id, journal_id):
        self.cr.execute('select sum(credit) from account_move_line where period_id=%s and journal_id=%s and state<>\'draft\'', (period_id, journal_id))
        return self.cr.fetchone()[0] or 0.0

report_sxw.report_sxw('report.account.journal.period.print', 'account.journal.period', 'addons/account/report/account_journal.rml', parser=journal_print, header=False)
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

