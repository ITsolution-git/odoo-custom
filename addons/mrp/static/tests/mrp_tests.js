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
                    state: {
                        string: "State",
                        type: "selection",
                        selection: [['waiting', 'Waiting'], ['chilling', 'Chilling']],
                    },
                    document: {string: "Document", type: "binary"},
                    duration: {string: "Duration", type: "float"},
                },
                records: [{
                    id: 1,
                    document: 'coucou==\n',
                    state: 'waiting',
                    duration: 6000,
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

    QUnit.test("bullet_state: basic rendering", function (assert) {
        assert.expect(2);

        var form = createView({
            View: FormView,
            model: 'partner',
            data: this.data,
            res_id: 1,
            arch:
                '<form>' +
                    '<field name="state" widget="bullet_state" options="{\'classes\': {\'waiting\': \'danger\'}}"/>' +
                '</form>',
        });

        assert.strictEqual(form.$('.o_form_field').text(), "Waiting Materials",
            "the widget should be correctly named");
        assert.strictEqual(form.$('.o_form_field .label-danger').length, 1,
            "the label should be danger");

        form.destroy();
    });

    QUnit.test("mrp_time_counter: basic rendering", function (assert) {
        assert.expect(2);

        var form = createView({
            View: FormView,
            model: 'partner',
            data: this.data,
            res_id: 1,
            arch:
                '<form>' +
                    '<field name="duration" widget="mrp_time_counter"/>' +
                '</form>',
            mockRPC: function (route, args) {
                if (args.method === 'search_read' && args.model === 'mrp.workcenter.productivity') {
                    assert.ok(true, "the widget should fetch the mrp.workcenter.productivity");
                    return $.when([{
                        date_start: '2017-01-01 08:00:00',
                        date_end: '2017-01-01 10:00:00',
                    }, {
                        date_start: '2017-01-01 12:00:00',
                        date_end: '2017-01-01 12:30:00',
                    }]);
                }
                return this._super.apply(this, arguments);
            },
        });

        assert.strictEqual(form.$('.o_form_field[name="duration"]').text(), "02:30:00",
            "the timer should be correctly set");

        form.destroy();
    });
});
});
