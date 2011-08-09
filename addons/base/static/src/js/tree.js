openerp.base.tree = function(openerp) {
openerp.base.views.add('tree', 'openerp.base.TreeView');

/**
 * Genuine tree view (the one displayed as a tree, not the list)
 */
openerp.base.TreeView = openerp.base.View.extend({
    /**
     * Indicates that this view is not searchable, and thus that no search
     * view should be displayed (if there is one active).
     */
    searchable : false,

    init: function(view_manager, session, element_id, dataset, view_id, options) {
        this._super(session, element_id);
        this.view_manager = view_manager || new openerp.base.NullViewManager();
        this.dataset = dataset;
        this.model = dataset.model;
        this.view_id = view_id;
        this.session = session;

        this.records = {};

        this.options = _.extend({}, this.defaults, options || {});

        this.flags =  this.view_manager.action.flags;

        this.view_manager.flags.search_view = this.view_manager.action.flags.search_view = false;
        this.view_manager.flags.sidebar = this.view_manager.action.flags.sidebar = false;
    },

    start: function () {
        this._super();
        return this.rpc("/base/treeview/load", {
            model: this.model,
            view_id: this.view_id,
            toolbar: this.view_manager ? !!this.view_manager.sidebar : false
        }, this.on_loaded);
    },
    /**
     * Returns the list of fields needed to correctly read objects.
     *
     * Gathers the names of all fields in fields_view_get, and adds the
     * field_parent (children_field in the tree view) if it's not already one
     * of the fields to fetch
     *
     * @returns {Array} an array of fields which can be provided to DataSet.read_slice and others
     */
    fields_list: function () {
        var fields = _.keys(this.fields);
        if (!_(fields).contains(this.children_field)) {
            fields.push(this.children_field);
        }
        return fields;
    },
    on_loaded: function (fields_view) {
        var self = this;
        var has_toolbar = !!fields_view.arch.attrs.toolbar;
        // field name in OpenERP is kinda stupid: this is the name of the field
        // holding the ids to the children of the current node, why call it
        // field_parent?
        this.children_field = fields_view['field_parent'];
        this.fields_view = fields_view;
        _(this.fields_view.arch.children).each(function (field) {
            if (field.attrs.modifiers) {
                field.attrs.modifiers = JSON.parse(field.attrs.modifiers);
            }
        });
        this.fields = fields_view.fields;
        this.hook_row_click();
        this.$element.html(QWeb.render('TreeView', {
            'title': this.fields_view.arch.attrs.string,
            'fields_view': this.fields_view.arch.children,
            'fields': this.fields,
            'toolbar': has_toolbar
        }));

        this.dataset.read_slice(this.fields_list(), 0, false, function (records) {
            if (!has_toolbar) {
                // WARNING: will do a second read on the same ids, but only on
                //          first load so not very important
                self.getdata(null, _(records).pluck('id'));
                return;
            }

            var $select = self.$element.find('select')
                .change(function () {
                    var $option = $(this).find(':selected');
                    self.getdata($option.val(), $option.data('children'));
                });
            _(records).each(function (record) {
                self.records[record.id] = record;
                $('<option>')
                        .val(record.id)
                        .text(record.name)
                        .data('children', record[self.children_field])
                    .appendTo($select);
            });

            $select.change();
        });
    },
    /**
     * Sets up opening a row
     */
    hook_row_click: function () {
        var self = this;
        this.$element.delegate('.treeview-td span, .treeview-tr span', 'click', function (e) {
            e.stopImmediatePropagation();
            self.activate($(this).closest('tr').data('id'));
        });

        this.$element.delegate('.treeview-tr', 'click', function () {
            var is_loaded = 0,
                $this = $(this),
                record_id = $this.data('id'),
                record = self.records[record_id],
                children_ids = record[self.children_field];

            _(children_ids).each(function(childid) {
                if (self.$element.find('#treerow_' + childid).length) {
                    if (self.$element.find('#treerow_' + childid).is(':hidden')) {
                        is_loaded = -1;
                    } else {
                        is_loaded++;
                    }
                }
            });
            if (is_loaded === 0) {
                if (!$this.parent().hasClass('oe-open')) {
                    self.getdata(record_id, children_ids);
                }
            } else {
                self.showcontent(record_id, is_loaded < 0);
            }
        });
    },
    // get child data of selected value
    getdata: function (id, children_ids) {
        var self = this;

        self.dataset.read_ids(children_ids, this.fields_list(), function (records) {
            _(records).each(function (record) {
                self.records[record.id] = record;
            });

            var $curr_node = self.$element.find('#treerow_' + id);
            var children_rows = QWeb.render('TreeView.rows', {
                'records': records,
                'children_field': self.children_field,
                'fields_view': self.fields_view.arch.children,
                'field': self.fields,
                'level': $curr_node.data('level') || 0
            });

            if ($curr_node.length) {
                $curr_node.addClass('oe-open');
                $curr_node.after(children_rows);
            } else {
                self.$element.find('tbody').html(children_rows);
            }
        });
    },

    // Get details in listview
    activate: function(id) {
        var action_manager = new openerp.base.ActionManager(
                this.session, this.element_id);
        action_manager.start();
        this.rpc('/base/treeview/action', {
            id: id,
            model: this.dataset.model,
            context: new openerp.base.CompoundContext(
                this.dataset.get_context(), {
                    active_model: this.dataset.model,
                    active_id: id,
                    active_ids: [id]})
        }, function (actions) {
            if (!actions.length) { return; }
            var action = actions[0][2];
            action.flags.new_window = true;
            action_manager.do_action(action);
        });
    },

    // show & hide the contents
    showcontent: function (record_id, show) {
        this.$element.find('#treerow_' + record_id)
                .toggleClass('oe-open', show);

        _(this.records[record_id][this.children_field]).each(function (child_id) {
            var $child_row = this.$element.find('#treerow_' + child_id);
            if ($child_row.hasClass('oe-open')) {
                this.showcontent(child_id, false);
            }
            $child_row.toggle(show);
        }, this);
    },

    do_show: function () {
        this.$element.show();
        this.view_manager.sidebar.do_refresh(true);
    },

    do_hide: function () {
        this.$element.hide();
        this.hidden = true;
    }
});
};
