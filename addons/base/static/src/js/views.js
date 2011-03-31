/*---------------------------------------------------------
 * OpenERP base library
 *---------------------------------------------------------*/

openerp.base.views = function(openerp) {

openerp.base.ActionManager = openerp.base.Controller.extend({
// process all kind of actions
    init: function(session, element_id) {
        this._super(session, element_id);
        this.viewmanager = null;
    },
    /**
     * Process an action
     * Supported actions: act_window
     */
    do_action: function(action) {
        // instantiate the right controllers by understanding the action
        if(action.type == "ir.actions.act_window") {
            this.viewmanager = new openerp.base.ViewManager(this.session,this.element_id);
            this.viewmanager.do_action_window(action);
            this.viewmanager.start();
        }
    }
});

openerp.base.ViewManager =  openerp.base.Controller.extend({
// This will be ViewManager Abstract/Common
    init: function(session, element_id) {
        this._super(session, element_id);
        this.action = null;
        this.dataset = null;
        this.searchview_id = false;
        this.searchview = null;
        this.search_visible = true;
        this.active_view = null;
        this.auto_search = false;
        // this.views = { "list": { "view_id":1234, "controller": instance} }
        this.views = {};
    },
    start: function() {
    },
    on_mode_switch: function(view_type) {
        this.active_view = view_type;
        var view = this.views[view_type];
        if (!view.controller) {
            // Lazy loading of views
            var controller;
            switch (view_type) {
                case 'tree':
                    controller = new openerp.base.ListView(this.session, this.element_id + "_view_tree", this.dataset, view.view_id);
                    break;
                case 'form':
                    controller = new openerp.base.FormView(this.session, this.element_id + "_view_form", this.dataset, view.view_id);
                    break;
                case 'calendar':
                    controller = new openerp.base.CalendarView(this.session, this.element_id + "_view_calendar", this.dataset, view.view_id);
                    break;
                case 'gantt':
                    controller = new openerp.base.GanttView(this.session, this.element_id + "_view_gantt", this.dataset, view.view_id);
                    break;
            }
            controller.start();
            this.views[view_type].controller = controller;
            if (this.auto_search) {
                this.searchview.on_loaded.add_last(this.searchview.do_search);
                this.auto_search = false;
            }
        }
        for (var i in this.views) {
            if (this.views[i].controller) {
               this.views[i].controller.$element.toggle(i === view_type);
            }
        }
    },
    /**
     * Extract search view defaults from the current action's context.
     *
     * These defaults are of the form {search_default_*: value}
     *
     * @returns {Object} a clean defaults mapping of {field_name: value}
     */
    search_defaults: function () {
        var defaults = {};
        _.each(this.action.context, function (value, key) {
            var match = /^search_default_(.*)$/.exec(key);
            if (match) {
                defaults[match[1]] = value;
            }
        });
        return defaults;
    },
    do_action_window: function(action) {
        var self = this;
        var prefix_id = "#" + this.element_id;
        this.action = action;
        this.dataset = new openerp.base.DataSet(this.session, action.res_model);
        this.dataset.start();

        this.$element.html(QWeb.render("ViewManager", {"prefix": this.element_id, views: action.views}));

        this.searchview_id = false;
        if (this.search_visible && action.search_view_id) {
            this.searchview_id = action.search_view_id[0];
            var searchview = this.searchview = new openerp.base.SearchView(
                    this.session, this.element_id + "_search",
                    this.dataset, this.searchview_id,
                    this.search_defaults());
            searchview.on_search.add(function() {
                self.views[self.active_view].controller.do_search.apply(self, arguments);
            });
            searchview.start();

            this.auto_search = action.auto_search;
        }
        this.$element.find('.views_switchers button').click(function() {
            self.on_mode_switch($(this).data('view-type'));
        });
        _.each(action.views, function(view) {
            self.views[view[1]] = { view_id: view[0], controller: null };
        });
        // switch to the first one in sequence
        this.on_mode_switch(action.views[0][1]);
    },
    // create when root, also add to parent when o2m
    on_create: function() {
    },
    on_remove: function() {
    },
    on_edit: function() {
    }
});

openerp.base.ViewManagerRoot = openerp.base.Controller.extend({
// Extends view manager
});

openerp.base.ViewManagerUsedAsAMany2One = openerp.base.Controller.extend({
// Extends view manager
});

openerp.base.BaseWidget = openerp.base.Controller.extend({
    /**
     * The name of the QWeb template that will be used for rendering. Must be redifined
     * in subclasses or the render() method can not be used.
     * 
     * @type string
     */
    template: null,
    /**
     * The prefix used to generate an id automatically. Should be redifined in subclasses.
     * If it is not defined, a default identifier will be used.
     * 
     * @type string
     */
    identifier_prefix: 'generic-identifier',
    /**
 * Base class for widgets. Handle rendering (based on a QWeb template), identifier
 * generation, parenting and destruction of the widget.
     * Contructor. Also initialize the identifier.
     * 
     * @params {openerp.base.search.BaseWidget} parent The parent widget.
     */
    init: function (parent) {
        this.children = [];
        this.parent = null;
        this.set_parent(parent);
        this.make_id(this.identifier_prefix);
    },
    /**
     * Sets and returns a globally unique identifier for the widget.
     *
     * If a prefix is appended, the identifier will be appended to it.
     *
     * @params sections prefix sections, empty/falsy sections will be removed
     */
    make_id: function () {
        this.element_id = _.uniqueId(_.toArray(arguments).join('_'));
        return this.element_id;
    },
    /**
     * "Starts" the widgets. Called at the end of the rendering, this allows
     * to get a jQuery object referring to the DOM ($element attribute).
     */
    start: function () {
        this._super();
        var tmp = document.getElementById(this.element_id);
        this.$element = tmp ? $(tmp) : null;
    },
    /**
     * "Stops" the widgets. Called when the view destroys itself, this
     * lets the widgets clean up after themselves.
     */
    stop: function () {
        var tmp_children = this.children;
        this.children = [];
        _.each(tmp_children, function(x) {
            x.stop();
        });
        if(this.$element != null) {
            this.$element.remove();
        }
        this.set_parent(null);
        this._super();
    },
    /**
     * Set the parent of this component, also unregister the previous parent if there
     * was one.
     * 
     * @param {openerp.base.BaseWidget} parent The new parent.
     */
    set_parent: function(parent) {
        if(this.parent) {
            this.parent.children = _.without(this.parent.children, this);
        }
        this.parent = parent;
        if(this.parent) {
            parent.children.push(this);
        }
    },
    /**
     * Render the widget. This.template must be defined.
     * The content of the current object is passed as context to the template.
     * 
     * @param {object} additional Additional context arguments to pass to the template.
     */
    render: function (additional) {
        return QWeb.render(this.template, _.extend({}, this, additional != null ? additional : {}));
    }
});

openerp.base.CalendarView = openerp.base.Controller.extend({
// Dhtmlx scheduler ?
});

openerp.base.GanttView = openerp.base.Controller.extend({
// Dhtmlx gantt ?
});

openerp.base.DiagramView = openerp.base.Controller.extend({
// 
});

openerp.base.GraphView = openerp.base.Controller.extend({
});

openerp.base.ProcessView = openerp.base.Controller.extend({
});

openerp.base.HelpView = openerp.base.Controller.extend({
});

};

// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax:
