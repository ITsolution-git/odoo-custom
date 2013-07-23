##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2012 OpenERP SA (<http://www.openerp.com>).
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

import simplejson
from lxml import etree
import re
import requests

from openerp.osv import osv
from openerp import SUPERUSER_ID


class base_config_settings(osv.osv):
    _inherit = "base.config.settings"

    def _get_google_scope(self):
        return 'https://www.googleapis.com/auth/drive https://spreadsheets.google.com/feeds'


class config(osv.osv):
    _inherit = 'google.drive.config'

    def write_config_formula(self, cr, uid, attachment_id, spreadsheet_key, model, domain, groupbys, view_id, context=None):
        access_token = self.get_access_token(cr, uid, scope='https://spreadsheets.google.com/feeds', context=context)

        fields = self.pool.get(model).fields_view_get(cr, uid, view_id=view_id, view_type='tree')
        doc = etree.XML(fields.get('arch'))
        display_fields = []
        for node in doc.xpath("//field"):
            if node.get('modifiers'):
                modifiers = simplejson.loads(node.get('modifiers'))
                if not modifiers.get('invisible') and not modifiers.get('tree_invisible'):
                    display_fields.append(node.get('name'))
        fields = " ".join(display_fields)
        domain = domain.replace("'", r"\'").replace('"', "'")
        if groupbys:
            fields = "%s %s" % (groupbys, fields)
            formula = '=oe_read_group("%s";"%s";"%s";"%s")' % (model, fields, groupbys, domain)
        else:
            formula = '=oe_browse("%s";"%s";"%s")' % (model, fields, domain)
        url = self.pool.get('ir.config_parameter').get_param(cr, uid, 'web.base.url')
        dbname = cr.dbname
        user = self.pool['res.users'].read(cr, uid, uid, ['login', 'password'], context=context)
        username = user['login']
        password = user['password']
        if self.pool['ir.module.module'].search_count(cr, SUPERUSER_ID, ['&', ('name', '=', 'auth_crypt'), ('state', '=', 'installed')]) == 1:
            config_formula = '=oe_settings("%s";"%s")' % (url, dbname)
        else:
            config_formula = '=oe_settings("%s";"%s";"%s";"%s")' % (url, dbname, username, password)
        request = '''<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:batch="http://schemas.google.com/gdata/batch"
      xmlns:gs="http://schemas.google.com/spreadsheets/2006">
  <id>https://spreadsheets.google.com/feeds/cells/%s/od6/private/full</id>
  <entry>
    <batch:id>A1</batch:id>
    <batch:operation type="update"/>
    <id>https://spreadsheets.google.com/feeds/cells/%s/od6/private/full/R1C1</id>
    <link rel="edit" type="application/atom+xml"
      href="https://spreadsheets.google.com/feeds/cells/%s/od6/private/full/R1C1"/>
    <gs:cell row="1" col="1" inputValue="%s"/>
  </entry>
  <entry>
    <batch:id>A2</batch:id>
    <batch:operation type="update"/>
    <id>https://spreadsheets.google.com/feeds/cells/%s/od6/private/full/R60C15</id>
    <link rel="edit" type="application/atom+xml"
      href="https://spreadsheets.google.com/feeds/cells/%s/od6/private/full/R60C15"/>
    <gs:cell row="60" col="15" inputValue="%s"/>
  </entry>
</feed>''' % (spreadsheet_key, spreadsheet_key, spreadsheet_key, formula.replace('"', '&quot;'), spreadsheet_key, spreadsheet_key, config_formula.replace('"', '&quot;'))

        requests.post('https://spreadsheets.google.com/feeds/cells/%s/od6/private/full/batch?v=3&access_token=%s' % (spreadsheet_key, access_token), data=request, headers={'content-type': 'application/atom+xml', 'If-Match': '*'})

        description = '''
        formula: %s
        ''' % formula
        if attachment_id:
            self.pool['ir.attachment'].write(cr, uid, attachment_id, {'description': description}, context=context)
        return True

    def set_spreadsheet(self, cr, uid, model, domain, groupbys, view_id, context=None):
        try:
            config_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'google_spreadsheet', 'google_spreadsheet_template')[1]
        except ValueError:
            raise
        config = self.browse(cr, uid, config_id, context=context)
        title = 'Spreadsheet %s' % model
        res = self.copy_doc(cr, uid, 1, config.google_drive_resource_id, title, model, context=context)

        mo = re.search("(key=|/d/)([A-Za-z0-9-_]+)", res['url'])
        if mo:
            key = mo.group(2)

        self.write_config_formula(cr, uid, res.get('id'), key, model, domain, groupbys, view_id, context=context)
        return res
