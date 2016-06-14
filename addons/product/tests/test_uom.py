# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import TransactionCase


class TestUom(TransactionCase):

    def setUp(self):
        super(TestUom, self).setUp()
        self.uom_gram = self.env.ref('product.product_uom_gram')
        self.uom_kgm = self.env.ref('product.product_uom_kgm')
        self.uom_ton = self.env.ref('product.product_uom_ton')
        self.uom_unit = self.env.ref('product.product_uom_unit')
        self.uom_dozen = self.env.ref('product.product_uom_dozen')
        self.categ_unit_id = self.ref('product.product_uom_categ_unit')

    def test_10_conversion(self):
        qty = self.uom_gram._compute_quantity(1020000, self.uom_ton)
        self.assertEquals(qty, 1.02, "Converted quantity does not correspond.")

        price = self.uom_gram._compute_price(2, self.uom_ton)
        self.assertEquals(price, 2000000.0, "Converted price does not correspond.")

        # If the conversion factor for Dozens (1/12) is not stored with sufficient precision,
        # the conversion of 1 Dozen into Units will give e.g. 12.00000000000047 Units
        # and the Unit rounding will round that up to 13.
        # This is a partial regression test for rev. 311c77bb, which is further improved
        # by rev. fa2f7b86.
        qty = self.uom_dozen._compute_quantity(1, self.uom_unit)
        self.assertEquals(qty, 12.0, "Converted quantity does not correspond.")

        # Regression test for side-effect of commit 311c77bb - converting 1234 Grams
        # into Kilograms should work even if grams are rounded to 1.
        self.uom_gram.write({'rounding': 1})
        qty = self.uom_gram._compute_quantity(1234, self.uom_kgm)
        self.assertEquals(qty, 1.234, "Converted quantity does not correspond.")

    def test_20_rounding(self):
        product_uom = self.env['product.uom'].create({
            'name': 'Score',
            'factor_inv': 20,
            'uom_type': 'bigger',
            'rounding': 1.0,
            'category_id': self.categ_unit_id
        })

        qty = self.uom_unit._compute_quantity(2, product_uom)
        self.assertEquals(qty, 1, "Converted quantity should be rounded up.")
