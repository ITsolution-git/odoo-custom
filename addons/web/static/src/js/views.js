/*---------------------------------------------------------
 * OpenERP web library
 *---------------------------------------------------------*/

openerp.web.views = function(instance) {
var QWeb = instance.web.qweb,
    _t = instance.web._t;

instance.web.ActionManager = instance.web.Widget.extend({
    init: function(parent) {
        this._super(parent);
        this.inner_action = null;
        this.inner_widget = null;
        this.dialog = null;
        this.dialog_widget = null;
        this.breadcrumbs = [];
        this.on('history_back', this, function() {
            return this.history_back();
        });
    },
    start: function() {
        this._super.apply(this, arguments);
        this.$el.on('click', 'a.oe_breadcrumb_item', this.on_breadcrumb_clicked);
    },
    dialog_stop: function () {
        if (this.dialog) {
            this.dialog.destroy();
        }
        this.dialog = null;
    },
    /**
     * Add a new item to the breadcrumb
     *
     * If the title of an item is an array, the multiple title mode is in use.
     * (eg: a widget with multiple views might need to display a title for each view)
     * In multiple title mode, the show() callback can check the index it receives
     * in order to detect which of its titles has been clicked on by the user.
     *
     * @param {Object} item breadcrumb item
     * @param {Object} item.widget widget containing the view(s) to be added to the breadcrumb added
     * @param {Function} [item.show] triggered whenever the widget should be shown back
     * @param {Function} [item.hide] triggered whenever the widget should be shown hidden
     * @param {Function} [item.destroy] triggered whenever the widget should be destroyed
     * @param {String|Array} [item.title] title(s) of the view(s) to be displayed in the breadcrumb
     * @param {Function} [item.get_title] should return the title(s) of the view(s) to be displayed in the breadcrumb
     */
    push_breadcrumb: function(item) {
        var last = this.breadcrumbs.slice(-1)[0];
        if (last) {
            last.hide();
        }
        var item = _.extend({
            show: function(index) {
                this.widget.$el.show();
            },
            hide: function() {
                this.widget.$el.hide();
            },
            destroy: function() {
                this.widget.destroy();
            },
            get_title: function() {
                return this.title || this.widget.get('title');
            }
        }, item);
        item.id = _.uniqueId('breadcrumb_');
        this.breadcrumbs.push(item);
    },
    history_back: function() {
        var last = this.breadcrumbs.slice(-1)[0];
        if (!last) {
            return false;
        }
        var title = last.get_title();
        if (_.isArray(title) && title.length > 1) {
            return this.select_breadcrumb(this.breadcrumbs.length - 1, title.length - 2);
        } else if (this.breadcrumbs.length === 1) {
            // Only one single titled item in breadcrumb, most of the time you want to trigger back to home
            return false;
        } else {
            var prev = this.breadcrumbs[this.breadcrumbs.length - 2];
            title = prev.get_title();
            return this.select_breadcrumb(this.breadcrumbs.length - 2, _.isArray(title) ? title.length - 1 : undefined);
        }
    },
    on_breadcrumb_clicked: function(ev) {
        var $e = $(ev.target);
        var id = $e.data('id');
        var index;
        for (var i = this.breadcrumbs.length - 1; i >= 0; i--) {
            if (this.breadcrumbs[i].id == id) {
                index = i;
                break;
            }
        }
        var subindex = $e.parent().find('a.oe_breadcrumb_item[data-id=' + $e.data('id') + ']').index($e);
        this.select_breadcrumb(index, subindex);
    },
    select_breadcrumb: function(index, subindex) {
        var next_item = this.breadcrumbs[index + 1];
        if (next_item && next_item.on_reverse_breadcrumb) {
            next_item.on_reverse_breadcrumb(this.breadcrumbs[index].widget);
        }
        for (var i = this.breadcrumbs.length - 1; i >= 0; i--) {
            if (i > index) {
                if (this.remove_breadcrumb(i) === false) {
                    return false;
                }
            }
        }
        var item = this.breadcrumbs[index];
        item.show(subindex);
        this.inner_widget = item.widget;
        this.inner_action = item.action;
        return true;
    },
    clear_breadcrumbs: function() {
        for (var i = this.breadcrumbs.length - 1; i >= 0; i--) {
            if (this.remove_breadcrumb(0) === false) {
                break;
            }
        }
    },
    remove_breadcrumb: function(index) {
        var item = this.breadcrumbs.splice(index, 1)[0];
        if (item) {
            var dups = _.filter(this.breadcrumbs, function(it) {
                return item.widget === it.widget;
            });
            if (!dups.length) {
                if (this.getParent().has_uncommitted_changes()) {
                    this.inner_widget = item.widget;
                    this.inner_action = item.action;
                    this.breadcrumbs.splice(index, 0, item);
                    return false;
                } else {
                    item.destroy();
                }
            }
        }
        var last_widget = this.breadcrumbs.slice(-1)[0];
        if (last_widget) {
            this.inner_widget = last_widget.widget;
            this.inner_action = last_widget.action;
        }
    },
    get_title: function() {
        var titles = [];
        for (var i = 0; i < this.breadcrumbs.length; i += 1) {
            var item = this.breadcrumbs[i];
            var tit = item.get_title();
            if (!_.isArray(tit)) {
                tit = [tit];
            }
            for (var j = 0; j < tit.length; j += 1) {
                var label = _.escape(tit[j]);
                if (i === this.breadcrumbs.length - 1 && j === tit.length - 1) {
                    titles.push(_.str.sprintf('<span class="oe_breadcrumb_item">%s</span>', label));
                } else {
                    titles.push(_.str.sprintf('<a href="#" class="oe_breadcrumb_item" data-id="%s">%s</a>', item.id, label));
                }
            }
        }
        return titles.join(' <span class="oe_fade">/</span> ');
    },
    do_push_state: function(state) {
        state = state || {};
        if (this.getParent() && this.getParent().do_push_state) {
            if (this.inner_action) {
                if (this.inner_action._push_me === false) {
                    // this action has been explicitly marked as not pushable
                    return;
                }
                state['title'] = this.inner_action.name;
                if(this.inner_action.type == 'ir.actions.act_window') {
                    state['model'] = this.inner_action.res_model;
                }
                if (this.inner_action.menu_id) {
                    state['menu_id'] = this.inner_action.menu_id;
                }
                if (this.inner_action.id) {
                    state['action'] = this.inner_action.id;
                } else if (this.inner_action.type == 'ir.actions.client') {
                    state['action'] = this.inner_action.tag;
                    var params = {};
                    _.each(this.inner_action.params, function(v, k) {
                        if(_.isString(v) || _.isNumber(v)) {
                            params[k] = v;
                        }
                    });
                    state = _.extend(params || {}, state);
                }
            }
            if(!this.dialog) {
                this.getParent().do_push_state(state);
            }
        }
    },
    do_load_state: function(state, warm) {
        var self = this,
            action_loaded;
        if (state.action) {
            if (_.isString(state.action) && instance.web.client_actions.contains(state.action)) {
                var action_client = {
                    type: "ir.actions.client",
                    tag: state.action,
                    params: state,
                    _push_me: state._push_me,
                };
                this.null_action();
                action_loaded = this.do_action(action_client);
            } else {
                var run_action = (!this.inner_widget || !this.inner_widget.action) || this.inner_widget.action.id !== state.action;
                if (run_action) {
                    this.null_action();
                    action_loaded = this.do_action(state.action);
                    $.when(action_loaded || null).done(function() {
                        instance.webclient.menu.has_been_loaded.done(function() {
                            if (self.inner_action && self.inner_action.id) {
                                instance.webclient.menu.open_action(self.inner_action.id);
                            }
                        });
                    });
                }
            }
        } else if (state.model && state.id) {
            // TODO handle context & domain ?
            this.null_action();
            var action = {
                res_model: state.model,
                res_id: state.id,
                type: 'ir.actions.act_window',
                views: [[false, 'form']]
            };
            action_loaded = this.do_action(action);
        } else if (state.sa) {
            // load session action
            this.null_action();
            action_loaded = this.rpc('/web/session/get_session_action',  {key: state.sa}).then(function(action) {
                if (action) {
                    return self.do_action(action);
                }
            });
        }

        $.when(action_loaded || null).done(function() {
            if (self.inner_widget && self.inner_widget.do_load_state) {
                self.inner_widget.do_load_state(state, warm);
            }
        });
    },
    do_action: function(action, options) {
        options = _.defaults(options || {}, {
            clear_breadcrumbs: false,
            on_reverse_breadcrumb: function() {},
            on_close: function() {},
            action_menu_id: null,
        });
        if (_.isString(action) && instance.web.client_actions.contains(action)) {
            var action_client = { type: "ir.actions.client", tag: action, params: {} };
            return this.do_action(action_client, options);
        } else if (_.isNumber(action) || _.isString(action)) {
            var self = this;
            return self.rpc("/web/action/load", { action_id: action }).then(function(result) {
                return self.do_action(result, options);
            });
        }

        // Ensure context & domain are evaluated and can be manipulated/used
        if (action.context) {
            action.context = instance.web.pyeval.eval(
                'context', action.context);
        }
        if (action.domain) {
            action.domain = instance.web.pyeval.eval(
                'domain', action.domain);
        }

        if (!action.type) {
            console.error("No type for action", action);
            return $.Deferred().reject();
        }
        var type = action.type.replace(/\./g,'_');
        var popup = action.target === 'new';
        var inline = action.target === 'inline' || action.target === 'inlineview';
        action.flags = _.extend({
            views_switcher : !popup && !inline,
            search_view : !popup && !inline,
            action_buttons : !popup && !inline,
            sidebar : !popup && !inline,
            pager : !popup && !inline,
            display_title : !popup
        }, action.flags || {});
        action.menu_id = options.action_menu_id;
        if (!(type in this)) {
            console.error("Action manager can't handle action of type " + action.type, action);
            return $.Deferred().reject();
        }
        return this[type](action, options);
    },
    null_action: function() {
        this.dialog_stop();
        this.clear_breadcrumbs();
    },
    /**
     *
     * @param {Object} executor
     * @param {Object} executor.action original action
     * @param {Function<instance.web.Widget>} executor.widget function used to fetch the widget instance
     * @param {String} executor.klass CSS class to add on the dialog root, if action.target=new
     * @param {Function<instance.web.Widget, undefined>} executor.post_process cleanup called after a widget has been added as inner_widget
     * @param {Object} options
     * @return {*}
     */
    ir_actions_common: function(executor, options) {
        if (this.inner_widget && executor.action.target !== 'new') {
            if (this.getParent().has_uncommitted_changes()) {
                return $.Deferred().reject();
            } else if (options.clear_breadcrumbs) {
                this.clear_breadcrumbs();
            }
        }
        var widget = executor.widget();
        if (executor.action.target === 'new') {
            if (this.dialog_widget && !this.dialog_widget.isDestroyed()) {
                this.dialog_widget.destroy();
            }
            this.dialog_stop();
            this.dialog = new instance.web.Dialog(this, {
                dialogClass: executor.klass,
            });
            this.dialog.on("closing", null, options.on_close);
            this.dialog.init_dialog();
            this.dialog.dialog_title = executor.action.name;
            if (widget instanceof instance.web.ViewManager) {
                _.extend(widget.flags, {
                    $buttons: this.dialog.$buttons,
                    footer_to_buttons: true,
                });
            }
            this.dialog_widget = widget;
            this.dialog_widget.setParent(this.dialog);
            var initialized = this.dialog_widget.appendTo(this.dialog.$el);
            this.dialog.open();
            return initialized;
        } else  {
            this.dialog_stop();
            this.inner_action = executor.action;
            this.inner_widget = widget;
            executor.post_process(widget);
            return this.inner_widget.appendTo(this.$el);
        }
    },
    ir_actions_act_window: function (action, options) {
        var self = this;

        return this.ir_actions_common({
            widget: function () { return new instance.web.ViewManagerAction(self, action); },
            action: action,
            klass: 'oe_act_window',
            post_process: function (widget) { widget.add_breadcrumb(options.on_reverse_breadcrumb); }
        }, options);
    },
    ir_actions_client: function (action, options) {
        var self = this;
        var ClientWidget = instance.web.client_actions.get_object(action.tag);

        if (!(ClientWidget.prototype instanceof instance.web.Widget)) {
            var next;
            if (next = ClientWidget(this, action)) {
                return this.do_action(next, options);
            }
            return $.when();
        }

        return this.ir_actions_common({
            widget: function () { return new ClientWidget(self, action); },
            action: action,
            klass: 'oe_act_client',
            post_process: function(widget) {
                self.push_breadcrumb({
                    widget: widget,
                    title: action.name,
                    on_reverse_breadcrumb: options.on_reverse_breadcrumb,
                });
                if (action.tag !== 'reload') {
                    self.do_push_state({});
                }
            }
        }, options);
    },
    ir_actions_act_window_close: function (action, options) {
        if (!this.dialog) {
            options.on_close();
        }
        this.dialog_stop();
        return $.when();
    },
    ir_actions_server: function (action, options) {
        var self = this;
        this.rpc('/web/action/run', {
            action_id: action.id,
            context: action.context || {}
        }).done(function (action) {
            self.do_action(action, options)
        });
    },
    ir_actions_report_xml: function(action, options) {
        var self = this;
        instance.web.blockUI();
        return instance.web.pyeval.eval_domains_and_contexts({
            contexts: [action.context],
            domains: []
        }).then(function(res) {
            action = _.clone(action);
            action.context = res.context;
            var c = instance.webclient.crashmanager;
            return $.Deferred(function (d) {
                self.session.get_file({
                    url: '/web/report',
                    data: {action: JSON.stringify(action)},
                    complete: instance.web.unblockUI,
                    success: function(){
                        if (!self.dialog) {
                            options.on_close();
                        }
                        self.dialog_stop();
                        d.resolve();
                    },
                    error: function () {
                        c.rpc_error.apply(c, arguments);
                        d.reject();
                    }
                })
            });
        });
    },
    ir_actions_act_url: function (action) {
        window.open(action.url, action.target === 'self' ? '_self' : '_blank');
        return $.when();
    },
});

instance.web.ViewManager =  instance.web.Widget.extend({
    template: "ViewManager",
    init: function(parent, dataset, views, flags) {
        this._super(parent);
        this.url_states = {};
        this.model = dataset ? dataset.model : undefined;
        this.dataset = dataset;
        this.searchview = null;
        this.active_view = null;
        this.views_src = _.map(views, function(x) {
            if (x instanceof Array) {
                var View = instance.web.views.get_object(x[1], true);
                return {
                    view_id: x[0],
                    view_type: x[1],
                    label: View ? View.prototype.display_name : (void 'nope')
                };
            } else {
                return x;
            }
        });
        this.views = {};
        this.flags = flags || {};
        this.registry = instance.web.views;
        this.views_history = [];
    },
    /**
     * @returns {jQuery.Deferred} initial view loading promise
     */
    start: function() {
        this._super();
        var self = this;
        this.$el.find('.oe_view_manager_switch a').click(function() {
            self.switch_mode($(this).data('view-type'));
        }).tipsy();
        var views_ids = {};
        _.each(this.views_src, function(view) {
            self.views[view.view_type] = $.extend({}, view, {
                deferred : $.Deferred(),
                controller : null,
                options : _.extend({
                    $buttons : self.$el.find('.oe_view_manager_buttons'),
                    $sidebar : self.flags.sidebar ? self.$el.find('.oe_view_manager_sidebar') : undefined,
                    $pager : self.$el.find('.oe_view_manager_pager'),
                    action : self.action,
                    action_views_ids : views_ids
                }, self.flags, self.flags[view.view_type] || {}, view.options || {})
            });
            views_ids[view.view_type] = view.view_id;
        });
        if (this.flags.views_switcher === false) {
            this.$el.find('.oe_view_manager_switch').hide();
        }
        // If no default view defined, switch to the first one in sequence
        var default_view = this.flags.default_view || this.views_src[0].view_type;
        return this.switch_mode(default_view);
    },
    switch_mode: function(view_type, no_store, view_options) {
        var self = this;
        var view = this.views[view_type];
        var view_promise;
        var form = this.views['form'];
        if (!view || (form && form.controller && !form.controller.can_be_discarded())) {
            self.trigger('switch_mode', view_type, no_store, view_options);
            return $.Deferred().reject();
        }
        if (!no_store) {
            this.views_history.push(view_type);
        }
        this.active_view = view_type;

        if (!view.controller) {
            view_promise = this.do_create_view(view_type);
        } else if (this.searchview
                && self.flags.auto_search
                && view.controller.searchable !== false) {
            this.searchview.ready.done(this.searchview.do_search);
        }

        if (this.searchview) {
            this.searchview[(view.controller.searchable === false || this.searchview.hidden) ? 'hide' : 'show']();
        }

        this.$el.find('.oe_view_manager_switch a').parent().removeClass('active');
        this.$el
            .find('.oe_view_manager_switch a').filter('[data-view-type="' + view_type + '"]')
            .parent().addClass('active');

        return $.when(view_promise).done(function () {
            _.each(_.keys(self.views), function(view_name) {
                var controller = self.views[view_name].controller;
                if (controller) {
                    var container = self.$el.find(".oe_view_manager_view_" + view_name + ":first");
                    if (view_name === view_type) {
                        container.show();
                        controller.do_show(view_options || {});
                    } else {
                        container.hide();
                        controller.do_hide();
                    }
                }
            });
            self.trigger('switch_mode', view_type, no_store, view_options);
        });
    },
    do_create_view: function(view_type) {
        // Lazy loading of views
        var self = this;
        var view = this.views[view_type];
        var viewclass = this.registry.get_object(view_type);
        var options = _.clone(view.options);
        if (view_type === "form" && this.action && (this.action.target == 'new' || this.action.target == 'inline')) {
            options.initial_mode = 'edit';
        }
        var controller = new viewclass(this, this.dataset, view.view_id, options);

        controller.on('history_back', this, function() {
            var am = self.getParent();
            if (am && am.trigger) {
                return am.trigger('history_back');
            }
        });

        controller.on("change:title", this, function() {
            if (self.active_view === view_type) {
                self.set_title(controller.get('title'));
            }
        });

        if (view.embedded_view) {
            controller.set_embedded_view(view.embedded_view);
        }
        controller.on('switch_mode', self, this.switch_mode);
        controller.on('previous_view', self, this.prev_view);
        
        var container = this.$el.find(".oe_view_manager_view_" + view_type);
        var view_promise = controller.appendTo(container);
        this.views[view_type].controller = controller;
        this.views[view_type].deferred.resolve(view_type);
        return $.when(view_promise).done(function() {
            if (self.searchview
                    && self.flags.auto_search
                    && view.controller.searchable !== false) {
                self.searchview.ready.done(self.searchview.do_search);
            }
            self.trigger("controller_inited",view_type,controller);
        });
    },
    set_title: function(title) {
        this.$el.find('.oe_view_title_text:first').text(title);
    },
    add_breadcrumb: function(on_reverse_breadcrumb) {
        var self = this;
        var views = [this.active_view || this.views_src[0].view_type];
        this.on('switch_mode', self, function(mode) {
            var last = views.slice(-1)[0];
            if (mode !== last) {
                if (mode !== 'form') {
                    views.length = 0;
                }
                views.push(mode);
            }
        });
        this.getParent().push_breadcrumb({
            widget: this,
            action: this.action,
            show: function(index) {
                var view_to_select = views[index];
                var state = self.url_states[view_to_select];
                self.do_push_state(state || {});
                $.when(self.switch_mode(view_to_select)).done(function() {
                    self.$el.show();
                });
            },
            get_title: function() {
                var id;
                var currentIndex;
                _.each(self.getParent().breadcrumbs, function(bc, i) {
                    if (bc.widget === self) {
                        currentIndex = i;
                    }
                });
                var next = self.getParent().breadcrumbs.slice(currentIndex + 1)[0];
                var titles = _.map(views, function(v) {
                    var controller = self.views[v].controller;
                    if (v === 'form') {
                        id = controller.datarecord.id;
                    }
                    return controller.get('title');
                });
                if (next && next.action && next.action.res_id && self.dataset &&
                    self.active_view === 'form' && self.dataset.model === next.action.res_model && id === next.action.res_id) {
                    // If the current active view is a formview and the next item in the breadcrumbs
                    // is an action on same object (model / res_id), then we omit the current formview's title
                    titles.pop();
                }
                return titles;
            },
            on_reverse_breadcrumb: on_reverse_breadcrumb,
        });
    },
    /**
     * Returns to the view preceding the caller view in this manager's
     * navigation history (the navigation history is appended to via
     * switch_mode)
     *
     * @param {Object} [options]
     * @param {Boolean} [options.created=false] resource was created
     * @param {String} [options.default=null] view to switch to if no previous view
     * @returns {$.Deferred} switching end signal
     */
    prev_view: function (options) {
        options = options || {};
        var current_view = this.views_history.pop();
        var previous_view = this.views_history[this.views_history.length - 1] || options['default'];
        if (options.created && current_view === 'form' && previous_view === 'list') {
            // APR special case: "If creation mode from list (and only from a list),
            // after saving, go to page view (don't come back in list)"
            return this.switch_mode('form');
        } else if (options.created && !previous_view && this.action && this.action.flags.default_view === 'form') {
            // APR special case: "If creation from dashboard, we have no previous view
            return this.switch_mode('form');
        }
        return this.switch_mode(previous_view, true);
    },
    /**
     * Sets up the current viewmanager's search view.
     *
     * @param {Number|false} view_id the view to use or false for a default one
     * @returns {jQuery.Deferred} search view startup deferred
     */
    setup_search_view: function(view_id, search_defaults) {
        var self = this;
        if (this.searchview) {
            this.searchview.destroy();
        }
        this.searchview = new instance.web.SearchView(this, this.dataset, view_id, search_defaults, this.flags.search_view === false);

        this.searchview.on('search_data', self, this.do_searchview_search);
        return this.searchview.appendTo(this.$el.find(".oe_view_manager_view_search"));
    },
    do_searchview_search: function(domains, contexts, groupbys) {
        var self = this,
            controller = this.views[this.active_view].controller,
            action_context = this.action.context || {};
        instance.web.pyeval.eval_domains_and_contexts({
            domains: [this.action.domain || []].concat(domains || []),
            contexts: [action_context].concat(contexts || []),
            group_by_seq: groupbys || []
        }).done(function (results) {
            self.dataset._model = new instance.web.Model(
                self.dataset.model, results.context, results.domain);
            var groupby = results.group_by.length
                        ? results.group_by
                        : action_context.group_by;
            if (_.isString(groupby)) {
                groupby = [groupby];
            }
            controller.do_search(results.domain, results.context, groupby || []);
        });
    },
    /**
     * Called when one of the view want to execute an action
     */
    on_action: function(action) {
    },
    on_create: function() {
    },
    on_remove: function() {
    },
    on_edit: function() {
    },
    /**
     * Called by children view after executing an action
     */
    on_action_executed: function () {
    },
});

instance.web.ViewManagerAction = instance.web.ViewManager.extend({
    template:"ViewManagerAction",
    /**
     * @constructs instance.web.ViewManagerAction
     * @extends instance.web.ViewManager
     *
     * @param {instance.web.ActionManager} parent parent object/widget
     * @param {Object} action descriptor for the action this viewmanager needs to manage its views.
     */
    init: function(parent, action) {
        // dataset initialization will take the session from ``this``, so if we
        // do not have it yet (and we don't, because we've not called our own
        // ``_super()``) rpc requests will blow up.
        var flags = action.flags || {};
        if (!('auto_search' in flags)) {
            flags.auto_search = action.auto_search !== false;
        }
        if (action.res_model == 'board.board' && action.view_mode === 'form') {
            // Special case for Dashboards
            _.extend(flags, {
                views_switcher : false,
                display_title : false,
                search_view : false,
                pager : false,
                sidebar : false,
                action_buttons : false
            });
        }
        this._super(parent, null, action.views, flags);
        this.session = parent.session;
        this.action = action;
        var dataset = new instance.web.DataSetSearch(this, action.res_model, action.context, action.domain);
        if (action.res_id) {
            dataset.ids.push(action.res_id);
            dataset.index = 0;
        }
        this.dataset = dataset;

        // setup storage for session-wise menu hiding
        if (this.session.hidden_menutips) {
            return;
        }
        this.session.hidden_menutips = {};
    },
    /**
     * Initializes the ViewManagerAction: sets up the searchview (if the
     * searchview is enabled in the manager's action flags), calls into the
     * parent to initialize the primary view and (if the VMA has a searchview)
     * launches an initial search after both views are done rendering.
     */
    start: function() {
        var self = this,
            searchview_loaded,
            search_defaults = {};
        _.each(this.action.context, function (value, key) {
            var match = /^search_default_(.*)$/.exec(key);
            if (match) {
                search_defaults[match[1]] = value;
            }
        });
        // init search view
        var searchview_id = this.action['search_view_id'] && this.action['search_view_id'][0];

        searchview_loaded = this.setup_search_view(searchview_id || false, search_defaults);

        var main_view_loaded = this._super();

        var manager_ready = $.when(searchview_loaded, main_view_loaded);

        this.$el.find('.oe_debug_view').change(this.on_debug_changed);
        this.$el.addClass("oe_view_manager_" + (this.action.target || 'current'));
        return manager_ready;
    },
    on_debug_changed: function (evt) {
        var self = this,
            $sel = $(evt.currentTarget),
            $option = $sel.find('option:selected'),
            val = $sel.val(),
            current_view = this.views[this.active_view].controller;
        switch (val) {
            case 'fvg':
                var dialog = new instance.web.Dialog(this, { title: _t("Fields View Get"), width: '95%' }).open();
                $('<pre>').text(instance.web.json_node_to_xml(current_view.fields_view.arch, true)).appendTo(dialog.$el);
                break;
            case 'tests':
                this.do_action({
                    name: "JS Tests",
                    target: 'new',
                    type : 'ir.actions.act_url',
                    url: '/web/tests?mod=*'
                });
                break;
            case 'perm_read':
                var ids = current_view.get_selected_ids();
                if (ids.length === 1) {
                    this.dataset.call('perm_read', [ids]).done(function(result) {
                        var dialog = new instance.web.Dialog(this, {
                            title: _.str.sprintf(_t("View Log (%s)"), self.dataset.model),
                            width: 400
                        }, QWeb.render('ViewManagerDebugViewLog', {
                            perm : result[0],
                            format : instance.web.format_value
                        })).open();
                    });
                }
                break;
            case 'toggle_layout_outline':
                current_view.rendering_engine.toggle_layout_debugging();
                break;
            case 'translate':
                this.do_action({
                    name: "Technical Translation",
                    res_model : 'ir.translation',
                    domain : [['type', '!=', 'object'], '|', ['name', '=', this.dataset.model], ['name', 'ilike', this.dataset.model + ',']],
                    views: [[false, 'list'], [false, 'form']],
                    type : 'ir.actions.act_window',
                    view_type : "list",
                    view_mode : "list"
                });
                break;
            case 'fields':
                this.dataset.call('fields_get', [false, {}]).done(function (fields) {
                    var $root = $('<dl>');
                    _(fields).each(function (attributes, name) {
                        $root.append($('<dt>').append($('<h4>').text(name)));
                        var $attrs = $('<dl>').appendTo($('<dd>').appendTo($root));
                        _(attributes).each(function (def, name) {
                            if (def instanceof Object) {
                                def = JSON.stringify(def);
                            }
                            $attrs
                                .append($('<dt>').text(name))
                                .append($('<dd style="white-space: pre-wrap;">').text(def));
                        });
                    });
                    new instance.web.Dialog(self, {
                        title: _.str.sprintf(_t("Model %s fields"),
                                             self.dataset.model),
                        width: '95%'}, $root).open();
                });
                break;
            case 'edit_workflow':
                return this.do_action({
                    res_model : 'workflow',
                    domain : [['osv', '=', this.dataset.model]],
                    views: [[false, 'list'], [false, 'form'], [false, 'diagram']],
                    type : 'ir.actions.act_window',
                    view_type : 'list',
                    view_mode : 'list'
                });
                break;
            case 'edit':
                this.do_edit_resource($option.data('model'), $option.data('id'), { name : $option.text() });
                break;
            case 'manage_filters':
                this.do_action({
                    res_model: 'ir.filters',
                    views: [[false, 'list'], [false, 'form']],
                    type: 'ir.actions.act_window',
                    context: {
                        search_default_my_filters: true,
                        search_default_model_id: this.dataset.model
                    }
                });
                break;
            case 'print_workflow':
                if (current_view.get_selected_ids  && current_view.get_selected_ids().length == 1) {
                    instance.web.blockUI();
                    var action = {
                        context: { active_ids: current_view.get_selected_ids() },
                        report_name: "workflow.instance.graph",
                        datas: {
                            model: this.dataset.model,
                            id: current_view.get_selected_ids()[0],
                            nested: true,
                        }
                    };
                    this.session.get_file({
                        url: '/web/report',
                        data: {action: JSON.stringify(action)},
                        complete: instance.web.unblockUI
                    });
                }
                break;
            default:
                if (val) {
                    console.log("No debug handler for ", val);
                }
        }
        evt.currentTarget.selectedIndex = 0;
    },
    do_edit_resource: function(model, id, action) {
        var action = _.extend({
            res_model : model,
            res_id : id,
            type : 'ir.actions.act_window',
            view_type : 'form',
            view_mode : 'form',
            views : [[false, 'form']],
            target : 'new',
            flags : {
                action_buttons : true,
                form : {
                    resize_textareas : true
                }
            }
        }, action || {});
        this.do_action(action);
    },
    switch_mode: function (view_type, no_store, options) {
        var self = this;

        return $.when(this._super.apply(this, arguments)).done(function () {
            var controller = self.views[self.active_view].controller;
            self.$el.find('.oe_debug_view').html(QWeb.render('ViewManagerDebug', {
                view: controller,
                view_manager: self
            }));
            self.set_title();
        });
    },
    do_create_view: function(view_type) {
        var r = this._super.apply(this, arguments);
        var view = this.views[view_type].controller;
        view.set({ 'title': this.action.name });
        return r;
    },
    get_action_manager: function() {
        var cur = this;
        while (cur = cur.getParent()) {
            if (cur instanceof instance.web.ActionManager) {
                return cur;
            }
        }
        return undefined;
    },
    set_title: function(title) {
        this.$el.find('.oe_breadcrumb_title:first').html(this.get_action_manager().get_title());
    },
    do_push_state: function(state) {
        if (this.getParent() && this.getParent().do_push_state) {
            state["view_type"] = this.active_view;
            this.url_states[this.active_view] = state;
            this.getParent().do_push_state(state);
        }
    },
    do_load_state: function(state, warm) {
        var self = this,
            defs = [];
        if (state.view_type && state.view_type !== this.active_view) {
            defs.push(
                this.views[this.active_view].deferred.then(function() {
                    return self.switch_mode(state.view_type, true);
                })
            );
        } 

        $.when(defs).done(function() {
            self.views[self.active_view].controller.do_load_state(state, warm);
        });
    },
});

instance.web.Sidebar = instance.web.Widget.extend({
    init: function(parent) {
        var self = this;
        this._super(parent);
        var view = this.getParent();
        this.sections = [
            { 'name' : 'print', 'label' : _t('Print'), },
            { 'name' : 'other', 'label' : _t('More'), }
        ];
        this.items = {
            'print' : [],
            'other' : []
        };
        this.fileupload_id = _.uniqueId('oe_fileupload');
        $(window).on(this.fileupload_id, function() {
            var args = [].slice.call(arguments).slice(1);
            if (args[0] && args[0].error) {
                alert(args[0].error);
            } else {
                self.do_attachement_update(self.dataset, self.model_id);
            }
            instance.web.unblockUI();
        });
    },
    start: function() {
        var self = this;
        this._super(this);
        this.redraw();
        this.$el.on('click','.oe_dropdown_menu li a', function(event) {
            var section = $(this).data('section');
            var index = $(this).data('index');
            var item = self.items[section][index];
            if (item.callback) {
                item.callback.apply(self, [item]);
            } else if (item.action) {
                self.on_item_action_clicked(item);
            } else if (item.url) {
                return true;
            }
            event.preventDefault();
        });
    },
    redraw: function() {
        var self = this;
        self.$el.html(QWeb.render('Sidebar', {widget: self}));

        // Hides Sidebar sections when item list is empty
        this.$('.oe_form_dropdown_section').each(function() {
            $(this).toggle(!!$(this).find('li').length);
        });
    },
    /**
     * For each item added to the section:
     *
     * ``label``
     *     will be used as the item's name in the sidebar, can be html
     *
     * ``action``
     *     descriptor for the action which will be executed, ``action`` and
     *     ``callback`` should be exclusive
     *
     * ``callback``
     *     function to call when the item is clicked in the sidebar, called
     *     with the item descriptor as its first argument (so information
     *     can be stored as additional keys on the object passed to
     *     ``add_items``)
     *
     * ``classname`` (optional)
     *     ``@class`` set on the sidebar serialization of the item
     *
     * ``title`` (optional)
     *     will be set as the item's ``@title`` (tooltip)
     *
     * @param {String} section_code
     * @param {Array<{label, action | callback[, classname][, title]}>} items
     */
    add_items: function(section_code, items) {
        var self = this;
        if (items) {
            this.items[section_code].push.apply(this.items[section_code],items);
            this.redraw();
        }
    },
    add_toolbar: function(toolbar) {
        var self = this;
        _.each(['print','action','relate'], function(type) {
            var items = toolbar[type];
            if (items) {
                for (var i = 0; i < items.length; i++) {
                    items[i] = {
                        label: items[i]['name'],
                        action: items[i],
                        classname: 'oe_sidebar_' + type
                    }
                }
                self.add_items(type=='print' ? 'print' : 'other', items);
            }
        });
    },
    on_item_action_clicked: function(item) {
        var self = this;
        self.getParent().sidebar_context().done(function (context) {
            var ids = self.getParent().get_selected_ids();
            if (ids.length == 0) {
                instance.web.dialog($("<div />").text(_t("You must choose at least one record.")), { title: _t("Warning"), modal: true });
                return false;
            }
            var c = instance.web.pyeval.eval('context',
                new instance.web.CompoundContext({
                    active_id: ids[0],
                    active_ids: ids,
                    active_model: self.getParent().dataset.model
                }, context));
            self.rpc("/web/action/load", {
                action_id: item.action.id,
                context: c
            }).done(function(result) {
                result.context = new instance.web.CompoundContext(
                    c, result.context);
                result.flags = result.flags || {};
                result.flags.new_window = true;
                self.do_action(result, {
                    on_close: function() {
                        // reload view
                        self.getParent().reload();
                    },
                });
            });
        });
    },
    do_attachement_update: function(dataset, model_id) {
        this.dataset = dataset;
        this.model_id = model_id;
        if (!model_id) {
            this.on_attachments_loaded([]);
        } else {
            var dom = [ ['res_model', '=', dataset.model], ['res_id', '=', model_id], ['type', 'in', ['binary', 'url']] ];
            var ds = new instance.web.DataSetSearch(this, 'ir.attachment', dataset.get_context(), dom);
            ds.read_slice(['name', 'url', 'type'], {}).done(this.on_attachments_loaded);
        }
    },
    on_attachments_loaded: function(attachments) {
        var self = this;
        var items = [];
        var prefix = this.session.url('/web/binary/saveas', {model: 'ir.attachment', field: 'datas', filename_field: 'name'});
        _.each(attachments,function(a) {
            a.label = a.name;
            if(a.type === "binary") {
                a.url = prefix  + '&id=' + a.id + '&t=' + (new Date().getTime());
            }
        });
        self.items['files'] = attachments;
        self.redraw();
        this.$('.oe_sidebar_add_attachment .oe_form_binary_file').change(this.on_attachment_changed);
        this.$el.find('.oe_sidebar_delete_item').click(this.on_attachment_delete);
    },
    on_attachment_changed: function(e) {
        var $e = $(e.target);
        if ($e.val() !== '') {
            this.$el.find('form.oe_form_binary_form').submit();
            $e.parent().find('input[type=file]').prop('disabled', true);
            $e.parent().find('button').prop('disabled', true).find('img, span').toggle();
            this.$('.oe_sidebar_add_attachment span').text(_t('Uploading...'));
            instance.web.blockUI();
        }
    },
    on_attachment_delete: function(e) {
        e.preventDefault();
        e.stopPropagation();
        var self = this;
        var $e = $(e.currentTarget);
        if (confirm(_t("Do you really want to delete this attachment ?"))) {
            (new instance.web.DataSet(this, 'ir.attachment')).unlink([parseInt($e.attr('data-id'), 10)]).done(function() {
                self.do_attachement_update(self.dataset, self.model_id);
            });
        }
    }
});

instance.web.View = instance.web.Widget.extend({
    // name displayed in view switchers
    display_name: '',
    /**
     * Define a view type for each view to allow automatic call to fields_view_get.
     */
    view_type: undefined,
    init: function(parent, dataset, view_id, options) {
        this._super(parent);
        this.dataset = dataset;
        this.view_id = view_id;
        this.set_default_options(options);
    },
    start: function () {
        return this.load_view();
    },
    load_view: function(context) {
        var self = this;
        var view_loaded;
        if (this.embedded_view) {
            view_loaded = $.Deferred();
            $.async_when().done(function() {
                view_loaded.resolve(self.embedded_view);
            });
        } else {
            if (! this.view_type)
                console.warn("view_type is not defined", this);
            view_loaded = this.rpc("/web/view/load", {
                "model": this.dataset.model,
                "view_id": this.view_id,
                "view_type": this.view_type,
                toolbar: !!this.options.$sidebar,
                context: instance.web.pyeval.eval(
                    'context', this.dataset.get_context(context))
            });
        }
        return view_loaded.then(function(r) {
            self.trigger('view_loaded', r);
            // add css classes that reflect the (absence of) access rights
            self.$el.addClass('oe_view')
                .toggleClass('oe_cannot_create', !self.is_action_enabled('create'))
                .toggleClass('oe_cannot_edit', !self.is_action_enabled('edit'))
                .toggleClass('oe_cannot_delete', !self.is_action_enabled('delete'));
        });
    },
    set_default_options: function(options) {
        this.options = options || {};
        _.defaults(this.options, {
            // All possible views options should be defaulted here
            $sidebar: null,
            sidebar_id: null,
            action: null,
            action_views_ids: {}
        });
    },
    /**
     * Fetches and executes the action identified by ``action_data``.
     *
     * @param {Object} action_data the action descriptor data
     * @param {String} action_data.name the action name, used to uniquely identify the action to find and execute it
     * @param {String} [action_data.special=null] special action handlers (currently: only ``'cancel'``)
     * @param {String} [action_data.type='workflow'] the action type, if present, one of ``'object'``, ``'action'`` or ``'workflow'``
     * @param {Object} [action_data.context=null] additional action context, to add to the current context
     * @param {instance.web.DataSet} dataset a dataset object used to communicate with the server
     * @param {Object} [record_id] the identifier of the object on which the action is to be applied
     * @param {Function} on_closed callback to execute when dialog is closed or when the action does not generate any result (no new action)
     */
    do_execute_action: function (action_data, dataset, record_id, on_closed) {
        var self = this;
        var result_handler = function () {
            if (on_closed) { on_closed.apply(null, arguments); }
            if (self.getParent() && self.getParent().on_action_executed) {
                return self.getParent().on_action_executed.apply(null, arguments);
            }
        };
        var context = new instance.web.CompoundContext(dataset.get_context(), action_data.context || {});

        var handler = function (action) {
            if (action && action.constructor == Object) {
                var ncontext = new instance.web.CompoundContext(context);
                if (record_id) {
                    ncontext.add({
                        active_id: record_id,
                        active_ids: [record_id],
                        active_model: dataset.model
                    });
                }
                ncontext.add(action.context || {});
                action.context = ncontext;
                return self.do_action(action, {
                    on_close: result_handler,
                });
            } else {
                self.do_action({"type":"ir.actions.act_window_close"});
                return result_handler();
            }
        };

        if (action_data.special === 'cancel') {
            return handler({"type":"ir.actions.act_window_close"});
        } else if (action_data.type=="object") {
            var args = [[record_id]], additional_args = [];
            if (action_data.args) {
                try {
                    // Warning: quotes and double quotes problem due to json and xml clash
                    // Maybe we should force escaping in xml or do a better parse of the args array
                    additional_args = JSON.parse(action_data.args.replace(/'/g, '"'));
                    args = args.concat(additional_args);
                } catch(e) {
                    console.error("Could not JSON.parse arguments", action_data.args);
                }
            }
            args.push(context);
            return dataset.call_button(action_data.name, args).then(handler);
        } else if (action_data.type=="action") {
            return this.rpc('/web/action/load', {
                action_id: action_data.name,
                context: instance.web.pyeval.eval('context', context),
                do_not_eval: true
            }).then(handler);
        } else  {
            return dataset.exec_workflow(record_id, action_data.name).then(handler);
        }
    },
    /**
     * Directly set a view to use instead of calling fields_view_get. This method must
     * be called before start(). When an embedded view is set, underlying implementations
     * of instance.web.View must use the provided view instead of any other one.
     *
     * @param embedded_view A view.
     */
    set_embedded_view: function(embedded_view) {
        this.embedded_view = embedded_view;
    },
    do_show: function () {
        this.$el.show();
    },
    do_hide: function () {
        this.$el.hide();
    },
    is_active: function () {
        var manager = this.getParent();
        return !manager || !manager.active_view
             || manager.views[manager.active_view].controller === this;
    }, /**
     * Wraps fn to only call it if the current view is the active one. If the
     * current view is not active, doesn't call fn.
     *
     * fn can not return anything, as a non-call to fn can't return anything
     * either
     *
     * @param {Function} fn function to wrap in the active guard
     */
    guard_active: function (fn) {
        var self = this;
        return function () {
            if (self.is_active()) {
                fn.apply(self, arguments);
            }
        }
    },
    do_push_state: function(state) {
        if (this.getParent() && this.getParent().do_push_state) {
            this.getParent().do_push_state(state);
        }
    },
    do_load_state: function(state, warm) {
    },
    /**
     * Switches to a specific view type
     */
    do_switch_view: function() { 
        this.trigger.apply(this, ['switch_mode'].concat(_.toArray(arguments)));
    },
    /**
     * Cancels the switch to the current view, switches to the previous one
     *
     * @param {Object} [options]
     * @param {Boolean} [options.created=false] resource was created
     * @param {String} [options.default=null] view to switch to if no previous view
     */

    do_search: function(view) {
    },
    on_sidebar_export: function() {
        new instance.web.DataExport(this, this.dataset).open();
    },
    sidebar_context: function () {
        return $.when();
    },
    /**
     * Asks the view to reload itself, if the reloading is asynchronous should
     * return a {$.Deferred} indicating when the reloading is done.
     */
    reload: function () {
        return $.when();
    },
    /**
     * Return whether the user can perform the action ('create', 'edit', 'delete') in this view.
     * An action is disabled by setting the corresponding attribute in the view's main element,
     * like: <form string="" create="false" edit="false" delete="false">
     */
    is_action_enabled: function(action) {
        var attrs = this.fields_view.arch.attrs;
        return (action in attrs) ? JSON.parse(attrs[action]) : true;
    }
});

instance.web.xml_to_json = function(node) {
    switch (node.nodeType) {
        case 3:
        case 4:
            return node.data;
        break;
        case 1:
            var attrs = $(node).getAttributes();
            _.each(['domain', 'filter_domain', 'context', 'default_get'], function(key) {
                if (attrs[key]) {
                    try {
                        attrs[key] = JSON.parse(attrs[key]);
                    } catch(e) { }
                }
            });
            return {
                tag: node.tagName.toLowerCase(),
                attrs: attrs,
                children: _.map(node.childNodes, instance.web.xml_to_json)
            }
    }
}
instance.web.json_node_to_xml = function(node, human_readable, indent) {
    // For debugging purpose, this function will convert a json node back to xml
    indent = indent || 0;
    var sindent = (human_readable ? (new Array(indent + 1).join('\t')) : ''),
        r = sindent + '<' + node.tag,
        cr = human_readable ? '\n' : '';

    if (typeof(node) === 'string') {
        return sindent + node;
    } else if (typeof(node.tag) !== 'string' || !node.children instanceof Array || !node.attrs instanceof Object) {
        throw new Error(
            _.str.sprintf("Node [%s] is not a JSONified XML node",
                          JSON.stringify(node)));
    }
    for (var attr in node.attrs) {
        var vattr = node.attrs[attr];
        if (typeof(vattr) !== 'string') {
            // domains, ...
            vattr = JSON.stringify(vattr);
        }
        vattr = vattr.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        if (human_readable) {
            vattr = vattr.replace(/&quot;/g, "'");
        }
        r += ' ' + attr + '="' + vattr + '"';
    }
    if (node.children && node.children.length) {
        r += '>' + cr;
        var childs = [];
        for (var i = 0, ii = node.children.length; i < ii; i++) {
            childs.push(instance.web.json_node_to_xml(node.children[i], human_readable, indent + 1));
        }
        r += childs.join(cr);
        r += cr + sindent + '</' + node.tag + '>';
        return r;
    } else {
        return r + '/>';
    }
};
instance.web.xml_to_str = function(node) {
    if (window.XMLSerializer) {
        return (new XMLSerializer()).serializeToString(node);
    } else if (window.ActiveXObject) {
        return node.xml;
    } else {
        throw new Error("Could not serialize XML");
    }
};
instance.web.str_to_xml = function(s) {
    if (window.DOMParser) {
        var dp = new DOMParser();
        var r = dp.parseFromString(s, "text/xml");
        if (r.body && r.body.firstChild && r.body.firstChild.nodeName == 'parsererror') {
            throw new Error("Could not parse string to xml");
        }
        return r;
    }
    var xDoc;
    try {
        xDoc = new ActiveXObject("MSXML2.DOMDocument");
    } catch (e) {
        throw new Error("Could not find a DOM Parser: " + e.message);
    }
    xDoc.async = false;
    xDoc.preserveWhiteSpace = true;
    xDoc.loadXML(s);
    return xDoc;
}

/**
 * Registry for all the main views
 */
instance.web.views = new instance.web.Registry();

};

// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax:
