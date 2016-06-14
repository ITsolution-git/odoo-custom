# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import cgi
import collections
import json
import os.path
import re

from lxml import etree

from odoo.addons.base.ir.ir_qweb import QWebContext, FileSystemLoader
from odoo.modules import get_module_resource
from odoo.tests.common import TransactionCase


class TestQWebTField(TransactionCase):
    def setUp(self):
        super(TestQWebTField, self).setUp()
        self.env_branding = self.env(context={'inherit_branding': True})
        self.engine = self.env_branding['ir.qweb']

    def context(self, values):
        return QWebContext(self.env_branding, values)

    def test_trivial(self):
        field = etree.Element('span', {'t-field': u'company.name'})
        company = self.env['res.company'].create({'name': "My Test Company"})

        result = self.engine.render_node(field, self.context({'company': company}))
        self.assertEqual(
            result,
            '<span data-oe-model="res.company" data-oe-id="%d" '
                  'data-oe-field="name" data-oe-type="char" '
                  'data-oe-expression="company.name">%s</span>' % (
                company.id,
                "My Test Company",
            ),
        )

    def test_i18n(self):
        field = etree.Element('span', {'t-field': u'company.name'})
        s = u"Testing «ταБЬℓσ»: 1<2 & 4+1>3, now 20% off!"
        company = self.env['res.company'].create({'name': s})

        result = self.engine.render_node(field, self.context({'company': company}))
        self.assertEqual(
            result,
            '<span data-oe-model="res.company" data-oe-id="%d" '
                  'data-oe-field="name" data-oe-type="char" '
                  'data-oe-expression="company.name">%s</span>' % (
                company.id,
                cgi.escape(s.encode('utf-8')),
            ),
        )

    def test_reject_crummy_tags(self):
        field = etree.Element('td', {'t-field': u'company.name'})

        with self.assertRaisesRegexp(AssertionError, r'^RTE widgets do not work correctly'):
            self.engine.render_node(field, self.context({'company': None}))

    def test_reject_t_tag(self):
        field = etree.Element('t', {'t-field': u'company.name'})

        with self.assertRaisesRegexp(AssertionError, r'^t-field can not be used on a t element'):
            self.engine.render_node(field, self.context({'company': None}))


class TestQWeb(TransactionCase):
    matcher = re.compile(r'^qweb-test-(.*)\.xml$')

    @classmethod
    def get_cases(cls):
        path = cls.qweb_test_file_path()
        return (
            cls("test_qweb_{}".format(cls.matcher.match(f).group(1)))
            for f in os.listdir(path)
            # js inheritance
            if f != 'qweb-test-extend.xml'
            if cls.matcher.match(f)
        )

    @classmethod
    def qweb_test_file_path(cls):
        return os.path.dirname(get_module_resource('web', 'static', 'lib', 'qweb', 'qweb2.js'))

    def __getattr__(self, item):
        if not item.startswith('test_qweb_'):
            raise AttributeError("No {} on {}".format(item, self))

        f = 'qweb-test-{}.xml'.format(item[10:])
        path = self.qweb_test_file_path()

        return lambda: self.run_test_file(os.path.join(path, f))

    def run_test_file(self, path):
        doc = etree.parse(path).getroot()
        loader = FileSystemLoader(path)
        context = QWebContext(self.env, {}, loader=loader)
        qweb = self.env['ir.qweb']
        for template in loader:
            if not template or template.startswith('_'):
                continue
            param = doc.find('params[@id="{}"]'.format(template))
            # OrderedDict to ensure JSON mappings are iterated in source order
            # so output is predictable & repeatable
            params = {} if param is None else json.loads(param.text, object_pairs_hook=collections.OrderedDict)

            ctx = context.copy()
            ctx.update(params)
            result = doc.find('result[@id="{}"]'.format(template)).text
            self.assertEqual(
                qweb.render(template, qwebcontext=ctx).strip().encode('utf-8'),
                (result or u'').strip().encode('utf-8'),
                template
            )

def load_tests(loader, suite, _):
    # can't override TestQWeb.__dir__ because dir() called on *class* not
    # instance
    suite.addTests(TestQWeb.get_cases())
    return suite
