/**
 * handles editability case for lists, because it depends on form and forms already depends on lists it had to be split out
 * @namespace
 */
openerp.web.list_editable = function (instance) {
    var KEY_RETURN = 13,
        KEY_ESCAPE = 27;
    var QWeb = instance.web.qweb;

    // editability status of list rows
    instance.web.ListView.prototype.defaults.editable = null;

    // TODO: not sure second @lends on existing item is correct, to check
    instance.web.ListView.include(/** @lends instance.web.ListView# */{
        init: function () {
            var self = this;
            this._super.apply(this, arguments);
            $(this.groups).bind({
                'edit': function (e, id, dataset) {
                    self.do_edit(dataset.index, id, dataset);
                },
                'saved': function () {
                    if (self.groups.get_selection().length) {
                        return;
                    }
                    self.configure_pager(self.dataset);
                    self.compute_aggregates();
                }
            })
        },
        /**
         * Handles the activation of a record in editable mode (making a record
         * editable), called *after* the record has become editable.
         *
         * The default behavior is to setup the listview's dataset to match
         * whatever dataset was provided by the editing List
         *
         * @param {Number} index index of the record in the dataset
         * @param {Object} id identifier of the record being edited
         * @param {instance.web.DataSet} dataset dataset in which the record is available
         */
        do_edit: function (index, id, dataset) {
            _.extend(this.dataset, dataset);
        },
        /**
         * Sets editability status for the list, based on defaults, view
         * architecture and the provided flag, if any.
         *
         * @param {Boolean} [force] forces the list to editability. Sets new row edition status to "bottom".
         */
        set_editable: function (force) {
            // If ``force``, set editability to bottom
            // otherwise rely on view default
            // view' @editable is handled separately as we have not yet
            // fetched and processed the view at this point.
            this.options.editable = true || (
                    ! this.options.read_only && ((force && "bottom") || this.defaults.editable));
        },
        /**
         * Replace do_search to handle editability process
         */
        do_search: function(domain, context, group_by) {
            this.set_editable(context['set_editable']);
            this._super.apply(this, arguments);
        },
        /**
         * Replace do_add_record to handle editability (and adding new record
         * as an editable row at the top or bottom of the list)
         */
        do_add_record: function () {
            if (this.options.editable) {
                this.$element.find('table:first').show();
                this.$element.find('.oe_view_nocontent').remove();
                this.groups.new_record();
            } else {
                this._super();
            }
        },
        on_loaded: function (data, grouped) {
            var self = this, form_ready = $.when();
            // tree/@editable takes priority on everything else if present.
            this.options.editable = ! this.options.read_only && (data.arch.attrs.editable || this.options.editable);
            var result = this._super(data, grouped);
            if (this.options.editable || true) {
                // TODO: [Return], [Esc] events
                this.form = new instance.web.FormView(this, this.dataset, false, {
                    initial_mode: 'edit',
                    $buttons: $(),
                    $pager: $()
                });
                this.form.embedded_view = this.view_to_form_view();
                form_ready = this.form.prependTo(this.$element).then(function () {
                    self.form.do_hide();
                });
            }

            return $.when(result, form_ready);
        },
        /**
         * Ensures the editable list is saved (saves any pending edition if
         * needed, or tries to)
         *
         * Returns a deferred to the end of the saving.
         *
         * @returns {$.Deferred}
         */
        ensure_saved: function () {
            return this.groups.ensure_saved();
        },
        view_to_form_view: function () {
            var view = $.extend(true, {}, this.fields_view);
            view.arch.tag = 'form';
            _.extend(view.arch.attrs, {
                'class': 'oe_form_container',
                version: '7.0'
            });
            _(view.arch.children).each(function (widget) {
                var modifiers = JSON.parse(widget.attrs.modifiers || '{}');
                widget.attrs.nolabel = true;
                if (modifiers['tree_invisible'] || widget.tag === 'button') {
                    modifiers.invisible = true;
                }
                widget.attrs.modifiers = JSON.stringify(modifiers);
            });
            return view;
        },
        /**
         * Set up the edition of a record of the list view "inline"
         *
         * @param {Number} id id of the record to edit, null for new record
         * @param {Number} index index of the record to edit in the dataset, null for new record
         * @param {Object} cells map of field names to the DOM elements used to display these fields for the record being edited
         */
        edit_record: function (id, index, cells) {
            // TODO: save previous edition if any
            var self = this;
            var record = this.records.get(id);
            var e = {
                id: id,
                record: record,
                cancel: false
            };
            this.trigger('edit:before', e);
            if (e.cancel) {
                return;
            }
            return this.form.on_record_loaded(record.attributes).pipe(function () {
                return self.form.do_show({reload: false});
            }).then(function () {
                // TODO: automatic focus of ?first field
                // TODO: [Save] button
                // TODO: save on action button?
                _(cells).each(function (cell, field_name) {
                    var $cell = $(cell);
                    var position = $cell.position();
                    var field = self.form.fields[field_name];

                    // FIXME: this is shit. Is it possible to prefilter?
                    if (field.get('effective_readonly')) {
                        // Readonly fields can just remain the list's, form's
                        // usually don't have backgrounds &al
                        field.$element.hide();
                        return;
                    }
                    field.$element.show().css({
                        top: position.top,
                        left: position.left,
                        width: $cell.outerWidth(),
                        minHeight: $cell.outerHeight()
                    });
                });
                self.trigger('edit:after', record, self.form)
            });

        }
    });

    instance.web.ListView.Groups.include(/** @lends instance.web.ListView.Groups# */{
        passtrough_events: instance.web.ListView.Groups.prototype.passtrough_events + " edit saved",
        new_record: function () {
            // TODO: handle multiple children
            this.children[null].new_record();
        },
        /**
         * Ensures descendant editable List instances are all saved if they have
         * pending editions.
         *
         * @returns {$.Deferred}
         */
        ensure_saved: function () {
            return $.when.apply(null,
                _.invoke(
                    _.values(this.children),
                    'ensure_saved'));
        }
    });

    instance.web.ListView.List.include(/** @lends instance.web.ListView.List# */{
        row_clicked: function (event) {
            if (!this.options.editable) {
                return this._super.apply(this, arguments);
            }
            this.edit_record($(event.currentTarget).data('id'));
        },
        /**
         * Checks if a record is being edited, and if so cancels it
         */
        cancel_pending_edition: function () {
            var self = this, cancelled;
            if (!this.edition) {
                return $.when();
            }

            if (this.edition_id) {
                cancelled = this.reload_record(this.records.get(this.edition_id));
            } else {
                cancelled = $.when();
            }
            cancelled.then(function () {
                self.view.unpad_columns();
                self.edition_form.destroy();
                self.edition_form.$element.remove();
                delete self.edition_form;
                self.dataset.index = null;
                delete self.edition_id;
                delete self.edition;
            });
            this.pad_table_to(5);
            return cancelled;
        },
        on_row_keyup: function (e) {
            var self = this;
            switch (e.which) {
            case KEY_RETURN:
                $(e.target).blur();
                e.preventDefault();
                //e.stopImmediatePropagation();
                setTimeout(function () {
                    self.save_row().then(function (result) {
                        if (result.created) {
                            self.new_record();
                            return;
                        }

                        var next_record_id,
                            next_record = self.records.at(
                                    self.records.indexOf(result.edited_record) + 1);
                        if (next_record) {
                            next_record_id = next_record.get('id');
                            self.dataset.index = _(self.dataset.ids)
                                    .indexOf(next_record_id);
                        } else {
                            self.dataset.index = 0;
                            next_record_id = self.records.at(0).get('id');
                        }
                        self.edit_record(next_record_id);
                    }, 0);
                });
                break;
            case KEY_ESCAPE:
                this.cancel_edition();
                break;
            }
        },
        render_row_as_form: function (row) {
            var record_id = $(row).data('id');
            var index = _(this.dataset.ids).indexOf(record_id);

            var cells = {};
            row.children('td').each(function (index, el) {
                cells[el.getAttribute('data-field')] = el
            });

            // TODO: creation (record_id === null?)
            return this.view.edit_record(
                record_id,
                index !== -1 ? index : null,
                cells);
        },
        handle_onwrite: function (source_record_id) {
            var self = this;
            var on_write_callback = self.view.fields_view.arch.attrs.on_write;
            if (!on_write_callback) { return; }
            this.dataset.call(on_write_callback, [source_record_id], function (ids) {
                _(ids).each(function (id) {
                    var record = self.records.get(id);
                    if (!record) {
                        // insert after the source record
                        var index = self.records.indexOf(
                            self.records.get(source_record_id)) + 1;
                        record = new instance.web.list.Record({id: id});
                        self.records.add(record, {at: index});
                        self.dataset.ids.splice(index, 0, id);
                    }
                    self.reload_record(record);
                });
            });
        },
        /**
         * Saves the current row, and returns a Deferred resolving to an object
         * with the following properties:
         *
         * ``created``
         *   Boolean flag indicating whether the record saved was being created
         *   (``true`` or edited (``false``)
         * ``edited_record``
         *   The result of saving the record (either the newly created record,
         *   or the post-edition record), after insertion in the Collection if
         *   needs be.
         *
         * @returns {$.Deferred<{created: Boolean, edited_record: Record}>}
         */
        save_row: function () {
            //noinspection JSPotentiallyInvalidConstructorUsage
            var self = this;
            return this.edition_form
                .do_save(null, this.options.editable === 'top')
                .pipe(function (result) {
                    if (result.created && !self.edition_id) {
                        self.records.add({id: result.result},
                            {at: self.options.editable === 'top' ? 0 : null});
                        self.edition_id = result.result;
                    }
                    var edited_record = self.records.get(self.edition_id);

                    return $.when(
                        self.handle_onwrite(self.edition_id),
                        self.cancel_pending_edition().then(function () {
                            $(self).trigger('saved', [self.dataset]);
                        })).pipe(function () {
                            return {
                                created: result.created || false,
                                edited_record: edited_record
                            };
                        });
                });
        },
        /**
         * If the current list is being edited, ensures it's saved
         */
        ensure_saved: function () {
            if (this.edition) {
                // kinda-hack-ish: if the user has entered data in a field,
                // oe_form_dirty will be set on the form so save, otherwise
                // discard the current (entirely empty) line
                if (this.edition_form.$element.is('.oe_form_dirty')) {
                    return this.save_row();
                }
                return this.cancel_pending_edition();
            }
            //noinspection JSPotentiallyInvalidConstructorUsage
            return $.when();
        },
        /**
         * Cancels the edition of the row for the current dataset index
         */
        cancel_edition: function () {
            this.cancel_pending_edition();
        },
        /**
         * Edits record currently selected via dataset
         */
        edit_record: function (record_id) {
            this.render_row_as_form(
                this.$current.find('[data-id=' + record_id + ']'));
            $(this).trigger(
                'edit',
                [record_id, this.dataset]);
        },
        new_record: function () {
            this.render_row_as_form();
        }
    });
};
