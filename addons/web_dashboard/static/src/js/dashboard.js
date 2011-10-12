openerp.web_dashboard = function(openerp) {
var QWeb = openerp.web.qweb;
QWeb.add_template('/web_dashboard/static/src/xml/web_dashboard.xml');

if (!openerp.web_dashboard) {
    /** @namespace */
    openerp.web_dashboard = {};
}

openerp.web.form.DashBoard = openerp.web.form.Widget.extend({
    init: function(view, node) {
        this._super(view, node);
        this.template = 'DashBoard';
        this.actions_attrs = {};
        this.action_managers = [];
    },
    start: function() {
        var self = this;
        this._super.apply(this, arguments);

        this.$element.find('.oe-dashboard-column').sortable({
            connectWith: '.oe-dashboard-column',
            handle: '.oe-dashboard-action-header',
            scroll: false
        }).disableSelection().bind('sortstop', self.do_save_dashboard);

        // Events
        this.$element.find('.oe-dashboard-link-undo').click(this.on_undo);
        this.$element.find('.oe-dashboard-link-reset').click(this.on_reset);
        this.$element.find('.oe-dashboard-link-add_widget').click(this.on_add_widget);
        this.$element.find('.oe-dashboard-link-change_layout').click(this.on_change_layout);

        this.$element.delegate('.oe-dashboard-column .oe-dashboard-fold', 'click', this.on_fold_action);
        this.$element.delegate('.oe-dashboard-column .ui-icon-closethick', 'click', this.on_close_action);

        this.actions_attrs = {};
        // Init actions
        _.each(this.node.children, function(column) {
            _.each(column.children, function(action) {
                delete(action.attrs.width);
                delete(action.attrs.height);
                delete(action.attrs.colspan);
                self.actions_attrs[action.attrs.name] = action.attrs;
                self.rpc('/web/action/load', {
                    action_id: parseInt(action.attrs.name, 10)
                }, self.on_load_action);
            });
        });

        //this.$element.find('a.oe-dashboard-action-rename').live('click', this.on_rename);
    },
    on_undo: function() {
        this.rpc('/web/view/undo_custom', {
            view_id: this.view.fields_view.view_id
        }, this.do_reload);
    },
    on_reset: function() {
        this.rpc('/web/view/undo_custom', {
            view_id: this.view.fields_view.view_id,
            reset: true
        }, this.do_reload);
    },
    on_add_widget: function() {
        var self = this;
        var action_manager = new openerp.web.ActionManager(this);
        var dialog = new openerp.web.Dialog(this, {
            title : 'Actions',
            width: 800,
            height: 600,
            buttons : {
                Cancel : function() {
                    $(this).dialog('destroy');
                },
                Add : function() {
                    self.do_add_widget(action_manager.inner_viewmanager.views.list.controller);
                    $(this).dialog('destroy');
                }
            }
        }).start().open();
        action_manager.appendTo(dialog.$element);
        action_manager.do_action({
            res_model : 'ir.actions.actions',
            views : [[false, 'list']],
            type : 'ir.actions.act_window',
            limit : 80,
            auto_search : true,
            flags : {
                sidebar : false,
                views_switcher : false,
                action_buttons : false
            }
        });
        // TODO: should bind ListView#select_record in order to catch record clicking
    },
    do_add_widget : function(listview) {
        var self = this,
            actions = listview.groups.get_selection().ids,
            results = [],
            qdict = { view : this.view };
        // TODO: should load multiple actions at once
        _.each(actions, function(aid) {
            self.rpc('/web/action/load', {
                action_id: aid
            }, function(result) {
                self.actions_attrs[aid] = {
                    name: aid,
                    string: _.trim(result.result.name)
                };
                qdict.action = {
                    attrs : self.actions_attrs[aid]
                };
                self.$element.find('.oe-dashboard-column:first').prepend(QWeb.render('DashBoard.action', qdict));
                self.do_save_dashboard();
                self.on_load_action(result)
            });
        });
    },
    on_rename : function(e) {
        var self = this,
            id = parseInt($(e.currentTarget).parents('.oe-dashboard-action:first').attr('data-id'), 10),
            $header = $(e.currentTarget).parents('.oe-dashboard-action-header:first'),
            $rename = $header.find('a.oe-dashboard-action-rename').hide(),
            $title = $header.find('span.oe-dashboard-action-title').hide(),
            $input = $header.find('input[name=title]');
        $input.val($title.text()).show().focus().bind('keydown', function(e) {
            if (e.which == 13 || e.which == 27) {
                if (e.which == 13) { //enter
                    var val = $input.val();
                    if (!val) {
                        return false;
                    }
                    $title.text(val);
                    self.actions_attrs[id].string = val;
                    self.do_save_dashboard();
                }
                $input.unbind('keydown').hide();
                $rename.show();
                $title.show();
            }
        });
    },
    on_change_layout: function() {
        var self = this;
        var qdict = {
            current_layout : this.$element.find('.oe-dashboard').attr('data-layout')
        };
        var $dialog = $('<div>').dialog({
                            modal: true,
                            title: 'Edit Layout',
                            width: 'auto',
                            height: 'auto'
                        }).html(QWeb.render('DashBoard.layouts', qdict));
        $dialog.find('li').click(function() {
            var layout = $(this).attr('data-layout');
            $dialog.dialog('destroy');
            self.do_change_layout(layout);
        });
    },
    do_change_layout: function(new_layout) {
        var $dashboard = this.$element.find('.oe-dashboard');
        var current_layout = $dashboard.attr('data-layout');
        if (current_layout != new_layout) {
            var clayout = current_layout.split('-').length,
                nlayout = new_layout.split('-').length,
                column_diff = clayout - nlayout;
            if (column_diff > 0) {
                var $last_column = $();
                $dashboard.find('.oe-dashboard-column').each(function(k, v) {
                    if (k >= nlayout) {
                        $(v).find('.oe-dashboard-action').appendTo($last_column);
                    } else {
                        $last_column = $(v);
                    }
                });
            }
            $dashboard.toggleClass('oe-dashboard-layout_' + current_layout + ' oe-dashboard-layout_' + new_layout);
            $dashboard.attr('data-layout', new_layout);
            this.do_save_dashboard();
        }
    },
    on_fold_action: function(e) {
        var $e = $(e.currentTarget),
            $action = $e.parents('.oe-dashboard-action:first'),
            id = parseInt($action.attr('data-id'), 10);
        if ($e.is('.ui-icon-minusthick')) {
            this.actions_attrs[id].fold = '1';
        } else {
            delete(this.actions_attrs[id].fold);
        }
        $e.toggleClass('ui-icon-minusthick ui-icon-plusthick');
        $action.find('.oe-dashboard-action-content').toggle();
        this.do_save_dashboard();
    },
    on_close_action: function(e) {
        $(e.currentTarget).parents('.oe-dashboard-action:first').remove();
        this.do_save_dashboard();
    },
    do_save_dashboard: function() {
        var self = this;
        var board = {
                form_title : this.view.fields_view.arch.attrs.string,
                style : this.$element.find('.oe-dashboard').attr('data-layout'),
                columns : []
            };
        this.$element.find('.oe-dashboard-column').each(function() {
            var actions = [];
            $(this).find('.oe-dashboard-action').each(function() {
                var action_id = $(this).attr('data-id');
                actions.push(self.actions_attrs[action_id]);
            });
            board.columns.push(actions);
        });
        var arch = QWeb.render('DashBoard.xml', board);
        this.rpc('/web/view/add_custom', {
            view_id: this.view.fields_view.view_id,
            arch: arch
        }, function() {
            self.$element.find('.oe-dashboard-link-undo, .oe-dashboard-link-reset').show();
        });
    },
    on_load_action: function(result) {
        var self = this;
        var action_orig = _.extend({}, result.result);
        var action = result.result;
        action.flags = {
            search_view : false,
            sidebar : false,
            views_switcher : false,
            action_buttons : false,
            pager: false,
            low_profile: true,
            display_title: false
        };
        var am = new openerp.web.ActionManager(this);
        this.action_managers.push(am);
        am.appendTo($("#"+this.view.element_id + '_action_' + action.id));
        am.do_action(action);
        am.do_action = function(action) {
            self.do_action(action);
        }
        if (am.inner_viewmanager) {
            am.inner_viewmanager.on_mode_switch.add(function(mode) {
                self.do_action(action_orig);
            });
        }
    },
    render: function() {
        // We should start with three columns available
        for (var i = this.node.children.length; i < 3; i++) {
            this.node.children.push({
                tag: 'column',
                attrs: {},
                children: []
            });
        }
        return QWeb.render(this.template, this);
    },
    do_reload: function() {
        var view_manager = this.view.widget_parent,
            action_manager = view_manager.widget_parent;
        this.view.stop();
        action_manager.do_action(view_manager.action);
    }
});
openerp.web.form.DashBoardLegacy = openerp.web.form.DashBoard.extend({
    render: function() {
        if (this.node.tag == 'hpaned') {
            this.node.attrs.style = '2-1';
        } else if (this.node.tag == 'vpaned') {
            this.node.attrs.style = '1';
        }
        this.node.tag = 'board';
        _.each(this.node.children, function(child) {
            if (child.tag.indexOf('child') == 0) {
                child.tag = 'column';
                var actions = [], first_child = child.children[0];
                if (first_child && first_child.tag == 'vpaned') {
                    _.each(first_child.children, function(subchild) {
                        actions.push.apply(actions, subchild.children);
                    });
                    child.children = actions;
                }
            }
        });
        return this._super(this, arguments);
    }
});

openerp.web.form.widgets.add('hpaned', 'openerp.web.form.DashBoardLegacy');
openerp.web.form.widgets.add('vpaned', 'openerp.web.form.DashBoardLegacy');
openerp.web.form.widgets.add('board', 'openerp.web.form.DashBoard');

/*
 * ConfigOverview
 * This client action designed to be used as a dashboard widget display
 * ir.actions.todo in a fancy way
 */
openerp.web.client_actions.add( 'board.config.overview', 'openerp.web_dashboard.ConfigOverview');
openerp.web_dashboard.ConfigOverview = openerp.web.View.extend({
    template: 'ConfigOverview',
    init: function (parent) {
        this._super(parent);
        this.dataset = new openerp.web.DataSetSearch(
                this, 'ir.actions.todo');
        this.dataset.domain = [['type', '!=', 'automatic']];
    },
    start: function () {
        this._super();
        $.when(this.dataset.read_slice(['state', 'action_id', 'category_id']),
               this.dataset.call('progress'))
            .then(this.on_records_loaded);
    },
    on_records_loaded: function (read_response, progress_response) {
        var records = read_response,
           progress = progress_response[0];

        var grouped_todos = _(records).chain()
            .map(function (record) {
                return {
                    id: record.id,
                    name: record.action_id[1],
                    done: record.state !== 'open',
                    to_do: record.state === 'open',
                    category: record['category_id'][1] || "Uncategorized"
                }
            })
            .groupBy(function (record) {return record.category})
            .value();
        this.$element.html(QWeb.render('ConfigOverview.content', {
            completion: 100 * progress.done / progress.total,
            groups: grouped_todos
        }));
        var $progress = this.$element.find('div.oe-config-progress-bar');
        $progress.progressbar({value: $progress.data('completion')});

        var self = this;
        this.$element.find('dl')
            .delegate('input', 'click', function (e) {
                // switch todo status
                e.stopImmediatePropagation();
                var new_state = this.checked ? 'done' : 'open',
                      todo_id = parseInt($(this).val(), 10);
                self.dataset.write(todo_id, {state: new_state}, {}, function () {
                    self.start();
                });
            })
            .delegate('li:not(.oe-done)', 'click', function () {
                self.widget_parent.widget_parent.widget_parent.do_execute_action({
                        type: 'object',
                        name: 'action_launch'
                    }, self.dataset,
                    $(this).data('id'), function () {
                        // after action popup closed, refresh configuration
                        // thingie
                        self.start();
                    });
            });
    }
});

/*
 * ApplicationTiles
 * This client action designed to be used as a dashboard widget display
 * either a list of application to install (if none is installed yet) or
 * a list of root menu
 */
openerp.web.client_actions.add( 'board.home.applications', 'openerp.web_dashboard.ApplicationTiles');
openerp.web_dashboard.apps = {
    applications: [
        [
            {
                module: 'crm', name: 'CRM',
                help: "Acquire leads, follow opportunities, manage prospects and phone calls, \u2026"
            }, {
                module: 'sale', name: 'Sales',
                help: "Do quotations, follow sales orders, invoice and control deliveries"
            }, {
                module: 'account_voucher', name: 'Invoicing',
                help: "Send invoice, track payments and reminders"
            }, {
                module: 'project', name: 'Projects',
                help: "Manage projects, track tasks, invoice task works, follow issues, \u2026"
            }
        ], [
            {
                module: 'purchase', name: 'Purchase',
                help: "Do purchase orders, control invoices and reception, follow your suppliers, \u2026"
            }, {
                module: 'stock', name: 'Warehouse',
                help: "Track your stocks, schedule product moves, manage incoming and outgoing shipments, \u2026"
            }, {
                module: 'hr', name: 'Human Resources',
                help: "Manage employees and their contracts, follow laves, recruit people, \u2026"
            }, {
                module: 'point_of_sale', name: 'Point of Sales',
                help: "Manage shop sales, use touch-screen POS"
            }
        ], [
            {
                module: 'profile_tools', name: 'Extra Tools',
                help: "Track ideas, manage lunch, create surveys, share data"
            }, {
                module: 'mrp', name: 'Manufacturing',
                help: "Manage your manufacturing, control your supply chain, personalize master data, \u2026"
            }, {
                module: 'marketing', name: 'Marketing',
                help: "Manage campaigns, follow activities, automate emails, \u2026"
            }, {
                module: 'knowledge', name: 'Knowledge',
                help: "Track your documents, browse your files, \u2026"
            }
        ]
    ]
};
openerp.web_dashboard.ApplicationTiles = openerp.web.View.extend({
    template: 'ApplicationTiles',
    start: function () {
        var self = this;
        this._super();
        // Check for installed application
        var Installer = new openerp.web.DataSet(this, 'base.setup.installer');
        Installer.call('default_get', [], function (installed_modules) {
            var installed = false;
            _.each(installed_modules, function(v,k) {
                if(_.startsWith(k,"cat")) {
                   installed =installed || v;
                }
            });
            if(installed) {
                self.do_display_root_menu();
            } else {
                self.do_display_installer();
            }
        } );
    },
    do_display_root_menu: function() {
        var self = this;
        var dss = new openerp.web.DataSetSearch( this, 'ir.ui.menu', null, [['parent_id', '=', false]]);
        var r = dss.read_slice( ['name', 'web_icon_data', 'web_icon_hover_data'], {}, function (applications) {
            // Create a matrix of 3*x applications
            var rows = [];
            while (applications.length) {
                rows.push(applications.splice(0, 3));
            }
            var tiles = QWeb.render( 'ApplicationTiles.content', {rows: rows});
            self.$element.append(tiles)
                .find('.oe-dashboard-home-tile')
                    .click(function () {
                        openerp.webclient.menu.on_menu_click(null, $(this).data('menuid'))
                    });
        });
        return  r;
    },
    do_display_installer: function() {
        var self = this;
        var render_ctx = {
            url: window.location.protocol + '//' + window.location.host + window.location.pathname,
            session: self.session,
            rows: openerp.web_dashboard.apps.applications
        };
        var installer = QWeb.render('StaticHome', render_ctx);
        self.$element.append(installer);
        this.$element.delegate('.oe-static-home-tile-text button', 'click', function () {
            self.install_module($(this).val());
        });
    },
    install_module: function (module_name) {
        var self = this;
        var Modules = new openerp.web.DataSetSearch(
            this, 'ir.module.module', null,
            [['name', '=', module_name], ['state', '=', 'uninstalled']]);
        var Upgrade = new openerp.web.DataSet(this, 'base.module.upgrade');

        $.blockUI({message:'<img src="/web/static/src/img/throbber2.gif">'});
        Modules.read_slice(['id'], {}, function (records) {
            if (!(records.length === 1)) { $.unblockUI(); return; }
            Modules.call('state_update',
                [_.pluck(records, 'id'), 'to install', ['uninstalled']],
                function () {
                    Upgrade.call('upgrade_module', [[]], function () {
                        self.run_configuration_wizards();
                    });
                }
            )
        });
    },
    run_configuration_wizards: function () {
        var self = this;
        new openerp.web.DataSet(this, 'res.config').call('start', [[]], function (action) {
            $.unblockUI();
            self.do_action(action, function () {
                // TODO: less brutal reloading
                window.location.reload(true);
            });
        });
    }
});

/*
 * Widgets
 * This client action designed to be used as a dashboard widget display
 * the html content of a res_widget given as argument
 */
openerp.web.client_actions.add( 'board.home.widgets', 'openerp.web_dashboard.Widget');
openerp.web_dashboard.Widget = openerp.web.View.extend(/** @lends openerp.web_dashboard.Widgets# */{
    template: 'HomeWidget',
    /**
     * Initializes a "HomeWidget" client widget: handles the display of a given
     * res.widget objects in an OpenERP view (mainly a dashboard).
     *
     * @constructs openerp.web_dashboard.Widget
     * @extends openerp.web.View
     *
     * @param {Object} parent
     * @param {Object} options
     * @param {Number} options.widget_id
     */
    init: function (parent, options) {
        this._super(parent);
        this.widget_id = options.widget_id;
    },
    start: function () {
        this._super();
        return new openerp.web.DataSet(this, 'res.widget').read_ids(
                [this.widget_id], ['title'], this.on_widget_loaded);
    },
    on_widget_loaded: function (widgets) {
        var widget = widgets[0];
        var url = _.sprintf(
            '/web_dashboard/widgets/content?session_id=%s&widget_id=%d',
            this.session.session_id, widget.id);
        this.$element.html(QWeb.render('HomeWidget.content', {
            widget: widget,
            url: url
        }));
    }
});

};
