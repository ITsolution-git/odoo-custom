
(function() {

function declare($, _, QWeb2) {
var openerp = {};
openerp.web = {};

    /**
 * Improved John Resig's inheritance, based on:
 *
 * Simple JavaScript Inheritance
 * By John Resig http://ejohn.org/
 * MIT Licensed.
 *
 * Adds "include()"
 *
 * Defines The Class object. That object can be used to define and inherit classes using
 * the extend() method.
 *
 * Example:
 *
 * var Person = openerp.web.Class.extend({
 *  init: function(isDancing){
 *     this.dancing = isDancing;
 *   },
 *   dance: function(){
 *     return this.dancing;
 *   }
 * });
 *
 * The init() method act as a constructor. This class can be instancied this way:
 *
 * var person = new Person(true);
 * person.dance();
 *
 * The Person class can also be extended again:
 *
 * var Ninja = Person.extend({
 *   init: function(){
 *     this._super( false );
 *   },
 *   dance: function(){
 *     // Call the inherited version of dance()
 *     return this._super();
 *   },
 *   swingSword: function(){
 *     return true;
 *   }
 * });
 *
 * When extending a class, each re-defined method can use this._super() to call the previous
 * implementation of that method.
 */
(function() {
    var initializing = false,
        fnTest = /xyz/.test(function(){xyz();}) ? /\b_super\b/ : /.*/;
    // The web Class implementation (does nothing)
    openerp.web.Class = function(){};

    /**
     * Subclass an existing class
     *
     * @param {Object} prop class-level properties (class attributes and instance methods) to set on the new class
     */
    openerp.web.Class.extend = function() {
        var _super = this.prototype;
        // Support mixins arguments
        var args = _.toArray(arguments);
        args.unshift({});
        var prop = _.extend.apply(_,args);

        // Instantiate a web class (but only create the instance,
        // don't run the init constructor)
        initializing = true;
        var prototype = new this();
        initializing = false;

        // Copy the properties over onto the new prototype
        _.each(prop, function(val, name) {
            // Check if we're overwriting an existing function
            prototype[name] = typeof prop[name] == "function" &&
                              fnTest.test(prop[name]) ?
                    (function(name, fn) {
                        return function() {
                            var tmp = this._super;

                            // Add a new ._super() method that is the same
                            // method but on the super-class
                            this._super = _super[name];

                            // The method only need to be bound temporarily, so
                            // we remove it when we're done executing
                            var ret = fn.apply(this, arguments);
                            this._super = tmp;

                            return ret;
                        };
                    })(name, prop[name]) :
                    prop[name];
        });

        // The dummy class constructor
        function Class() {
            if(this.constructor !== openerp.web.Class){
                throw new Error("You can only instanciate objects with the 'new' operator");
            }
            // All construction is actually done in the init method
            if (!initializing && this.init) {
                var ret = this.init.apply(this, arguments);
                if (ret) { return ret; }
            }
            return this;
        }
        Class.include = function (properties) {
            _.each(properties, function(val, name) {
                if (typeof properties[name] !== 'function'
                        || !fnTest.test(properties[name])) {
                    prototype[name] = properties[name];
                } else if (typeof prototype[name] === 'function'
                           && prototype.hasOwnProperty(name)) {
                    prototype[name] = (function (name, fn, previous) {
                        return function () {
                            var tmp = this._super;
                            this._super = previous;
                            var ret = fn.apply(this, arguments);
                            this._super = tmp;
                            return ret;
                        };
                    })(name, properties[name], prototype[name]);
                } else if (typeof _super[name] === 'function') {
                    prototype[name] = (function (name, fn) {
                        return function () {
                            var tmp = this._super;
                            this._super = _super[name];
                            var ret = fn.apply(this, arguments);
                            this._super = tmp;
                            return ret;
                        };
                    })(name, properties[name]);
                }
            });
        };

        // Populate our constructed prototype object
        Class.prototype = prototype;

        // Enforce the constructor to be what we expect
        Class.constructor = Class;

        // And make this class extendable
        Class.extend = arguments.callee;

        return Class;
    };
})();

// Mixins

/**
 * Mixin to structure objects' life-cycles folowing a parent-children
 * relationship. Each object can a have a parent and multiple children.
 * When an object is destroyed, all its children are destroyed too releasing
 * any resource they could have reserved before.
 */
openerp.web.ParentedMixin = {
    __parentedMixin : true,
    init: function() {
        this.__parentedDestroyed = false;
        this.__parentedChildren = [];
        this.__parentedParent = null;
    },
    /**
     * Set the parent of the current object. When calling this method, the
     * parent will also be informed and will return the current object
     * when its getChildren() method is called. If the current object did
     * already have a parent, it is unregistered before, which means the
     * previous parent will not return the current object anymore when its
     * getChildren() method is called.
     */
    setParent : function(parent) {
        if (this.getParent()) {
            if (this.getParent().__parentedMixin) {
                this.getParent().__parentedChildren = _.without(this
                        .getParent().getChildren(), this);
            }
        }
        this.__parentedParent = parent;
        if (parent && parent.__parentedMixin) {
            parent.__parentedChildren.push(this);
        }
    },
    /**
     * Return the current parent of the object (or null).
     */
    getParent : function() {
        return this.__parentedParent;
    },
    /**
     * Return a list of the children of the current object.
     */
    getChildren : function() {
        return _.clone(this.__parentedChildren);
    },
    /**
     * Returns true if destroy() was called on the current object.
     */
    isDestroyed : function() {
        return this.__parentedDestroyed;
    },
    /**
        Utility method to only execute asynchronous actions if the current
        object has not been destroyed.

        @param {$.Deferred} promise The promise representing the asynchronous
                                    action.
        @param {bool} [reject=false] If true, the returned promise will be
                                     rejected with no arguments if the current
                                     object is destroyed. If false, the
                                     returned promise will never be resolved
                                     or rejected.
        @returns {$.Deferred} A promise that will mirror the given promise if
                              everything goes fine but will either be rejected
                              with no arguments or never resolved if the
                              current object is destroyed.
    */
    alive: function(promise, reject) {
        var def = $.Deferred();
        var self = this;
        promise.done(function() {
            if (! self.isDestroyed()) {
                if (! reject)
                    def.resolve.apply(def, arguments);
                else
                    def.reject();
            }
        }).fail(function() {
            if (! self.isDestroyed()) {
                if (! reject)
                    def.reject.apply(def, arguments);
                else
                    def.reject();
            }
        });
        return def.promise();
    },
    /**
     * Inform the object it should destroy itself, releasing any
     * resource it could have reserved.
     */
    destroy : function() {
        _.each(this.getChildren(), function(el) {
            el.destroy();
        });
        this.setParent(undefined);
        this.__parentedDestroyed = true;
    }
};

/**
 * Backbone's events. Do not ever use it directly, use EventDispatcherMixin instead.
 *
 * This class just handle the dispatching of events, it is not meant to be extended,
 * nor used directly. All integration with parenting and automatic unregistration of
 * events is done in EventDispatcherMixin.
 *
 * Copyright notice for the following Class:
 *
 * (c) 2010-2012 Jeremy Ashkenas, DocumentCloud Inc.
 * Backbone may be freely distributed under the MIT license.
 * For all details and documentation:
 * http://backbonejs.org
 *
 */
var Events = openerp.web.Class.extend({
    on : function(events, callback, context) {
        var ev;
        events = events.split(/\s+/);
        var calls = this._callbacks || (this._callbacks = {});
        while ((ev = events.shift())) {
            var list = calls[ev] || (calls[ev] = {});
            var tail = list.tail || (list.tail = list.next = {});
            tail.callback = callback;
            tail.context = context;
            list.tail = tail.next = {};
        }
        return this;
    },

    off : function(events, callback, context) {
        var ev, calls, node;
        if (!events) {
            delete this._callbacks;
        } else if ((calls = this._callbacks)) {
            events = events.split(/\s+/);
            while ((ev = events.shift())) {
                node = calls[ev];
                delete calls[ev];
                if (!callback || !node)
                    continue;
                while ((node = node.next) && node.next) {
                    if (node.callback === callback
                            && (!context || node.context === context))
                        continue;
                    this.on(ev, node.callback, node.context);
                }
            }
        }
        return this;
    },

    callbackList: function() {
        var lst = [];
        _.each(this._callbacks || {}, function(el, eventName) {
            var node = el;
            while ((node = node.next) && node.next) {
                lst.push([eventName, node.callback, node.context]);
            }
        });
        return lst;
    },

    trigger : function(events) {
        var event, node, calls, tail, args, all, rest;
        if (!(calls = this._callbacks))
            return this;
        all = calls['all'];
        (events = events.split(/\s+/)).push(null);
        // Save references to the current heads & tails.
        while ((event = events.shift())) {
            if (all)
                events.push({
                    next : all.next,
                    tail : all.tail,
                    event : event
                });
            if (!(node = calls[event]))
                continue;
            events.push({
                next : node.next,
                tail : node.tail
            });
        }
        rest = Array.prototype.slice.call(arguments, 1);
        while ((node = events.pop())) {
            tail = node.tail;
            args = node.event ? [ node.event ].concat(rest) : rest;
            while ((node = node.next) !== tail) {
                node.callback.apply(node.context || this, args);
            }
        }
        return this;
    }
});

openerp.web.EventDispatcherMixin = _.extend({}, openerp.web.ParentedMixin, {
    __eventDispatcherMixin: true,
    init: function() {
        openerp.web.ParentedMixin.init.call(this);
        this.__edispatcherEvents = new Events();
        this.__edispatcherRegisteredEvents = [];
    },
    on: function(events, dest, func) {
        var self = this;
        if (!(func instanceof Function)) {
            throw new Error("Event handler must be a function.");
        }
        events = events.split(/\s+/);
        _.each(events, function(eventName) {
            self.__edispatcherEvents.on(eventName, func, dest);
            if (dest && dest.__eventDispatcherMixin) {
                dest.__edispatcherRegisteredEvents.push({name: eventName, func: func, source: self});
            }
        });
        return this;
    },
    off: function(events, dest, func) {
        var self = this;
        events = events.split(/\s+/);
        _.each(events, function(eventName) {
            self.__edispatcherEvents.off(eventName, func, dest);
            if (dest && dest.__eventDispatcherMixin) {
                dest.__edispatcherRegisteredEvents = _.filter(dest.__edispatcherRegisteredEvents, function(el) {
                    return !(el.name === eventName && el.func === func && el.source === self);
                });
            }
        });
        return this;
    },
    trigger: function(events) {
        this.__edispatcherEvents.trigger.apply(this.__edispatcherEvents, arguments);
        return this;
    },
    destroy: function() {
        var self = this;
        _.each(this.__edispatcherRegisteredEvents, function(event) {
            event.source.__edispatcherEvents.off(event.name, event.func, self);
        });
        this.__edispatcherRegisteredEvents = [];
        _.each(this.__edispatcherEvents.callbackList(), function(cal) {
            this.off(cal[0], cal[2], cal[1]);
        }, this);
        this.__edispatcherEvents.off();
        openerp.web.ParentedMixin.destroy.call(this);
    }
});

openerp.web.PropertiesMixin = _.extend({}, openerp.web.EventDispatcherMixin, {
    init: function() {
        openerp.web.EventDispatcherMixin.init.call(this);
        this.__getterSetterInternalMap = {};
    },
    set: function(arg1, arg2, arg3) {
        var map;
        var options;
        if (typeof arg1 === "string") {
            map = {};
            map[arg1] = arg2;
            options = arg3 || {};
        } else {
            map = arg1;
            options = arg2 || {};
        }
        var self = this;
        var changed = false;
        _.each(map, function(val, key) {
            var tmp = self.__getterSetterInternalMap[key];
            if (tmp === val)
                return;
            changed = true;
            self.__getterSetterInternalMap[key] = val;
            if (! options.silent)
                self.trigger("change:" + key, self, {
                    oldValue: tmp,
                    newValue: val
                });
        });
        if (changed)
            self.trigger("change", self);
    },
    get: function(key) {
        return this.__getterSetterInternalMap[key];
    }
});

/**
 * Base class for all visual components. Provides a lot of functionalities helpful
 * for the management of a part of the DOM.
 *
 * Widget handles:
 * - Rendering with QWeb.
 * - Life-cycle management and parenting (when a parent is destroyed, all its children are
 *     destroyed too).
 * - Insertion in DOM.
 *
 * Guide to create implementations of the Widget class:
 * ==============================================
 *
 * Here is a sample child class:
 *
 * MyWidget = openerp.base.Widget.extend({
 *     // the name of the QWeb template to use for rendering
 *     template: "MyQWebTemplate",
 *
 *     init: function(parent) {
 *         this._super(parent);
 *         // stuff that you want to init before the rendering
 *     },
 *     start: function() {
 *         // stuff you want to make after the rendering, `this.$el` holds a correct value
 *         this.$el.find(".my_button").click(/* an example of event binding * /);
 *
 *         // if you have some asynchronous operations, it's a good idea to return
 *         // a promise in start()
 *         var promise = this.rpc(...);
 *         return promise;
 *     }
 * });
 *
 * Now this class can simply be used with the following syntax:
 *
 * var my_widget = new MyWidget(this);
 * my_widget.appendTo($(".some-div"));
 *
 * With these two lines, the MyWidget instance was inited, rendered, it was inserted into the
 * DOM inside the ".some-div" div and its events were binded.
 *
 * And of course, when you don't need that widget anymore, just do:
 *
 * my_widget.destroy();
 *
 * That will kill the widget in a clean way and erase its content from the dom.
 */
openerp.web.Widget = openerp.web.Class.extend(openerp.web.PropertiesMixin, {
    // Backbone-ish API
    tagName: 'div',
    id: null,
    className: null,
    attributes: {},
    events: {},
    /**
     * The name of the QWeb template that will be used for rendering. Must be
     * redefined in subclasses or the default render() method can not be used.
     *
     * @type string
     */
    template: null,
    /**
     * Constructs the widget and sets its parent if a parent is given.
     *
     * @constructs openerp.web.Widget
     *
     * @param {openerp.web.Widget} parent Binds the current instance to the given Widget instance.
     * When that widget is destroyed by calling destroy(), the current instance will be
     * destroyed too. Can be null.
     */
    init: function(parent) {
        openerp.web.PropertiesMixin.init.call(this);
        this.setParent(parent);
        // Bind on_/do_* methods to this
        // We might remove this automatic binding in the future
        for (var name in this) {
            if(typeof(this[name]) == "function") {
                if((/^on_|^do_/).test(name)) {
                    this[name] = this[name].bind(this);
                }
            }
        }
        // FIXME: this should not be
        this.setElement(this._make_descriptive());
    },
    /**
     * Destroys the current widget, also destroys all its children before destroying itself.
     */
    destroy: function() {
        _.each(this.getChildren(), function(el) {
            el.destroy();
        });
        if(this.$el) {
            this.$el.remove();
        }
        openerp.web.PropertiesMixin.destroy.call(this);
    },
    /**
     * Renders the current widget and appends it to the given jQuery object or Widget.
     *
     * @param target A jQuery object or a Widget instance.
     */
    appendTo: function(target) {
        var self = this;
        return this.__widgetRenderAndInsert(function(t) {
            self.$el.appendTo(t);
        }, target);
    },
    /**
     * Renders the current widget and prepends it to the given jQuery object or Widget.
     *
     * @param target A jQuery object or a Widget instance.
     */
    prependTo: function(target) {
        var self = this;
        return this.__widgetRenderAndInsert(function(t) {
            self.$el.prependTo(t);
        }, target);
    },
    /**
     * Renders the current widget and inserts it after to the given jQuery object or Widget.
     *
     * @param target A jQuery object or a Widget instance.
     */
    insertAfter: function(target) {
        var self = this;
        return this.__widgetRenderAndInsert(function(t) {
            self.$el.insertAfter(t);
        }, target);
    },
    /**
     * Renders the current widget and inserts it before to the given jQuery object or Widget.
     *
     * @param target A jQuery object or a Widget instance.
     */
    insertBefore: function(target) {
        var self = this;
        return this.__widgetRenderAndInsert(function(t) {
            self.$el.insertBefore(t);
        }, target);
    },
    /**
     * Renders the current widget and replaces the given jQuery object.
     *
     * @param target A jQuery object or a Widget instance.
     */
    replace: function(target) {
        return this.__widgetRenderAndInsert(_.bind(function(t) {
            this.$el.replaceAll(t);
        }, this), target);
    },
    __widgetRenderAndInsert: function(insertion, target) {
        this.renderElement();
        insertion(target);
        return this.start();
    },
    /**
     * Method called after rendering. Mostly used to bind actions, perform asynchronous
     * calls, etc...
     *
     * By convention, this method should return an object that can be passed to $.when() 
     * to inform the caller when this widget has been initialized.
     *
     * @returns {jQuery.Deferred or any}
     */
    start: function() {
        return $.when();
    },
    /**
     * Renders the element. The default implementation renders the widget using QWeb,
     * `this.template` must be defined. The context given to QWeb contains the "widget"
     * key that references `this`.
     */
    renderElement: function() {
        var $el;
        if (this.template) {
            $el = $(_.str.trim(openerp.web.qweb.render(
                this.template, {widget: this})));
        } else {
            $el = this._make_descriptive();
        }
        this.replaceElement($el);
    },
    /**
     * Re-sets the widget's root element and replaces the old root element
     * (if any) by the new one in the DOM.
     *
     * @param {HTMLElement | jQuery} $el
     * @returns {*} this
     */
    replaceElement: function ($el) {
        var $oldel = this.$el;
        this.setElement($el);
        if ($oldel && !$oldel.is(this.$el)) {
            $oldel.replaceWith(this.$el);
        }
        return this;
    },
    /**
     * Re-sets the widget's root element (el/$el/$el).
     *
     * Includes:
     * * re-delegating events
     * * re-binding sub-elements
     * * if the widget already had a root element, replacing the pre-existing
     *   element in the DOM
     *
     * @param {HTMLElement | jQuery} element new root element for the widget
     * @return {*} this
     */
    setElement: function (element) {
        // NB: completely useless, as WidgetMixin#init creates a $el
        // always
        if (this.$el) {
            this.undelegateEvents();
        }

        this.$el = (element instanceof $) ? element : $(element);
        this.el = this.$el[0];

        this.delegateEvents();

        return this;
    },
    /**
     * Utility function to build small DOM elements.
     *
     * @param {String} tagName name of the DOM element to create
     * @param {Object} [attributes] map of DOM attributes to set on the element
     * @param {String} [content] HTML content to set on the element
     * @return {Element}
     */
    make: function (tagName, attributes, content) {
        var el = document.createElement(tagName);
        if (!_.isEmpty(attributes)) {
            $(el).attr(attributes);
        }
        if (content) {
            $(el).html(content);
        }
        return el;
    },
    /**
     * Makes a potential root element from the declarative builder of the
     * widget
     *
     * @return {jQuery}
     * @private
     */
    _make_descriptive: function () {
        var attrs = _.extend({}, this.attributes || {});
        if (this.id) { attrs.id = this.id; }
        if (this.className) { attrs['class'] = this.className; }
        return $(this.make(this.tagName, attrs));
    },
    delegateEvents: function () {
        var events = this.events;
        if (_.isEmpty(events)) { return; }

        for(var key in events) {
            if (!events.hasOwnProperty(key)) { continue; }

            var method = this.proxy(events[key]);

            var match = /^(\S+)(\s+(.*))?$/.exec(key);
            var event = match[1];
            var selector = match[3];

            event += '.widget_events';
            if (!selector) {
                this.$el.on(event, method);
            } else {
                this.$el.on(event, selector, method);
            }
        }
    },
    undelegateEvents: function () {
        this.$el.off('.widget_events');
    },
    /**
     * Shortcut for ``this.$el.find(selector)``
     *
     * @param {String} selector CSS selector, rooted in $el
     * @returns {jQuery} selector match
     */
    $: function(selector) {
        return this.$el.find(selector);
    },
    /**
     * Proxies a method of the object, in order to keep the right ``this`` on
     * method invocations.
     *
     * This method is similar to ``Function.prototype.bind`` or ``_.bind``, and
     * even more so to ``jQuery.proxy`` with a fundamental difference: its
     * resolution of the method being called is lazy, meaning it will use the
     * method as it is when the proxy is called, not when the proxy is created.
     *
     * Other methods will fix the bound method to what it is when creating the
     * binding/proxy, which is fine in most javascript code but problematic in
     * OpenERP Web where developers may want to replace existing callbacks with
     * theirs.
     *
     * The semantics of this precisely replace closing over the method call.
     *
     * @param {String|Function} method function or name of the method to invoke
     * @returns {Function} proxied method
     */
    proxy: function (method) {
        var self = this;
        return function () {
            var fn = (typeof method === 'string') ? self[method] : method;
            return fn.apply(self, arguments);
        };
    },
});

openerp.web.qweb = new QWeb2.Engine();

openerp.web.qweb.default_dict = {
    '_' : _,
    'JSON': JSON,
};

return openerp;
};

if (typeof(define) !== "undefined") { // amd
    define(["jquery", "underscore", "qweb2"], declare);
} else {
    window.openerp = declare($, _, QWeb2);
}

})();