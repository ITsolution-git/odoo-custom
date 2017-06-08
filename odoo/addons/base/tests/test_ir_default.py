# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestIrDefault(TransactionCase):

    def test_defaults(self):
        """ check the mechanism of user-defined defaults """
        companyA = self.env.user.company_id
        companyB = companyA.create({'name': 'CompanyB'})
        user1 = self.env.user
        user2 = user1.create({'name': 'u2', 'login': 'u2'})
        user3 = user1.create({'name': 'u3', 'login': 'u3',
                              'company_id': companyB.id,
                              'company_ids': companyB.ids})

        # create some default value for some model
        IrDefault1 = self.env['ir.default']
        IrDefault2 = IrDefault1.sudo(user2)
        IrDefault3 = IrDefault1.sudo(user3)

        # set a default value for all users
        IrDefault1.search([('field_id.model', '=', 'res.partner')]).unlink()
        IrDefault1.set('res.partner', 'ref', 'GLOBAL', user_id=False, company_id=False)
        self.assertEqual(IrDefault1.get_model_defaults('res.partner'), {'ref': 'GLOBAL'},
                         "Can't retrieve the created default value for all users.")
        self.assertEqual(IrDefault2.get_model_defaults('res.partner'), {'ref': 'GLOBAL'},
                         "Can't retrieve the created default value for all users.")
        self.assertEqual(IrDefault3.get_model_defaults('res.partner'), {'ref': 'GLOBAL'},
                         "Can't retrieve the created default value for all users.")

        # set a default value for current company (behavior of 'set default' from debug mode)
        IrDefault1.set('res.partner', 'ref', 'COMPANY', user_id=False, company_id=True)
        self.assertEqual(IrDefault1.get_model_defaults('res.partner'), {'ref': 'COMPANY'},
                         "Can't retrieve the created default value for company.")
        self.assertEqual(IrDefault2.get_model_defaults('res.partner'), {'ref': 'COMPANY'},
                         "Can't retrieve the created default value for company.")
        self.assertEqual(IrDefault3.get_model_defaults('res.partner'), {'ref': 'GLOBAL'},
                         "Unexpected default value for company.")

        # set a default value for current user (behavior of 'set default' from debug mode)
        IrDefault2.set('res.partner', 'ref', 'USER', user_id=True, company_id=True)
        self.assertEqual(IrDefault1.get_model_defaults('res.partner'), {'ref': 'COMPANY'},
                         "Can't retrieve the created default value for user.")
        self.assertEqual(IrDefault2.get_model_defaults('res.partner'), {'ref': 'USER'},
                         "Unexpected default value for user.")
        self.assertEqual(IrDefault3.get_model_defaults('res.partner'), {'ref': 'GLOBAL'},
                         "Unexpected default value for company.")

        # check default values on partners
        default1 = IrDefault1.env['res.partner'].default_get(['ref']).get('ref')
        self.assertEqual(default1, 'COMPANY', "Wrong default value.")
        default2 = IrDefault2.env['res.partner'].default_get(['ref']).get('ref')
        self.assertEqual(default2, 'USER', "Wrong default value.")
        default3 = IrDefault3.env['res.partner'].default_get(['ref']).get('ref')
        self.assertEqual(default3, 'GLOBAL', "Wrong default value.")

    def test_conditions(self):
        """ check user-defined defaults with condition """
        IrDefault = self.env['ir.default']

        # default without condition
        IrDefault.search([('field_id.model', '=', 'res.partner')]).unlink()
        IrDefault.set('res.partner', 'ref', 'X')
        self.assertEqual(IrDefault.get_model_defaults('res.partner'),
                         {'ref': 'X'})
        self.assertEqual(IrDefault.get_model_defaults('res.partner', condition='name=Agrolait'),
                         {})

        # default with a condition
        IrDefault.search([('field_id.model', '=', 'res.partner.title')]).unlink()
        IrDefault.set('res.partner.title', 'shortcut', 'X')
        IrDefault.set('res.partner.title', 'shortcut', 'Mr', condition='name=Mister')
        self.assertEqual(IrDefault.get_model_defaults('res.partner.title'),
                         {'shortcut': 'X'})
        self.assertEqual(IrDefault.get_model_defaults('res.partner.title', condition='name=Miss'),
                         {})
        self.assertEqual(IrDefault.get_model_defaults('res.partner.title', condition='name=Mister'),
                         {'shortcut': 'Mr'})

    def test_invalid(self):
        """ check error cases with 'ir.default' """
        IrDefault = self.env['ir.default']
        with self.assertRaises(ValidationError):
            IrDefault.set('unknown_model', 'unknown_field', 42)
        with self.assertRaises(ValidationError):
            IrDefault.set('res.partner', 'unknown_field', 42)
        with self.assertRaises(ValidationError):
            IrDefault.set('res.partner', 'lang', 'some_LANG')
        with self.assertRaises(ValidationError):
            IrDefault.set('res.partner', 'credit_limit', 'foo')

    def test_removal(self):
        """ check defaults for many2one with their value being removed """
        IrDefault = self.env['ir.default']
        IrDefault.search([('field_id.model', '=', 'res.partner')]).unlink()

        # set a record as a default value
        title = self.env['res.partner.title'].create({'name': 'President'})
        IrDefault.set('res.partner', 'title', title.id)
        self.assertEqual(IrDefault.get_model_defaults('res.partner'), {'title': title.id})

        # delete the record, and check the presence of the default value
        title.unlink()
        self.assertEqual(IrDefault.get_model_defaults('res.partner'), {})
