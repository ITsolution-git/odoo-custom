# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Business Applications
#    Copyright (c) 2012-TODAY OpenERP S.A. <http://openerp.com>
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

from openerp.tests import common


class TestMrpMulticompany(common.TransactionCase):

    def setUp(self):
        super(TestMrpMulticompany, self).setUp()
        cr, uid = self.cr, self.uid

        # Usefull models
        self.ir_model_data = self.registry('ir.model.data')
        self.res_users = self.registry('res.users')
        self.stock_location = self.registry('stock.location')

        model, self.multicompany_user_id = self.ir_model_data.get_object_reference(cr, uid, 'stock', 'multicompany_user')


    def test_00_multicompany_user(self):
        """check no error on getting default mrp.production values in multicompany setting"""
        cr, uid, context = self.cr, self.multicompany_user_id, {}
        fields = ['location_src_id', 'location_dest_id']
        defaults = self.stock_location.default_get(cr, uid, ['location_id', 'location_dest_id', 'type'], context)
        for field in fields:
            print field, uid, defaults
            if defaults.get(field):
                try:
                    self.stock_location.check_access_rule(cr, uid, [defaults[field]], 'read', context)
                except Exception, exc:
                    assert False, "unreadable location %s: %s" % (field, exc)
