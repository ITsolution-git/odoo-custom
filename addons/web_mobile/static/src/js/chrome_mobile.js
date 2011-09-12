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
        this.login = new openerp.web_mobile.Login(this, "oe_login");
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

        this.menu = new openerp.web_mobile.Menu(this, "oe_menu", "oe_secondary_menu");
        this.menu.start();
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

openerp.web_mobile.Header =  openerp.web.Widget.extend({
    init: function(session, element_id) {
        this._super(session, element_id);
    },
    start: function() {
        this.$element.html(QWeb.render("Header", this));
    }
});

openerp.web_mobile.Footer =  openerp.web.Widget.extend({
    init: function(session, element_id) {
        this._super(session, element_id);
    },
    start: function() {
        this.$element.html(QWeb.render("Footer", this));
    }
});

openerp.web_mobile.Shortcuts =  openerp.web.Widget.extend({
    init: function(session, element_id) {
        this._super(session, element_id);
    },
    start: function() {
        var self = this;
        this.rpc('/web/session/sc_list',{} ,function(res){
            self.$element.html(QWeb.render("Shortcuts", {'sc' : res}))

            self.$element.find("[data-role=header]").find('h1').html('Favourite');
            self.$element.find("[data-role=header]").find('#home').click(function(){
                $.mobile.changePage($("#oe_menu"), "slide", true, true);
            });
            self.$element.find('#content').find("a").click(self.on_clicked);
            self.$element.find("[data-role=footer]").find('#preference').click(function(){
                if(!$('#oe_options').html().length){
                    this.options = new openerp.web_mobile.Options(self, "oe_options");
                    this.options.start();
                }
                else{
                    $.mobile.changePage($("#oe_options"), "slide", true, true);
                }
            });
            $.mobile.changePage($("#oe_shortcuts"), "slide", true, true);
        });
    },
    on_clicked: function(ev) {
        $shortcut = $(ev.currentTarget);
        id = $shortcut.data('menu');
        res_id = $shortcut.data('res');
        this.listview = new openerp.web_mobile.ListView(this, "oe_list", res_id);
        this.listview.start();
        jQuery("#oe_header").find("h1").html($shortcut.data('name'));
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
        var self = this;
        this.data = data;

        this.header = new openerp.web_mobile.Header(this, "oe_header");
        this.header.start();
        this.footer = new openerp.web_mobile.Footer(this, "oe_footer");
        this.footer.start();

        this.$element.html(QWeb.render("Menu", this.data));
        this.$element.find("[data-role=header]").find('h1').html('Application');
        this.$element.find("[data-role=footer]").find('#shrotcuts').click(function(){
            if(!$('#oe_shortcuts').html().length){
                this.shortcuts = new openerp.web_mobile.Shortcuts(self, "oe_shortcuts");
                this.shortcuts.start();
            }
            else{
                $.mobile.changePage($("#oe_shortcuts"), "slide", true, true);
            }
        });
        this.$element.find("[data-role=footer]").find('#preference').click(function(){
            if(!$('#oe_options').html().length){
                this.options = new openerp.web_mobile.Options(self, "oe_options");
                this.options.start();
            }
            else{
                $.mobile.changePage($("#oe_options"), "slide", true, true);
            }
        });
        this.$element.add(this.$secondary_menu).find("#content").find('a').click(this.on_menu_click);
        $.mobile.changePage($("#oe_menu"), "slide", true, true);
    },
    on_menu_click: function(ev, id) {
        var $menu = $(ev.currentTarget);
        id = $menu.data('menu');
        for (var i = 0; i < this.data.data.children.length; i++) {
            if (this.data.data.children[i].id == id) {
                this.children = this.data.data.children[i];
            }
        }
        this.$element
            .removeClass("login_valid")
            .addClass("secondary_menu");
            //.hide();
    /*if(!$('#oe_sec_menu').html().length){
            this.secondary = new openerp.web_mobile.Secondary(this, "oe_sec_menu", this.children);
                   this.secondary.start();
         }else{
            //console.log('heree>>>>>>>>>>>>>>>>>>',$('#'+$('.ui-page-active').attr('id')));
            var id=$('.ui-page-active').attr('id');
            //console.log('heree>>>>>>>>>>>>>>>>>>',$('#'+id).removeClass('ui-page-active'));

            this.secondary = new openerp.web_mobile.Secondary(this, "oe_sec_menu", this.children);
            this.secondary.start();
            $('#'+id).removeClass('ui-page-active');
            $('#oe_sec_menu').addClass('ui-page-active');
            //console.log();
            $.mobile.changePage($("#oe_menu"), "slide", true, true);

            //if($('.ui-page-active').attr('id').live())
            //$.mobile.changePage($("#oe_sec_menu"), "slide", true, true);
           // this.secondary = new openerp.web_mobile.Secondary(this, "oe_sec_menu", this.children);
                  // this.secondary.start();


                   //$.mobile.loadPage();
                   //$.mobile.changePage($("#oe_sec_menu"), "slide", true, true);
            //this.$element.find("#content").find('a').attr('href','#oe_sec_menu');
         }*/
        if(!$('#oe_sec_menu').html().length){
            this.secondary = new openerp.web_mobile.Secondary(this, "oe_sec_menu", this.children);
            this.secondary.start();
        }else{
            $.mobile.changePage($("#oe_sec_menu"), "slide", true, true);
        }
    }
});
openerp.web_mobile.Secondary =  openerp.web.Widget.extend({
    init: function(session, element_id, secondary_menu_id) {
        this._super(session, element_id);
        this.data = secondary_menu_id;
    },
    start: function(ev, id) {
        var self = this;

     /*   if(this.$element.html().length){
                self.$element.find('[data-role="listview"]').remove();

                _.each(self.data.children,function(i){
                    var newul = '<ul data-dividertheme="b" class="ui-listview ui-listview-inset ui-corner-all ui-shadow" data-theme="c" data-inset="true" data-role="listview"><li data-role="list-divider">'+
                    i.name+'</li></ul>';  // Create New List Item
                    self.$element.find('#content').append(newul);
                    //console.log('in for loop',i.children);
                });
                console.log('saaasasaaa',self.$element.find('#content'),self.data);
                //self.$element.find('[data-role="listview"]').listview('refresh');
            }else{*/

        var v = { menu : this.data };

        this.$element.html(QWeb.render("Menu.secondary", v));

        this.$element.find("[data-role=header]").find("h1").html(this.data.name);
        this.$element.add(this.$secondary_menu).find('#content').find("a").click(this.on_menu_click);
        this.$element.find("[data-role=footer]").find('#shrotcuts').click(function(){
            if(!$('#oe_shortcuts').html().length){
                this.shortcuts = new openerp.web_mobile.Shortcuts(self, "oe_shortcuts");
                this.shortcuts.start();
            }
            else{
                $.mobile.changePage($("#oe_shortcuts"), "slide", true, true);
            }
        });
        this.$element.find("[data-role=footer]").find('#preference').click(function(){
            if(!$('#oe_options').html().length){
                this.options = new openerp.web_mobile.Options(self, "oe_options");
                this.options.start();
            }
            else{
                $.mobile.changePage($("#oe_options"), "slide", true, true);
            }
        });
        this.$element.find("[data-role=header]").find('#home').click(function(){
            $.mobile.changePage($("#oe_menu"), "slide", true, true);
        });

        $.mobile.changePage($("#oe_sec_menu"), "slide", true, true);
    },
    on_menu_click: function(ev, id) {
        var $menu = $(ev.currentTarget);
        id = $menu.data('menu');
        if (id) {
            this.listview = new openerp.web_mobile.ListView(this, "oe_list", id);
            this.listview.start();
        }
        jQuery("#oe_header").find("h1").html($menu.data('name'));
    }
});

openerp.web_mobile.Options =  openerp.web.Widget.extend({
    start: function() {
        var self = this;

        this.$element.html(QWeb.render("Options", this));
        this.$element.find("[data-role=header]").find('h1').html('Preference');
        this.$element.find("[data-role=footer]").find('#shrotcuts').click(function(){
            if(!$('#oe_shortcuts').html().length){
                this.shortcuts = new openerp.web_mobile.Shortcuts(self, "oe_shortcuts");
                this.shortcuts.start();
            }
            else{
                $.mobile.changePage($("#oe_shortcuts"), "slide", true, true);
                //self.$element.find("#footer").find('#shrotcuts').attr('href','#oe_shortcuts');
            }
        });
        this.$element.find("[data-role=header]").find('#home').click(function(){
            $.mobile.changePage($("#oe_menu"), "slide", true, true);
        });
        $.mobile.changePage($("#oe_options"), "slide", true, true);
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
