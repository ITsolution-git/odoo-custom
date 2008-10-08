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
import netsvc
from osv import fields, osv
import pooler
from tools.misc import currency

import mx.DateTime
from mx.DateTime import RelativeDateTime, now, DateTime, localtime


class account_report(osv.osv):
    _name = "account.report.report"
    _description = "Account reporting"
#    _color = [
#            ('', ''),
#            ('green','Green'),
#            ('red','Red'),
#            ('pink','Pink'),
#            ('blue','Blue'),
#            ('yellow','Yellow'),
#            ('cyan','Cyan'),
#            ('lightblue','Light Blue'),
#            ('orange','Orange'),
#            ]
#    _style = [
#            ('1','Header 1'),
#            ('2','Header 2'),
#            ('3','Header 3'),
#            ('4','Header 4'),
#            ('5','Normal'),
#            ('6', 'Small'),
#            ]

    def _amount_get(self, cr, uid, ids, field_name, arg, context={}):
        def _calc_credit(*code):
            acc = self.pool.get('account.account')
            acc_id = acc.search(cr, uid, [('code','in',code)])
            return reduce(lambda y,x=0: x.credit+y, acc.browse(cr, uid, acc_id, context),0)
        def _calc_debit(*code):
            acc = self.pool.get('account.account')
            acc_id = acc.search(cr, uid, [('code','in',code)])
            return reduce(lambda y,x=0: x.debit+y, acc.browse(cr, uid, acc_id, context),0)
        def _calc_balance(*code):
            acc = self.pool.get('account.account')
            acc_id = acc.search(cr, uid, [('code','in',code)])
            return reduce(lambda y,x=0: x.balance+y, acc.browse(cr, uid, acc_id, context),0)
        def _calc_report(*code):
            acc = self.pool.get('account.report.report')
            acc_id = acc.search(cr, uid, [('code','in',code)])
            return reduce(lambda y,x=0: x.amount+y, acc.browse(cr, uid, acc_id, context),0)
        result = {}
        for rep in self.browse(cr, uid, ids, context):
            objdict = {
                'debit': _calc_debit,
                'credit': _calc_credit,
                'balance': _calc_balance,
                'report': _calc_report,
            }
            if field_name=='status':
                fld_name = 'expression_status'
            else:
                fld_name = 'expression'
            try:
                val = eval(getattr(rep, fld_name), objdict)
            except:
                val = 0.0
            if field_name=='status':
                if val<-1:
                    result[rep.id] = 'very bad'
                elif val<0:
                    result[rep.id] = 'bad'
                elif val==0:
                    result[rep.id] = 'normal'
                elif val<1:
                    result[rep.id] = 'good'
                else:
                    result[rep.id] = 'excellent'
            else:
                result[rep.id] =  val
        return result

    def onchange_parent_id(self, cr, uid, ids, parent_id):
        v={}
        if parent_id:
            acc=self.pool.get('account.report.report').browse(cr,uid,parent_id)
            v['type']=acc.type
#            if int(acc.style) < 6:
#                v['style'] = str(int(acc.style)+1)
        return {'value': v}

    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'active': fields.boolean('Active'),
        'sequence': fields.integer('Sequence'),
        'code': fields.char('Code', size=64, required=True),
        'type': fields.selection([
            ('fiscal', 'Fiscal statement'),
            ('indicator','Indicator'),
            ('view','View'),
            ('other','Others')],
            'Type', required=True),
        'expression': fields.char('Expression', size=240, required=True),
        'expression_status': fields.char('Status expression', size=240, required=True),
        'parent_id': fields.many2one('account.report.report', 'Parent'),
        'child_ids': fields.one2many('account.report.report', 'parent_id', 'Childs'),
        'note': fields.text('Note'),
        'amount': fields.function(_amount_get, method=True, string='Value'),
        'status': fields.function(_amount_get,
            method=True,
            type="selection",
            selection=[
                ('very bad', 'Very Bad'),
                ('bad', 'Bad'),
                ('normal', ''),
                ('good', 'Good'),
                ('excellent', 'Excellent')
            ],
            string='Status'),
#        'style': fields.selection(_style, 'Style', required=True),
#        'color_font' : fields.selection(_color, 'Font Color', help="Font Color for the report"),
#        'color_back' : fields.selection(_color, 'Back Color')
    }
    _defaults = {
#        'style': lambda *args: '5',
        'active': lambda *args: True,
        'type': lambda *args: 'indicator',
    }

    def name_search(self, cr, user, name, args=None, operator='ilike', context=None, limit=80):
        if not args:
            args=[]
        if not context:
            context={}
        ids = []
        if name:
            ids = self.search(cr, user, [('code','=',name)]+ args, limit=limit, context=context)
            if not ids:
                ids = self.search(cr, user, [('name',operator,name)]+ args, limit=limit, context=context)
        else:
            ids = self.search(cr, user, args, limit=limit, context=context)
        return self.name_get(cr, user, ids, context=context)

    _constraints = [
    #TODO Put an expression to valid expression and expression_status
    ]
    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'The code of the report entry must be unique !')
    ]

account_report()

class account_report_history(osv.osv):

    def _calc_value(self, cr, uid, ids, name, args, context):
        acc_report_id=self.read(cr,uid,ids,['tmp','period_id'])
        tmp_ids={}
        for a in acc_report_id:
            period_val=pooler.get_pool(cr.dbname).get('account.period').read(cr,uid,[a['period_id'][0]])[0]
            period_id=pooler.get_pool(cr.dbname).get('account.period').search(cr,uid,[('date_start','<=',period_val['date_start']),('fiscalyear_id','=',period_val['fiscalyear_id'][0])])
            tmp_ids[a['id']] = pooler.get_pool(cr.dbname).get('account.report.report').read(cr,uid,[a['tmp']],context={'periods':period_id})[0]['amount']
        return tmp_ids

    _name = "account.report.history"
    _description = "Indicator"
    _table = "account_report"
    _auto = False
    _order='name'
    _columns = {
        'period_id': fields.many2one('account.period','Period', readonly=True, select=True),
        'fiscalyear_id': fields.many2one('account.fiscalyear','Fiscal Year', readonly=True, select=True),
        'name': fields.many2one('account.report.report','Indicator', readonly=True, select=True),
        'val': fields.function(_calc_value, method=True, string='Value', readonly=True),
        'tmp' : fields.integer(string='temp',readonly=True)
    }

    def init(self, cr):
        cr.execute('''create or replace view account_report as (select ar.id as tmp,((pr.id*100000)+ar.id) as id,ar.id as name,pr.id as period_id,pr.fiscalyear_id as fiscalyear_id from account_report_report as ar cross join account_period as pr group by ar.id,pr.id,pr.fiscalyear_id)''')

account_report_history()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

