# -*- encoding: utf-8 -*-
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

from osv import osv, fields
from tools import cache
import pooler


class decimal_precision(osv.osv):
    _name = 'decimal.precision'
    _columns = {
        'name': fields.char('Usage', size=50, required=True),
        'digits': fields.integer('Digits', required=True),
    }
    _defaults = {
        'digits': lambda *a : 2,
    }

    _sql_constraints = [
        ('name_uniq', 'unique (name)', """The Usage of the decimal precision must be unique!"""),
    ]

    @cache(skiparg=3)
    def precision_get(self, cr, uid, application):
        cr.execute('select digits from decimal_precision where name=%s', (application,))
        res = cr.fetchone()
        return res and res[0] or 2

    def write(self, cr, uid, ids, data, *args, **argv):
        res = super(decimal_precision, self).write(cr, uid, ids, data, *args, **argv)
        for obj in self.pool.obj_list():
            for colname,col in self.pool.get(obj)._columns.items():
                if isinstance(col, fields.float):
                    col.digits_change(cr)
        return res

decimal_precision()


def get_precision(application):
    def change_digit(cr):
        return pooler.get_pool(cr.dbname).get('decimal.precision').precision_get(cr, 1, application)
    return change_digit


