#
# test cases for fields access, etc.
#

import unittest2
import common

import openerp
from openerp.osv import fields

class TestRelatedField(common.TransactionCase):

    def setUp(self):
        super(TestRelatedField, self).setUp()
        self.partner = self.registry('res.partner')
        self.company = self.registry('res.company')

    def test_0_related(self):
        """ test an usual related field """
        # add a related field test_related_company_id on res.partner
        old_columns = self.partner._columns
        self.partner._columns = dict(old_columns)
        self.partner._columns.update({
            'related_company_partner_id': fields.related('company_id', 'partner_id', type='many2one', obj='res.partner'),
        })

        # find a company with a non-null partner_id
        ids = self.company.search(self.cr, self.uid, [('partner_id', '!=', False)], limit=1)
        id = ids[0]

        # find partners that satisfy [('partner_id.company_id', '=', id)]
        company_ids = self.company.search(self.cr, self.uid, [('partner_id', '=', id)])
        partner_ids1 = self.partner.search(self.cr, self.uid, [('company_id', 'in', company_ids)])
        partner_ids2 = self.partner.search(self.cr, self.uid, [('related_company_partner_id', '=', id)])
        self.assertEqual(partner_ids1, partner_ids2)

        # restore res.partner fields
        self.partner._columns = old_columns

    def do_test_company_field(self, field):
        # get a partner with a non-null company_id
        ids = self.partner.search(self.cr, self.uid, [('company_id', '!=', False)], limit=1)
        partner = self.partner.browse(self.cr, self.uid, ids[0])

        # check reading related field
        self.assertEqual(partner[field], partner.company_id)

        # check that search on related field is equivalent to original field
        ids1 = self.partner.search(self.cr, self.uid, [('company_id', '=', partner.company_id.id)])
        ids2 = self.partner.search(self.cr, self.uid, [(field, '=', partner.company_id.id)])
        self.assertEqual(ids1, ids2)

    def test_1_single_related(self):
        """ test a related field with a single indirection like fields.related('foo') """
        # add a related field test_related_company_id on res.partner
        old_columns = self.partner._columns
        self.partner._columns = dict(old_columns)
        self.partner._columns.update({
            'single_related_company_id': fields.related('company_id', type='many2one', obj='res.company'),
        })

        self.do_test_company_field('single_related_company_id')

        # restore res.partner fields
        self.partner._columns = old_columns

    def test_2_related_related(self):
        """ test a related field referring to a related field """
        # add a related field on a related field on res.partner
        old_columns = self.partner._columns
        self.partner._columns = dict(old_columns)
        self.partner._columns.update({
            'single_related_company_id': fields.related('company_id', type='many2one', obj='res.company'),
            'related_related_company_id': fields.related('single_related_company_id', type='many2one', obj='res.company'),
        })

        self.do_test_company_field('related_related_company_id')

        # restore res.partner fields
        self.partner._columns = old_columns

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
