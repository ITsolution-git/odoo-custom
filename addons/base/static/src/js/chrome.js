/*---------------------------------------------------------
 * OpenERP base library
 *---------------------------------------------------------*/

openerp.base.chrome = function(openerp) {

openerp.base.callback = function(obj, method) {
    var callback = function() {
        var args = Array.prototype.slice.call(arguments);
        var r;
        for(var i = 0; i < callback.callback_chain.length; i++)  {
            var c = callback.callback_chain[i];
            if(c.unique) {
                callback.callback_chain.splice(i, 1);
                i -= 1;
            }
            r = c.callback.apply(c.self, c.args.concat(args));
            // TODO special value to stop the chain
            // openerp.base.callback_stop
        }
        return r;
    };
    callback.callback_chain = [];
    callback.add = function(f) {
        if(typeof(f) == 'function') {
            f = { callback: f, args: Array.prototype.slice.call(arguments, 1) };
        }
        f.self = f.self || null;
        f.args = f.args || [];
        f.unique = !!f.unique;
        if(f.position == 'last') {
            callback.callback_chain.push(f);
        } else {
            callback.callback_chain.unshift(f);
        }
        return callback;
    };
    callback.add_first = function(f) {
        return callback.add.apply(null,arguments);
    };
    callback.add_last = function(f) {
        return callback.add({
            callback: f,
            args: Array.prototype.slice.call(arguments, 1),
            position: "last"
        });
    };

    return callback.add({
        callback: method,
        self:obj,
        args:Array.prototype.slice.call(arguments, 2)
    });
};

/**
 * Base error for lookup failure
 *
 * @class
 */
openerp.base.NotFound = Class.extend( /** @lends openerp.base.NotFound# */ {
});
openerp.base.KeyNotFound = openerp.base.NotFound.extend( /** @lends openerp.base.KeyNotFound# */ {
    /**
     * Thrown when a key could not be found in a mapping
     *
     * @constructs
     * @extends openerp.base.NotFound
     * @param {String} key the key which could not be found
     */
    init: function (key) {
        this.key = key;
    },
    toString: function () {
        return "The key " + this.key + " was not found";
    }
});
openerp.base.ObjectNotFound = openerp.base.NotFound.extend( /** @lends openerp.base.ObjectNotFound# */ {
    /**
     * Thrown when an object path does not designate a valid class or object
     * in the openerp hierarchy.
     *
     * @constructs
     * @extends openerp.base.NotFound
     * @param {String} path the invalid object path
     */
    init: function (path) {
        this.path = path;
    },
    toString: function () {
        return "Could not find any object of path " + this.path;
    }
});
openerp.base.Registry = Class.extend( /** @lends openerp.base.Registry# */ {
    /**
     * Stores a mapping of arbitrary key (strings) to object paths (as strings
     * as well).
     *
     * Resolves those paths at query time in order to always fetch the correct
     * object, even if those objects have been overloaded/replaced after the
     * registry was created.
     *
     * An object path is simply a dotted name from the openerp root to the
     * object pointed to (e.g. ``"openerp.base.Session"`` for an OpenERP
     * session object).
     *
     * @constructs
     * @param {Object} mapping a mapping of keys to object-paths
     */
    init: function (mapping) {
        this.map = mapping || {};
    },
    /**
     * Retrieves the object matching the provided key string.
     *
     * @param {String} key the key to fetch the object for
     * @returns {Class} the stored class, to initialize
     *
     * @throws {openerp.base.KeyNotFound} if the object was not in the mapping
     * @throws {openerp.base.ObjectNotFound} if the object path was invalid
     */
    get_object: function (key) {
        var path_string = this.map[key];
        if (path_string === undefined) {
            throw new openerp.base.KeyNotFound(key);
        }

        var object_match = openerp;
        var path = path_string.split('.');
        // ignore first section
        for(var i=1; i<path.length; ++i) {
            object_match = object_match[path[i]];

            if (object_match === undefined) {
                throw new openerp.base.ObjectNotFound(path_string);
            }
        }
        return object_match;
    },
    /**
     * Tries a number of keys, and returns the first object matching one of
     * the keys.
     *
     * @param {Array} keys a sequence of keys to fetch the object for
     * @returns {Class} the first class found matching an object
     *
     * @throws {openerp.base.KeyNotFound} if none of the keys was in the mapping
     * @trows {openerp.base.ObjectNotFound} if a found object path was invalid
     */
    get_any: function (keys) {
        for (var i=0; i<keys.length; ++i) {
            try {
                return this.get_object(keys[i]);
            } catch (e) {
                if (e instanceof openerp.base.KeyNotFound) {
                    continue;
                }
                throw e;
            }
        }
        throw new openerp.base.KeyNotFound(keys.join(','));
    },
    /**
     * Adds a new key and value to the registry.
     *
     * This method can be chained.
     *
     * @param {String} key
     * @param {String} object_path fully qualified dotted object path
     * @returns {openerp.base.Registry} itself
     */
    add: function (key, object_path) {
        this.map[key] = object_path;
        return this;
    },
    /**
     * Creates and returns a copy of the current mapping, with the provided
     * mapping argument added in (replacing existing keys if needed)
     *
     * @param {Object} [mapping={}] a mapping of keys to object-paths
     */
    clone: function (mapping) {
        return new openerp.base.Registry(
            _.extend({}, this.map, mapping || {}));
    }
});

openerp.base.BasicController = Class.extend( /** @lends openerp.base.BasicController# */{
    /**
     * rpc operations, event binding and callback calling should be done in
     * start() instead of init so that event can be hooked in between.
     *
     *  @constructs
     */
    init: function(element_id) {
        this.element_id = element_id;
        this.$element = $('#' + element_id);
        if (element_id) {
            openerp.screen[element_id] = this;
        }

        // Transform on_* method into openerp.base.callbacks
        for (var name in this) {
            if(typeof(this[name]) == "function") {
                this[name].debug_name = name;
                // bind ALL function to this not only on_and _do ?
                if((/^on_|^do_/).test(name)) {
                    this[name] = openerp.base.callback(this, this[name]);
                }
            }
        }
    },
    /**
     * Controller start
     * event binding, rpc and callback calling required to initialize the
     * object can happen here
     *
     * Returns a promise object letting callers (subclasses and direct callers)
     * know when this component is done starting
     *
     * @returns {jQuery.Deferred}
     */
    start: function() {
        // returns an already fulfilled promise. Maybe we could return nothing?
        // $.when can take non-deferred and in that case it simply considers
        // them all as fulfilled promises.
        // But in thise case we *have* to ensure callers use $.when and don't
        // try to call deferred methods on this return value.
        return $.Deferred().done().promise();
    },
    stop: function() {
    },
    log: function() {
        var args = Array.prototype.slice.call(arguments);
        var caller = arguments.callee.caller;
        // TODO add support for line number using
        // https://github.com/emwendelin/javascript-stacktrace/blob/master/stacktrace.js
        // args.unshift("" + caller.debug_name);
        this.on_log.apply(this,args);
    },
    on_log: function() {
        if(window.openerp.debug || (window.location.search.indexOf('?debug') !== -1)) {
            var notify = false;
            var body = false;
            if(window.console) {
                console.log(arguments);
            } else {
                body = true;
            }
            var a = Array.prototype.slice.call(arguments, 0);
            for(var i = 0; i < a.length; i++) {
                var v = a[i]==null ? "null" : a[i].toString();
                if(i==0) {
                    notify = v.match(/^not/);
                    body = v.match(/^bod/);
                }
                if(body) {
                    $('<pre></pre>').text(v).appendTo($('body'));
                }
                if(notify && this.notification) {
                    this.notification.notify("Logging:",v);
                }
            }
        }

    }
});

/**
 * Generates an inherited class that replaces all the methods by null methods (methods
 * that does nothing and always return undefined).
 * 
 * @param {Class} claz
 * @param {Object} add Additional functions to override.
 * @return {Class}
 */
openerp.base.generate_null_object_class = function(claz, add) {
    var newer = {};
    var copy_proto = function(prototype) {
        for (var name in prototype) {
            if(typeof prototype[name] == "function") {
                newer[name] = function() {};
            }
        }
        if (prototype.prototype)
            copy_proto(prototype.prototype);
    };
    copy_proto(claz.prototype);
    newer.init = openerp.base.BasicController.prototype.init;
    var tmpclass = claz.extend(newer);
    return tmpclass.extend(add || {});
};

openerp.base.Notification =  openerp.base.BasicController.extend({
    init: function(element_id) {
        this._super(element_id);
        this.$element.notify({
            speed: 500,
            expires: 1500
        });
    },
    notify: function(title, text) {
        this.$element.notify('create', {
            title: title,
            text: text
        });
    },
    warn: function(title, text) {
        this.$element.notify('create', 'oe_notification_alert', {
            title: title,
            text: text
        });
    }
});

openerp.base.Session = openerp.base.BasicController.extend( /** @lends openerp.base.Session# */{
    /**
     * @constructs
     * @extends openerp.base.BasicController
     * @param element_id to use for exception reporting
     * @param server
     * @param port
     */
    init: function(element_id, server, port) {
        this._super(element_id);
        this.server = (server == undefined) ? location.hostname : server;
        this.port = (port == undefined) ? location.port : port;
        this.rpc_mode = (server == location.hostname) ? "ajax" : "jsonp";
        this.debug = true;
        this.db = "";
        this.login = "";
        this.password = "";
        this.uid = false;
        this.session_id = false;
        this.module_list = [];
        this.module_loaded = {"base": true};
        this.context = {};
    },
    start: function() {
        var self = this;
        return this.session_restore().then(function () {
            self.on_session_valid();
        }, function () {
            self.on_session_invalid();
        });
    },
    /**
     * Executes an RPC call, registering the provided callbacks.
     *
     * Registers a default error callback if none is provided, and handles
     * setting the correct session id and session context in the parameter
     * objects
     *
     * @param {String} url RPC endpoint
     * @param {Object} params call parameters
     * @param {Function} success_callback function to execute on RPC call success
     * @param {Function} error_callback function to execute on RPC call failure
     * @returns {jQuery.Deferred} jquery-provided ajax deferred
     */
    rpc: function(url, params, success_callback, error_callback) {
        var self = this;
        // Construct a JSON-RPC2 request, method is currently unused
        params.session_id = this.session_id;

        // Call using the rpc_mode
        var deferred = $.Deferred();
        this.rpc_ajax(url, {
            jsonrpc: "2.0",
            method: "call",
            params: params,
            id:null
        }).then(function () {deferred.resolve.apply(deferred, arguments);},
                function(error) {deferred.reject(error, $.Event());});
        return deferred.fail(function() {
            deferred.fail(function(error, event) {
                if (!event.isDefaultPrevented()) {
                    self.on_rpc_error(error, event);
                }
            });
        }).then(success_callback, error_callback).promise();
    },
    /**
     * Raw JSON-RPC call
     *
     * @returns {jQuery.Deferred} ajax-based deferred object
     */
    rpc_ajax: function(url, payload) {
        var self = this;
        this.on_rpc_request();
        // url can be an $.ajax option object
        if (_.isString(url)) {
            url = {
                url: url
            }
        }
        var ajax = _.extend({
            type: "POST",
            url: url,
            dataType: 'json',
            contentType: 'application/json',
            data: JSON.stringify(payload),
            processData: false
        }, url);
        var deferred = $.Deferred();
        $.ajax(ajax).done(function(response, textStatus, jqXHR) {
            self.on_rpc_response();
            if (!response.error) {
                deferred.resolve(response["result"], textStatus, jqXHR);
                return;
            }
            if (response.error.data.type !== "session_invalid") {
                deferred.reject(response.error);
                return;
            }
            self.uid = false;
            self.on_session_invalid(function() {
                self.rpc(url, payload.params,
                    function() {
                        deferred.resolve.apply(deferred, arguments);
                    },
                    function(error, event) {
                        event.preventDefault();
                        deferred.reject.apply(deferred, arguments);
                    });
            });
        }).fail(function(jqXHR, textStatus, errorThrown) {
            self.on_rpc_response();
            var error = {
                code: -32098,
                message: "XmlHttpRequestError " + errorThrown,
                data: {type: "xhr"+textStatus, debug: jqXHR.responseText, objects: [jqXHR, errorThrown] }
            };
            deferred.reject(error);
        });
        return deferred.promise();
    },
    on_rpc_request: function() {
    },
    on_rpc_response: function() {
    },
    on_rpc_error: function(error) {
    },
    /**
     * The session is validated either by login or by restoration of a previous session
     */
    on_session_valid: function() {
        if(!openerp._modules_loaded)
            this.load_modules();
    },
    on_session_invalid: function(contination) {
    },
    session_is_valid: function() {
        return this.uid;
    },
    session_login: function(db, login, password, success_callback) {
        var self = this;
        this.db = db;
        this.login = login;
        this.password = password;
        var params = { db: this.db, login: this.login, password: this.password };
        this.rpc("/base/session/login", params, function(result) {
            self.session_id = result.session_id;
            self.uid = result.uid;
            self.session_save();
            self.on_session_valid();
            if (success_callback)
                success_callback();
        });
    },
    session_logout: function() {
        this.uid = false;
    },
    /**
     * Reloads uid and session_id from local storage, if they exist
     */
    session_restore: function () {
        this.uid = this.get_cookie('uid');
        this.session_id = this.get_cookie('session_id');
        // we should do an rpc to confirm that this session_id is valid and if it is retrieve the information about db and login
        // then call on_session_valid
        return this.rpc('/base/session/check', {}, function () {}, function () {});
    },
    /**
     * Saves the session id and uid locally
     */
    session_save: function () {
        this.set_cookie('uid', this.uid);
        this.set_cookie('session_id', this.session_id);
    },
    logout: function() {
        this.uid = this.get_cookie('uid');
        this.session_id = this.get_cookie('session_id');
        this.set_cookie('uid', '');
        this.set_cookie('session_id', '');
        this.on_session_invalid(function() {});
    },
    /**
     * Fetches a cookie stored by an openerp session
     *
     * @private
     * @param name the cookie's name
     */
    get_cookie: function (name) {
        var nameEQ = this.element_id + '|' + name + '=';
        var cookies = document.cookie.split(';');
        for(var i=0; i<cookies.length; ++i) {
            var cookie = cookies[i].replace(/^\s*/, '');
            if(cookie.indexOf(nameEQ) === 0) {
                return decodeURIComponent(cookie.substring(nameEQ.length));
            }
        }
        return null;
    },
    /**
     * Create a new cookie with the provided name and value
     *
     * @private
     * @param name the cookie's name
     * @param value the cookie's value
     * @param ttl the cookie's time to live, 1 year by default, set to -1 to delete
     */
    set_cookie: function (name, value, ttl) {
        ttl = ttl || 24*60*60*365;
        document.cookie = [
            this.element_id + '|' + name + '=' + encodeURIComponent(value),
            'max-age=' + ttl,
            'expires=' + new Date(new Date().getTime() + ttl*1000).toGMTString()
        ].join(';');
    },
    /**
     * Load additional web addons of that instance and init them
     */
    load_modules: function() {
        var self = this;
        this.rpc('/base/session/modules', {}, function(result) {
            self.module_list = result['modules'];
            var modules = self.module_list.join(',');
            self.rpc('/base/session/csslist', {mods: modules}, self.do_load_css);
            self.rpc('/base/session/jslist', {"mods": modules}, self.debug ? self.do_load_modules_debug : self.do_load_modules_prod);
        });
    },
    do_load_css: function (result) {
        _.each(result.files, function (file) {
            $('head').append($('<link>', {
                'href': file,
                'rel': 'stylesheet',
                'type': 'text/css'
            }));
        });
    },
    do_load_modules_debug: function(result) {
        $LAB.setOptions({AlwaysPreserveOrder: true})
            .script(result.files)
            .wait(this.on_modules_loaded);
    },
    do_load_modules_prod: function() {
        // load merged ones
        // /base/session/css?mod=mod1,mod2,mod3
        // /base/session/js?mod=mod1,mod2,mod3
        // use $.getScript(‘your_3rd_party-script.js’); ? i want to keep lineno !
    },
    on_modules_loaded: function() {
        for(var j=0; j<this.module_list.length; j++) {
            var mod = this.module_list[j];
            if(this.module_loaded[mod])
                continue;
            openerp[mod] = {};
            // init module mod
            if(openerp._openerp[mod] != undefined) {
                openerp._openerp[mod](openerp);
                this.module_loaded[mod] = true;
            }
        }
        openerp._modules_loaded = true;
    }
});

// A controller takes an already existing element
// new()
// start()
openerp.base.Controller = openerp.base.BasicController.extend( /** @lends openerp.base.Controller# */{
    /**
     * Controller manifest used to declare standard controller attributes
     */
    controller_manifest: {
        register: null,
        template: "",
        element_post_prefix: false
    },
    /**
     * Controller registry, 
     */
    controller_registry: {
    },
    /**
     * Add a new child controller
     */
    controller_get: function(key) {
        return this.controller_registry[key];
        // OR should build it ? setting parent correctly ?
        // function construct(constructor, args) {
        //     function F() {
        //         return constructor.apply(this, args);
        //     }
        //     F.prototype = constructor.prototype;
        //     return new F();
        // }
        // var obj = this.controller_registry[key];
        // if(obj) {
        //     return construct(obj, Array.prototype.slice.call(arguments, 1));
        // }
    },
    controller_new: function(key) {
        var self;
        // OR should contrustct it ? setting parent correctly ?
        function construct(constructor, args) {
            function F() {
                return constructor.apply(this, args);
            }
            F.prototype = constructor.prototype;
            return new F();
        }
        var obj = this.controller_registry[key];
        if(obj) {
            // TODO Prepend parent
            return construct(obj, Array.prototype.slice.call(arguments, 1));
        }
    },
    /**
     * @constructs
     * @extends openerp.base.BasicController
     */
    init: function(parent_or_session, element_id) {
        this._super(element_id);
        this.controller_parent = null;
        this.controller_children = [];
        if(parent_or_session) {
            if(parent_or_session.session) {
                this.parent = parent_or_session;
                this.session = this.parent.session;
                if(this.parent.children) {
                    this.parent.children.push(this);
                }
            } else {
                // TODO remove Backward compatilbility
                this.session = parent_or_session;
            }
        }
        // Apply manifest options
        if(this.controller_manifest) {
            var register = this.controller_manifest.register;
            // TODO accept a simple string
            if(register) {
                for(var i=0; i<register.length; i++) {
                    this.controller_registry[register[i]] = this;
                }
            }
            // TODO if post prefix
            //this.element_id = _.uniqueId(_.toArray(arguments).join('_'));
        }
    },
    /**
     * Performs a JSON-RPC call
     *
     * @param {String} url endpoint url
     * @param {Object} data RPC parameters
     * @param {Function} success RPC call success callback
     * @param {Function} error RPC call error callback
     * @returns {jQuery.Deferred} deferred object for the RPC call
     */
    rpc: function(url, data, success, error) {
        // TODO: support additional arguments ?
        return this.session.rpc(url, data, success, error);
    }
});

// A widget is a controller that doesnt take an element_id
// it render its own html that you should insert into the dom
// and bind it a start()
//
// new()
// render() and insert it place it where you want
// start()
openerp.base.BaseWidget = openerp.base.Controller.extend({
    /**
     * The name of the QWeb template that will be used for rendering. Must be
     * redefined in subclasses or the render() method can not be used.
     * 
     * @type string
     */
    template: null,
    /**
     * The prefix used to generate an id automatically. Should be redefined in
     * subclasses. If it is not defined, a default identifier will be used.
     * 
     * @type string
     */
    identifier_prefix: 'generic-identifier',
    /**
     * Base class for widgets. Handle rendering (based on a QWeb template),
     * identifier generation, parenting and destruction of the widget.
     * Also initialize the identifier.
     *
     * @constructs
     * @params {openerp.base.search.BaseWidget} parent The parent widget.
     */
    init: function (parent, session) {
        this._super(session);
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
     * Set the parent of this component, also un-register the previous parent
     * if there was one.
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

openerp.base.Dialog = openerp.base.BaseWidget.extend({
    dialog_title: "",
    identifier_prefix: 'dialog',
    init: function (session, options) {
        this._super(null, session);
        this.options = {
            modal: true,
            width: 'auto',
            min_width: 0,
            max_width: '100%',
            height: 'auto',
            min_height: 0,
            max_height: '100%',
            autoOpen: false,
            buttons: {}
        };
        for (var f in this) {
            if (f.substr(0, 10) == 'on_button_') {
                this.options.buttons[f.substr(10)] = this[f];
            }
        }
        if (options) {
            this.set_options(options);
        }
    },
    set_options: function(options) {
        options = options || {};
        options.width = this.get_width(options.width || this.options.width);
        options.min_width = this.get_width(options.min_width || this.options.min_width);
        options.max_width = this.get_width(options.max_width || this.options.max_width);
        options.height = this.get_height(options.height || this.options.height);
        options.min_height = this.get_height(options.min_height || this.options.min_height);
        options.max_height = this.get_height(options.max_height || this.options.max_width);

        if (options.width !== 'auto') {
            if (options.width > options.max_width) options.width = options.max_width;
            if (options.width < options.min_width) options.width = options.min_width;
        }
        if (options.height !== 'auto') {
            if (options.height > options.max_height) options.height = options.max_height;
            if (options.height < options.min_height) options.height = options.min_height;
        }
        if (!options.title && this.dialog_title) {
            options.title = this.dialog_title;
        }
        _.extend(this.options, options);
    },
    get_width: function(val) {
        return this.get_size(val.toString(), $(window.top).width());
    },
    get_height: function(val) {
        return this.get_size(val.toString(), $(window.top).height());
    },
    get_size: function(val, available_size) {
        if (val === 'auto') {
            return val;
        } else if (val.slice(-1) == "%") {
            return Math.round(available_size / 100 * parseInt(val.slice(0, -1), 10));
        } else {
            return parseInt(val, 10);
        }
    },
    start: function (auto_open) {
        this.$dialog = $('<div id="' + this.element_id + '"></div>').dialog(this.options);
        if (auto_open !== false) {
            this.open();
        }
        this._super();
    },
    open: function(options) {
        // TODO fme: bind window on resize
        if (this.template) {
            this.$element.html(this.render());
        }
        this.set_options(options);
        this.$dialog.dialog(this.options).dialog('open');
    },
    close: function(options) {
        this.$dialog.dialog('close');
    },
    stop: function () {
        this.close();
        this.$dialog.dialog('destroy');
    }
});

openerp.base.CrashManager = openerp.base.Dialog.extend({
    identifier_prefix: 'dialog_crash',
    init: function(session) {
        this._super(session);
        this.session.on_rpc_error.add(this.on_rpc_error);
    },
    on_button_Ok: function() {
        this.close();
    },
    on_rpc_error: function(error) {
        this.error = error;
        if (error.data.fault_code) {
            var split = error.data.fault_code.split('\n')[0].split(' -- ');
            if (split.length > 1) {
                error.type = split.shift();
                error.data.fault_code = error.data.fault_code.substr(error.type.length + 4);
            }
        }
        if (error.code === 200 && error.type) {
            this.dialog_title = "OpenERP " + _.capitalize(error.type);
            this.template = 'DialogWarning';
            this.open({
                width: 'auto',
                height: 'auto'
            });
        } else {
            this.dialog_title = "OpenERP Error";
            this.template = 'DialogTraceback';
            this.open({
                width: '80%',
                height: '80%'
            });
        }
    }
});

openerp.base.Loading =  openerp.base.Controller.extend({
    controller_manifest: {
        register: ["Loading"]
    },
    init: function(session, element_id) {
        this._super(session, element_id);
        this.count = 0;
        this.session.on_rpc_request.add_first(this.on_rpc_event, 1);
        this.session.on_rpc_response.add_last(this.on_rpc_event, -1);
    },
    on_rpc_event : function(increment) {
        this.count += increment;
        if (this.count) {
            //this.$element.html(QWeb.render("Loading", {}));
            this.$element.html("Loading ("+this.count+")");
            this.$element.show();
        } else {
            this.$element.fadeOut();
        }
    }
});

openerp.base.Database = openerp.base.Controller.extend({
});

openerp.base.Login =  openerp.base.Controller.extend({
    remember_creditentials: true,
    init: function(session, element_id) {
        this._super(session, element_id);
        this.has_local_storage = typeof(localStorage) != 'undefined';
        this.selected_db = null;
        this.selected_login = null;
        if (this.has_local_storage && this.remember_creditentials) {
            this.selected_db = localStorage.getItem('last_db_login_success');
            this.selected_login = localStorage.getItem('last_login_login_success');
        }
        if (jQuery.deparam(jQuery.param.querystring()).debug != undefined) {
            this.selected_db = this.selected_db || "trunk";
            this.selected_login = this.selected_login || "admin";
            this.selected_password = this.selected_password || "a";
        }
    },
    start: function() {
        var self = this;
        this.rpc("/base/database/get_databases_list", {}, function(result) {
            self.db_list = result.db_list;
            self.display();
        }, function() {
            self.display();
        });
    },
    display: function() {
        this.$element.html(QWeb.render("Login", this));
        this.$element.find("form").submit(this.on_submit);
    },
    on_login_invalid: function() {
        this.$element.closest(".openerp").addClass("login-mode");
    },
    on_login_valid: function() {
        this.$element.closest(".openerp").removeClass("login-mode");
    },
    on_submit: function(ev) {
        ev.preventDefault();
        var self = this;
        var $e = this.$element;
        var db = $e.find("form [name=db]").val();
        var login = $e.find("form input[name=login]").val();
        var password = $e.find("form input[name=password]").val();
        //$e.hide();
        // Should hide then call callback
        this.session.session_login(db, login, password, function() {
            if(self.session.session_is_valid()) {
                if (self.has_local_storage) {
                    if(self.remember_creditentials) {
                        localStorage.setItem('last_db_login_success', db);
                        localStorage.setItem('last_login_login_success', login);
                    } else {
                        localStorage.setItem('last_db_login_success', '');
                        localStorage.setItem('last_login_login_success', '');
                    }
                }
                self.on_login_valid();
            } else {
                self.$element.addClass("login_invalid");
                self.on_login_invalid();
            }
        });
    },
    do_ask_login: function(continuation) {
        this.on_login_invalid();
        this.$element
            .removeClass("login_invalid");
        this.on_login_valid.add({
            position: "last",
            unique: true,
            callback: continuation
        });
    },
    on_logout: function() {
        this.session.logout();
    }
});

openerp.base.Header =  openerp.base.Controller.extend({
    init: function(session, element_id) {
        this._super(session, element_id);
    },
    start: function() {
        this.do_update();
    },
    do_update: function() {
        this.$element.html(QWeb.render("Header", this));
        this.$element.find(".logout").click(this.on_logout);
    },
    on_logout: function() {}
});

openerp.base.Menu =  openerp.base.Controller.extend({
    init: function(session, element_id, secondary_menu_id) {
        this._super(session, element_id);
        this.secondary_menu_id = secondary_menu_id;
        this.$secondary_menu = $("#" + secondary_menu_id).hide();
        this.menu = false;
    },
    start: function() {
        this.rpc("/base/menu/load", {}, this.on_loaded);
    },
    on_loaded: function(data) {
        this.data = data;
        this.$element.html(QWeb.render("Menu", this.data));
        for (var i = 0; i < this.data.data.children.length; i++) {
            var v = { menu : this.data.data.children[i] };
            this.$secondary_menu.append(QWeb.render("Menu.secondary", v));
        }
        this.$secondary_menu.find("div.menu_accordion").accordion({
            animated : false,
            autoHeight : false,
            icons : false
        });
        this.$secondary_menu.find("div.submenu_accordion").accordion({
            animated : false,
            autoHeight : false,
            active: false,
            collapsible: true,
            header: 'h4'
        });

        this.$element.add(this.$secondary_menu).find("a").click(this.on_menu_click);
    },
    on_menu_click: function(ev, id) {
        id = id || 0;
        var $menu, $parent, $secondary;

        if (id) {
            // We can manually activate a menu with it's id (for hash url mapping)
            $menu = this.$element.find('a[data-menu=' + id + ']');
            if (!$menu.length) {
                $menu = this.$secondary_menu.find('a[data-menu=' + id + ']');
            }
        } else {
            $menu = $(ev.currentTarget);
            id = $menu.data('menu');
        }
        if (this.$secondary_menu.has($menu).length) {
            $secondary = $menu.parents('.menu_accordion');
            $parent = this.$element.find('a[data-menu=' + $secondary.data('menu-parent') + ']');
        } else {
            $parent = $menu;
            $secondary = this.$secondary_menu.find('.menu_accordion[data-menu-parent=' + $menu.attr('data-menu') + ']');
        }

        this.$secondary_menu.find('.menu_accordion').hide();
        // TODO: ui-accordion : collapse submenus and expand the good one
        $secondary.show();

        if (id) {
            this.rpc('/base/menu/action', {'menu_id': id},
                    this.on_menu_action_loaded);
        }

        $('.active', this.$element.add(this.$secondary_menu.show())).removeClass('active');
        $parent.addClass('active');
        $menu.addClass('active');
        $menu.parent('h4').addClass('active');

        return !$menu.is(".leaf");
    },
    on_menu_action_loaded: function(data) {
        var self = this;
        if (data.action.length) {
            var action = data.action[0][2];
            self.on_action(action);
        }
    },
    on_action: function(action) {
    }
});

openerp.base.Homepage = openerp.base.Controller.extend({
});

openerp.base.Preferences = openerp.base.Controller.extend({
});

openerp.base.ImportExport = openerp.base.Controller.extend({
});

openerp.base.WebClient = openerp.base.Controller.extend({
    init: function(element_id) {
        this._super(null, element_id);
        this.view_manager = {};

        QWeb.add_template("xml/base.xml");
        var params = {};
        if(jQuery.param != undefined &&
                jQuery.deparam(jQuery.param.querystring()).kitten != undefined) {
            this.$element.addClass("kitten-mode-activated");
        }
        this.$element.html(QWeb.render("Interface", params));

        this.session = new openerp.base.Session("oe_errors");
        this.loading = new openerp.base.Loading(this.session, "oe_loading");
        this.crashmanager =  new openerp.base.CrashManager(this.session);
        this.crashmanager.start(false);

        // Do you autorize this ?
        openerp.base.Controller.prototype.notification = new openerp.base.Notification("oe_notification");

        this.header = new openerp.base.Header(this.session, "oe_header");
        this.login = new openerp.base.Login(this.session, "oe_login");
        this.header.on_logout.add(this.login.on_logout);

        this.session.on_session_invalid.add(this.login.do_ask_login);
        this.session.on_session_valid.add_last(this.header.do_update);
        this.session.on_session_valid.add_last(this.on_logged);

        this.menu = new openerp.base.Menu(this.session, "oe_menu", "oe_secondary_menu");
        this.menu.on_action.add(this.on_menu_action);
    },
    start: function() {
        this.session.start();
        this.header.start();
        this.login.start();
        this.menu.start();
        this.notification.notify("OpenERP Client", "The openerp client has been initialized.");
    },
    on_logged: function() {
        this.action_manager =  new openerp.base.ActionManager(this.session, "oe_app");
        this.action_manager.start();
        
        // if using saved actions, load the action and give it to action manager
        var parameters = jQuery.deparam(jQuery.param.querystring());
        if (parameters["s_action"] != undefined) {
            var key = parseInt(parameters["s_action"], 10);
            var self = this;
            this.rpc("/base/session/get_session_action", {key:key}, function(action) {
                self.action_manager.do_action(action);
            });
        } else if (openerp._modules_loaded) { // TODO: find better option than this
            this.load_url_state()
        } else {
            this.session.on_modules_loaded.add({
                callback: $.proxy(this, 'load_url_state'),
                unique: true,
                position: 'last'
            })
        }
    },
    /**
     * Loads state from URL if any, or checks if there is a home action and
     * loads that, assuming we're at the index
     */
    load_url_state: function () {
        var self = this;
        // TODO: add actual loading if there is url state to unpack, test on window.location.hash
        var ds = new openerp.base.DataSetSearch(this.session, 'res.users');
        ds.read_ids([parseInt(this.session.uid, 10)], ['action_id'], function (users) {
            var home_action = users[0].action_id;
            if (!home_action) { return; }
            // oh dear
            openerp.base.View.prototype.execute_action.call(
                self, {
                    'name': home_action[0],
                    'type': 'action'
                }, ds, self.action_manager);
        })
    },
    on_menu_action: function(action) {
        this.action_manager.do_action(action);
    },
    do_about: function() {
    }
});

openerp.base.webclient = function(element_id) {
    // TODO Helper to start webclient rename it openerp.base.webclient
    var client = new openerp.base.WebClient(element_id);
    client.start();
    return client;
};

};

// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax:
