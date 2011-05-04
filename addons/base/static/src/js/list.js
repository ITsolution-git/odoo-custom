openerp.base.list = function (openerp) {
openerp.base.views.add('list', 'openerp.base.ListView');
openerp.base.ListView = openerp.base.Controller.extend(
    /** @lends openerp.base.ListView# */ {
    defaults: {
        // records can be selected one by one
        'selectable': true,
        // list rows can be deleted
        'deletable': true,
        // whether the column headers should be displayed
        'header': true,
        // display addition button, with that label
        'addable': "New",
        // whether the list view can be sorted, note that once a view has been
        // sorted it can not be reordered anymore
        'sortable': true,
        // whether the view rows can be reordered (via vertical drag & drop)
        'reorderable': true
    },
    /**
     * Core class for list-type displays.
     *
     * As a view, needs a number of view-related parameters to be correctly
     * instantiated, provides options and overridable methods for behavioral
     * customization.
     *
     * See constructor parameters and method documentations for information on
     * the default behaviors and possible options for the list view.
     *
     * @constructs
     * @param view_manager
     * @param session An OpenERP session object
     * @param element_id the id of the DOM elements this view should link itself to
     * @param {openerp.base.DataSet} dataset the dataset the view should work with
     * @param {String} view_id the listview's identifier, if any
     * @param {Object} options A set of options used to configure the view
     * @param {Boolean} [options.selectable=true] determines whether view rows are selectable (e.g. via a checkbox)
     * @param {Boolean} [options.header=true] should the list's header be displayed
     * @param {Boolean} [options.deletable=true] are the list rows deletable
     * @param {null|String} [options.addable="New"] should the new-record button be displayed, and what should its label be. Use ``null`` to hide the button.
     * @param {Boolean} [options.sortable=true] is it possible to sort the table by clicking on column headers
     * @param {Boolean} [options.reorderable=true] is it possible to reorder list rows
     *
     * @borrows openerp.base.ActionExecutor#execute_action as #execute_action
     */
    init: function(view_manager, session, element_id, dataset, view_id, options) {
        this._super(session, element_id);
        this.view_manager = view_manager;
        this.dataset = dataset;
        this.model = dataset.model;
        this.view_id = view_id;

        this.columns = [];
        this.rows = [];

        this.options = _.extend({}, this.defaults, options || {});
    },
    /**
     * View startup method, the default behavior is to set the ``oe-listview``
     * class on its root element and to perform an RPC load call.
     *
     * @returns {$.Deferred} loading promise
     */
    start: function() {
        this.$element.addClass('oe-listview');
        return this.rpc("/base/listview/load", {
            model: this.model,
            view_id: this.view_id,
            toolbar: this.view_manager ? !!this.view_manager.sidebar : false
        }, this.on_loaded);
    },
    /**
     * Called after loading the list view's description, sets up such things
     * as the view table's columns, renders the table itself and hooks up the
     * various table-level and row-level DOM events (action buttons, deletion
     * buttons, selection of records, [New] button, selection of a given
     * record, ...)
     *
     * Sets up the following:
     *
     * * Processes arch and fields to generate a complete field descriptor for each field
     * * Create the table itself and allocate visible columns
     * * Hook in the top-level (header) [New|Add] and [Delete] button
     * * Sets up showing/hiding the top-level [Delete] button based on records being selected or not
     * * Sets up event handlers for action buttons and per-row deletion button
     * * Hooks global callback for clicking on a row
     * * Sets up its sidebar, if any
     *
     * @param {Object} data wrapped fields_view_get result
     * @param {Object} data.fields_view fields_view_get result (processed)
     * @param {Object} data.fields_view.fields mapping of fields for the current model
     * @param {Object} data.fields_view.arch current list view descriptor
     */
    on_loaded: function(data) {
        var self = this;
        this.fields_view = data.fields_view;
        //this.log(this.fields_view);
        this.name = "" + this.fields_view.arch.attrs.string;

        var fields = this.fields_view.fields;
        var domain_computer = openerp.base.form.compute_domain;
        this.columns = _(this.fields_view.arch.children).chain()
            .map(function (field) {
                var name = field.attrs.name;
                var column = _.extend({id: name, tag: field.tag},
                                      field.attrs, fields[name]);
                // attrs computer
                if (column.attrs) {
                    var attrs = eval('(' + column.attrs + ')');
                    column.attrs_for = function (fields) {
                        var result = {};
                        for (var attr in attrs) {
                            result[attr] = domain_computer(attrs[attr], fields);
                        }
                        return result;
                    };
                } else {
                    column.attrs_for = function () { return {}; };
                }
                return column;
            }).value();

        this.visible_columns = _.filter(this.columns, function (column) {
            return column.invisible !== '1';
        });
        this.$element.html(QWeb.render("ListView", this));

        // Head hook
        this.$element.find('#oe-list-add').click(this.do_add_record);
        this.$element.find('#oe-list-delete')
                .hide()
                .click(this.do_delete_selected);

        var $table = this.$element.find('table');
        // Cell events
        $table.delegate(
            'th.oe-record-selector', 'click', function (e) {
                // TODO: ~linear performances, would a simple counter work?
                if ($table.find('th.oe-record-selector input:checked').length) {
                    $table.find('#oe-list-delete').show();
                } else {
                    $table.find('#oe-list-delete').hide();
                }
                // A click in the selection cell should not activate the
                // linking feature
                e.stopImmediatePropagation();
        });
        $table.delegate(
            'td.oe-field-cell button', 'click', function (e) {
                e.stopImmediatePropagation();

                var $cell = $(e.currentTarget).closest('td');

                var col_index = $cell.prevAll('td').length;
                var field = self.visible_columns[col_index];

                var $row = $cell.parent('tr');
                var row = self.rows[$row.prevAll().length];

                // TODO: we should probably only reload content, also maybe diff records or something, instead of replacing every single row
                self.execute_action(
                    field, self.dataset, self.session.action_manager,
                    row.data.id.value, self.do_reload);
            });
        $table.delegate(
                'td.oe-record-delete button', 'click', this.do_delete);

        // Global rows handlers
        $table.delegate(
                'tr', 'click', this.on_select_row);

        // sidebar stuff
        if (this.view_manager && this.view_manager.sidebar) {
            this.view_manager.sidebar.set_toolbar(data.fields_view.toolbar);
        }
    },
    /**
     * Fills the table with the provided records after emptying it
     *
     * TODO: should also re-load the table itself, as e.g. columns may have changed
     *
     * @param {Object} result filling result
     * @param {Array} [result.view] the new view (wrapped fields_view_get result)
     * @param {Array} result.records records the records to fill the list view with
     * @returns {Promise} promise to the end of view rendering (list views are asynchronously filled for improved responsiveness)
     */
    do_fill_table: function(result) {
        if (result.view) {
            this.on_loaded({fields_view: result.view});
        }
        var records = result.records;
        var $table = this.$element.find('table');
        this.rows = records;

        // Keep current selected record, if it's still in our new search
        var current_record_id = this.dataset.ids[this.dataset.index];
        this.dataset.ids = _(records).chain().map(function (record) {
            return record.data.id.value;
        }).value();
        this.dataset.index = _.indexOf(this.dataset.ids, current_record_id);
        if (this.dataset.index < 0) {
            this.dataset.index = 0;
        }
        
        this.dataset.count = this.dataset.ids.length;
        var results = this.rows.length;
        $table.find('.oe-pager-last').text(results);
        $table.find('.oe-pager-total').text(results);


        // remove all data lines
        var $old_body = $table.find('tbody');

        // add new content
        var columns = this.columns,
            rows = this.rows,
            options = this.options;

        // Paginate by groups of 50 for rendering
        var PAGE_SIZE = 50,
            bodies_count = Math.ceil(this.rows.length / PAGE_SIZE),
            body = 0,
            $body = $('<tbody class="ui-widget-content">').appendTo($table);

        var rendered = $.Deferred();
        var render_body = function () {
            setTimeout(function () {
                $body.append(
                    QWeb.render("ListView.rows", {
                        columns: columns,
                        rows: rows.slice(body*PAGE_SIZE, (body+1)*PAGE_SIZE),
                        options: options
                }));
                ++body;
                if (body < bodies_count) {
                    render_body();
                } else {
                    rendered.resolve();
                }
            }, 0);
        };
        render_body();

        return rendered.promise().then(function () {
            $old_body.remove();
        });
    },
    /**
     * Used to handle a click on a table row, if no other handler caught the
     * event.
     *
     * The default implementation asks the list view's view manager to switch
     * to a different view (by calling
     * :js:func:`~openerp.base.ViewManager.on_mode_switch`), using the
     * provided record index (within the current list view's dataset).
     *
     * If the index is null, ``switch_to_record`` asks for the creation of a
     * new record.
     *
     * @param {Number|null} index the record index (in the current dataset) to switch to
     * @param {String} [view="form"] the view type to switch to
     */
    switch_to_record:function (index, view) {
        view = view || 'form';
        this.dataset.index = index;
        _.delay(_.bind(function () {
            if(this.view_manager) {
                this.view_manager.on_mode_switch(view);
            }
        }, this));
    },
    /**
     * Base handler for clicking on a row, discovers the index of the record
     * corresponding to the clicked row in the list view's dataset.
     *
     * Should not be overridden, use
     * :js:func:`~openerp.base.ListView.switch_to_record` to customize the
     * behavior of the list view when clicking on a row instead.
     *
     * @param {Object} event jQuery DOM event object
     */
    on_select_row: function (event) {
        var $target = $(event.currentTarget);
        if (!$target.parent().is('tbody')) {
            return;
        }
        // count number of preceding siblings to line clicked
        var row = this.rows[$target.prevAll().length];

        var index = _.indexOf(this.dataset.ids, row.data.id.value);
        if (index == undefined || index === -1) {
            return;
        }
        this.switch_to_record(index);
    },
    do_show: function () {
        this.$element.show();
        if (this.hidden) {
            this.do_reload();
            this.hidden = false;
        }
    },
    do_hide: function () {
        this.$element.hide();
        this.hidden = true;
    },
    /**
     * Reloads the search view based on the current settings (dataset & al)
     */
    do_reload: function () {
        // TODO: need to do 5 billion tons of pre-processing, bypass
        // DataSet for now
        //self.dataset.read_slice(self.dataset.fields, 0, self.limit,
        // self.do_fill_table);
        this.dataset.offset = 0;
        this.dataset.limit = false;
        return this.rpc('/base/listview/fill', {
            'model': this.dataset.model,
            'id': this.view_id,
            'context': this.dataset.context,
            'domain': this.dataset.domain,
            'ids': this.dataset.ids
        }, this.do_fill_table);
    },
    /**
     * Event handler for a search, asks for the computation/folding of domains
     * and contexts (and group-by), then reloads the view's content.
     *
     * @param {Array} domains a sequence of literal and non-literal domains
     * @param {Array} contexts a sequence of literal and non-literal contexts
     * @param {Array} groupbys a sequence of literal and non-literal group-by contexts
     * @returns {$.Deferred} fold request evaluation promise
     */
    do_search: function (domains, contexts, groupbys) {
        var self = this;
        return this.rpc('/base/session/eval_domain_and_context', {
            domains: domains,
            contexts: contexts,
            group_by_seq: groupbys
        }, function (results) {
            // TODO: handle non-empty results.group_by with read_group
            self.dataset.context = results.context;
            self.dataset.domain = results.domain;
            return self.do_reload();
        });
    },
    do_update: function () {
        var self = this;
        //self.dataset.read_ids(self.dataset.ids, self.dataset.fields, self.do_fill_table);
    },
    /**
     * Handles the signal to delete a line from the DOM
     *
     * @param e jQuery event object
     */
    do_delete: function (e) {
        // don't link to forms
        e.stopImmediatePropagation();
        this.dataset.unlink(
            [this.rows[$(e.currentTarget).closest('tr').prevAll().length].data.id.value]);
    },
    /**
     * Handles signal for the addition of a new record (can be a creation,
     * can be the addition from a remote source, ...)
     *
     * The default implementation is to switch to a new record on the form view
     */
    do_add_record: function () {
        this.notification.notify('Add', "New record");
        this.switch_to_record(null);
    },
    /**
     * Handles deletion of all selected lines
     */
    do_delete_selected: function () {
        var selection = this.get_selection();
        if (selection.length) {
            this.dataset.unlink(selection);
        }
    },
    /**
     * Gets the ids of all currently selected records, if any
     * @returns {Array} empty if no record is selected (or the list view is not selectable)
     */
    get_selection: function () {
        if (!this.options.selectable) {
            return [];
        }
        var rows = this.rows;
        return this.$element.find('th.oe-record-selector input:checked')
                .closest('tr').map(function () {
            return rows[$(this).prevAll().length].data.id.value;
        }).get();
    }
    // TODO: implement sort (click on column headers), if sorted, the list can not be reordered anymore
    // TODO: implement reorder (drag and drop rows)
});
_.extend(openerp.base.ListView.prototype, openerp.base.ActionExecutor);

openerp.base.TreeView = openerp.base.Controller.extend({
});

};

// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax:
