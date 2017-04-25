odoo.define('mrp.tests', function (require) {
"use strict";

var FormView = require('web.FormView');
var testUtils = require("web.test_utils");

var createView = testUtils.createView;

QUnit.module('mrp', {
    beforeEach: function () {
        this.data = {
            partner: {
                fields: {
                    document: {string: "Document", type: "binary"},
                },
                records: [{
                    id: 1,
                    document: 'coucou==\n',
                }],
                onchanges: {},
            },
        };
    },
}, function () {
    QUnit.test("pdf_viewer without data", function (assert) {
        assert.expect(3);

        var form = createView({
            View: FormView,
            model: 'partner',
            data: this.data,
            arch:
                '<form>' +
                    '<field name="document" widget="pdf_viewer"/>' +
                '</form>',
        });

        assert.ok(form.$('.o_form_field').hasClass('o_form_field_pdfviewer'));
        assert.strictEqual(form.$('.o_select_file_button:not(.o_hidden)').length, 1,
            "there should be a visible 'Upload' button");
        assert.ok(form.$('.o_form_field iframe.o_pdfview_iframe').hasClass('o_hidden'),
            "there should be an invisible iframe");

        form.destroy();
    });

    QUnit.test("pdf_viewer: basic rendering", function (assert) {
        assert.expect(4);

        var form = createView({
            View: FormView,
            model: 'partner',
            data: this.data,
            res_id: 1,
            arch:
                '<form>' +
                    '<field name="document" widget="pdf_viewer"/>' +
                '</form>',
            mockRPC: function (route) {
                if (route.indexOf('/web/static/lib/pdfjs/web/viewer.html') !== -1) {
                    return $.when();
                }
                return this._super.apply(this, arguments);
            }
        });

        assert.ok(form.$('.o_form_field').hasClass('o_form_field_pdfviewer'));
        assert.strictEqual(form.$('.o_select_file_button:not(.o_hidden)').length, 0,
            "there should not be a any visible 'Upload' button");
        assert.notOk(form.$('.o_form_field iframe.o_pdfview_iframe').hasClass('o_hidden'),
            "there should be an visible iframe");
        assert.strictEqual(form.$('.o_form_field iframe.o_pdfview_iframe').attr('src'),
            '#test:/web/static/lib/pdfjs/web/viewer.html?file=%2Fweb%2Fimage%3Fmodel%3Dpartner%26field%3Ddocument%26id%3D1',
            "the src attribute should be correctly set on the iframe");

        form.destroy();
    });
});
});
