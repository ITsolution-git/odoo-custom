openerp.web.form = function (instance) {
var _t = instance.web._t,
   _lt = instance.web._lt;
var QWeb = instance.web.qweb;

/** @namespace */
instance.web.form = {};

/**
 * Interface implemented by the form view or any other object
 * able to provide the features necessary for the fields to work.
 * 
 * Properties:
 *     - display_invalid_fields : if true, all fields where is_valid() return true should
 *     be displayed as invalid.
 * Events:
 *     - view_content_has_changed : when the values of the fields have changed. When
 *     this event is triggered all fields should reprocess their modifiers.
 */
instance.web.form.FieldManagerMixin = {
    /**
     * Must return the asked field as in fields_get.
     */
    get_field: function(field_name) {},
    /**
     * Called by the field when the translate button is clicked.
     */
    open_translate_dialog: function(field) {},
    /**
     * Returns true when the view is in create mode.
     */
    is_create_mode: function() {},
};

instance.web.views.add('form', 'instance.web.FormView');
instance.web.FormView = instance.web.View.extend(_.extend({}, instance.web.form.FieldManagerMixin, {
    /**
     * Indicates that this view is not searchable, and thus that no search
     * view should be displayed (if there is one active).
     */
    searchable: false,
    template: "FormView",
    display_name: _lt('Form'),
    view_type: "form",
    /**
     * @constructs instance.web.FormView
     * @extends instance.web.View
     *
     * @param {instance.web.Session} session the current openerp session
     * @param {instance.web.DataSet} dataset the dataset this view will work with
     * @param {String} view_id the identifier of the OpenERP view object
     * @param {Object} options
     *                  - resize_textareas : [true|false|max_height]
     *
     * @property {instance.web.Registry} registry=instance.web.form.widgets widgets registry for this form view instance
     */
    init: function(parent, dataset, view_id, options) {
        this._super(parent);
        this.set_default_options(options);
        this.dataset = dataset;
        this.model = dataset.model;
        this.view_id = view_id || false;
        this.fields_view = {};
        this.fields = {};
        this.fields_order = [];
        this.datarecord = {};
        this.default_focus_field = null;
        this.default_focus_button = null;
        this.fields_registry = instance.web.form.widgets;
        this.tags_registry = instance.web.form.tags;
        this.has_been_loaded = $.Deferred();
        this.translatable_fields = [];
        _.defaults(this.options, {
            "not_interactible_on_create": false,
            "initial_mode": "view",
        });
        this.is_initialized = $.Deferred();
        this.mutating_mutex = new $.Mutex();
        this.on_change_mutex = new $.Mutex();
        this.reload_mutex = new $.Mutex();
        this.rendering_engine = new instance.web.form.FormRenderingEngineReadonly(this);
        this.qweb = null; // A QWeb instance will be created if the view is a QWeb template
    },
    destroy: function() {
        _.each(this.get_widgets(), function(w) {
            w.destroy();
        });
        this._super();
    },
    on_loaded: function(data) {
        var self = this;
        if (!data) {
            throw new Error("No data provided.");
        }
        if (this.arch) {
            throw "Form view does not support multiple calls to on_loaded";
        }
        this.fields_order = [];
        this.fields_view = data;

        this.rendering_engine.set_fields_registry(this.fields_registry);
        this.rendering_engine.set_tags_registry(this.tags_registry);
        if (!this.extract_qweb_template(data)) {
            this.rendering_engine.set_fields_view(data);
            var $dest = this.$element.hasClass("oe_form_container") ? this.$element : this.$element.find('.oe_form_container');
            this.rendering_engine.render_to($dest);
        }


        this.$buttons = $(QWeb.render("FormView.buttons", {'widget':self}));
        if (this.options.$buttons) {
            this.$buttons.appendTo(this.options.$buttons);
        } else {
            this.$element.find('.oe_form_buttons').replaceWith(this.$buttons);
        }
        this.$buttons.on('click','.oe_form_button_create',this.on_button_create);
        this.$buttons.on('click','.oe_form_button_edit',this.on_button_edit);
        this.$buttons.on('click','.oe_form_button_save',this.on_button_save);
        this.$buttons.on('click','.oe_form_button_cancel',this.on_button_cancel);

        this.$pager = $(QWeb.render("FormView.pager", {'widget':self}));
        if (this.options.$pager) {
            this.$pager.appendTo(this.options.$pager);
        } else {
            this.$element.find('.oe_form_pager').replaceWith(this.$pager);
        }
        this.$pager.on('click','a[data-pager-action]',function() {
            var action = $(this).data('pager-action');
            self.on_pager_action(action);
        });

        this.$sidebar = this.options.$sidebar || this.$element.find('.oe_form_sidebar');
        if (!this.sidebar && this.options.$sidebar) {
            this.sidebar = new instance.web.Sidebar(this);
            this.sidebar.appendTo(this.$sidebar);
            if(this.fields_view.toolbar) {
                this.sidebar.add_toolbar(this.fields_view.toolbar);
            }
            this.sidebar.add_items('other', [
                { label: _t('Delete'), callback: self.on_button_delete },
                { label: _t('Duplicate'), callback: self.on_button_duplicate },
                { label: _t('Set Default'), callback: function (item) { self.open_defaults_dialog(); } },
            ]);
        }
        this.on("change:mode", this, this.switch_mode);
        this.set({mode: this.options.initial_mode});
        this.has_been_loaded.resolve();
        return $.when();
    },
    extract_qweb_template: function(fvg) {
        for (var i=0, ii=fvg.arch.children.length; i < ii; i++) {
            var child = fvg.arch.children[i];
            if (child.tag === "templates") {
                this.qweb = new QWeb2.Engine();
                this.qweb.add_template(instance.web.json_node_to_xml(child));
                if (!this.qweb.has_template('form')) {
                    throw new Error("No QWeb template found for form view");
                }
                return true;
            }
        }
        this.qweb = null;
        return false;
    },
    get_fvg_from_qweb: function(record) {
        var view = this.qweb.render('form', this.get_qweb_context(record));
        var fvg = _.clone(this.fields_view);
        fvg.arch = instance.web.xml_to_json(instance.web.str_to_xml(view).firstChild);
        return fvg;
    },
    get_qweb_context: function(record) {
        var self = this,
            new_record = {};
        _.each(record, function(value_, name) {
            var r = _.clone(self.fields_view.fields[name] || {});
            if ((r.type === 'date' || r.type === 'datetime') && value_) {
                r.raw_value = instance.web.auto_str_to_date(value_);
            } else {
                r.raw_value = value_;
            }
            r.value = instance.web.format_value(value_, r);
            new_record[name] = r;
        });
        return {
            record : new_record,
            new_record : !record.id
        };
    },
    kill_current_form: function() {
        _.each(this.getChildren(), function(el) {
            el.destroy();
        });
        this.fields = {};
        this.fields_order = [];
        this.default_focus_field = null;
        this.default_focus_button = null;
        this.translatable_fields = [];
        this.$element.find('.oe_form_container').empty();
    },
    do_load_state: function(state, warm) {
        if (state.id && this.datarecord.id != state.id) {
            if (!this.dataset.get_id_index(state.id)) {
                this.dataset.ids.push(state.id);
            }
            this.dataset.select_id(state.id);
            if (warm) {
                this.do_show();
            }
        }
    },
    do_show: function () {
        var self = this;
        if (this.sidebar) {
            this.sidebar.$element.show();
        }
        if (this.$buttons) {
            this.$buttons.show();
            this.$buttons.find('.oe_form_button_save').removeClass('oe_form_button_save_dirty');
        }
        if (this.$pager) {
            this.$pager.show();
        }
        this.$element.show().css('visibility', 'hidden');
        this.$element.removeClass('oe_form_dirty');
        return this.has_been_loaded.pipe(function() {
            var result;
            if (self.dataset.index === null) {
                // null index means we should start a new record
                result = self.on_button_new();
            } else {
                result = self.dataset.read_index(_.keys(self.fields_view.fields), {
                    context : { 'bin_size' : true }
                }).pipe(self.on_record_loaded);
            }
            result.pipe(function() {
                self.$element.css('visibility', 'visible');
            });
            return result;
        });
    },
    do_hide: function () {
        if (this.sidebar) {
            this.sidebar.$element.hide();
        }
        if (this.$buttons) {
            this.$buttons.hide();
        }
        if (this.$pager) {
            this.$pager.hide();
        }
        this._super();
    },
    on_record_loaded: function(record) {
        var self = this, set_values = [];
        if (!record) {
            this.do_warn("Form", "The record could not be found in the database.", true);
            return $.Deferred().reject();
        }
        this.datarecord = record;

        if (this.qweb) {
            this.kill_current_form();
            this.rendering_engine.set_fields_view(this.get_fvg_from_qweb(record));
            var $dest = this.$element.hasClass("oe_form_container") ? this.$element : this.$element.find('.oe_form_container');
            this.rendering_engine.render_to($dest);
        }

        _(this.fields).each(function (field, f) {
            field._dirty_flag = false;
            var result = field.set_value(self.datarecord[f] || false);
            set_values.push(result);
        });
        return $.when.apply(null, set_values).pipe(function() {
            if (!record.id) {
                // New record: Second pass in order to trigger the onchanges
                // respecting the fields order defined in the view
                _.each(self.fields_order, function(field_name) {
                    if (record[field_name] !== undefined) {
                        var field = self.fields[field_name];
                        field._dirty_flag = true;
                        self.do_onchange(field);
                    }
                });
            }
            self.on_form_changed();
            self.is_initialized.resolve();
            self.do_update_pager(record.id == null);
            if (self.sidebar) {
               self.sidebar.do_attachement_update(self.dataset, self.datarecord.id);
            }
            if (self.default_focus_field) {
                self.default_focus_field.focus();
            }
            if (record.id) {
                self.do_push_state({id:record.id});
            }
            self.$element.removeClass('oe_form_dirty');
            self.$buttons.find('.oe_form_button_save').removeClass('oe_form_button_save_dirty');
        });
    },
    on_form_changed: function() {
        this.trigger("view_content_has_changed");
    },
    do_notify_change: function() {
        this.$element.addClass('oe_form_dirty');
        this.$buttons.find('.oe_form_button_save').addClass('oe_form_button_save_dirty');
    },
    on_pager_action: function(action) {
        if (this.can_be_discarded()) {
            switch (action) {
                case 'first':
                    this.dataset.index = 0;
                    break;
                case 'previous':
                    this.dataset.previous();
                    break;
                case 'next':
                    this.dataset.next();
                    break;
                case 'last':
                    this.dataset.index = this.dataset.ids.length - 1;
                    break;
            }
            this.reload();
        }
    },
    do_update_pager: function(hide_index) {
        var index = hide_index ? '-' : this.dataset.index + 1;
        this.$pager.find('button').prop('disabled', this.dataset.ids.length < 2).end()
                   .find('span.oe_pager_index').html(index).end()
                   .find('span.oe_pager_count').html(this.dataset.ids.length);
    },
    parse_on_change: function (on_change, widget) {
        var self = this;
        var onchange = _.str.trim(on_change);
        var call = onchange.match(/^\s?(.*?)\((.*?)\)\s?$/);
        if (!call) {
            return null;
        }

        var method = call[1];
        if (!_.str.trim(call[2])) {
            return {method: method, args: [], context_index: null}
        }

        var argument_replacement = {
            'False': function () {return false;},
            'True': function () {return true;},
            'None': function () {return null;},
            'context': function (i) {
                context_index = i;
                var ctx = new instance.web.CompoundContext(self.dataset.get_context(), widget.build_context() ? widget.build_context() : {});
                return ctx;
            }
        };
        var parent_fields = null, context_index = null;
        var args = _.map(call[2].split(','), function (a, i) {
            var field = _.str.trim(a);

            // literal constant or context
            if (field in argument_replacement) {
                return argument_replacement[field](i);
            }
            // literal number
            if (/^-?\d+(\.\d+)?$/.test(field)) {
                return Number(field);
            }
            // form field
            if (self.fields[field]) {
                var value_ = self.fields[field].get_value();
                return value_ == null ? false : value_;
            }
            // parent field
            var splitted = field.split('.');
            if (splitted.length > 1 && _.str.trim(splitted[0]) === "parent" && self.dataset.parent_view) {
                if (parent_fields === null) {
                    parent_fields = self.dataset.parent_view.get_fields_values([self.dataset.child_name]);
                }
                var p_val = parent_fields[_.str.trim(splitted[1])];
                if (p_val !== undefined) {
                    return p_val == null ? false : p_val;
                }
            }
            // string literal
            var first_char = field[0], last_char = field[field.length-1];
            if ((first_char === '"' && last_char === '"')
                || (first_char === "'" && last_char === "'")) {
                return field.slice(1, -1);
            }

            throw new Error("Could not get field with name '" + field +
                            "' for onchange '" + onchange + "'");
        });

        return {
            method: method,
            args: args,
            context_index: context_index
        };
    },
    do_onchange: function(widget, processed) {
        var self = this;
        return this.on_change_mutex.exec(function() {
            try {
                var response = {}, can_process_onchange = $.Deferred();
                processed = processed || [];
                processed.push(widget.name);
                var on_change = widget.node.attrs.on_change;
                if (on_change) {
                    var change_spec = self.parse_on_change(on_change, widget);
                    if (change_spec) {
                        var ajax = {
                            url: '/web/dataset/onchange',
                            async: false
                        };
                        can_process_onchange = self.rpc(ajax, {
                            model: self.dataset.model,
                            method: change_spec.method,
                            args: [(self.datarecord.id == null ? [] : [self.datarecord.id])].concat(change_spec.args),
                            context_id: change_spec.context_index == undefined ? null : change_spec.context_index + 1
                        }).then(function(r) {
                            _.extend(response, r);
                        });
                    } else {
                        console.warn("Wrong on_change format", on_change);
                    }
                }
                // fail if onchange failed
                if (can_process_onchange.isRejected()) {
                    return can_process_onchange;
                }

                if (widget.field['change_default']) {
                    var fieldname = widget.name, value_;
                    if (response.value && (fieldname in response.value)) {
                        // Use value from onchange if onchange executed
                        value_ = response.value[fieldname];
                    } else {
                        // otherwise get form value for field
                        value_ = self.fields[fieldname].get_value();
                    }
                    var condition = fieldname + '=' + value_;

                    if (value_) {
                        can_process_onchange = self.rpc({
                            url: '/web/dataset/call',
                            async: false
                        }, {
                            model: 'ir.values',
                            method: 'get_defaults',
                            args: [self.model, condition]
                        }).then(function (results) {
                            if (!results.length) { return; }
                            if (!response.value) {
                                response.value = {};
                            }
                            for(var i=0; i<results.length; ++i) {
                                // [whatever, key, value]
                                var triplet = results[i];
                                response.value[triplet[1]] = triplet[2];
                            }
                        });
                    }
                }
                if (can_process_onchange.isRejected()) {
                    return can_process_onchange;
                }

                return self.on_processed_onchange(response, processed);
            } catch(e) {
                console.error(e);
                return $.Deferred().reject();
            }
        });
    },
    on_processed_onchange: function(response, processed) {
        try {
        var result = response;
        if (result.value) {
            for (var f in result.value) {
                if (!result.value.hasOwnProperty(f)) { continue; }
                var field = this.fields[f];
                // If field is not defined in the view, just ignore it
                if (field) {
                    var value_ = result.value[f];
                    if (field.get_value() != value_) {
                        field.set_value(value_);
                        field._dirty_flag = true;
                        if (!_.contains(processed, field.name)) {
                            this.do_onchange(field, processed);
                        }
                    }
                }
            }
            this.on_form_changed();
        }
        if (!_.isEmpty(result.warning)) {
        	instance.web.dialog($(QWeb.render("CrashManagerWarning", result.warning)), {
                modal: true,
                buttons: [
                    {text: _t("Ok"), click: function() { $(this).dialog("close"); }}
                ]
            });
        }
        if (result.domain) {
            function edit_domain(node) {
                var new_domain = result.domain[node.attrs.name];
                if (new_domain) {
                    node.attrs.domain = new_domain;
                }
                _(node.children).each(edit_domain);
            }
            edit_domain(this.fields_view.arch);
        }
        return $.Deferred().resolve();
        } catch(e) {
            console.error(e);
            return $.Deferred().reject();
        }
    },
    switch_mode: function() {
        var self = this;
        if(this.get("mode") == "view") {
            self.$buttons.find('.oe_form_buttons_edit').hide();
            self.$buttons.find('.oe_form_buttons_view').show();
            self.$sidebar.show();
            _.each(this.fields,function(field){
                field.set({"force_readonly": true});
            });
        } else {
            self.$buttons.find('.oe_form_buttons_edit').show();
            self.$buttons.find('.oe_form_buttons_view').hide();
            self.$sidebar.hide();
            _.each(this.fields,function(field){
                field.set({"force_readonly": false});
            });
        }
    },
    on_button_save: function() {
        var self = this;
        return this.do_save().then(function(result) {
            self.set({mode: "view"});
        });
    },
    on_button_cancel: function(event) {
        if (this.can_be_discarded()) {
            this.set({mode: "view"});
        }
        return false;
    },
    on_button_new: function() {
        var self = this;
        this.set({mode: "edit"});
        var def = $.Deferred();
        $.when(this.has_been_loaded).then(function() {
            if (self.can_be_discarded()) {
                var keys = _.keys(self.fields_view.fields);
                if (keys.length) {
                    self.dataset.default_get(keys).pipe(self.on_record_loaded).then(function() {
                        def.resolve();
                    });
                } else {
                    self.on_record_loaded({}).then(function() {
                        def.resolve();
                    });
                }
            }
        });
        return def.promise();
    },
    on_button_edit: function() {
        return this.set({mode: "edit"});
    },
    on_button_create: function() {
        this.dataset.index = null;
        this.do_show();
    },
    on_button_duplicate: function() {
        var self = this;
        var def = $.Deferred();
        $.when(this.has_been_loaded).then(function() {
            self.dataset.call('copy', [self.datarecord.id, {}, self.dataset.context]).then(function(new_id) {
                return self.on_created({ result : new_id });
            }).then(function() {
                return self.set({mode: "edit"});
            }).then(function() {
                def.resolve();
            });
        });
        return def.promise();
    },
    on_button_delete: function() {
        var self = this;
        var def = $.Deferred();
        $.when(this.has_been_loaded).then(function() {
            if (self.datarecord.id && confirm(_t("Do you really want to delete this record?"))) {
                self.dataset.unlink([self.datarecord.id]).then(function() {
                    self.on_pager_action('next');
                    def.resolve();
                });
            } else {
                $.async_when().then(function () {
                    def.reject();
                })
            }
        });
        return def.promise();
    },
    can_be_discarded: function() {
        return !this.$element.is('.oe_form_dirty') || confirm(_t("Warning, the record has been modified, your changes will be discarded."));
    },
    /**
     * Triggers saving the form's record. Chooses between creating a new
     * record or saving an existing one depending on whether the record
     * already has an id property.
     *
     * @param {Function} success callback on save success
     * @param {Boolean} [prepend_on_create=false] if ``do_save`` creates a new record, should that record be inserted at the start of the dataset (by default, records are added at the end)
     */
    do_save: function(success, prepend_on_create) {
        var self = this;
        return this.mutating_mutex.exec(function() { return self.is_initialized.pipe(function() {
            try {
            var form_invalid = false,
                values = {},
                first_invalid_field = null;
            for (var f in self.fields) {
                f = self.fields[f];
                if (!f.is_valid()) {
                    form_invalid = true;
                    if (!first_invalid_field) {
                        first_invalid_field = f;
                    }
                } else if (f.name !== 'id' && !f.get("readonly") && (!self.datarecord.id || f._dirty_flag)) {
                    // Special case 'id' field, do not save this field
                    // on 'create' : save all non readonly fields
                    // on 'edit' : save non readonly modified fields
                    values[f.name] = f.get_value();
                }
            }
            if (form_invalid) {
                self.set({'display_invalid_fields': true});
                first_invalid_field.focus();
                self.on_invalid();
                return $.Deferred().reject();
            } else {
                self.set({'display_invalid_fields': false});
                var save_deferral;
                if (!self.datarecord.id) {
                    //console.log("FormView(", self, ") : About to create", values);
                    save_deferral = self.dataset.create(values).pipe(function(r) {
                        return self.on_created(r, undefined, prepend_on_create);
                    }, null);
                } else if (_.isEmpty(values) && ! self.force_dirty) {
                    //console.log("FormView(", self, ") : Nothing to save");
                    save_deferral = $.Deferred().resolve({}).promise();
                } else {
                    self.force_dirty = false;
                    //console.log("FormView(", self, ") : About to save", values);
                    save_deferral = self.dataset.write(self.datarecord.id, values, {}).pipe(function(r) {
                        return self.on_saved(r);
                    }, null);
                }
                return save_deferral.then(success);
            }
            } catch (e) {
                console.error(e);
                return $.Deferred().reject();
            }
        });});
    },
    on_invalid: function() {
        var msg = "<ul>";
        _.each(this.fields, function(f) {
            if (!f.is_valid()) {
                msg += "<li>" + f.node.attrs.string + "</li>";
            }
        });
        msg += "</ul>";
        this.do_warn("The following fields are invalid :", msg);
    },
    on_saved: function(r, success) {
        if (!r.result) {
            // should not happen in the server, but may happen for internal purpose
            return $.Deferred().reject();
        } else {
            return $.when(this.reload()).pipe(function () {
                return $.when(r).then(success); }, null);
        }
    },
    /**
     * Updates the form' dataset to contain the new record:
     *
     * * Adds the newly created record to the current dataset (at the end by
     *   default)
     * * Selects that record (sets the dataset's index to point to the new
     *   record's id).
     * * Updates the pager and sidebar displays
     *
     * @param {Object} r
     * @param {Function} success callback to execute after having updated the dataset
     * @param {Boolean} [prepend_on_create=false] adds the newly created record at the beginning of the dataset instead of the end
     */
    on_created: function(r, success, prepend_on_create) {
        if (!r.result) {
            // should not happen in the server, but may happen for internal purpose
            return $.Deferred().reject();
        } else {
            this.datarecord.id = r.result;
            if (!prepend_on_create) {
                this.dataset.alter_ids(this.dataset.ids.concat([this.datarecord.id]));
                this.dataset.index = this.dataset.ids.length - 1;
            } else {
                this.dataset.alter_ids([this.datarecord.id].concat(this.dataset.ids));
                this.dataset.index = 0;
            }
            this.do_update_pager();
            if (this.sidebar) {
                this.sidebar.do_attachement_update(this.dataset, this.datarecord.id);
            }
            //instance.log("The record has been created with id #" + this.datarecord.id);
            this.reload();
            return $.when(_.extend(r, {created: true})).then(success);
        }
    },
    on_action: function (action) {
        console.debug('Executing action', action);
    },
    reload: function() {
        var self = this;
        return this.reload_mutex.exec(function() {
            if (self.dataset.index == null) {
                self.do_prev_view();
                return $.Deferred().reject().promise();
            }
            if (self.dataset.index == null || self.dataset.index < 0) {
                return $.when(self.on_button_new());
            } else {
                return self.dataset.read_index(_.keys(self.fields_view.fields), {
                    context : { 'bin_size' : true }
                }).pipe(self.on_record_loaded);
            }
        });
    },
    get_widgets: function() {
        return _.filter(this.getChildren(), function(obj) {
            return obj instanceof instance.web.form.FormWidget;
        });
    },
    get_fields_values: function(blacklist) {
    	blacklist = blacklist || [];
        var values = {};
        var ids = this.get_selected_ids();
        values["id"] = ids.length > 0 ? ids[0] : false;
        _.each(this.fields, function(value_, key) {
        	if (_.include(blacklist, key))
        		return;
            var val = value_.get_value();
            values[key] = val;
        });
        return values;
    },
    get_selected_ids: function() {
        var id = this.dataset.ids[this.dataset.index];
        return id ? [id] : [];
    },
    recursive_save: function() {
        var self = this;
        return $.when(this.do_save()).pipe(function(res) {
            if (self.dataset.parent_view)
                return self.dataset.parent_view.recursive_save();
        });
    },
    is_dirty: function() {
        return _.any(this.fields, function (value_) {
            return value_._dirty_flag;
        });
    },
    is_interactible_record: function() {
        var id = this.datarecord.id;
        if (!id) {
            if (this.options.not_interactible_on_create)
                return false;
        } else if (typeof(id) === "string") {
            if(instance.web.BufferedDataSet.virtual_id_regex.test(id))
                return false;
        }
        return true;
    },
    sidebar_context: function () {
        return this.do_save().pipe(_.bind(function() {return this.get_fields_values();}, this));
    },
    open_defaults_dialog: function () {
        var self = this;
        var fields = _.chain(this.fields)
            .map(function (field, name) {
                var value_ = field.get_value();
                // ignore fields which are empty, invisible, readonly, o2m
                // or m2m
                if (!value_
                        || field.get('invisible')
                        || field.get("readonly")
                        || field.field.type === 'one2many'
                        || field.field.type === 'many2many') {
                    return false;
                }
                var displayed;
                switch(field.field.type) {
                case 'selection':
                    displayed = _(field.values).find(function (option) {
                            return option[0] === value_;
                        })[1];
                    break;
                case 'many2one':
                    displayed = value_;
                    break;
                default:
                    displayed = value_;
                }

                return {
                    name: name,
                    string: field.node_atts.string,
                    value: value_,
                    displayed: displayed,
                    // convert undefined to false
                    change_default: !!field.field.change_default
                }
            })
            .compact()
            .sortBy(function (field) { return field.node_atts.string; })
            .value();
        var conditions = _.chain(fields)
            .filter(function (field) { return field.change_default; })
            .value();

        var d = new instance.web.Dialog(this, {
            title: _t("Set Default"),
            args: {
                fields: fields,
                conditions: conditions
            },
            buttons: [
                {text: _t("Close"), click: function () { d.close(); }},
                {text: _t("Save default"), click: function () {
                    var $defaults = d.$element.find('#formview_default_fields');
                    var field_to_set = $defaults.val();
                    if (!field_to_set) {
                        $defaults.parent().addClass('oe_form_invalid');
                        return;
                    }
                    var condition = d.$element.find('#formview_default_conditions').val(),
                        all_users = d.$element.find('#formview_default_all').is(':checked');
                    new instance.web.DataSet(self, 'ir.values').call(
                        'set_default', [
                            self.dataset.model,
                            field_to_set,
                            self.fields[field_to_set].get_value(),
                            all_users,
                            false,
                            condition || false
                    ]).then(function () { d.close(); });
                }}
            ]
        });
        d.template = 'FormView.set_default';
        d.open();
    },
    register_field: function(field, name) {
        this.fields[name] = field;
        this.fields_order.push(name);
        if (this.get_field(name).translate) {
            this.translatable_fields.push(field);
        }
        field.on('changed_value', this, function() {
            field._dirty_flag = true;
            if (field.is_syntax_valid()) {
                this.do_onchange(field);
                this.on_form_changed(true);
                this.do_notify_change();
            }
        });
    },
    get_field: function(field_name) {
        return this.fields_view.fields[field_name];
    },
    is_create_mode: function() {
        return !this.datarecord.id;
    },
}));

/**
 * Interface to be implemented by rendering engines for the form view.
 */
instance.web.form.FormRenderingEngineInterface = instance.web.Class.extend({
    set_fields_view: function(fields_view) {},
    set_fields_registry: function(fields_registry) {},
    render_to: function($element) {},
});

/**
 * Default rendering engine for the form view.
 * 
 * It is necessary to set the view using set_view() before usage.
 */
instance.web.form.FormRenderingEngine = instance.web.form.FormRenderingEngineInterface.extend({
    init: function(view) {
        this.view = view;
    },
    set_fields_view: function(fvg) {
        this.fvg = fvg;
    },
    set_tags_registry: function(tags_registry) {
        this.tags_registry = tags_registry;
    },
    set_fields_registry: function(fields_registry) {
        this.fields_registry = fields_registry;
    },
    render_to: function($target) {
        var self = this;
        this.$target = $target;

        // TODO: I know this will save the world and all the kitten for a moment,
        //       but one day, we will have to get rid of xml2json
        var xml = instance.web.json_node_to_xml(this.fvg.arch);
        this.$form = $('<div class="oe_form">' + xml + '</div>');
        if (this.fvg.arch.attrs && this.fvg.arch.attrs['layout'] !== 'manual') {
            this.$form.attr('layout', 'auto');
        }

        this.fields_to_init = [];
        this.tags_to_init = [];
        this.labels = {};
        this.process(this.$form);

        this.$form.appendTo(this.$target);

        _.each(this.fields_to_init, function($elem) {
            var name = $elem.attr("name");
            if (!self.fvg.fields[name]) {
                throw new Error("Field '" + name + "' specified in view could not be found.");
            }
            var obj = self.fields_registry.get_any([$elem.attr('widget'), self.fvg.fields[name].type]);
            if (!obj) {
                throw new Error("Widget type '"+ key + "' is not implemented");
            }
            var w = new (obj)(self.view, instance.web.xml_to_json($elem[0]));
            var $label = self.labels[$elem.attr("name")];
            if ($label) {
                w.set_input_id($label.attr("for"));
            }
            self.alter_field(w);
            self.view.register_field(w, $elem.attr("name"));
            w.replace($elem);
        });
        _.each(this.tags_to_init, function($elem) {
            var tag_name = $elem[0].tagName.toLowerCase();
            var obj = self.tags_registry.get_object(tag_name);
            var w = new (obj)(self.view, instance.web.xml_to_json($elem[0]));
            w.replace($elem);
        })
        // TODO: return a deferred
    },
    render_element: function(template, layout/* dictionaries */) {
        var dicts = [].slice.call(arguments).slice(2);
        dicts.unshift({ 'layout' : layout });
        var dict = _.extend.apply(_, dicts);
        dict['classnames'] = dict['class'] || ''; // class is a reserved word and might caused problem to Safari when used from QWeb
        var alt_template = template + '.' + layout;
        template = QWeb.has_template(alt_template) ? alt_template : template;
        return $(QWeb.render(template, dict));
    },
    alter_field: function(field) {
    },
    toggle_layout_debugging: function() {
        if (!this.$target.has('.oe_layout_debug_cell:first').length) {
            this.$target.find('[title]').removeAttr('title');
            this.$target.find('.oe_form_group_cell').each(function() {
                var text = 'W:' + ($(this).attr('width') || '') + ' - C:' + $(this).attr('colspan');
                $(this).attr('title', text);
            });
        }
        this.$target.toggleClass('oe_layout_debugging');
    },
    process: function($tag, layout) {
        var self = this;
        if ($tag.attr('layout') === 'auto') {
            $tag.addClass('oe_form_autolayout');
        }
        layout = $tag.attr('layout') || layout || 'auto';
        $tag.removeAttr('layout');
        var tagname = $tag[0].nodeName.toLowerCase();
        if (this.tags_registry.contains(tagname)) {
            this.tags_to_init.push($tag);
            return $tag;
        }
        var fn = self['process_' + tagname];
        if (fn) {
            var args = [].slice.call(arguments);
            args[0] = $tag;
            args[1] = layout;
            return fn.apply(self, args);
        } else {
            // generic tag handling, just process children
            $tag.children().each(function() {
                self.process($(this), layout);
            });
            self.handle_common_properties($tag, $tag);
            $tag.removeAttr("modifiers");
            return $tag;
        }
    },
    process_sheet: function($sheet, layout) {
        var $new_sheet = this.render_element('FormRenderingSheet', layout, $sheet.getAttributes());
        this.handle_common_properties($new_sheet, $sheet);
        var $dst = (layout === 'auto') ? $new_sheet.find('group:first') : $new_sheet.find('.oe_form_sheet');
        $sheet.children().appendTo($dst);
        $sheet.before($new_sheet).remove();
        this.process($new_sheet, layout);
    },
    process_form: function($form, layout) {
        var $new_form = this.render_element('FormRenderingForm', layout, $form.getAttributes());
        this.handle_common_properties($new_form, $form);
        var $dst = (layout === 'auto') ? $new_form.find('group:first') : $new_form;
        $form.children().appendTo($dst);
        if ($form[0] === this.$form[0]) {
            // If root element, replace it
            this.$form = $new_form;
        } else {
            $form.before($new_form).remove();
        }
        this.process($new_form, layout);
    },
    preprocess_field: function($field) {
        var self = this;
        var name = $field.attr('name'),
            field_colspan = parseInt($field.attr('colspan'), 10),
            field_modifiers = JSON.parse($field.attr('modifiers') || '{}');

        if ($field.attr('nolabel') === '1')
            return;
        $field.attr('nolabel', '1');
        var found = false;
        this.$form.find('label[for="' + name + '"]').each(function(i ,el) {
            $(el).parents().each(function(unused, tag) {
                var name = tag.tagName.toLowerCase();
                if (name === "field" || name in self.tags_registry.map)
                    found = true;
            });
        });
        if (found)
            return;

        $label = $('<label/>').attr({
            'for' : name,
            "modifiers": JSON.stringify({invisible: field_modifiers.invisible}),
            "string": $field.attr('string'),
            "help": $field.attr('help'),
        });
        $label.insertBefore($field);
        if (field_colspan > 1) {
            $field.attr('colspan', field_colspan - 1);
        }
        return $label;
    },
    process_field: function($field, layout) {
        var $label = this.preprocess_field($field);
        if ($label)
            this.process($label, layout);
        this.fields_to_init.push($field);
        return $field;
    },
    process_group: function($group, layout) {
        var self = this;
        if ($group.parent().is('.oe_form_group_cell')) {
            $group.parent().addClass('oe_form_group_nested');
        }
        $group.children('field').each(function() {
            self.preprocess_field($(this));
        });
        var $new_group = this.render_element('FormRenderingGroup', layout, $group.getAttributes()),
            $table;
        if ($new_group.is('table')) {
            $table = $new_group;
        } else {
            $table = $new_group.find('table:first');
        }
        $table.addClass('oe_form_group');
        var $tr, $td,
            cols = parseInt($group.attr('col') || 4, 10),
            row_cols = cols;

        var children = [];
        $group.children().each(function(a,b,c) {
            var $child = $(this);
            var colspan = parseInt($child.attr('colspan') || 1, 10);
            var tagName = $child[0].tagName.toLowerCase();
            var $td = $('<td/>').addClass('oe_form_group_cell').attr('colspan', colspan);
            var newline = tagName === 'newline';
            if ($tr && row_cols > 0 && (newline || row_cols < colspan)) {
                $tr.addClass('oe_form_group_row_incomplete');
                if (newline) {
                    $tr.addClass('oe_form_group_row_newline');
                }
            }
            if (newline) {
                $tr = null;
                return;
            }
            if (!$tr || row_cols < colspan) {
                $tr = $('<tr/>').addClass('oe_form_group_row').appendTo($table);
                row_cols = cols;
            }
            row_cols -= colspan;

            // invisibility transfer
            var field_modifiers = JSON.parse($child.attr('modifiers') || '{}');
            var invisible = field_modifiers.invisible;
            self.handle_common_properties($td, $("<dummy>").attr("modifiers", JSON.stringify({invisible: invisible})));

            $tr.append($td.append($child));
            children.push($child[0]);
        });
        if (row_cols && $td) {
            $td.attr('colspan', parseInt($td.attr('colspan'), 10) + row_cols);
        }
        $group.before($new_group).remove();

        // Now compute width of cells
        $table.find('> tbody > tr').each(function() {
            var to_compute = [],
                row_cols = cols,
                total = 100;
            $(this).children().each(function() {
                var $td = $(this),
                    $child = $td.children(':first');
                switch ($child[0].tagName.toLowerCase()) {
                    case 'separator':
                        if ($child.attr('orientation') === 'vertical') {
                            $td.addClass('oe_vertical_separator').attr('width', '1');
                            $td.empty();
                            row_cols--;
                        }
                        break;
                    case 'label':
                        if ($child.attr('for')) {
                            $td.attr('width', '1%').addClass('oe_form_group_cell_label');
                            row_cols--;
                            total--;
                        }
                        break;
                    default:
                        var width = _.str.trim($child.attr('width') || ''),
                            iwidth = parseInt(width, 10);
                        if (iwidth) {
                            if (width.substr(-1) === '%') {
                                total -= iwidth;
                                width = iwidth + '%';
                            } else {
                                // Absolute width
                                $td.css('min-width', width + 'px');
                            }
                            $td.attr('width', width);
                            $child.removeAttr('width');
                            row_cols--;
                        } else {
                            to_compute.push($td);
                        }

                }
            });
            var unit = Math.floor(total / row_cols);
            if (!$(this).is('.oe_form_group_row_incomplete')) {
                _.each(to_compute, function($td, i) {
                    var width = parseInt($td.attr('colspan'), 10) * unit;
                    $td.attr('width', ((i == to_compute.length - 1) ? total : width) + '%');
                    total -= width;
                });
            }
        });
        _.each(children, function(el) {
            self.process($(el));
        });
        this.handle_common_properties($new_group, $group);
        return $new_group;
    },
    process_notebook: function($notebook, layout) {
        var self = this;
        var pages = [];
        $notebook.find('> page').each(function() {
            var $page = $(this);
            var page_attrs = $page.getAttributes();
            page_attrs.id = _.uniqueId('notebook_page_');
            pages.push(page_attrs);
            var $new_page = self.render_element('FormRenderingNotebookPage', layout, page_attrs);
            var $dst = (layout === 'auto') ? $new_page.find('group:first') : $new_page;
            $page.children().appendTo($dst);
            $page.before($new_page).remove();
            self.handle_common_properties($new_page, $page);
        });
        var $new_notebook = this.render_element('FormRenderingNotebook', layout, { pages : pages });
        $notebook.children().appendTo($new_notebook);
        $notebook.before($new_notebook).remove();
        $new_notebook.children().each(function() {
            self.process($(this));
        });
        $new_notebook.tabs();
        this.handle_common_properties($new_notebook, $notebook);
        return $new_notebook;
    },
    process_separator: function($separator, layout) {
        var $new_separator = this.render_element('FormRenderingSeparator', layout, $separator.getAttributes());
        $separator.before($new_separator).remove();
        this.handle_common_properties($new_separator, $separator);
        return $new_separator;
    },
    process_label: function($label, layout) {
        var name = $label.attr("for"),
            field_orm = this.fvg.fields[name];
        var dict = {
            string: $label.attr('string') || (field_orm || {}).string || '',
            help: $label.attr('help') || (field_orm || {}).help || '',
            _for: name ? _.uniqueId('oe-field-input-') : undefined,
        };
        var align = parseFloat(dict.align);
        if (isNaN(align) || align === 1) {
            align = 'right';
        } else if (align === 0) {
            align = 'left';
        } else {
            align = 'center';
        }
        dict.align = align;
        var $new_label = this.render_element('FormRenderingLabel', layout, dict);
        $label.before($new_label).remove();
        this.handle_common_properties($new_label, $label);
        if (name) {
            this.labels[name] = $new_label;
        }
        return $new_label;
    },
    handle_common_properties: function($new_element, $node) {
        var str_modifiers = $node.attr("modifiers") || "{}"
        var modifiers = JSON.parse(str_modifiers);
        if (modifiers.invisible !== undefined)
            new instance.web.form.InvisibilityChanger(this.view, this.view, modifiers.invisible, $new_element);
        $new_element.addClass($node.attr("class") || "");
        $new_element.attr('style', $node.attr('style'));
    },
});

instance.web.form.FormRenderingEngineReadonly = instance.web.form.FormRenderingEngine.extend({
    alter_field: function(field) {
        field.set({"force_readonly": true});
    },
});

instance.web.form.FormDialog = instance.web.Dialog.extend({
    init: function(parent, options, view_id, dataset) {
        this._super(parent, options);
        this.dataset = dataset;
        this.view_id = view_id;
        return this;
    },
    start: function() {
        this._super();
        this.form = new instance.web.FormView(this, this.dataset, this.view_id, {
            pager: false
        });
        this.form.appendTo(this.$element);
        this.form.on_created.add_last(this.on_form_dialog_saved);
        this.form.on_saved.add_last(this.on_form_dialog_saved);
        return this;
    },
    select_id: function(id) {
        if (this.form.dataset.select_id(id)) {
            return this.form.do_show();
        } else {
            this.do_warn("Could not find id in dataset");
            return $.Deferred().reject();
        }
    },
    on_form_dialog_saved: function(r) {
        this.close();
    }
});

instance.web.form.compute_domain = function(expr, fields) {
    var stack = [];
    for (var i = expr.length - 1; i >= 0; i--) {
        var ex = expr[i];
        if (ex.length == 1) {
            var top = stack.pop();
            switch (ex) {
                case '|':
                    stack.push(stack.pop() || top);
                    continue;
                case '&':
                    stack.push(stack.pop() && top);
                    continue;
                case '!':
                    stack.push(!top);
                    continue;
                default:
                    throw new Error(_.str.sprintf(
                        _t("Unknown operator %s in domain %s"),
                        ex, JSON.stringify(expr)));
            }
        }

        var field = fields[ex[0]];
        if (!field) {
            throw new Error(_.str.sprintf(
                _t("Unknown field %s in domain %s"),
                ex[0], JSON.stringify(expr)));
        }
        var field_value = field.get_value ? field.get_value() : field.value;
        var op = ex[1];
        var val = ex[2];

        switch (op.toLowerCase()) {
            case '=':
            case '==':
                stack.push(field_value == val);
                break;
            case '!=':
            case '<>':
                stack.push(field_value != val);
                break;
            case '<':
                stack.push(field_value < val);
                break;
            case '>':
                stack.push(field_value > val);
                break;
            case '<=':
                stack.push(field_value <= val);
                break;
            case '>=':
                stack.push(field_value >= val);
                break;
            case 'in':
                if (!_.isArray(val)) val = [val];
                stack.push(_(val).contains(field_value));
                break;
            case 'not in':
                if (!_.isArray(val)) val = [val];
                stack.push(!_(val).contains(field_value));
                break;
            default:
                console.warn(
                    _t("Unsupported operator %s in domain %s"),
                    op, JSON.stringify(expr));
        }
    }
    return _.all(stack, _.identity);
};

/**
 * Must be applied over an class already possessing the PropertiesMixin.
 *
 * Apply the result of the "invisible" domain to this.$element.
 */
instance.web.form.InvisibilityChangerMixin = {
    init: function(field_manager, invisible_domain) {
        this._ic_field_manager = field_manager
        this._ic_invisible_modifier = invisible_domain;
        this._ic_field_manager.on("view_content_has_changed", this, function() {
            var result = this._ic_invisible_modifier === undefined ? false :
                instance.web.form.compute_domain(this._ic_invisible_modifier, this._ic_field_manager.fields);
            this.set({"invisible": result});
        });
        this.set({invisible: this._ic_invisible_modifier === true, force_invisible: false});
        var check = function() {
            if (this.get("invisible") || this.get('force_invisible')) {
                this.set({"effective_invisible": true});
            } else {
                this.set({"effective_invisible": false});
            }
        };
        this.on('change:invisible', this, check);
        this.on('change:force_invisible', this, check);
        _.bind(check, this)();
    },
    start: function() {
        var check_visibility = function() {
            if (this.get("effective_invisible")) {
                this.$element.hide();
            } else {
                this.$element.show();
            }
        };
        this.on("change:effective_invisible", this, check_visibility);
        _.bind(check_visibility, this)();
    },
};

instance.web.form.InvisibilityChanger = instance.web.Class.extend(_.extend({}, instance.web.PropertiesMixin, instance.web.form.InvisibilityChangerMixin, {
    init: function(parent, field_manager, invisible_domain, $element) {
        this.setParent(parent);
        instance.web.PropertiesMixin.init.call(this);
        instance.web.form.InvisibilityChangerMixin.init.call(this, field_manager, invisible_domain);
        this.$element = $element;
        this.start();
    },
}));

instance.web.form.FormWidget = instance.web.Widget.extend(_.extend({}, instance.web.form.InvisibilityChangerMixin, {
    /**
     * @constructs instance.web.form.FormWidget
     * @extends instance.web.Widget
     *
     * @param view
     * @param node
     */
    init: function(view, node) {
        this._super(view);
        this.view = view;
        this.node = node;
        this.modifiers = JSON.parse(this.node.attrs.modifiers || '{}');
        instance.web.form.InvisibilityChangerMixin.init.call(this, view, this.modifiers.invisible);

        this.view.on("view_content_has_changed", this, this.process_modifiers);
    },
    renderElement: function() {
        this._super();
        this.$element.addClass(this.node.attrs["class"] || "");
    },
    destroy: function() {
        $.fn.tipsy.clear();
        this._super.apply(this, arguments);
    },
    process_modifiers: function() {
        var compute_domain = instance.web.form.compute_domain;
        var to_set = {};
        for (var a in this.modifiers) {
            if (!_.include(["invisible"], a)) {
                var val = compute_domain(this.modifiers[a], this.view.fields);
                to_set[a] = val;
            }
        }
        this.set(to_set);
    },
    do_attach_tooltip: function(widget, trigger, options) {
        widget = widget || this;
        trigger = trigger || this.$element;
        options = _.extend({
                delayIn: 500,
                delayOut: 0,
                fade: true,
                title: function() {
                    var template = widget.template + '.tooltip';
                    if (!QWeb.has_template(template)) {
                        template = 'WidgetLabel.tooltip';
                    }
                    return QWeb.render(template, {
                        debug: instance.connection.debug,
                        widget: widget
                })},
                gravity: $.fn.tipsy.autoBounds(50, 'nw'),
                html: true,
                opacity: 0.85,
                trigger: 'hover'
            }, options || {});
        $(trigger).tipsy(options);
    },
    _build_view_fields_values: function(blacklist) {
        var a_dataset = this.view.dataset;
        var fields_values = this.view.get_fields_values(blacklist);
        var active_id = a_dataset.ids[a_dataset.index];
        _.extend(fields_values, {
            active_id: active_id || false,
            active_ids: active_id ? [active_id] : [],
            active_model: a_dataset.model,
            parent: {}
        });
        if (a_dataset.parent_view) {
        	fields_values.parent = a_dataset.parent_view.get_fields_values([a_dataset.child_name]);
        }
        return fields_values;
    },
    _build_eval_context: function(blacklist) {
        var a_dataset = this.view.dataset;
        return new instance.web.CompoundContext(a_dataset.get_context(), this._build_view_fields_values(blacklist));
    },
    /**
     * Builds a new context usable for operations related to fields by merging
     * the fields'context with the action's context.
     */
    build_context: function(blacklist) {
        // only use the model's context if there is not context on the node
        var v_context = this.node.attrs.context;
        if (! v_context) {
            v_context = (this.field || {}).context || {};
        }
        
        if (v_context.__ref || true) { //TODO: remove true
            var fields_values = this._build_eval_context(blacklist);
            v_context = new instance.web.CompoundContext(v_context).set_eval_context(fields_values);
        }
        return v_context;
    },
    build_domain: function() {
        var f_domain = this.field.domain || [];
        var n_domain = this.node.attrs.domain || null;
        // if there is a domain on the node, overrides the model's domain
        var final_domain = n_domain !== null ? n_domain : f_domain;
        if (!(final_domain instanceof Array) || true) { //TODO: remove true
            var fields_values = this._build_eval_context();
            final_domain = new instance.web.CompoundDomain(final_domain).set_eval_context(fields_values);
        }
        return final_domain;
    }
}));

instance.web.form.WidgetButton = instance.web.form.FormWidget.extend({
    template: 'WidgetButton',
    init: function(view, node) {
        this._super(view, node);
        this.force_disabled = false;
        this.string = (this.node.attrs.string || '').replace(/_/g, '');
        if (this.node.attrs.default_focus == '1') {
            // TODO fme: provide enter key binding to widgets
            this.view.default_focus_button = this;
        }
        this.view.on('view_content_has_changed', this, this.check_disable);
    },
    start: function() {
        this._super.apply(this, arguments);
        this.$element.click(this.on_click);
        if (this.node.attrs.help || instance.connection.debug) {
            this.do_attach_tooltip();
        }
    },
    on_click: function() {
        var self = this;
        this.force_disabled = true;
        this.check_disable();
        this.execute_action().always(function() {
            self.force_disabled = false;
            self.check_disable();
        });
    },
    execute_action: function() {
        var self = this;
        var exec_action = function() {
            if (self.node.attrs.confirm) {
                var def = $.Deferred();
                var dialog = instance.web.dialog($('<div/>').text(self.node.attrs.confirm), {
                    title: _t('Confirm'),
                    modal: true,
                    buttons: [
                        {text: _t("Cancel"), click: function() {
                                def.resolve();
                                $(this).dialog("close");
                            }
                        },
                        {text: _t("Ok"), click: function() {
                                self.on_confirmed().then(function() {
                                    def.resolve();
                                });
                                $(this).dialog("close");
                            }
                        }
                    ]
                });
                return def.promise();
            } else {
                return self.on_confirmed();
            }
        };
        if (!this.node.attrs.special) {
            this.view.force_dirty = true;
            return this.view.recursive_save().pipe(exec_action);
        } else {
            return exec_action();
        }
    },
    on_confirmed: function() {
        var self = this;

        var context = this.node.attrs.context;
        if (context && context.__ref) {
            context = new instance.web.CompoundContext(context);
            context.set_eval_context(this._build_eval_context());
        }

        return this.view.do_execute_action(
            _.extend({}, this.node.attrs, {context: context}),
            this.view.dataset, this.view.datarecord.id, function () {
                self.view.reload();
            });
    },
    check_disable: function() {
        var disabled = (this.force_disabled || !this.view.is_interactible_record());
        this.$element.prop('disabled', disabled);
        this.$element.css('color', disabled ? 'grey' : '');
    }
});

/**
 * Interface to be implemented by fields.
 * 
 * Properties:
 *     - readonly: boolean. If set to true the field should appear in readonly mode.
 *     - force_readonly: boolean, When it is true, the field should always appear
 *      in read only mode, no matter what the value of the "readonly" property can be.
 * Events:
 *     - changed_value: triggered to inform the view to check on_changes
 * 
 */
instance.web.form.FieldMixin = {
    /**
     * Constructor takes 2 arguments:
     * - field_manager: Implements FieldManagerMixin
     * - node: the "<field>" node in json form
     */
    init: function(field_manager, node) {},
    /**
     * Called by the form view to indicate the value of the field.
     * 
     * set_value() may return an object that can be passed to $.when() that represents the moment when
     * the field has finished all operations necessary before the user can effectively use the widget.
     * 
     * Multiple calls to set_value() can occur at any time and must be handled correctly by the implementation,
     * regardless of any asynchronous operation currently running and the status of any promise that a
     * previous call to set_value() could have returned.
     * 
     * set_value() must be able, at any moment, to handle the syntax returned by the "read" method of the
     * osv class in the OpenERP server as well as the syntax used by the set_value() (see below). It must
     * also be able to handle any other format commonly used in the _defaults key on the models in the addons
     * as well as any format commonly returned in a on_change. It must be able to autodetect those formats as
     * no information is ever given to know which format is used.
     */
    set_value: function(value_) {},
    /**
     * Get the current value of the widget.
     * 
     * Must always return a syntaxically correct value to be passed to the "write" method of the osv class in
     * the OpenERP server, although it is not assumed to respect the constraints applied to the field.
     * For example if the field is marqued as "required", a call to get_value() can return false.
     * 
     * get_value() can also be called *before* a call to set_value() and, in that case, is supposed to
     * return a defaut value according to the type of field.
     * 
     * This method is always assumed to perform synchronously, it can not return a promise.
     * 
     * If there was no user interaction to modify the value of the field, it is always assumed that
     * get_value() return the same semantic value than the one passed in the last call to set_value(),
     * altough the syntax can be different. This can be the case for type of fields that have a different
     * syntax for "read" and "write" (example: m2o: set_value([0, "Administrator"]), get_value() => 0).
     */
    get_value: function() {},
    /**
     * Inform the current object of the id it should use to match a html <label> that exists somewhere in the
     * view.
     */
    set_input_id: function(id) {},
    /**
     * Returns true if is_syntax_valid() returns true and the value is semantically
     * valid too according to the semantic restrictions applied to the field.
     */
    is_valid: function() {},
    /**
     * Returns true if the field holds a value which is syntaxically correct, ignoring
     * the potential semantic restrictions applied to the field.
     */
    is_syntax_valid: function() {},
    /**
     * Must set the focus on the field.
     */
    focus: function() {},
};

/**
 * Abstract class for classes implementing FieldMixin.
 * 
 * Properties:
 *     - effective_readonly: when it is true, the widget is displayed as readonly. Vary depending
 *      the values of the "readonly" property and the "force_readonly" property on the field manager.
 *     - value: useful property to hold the value of the field. By default, set_value() and get_value()
 *     set and retrieve the value property. Changing the value property also triggers automatically
 *     a 'changed_value' event that inform the view to trigger on_changes.
 * 
 */
instance.web.form.AbstractField = instance.web.form.FormWidget.extend(_.extend({}, instance.web.form.FieldMixin, {
    /**
     * @constructs instance.web.form.AbstractField
     * @extends instance.web.form.FormWidget
     *
     * @param field_manager
     * @param node
     */
    init: function(field_manager, node) {
        this._super(field_manager, node);
        this.field_manager = field_manager;
        this.name = this.node.attrs.name;
        this.set({'value': false});
        this.field = this.field_manager.get_field(this.name);
        this.set({required: this.modifiers['required'] === true});
        
        // some events to make the property "effective_readonly" sync automatically with "readonly" and
        // "force_readonly"
        this.set({"readonly": this.modifiers['readonly'] === true});
        var test_effective_readonly = function() {
            this.set({"effective_readonly": this.get("readonly") || !!this.get("force_readonly")});
        };
        this.on("change:readonly", this, test_effective_readonly);
        this.on("change:force_readonly", this, test_effective_readonly);
        _.bind(test_effective_readonly, this)();
        
        this.on("change:value", this, function() {
            if (! this._inhibit_on_change)
                this.trigger('changed_value');
            this._check_css_flags();
        });
    },
    renderElement: function() {
        var self = this;
        this._super();
        if (this.field.translate) {
            this.$element.addClass('oe_form_field_translatable');
            this.$element.find('.oe_field_translate').click(_.bind(function() {
                this.field_manager.open_translate_dialog(this);
            }, this));
        }
        this.$label = this.view.$element.find('label[for=' + this.id_for_label + ']');
        if (instance.connection.debug) {
            this.do_attach_tooltip(this, this.$label[0] || this.$element);
            this.$label.off('dblclick').on('dblclick', function() {
                console.log("Field '%s' of type '%s' in View: %o", self.name, (self.node.attrs.widget || self.field.type), self.view);
                window.w = self;
                console.log("window.w =", window.w);
            });
        }
        if (!this.disable_utility_classes) {
            this.off("change:required", this, this._set_required);
            this.on("change:required", this, this._set_required);
            this._set_required();
        }
    },
    /**
     * Private. Do not use.
     */
    _set_required: function() {
        this.$element.toggleClass('oe_form_required', this.get("required"));
    },
    set_value: function(value_) {
        this._inhibit_on_change = true;
        this.set({'value': value_});
        this._inhibit_on_change = false;
    },
    get_value: function() {
        return this.get('value');
    },
    is_valid: function() {
        return this.is_syntax_valid() && (! this.get('required') || ! this.is_false());
    },
    is_syntax_valid: function() {
        return true;
    },
    /**
     * Method useful to implement to ease validity testing. Must return true if the current
     * value is similar to false in OpenERP.
     */
    is_false: function() {
        return this.get('value') === false;
    },
    _check_css_flags: function(show_invalid) {
        if (this.field.translate) {
            this.$element.find('.oe_field_translate').toggle(!this.field_manager.is_create_mode());
        }
        if (!this.disable_utility_classes) {
            if (this.field_manager.get('display_invalid_fields')) {
                this.$element.toggleClass('oe_form_invalid', !this.is_valid());
            }
        }
    },
    focus: function() {
    },
    /**
     * Utility method to focus an element, but only after a small amount of time.
     */
    delay_focus: function($elem) {
        setTimeout(function() {
            $elem.focus();
        }, 50);
    },
    /**
     * Utility method to get the widget options defined in the field xml description.
     */
    get_definition_options: function() {
        if (!this.definition_options) {
            var str = this.node.attrs.options || '{}';
            this.definition_options = JSON.parse(str);
        }
        return this.definition_options;
    },
    set_input_id: function(id) {
        this.id_for_label = id;
    },
}));

/**
 * A mixin to apply on any field that has to completely re-render when its readonly state
 * switch.
 */
instance.web.form.ReinitializeFieldMixin =  {
    /**
     * Default implementation of start(), use it or call explicitly initialize_field().
     */
    start: function() {
        this._super();
        this.initialize_field();
    },
    initialize_field: function() {
        this.on("change:effective_readonly", this, function() {
            this.destroy_content();
            this.renderElement();
            this.initialize_content();
            this.render_value();
        });
        this.initialize_content();
        this.render_value();
    },
    /**
     * Called to destroy anything that could have been created previously, called before a
     * re-initialization.
     */
    destroy_content: function() {},
    /**
     * Called to initialize the content.
     */
    initialize_content: function() {},
    /**
     * Called to render the value. Should also be explicitly called at the end of a set_value().
     */
    render_value: function() {},
};

instance.web.form.FieldChar = instance.web.form.AbstractField.extend(_.extend({}, instance.web.form.ReinitializeFieldMixin, {
    template: 'FieldChar',
    init: function (field_manager, node) {
        this._super(field_manager, node);
        this.password = this.node.attrs.password === 'True' || this.node.attrs.password === '1';
    },
    initialize_content: function() {
        var self = this;
        this.$element.find('input').change(function() {
            self.set({'value': instance.web.parse_value(self.$element.find('input').val(), self)});
        });
    },
    set_value: function(value_) {
        this._super(value_);
        this.render_value();
    },
    render_value: function() {
        var show_value = instance.web.format_value(this.get('value'), this, '');
        if (!this.get("effective_readonly")) {
            this.$element.find('input').val(show_value);
        } else {
            if (this.password) {
                show_value = new Array(show_value.length + 1).join('*');
            }
            this.$element.text(show_value);
        }
    },
    is_syntax_valid: function() {
        if (!this.get("effective_readonly")) {
            try {
                var value_ = instance.web.parse_value(this.$element.find('input').val(), this, '');
                return true;
            } catch(e) {
                return false;
            }
        }
        return true;
    },
    is_false: function() {
        return this.get('value') === '';
    },
    focus: function() {
        this.delay_focus(this.$element.find('input:first'));
    }
}));

instance.web.form.FieldID = instance.web.form.FieldChar.extend({
    
});

instance.web.form.FieldEmail = instance.web.form.FieldChar.extend({
    template: 'FieldEmail',
    initialize_content: function() {
        this._super();
        this.$element.find('button').click(this.on_button_clicked);
    },
    render_value: function() {
        if (!this.get("effective_readonly")) {
            this._super();
        } else {
            this.$element.find('a')
                    .attr('href', 'mailto:' + this.get('value'))
                    .text(this.get('value'));
        }
    },
    on_button_clicked: function() {
        if (!this.get('value') || !this.is_syntax_valid()) {
            this.do_warn("E-mail error", "Can't send email to invalid e-mail address");
        } else {
            location.href = 'mailto:' + this.get('value');
        }
    }
});

instance.web.form.FieldUrl = instance.web.form.FieldChar.extend({
    template: 'FieldUrl',
    initialize_content: function() {
        this._super();
        this.$element.find('button').click(this.on_button_clicked);
    },
    render_value: function() {
        if (!this.get("effective_readonly")) {
            this._super();
        } else {
            var tmp = this.get('value');
            var s = /(\w+):(.+)/.exec(tmp);
            if (!s) {
                tmp = "http://" + this.get('value');
            }
            this.$element.find('a').attr('href', tmp).text(tmp);
        }
    },
    on_button_clicked: function() {
        if (!this.get('value')) {
            this.do_warn("Resource error", "This resource is empty");
        } else {
            var url = $.trim(this.get('value'));
            if(/^www\./i.test(url))
                url = 'http://'+url;
            window.open(url);
        }
    }
});

instance.web.form.FieldFloat = instance.web.form.FieldChar.extend({
    is_field_number: true,
    init: function (field_manager, node) {
        this._super(field_manager, node);
        this.set({'value': 0});
        if (this.node.attrs.digits) {
            this.digits = py.eval(node.attrs.digits);
        } else {
            this.digits = this.field.digits;
        }
    },
    set_value: function(value_) {
        if (value_ === false || value_ === undefined) {
            // As in GTK client, floats default to 0
            value_ = 0;
        }
        this._super.apply(this, [value_]);
    }
});

instance.web.DateTimeWidget = instance.web.OldWidget.extend({
    template: "web.datetimepicker",
    jqueryui_object: 'datetimepicker',
    type_of_date: "datetime",
    init: function(parent) {
        this._super(parent);
        this.name = parent.name;
    },
    start: function() {
        var self = this;
        this.$input = this.$element.find('input.oe_datepicker_master');
        this.$input_picker = this.$element.find('input.oe_datepicker_container');
        this.$input.change(this.on_change);
        this.picker({
            onSelect: this.on_picker_select,
            changeMonth: true,
            changeYear: true,
            showWeek: true,
            showButtonPanel: true
        });
        this.$element.find('img.oe_datepicker_trigger').click(function() {
            if (!self.get("effective_readonly") && !self.picker('widget').is(':visible')) {
                self.picker('setDate', self.get('value') ? instance.web.auto_str_to_date(self.get('value')) : new Date());
                self.$input_picker.show();
                self.picker('show');
                self.$input_picker.hide();
            }
        });
        this.set_readonly(false);
        this.set({'value': false});
    },
    picker: function() {
        return $.fn[this.jqueryui_object].apply(this.$input_picker, arguments);
    },
    on_picker_select: function(text, instance_) {
        var date = this.picker('getDate');
        this.$input.val(date ? this.format_client(date) : '').change();
    },
    set_value: function(value_) {
        this.set({'value': value_});
        this.$input.val(value_ ? this.format_client(value_) : '');
    },
    get_value: function() {
        return this.get('value');
    },
    set_value_from_ui_: function() {
        var value_ = this.$input.val() || false;
        this.set({'value': this.parse_client(value_)});
    },
    set_readonly: function(readonly) {
        this.readonly = readonly;
        this.$input.prop('readonly', this.readonly);
        this.$element.find('img.oe_datepicker_trigger').toggleClass('oe_input_icon_disabled', readonly);
    },
    is_valid_: function() {
        var value_ = this.$input.val();
        if (value_ === "") {
            return true;
        } else {
            try {
                this.parse_client(value_);
                return true;
            } catch(e) {
                return false;
            }
        }
    },
    parse_client: function(v) {
        return instance.web.parse_value(v, {"widget": this.type_of_date});
    },
    format_client: function(v) {
        return instance.web.format_value(v, {"widget": this.type_of_date});
    },
    on_change: function() {
        if (this.is_valid_()) {
            this.set_value_from_ui_();
        }
    }
});

instance.web.DateWidget = instance.web.DateTimeWidget.extend({
    jqueryui_object: 'datepicker',
    type_of_date: "date"
});

instance.web.form.FieldDatetime = instance.web.form.AbstractField.extend(_.extend({}, instance.web.form.ReinitializeFieldMixin, {
    template: "EmptyComponent",
    build_widget: function() {
        return new instance.web.DateTimeWidget(this);
    },
    destroy_content: function() {
        if (this.datewidget) {
            this.datewidget.destroy();
            this.datewidget = undefined;
        }
    },
    initialize_content: function() {
        if (!this.get("effective_readonly")) {
            this.datewidget = this.build_widget();
            this.datewidget.on_change.add_last(_.bind(function() {
                this.set({'value': this.datewidget.get_value()});
            }, this));
            this.datewidget.appendTo(this.$element);
        }
    },
    set_value: function(value_) {
        this._super(value_);
        this.render_value();
    },
    render_value: function() {
        if (!this.get("effective_readonly")) {
            this.datewidget.set_value(this.get('value'));
        } else {
            this.$element.text(instance.web.format_value(this.get('value'), this, ''));
        }
    },
    is_syntax_valid: function() {
        if (!this.get("effective_readonly")) {
            return this.datewidget.is_valid_();
        }
        return true;
    },
    is_false: function() {
        return this.get('value') === '';
    },
    focus: function() {
        if (this.datewidget && this.datewidget.$input)
            this.delay_focus(this.datewidget.$input);
    }
}));

instance.web.form.FieldDate = instance.web.form.FieldDatetime.extend({
    build_widget: function() {
        return new instance.web.DateWidget(this);
    }
});

instance.web.form.FieldText = instance.web.form.AbstractField.extend(_.extend({}, instance.web.form.ReinitializeFieldMixin, {
    template: 'FieldText',
    initialize_content: function() {
        this.$textarea = this.$element.find('textarea');
        if (!this.get("effective_readonly")) {
            this.$textarea.change(_.bind(function() {
                this.set({'value': instance.web.parse_value(this.$textarea.val(), this)});
            }, this));
        } else {
            this.$textarea.attr('disabled', 'disabled');
        }
    },
    set_value: function(value_) {
        this._super.apply(this, arguments);
        this.render_value();
    },
    render_value: function() {
        var show_value = instance.web.format_value(this.get('value'), this, '');
        this.$textarea.val(show_value);
        if (show_value && this.view.options.resize_textareas) {
            this.do_resize(this.view.options.resize_textareas);
        }
    },
    is_syntax_valid: function() {
        if (!this.get("effective_readonly")) {
            try {
                var value_ = instance.web.parse_value(this.$textarea.val(), this, '');
                return true;
            } catch(e) {
                return false;
            }
        }
        return true;
    },
    is_false: function() {
        return this.get('value') === '';
    },
    focus: function($element) {
        this.delay_focus(this.$textarea);
    },
    do_resize: function(max_height) {
        max_height = parseInt(max_height, 10);
        var $input = this.$textarea,
            $div = $('<div style="position: absolute; z-index: 1000; top: 0"/>').width($input.width()),
            new_height;
        $div.text($input.val());
        _.each('font-family,font-size,white-space'.split(','), function(style) {
            $div.css(style, $input.css(style));
        });
        $div.appendTo($('body'));
        new_height = $div.height();
        if (new_height < 90) {
            new_height = 90;
        }
        if (!isNaN(max_height) && new_height > max_height) {
            new_height = max_height;
        }
        $div.remove();
        $input.height(new_height);
    },
}));

instance.web.form.FieldBoolean = instance.web.form.AbstractField.extend({
    template: 'FieldBoolean',
    start: function() {
        this._super.apply(this, arguments);
        this.$checkbox = $("input", this.$element);
        this.$element.click(_.bind(function() {
            this.set({'value': this.$checkbox.is(':checked')});
        }, this));
        var check_readonly = function() {
            this.$checkbox.prop('disabled', this.get("effective_readonly"));
        };
        this.on("change:effective_readonly", this, check_readonly);
        _.bind(check_readonly, this)();
    },
    set_value: function(value_) {
        this._super.apply(this, arguments);
        this.$checkbox[0].checked = value_;
    },
    focus: function() {
        this.delay_focus(this.$checkbox);
    }
});

instance.web.form.FieldProgressBar = instance.web.form.AbstractField.extend({
    template: 'FieldProgressBar',
    start: function() {
        this._super.apply(this, arguments);
        this.$element.progressbar({
            value: this.get('value'),
            disabled: this.get("effective_readonly")
        });
    },
    set_value: function(value_) {
        this._super.apply(this, arguments);
        var show_value = Number(value_);
        if (isNaN(show_value)) {
            show_value = 0;
        }
        var formatted_value = instance.web.format_value(show_value, { type : 'float' }, '0');
        this.$element.progressbar('option', 'value', show_value).find('span').html(formatted_value + '%');
    }
});

instance.web.form.FieldTextXml = instance.web.form.AbstractField.extend({
// to replace view editor
});

instance.web.form.FieldSelection = instance.web.form.AbstractField.extend(_.extend({}, instance.web.form.ReinitializeFieldMixin, {
    template: 'FieldSelection',
    init: function(field_manager, node) {
        var self = this;
        this._super(field_manager, node);
        this.values = _.clone(this.field.selection);
        _.each(this.values, function(v, i) {
            if (v[0] === false && v[1] === '') {
                self.values.splice(i, 1);
            }
        });
        this.values.unshift([false, '']);
    },
    initialize_content: function() {
        // Flag indicating whether we're in an event chain containing a change
        // event on the select, in order to know what to do on keyup[RETURN]:
        // * If the user presses [RETURN] as part of changing the value of a
        //   selection, we should just let the value change and not let the
        //   event broadcast further (e.g. to validating the current state of
        //   the form in editable list view, which would lead to saving the
        //   current row or switching to the next one)
        // * If the user presses [RETURN] with a select closed (side-effect:
        //   also if the user opened the select and pressed [RETURN] without
        //   changing the selected value), takes the action as validating the
        //   row
        var ischanging = false;
        this.$element.find('select')
            .change(_.bind(function() {
                this.set({'value': this.values[this.$element.find('select')[0].selectedIndex][0]});
            }, this))
            .change(function () { ischanging = true; })
            .click(function () { ischanging = false; })
            .keyup(function (e) {
                if (e.which !== 13 || !ischanging) { return; }
                e.stopPropagation();
                ischanging = false;
            });
    },
    set_value: function(value_) {
        value_ = value_ === null ? false : value_;
        value_ = value_ instanceof Array ? value_[0] : value_;
        this._super(value_);
        this.render_value();
    },
    render_value: function() {
        if (!this.get("effective_readonly")) {
            var index = 0;
            for (var i = 0, ii = this.values.length; i < ii; i++) {
                if (this.values[i][0] === this.get('value')) index = i;
            }
            this.$element.find('select')[0].selectedIndex = index;
        } else {
            var self = this;
            var option = _(this.values)
                .detect(function (record) { return record[0] === self.get('value'); }); 
            this.$element.text(option ? option[1] : this.values[0][1]);
        }
    },
    is_syntax_valid: function() {
        if (this.get("effective_readonly")) {
            return true;
        }
        var value_ = this.values[this.$element.find('select')[0].selectedIndex];
        return !! value_;
    },
    focus: function() {
        this.delay_focus(this.$element.find('select:first'));
    }
}));

// jquery autocomplete tweak to allow html
(function() {
    var proto = $.ui.autocomplete.prototype,
        initSource = proto._initSource;

    function filter( array, term ) {
        var matcher = new RegExp( $.ui.autocomplete.escapeRegex(term), "i" );
        return $.grep( array, function(value_) {
            return matcher.test( $( "<div>" ).html( value_.label || value_.value || value_ ).text() );
        });
    }

    $.extend( proto, {
        _initSource: function() {
            if ( this.options.html && $.isArray(this.options.source) ) {
                this.source = function( request, response ) {
                    response( filter( this.options.source, request.term ) );
                };
            } else {
                initSource.call( this );
            }
        },

        _renderItem: function( ul, item) {
            return $( "<li></li>" )
                .data( "item.autocomplete", item )
                .append( $( "<a></a>" )[ this.options.html ? "html" : "text" ]( item.label ) )
                .appendTo( ul );
        }
    });
})();

instance.web.form.dialog = function(content, options) {
    options = _.extend({
        width: '90%',
        height: 'auto',
        min_width: '800px'
    }, options || {});
    var dialog = new instance.web.Dialog(null, options, content).open();
    return dialog.$element;
};

/**
 * A mixin containing some useful methods to handle completion inputs.
 */
instance.web.form.CompletionFieldMixin = {
    init: function() {
        this.limit = 7;
        this.orderer = new instance.web.DropMisordered();
    },
    /**
     * Call this method to search using a string.
     */
    get_search_result: function(search_val) {
        var self = this;

        var dataset = new instance.web.DataSet(this, this.field.relation, self.build_context());

        return this.orderer.add(dataset.name_search(
                search_val, self.build_domain(), 'ilike', this.limit + 1)).pipe(function(data) {
            self.last_search = data;
            // possible selections for the m2o
            var values = _.map(data, function(x) {
                return {
                    label: _.str.escapeHTML(x[1]),
                    value:x[1],
                    name:x[1],
                    id:x[0]
                };
            });

            // search more... if more results that max
            if (values.length > self.limit) {
                values = values.slice(0, self.limit);
                values.push({label: _t("<em>   Search More...</em>"), action: function() {
                    dataset.name_search(search_val, self.build_domain(), 'ilike'
                    , false, function(data) {
                        self._search_create_popup("search", data);
                    });
                }});
            }
            // quick create
            var raw_result = _(data.result).map(function(x) {return x[1];});
            if (search_val.length > 0 && !_.include(raw_result, search_val)) {
                values.push({label: _.str.sprintf(_t('<em>   Create "<strong>%s</strong>"</em>'),
                        $('<span />').text(search_val).html()), action: function() {
                    self._quick_create(search_val);
                }});
            }
            // create...
            values.push({label: _t("<em>   Create and Edit...</em>"), action: function() {
                self._search_create_popup("form", undefined, {"default_name": search_val});
            }});

            return values;
        });
    },
    _quick_create: function(name) {
        var self = this;
        var slow_create = function () {
            self._search_create_popup("form", undefined, {"default_name": name});
        };
        if (self.get_definition_options().quick_create === undefined || self.get_definition_options().quick_create) {
            new instance.web.DataSet(this, this.field.relation, self.build_context())
                .name_create(name, function(data) {
                    self.add_id(data[0]);
                }).fail(function(error, event) {
                    event.preventDefault();
                    slow_create();
                });
        } else
            slow_create();
    },
    // all search/create popup handling
    _search_create_popup: function(view, ids, context) {
        var self = this;
        var pop = new instance.web.form.SelectCreatePopup(this);
        pop.select_element(
            self.field.relation,
            {
                title: (view === 'search' ? _t("Search: ") : _t("Create: ")) + (this.string || this.name),
                initial_ids: ids ? _.map(ids, function(x) {return x[0]}) : undefined,
                initial_view: view,
                disable_multiple_selection: true
            },
            self.build_domain(),
            new instance.web.CompoundContext(self.build_context(), context || {})
        );
        pop.on_select_elements.add(function(element_ids) {
            self.add_id(element_ids[0]);
        });
    },
    /**
     * To implement.
     */
    add_id: function(id) {},
};

instance.web.form.FieldMany2One = instance.web.form.AbstractField.extend(_.extend({}, instance.web.form.ReinitializeFieldMixin,
        instance.web.form.CompletionFieldMixin, {
    template: "FieldMany2One",
    init: function(field_manager, node) {
        this._super(field_manager, node);
        instance.web.form.CompletionFieldMixin.init.call(this);
        this.set({'value': false});
        this.display_value = {};
        this.last_search = [];
        this.floating = false;
        this.inhibit_on_change = false;
    },
    start: function() {
        this._super();
        instance.web.form.ReinitializeFieldMixin.start.call(this);
        this.on("change:value", this, function() {
            this.floating = false;
            this.render_value();
        });
    },
    initialize_content: function() {
        if (!this.get("effective_readonly"))
            this.render_editable();
        this.render_value();
    },
    render_editable: function() {
        var self = this;
        this.$input = this.$element.find("input");
        
        self.$input.tipsy({
            title: function() {
                return "No element was selected, you should create or select one from the dropdown list.";
            },
            trigger:'manual',
            fade: true,
        });
        
        this.$drop_down = this.$element.find(".oe-m2o-drop-down-button");
        this.$follow_button = $(".oe-m2o-cm-button", this.$element);
        
        this.$follow_button.click(function() {
            if (!self.get('value')) {
                return;
            }
            var pop = new instance.web.form.FormOpenPopup(self.view);
            pop.show_element(
                self.field.relation,
                self.get("value"),
                self.build_context(),
                {
                    title: _t("Open: ") + (self.string || self.name)
                }
            );
            pop.on_write_completed.add_last(function() {
                self.display_value = {};
                self.render_value();
            });
        });

        // some behavior for input
        this.$input.keyup(function() {
            if (self.$input.val() === "") {
                self.set({value: false});
            } else {
                self.floating = true;
            }
        });
        this.$drop_down.click(function() {
            if (self.$input.autocomplete("widget").is(":visible")) {
                self.$input.autocomplete("close");
            } else {
                if (self.get("value") && ! self.floating) {
                    self.$input.autocomplete("search", "");
                } else {
                    self.$input.autocomplete("search");
                }
                self.$input.focus();
            }
        });
        var tip_def = $.Deferred();
        var untip_def = $.Deferred();
        var tip_delay = 200;
        var tip_duration = 3000;
        var anyoneLoosesFocus = function() {
            if (self.floating) {
                if (self.last_search.length > 0) {
                    if (self.last_search[0][0] != self.get("value")) {
                        self.display_value = {};
                        self.display_value["" + self.last_search[0][0]] = self.last_search[0][1];
                        self.set({value: self.last_search[0][0]});
                    } else {
                        self.render_value();
                    }
                } else {
                    self.set({value: false});
                }
            }
            if (! self.get("value")) {
                tip_def.reject();
                untip_def.reject();
                tip_def = $.Deferred();
                tip_def.then(function() {
                    self.$input.tipsy("show");
                });
                setTimeout(function() {
                    tip_def.resolve();
                    untip_def.reject();
                    untip_def = $.Deferred();
                    untip_def.then(function() {
                        self.$input.tipsy("hide");
                    });
                    setTimeout(function() {untip_def.resolve();}, tip_duration);
                }, tip_delay);
            } else {
                tip_def.reject();
            }
        };
        this.$input.focusout(anyoneLoosesFocus);

        var isSelecting = false;
        // autocomplete
        this.$input.autocomplete({
            source: function(req, resp) {
                self.get_search_result(req.term).then(function(result) {
                    resp(result);
                });
            },
            select: function(event, ui) {
                isSelecting = true;
                var item = ui.item;
                if (item.id) {
                    self.display_value = {};
                    self.display_value["" + item.id] = item.name;
                    self.set({value: item.id});
                } else if (item.action) {
                    self.floating = true;
                    item.action();
                    return false;
                }
            },
            focus: function(e, ui) {
                e.preventDefault();
            },
            html: true,
            close: anyoneLoosesFocus,
            minLength: 0,
            delay: 0
        });
        this.$input.autocomplete("widget").addClass("openerp");
        // used to correct a bug when selecting an element by pushing 'enter' in an editable list
        this.$input.keyup(function(e) {
            if (e.which === 13) {
                if (isSelecting)
                    e.stopPropagation();
            }
            isSelecting = false;
        });
    },

    render_value: function(no_recurse) {
        var self = this;
        if (! this.get("value")) {
            this.display_string("");
            return;
        }
        var display = this.display_value["" + this.get("value")];
        if (display) {
            this.display_string(display);
            return;
        }
        if (! no_recurse) {
            var dataset = new instance.web.DataSetStatic(this, this.field.relation, self.view.dataset.get_context());
            dataset.name_get([self.get("value")], function(data) {
                self.display_value["" + self.get("value")] = data[0][1];
                self.render_value(true);
            });
        }
    },
    display_string: function(str) {
        var self = this;
        if (!this.get("effective_readonly")) {
            this.$input.val(str);
        } else {
            this.$element.find('a')
                 .unbind('click')
                 .text(str)
                 .click(function () {
                    self.do_action({
                        type: 'ir.actions.act_window',
                        res_model: self.field.relation,
                        res_id: self.get("value"),
                        context: self.build_context(),
                        views: [[false, 'form']],
                        target: 'current'
                    });
                    return false;
                 });
        }
    },
    set_value: function(value_) {
        var self = this;
        if (value_ instanceof Array) {
            this.display_value = {};
            this.display_value["" + value_[0]] = value_[1];
            value_ = value_[0];
        }
        value_ = value_ || false;
        this.inhibit_on_change = true;
        this._super(value_);
        this.inhibit_on_change = false;
    },
    add_id: function(id) {
        this.display_value = {};
        this.set({value: id});
    },
    is_false: function() {
        return ! this.get("value");
    },
    focus: function () {
        this.delay_focus(this.$input);
    }
}));

/*
# Values: (0, 0,  { fields })    create
#         (1, ID, { fields })    update
#         (2, ID)                remove (delete)
#         (3, ID)                unlink one (target id or target of relation)
#         (4, ID)                link
#         (5)                    unlink all (only valid for one2many)
*/
var commands = {
    // (0, _, {values})
    CREATE: 0,
    'create': function (values) {
        return [commands.CREATE, false, values];
    },
    // (1, id, {values})
    UPDATE: 1,
    'update': function (id, values) {
        return [commands.UPDATE, id, values];
    },
    // (2, id[, _])
    DELETE: 2,
    'delete': function (id) {
        return [commands.DELETE, id, false];
    },
    // (3, id[, _]) removes relation, but not linked record itself
    FORGET: 3,
    'forget': function (id) {
        return [commands.FORGET, id, false];
    },
    // (4, id[, _])
    LINK_TO: 4,
    'link_to': function (id) {
        return [commands.LINK_TO, id, false];
    },
    // (5[, _[, _]])
    DELETE_ALL: 5,
    'delete_all': function () {
        return [5, false, false];
    },
    // (6, _, ids) replaces all linked records with provided ids
    REPLACE_WITH: 6,
    'replace_with': function (ids) {
        return [6, false, ids];
    }
};
instance.web.form.FieldOne2Many = instance.web.form.AbstractField.extend({
    multi_selection: false,
    disable_utility_classes: true,
    init: function(field_manager, node) {
        this._super(field_manager, node);
        lazy_build_o2m_kanban_view();
        this.is_loaded = $.Deferred();
        this.initial_is_loaded = this.is_loaded;
        this.is_setted = $.Deferred();
        this.form_last_update = $.Deferred();
        this.init_form_last_update = this.form_last_update;
    },
    start: function() {
        this._super.apply(this, arguments);

        var self = this;

        this.dataset = new instance.web.form.One2ManyDataSet(this, this.field.relation);
        this.dataset.o2m = this;
        this.dataset.parent_view = this.view;
        this.dataset.child_name = this.name;
        //this.dataset.child_name = 
        this.dataset.on_change.add_last(function() {
            self.trigger_on_change();
        });

        this.is_setted.then(function() {
            self.load_views();
        });
        this.is_loaded.then(function() {
            self.on("change:effective_readonly", self, function() {
                self.is_loaded = self.is_loaded.pipe(function() {
                    self.viewmanager.destroy();
                    return $.when(self.load_views()).then(function() {
                        self.reload_current_view();
                    });
                });
            });
        });
    },
    trigger_on_change: function() {
        var tmp = this.doing_on_change;
        this.doing_on_change = true;
        this.trigger('changed_value');
        this.doing_on_change = tmp;
    },
    load_views: function() {
        var self = this;
        
        var modes = this.node.attrs.mode;
        modes = !!modes ? modes.split(",") : ["tree"];
        var views = [];
        _.each(modes, function(mode) {
            var view = {
                view_id: false,
                view_type: mode == "tree" ? "list" : mode,
                options: {}
            };
            if (self.field.views && self.field.views[mode]) {
                view.embedded_view = self.field.views[mode];
            }
            if(view.view_type === "list") {
                view.options.selectable = self.multi_selection;
                if (self.get("effective_readonly")) {
                    view.options.addable = null;
                    view.options.deletable = null;
                }
            } else if (view.view_type === "form") {
                if (self.get("effective_readonly")) {
                    view.view_type = 'form';
                }
                view.options.not_interactible_on_create = true;
            } else if (view.view_type === "kanban") {
                if (self.get("effective_readonly")) {
                    view.options.action_buttons = false;
                    view.options.quick_creatable = false;
                }
            }
            views.push(view);
        });
        this.views = views;

        this.viewmanager = new instance.web.form.One2ManyViewManager(this, this.dataset, views, {});
        this.viewmanager.o2m = self;
        var once = $.Deferred().then(function() {
            self.init_form_last_update.resolve();
        });
        var def = $.Deferred().then(function() {
            self.initial_is_loaded.resolve();
        });
        this.viewmanager.on_controller_inited.add_last(function(view_type, controller) {
            controller.o2m = self;
            if (view_type == "list") {
                if (self.get("effective_readonly"))
                    controller.set_editable(false);
            } else if (view_type === "form") {
                if (self.get("effective_readonly")) {
                    $(".oe_form_buttons", controller.$element).children().remove();
                }
                controller.on_record_loaded.add_last(function() {
                    once.resolve();
                });
                controller.on_pager_action.add_first(function() {
                    self.save_any_view();
                });
            } else if (view_type == "graph") {
                self.reload_current_view()
            }
            def.resolve();
        });
        this.viewmanager.on_mode_switch.add_first(function(n_mode, b, c, d, e) {
            $.when(self.save_any_view()).then(function() {
                if(n_mode === "list")
                    $.async_when().then(function() {self.reload_current_view();});
            });
        });
        this.is_setted.then(function() {
            $.async_when().then(function () {
                self.viewmanager.appendTo(self.$element);
            });
        });
        return def;
    },
    reload_current_view: function() {
        var self = this;
        return self.is_loaded = self.is_loaded.pipe(function() {
            var active_view = self.viewmanager.active_view;
            var view = self.viewmanager.views[active_view].controller;
            if(active_view === "list") {
                return view.reload_content();
            } else if (active_view === "form") {
                if (self.dataset.index === null && self.dataset.ids.length >= 1) {
                    self.dataset.index = 0;
                }
                var act = function() {
                    return view.do_show();
                };
                self.form_last_update = self.form_last_update.pipe(act, act);
                return self.form_last_update;
            } else if (view.do_search) {
                return view.do_search(self.build_domain(), self.dataset.get_context(), []);
            }
        }, undefined);
    },
    set_value: function(value_) {
        value_ = value_ || [];
        var self = this;
        this.dataset.reset_ids([]);
        if(value_.length >= 1 && value_[0] instanceof Array) {
            var ids = [];
            _.each(value_, function(command) {
                var obj = {values: command[2]};
                switch (command[0]) {
                    case commands.CREATE:
                        obj['id'] = _.uniqueId(self.dataset.virtual_id_prefix);
                        obj.defaults = {};
                        self.dataset.to_create.push(obj);
                        self.dataset.cache.push(_.extend(_.clone(obj), {values: _.clone(command[2])}));
                        ids.push(obj.id);
                        return;
                    case commands.UPDATE:
                        obj['id'] = command[1];
                        self.dataset.to_write.push(obj);
                        self.dataset.cache.push(_.extend(_.clone(obj), {values: _.clone(command[2])}));
                        ids.push(obj.id);
                        return;
                    case commands.DELETE:
                        self.dataset.to_delete.push({id: command[1]});
                        return;
                    case commands.LINK_TO:
                        ids.push(command[1]);
                        return;
                    case commands.DELETE_ALL:
                        self.dataset.delete_all = true;
                        return;
                }
            });
            this._super(ids);
            this.dataset.set_ids(ids);
        } else if (value_.length >= 1 && typeof(value_[0]) === "object") {
            var ids = [];
            this.dataset.delete_all = true;
            _.each(value_, function(command) {
                var obj = {values: command};
                obj['id'] = _.uniqueId(self.dataset.virtual_id_prefix);
                obj.defaults = {};
                self.dataset.to_create.push(obj);
                self.dataset.cache.push(_.clone(obj));
                ids.push(obj.id);
            });
            this._super(ids);
            this.dataset.set_ids(ids);
        } else {
            this._super(value_);
            this.dataset.reset_ids(value_);
        }
        if (this.dataset.index === null && this.dataset.ids.length > 0) {
            this.dataset.index = 0;
        }
        self.is_setted.resolve();
        return self.reload_current_view();
    },
    get_value: function() {
        var self = this;
        if (!this.dataset)
            return [];
        this.save_any_view();
        var val = this.dataset.delete_all ? [commands.delete_all()] : [];
        val = val.concat(_.map(this.dataset.ids, function(id) {
            var alter_order = _.detect(self.dataset.to_create, function(x) {return x.id === id;});
            if (alter_order) {
                return commands.create(alter_order.values);
            }
            alter_order = _.detect(self.dataset.to_write, function(x) {return x.id === id;});
            if (alter_order) {
                return commands.update(alter_order.id, alter_order.values);
            }
            return commands.link_to(id);
        }));
        return val.concat(_.map(
            this.dataset.to_delete, function(x) {
                return commands['delete'](x.id);}));
    },
    save_any_view: function() {
        if (this.doing_on_change)
            return false;
    	return this.session.synchronized_mode(_.bind(function() {
	        if (this.viewmanager && this.viewmanager.views && this.viewmanager.active_view &&
	            this.viewmanager.views[this.viewmanager.active_view] &&
	            this.viewmanager.views[this.viewmanager.active_view].controller) {
	            var view = this.viewmanager.views[this.viewmanager.active_view].controller;
	            if (this.viewmanager.active_view === "form") {
	                if (!view.is_initialized.isResolved()) {
	                    return false;
	                }
	                var res = $.when(view.do_save());
	                if (!res.isResolved() && !res.isRejected()) {
	                    console.warn("Asynchronous get_value() is not supported in form view.");
	                }
	                return res;
	            } else if (this.viewmanager.active_view === "list") {
	                var res = $.when(view.ensure_saved());
	                if (!res.isResolved() && !res.isRejected()) {
	                    console.warn("Asynchronous get_value() is not supported in list view.");
	                }
	                return res;
	            }
	        }
	        return false;
	    }, this));
    },
    is_syntax_valid: function() {
        if (!this.viewmanager.views[this.viewmanager.active_view])
            return true;
        var view = this.viewmanager.views[this.viewmanager.active_view].controller;
        if (this.viewmanager.active_view === "form") {
            for (var f in view.fields) {
                f = view.fields[f];
                if (!f.is_valid()) {
                    return false;
                }
            }
        }
        return true;
    },
});

instance.web.form.One2ManyViewManager = instance.web.ViewManager.extend({
    template: 'One2Many.viewmanager',
    init: function(parent, dataset, views, flags) {
        this._super(parent, dataset, views, _.extend({}, flags, {$sidebar: false}));
        this.registry = this.registry.extend({
            list: 'instance.web.form.One2ManyListView',
            form: 'instance.web.form.One2ManyFormView',
            kanban: 'instance.web.form.One2ManyKanbanView',
        });
    },
    switch_view: function(mode, unused) {
        if (mode !== 'form') {
            return this._super(mode, unused);
        }
        var self = this;
        var id = self.o2m.dataset.index !== null ? self.o2m.dataset.ids[self.o2m.dataset.index] : null;
        var pop = new instance.web.form.FormOpenPopup(self.o2m.view);
        pop.show_element(self.o2m.field.relation, id, self.o2m.build_context(), {
            title: _t("Open: ") + self.name,
            write_function: function(id, data, options) {
                return self.o2m.dataset.write(id, data, {}).then(function() {
                    self.o2m.reload_current_view();
                });
            },
            alternative_form_view: self.o2m.field.views ? self.o2m.field.views["form"] : undefined,
            parent_view: self.o2m.view,
            child_name: self.o2m.name,
            read_function: function() {
                return self.o2m.dataset.read_ids.apply(self.o2m.dataset, arguments);
            },
            form_view_options: {'not_interactible_on_create':true},
            readonly: self.o2m.get("effective_readonly")
        });
    },
});

instance.web.form.One2ManyDataSet = instance.web.BufferedDataSet.extend({
    get_context: function() {
        this.context = this.o2m.build_context([this.o2m.name]);
        return this.context;
    }
});

instance.web.form.One2ManyListView = instance.web.ListView.extend({
    _template: 'One2Many.listview',
    do_add_record: function () {
        if (this.options.editable) {
            this._super.apply(this, arguments);
        } else {
            var self = this;
            var pop = new instance.web.form.SelectCreatePopup(this);
            pop.select_element(
                self.o2m.field.relation,
                {
                    title: _t("Create: ") + self.name,
                    initial_view: "form",
                    alternative_form_view: self.o2m.field.views ? self.o2m.field.views["form"] : undefined,
                    create_function: function(data, callback, error_callback) {
                        return self.o2m.dataset.create(data).then(function(r) {
                            self.o2m.dataset.set_ids(self.o2m.dataset.ids.concat([r.result]));
                            self.o2m.dataset.on_change();
                        }).then(callback, error_callback);
                    },
                    read_function: function() {
                        return self.o2m.dataset.read_ids.apply(self.o2m.dataset, arguments);
                    },
                    parent_view: self.o2m.view,
                    child_name: self.o2m.name,
                    form_view_options: {'not_interactible_on_create':true}
                },
                self.o2m.build_domain(),
                self.o2m.build_context()
            );
            pop.on_select_elements.add_last(function() {
                self.o2m.reload_current_view();
            });
        }
    },
    do_activate_record: function(index, id) {
        var self = this;
        var pop = new instance.web.form.FormOpenPopup(self.o2m.view);
        pop.show_element(self.o2m.field.relation, id, self.o2m.build_context(), {
            title: _t("Open: ") + self.name,
            write_function: function(id, data) {
                return self.o2m.dataset.write(id, data, {}, function(r) {
                    self.o2m.reload_current_view();
                });
            },
            alternative_form_view: self.o2m.field.views ? self.o2m.field.views["form"] : undefined,
            parent_view: self.o2m.view,
            child_name: self.o2m.name,
            read_function: function() {
                return self.o2m.dataset.read_ids.apply(self.o2m.dataset, arguments);
            },
            form_view_options: {'not_interactible_on_create':true},
            readonly: self.o2m.get("effective_readonly")
        });
    },
    do_button_action: function (name, id, callback) {
        var self = this;
        var def = $.Deferred().then(callback).then(function() {self.o2m.view.reload();});
        return this._super(name, id, _.bind(def.resolve, def));
    }
});

instance.web.form.One2ManyFormView = instance.web.FormView.extend({
    form_template: 'One2Many.formview',
    on_loaded: function(data) {
        this._super(data);
        var self = this;
        this.$buttons.find('button.oe_form_button_create').click(function() {
            self.do_save().then(self.on_button_new);
        });
    },
    do_notify_change: function() {
        if (this.dataset.parent_view) {
            this.dataset.parent_view.do_notify_change();
        } else {
            this._super.apply(this, arguments);
        }
    }
});

var lazy_build_o2m_kanban_view = function() {
if (! instance.web_kanban || instance.web.form.One2ManyKanbanView)
    return;
instance.web.form.One2ManyKanbanView = instance.web_kanban.KanbanView.extend({
});
}

instance.web.form.FieldMany2ManyTags = instance.web.form.AbstractField.extend(_.extend({}, instance.web.form.CompletionFieldMixin,
                                                                                       instance.web.form.ReinitializeFieldMixin, {
    template: "FieldMany2ManyTags",
    init: function() {
        this._super.apply(this, arguments);
        instance.web.form.CompletionFieldMixin.init.call(this);
        this.set({"value": []});
        this._display_orderer = new instance.web.DropMisordered();
        this._drop_shown = false;
    },
    start: function() {
        this._super();
        instance.web.form.ReinitializeFieldMixin.start.call(this);
        this.on("change:value", this, this.render_value);
    },
    initialize_content: function() {
        if (this.get("effective_readonly"))
            return;
        var self = this;
        self. $text = $("textarea", this.$element);
        self.$text.textext({
            plugins : 'tags arrow autocomplete',
            autocomplete: {
                render: function(suggestion) {
                    return $('<span class="text-label"/>').
                             data('index', suggestion['index']).html(suggestion['label']);
                }
            },
            ext: {
                autocomplete: {
                    selectFromDropdown: function() {
                        $(this).trigger('hideDropdown');
                        var index = Number(this.selectedSuggestionElement().children().children().data('index'));
                        var data = self.search_result[index];
                        if (data.id) {
                            self.add_id(data.id);
                        } else {
                            data.action();
                        }
                    },
                },
                tags: {
                    isTagAllowed: function(tag) {
                        if (! tag.name)
                            return false;
                        return true;
                    },
                    removeTag: function(tag) {
                        var id = tag.data("id");
                        self.set({"value": _.without(self.get("value"), id)});
                    },
                    renderTag: function(stuff) {
                        return $.fn.textext.TextExtTags.prototype.renderTag.
                            call(this, stuff).data("id", stuff.id);
                    },
                },
                itemManager: {
                    itemToString: function(item) {
                        return item.name;
                    },
                },
            },
        }).bind('getSuggestions', function(e, data) {
            var _this = this;
            var str = !!data ? data.query || '' : '';
            self.get_search_result(str).then(function(result) {
                self.search_result = result;
                $(_this).trigger('setSuggestions', {result : _.map(result, function(el, i) {
                    return _.extend(el, {index:i});
                })});
            });
        }).bind('tagClick', function(e, tag, value, callback) {
            var pop = new instance.web.form.FormOpenPopup(self.view);
            pop.show_element(
                self.field.relation,
                value.id,
                self.build_context(),
                {
                    title: _t("Open: ") + (self.string || self.name)
                }
            );
            pop.on_write_completed.add_last(function() {
                self.render_value();
            });
        }).bind('hideDropdown', function() {
            self._drop_shown = false;
        }).bind('hideDropdown', function() {
            self._drop_shown = true;
        });
        self.tags = self.$text.textext()[0].tags();
        $("textarea", this.$element).focusout(function() {
            $("textarea", this.$element).val("");
        }).keydown(function(e) {
            if (event.keyCode === 9 && self._drop_shown) {
                self.$text.textext()[0].autocomplete().selectFromDropdown();
            }
        });
    },
    set_value: function(value_) {
        value_ = value_ || [];
        if (value_.length >= 1 && value_[0] instanceof Array) {
            value_ = value_[0][2];
        }
        this._super(value_);
    },
    get_value: function() {
        var tmp = [commands.replace_with(this.get("value"))];
        return tmp;
    },
    render_value: function() {
        var self = this;
        var dataset = new instance.web.DataSetStatic(this, this.field.relation, self.view.dataset.get_context());
        var handle_names = function(data) {
            var indexed = {};
            _.each(data, function(el) {
                indexed[el[0]] = el;
            });
            data = _.map(self.get("value"), function(el) { return indexed[el]; });
            if (! self.get("effective_readonly")) {
                self.tags.containerElement().children().remove();
                $("textarea", self.$element).css("padding-left", "3px");
                self.tags.addTags(_.map(data, function(el) {return {name: el[1], id:el[0]};}));
            } else {
                self.$element.html(QWeb.render("FieldMany2ManyTags.box", {elements: data}));
                $(".oe_form_field_many2manytags_box", self.$element).click(function() {
                    var index = Number($(this).data("index"));
                    self.do_action({
                        type: 'ir.actions.act_window',
                        res_model: self.field.relation,
                        res_id: self.get("value")[index],
                        context: self.build_context(),
                        views: [[false, 'form']],
                        target: 'current'
                    });
                });
            }
        };
        if (! self.get('values') || self.get('values').length > 0) {
            this._display_orderer.add(dataset.name_get(self.get("value"))).then(handle_names);
        } else {
            handle_names([]);
        }
    },
    add_id: function(id) {
        this.set({'value': _.uniq(this.get('value').concat([id]))});
    },
}));

/*
 * TODO niv: clean those deferred stuff, it could be better
 */
instance.web.form.FieldMany2Many = instance.web.form.AbstractField.extend({
    template: "FieldMany2Many.render",
    multi_selection: false,
    disable_utility_classes: true,
    init: function(field_manager, node) {
        this._super(field_manager, node);
        this.is_loaded = $.Deferred();
        this.initial_is_loaded = this.is_loaded;
        this.is_setted = $.Deferred();
    },
    start: function() {
        this._super.apply(this, arguments);

        var self = this;

        this.dataset = new instance.web.form.Many2ManyDataSet(this, this.field.relation);
        this.dataset.m2m = this;
        this.dataset.on_unlink.add_last(function(ids) {
            self.dataset_changed();
        });
        
        this.is_setted.then(function() {
            self.load_view();
        });
        this.is_loaded.then(function() {
            self.on("change:effective_readonly", self, function() {
                self.is_loaded = self.is_loaded.pipe(function() {
                    self.list_view.destroy();
                    return $.when(self.load_view()).then(function() {
                        self.reload_content();
                    });
                });
            });
        })
    },
    set_value: function(value_) {
        value_ = value_ || [];
        if (value_.length >= 1 && value_[0] instanceof Array) {
            value_ = value_[0][2];
        }
        this._super(value_);
        this.dataset.set_ids(value_);
        var self = this;
        self.reload_content();
        this.is_setted.resolve();
    },
    load_view: function() {
        var self = this;
        this.list_view = new instance.web.form.Many2ManyListView(this, this.dataset, false, {
                    'addable': self.get("effective_readonly") ? null : _t("Add"),
                    'deletable': self.get("effective_readonly") ? false : true,
                    'selectable': self.multi_selection,
                    '$buttons': $(".oe_form_view_m2m_buttons", self.$element),
            });
        var embedded = (this.field.views || {}).tree;
        if (embedded) {
            this.list_view.set_embedded_view(embedded);
        }
        this.list_view.m2m_field = this;
        var loaded = $.Deferred();
        this.list_view.on_loaded.add_last(function() {
            self.initial_is_loaded.resolve();
            loaded.resolve();
        });
        $.async_when().then(function () {
            self.list_view.appendTo($(".oe_form_view_m2m_view", self.$element));
        });
        return loaded;
    },
    reload_content: function() {
        var self = this;
        this.is_loaded = this.is_loaded.pipe(function() {
            return self.list_view.reload_content();
        });
    },
    dataset_changed: function() {
        this.set({'value': [commands.replace_with(this.dataset.ids)]});
    },
});

instance.web.form.Many2ManyDataSet = instance.web.DataSetStatic.extend({
    get_context: function() {
        this.context = this.m2m.build_context();
        return this.context;
    }
});

/**
 * @class
 * @extends instance.web.ListView
 */
instance.web.form.Many2ManyListView = instance.web.ListView.extend(/** @lends instance.web.form.Many2ManyListView# */{
    do_add_record: function () {
        var pop = new instance.web.form.SelectCreatePopup(this);
        pop.select_element(
            this.model,
            {
                title: _t("Add: ") + this.name
            },
            new instance.web.CompoundDomain(this.m2m_field.build_domain(), ["!", ["id", "in", this.m2m_field.dataset.ids]]),
            this.m2m_field.build_context()
        );
        var self = this;
        pop.on_select_elements.add(function(element_ids) {
            _.each(element_ids, function(one_id) {
                if(! _.detect(self.dataset.ids, function(x) {return x == one_id;})) {
                    self.dataset.set_ids([].concat(self.dataset.ids, [one_id]));
                    self.m2m_field.dataset_changed();
                    self.reload_content();
                }
            });
        });
    },
    do_activate_record: function(index, id) {
        var self = this;
        var pop = new instance.web.form.FormOpenPopup(this);
        pop.show_element(this.dataset.model, id, this.m2m_field.build_context(), {
            title: _t("Open: ") + this.name,
            readonly: this.getParent().get("effective_readonly")
        });
        pop.on_write_completed.add_last(function() {
            self.reload_content();
        });
    }
});

instance.web.form.AbstractFormPopup = instance.web.OldWidget.extend({
    template: "AbstractFormPopup.render",
    /**
     *  options:
     *  -readonly: only applicable when not in creation mode, default to false
     */
    init_popup: function(model, row_id, domain, context, options) {
        this.row_id = row_id;
        this.model = model;
        this.domain = domain || [];
        this.context = context || {};
        this.options = options;
        _.defaults(this.options, {
        });
    },
    init_dataset: function() {
        var self = this;
        this.dataset = new instance.web.ProxyDataSet(this, this.model, this.context);
        this.dataset.read_function = this.options.read_function;
        this.dataset.create_function = function(data, sup) {
            var fct = self.options.create_function || sup;
            return fct.call(this, data).then(function(r) {
                self.created_elements.push(r.result);
            });
        };
        this.dataset.write_function = function(id, data, options, sup) {
            var fct = self.options.write_function || sup;
            return fct.call(this, id, data, options).then(self.on_write_completed);
        };
        this.dataset.parent_view = this.options.parent_view;
        this.dataset.child_name = this.options.child_name;
    },
    display_popup: function() {
        this.renderElement();
        instance.web.form.dialog(this.$element, {
            close: function() {
                self.check_exit();
            },
            title: this.options.title || ""
        });
        this.start();
    },
    on_write_completed: function() {},
    setup_form_view: function() {
        var self = this;
        var options = _.clone(self.options.form_view_options) || {};
        if (this.row_id !== null) {
            options.initial_mode = this.options.readonly ? "view" : "edit";
        }
        this.view_form = new instance.web.FormView(this, this.dataset, false, options);
        if (this.options.alternative_form_view) {
            this.view_form.set_embedded_view(this.options.alternative_form_view);
        }
        this.view_form.appendTo(this.$element.find(".oe-form-view-popup-form-placeholder"));
        this.view_form.on_loaded.add_last(function() {
            var $buttons = self.view_form.$element.find(".oe_form_buttons");
            var multi_select = self.row_id === null && ! self.options.disable_multiple_selection;
            $buttons.html(QWeb.render("AbstractFormPopup.buttons", {multi_select: multi_select}));
            var $snbutton = $buttons.find(".oe_abstractformpopup-form-save-new");
            $snbutton.click(function() {
                $.when(self.view_form.do_save()).then(function() {
                    self.view_form.reload_mutex.exec(function() {
                        self.view_form.on_button_new();
                    });
                });
            });
            var $sbutton = $buttons.find(".oe_abstractformpopup-form-save");
            $sbutton.click(function() {
                $.when(self.view_form.do_save()).then(function() {
                    self.view_form.reload_mutex.exec(function() {
                        self.check_exit();
                    });
                });
            });
            var $cbutton = $buttons.find(".oe_abstractformpopup-form-close");
            $cbutton.click(function() {
                self.check_exit();
            });
            if (self.row_id !== null && self.options.readonly) {
                $snbutton.hide();
                $sbutton.hide();
                $cbutton.text(_t("Close"));
            }
            self.view_form.do_show();
        });
    },
    check_exit: function() {
        this.destroy();
    },
});

/**
 * @class
 * @extends instance.web.OldWidget
 */
instance.web.form.SelectCreatePopup = instance.web.form.AbstractFormPopup.extend(/** @lends instance.web.form.SelectCreatePopup# */{
    /**
     * options:
     * - initial_ids
     * - initial_view: form or search (default search)
     * - disable_multiple_selection
     * - alternative_form_view
     * - create_function (defaults to a naive saving behavior)
     * - parent_view
     * - child_name
     * - form_view_options
     * - list_view_options
     * - read_function
     */
    select_element: function(model, options, domain, context) {
        this.init_popup(model, null, domain, context, options);
        var self = this;
        _.defaults(this.options, {
            initial_view: "search",
            create_function: function() {
                return self.create_row.apply(self, arguments);
            },
            read_function: null,
        });
        this.initial_ids = this.options.initial_ids;
        this.created_elements = [];
        this.display_popup();
    },
    start: function() {
        var self = this;
        this.init_dataset();
        if (this.options.initial_view == "search") {
            self.rpc('/web/session/eval_domain_and_context', {
                domains: [],
                contexts: [this.context]
            }, function (results) {
                var search_defaults = {};
                _.each(results.context, function (value_, key) {
                    var match = /^search_default_(.*)$/.exec(key);
                    if (match) {
                        search_defaults[match[1]] = value_;
                    }
                });
                self.setup_search_view(search_defaults);
            });
        } else { // "form"
            this.new_object();
        }
    },
    stop: function () {
        this.$element.dialog('close');
        this._super();
    },
    setup_search_view: function(search_defaults) {
        var self = this;
        if (this.searchview) {
            this.searchview.destroy();
        }
        this.searchview = new instance.web.SearchView(this,
                this.dataset, false,  search_defaults);
        this.searchview.on_search.add(function(domains, contexts, groupbys) {
            if (self.initial_ids) {
                self.do_search(domains.concat([[["id", "in", self.initial_ids]], self.domain]),
                    contexts, groupbys);
                self.initial_ids = undefined;
            } else {
                self.do_search(domains.concat([self.domain]), contexts.concat(self.context), groupbys);
            }
        });
        this.searchview.on_loaded.add_last(function () {
            self.view_list = new instance.web.form.SelectCreateListView(self,
                    self.dataset, false,
                    _.extend({'deletable': false,
                        'selectable': !self.options.disable_multiple_selection
                    }, self.options.list_view_options || {}));
            self.view_list.popup = self;
            self.view_list.appendTo($(".oe-select-create-popup-view-list", self.$element)).pipe(function() {
                self.view_list.do_show();
            }).pipe(function() {
                self.searchview.do_search();
            });
            self.view_list.on_loaded.add_last(function() {
                var $buttons = self.view_list.$element.find(".oe-actions");
                $buttons.prepend(QWeb.render("SelectCreatePopup.search.buttons"));
                var $cbutton = $buttons.find(".oe_selectcreatepopup-search-close");
                $cbutton.click(function() {
                    self.destroy();
                });
                var $sbutton = $buttons.find(".oe_selectcreatepopup-search-select");
                if(self.options.disable_multiple_selection) {
                    $sbutton.hide();
                }
                $sbutton.click(function() {
                    self.on_select_elements(self.selected_ids);
                    self.destroy();
                });
            });
        });
        this.searchview.appendTo($(".oe-select-create-popup-view-list", self.$element));
    },
    do_search: function(domains, contexts, groupbys) {
        var self = this;
        this.rpc('/web/session/eval_domain_and_context', {
            domains: domains || [],
            contexts: contexts || [],
            group_by_seq: groupbys || []
        }, function (results) {
            self.view_list.do_search(results.domain, results.context, results.group_by);
        });
    },
    create_row: function() {
        var self = this;
        var wdataset = new instance.web.DataSetSearch(this, this.model, this.context, this.domain);
        wdataset.parent_view = this.options.parent_view;
        wdataset.child_name = this.options.child_name;
        return wdataset.create.apply(wdataset, arguments);
    },
    on_select_elements: function(element_ids) {
    },
    on_click_element: function(ids) {
        this.selected_ids = ids || [];
        if(this.selected_ids.length > 0) {
            this.$element.find(".oe_selectcreatepopup-search-select").removeAttr('disabled');
        } else {
            this.$element.find(".oe_selectcreatepopup-search-select").attr('disabled', "disabled");
        }
    },
    new_object: function() {
        if (this.searchview) {
            this.searchview.hide();
        }
        if (this.view_list) {
            this.view_list.$element.hide();
        }
        this.dataset.index = null;
        this.setup_form_view();
    },
    check_exit: function() {
        if (this.created_elements.length > 0) {
            this.on_select_elements(this.created_elements);
        }
        this._super();
    },
});

instance.web.form.SelectCreateListView = instance.web.ListView.extend({
    do_add_record: function () {
        this.popup.new_object();
    },
    select_record: function(index) {
        this.popup.on_select_elements([this.dataset.ids[index]]);
        this.popup.destroy();
    },
    do_select: function(ids, records) {
        this._super(ids, records);
        this.popup.on_click_element(ids);
    }
});

/**
 * @class
 * @extends instance.web.OldWidget
 */
instance.web.form.FormOpenPopup = instance.web.form.AbstractFormPopup.extend(/** @lends instance.web.form.FormOpenPopup# */{
    /**
     * options:
     * - alternative_form_view
     * - write_function
     * - read_function
     * - parent_view
     * - child_name
     * - form_view_options
     */
    show_element: function(model, row_id, context, options) {
        this.init_popup(model, row_id, [], context,  options);
        _.defaults(this.options, {
            auto_write: true,
        });
        this.display_popup();
    },
    start: function() {
        this._super();
        this.init_dataset();
        this.dataset.ids = [this.row_id];
        this.dataset.index = 0;
        this.setup_form_view();
    },
});

instance.web.form.FieldReference = instance.web.form.AbstractField.extend(_.extend({}, instance.web.form.ReinitializeFieldMixin, {
    template: 'FieldReference',
    init: function(field_manager, node) {
        this._super(field_manager, node);
        this.reference_ready = true;
    },
    on_nop: function() {
    },
    on_selection_changed: function() {
        if (this.reference_ready) {
            var sel = this.selection.get_value();
            this.m2o.field.relation = sel;
            this.m2o.set_value(false);
            this.m2o.$element.toggle(sel !== false);
        }
    },
    destroy_content: function() {
        if (this.selection) {
            this.selection.destroy();
            this.selection = undefined;
        }
        if (this.m2o) {
            this.m2o.destroy();
            this.m2o = undefined;
        }
    },
    initialize_content: function() {
        this.selection = new instance.web.form.FieldSelection(this, { attrs: {
            name: 'selection'
        }});
        this.selection.view = this.view;
        this.selection.set({force_readonly: this.get('effective_readonly')});
        this.selection.on("change:value", this, this.on_selection_changed);
        this.selection.$element = $(".oe_form_view_reference_selection", this.$element);
        this.selection.renderElement();
        this.selection.start();

        this.m2o = new instance.web.form.FieldMany2One(this, { attrs: {
            name: 'm2o'
        }});
        this.m2o.view = this.view;
        this.m2o.set({force_readonly: this.get("effective_readonly")});
        this.m2o.on("change:value", this, this.data_changed);
        this.m2o.$element = $(".oe_form_view_reference_m2o", this.$element);
        this.m2o.renderElement();
        this.m2o.start();
    },
    is_false: function() {
        return typeof(this.get_value()) !== 'string';
    },
    set_value: function(value_) {
        this._super(value_);
        this.render_value();
    },
    render_value: function() {
        this.reference_ready = false;
        var vals = [], sel_val, m2o_val;
        if (typeof(this.get('value')) === 'string') {
            vals = this.get('value').split(',');
        }
        sel_val = vals[0] || false;
        m2o_val = vals[1] ? parseInt(vals[1], 10) : vals[1];
        if (!this.get("effective_readonly")) {
            this.selection.set_value(sel_val);
        }
        this.m2o.field.relation = sel_val;
        this.m2o.set_value(m2o_val);
        this.reference_ready = true;
    },
    data_changed: function() {
        var model = this.selection.get_value(),
            id = this.m2o.get_value();
        if (typeof(model) === 'string' && typeof(id) === 'number') {
            this.set({'value': model + ',' + id});
        } else {
            this.set({'value': false});
        }
    },
    get_field: function(name) {
        if (name === "selection") {
            return {
                selection: this.view.fields_view.fields[this.name].selection,
                type: "selection",
            };
        } else if (name === "m2o") {
            return {
                relation: null,
                type: "many2one",
            };
        }
        throw Exception("Should not happen");
    },
}));

instance.web.form.FieldBinary = instance.web.form.AbstractField.extend(_.extend({}, instance.web.form.ReinitializeFieldMixin, {
    init: function(field_manager, node) {
        this._super(field_manager, node);
        this.iframe = this.element_id + '_iframe';
        this.binary_value = false;
    },
    initialize_content: function() {
        this.$element.find('input.oe-binary-file').change(this.on_file_change);
        this.$element.find('button.oe-binary-file-save').click(this.on_save_as);
        this.$element.find('.oe-binary-file-clear').click(this.on_clear);
    },
    human_filesize : function(size) {
        var units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
        var i = 0;
        while (size >= 1024) {
            size /= 1024;
            ++i;
        }
        return size.toFixed(2) + ' ' + units[i];
    },
    on_file_change: function(e) {
        // TODO: on modern browsers, we could directly read the file locally on client ready to be used on image cropper
        // http://www.html5rocks.com/tutorials/file/dndfiles/
        // http://deepliquid.com/projects/Jcrop/demos.php?demo=handler
        window[this.iframe] = this.on_file_uploaded;
        if ($(e.target).val() != '') {
            this.$element.find('form.oe-binary-form input[name=session_id]').val(this.session.session_id);
            this.$element.find('form.oe-binary-form').submit();
            this.$element.find('.oe-binary-progress').show();
            this.$element.find('.oe-binary').hide();
        }
    },
    on_file_uploaded: function(size, name, content_type, file_base64) {
        delete(window[this.iframe]);
        if (size === false) {
            this.do_warn("File Upload", "There was a problem while uploading your file");
            // TODO: use openerp web crashmanager
            console.warn("Error while uploading file : ", name);
        } else {
            this.on_file_uploaded_and_valid.apply(this, arguments);
        }
        this.$element.find('.oe-binary-progress').hide();
        this.$element.find('.oe-binary').show();
    },
    on_file_uploaded_and_valid: function(size, name, content_type, file_base64) {
    },
    on_save_as: function() {
        $.blockUI();
        this.session.get_file({
            url: '/web/binary/saveas_ajax',
            data: {data: JSON.stringify({
                model: this.view.dataset.model,
                id: (this.view.datarecord.id || ''),
                field: this.name,
                filename_field: (this.node.attrs.filename || ''),
                context: this.view.dataset.get_context()
            })},
            complete: $.unblockUI,
            error: instance.webclient.crashmanager.on_rpc_error
        });
    },
    on_clear: function() {
        if (this.get('value') !== false) {
            this.binary_value = false;
            this.set({'value': false});
        }
        return false;
    }
}));

instance.web.form.FieldBinaryFile = instance.web.form.FieldBinary.extend({
    template: 'FieldBinaryFile',
    initialize_content: function() {
        this._super();
        if (this.get("effective_readonly")) {
            var self = this;
            this.$element.find('a').click(function() {
                if (self.get('value')) {
                    self.on_save_as();
                }
                return false;
            });
        }
    },
    set_value: function(value_) {
        this._super.apply(this, arguments);
        this.render_value();
    },
    render_value: function() {
        if (!this.get("effective_readonly")) {
            var show_value;
            if (this.node.attrs.filename) {
                show_value = this.view.datarecord[this.node.attrs.filename] || '';
            } else {
                show_value = (this.get('value') != null && this.get('value') !== false) ? this.get('value') : '';
            }
            this.$element.find('input').eq(0).val(show_value);
        } else {
            this.$element.find('a').show(!!this.get('value'));
            if (this.get('value')) {
                var show_value = _t("Download") + " " + (this.view.datarecord[this.node.attrs.filename] || '');
                this.$element.find('a').text(show_value);
            }
        }
    },
    on_file_uploaded_and_valid: function(size, name, content_type, file_base64) {
        this.binary_value = true;
        this.set({'value': file_base64});
        var show_value = name + " (" + this.human_filesize(size) + ")";
        this.$element.find('input').eq(0).val(show_value);
        this.set_filename(name);
    },
    set_filename: function(value_) {
        var filename = this.node.attrs.filename;
        if (this.view.fields[filename]) {
            this.view.fields[filename].set({value: value_});
        }
    },
    on_clear: function() {
        this._super.apply(this, arguments);
        this.$element.find('input').eq(0).val('');
        this.set_filename('');
    }
});

instance.web.form.FieldBinaryImage = instance.web.form.FieldBinary.extend({
    template: 'FieldBinaryImage',
    initialize_content: function() {
        this._super();
        this.$placeholder = $(".oe_form_field-binary-image-placeholder", this.$element);
        if (!this.get("effective_readonly"))
            this.$element.find('.oe-binary').show();
        else
            this.$element.find('.oe-binary').hide();
    },
    set_value: function(value_) {
        this._super.apply(this, arguments);
        this.render_value();
    },
    render_value: function() {
        var url;
        if (this.get('value') && this.get('value').substr(0, 10).indexOf(' ') == -1) {
            url = 'data:image/png;base64,' + this.get('value');
        } else if (this.get('value')) {
            url = '/web/binary/image?session_id=' + this.session.session_id + '&model=' +
                this.view.dataset.model +'&id=' + (this.view.datarecord.id || '') + '&field=' + this.name + '&t=' + (new Date().getTime());
        } else {
            url = "/web/static/src/img/placeholder.png";
        }
        var rendered = QWeb.render("FieldBinaryImage-img", {widget: this, url: url});;
        this.$placeholder.html(rendered);
    },
    on_file_change: function() {
        this.render_value();
        this._super.apply(this, arguments);
    },
    on_file_uploaded_and_valid: function(size, name, content_type, file_base64) {
        this.set({'value': file_base64});
        this.binary_value = true;
        this.render_value();
    },
    on_clear: function() {
        this._super.apply(this, arguments);
        this.render_value();
    }
});

instance.web.form.FieldStatus = instance.web.form.AbstractField.extend({
    template: "EmptyComponent",
    start: function() {
        this._super();
        this.selected_value = null;

        this.render_list();
    },
    set_value: function(value_) {
        this._super(value_);
        this.selected_value = value_;

        this.render_list();
    },
    render_list: function() {
        var self = this;
        var shown = _.map(((this.node.attrs || {}).statusbar_visible || "").split(","),
            function(x) { return _.str.trim(x); });
        shown = _.select(shown, function(x) { return x.length > 0; });

        if (shown.length == 0) {
            this.to_show = this.field.selection;
        } else {
            this.to_show = _.select(this.field.selection, function(x) {
                return _.indexOf(shown, x[0]) !== -1 || x[0] === self.selected_value;
            });
        }

        var content = instance.web.qweb.render("FieldStatus.content", {widget: this, _:_});
        this.$element.html(content);

        var colors = JSON.parse((this.node.attrs || {}).statusbar_colors || "{}");
        var color = colors[this.selected_value];
        if (color) {
            var elem = this.$element.find("li.oe-arrow-list-selected span");
            elem.css("border-color", color);
            if (this.check_white(color))
                elem.css("color", "white");
            elem = this.$element.find("li.oe-arrow-list-selected .oe-arrow-list-before");
            elem.css("border-left-color", "rgba(0,0,0,0)");
            elem = this.$element.find("li.oe-arrow-list-selected .oe-arrow-list-after");
            elem.css("border-color", "rgba(0,0,0,0)");
            elem.css("border-left-color", color);
        }
    },
    check_white: function(color) {
        var div = $("<div></div>");
        div.css("display", "none");
        div.css("color", color);
        div.appendTo($("body"));
        var ncolor = div.css("color");
        div.remove();
        var res = /^\s*rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*$/.exec(ncolor);
        if (!res) {
            return false;
        }
        var comps = [parseInt(res[1]), parseInt(res[2]), parseInt(res[3])];
        var lum = comps[0] * 0.3 + comps[1] * 0.59 + comps[1] * 0.11;
        if (lum < 128) {
            return true;
        }
        return false;
    }
});

/**
 * Registry of form fields, called by :js:`instance.web.FormView`.
 *
 * All referenced classes must implement FieldMixin. Those represent the classes whose instances
 * will substitute to the <field> tags as defined in OpenERP's views.
 */
instance.web.form.widgets = new instance.web.Registry({
    'char' : 'instance.web.form.FieldChar',
    'id' : 'instance.web.form.FieldID',
    'email' : 'instance.web.form.FieldEmail',
    'url' : 'instance.web.form.FieldUrl',
    'text' : 'instance.web.form.FieldText',
    'date' : 'instance.web.form.FieldDate',
    'datetime' : 'instance.web.form.FieldDatetime',
    'selection' : 'instance.web.form.FieldSelection',
    'many2one' : 'instance.web.form.FieldMany2One',
    'many2many' : 'instance.web.form.FieldMany2Many',
    'many2manytags' : 'instance.web.form.FieldMany2ManyTags',
    'one2many' : 'instance.web.form.FieldOne2Many',
    'one2many_list' : 'instance.web.form.FieldOne2Many',
    'reference' : 'instance.web.form.FieldReference',
    'boolean' : 'instance.web.form.FieldBoolean',
    'float' : 'instance.web.form.FieldFloat',
    'integer': 'instance.web.form.FieldFloat',
    'float_time': 'instance.web.form.FieldFloat',
    'progressbar': 'instance.web.form.FieldProgressBar',
    'image': 'instance.web.form.FieldBinaryImage',
    'binary': 'instance.web.form.FieldBinaryFile',
    'statusbar': 'instance.web.form.FieldStatus'
});

/**
 * Registry of widgets usable in the form view that can substitute to any possible
 * tags defined in OpenERP's form views.
 *
 * Every referenced class should extend FormWidget.
 */
instance.web.form.tags = new instance.web.Registry({
    'button' : 'instance.web.form.WidgetButton',
});

};

// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax:
