# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012-today OpenERP SA (<http://www.openerp.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################

from openerp.osv import osv, fields
from openerp.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.translate import _

from datetime import datetime, timedelta

def now(**kwargs):
    dt = datetime.now() + timedelta(**kwargs)
    return dt.strftime(DEFAULT_SERVER_DATETIME_FORMAT)


class res_users(osv.osv):
    _inherit = 'res.users'

    def reset_password(self, cr, uid, login, context=None):
        """ retrieve the user corresponding to login (login or email),
            and reset their password
        """
        user_ids = self.search(cr, uid, [('login', '=', login)], context=context)
        if not user_ids:
            user_ids = self.search(cr, uid, [('email', '=', login)], context=context)
        if len(user_ids) != 1:
            raise Exception('Reset password: invalid username or email')
        return self.action_reset_password(cr, uid, user_ids, context=context)

    def action_reset_password(self, cr, uid, ids, context=None):
        """ create signup token for each user, and send their signup url by email """
        # prepare reset password signup
        res_partner = self.pool.get('res.partner')
        partner_ids = [user.partner_id.id for user in self.browse(cr, uid, ids, context)]
        res_partner.signup_prepare(cr, uid, partner_ids, expiration=now(days=+1), context=context)

        # send email to users with their signup url
        template = self.pool.get('ir.model.data').get_object(cr, uid, 'auth_reset_password', 'reset_password_email')
        assert template._name == 'email.template'
        for user in self.browse(cr, uid, ids, context):
            if not user.email:
                raise osv.except_osv(_("Cannot send email: user has no email address."), user.name)
            msg_id = None
            msg_id = self.pool.get('email.template').send_mail(cr, uid, template.id, user.id, context=context)
            if not msg_id:
                raise osv.except_osv(_("The email to reset the password has not been sent. Configure the outgoing server and retry resetting the password"), "")
            else :
                warning = {
                    'title': _("Reset Password"),
                    'message': _("An email has been sent to %s, the user will be able to change his password using the link provided in the email. The old password is still valid until the user changes his password.")% user.email
                }
                return {'warning':warning}
        return True
