##############################################################################
#
# Copyright (c) 2005-2006 TINY SPRL. (http://tiny.be) All Rights Reserved.
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

from osv import fields, osv

class olap_load_column(osv.osv_memory):
    _name = "olap.load.column"
    _description = "Olap Load Column"

    def get_table_data(self, cr, uid, ids, context={}):
        """
        This function load column
        @param cr: the current row, from the database cursor,
        @param uid: the current user\'s ID for security checks,
        @param ids: List of load column,
        @return: dictionary of database columns window on give id

        """
        data = context and context.get('active_id', False) or False
        ids_cols = self.pool.get('olap.database.columns').search(cr, uid,\
                             ([('table_id','=',data)]),context={})
        model_data_ids = self.pool.get('ir.model.data').search(cr,uid,\
                        [('model','=','ir.ui.view'),\
                    ('name','=','view_olap_database_columns_form')],context={})
        resource_id = self.pool.get('ir.model.data').read(cr,uid,\
                                model_data_ids,fields=['res_id'])[0]['res_id']
        return {
            'domain': "[('id','in', ["+','.join(map(str,ids_cols))+"])]",
            'name': 'Database Columns',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'olap.database.columns',
            'views': [(False,'tree'),(resource_id,'form')],
            'type': 'ir.actions.act_window',
        }
    _columns = {

            }

olap_load_column()

# vim: ts=4 sts=4 sw=4 si et