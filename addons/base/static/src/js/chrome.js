/*---------------------------------------------------------
 * OpenERP base library
 *---------------------------------------------------------*/

openerp.base.chrome = function(openerp) {

/**
 * Base error for lookup failure
 *
 * @class
 */
openerp.base.NotFound = openerp.base.Class.extend( /** @lends openerp.base.NotFound# */ {
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
openerp.base.Registry = openerp.base.Class.extend( /** @lends openerp.base.Registry# */ {
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


openerp.base.Session = openerp.base.Controller.extend( /** @lends openerp.base.Session# */{
    /**
     * @constructs
     * @param element_id to use for exception reporting
     * @param server
     * @param port
     */
    init: function(parent, element_id, server, port) {
        this._super(parent, element_id);
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
        this.session_restore();
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
        this.on_session_valid();
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
                return JSON.parse(decodeURIComponent(cookie.substring(nameEQ.length)));
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
            this.element_id + '|' + name + '=' + encodeURIComponent(JSON.stringify(value)),
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
            self.module_list = result;
            var modules = self.module_list.join(',');
            if(self.debug || true) {
                self.rpc('/base/webclient/csslist', {"mods": modules}, self.do_load_css);
                self.rpc('/base/webclient/jslist', {"mods": modules}, self.do_load_js);
            } else {
                self.do_load_css(["/base/webclient/css?mods="+modules]);
                self.do_load_js(["/base/webclient/js?mods="+modules]);
            }
            openerp._modules_loaded = true;
        });
    },
    do_load_css: function (files) {
        _.each(files, function (file) {
            $('head').append($('<link>', {
                'href': file,
                'rel': 'stylesheet',
                'type': 'text/css'
            }));
        });
    },
    do_load_js: function(files) {
        var self = this;
        if(files.length != 0) {
            var file = files.shift();
            var tag = document.createElement('script');
            tag.type = 'text/javascript';
            tag.src = file;
            tag.onload = tag.onreadystatechange = function() {
                if ( (tag.readyState && tag.readyState != "loaded" && tag.readyState != "complete") || tag.onload_done )
                    return;
                tag.onload_done = true;
                self.do_load_js(files);
            };
            document.head.appendChild(tag);
        } else {
            this.on_modules_loaded();
        }
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
    }
});

openerp.base.Notification =  openerp.base.Controller.extend({
    init: function(parent, element_id) {
        this._super(parent, element_id);
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

openerp.base.Dialog = openerp.base.BaseWidget.extend({
    dialog_title: "",
    identifier_prefix: 'dialog',
    init: function (parent, options) {
        var self = this;
        this._super(parent);
        this.options = {
            modal: true,
            width: 'auto',
            min_width: 0,
            max_width: '100%',
            height: 'auto',
            min_height: 0,
            max_height: '100%',
            autoOpen: false,
            buttons: {},
            beforeClose: function () {
                self.on_close();
            }
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
    close: function() {
        // Closes the dialog but leave it in a state where it could be opened again.
        this.$dialog.dialog('close');
    },
    on_close: function() {
    },
    stop: function () {
        // Destroy widget
        this.close();
        this.$dialog.dialog('destroy');
    }
});

openerp.base.CrashManager = openerp.base.Dialog.extend({
    identifier_prefix: 'dialog_crash',
    init: function(parent) {
        this._super(parent);
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
    init: function(parent, element_id) {
        this._super(parent, element_id);
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
    init: function(parent, element_id) {
        this._super(parent, element_id);
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
    init: function(parent, element_id) {
        this._super(parent, element_id);
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
    init: function(parent, element_id, secondary_menu_id) {
        this._super(parent, element_id);
        this.secondary_menu_id = secondary_menu_id;
        this.$secondary_menu = $("#" + secondary_menu_id);
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

        $('.active', this.$element.add(this.$secondary_menu)).removeClass('active');
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

        QWeb.add_template("/base/static/src/xml/base.xml");
        var params = {};
        if(jQuery.param != undefined && jQuery.deparam(jQuery.param.querystring()).kitten != undefined) {
            this.$element.addClass("kitten-mode-activated");
        }
        this.$element.html(QWeb.render("Interface", params));

        this.session = new openerp.base.Session(this,"oe_errors");
        this.loading = new openerp.base.Loading(this,"oe_loading");
        this.crashmanager =  new openerp.base.CrashManager(this);
        this.crashmanager.start(false);

        // Do you autorize this ? will be replaced by notify() in controller
        openerp.base.Controller.prototype.notification = new openerp.base.Notification(this, "oe_notification");

        this.header = new openerp.base.Header(this, "oe_header");
        this.login = new openerp.base.Login(this, "oe_login");
        this.header.on_logout.add(this.login.on_logout);

        this.session.on_session_invalid.add(this.login.do_ask_login);
        this.session.on_session_valid.add_last(this.header.do_update);
        this.session.on_session_valid.add_last(this.on_logged);

        this.menu = new openerp.base.Menu(this, "oe_menu", "oe_secondary_menu");
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
        this.action_manager =  new openerp.base.ActionManager(this, "oe_app");
        this.action_manager.start();

        // if using saved actions, load the action and give it to action manager
        var parameters = jQuery.deparam(jQuery.param.querystring());
        if(parameters["s_action"] != undefined) {
            var key = parseInt(parameters["s_action"]);
            var self = this;
            this.rpc("/base/session/get_session_action", {key:key}, function(action) {
                self.action_manager.do_action(action);
            });
        }
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
