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
import datetime

try:
    import gdata
    import gdata.contacts.service
    import gdata.contacts
except ImportError:
    raise osv.except_osv(_('Google Contacts Import Error!'), _('Please install gdata-python-client from http://code.google.com/p/gdata-python-client/downloads/list'))
from osv import fields
from osv import osv
from tools.translate import _
from import_google import google_import


class google_login_contact(osv.osv_memory):
    _inherit = 'google.login'
    
    def _get_next_action(self, cr, uid, context=None):
        data_obj = self.pool.get('ir.model.data')
        data_id = data_obj._get_id(cr, uid, 'import_google', 'view_synchronize_google_contact_import_form')
        view_id = False
        if context.get('contact'):
             data_id = data_obj._get_id(cr, uid, 'import_google', 'view_synchronize_google_contact_import_form')
        if  context.get('calendar'):
             data_id = data_obj._get_id(cr, uid, 'import_google', 'view_synchronize_google_calendar_import_form')     
        if data_id:
            view_id = data_obj.browse(cr, uid, data_id, context=context).res_id
        value = {
            'name': _('Import google'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'synchronize.google.import',
            'view_id': False,
            'context': context,
            'views': [(view_id, 'form')],
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
        return value
    
google_login_contact()

class synchronize_google(osv.osv_memory):
    _name = 'synchronize.google.import'

    def _get_group(self, cr, uid, context=None):
        user_obj = self.pool.get('res.users').browse(cr, uid, uid)
        google=self.pool.get('google.login')
        if not user_obj.gmail_user or not user_obj.gmail_password:
            raise osv.except_osv(_('Warning !'), _("No Google Username or password Defined for user.\nPlease define in user view"))
        gd_client = google.google_login(user_obj.gmail_user,user_obj.gmail_password,type='group')
        if not gd_client:
            raise osv.except_osv(_('Error'), _("Authentication fail check the user and password !"))

        res = []
        query = gdata.contacts.service.GroupsQuery(feed='/m8/feeds/groups/default/full')
        if gd_client:
            groups = gd_client.GetFeed(query.ToUri())
            for grp in groups.entry:
                res.append((grp.id.text, grp.title.text))
        res.append(('all','All Groups'))
        return res

    def _get_calendars(self, cr, uid, context=None):
        user_obj = self.pool.get('res.users').browse(cr, uid, uid)
        google = self.pool.get('google.login')
        res = []
        try:
            gd_client = google.google_login(user_obj.gmail_user, user_obj.gmail_password, type='calendar')
            calendars = gd_client.GetAllCalendarsFeed()
            for cal in calendars.entry:
                res.append((cal.id.text, cal.title.text))
        except Exception, e:
            raise osv.except_osv('Error !', e.args[0].get('body'))
        res.append(('all', 'All Calendars'))
        return res

    _columns = {
        'create_partner': fields.selection([('create_all','Create partner for each contact'),('create_address','Import only address')],'Options'),
        'customer': fields.boolean('Customer', help="Check this box to set newly created partner as Customer."),
        'supplier': fields.boolean('Supplier', help="Check this box to set newly created partner as Supplier."),
        'group_name': fields.selection(_get_group, "Group Name", size=32,help="Choose which group to import, By default it takes all."),
        'calendar_name': fields.selection(_get_calendars, "Calendar Name", size=32),
     }

    _defaults = {
        'create_partner': 'create_all',
        'group_name': 'all',
        'calendar_name': 'all',
    }

    def import_google(self, cr, uid, ids, context=None):
        if context == None:
            context = {}
        if not ids:
            return {'type': 'ir.actions.act_window_close'}
        obj = self.browse(cr, uid, ids, context=context)[0]
        cust = obj.customer
        sup = obj.supplier
        tables=[]
        user_obj = self.pool.get('res.users').browse(cr, uid, uid)
        
        gmail_user = user_obj.gmail_user
        gmail_pwd = user_obj.gmail_password
        google = self.pool.get('google.login')
        if not gmail_user or not gmail_pwd:
            raise osv.except_osv(_('Error'), _("Invalid login detail !\n Specify Username/Password."))
        
        if context.get('contact'):
            gd_client = google.google_login(gmail_user, gmail_pwd, type='contact')
            if not gd_client:
                raise osv.except_osv(_('Error'), _("Please specify correct user and password !"))        
            if obj.group_name not in ['all']:
                query = gdata.contacts.service.ContactsQuery()
                query.group = obj.group_name
                contact = gd_client.GetContactsFeed(query.ToUri())
            else:
                contact = gd_client.GetContactsFeed()
            if obj.create_partner=='create_all':
                tables.append('Contact')    
            else:    
                tables.append('Address')
            context.update({'gd_client':contact,
                           'client':gd_client,
                            'table':tables,
                            'customer':cust,
                            'supplier':sup})
              
        elif context.get('calendar'):
            tables.append('Events')
            current_rec = self.browse(cr, uid, ids, context=context)
            calendars = False
            for rec in current_rec:
                if rec.calendar_name != 'all':
                    calendars = [rec.calendar_name]
                else:
                    calendars = map(lambda x: x[0], [cal for cal in self._get_calendars(cr, uid, context) if cal[0] != 'all'])
            context.update({'user': gmail_user,
                        'password': gmail_pwd,
                        'calendars': calendars,
                        'instance': 'calendar'})
     
        imp = google_import(self, cr, uid,'import_google' , "synchronize_google", gmail_user, context)
        imp.set_table_list(tables)
        imp.start()            
        return context

synchronize_google()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
