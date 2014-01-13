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
from openerp.osv import fields, osv

class product_template(osv.osv):
    _inherit = "product.template"
    _columns = {
        'email_template_id': fields.many2one('email.template','Product Email Template'),
    }

class account_invoice(osv.Model):
    _inherit = 'account.invoice'

    def invoice_validate(self, cr, uid, ids, context=None):
        for line in self.browse(cr, uid, ids[0], context=context).invoice_line:
            if line.product_id.email_template_id:
                self.pool.get('email.template').send_mail(cr, uid, line.product_id.email_template_id.id, uid, force_send=True, raise_exception=True, context=context)
        return super(account_invoice, self).invoice_validate(cr, uid, ids, context=context)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
