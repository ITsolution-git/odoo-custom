# coding=utf-8
# -*- encoding: utf-8 -*-

import glob
import itertools
import json
import operator
import os

from mako.template import Template
from openerp.modules import module
from openerp import http
from openerp.http import request

from .main import module_topological_sort

NOMODULE_TEMPLATE = Template(u"""<!DOCTYPE html>
<html>
    <head>
        <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1"/>
        <meta http-equiv="content-type" content="text/html; charset=utf-8" />
        <title>OpenERP Testing</title>
    </head>
    <body>
        <form action="/web/tests" method="GET">
            <button name="mod" value="*">Run all tests</button>
            <ul>
            % for name, module in modules:
                <li>${name} <button name="mod" value="${module}">
                    Run Tests</button></li>
            % endfor
            </ul>
        </form>
    </body>
</html>
""", default_filters=['h'])
NOTFOUND = Template(u"""
<p>Unable to find the module [${module}], please check that the module
   name is correct and the module is on OpenERP's path.</p>
<a href="/web/tests">&lt;&lt; Back to tests</a>
""", default_filters=['h'])
TESTING = Template(u"""<!DOCTYPE html>
<html style="height: 100%">
<%def name="to_path(module, p)">/${module}/${p}</%def>
<head>
    <meta http-equiv="X-UA-Compatible" content="IE=edge"/>
    <meta http-equiv="content-type" content="text/html; charset=utf-8" />
    <title>OpenERP Web Tests</title>
    <link rel="shortcut icon" href="/web/static/src/img/favicon.ico" type="image/x-icon"/>

    <link rel="stylesheet" href="/web/static/lib/qunit/qunit.css">
    <script src="/web/static/lib/qunit/qunit.js"></script>

    <script type="text/javascript">
        // List of modules, each module is preceded by its dependencies
        var oe_all_dependencies = ${dependencies | n};
        QUnit.config.testTimeout = 5 * 60 * 1000;
    </script>
</head>
<body id="oe" class="openerp">
    <div id="qunit"></div>
    <div id="qunit-fixture"></div>
</body>
<!-- TODO fme: Remove manifest usage for js and css -->
${bundle('web.assets_backend') | n}
% for module, jss, tests, templates in files:
    % for js in jss:
        % if not js.endswith('/apps.js'):
            <script src="${to_path(module, js)}"></script>
        % endif
    % endfor
    % if tests or templates:
    <script>
        openerp.testing.current_module = "${module}";
        % for template in templates:
        openerp.testing.add_template("${to_path(module, template)}");
        % endfor
    </script>
    % endif
    % if tests:
        % for test in tests:
            <script type="text/javascript" src="${to_path(module, test)}"></script>
        % endfor
    % endif
% endfor
</html>
""", default_filters=['h'])

class TestRunnerController(http.Controller):

    @http.route('/web/tests', type='http', auth="none")
    def index(self, mod=None, **kwargs):
        ms = module.get_modules()
        manifests = dict(
            (name, desc)
            for name, desc in zip(ms, map(self.load_manifest, ms))
            if desc # remove not-actually-openerp-modules
        )

        if not mod:
            return NOMODULE_TEMPLATE.render(modules=(
                (manifest['name'], name)
                for name, manifest in manifests.iteritems()
                if any(testfile.endswith('.js')
                       for testfile in manifest['test'])
            ))
        sorted_mods = module_topological_sort(dict(
            (name, manifest.get('depends', []))
            for name, manifest in manifests.iteritems()
        ))
        # to_load and to_test should be zippable lists of the same length.
        # A falsy value in to_test indicate nothing to test at that index (just
        # load the corresponding part of to_load)
        to_test = sorted_mods
        if mod != '*':
            if mod not in manifests:
                return request.not_found(NOTFOUND.render(module=mod))
            idx = sorted_mods.index(mod)
            to_test = [None] * len(sorted_mods)
            to_test[idx] = mod

        tests_candicates = [
            filter(lambda path: path.endswith('.js'),
                   manifests[mod]['test'] if mod else [])
            for mod in to_test]
        # remove trailing test-less modules
        tests = reversed(list(
            itertools.dropwhile(
                operator.not_,
                reversed(tests_candicates))))

        files = [
            (mod, manifests[mod]['js'], tests, manifests[mod]['qweb'])
            for mod, tests in itertools.izip(sorted_mods, tests)
        ]

        def bundle(xmlid):
            return request.render(xmlid, lazy=False)

        return TESTING.render(bundle=bundle, files=files, dependencies=json.dumps(
            [name for name in sorted_mods
             if module.get_module_resource(name, 'static')
             # TODO fme: find a way to detect modules with js bundles
             # if manifests[name]['js']
            ]))


    def load_manifest(self, name):
        manifest = module.load_information_from_description_file(name)
        if manifest:
            path = module.get_module_path(name)
            manifest['js'] = list(
                self.expand_patterns(path, manifest.get('js', [])))
            manifest['test'] = list(
                self.expand_patterns(path, manifest.get('test', [])))
            manifest['qweb'] = list(
                self.expand_patterns(path, manifest.get('qweb', [])))
        return manifest

    def expand_patterns(self, root, patterns):
        for pattern in patterns:
            normalized_pattern = os.path.normpath(os.path.join(root, pattern))
            for path in glob.glob(normalized_pattern):
                # replace OS path separators (from join & normpath) by URI ones
                yield path[len(root):].replace(os.path.sep, '/')

