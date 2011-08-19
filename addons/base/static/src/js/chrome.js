/*---------------------------------------------------------
 * OpenERP Web chrome
 *---------------------------------------------------------*/

openerp.base.chrome = function(openerp) {

openerp.base.Notification =  openerp.base.Widget.extend({
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

openerp.base.Dialog = openerp.base.OldWidget.extend({
    dialog_title: "",
    identifier_prefix: 'dialog',
    init: function (parent, dialog_options) {
        var self = this;
        this._super(parent);
        this.dialog_options = {
            modal: true,
            width: 'auto',
            min_width: 0,
            max_width: '100%',
            height: 'auto',
            min_height: 0,
            max_height: '100%',
            autoOpen: false,
            buttons: {},
            beforeClose: function () { self.on_close(); }
        };
        for (var f in this) {
            if (f.substr(0, 10) == 'on_button_') {
                this.dialog_options.buttons[f.substr(10)] = this[f];
            }
        }
        if (dialog_options) {
            this.set_options(dialog_options);
        }
    },
    set_options: function(options) {
        options = options || {};
        options.width = this.get_width(options.width || this.dialog_options.width);
        options.min_width = this.get_width(options.min_width || this.dialog_options.min_width);
        options.max_width = this.get_width(options.max_width || this.dialog_options.max_width);
        options.height = this.get_height(options.height || this.dialog_options.height);
        options.min_height = this.get_height(options.min_height || this.dialog_options.min_height);
        options.max_height = this.get_height(options.max_height || this.dialog_options.max_width);

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
        _.extend(this.dialog_options, options);
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
    start: function () {
        this.$dialog = $('<div id="' + this.element_id + '"></div>').dialog(this.dialog_options);
        this._super();
        return this;
    },
    open: function(dialog_options) {
        // TODO fme: bind window on resize
        if (this.template) {
            this.$element.html(this.render());
        }
        this.set_options(dialog_options);
        this.$dialog.dialog(this.dialog_options).dialog('open');
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
                width: 'auto',
                height: 'auto'
            });
        }
    }
});

openerp.base.Loading =  openerp.base.Widget.extend({
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

openerp.base.Database = openerp.base.Widget.extend({
    init: function(parent, element_id, option_id) {
        this._super(parent, element_id);
        this.$option_id = $('#' + option_id);
    },
    start: function() {
        this.$element.html(QWeb.render("Database", this));
        this.$element.closest(".openerp")
                .removeClass("login-mode")
                .addClass("database_block");

        var self = this;

        var fetch_db = this.rpc("/base/database/get_list", {}, function(result) {
            self.db_list = result.db_list;
        });
        var fetch_langs = this.rpc("/base/session/get_lang_list", {}, function(result) {
            if (result.error) {
                self.display_error(result);
                return;
            }
            self.lang_list = result.lang_list;
        });
        $.when(fetch_db, fetch_langs).then(function () {self.do_create();});

        this.$element.find('#db-create').click(this.do_create);
        this.$element.find('#db-drop').click(this.do_drop);
        this.$element.find('#db-backup').click(this.do_backup);
        this.$element.find('#db-restore').click(this.do_restore);
        this.$element.find('#db-change-password').click(this.do_change_password);
       	this.$element.find('#back-to-login').click(function() {
            self.stop();
        });
    },
    stop: function () {
        this.$option_id.empty();

        this.$element
            .find('#db-create, #db-drop, #db-backup, #db-restore, #db-change-password, #back-to-login')
                .unbind('click')
            .end()
            .closest(".openerp")
                .addClass("login-mode")
                .removeClass("database_block")
            .end()
            .empty();

    },
    /**
     * Converts a .serializeArray() result into a dict. Does not bother folding
     * multiple identical keys into an array, last key wins.
     *
     * @param {Array} array
     */
    to_object: function (array) {
        var result = {};
        _(array).each(function (record) {
            result[record.name] = record.value;
        });
        return result;
    },
    /**
     * Waits until the new database is done creating, then unblocks the UI and
     * logs the user in as admin
     *
     * @param {Number} db_creation_id identifier for the db-creation operation, used to fetch the current installation progress
     * @param {Object} info info fields for this database creation
     * @param {String} info.db name of the database being created
     * @param {String} info.password super-admin password for the database
     */
    wait_for_newdb: function (db_creation_id, info) {
        var self = this;
        self.rpc('/base/database/progress', {
            id: db_creation_id,
            password: info.password
        }, function (result) {
            var progress = result[0];
            // I'd display a progress bar, but turns out the progress status
            // the server report kind-of blows goats: it's at 0 for ~75% of
            // the installation, then jumps to 75%, then jumps down to either
            // 0 or ~40%, then back up to 75%, then terminates. Let's keep that
            // mess hidden behind a not-very-useful but not overly weird
            // message instead.
            if (progress < 1) {
                setTimeout(function () {
                    self.wait_for_newdb(db_creation_id, info);
                }, 500);
                return;
            }

            var admin = result[1][0];
            setTimeout(function () {
                self.stop();
                self.widget_parent.do_login(
                        info.db, admin.login, admin.password);
                $.unblockUI();
            });
        });
    },
    /**
     * Displays an error dialog resulting from the various RPC communications
     * failing over themselves
     *
     * @param {Object} error error description
     * @param {String} error.title title of the error dialog
     * @param {String} error.error message of the error dialog
     */
    display_error: function (error) {
        return $('<div>').dialog({
            modal: true,
            title: error.title,
            buttons: {
                Ok: function() {
                    $(this).dialog("close");
                }
            }
        }).html(error.error);
    },
    do_create: function() {
        var self = this;
       	self.$option_id.html(QWeb.render("Database.CreateDB", self));
        self.$option_id.find("form[name=create_db_form]").validate({
            submitHandler: function (form) {
                var fields = $(form).serializeArray();
                $.blockUI();
                self.rpc("/base/database/create", {'fields': fields}, function(result) {
                    if (result.error) {
                        $.unblockUI();
                        self.display_error(result);
                        return;
                    }
                    self.db_list.push(self.to_object(fields)['db_name']);
                    self.db_list.sort();
                    var form_obj = self.to_object(fields);
                    self.wait_for_newdb(result, {
                        password: form_obj['super_admin_pwd'],
                        db: form_obj['db_name']
                    });
                });
            }
        });
    },
    do_drop: function() {
        var self = this;
       	self.$option_id.html(QWeb.render("DropDB", self));
       	self.$option_id.find("form[name=drop_db_form]").validate({
            submitHandler: function (form) {
                var $form = $(form),
                    fields = $form.serializeArray(),
                    $db_list = $form.find('select[name=drop_db]'),
                    db = $db_list.val();

                if (!confirm("Do you really want to delete the database: " + db + " ?")) {
                    return;
                }
                self.rpc("/base/database/drop", {'fields': fields}, function(result) {
                    if (result.error) {
                        self.display_error(result);
                        return;
                    }
                    $db_list.find(':selected').remove();
                    self.db_list.splice(_.indexOf(self.db_list, db, true), 1);
                    self.notification.notify("Dropping database", "The database '" + db + "' has been dropped");
                });
            }
        });
    },
    wait_for_file: function (token, cleanup) {
        var self = this,
            cookie_name = 'fileToken',
            cookie_length = cookie_name.length;
        this.backup_timer = setInterval(function () {
            var cookies = document.cookie.split(';');
            for(var i=0; i<cookies.length; ++i) {
                var cookie = cookies[i].replace(/^\s*/, '');
                if(!cookie.indexOf(cookie_name) === 0) { continue; }
                var cookie_val = cookie.substring(cookie_length + 1);
                if(parseInt(cookie_val, 10) !== token) { continue; }

                // clear waiter
                clearInterval(self.backup_timer);
                // clear cookie
                document.cookie = _.sprintf("%s=;expires=%s;path=/",
                    cookie_name, new Date().toGMTString());

                if (cleanup) { cleanup(); }
            }
        }, 200);
    },
    do_backup: function() {
        var self = this;
       	self.$option_id.html(QWeb.render("BackupDB", self));

        self.$option_id.find("form[name=backup_db_form]").validate({
            submitHandler: function (form) {
                $.blockUI();
                // need to detect when the file is done downloading (not used
                // yet, but we'll need it to fix the UI e.g. with a throbber
                // while dump is being generated), iframe load event only fires
                // when the iframe content loads, so we need to go smarter:
                // http://geekswithblogs.net/GruffCode/archive/2010/10/28/detecting-the-file-download-dialog-in-the-browser.aspx
                var $target = $('#backup-target'),
                      token = new Date().getTime();
                if (!$target.length) {
                    $target = $('<iframe id="backup-target" style="display: none;">')
                        .appendTo(document.body)
                        .load(function () {
                            $.unblockUI();
                            clearInterval(self.backup_timer);
                            var error = this.contentDocument.body
                                    .firstChild.data
                                    .split('|');
                            self.display_error({
                                title: error[0],
                                error: error[1]
                            });
                        });
                }
                $(form).find('input[name=token]').val(token);
                form.submit();

                self.wait_for_file(token, function () {
                    $.unblockUI();
                });
            }
        });
    },
    do_restore: function() {
        var self = this;
       	self.$option_id.html(QWeb.render("RestoreDB", self));

       	self.$option_id.find("form[name=restore_db_form]").validate({
            submitHandler: function (form) {
                $.blockUI();
                $(form).ajaxSubmit({
                    url: '/base/database/restore',
                    type: 'POST',
                    resetForm: true,
                    success: function (body) {
                        // TODO: ui manipulations
                        // note: response objects don't work, but we have the
                        // HTTP body of the response~~

                        // If empty body, everything went fine
                        if (!body) { return; }

                        if (body.indexOf('403 Forbidden') !== -1) {
                            self.display_error({
                                title: 'Access Denied',
                                error: 'Incorrect super-administrator password'
                            })
                        } else {
                            self.display_error({
                                title: 'Restore Database',
                                error: 'Could not restore the database'
                            })
                        }
                    },
                    complete: function () {
                        $.unblockUI();
                    }
                });
            }
        });
    },
    do_change_password: function() {
        var self = this;
       	self.$option_id.html(QWeb.render("Change_DB_Pwd", self));

        self.$option_id.find("form[name=change_pwd_form]").validate({
            messages: {
                old_pwd: "Please enter your previous password",
                new_pwd: "Please enter your new password",
                confirm_pwd: {
                    required: "Please confirm your new password",
                    equalTo: "The confirmation does not match the password"
                }
            },
            submitHandler: function (form) {
                self.rpc("/base/database/change_password", {
                    'fields': $(form).serializeArray()
                }, function(result) {
                    if (result.error) {
                        self.display_error(result);
                        return;
                    }
                    self.notification.notify("Changed Password", "Password has been changed successfully");
                });
            }
        });
    }
});

openerp.base.Login =  openerp.base.Widget.extend({
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
        this.rpc("/base/database/get_list", {}, function(result) {
            self.db_list = result.db_list;
            self.display();
        }, function() {
            self.display();
        });
    },
    display: function() {
        var self = this;

        this.$element.html(QWeb.render("Login", this));
        this.database = new openerp.base.Database(
                this, "oe_database", "oe_db_options");

        this.$element.find('#oe-db-config').click(function() {
            self.database.start();
        });

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
        var $e = this.$element;
        var db = $e.find("form [name=db]").val();
        var login = $e.find("form input[name=login]").val();
        var password = $e.find("form input[name=password]").val();

        this.do_login(db, login, password);
    },
    /**
     * Performs actual login operation, and UI-related stuff
     *
     * @param {String} db database to log in
     * @param {String} login user login
     * @param {String} password user password
     */
    do_login: function (db, login, password) {
        var self = this;
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

openerp.base.Header =  openerp.base.Widget.extend({
    init: function(parent, element_id) {
        this._super(parent, element_id);
    },
    start: function() {
        return this.do_update();
    },
    do_update: function () {
        this.$element.html(QWeb.render("Header", this));
        this.$element.find(".logout").click(this.on_logout);
        return this.shortcut_load();
    },
    shortcut_load :function(){
        var self = this,
            sc = self.session.shortcuts,
            shortcuts_ds = new openerp.base.DataSet(this, 'ir.ui.view_sc');
        // TODO: better way to communicate between sections.
        // sc.bindings, because jquery does not bind/trigger on arrays...
        if (!sc.binding) {
            sc.binding = {};
            $(sc.binding).bind({
                'add': function (e, attrs) {
                    var $shortcut = $('<li>', {
                            'data-id': attrs.res_id
                        }).text(attrs.name)
                        .appendTo(self.$element.find('.oe-shortcuts ul'));
                    shortcuts_ds.create(attrs, function (out) {
                        $shortcut.data('shortcut-id', out.result);
                    });
                },
                'remove-current': function () {
                    var menu_id = self.session.active_id;
                    var $shortcut = self.$element
                            .find('.oe-shortcuts li[data-id=' + menu_id + ']');
                    var shortcut_id = $shortcut.data('shortcut-id');
                    $shortcut.remove();
                    shortcuts_ds.unlink([shortcut_id]);
                }
            });
        }
        return this.rpc('/base/session/sc_list', {}, function(shortcuts) {
            sc.splice(0, sc.length);
            sc.push.apply(sc, shortcuts);

            self.$element.find('.oe-shortcuts')
                .html(QWeb.render('Shortcuts', {'shortcuts': shortcuts}))
                .undelegate('li', 'click')
                .delegate('li', 'click', function(e) {
                    e.stopPropagation();
                    var id = $(this).data('id');
                    self.session.active_id = id;
                    self.rpc('/base/menu/action', {'menu_id':id}, function(ir_menu_data) {
                        if (ir_menu_data.action.length){
                            self.on_action(ir_menu_data.action[0][2]);
                        }
                    });
                });
        });
    },
    on_action: function(action) {
    },

    on_logout: function() {
        this.$element.find('.oe-shortcuts ul').empty();
    }
});

openerp.base.Menu =  openerp.base.Widget.extend({
    init: function(parent, element_id, secondary_menu_id) {
        this._super(parent, element_id);
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
            this.session.active_id = id;
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

openerp.base.Homepage = openerp.base.Widget.extend({
});

openerp.base.Preferences = openerp.base.Widget.extend({
});

openerp.base.WebClient = openerp.base.Widget.extend({
    init: function(element_id) {
        this._super(null, element_id);
        openerp.webclient = this;

        QWeb.add_template("/base/static/src/xml/base.xml");
        var params = {};
        if(jQuery.param != undefined && jQuery.deparam(jQuery.param.querystring()).kitten != undefined) {
            this.$element.addClass("kitten-mode-activated");
        }
        this.$element.html(QWeb.render("Interface", params));

        this.session = new openerp.base.Session();
        this.loading = new openerp.base.Loading(this,"oe_loading");
        this.crashmanager =  new openerp.base.CrashManager(this);
        this.crashmanager.start();

        // Do you autorize this ? will be replaced by notify() in controller
        openerp.base.Widget.prototype.notification = new openerp.base.Notification(this, "oe_notification");

        this.header = new openerp.base.Header(this, "oe_header");
        this.login = new openerp.base.Login(this, "oe_login");
        this.header.on_logout.add(this.login.on_logout);

        this.session.on_session_invalid.add(this.login.do_ask_login);
        this.session.on_session_valid.add_last(this.header.do_update);
        this.session.on_session_valid.add_last(this.on_logged);

        this.menu = new openerp.base.Menu(this, "oe_menu", "oe_secondary_menu");
        this.menu.on_action.add(this.on_menu_action);
        this.header.on_action.add(this.on_menu_action);
    },
    start: function() {
        this.session.start();
        this.header.start();
        this.login.start();
        this.menu.start();
        this.notification.notify("OpenERP Client", "The openerp client has been initialized.");
    },
    on_logged: function() {
        if(this.action_manager)
            this.action_manager.stop();
        this.action_manager = new openerp.base.ActionManager(this);
        this.action_manager.appendTo($("#oe_app"));

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

        // not logged in
        if (!this.session.uid) { return; }
        var ds = new openerp.base.DataSetSearch(this, 'res.users');
        ds.read_ids([this.session.uid], ['action_id'], function (users) {
            var home_action = users[0].action_id;
            if (!home_action) {
                self.default_home();
                return;
            }
            self.execute_home_action(home_action[0], ds);
        })
    },
    default_home: function () {
    },
    /**
     * Bundles the execution of the home action
     *
     * @param {Number} action action id
     * @param {openerp.base.DataSet} dataset action executor
     */
    execute_home_action: function (action, dataset) {
        var self = this;
        this.rpc('/base/action/load', {
            action_id: action,
            context: dataset.get_context()
        }, function (meh) {
            var action = meh.result;
            action.context = _.extend(action.context || {}, {
                active_id: false,
                active_ids: [false],
                active_model: dataset.model
            });
            self.action_manager.do_action(action);
        });
    },
    on_menu_action: function(action) {
        this.action_manager.do_action(action);
    },
    do_about: function() {
    }
});

};

// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax:
