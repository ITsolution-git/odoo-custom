/*---------------------------------------------------------
 * OpenERP Web Mobile chrome
 *---------------------------------------------------------*/

openerp.web_mobile.chrome_mobile = function(openerp) {

openerp.web_mobile.mobilewebclient = function(element_id) {
    // TODO Helper to start mobile webclient rename it openerp.web.webclient
    var client = new openerp.web_mobile.MobileWebClient(element_id);
    client.start();
    return client;
};

openerp.web_mobile.MobileWebClient = openerp.web.Widget.extend({
    init: function(element_id) {
        this._super(null, element_id);
        QWeb.add_template("xml/web_mobile.xml");
        var params = {};
        this.$element.html(QWeb.render("WebClient", {}));
        this.session = new openerp.web.Session("oe_errors");
        this.crashmanager =  new openerp.web.CrashManager(this);
        this.login = new openerp.web_mobile.Login(this, "oe_app");
//        this.session.on_session_invalid.add(this.login.do_ask_login);
    },
    start: function() {
        this.session.start();
        this.login.start();
    }
});

openerp.web_mobile.Login =  openerp.web.Widget.extend({
    start: function() {
        var self = this;
        jQuery("#oe_header").children().remove();
        this.rpc("/web/database/get_list", {}, function(result) {
            var selection = new openerp.web_mobile.Selection();
            self.db_list = result.db_list;
            self.$element.html(QWeb.render("Login", self));
            self.$element.find("#login_btn").click(self.on_login);
            $.mobile.initializePage();
        });
        this.$element
            .removeClass("login_invalid");
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
        this.homepage = new openerp.web_mobile.HomePage(this, "oe_app");
        this.homepage.start();
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

openerp.web_mobile.HomePage =  openerp.web.Widget.extend({
    init: function(session, element_id) {
        this._super(session, element_id);
    },
    start: function() {
        this.$element.html(QWeb.render("HomePage", {}));
        this.header = new openerp.web_mobile.Header(this, "oe_header");
        this.shortcuts = new openerp.web_mobile.Shortcuts(this, "oe_shortcuts");
        this.menu = new openerp.web_mobile.Menu(this, "oe_menu", "oe_secondary_menu");
        this.options = new openerp.web_mobile.Options(this, "oe_options");
        this.header.start();
        this.shortcuts.start();
        this.menu.start();
        this.options.start();
        jQuery("#oe_header").find("h1").html('Home');
        this.$element.find("a").click(this.on_clicked);
    }
});

openerp.web_mobile.Header =  openerp.web.Widget.extend({
    init: function(session, element_id) {
        this._super(session, element_id);
    },
    start: function() {
        var self = this;
        self.$element.html(QWeb.render("Header", this));
        self.$element.find("a").click(this.on_clicked);
    },
    on_clicked: function(ev) {
        var $opt = $(ev.currentTarget);
        var current_id = $opt.attr('id');
        if (current_id == 'home') {
            this.homepage = new openerp.web_mobile.HomePage(this, "oe_app");
            this.homepage.start();
        }
    }
});

openerp.web_mobile.Shortcuts =  openerp.web.Widget.extend({
    init: function(session, element_id) {
        this._super(session, element_id);
    },
    start: function() {
        var self = this;
        this.rpc('/web/session/sc_list',{} ,function(res){
            self.$element.html(QWeb.render("Shortcuts", {'sc' : res}));
            self.$element.find("a").click(self.on_clicked);
        })
    },
    on_clicked: function(ev) {
        var $shortcut = $(ev.currentTarget);
        var id = $shortcut.data('menu');
        var res_id = $shortcut.data('res');
        jQuery("#oe_header").find("h1").html($shortcut.data('name'));
        this.listview = new openerp.web_mobile.ListView(this, "oe_app", res_id);
        this.listview.start();
    }
});

openerp.web_mobile.Menu =  openerp.web.Widget.extend({
    init: function(session, element_id, secondary_menu_id) {
        this._super(session, element_id);
        this.secondary_menu_id = secondary_menu_id;
        this.$secondary_menu = $("#" + secondary_menu_id);
        this.menu = false;
    },
    start: function() {
        this.rpc("/web/menu/load", {}, this.on_loaded);
    },
    on_loaded: function(data) {
        this.data = data;
        this.$element.html(QWeb.render("Menu", this.data));
        this.$element.add(this.$secondary_menu).find("a").click(this.on_menu_click);
    },
    on_menu_click: function(ev, id) {
        var $menu = $(ev.currentTarget);
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
        this.secondary = new openerp.web_mobile.Secondary(this, "oe_app", this.children);
        this.secondary.start();
    }
});

openerp.web_mobile.Secondary =  openerp.web.Widget.extend({
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
        var $menu = $(ev.currentTarget);
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
            this.secondary = new openerp.web_mobile.Secondary(this, "oe_app", this.children);
            this.secondary.start();
        }
        else {
            if (id) {
                this.listview = new openerp.web_mobile.ListView(this, "oe_app", id);
                this.listview.start();
            }
        }
    }
});

openerp.web_mobile.Options =  openerp.web.Widget.extend({
    start: function() {
        var self = this;
        this.$element.html(QWeb.render("Options", this));
        self.$element.find("#logout").click(self.on_logout);
    },
    on_logout: function(ev) {
        this.session.logout();
//        this.login = new openerp.web_mobile.Login(this, "oe_app");
//        this.login.start();
    }
});

openerp.web_mobile.Selection = openerp.web.Widget.extend({
    on_select_option: function(ev){
        ev.preventDefault();
        var $this = ev.currentTarget;
        $($this).prev().find(".ui-btn-text").html($($this).find("option:selected").text());
    }
});
};
