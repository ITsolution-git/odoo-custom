openerp.web.data_import = function(openerp) {
var QWeb = openerp.web.qweb;
/**
 * Safari does not deal well at all with raw JSON data being returned. As a
 * result, we're going to cheat by using a pseudo-jsonp: instead of getting
 * JSON data in the iframe, we're getting a ``script`` tag which consists of a
 * function call and the returned data (the json dump).
 *
 * The function is an auto-generated name bound to ``window``, which calls
 * back into the callback provided here.
 *
 * @param {Object} form the form element (DOM or jQuery) to use in the call
 * @param {Object} attributes jquery.form attributes object
 * @param {Function} callback function to call with the returned data
 */
function jsonp(form, attributes, callback) {
    var options = {jsonp: _.uniqueId('import_callback_')};
    window[options.jsonp] = function () {
        delete window[options.jsonp];
        callback.apply(null, arguments);
    };
    $(form).ajaxSubmit(_.extend({
        data: options
    }, attributes));
}

openerp.web.DataImport = openerp.web.Dialog.extend({
    template: 'ImportDataView',
    dialog_title: "Import Data",
    init: function(parent, dataset){
        var self = this;
        this._super(parent, {});
        this.model = parent.model;
        this.fields = [];
        this.all_fields = [];
        this.required_fields;

        var convert_fields = function (root, prefix) {
            prefix = prefix || '';
            _(root.fields).each(function (f) {
                var name = prefix + f.name;
                self.all_fields.push(name);
                if (f.fields) {
                    convert_fields(f, name + '/');
                }
            });
        };
        this.ready  = $.Deferred.queue().then(function () {
            self.required_fields = _(self.fields).chain()
                .filter(function (field) { return field.required; })
                .pluck('name')
                .value();
            convert_fields(self);
            self.all_fields.sort();
        });
    },
    start: function() {
        var self = this;
        this._super();
        this.open({
            modal: true,
            width: '70%',
            height: 'auto',
            position: 'top',
            buttons: [
                {text: "Close", click: function() { self.stop(); }},
                {text: "Import File", click: function() { self.do_import(); }, 'class': 'oe-dialog-import-button'}
            ],
            close: function(event, ui) {
                self.stop();
            }
        });
        this.toggle_import_button(false);
        this.$element.find('#csvfile').change(this.on_autodetect_data);
        this.$element.find('fieldset').change(this.on_autodetect_data);
        this.$element.find('fieldset legend').click(function() {
            $(this).next().toggle();
        });
        this.ready.push(new openerp.web.DataSet(this, this.model).call(
            'fields_get', [], function (fields) {
                self.graft_fields(fields);
            }));
    },
    graft_fields: function (fields, parent, level) {
        parent = parent || this;
        level = level || 0;

        var self = this;
        _(fields).each(function (field, field_name) {
            var f = {
                name: field_name,
                string: field.string,
                required: field.required
            };

            if (field.type === 'one2many') {
                f.fields = [];
                // only fetch sub-fields to a depth of 2 levels
                if (level < 2) {
                    self.ready.push(new openerp.web.DataSet(self, field.relation).call(
                        'fields_get', [], function (fields) {
                            self.graft_fields(fields, f, level+1);
                    }));
                }
            }
            parent.fields.push(f);
        });
    },
    toggle_import_button: function (newstate) {
        this.$dialog.dialog('widget')
                .find('.oe-dialog-import-button')
                .button('option', 'disabled', !newstate);
    },
    do_import: function() {
        if(!this.$element.find('#csvfile').val()) { return; }
        jsonp(this.$element.find('#import_data'), {
            url: '/web/import/import_data'
        }, this.on_import_results);
    },
    on_autodetect_data: function() {
        if(!this.$element.find('#csvfile').val()) { return; }
        jsonp(this.$element.find('#import_data'), {
            url: '/web/import/detect_data'
        }, this.on_import_results);
    },
    on_import_results: function(results) {
        this.$element.find('#result, #success').empty();
        var result_node = this.$element.find("#result");

        if (results['records']) {
            result_node.append(QWeb.render('ImportView.result', {
                'headers': results.records[0],
                'records': results.records.slice(1)
            }));
        } else if (results['error']) {
            result_node.append(QWeb.render('ImportView.error', {
                'error': results['error']}));
        } else if (results['success']) {
            self.stop();
            if (this.widget_parent.widget_parent.active_view == "list") {
                this.widget_parent.reload_content();
            }
        }

        var self = this;
        this.ready.then(function () {
            self.$element.find('.sel_fields').autocomplete({
                minLength: 0,
                source: self.all_fields,
                change: self.on_check_field_values
            }).focus(function () {
                $(this).autocomplete('search');
            });
            self.on_check_field_values();
        });
    },
    /**
     * Looks through all the field selections, and tries to find if two
     * (or more) columns were matched to the same model field.
     *
     * Returns a map of the multiply-mapped fields to an array of offending
     * columns (not actually columns, but the inputs containing the same field
     * names).
     *
     * Also has the side-effect of marking the discovered inputs with the class
     * ``duplicate_fld``.
     *
     * @returns {Object<String, Array<String>>} map of duplicate field matches to same-valued inputs
     */
    find_duplicate_fields: function() {
        // Maps values to DOM nodes, in order to discover duplicates
        var values = {}, duplicates = {};
        this.$element.find(".sel_fields").each(function(index, element) {
            var value = element.value;
            var $element = $(element).removeClass('duplicate_fld');
            if (!value) { return; }

            if (!(value in values)) {
                values[value] = element;
            } else {
                var same_valued_field = values[value];
                if (value in duplicates) {
                    duplicates[value].push(element);
                } else {
                    duplicates[value] = [same_valued_field, element];
                }
                $element.add(same_valued_field).addClass('duplicate_fld');
            }
        });
        return duplicates;
    },
    on_check_field_values: function () {
        this.$element.find("#message, #msg").remove();

        var required_valid = this.check_required();

        var duplicates = this.find_duplicate_fields();
        if (_.isEmpty(duplicates)) {
            this.toggle_import_button(required_valid);
        } else {
            var $err = $('<div id="msg" style="color: red;">Destination fields should only be selected once, some fields are selected more than once:</div>').insertBefore(this.$element.find('#result'));
            var $dupes = $('<dl>').appendTo($err);
            _(duplicates).each(function(elements, value) {
                $('<dt>').text(value).appendTo($dupes);
                _(elements).each(function(element) {
                    var cell = $(element).closest('td');
                    $('<dd>').text(cell.parent().children().index(cell)).appendTo($dupes);
                });
            });
            this.toggle_import_button(false);
        }

    },
    check_required: function() {
        if (!this.required_fields.length) { return true; }

        var selected_fields = _(this.$element.find('.sel_fields').get()).chain()
            .pluck('value')
            .compact()
            .value();

        var missing_fields = _.difference(this.required_fields, selected_fields);
        if (missing_fields.length) {
            this.$element.find("#result").before('<div id="message" style="color:red">*Required Fields are not selected : ' + missing_fields + '.</div>');
            return false;
        }
        return true;
    },
    stop: function() {
        $(this.$dialog).remove();
        this._super();
    }
});
};
