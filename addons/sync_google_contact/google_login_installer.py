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
from tools.translate import _
try:
    import gdata.contacts.service
except ImportError:
    raise osv.except_osv(_('Google Contacts Import Error!'), _('Please install gdata-python-client from http://code.google.com/p/gdata-python-client/downloads/list'))

class google_installer_crm(osv.osv_memory):
	_name = 'google.installer.crm'
	_inherit = 'res.config.installer'
	_columns =	{
		'user': fields.char('Google Username', size=64, required=True),
		'password': fields.char('Google Password', size=64)
	}
	
	def google_login(self, user, password, type='group', context=None):
		gd_client = gdata.contacts.service.ContactsService()
		try:    
			gd_client.ClientLogin(user, password,gd_client.source)
		except Exception:
			return False
		return gd_client
	
	def login(self, cr, uid, ids, context=None):
		data = self.read(cr, uid, ids)[0]
		user = data['user']
		password = data['password']
		if self.google_login(user, password):
			res = {
                   'gmail_user': user,
                   'gmail_password': password
            }
			self.pool.get('res.users').write(cr, uid, uid, res, context=context)
		else:
			raise osv.except_osv(_('Error'), _("Authentication failed! Check the user and password !"))
		return {}
	
google_installer_crm()
