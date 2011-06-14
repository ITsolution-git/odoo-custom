
openerp.web_mobile = function(openerp) {
    
openerp.web_mobile = {};
    
openerp.web_mobile.MobileWebClient = openerp.base.Controller.extend({
    init: function(element_id) {
        var self = this;
        this._super(null, element_id);
        QWeb.add_template("xml/web_mobile.xml");
        var params = {};

        this.$element.html(QWeb.render("WebClient", {}));
        this.session = new openerp.base.Session("oe_errors");
        this.crashmanager =  new openerp.base.CrashManager(this.session);
        this.login = new openerp.web_mobile.Login(this.session, "oe_app");

        this.session.on_session_invalid.add(this.login.do_ask_login);
       
    },
    start: function() {
        this.session.start();
        this.login.start();
    }
});

openerp.web_mobile.mobilewebclient = function(element_id) {
    // TODO Helper to start mobile webclient rename it openerp.base.webclient
    var client = new openerp.web_mobile.MobileWebClient(element_id);
    client.start();
    return client;
};

openerp.web_mobile.Header =  openerp.base.Controller.extend({
    init: function(session, element_id) {
        this._super(session, element_id);
    },
    start: function() {
        this.$element.html(QWeb.render("Header", this));
        this.$element.find("a").click(this.on_clicked);
    },
    on_clicked: function(ev) {
        $opt = $(ev.currentTarget);
        current_id = $opt.attr('id');
        if (current_id == 'home') {
            this.homepage = new openerp.web_mobile.Login(this.session, "oe_app");
            this.homepage.on_login_valid();
        }
    }
    
});

openerp.web_mobile.Shortcuts =  openerp.base.Controller.extend({
    init: function(session, element_id) {
        this._super(session, element_id);
    },
    start: function() {
        var self = this;
        this.rpc('/base/session/sc_list',{} ,function(res){
            self.$element.html(QWeb.render("Shortcuts", {'sc' : res}))
            self.$element.find("a").click(self.on_clicked);
        })
    },
    on_clicked: function(ev) {
        $shortcut = $(ev.currentTarget);
        id = $shortcut.data('menu');
        res_id = $shortcut.data('res');
        jQuery("#oe_header").find("h1").html($shortcut.data('name'));
        this.listview = new openerp.web_mobile.ListView(this.session, "oe_app", res_id);
        this.listview.start();
    }
});

openerp.web_mobile.ListView = openerp.base.Controller.extend({
    init: function(session, element_id, list_id) {
        this._super(session, element_id);
        this.list_id = list_id;
    },
    start: function() {
        this.rpc('/base/menu/action', {'menu_id': this.list_id},
                    this.on_menu_action_loaded);
    },
    on_menu_action_loaded: function(data) {
        var self = this;
        if (data.action.length) {
            var action = data.action[0][2];
            self.on_action(action);
        }
    },
    on_action: function(action) {
        var self = this;
        var view_id = action.views[0][0];
        var model = action.res_model;

        self.rpc('/base/dataset/search_read', {
            model: model
            },function(result){
                this.listview = new openerp.web_mobile.ListView(this.session, "oe_app");
                self.$element.html(QWeb.render("ListView", {'records' : result}));
            });
    }
 });

openerp.web_mobile.Secondary =  openerp.base.Controller.extend({
    init: function(session, element_id, secondary_menu_id) {
        this._super(session, element_id);
        this.data = secondary_menu_id;
    },
    start: function(ev, id) {
        var v = { menu : this.data };
        this.$element.html(QWeb.render("Menu.secondary", v));
        this.$element.add(this.$secondary_menu).find("a").click(this.on_menu_click);
    },
    on_menu_click: function(ev, id) {
        $menu = $(ev.currentTarget);
        id = $menu.data('menu');
        for (var i = 0; i < this.data.children.length; i++) {
            if (this.data.children[i].id == id) {
                this.children = this.data.children[i];
            }
        }
        jQuery("#oe_header").find("h1").html($menu.data('name'));

        var child_len = this.children.children.length;
        if (child_len > 0) {
            this.$element
                .removeClass("secondary_menu")
                .addClass("content_menu");
                //.hide();
            this.secondary = new openerp.web_mobile.Secondary(this.session, "oe_app", this.children);
            this.secondary.start();
        }
        else {
            if (id) {
            this.listview = new openerp.web_mobile.ListView(this.session, "oe_app", id);
            this.listview.start();
            }
        }
    }
});

openerp.web_mobile.Menu =  openerp.base.Controller.extend({
    init: function(session, element_id, secondary_menu_id) {
        this._super(session, element_id);
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
        this.$element.add(this.$secondary_menu).find("a").click(this.on_menu_click);
    },
    on_menu_click: function(ev, id) {
        $menu = $(ev.currentTarget);
        id = $menu.data('menu');
        for (var i = 0; i < this.data.data.children.length; i++) {
            if (this.data.data.children[i].id == id) {
                this.children = this.data.data.children[i];
            }
        }
        jQuery("#oe_header").find("h1").html($menu.data('name'));
        this.$element
            .removeClass("login_valid")
            .addClass("secondary_menu");
            //.hide();
        this.secondary = new openerp.web_mobile.Secondary(this.session, "oe_app", this.children);
        this.secondary.start();
    }
});

openerp.web_mobile.Options =  openerp.base.Controller.extend({
    init: function(session, element_id) {
        this._super(session, element_id);
    },
    start: function() {
        var self = this;
        this.$element.html(QWeb.render("Options", this));
        self.$element.find("#logout").click(self.on_logout);
    },
    on_logout: function(ev) {
        this.session.logout();
        this.login = new openerp.web_mobile.Login(this.session, "oe_app");
        this.login.start();
    }
});
openerp.web_mobile.Login =  openerp.base.Controller.extend({
    init: function(session, element_id) {
        this._super(session, element_id);
    },
    start: function() {
        var self = this;

        jQuery("#oe_header").children().remove();
        this.rpc("/base/session/get_databases_list", {}, function(result) {
            self.db_list = result.db_list;
            self.$element.html(QWeb.render("Login", self));
            self.$element.find('#database').click(self.on_db_select);
            self.$element.find("#login").click(self.on_login);
            $.mobile.initializePage();
        })
    },
    on_db_select: function(ev) {
        var db = this.$element.find("#database option:selected").val();
        jQuery("#db_text").html(db);
    },
    on_login: function(ev) {
        ev.preventDefault();
        var self = this;
        var $e = this.$element;
        var db = $e.find("div select[name=database]").val();
        var login = $e.find("div input[name=login]").val();
        var password = $e.find("div input[name=password]").val();
        //$e.hide();
        // Should hide then call callback
        this.session.session_login(db, login, password, function() {
            if(self.session.session_is_valid()) {
                self.on_login_valid();
            } else {
                self.on_login_invalid();
            }
        });
    },
    on_login_invalid: function() {
        this.$element
            .removeClass("login_valid")
            .addClass("login_invalid")
            .show();
    },
    on_login_valid: function() {
        this.$element
            .removeClass("login_invalid")
            .addClass("login_valid");
            //.hide();
        this.$element.html(QWeb.render("HomePage", {}));
        this.header = new openerp.web_mobile.Header(this.session, "oe_header");
        this.shortcuts = new openerp.web_mobile.Shortcuts(this.session, "oe_shortcuts");
        this.menu = new openerp.web_mobile.Menu(this.session, "oe_menu", "oe_secondary_menu");
        this.options = new openerp.web_mobile.Options(this.session, "oe_options");
        this.header.start();
        this.shortcuts.start();
        this.menu.start();
        this.options.start();
        jQuery("#oe_header").find("h1").html('Home');

    },
    do_ask_login: function(continuation) {
        this.on_login_invalid();
        this.on_login_valid.add({
            position: "last",
            unique: true,
            callback: continuation
        });
    }
});
    
};
