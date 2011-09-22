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
        this._super(parent, {});
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
        if(this.$element.find("#res td")){
            this.$element.find("#res td").remove();
            this.$element.find("#imported_success").css('display','none');
        }
        if(!this.$element.find('#csvfile').val()) { return; }
        jsonp(this.$element.find('#import_data'), {
            url: '/web/import/detect_data'
        }, this.on_import_results);
    },
    on_import_results: function(results) {
        this.$element.find('#result, #success').empty();
        var result_node = this.$element.find("#result");
        var records = {};

        if (results['records']) {
            records = {'header': results['header'], 'row': results['records']};
            result_node.append(QWeb.render('ImportView-result', {'records': records}));
        } else if (results['error']) {
            result_node.append(QWeb.render('ImportView-result', {'error': results['error']}));
        } else if (results['success']) {
            self.stop();
            if (this.widget_parent.widget_parent.active_view == "list") {
                this.widget_parent.reload_content();
            }
        }

        var self = this;
        this.$element.find('.sel_fields').autocomplete({
            minLength: 0,
            source: results.all_fields,
            change: function () {
                self.on_check_field_values(results['required_fields']);
            }
        }).focus(function () {
            $(this).autocomplete('search');
        });

        this.on_check_field_values(results['required_fields']);
    },
    on_check_field_values: function (required_fields) {
        this.$element.find("#message, #msg").remove();

        // Maps values to DOM nodes, in order to discover duplicates
        var values = {}, duplicates = {};
        this.$element.find(".sel_fields").each(function (index, element) {
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

        if (!_.isEmpty(duplicates)) {
            var $err = $('<div id="msg" style="color: red;">Destination fields should only be selected once, some fields are selected more than once:</div>')
                .insertBefore(this.$element.find('#result'));
            var $dupes = $('<dl>').appendTo($err);
            _(duplicates).each(function (elements, value) {
                $('<dt>').text(value).appendTo($dupes);
                _(elements).each(function (element) {
                    var cell = $(element).closest('td');
                    $('<dd>').text(cell.parent().children().index(cell))
                           .appendTo($dupes);
                });
            });
            this.toggle_import_button(false);
        } else {
            this.$element.find("#msg").remove();
            this.toggle_import_button(true);
        }

        this.do_check_required(required_fields);
    },
    do_check_required: function(req_fld) {
        if (!req_fld.length) { return; }

        this.$element.find("#message").remove();
        var sel_fields = _.map(this.$element.find("td #sel_field option:selected"), function(fld) {
            return fld['text']
        });
        var required_fields = _.filter(req_fld, function(fld) {
            return !_.contains(sel_fields, fld)
        });
        if (required_fields.length) {
            this.$element.find("#result").before('<div id="message" style="color:red">*Required Fields are not selected : ' + required_fields + '.</div>');
            this.toggle_import_button(false);
        } else {
            this.$element.find("#message").remove();
            this.toggle_import_button(true);
        }
    },
    stop: function() {
        $(this.$dialog).remove();
        this._super();
    }
});
};
