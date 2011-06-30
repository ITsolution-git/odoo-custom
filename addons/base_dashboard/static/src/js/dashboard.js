openerp.base_dashboard = function(openerp) {

QWeb.add_template('/base_dashboard/static/src/xml/base_dashboard.xml');

openerp.base.form.DashBoard = openerp.base.form.Widget.extend({
    init: function(view, node) {
        this._super(view, node);
        this.template = 'DashBoard';
        this.actions_attrs = {};
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
        this.$element.find('.oe-dashboard-column .oe-dashboard-fold').click(this.on_fold_action);
        this.$element.find('.oe-dashboard-column .ui-icon-closethick').click(this.on_close_action);

        this.actions_attrs = {};
        // Init actions
        _.each(this.node.children, function(column) {
            _.each(column.children, function(action) {
                delete(action.attrs.width);
                delete(action.attrs.height);
                delete(action.attrs.colspan);
                self.actions_attrs[action.attrs.name] = action.attrs;
                self.rpc('/base/action/load', {
                    action_id: parseInt(action.attrs.name, 10)
                }, self.on_load_action);
            });
        });

        this.$element.find('a.oe-dashboard-action-rename').live('click', this.on_rename);
    },
    on_undo: function() {
        this.rpc('/base/view/undo_custom', {
            view_id: this.view.fields_view.view_id
        }, this.do_reload);
    },
    on_reset: function() {
        this.rpc('/base/view/undo_custom', {
            view_id: this.view.fields_view.view_id,
            reset: true
        }, this.do_reload);
    },
    on_add_widget: function() {
        var self = this;
        var action = {
            res_model : 'ir.actions.actions',
            views : [[false, 'list']],
            type : 'ir.actions.act_window',
            limit : 80,
            auto_search : true,
            domain : [['type', '=', 'ir.actions.act_window']],
            flags : {
                sidebar : false,
                views_switcher : false,
                action_buttons : false
            }
        };
        // TODO: create a Dialog controller which optionally takes an action
        // Should set width & height automatically and take buttons & views callback
        var dialog_id = _.uniqueId('act_window_dialog');
        var action_manager = new openerp.base.ActionManager(this.session, dialog_id);
        var $dialog = $('<div id=' + dialog_id + '>').dialog({
                            modal : true,
                            title : 'Actions',
                            width : 800,
                            height : 600,
                            buttons : {
                                Cancel : function() {
                                    $(this).dialog('destroy');
                                },
                                Add : function() {
                                    self.do_add_widget(action_manager);
                                    $(this).dialog('destroy');
                                }
                            }
                        });
        action_manager.start();
        action_manager.do_action(action);
        // TODO: should bind ListView#select_record in order to catch record clicking
    },
    do_add_widget : function(action_manager) {
        var self = this,
            actions = action_manager.viewmanager.views.list.controller.groups.get_selection().ids,
            results = [],
            qdict = { view : this.view };
        // TODO: should load multiple actions at once
        _.each(actions, function(aid) {
            self.rpc('/base/action/load', {
                action_id: aid
            }, function(result) {
                self.actions_attrs[aid] = {
                    name: aid,
                    string: _.trim(result.result.name)
                }
                qdict.action = {
                    attrs : self.actions_attrs[aid]
                }
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
                            height: 'auto',
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
        this.rpc('/base/view/add_custom', {
            view_id: this.view.fields_view.view_id,
            arch: arch
        }, function() {
            self.$element.find('.oe-dashboard-link-undo, .oe-dashboard-link-reset').show();
        });
    },
    on_load_action: function(result) {
        var action = result.result;
        action.flags = {
            search_view : false,
            sidebar : false,
            views_switcher : false,
            action_buttons : false,
            pager: false
        }
        var element_id = this.view.element_id + '_action_' + action.id;
        var view = new openerp.base.ViewManagerAction(this.session, element_id, action);
        view.start();
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
        this.view.view_manager.stop();
        this.view.view_manager.start();
    }
});
openerp.base.form.DashBoardLegacy = openerp.base.form.DashBoard.extend({
    render: function() {
        if (this.node.tag == 'hpaned') {
            this.node.attrs.style = '1-1';
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

openerp.base.form.widgets.add('hpaned', 'openerp.base.form.DashBoardLegacy');
openerp.base.form.widgets.add('vpaned', 'openerp.base.form.DashBoardLegacy');
openerp.base.form.widgets.add('board', 'openerp.base.form.DashBoard');
}
