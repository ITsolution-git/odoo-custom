odoo.define('website_form.animation', function (require) {
'use strict';

    var core = require('web.core');
    var time = require('web.time');
    var ajax = require('web.ajax');
    var snippet_animation = require('web_editor.snippets.animation');

    var _t = core._t;
    var qweb = core.qweb;


    snippet_animation.registry.form_builder_send = snippet_animation.Class.extend({
        selector: '.s_website_form',

        start: function() {
            var self = this;
            qweb.add_template('/website_form/static/src/xml/website_form.xml');
            this.$target.find('.o_website_form_send').on('click',function(e) {self.send(e);});

            // Initialize datetimepickers
            var l10n = _t.database.parameters;
            this.$target.find('.o_website_form_datetime').datetimepicker({
                pickTime: true,
                useSeconds: true,
                startDate: moment({ y: 1900 }),
                endDate: moment().add(200, "y"),
                calendarWeeks: true,
                icons : {
                    time: 'fa fa-clock-o',
                    date: 'fa fa-calendar',
                    up: 'fa fa-chevron-up',
                    down: 'fa fa-chevron-down'
                   },
                language : moment.locale(),
                format : time.strftime_to_moment_format(l10n.date_format +' '+ l10n.time_format),
            });
        },

        stop: function() {
            this.$target.find('button').off('click');
        },

        send: function(e) {
            e.preventDefault();  // Prevent the default submit behavior

            var self = this;

            self.$target.find('#o_website_form_result').empty();
            if (!self.check_error_fields([])) {
                self.update_status('invalid');
                return false;
            }

            // Prepare form inputs
            this.form_fields = this.$target.serializeArray();
            _.each(this.$target.find('input[type=file]'), function(input) {
                $.each($(input).prop('files'), function(index, file) {
                    // Index field name as ajax won't accept arrays of files
                    // when aggregating multiple files into a single field value
                    self.form_fields.push({
                        name: input.name + '[' + index + ']',
                        value: file
                    });
                });
            });

            // Serialize form inputs into a single object
            // Aggregate multiple values into arrays
            var form_values = {};
            _.each(this.form_fields, function(input) {
                if (input.name in form_values) {
                    // If a value already exists for this field,
                    // we are facing a x2many field, so we store
                    // the values in an array.
                    if (Array.isArray(form_values[input.name])) {
                        form_values[input.name].push(input.value);
                    } else {
                        form_values[input.name] = [form_values[input.name], input.value];
                    }
                } else {
                    if (input.value != '') {
                        form_values[input.name] = input.value;
                    }
                }
            });

            // Overwrite form_values array with values from the form tag
            // Necessary to handle field values generated server-side, since
            // using t-att- inside a snippet makes it non-editable !
            for (var key in this.$target.data()) {
                if (_.str.startsWith(key, 'form_field_')){
                    form_values[key.replace('form_field_', '')] = this.$target.data(key);
                }
            }

            // Post form and handle result
            ajax.post(this.$target.attr('action') + this.$target.data('model_name'), form_values)
            .then(function(result_data) {
                result_data = $.parseJSON(result_data);
                if(!result_data.id) {
                    // Failure, the server didn't return the created record ID
                    self.update_status('error');
                    if (result_data.error_fields && result_data.error_fields.length) {
                        // If the server return a list of bad fields, show these fields for users
                        self.check_error_fields(result_data.error_fields);
                    }
                } else {
                    // Success, redirect or update status
                    var success_page = self.$target.attr('data-success_page');
                    if(success_page) {
                        $(location).attr('href', success_page);
                    }
                    else {
                        self.update_status('success');
                    }
                }
            })
            .fail(function(result_data){
                self.update_status('error');
            });
        },

        check_error_fields: function(error_fields) {
            var form_valid = true;
            // Loop on all fields
            this.$target.find('.form-field').each(function(k, field){
                var $field = $(field);
                var $fields = self.$fields;
                var field_name = $field.find('.control-label').attr('for')

                // Validate inputs for this field
                var field_valid = true;
                var inputs = $field.find('.o_website_form_input');
                var invalid_inputs = inputs.toArray().filter(function(input, k, inputs) {
                    // Special check for multiple required checkbox for same
                    // field as it seems checkValidity forces every required
                    // checkbox to be checked, instead of looking at other
                    // checkboxes with the same name and only requiring one
                    // of them to be checked.
                    if (input.required && input.type == 'checkbox') {
                        // Considering we are currently processing a single
                        // field, we can assume that all checkboxes in the
                        // inputs variable have the same name
                        var checkboxes = _.filter(inputs, function(input){
                            return input.required && input.type == 'checkbox'
                        })
                        return !_.any(checkboxes, function(checkbox){return checkbox.checked})
                    } else {
                        return !input.checkValidity();
                    }
                })

                // Update field color if invalid or erroneous
                $field.removeClass('has-error');
                if(invalid_inputs.length || error_fields.indexOf(field_name) >= 0){
                    $field.addClass('has-error');
                    form_valid = false;
                }
            });
            return form_valid;
        },

        update_status: function(status) {
            this.$target.find('#o_website_form_result').replaceWith(qweb.render("website_form.status_" + status))
        },
    });
});
