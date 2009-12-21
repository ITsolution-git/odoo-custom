# -*- coding: utf-8 -*-
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

from osv import fields, osv

class res_company(osv.osv):
    _inherit = "res.company"
    _columns = {
        'overdue_msg' : fields.text('Overdue Payments Message', translate=True),
    }

    _defaults = {
        'overdue_msg': lambda *a: 'Would your payment have been carried \
out after this mail was sent, please consider the present one as \
void. Do not hesitate to contact our accounting department'
    }
res_company()

class company_setup(osv.osv_memory):
    """
    Insert Information for a company.
    Wizard asks for:
        * A Company with its partner
        * Insert a suitable message for Overdue Payment Report.
    """
    _name='wizard.company.setup'
    _inherit = 'res.config'

    _columns = {
        'company_id':fields.many2one('res.company','Company',required=True),
        'partner_id':fields.many2one('res.partner','Partner'),
        'overdue_msg': fields.text('Overdue Payment Message'),
    }
    def get_message(self,cr,uid,context={}):
        company =self.pool.get('res.users').browse(cr,uid,[uid],context)[0].company_id
        msg = company.overdue_msg
        phone = company.partner_id.address and (company.partner_id.address[0].phone and ' at ' + str(company.partner_id.address[0].phone) + '.' or '.') or '.'
        msg += str(phone)
        return msg

    _defaults = {
        'company_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr,uid,[uid],c)[0].company_id.id,
        'partner_id': lambda self, cr, uid, c: self.pool.get('res.users').browse(cr,uid,[uid],c)[0].company_id.partner_id.id,
        'overdue_msg': get_message,
    }

    def onchange_company_id(self, cr, uid, ids, company, context=None):
        if not company:
            return {}
        comp_obj = self.pool.get('res.company').browse(cr,uid,company)
        partner_address = comp_obj.partner_id.address
        if partner_address and partner_address[0].phone:
            msg_tail = ' at %s.'%(partner_address[0].phone)
        else:
            msg_tail = '.'

        return {'value': {'overdue_msg': comp_obj.overdue_msg + msg_tail,
                          'partner_id': comp_obj.partner_id.id } }

    def execute(self, cr, uid, ids, context=None):
        content_wiz = self.pool.get('wizard.company.setup')\
            .read(cr,uid,ids,['company_id','overdue_msg'])
        if content_wiz:
            wiz_data = content_wiz[0]
            self.pool.get('res.company').write(
                cr, uid,
                [wiz_data['company_id']],
                {'overdue_msg':wiz_data['overdue_msg']})
company_setup()
