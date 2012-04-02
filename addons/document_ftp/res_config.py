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
from tools import config
from lxml import etree

class documnet_ftp_configuration(osv.osv_memory):
    _name = 'knowledge.configuration'
    _inherit = 'knowledge.configuration'
    _columns = {
        'server_address_port': fields.char('Server address/IP and port',size=128,
                           help ="""It assign server address/IP and port."""),               
    }
    

    _defaults = {
        'server_address_port': config.get('ftp_server_host', 'localhost') + ':' + config.get('ftp_server_port', '8021'),
    }
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: