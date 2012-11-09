openerp.auth_oauth = function(instance) {
    var QWeb = instance.web.qweb;

    instance.web.Login.include({
        start: function(parent, params) {
            var self = this;
            var d = this._super.apply(this, arguments);
            this.$el.on('click', 'a.zocial', this.on_oauth_sign_in);
            this.oauth_providers = [];
            if(this.params.oauth_error === 1) {
                this.do_warn("Sign up error.","Sign up is not allowed on this database.");
            } else if(this.params.oauth_error === 2) {
                this.do_warn("Authentication error","");
            }
            return d.done(this.do_oauth_load).fail(function() {
                self.do_oauth_load([]);
            });
        },
        on_db_loaded: function(result) {
            this._super.apply(this, arguments);
            this.$("form [name=db]").change(this.do_oauth_load);
        },
        do_oauth_load: function() {
            var db = this.$("form [name=db]").val();
            if (db) {
                this.rpc("/auth_oauth/list_providers", { dbname: db }).done(this.on_oauth_loaded);
            }
        },
        on_oauth_loaded: function(result) {
            this.oauth_providers = result;
            this.$('.oe_oauth_provider_login_button').remove();
            var buttons = QWeb.render("auth_oauth.Login.button",{"widget":this});
            this.$(".oe_login_pane form ul").after(buttons);
        },
        on_oauth_sign_in: function(ev) {
            ev.preventDefault();
            var index = $(ev.target).data('index');
            var p = this.oauth_providers[index];
            var ret = location.protocol+"//"+location.host+"/";
            var dbname = self.$("form [name=db]").val();
            var state_object = {
                d: dbname,
                p: p.id
            };
            var state = JSON.stringify(state_object);
            var params = {
                response_type: 'token',
                client_id: p.client_id,
                redirect_uri: ret,
                scope: p.scope,
                state: state,
            };
            var url = p.auth_endpoint + '?' + $.param(params);
            window.location = url;
        },
    });

    instance.web.WebClient = instance.web.WebClient.extend({
        start: function() {
            this._super.apply(this, arguments);
            var params = $.deparam(window.location.hash.substring(1));
            // alert(JSON.stringify(params));
            if (params.hasOwnProperty('access_token')) {
                var url = "/auth_oauth/signin" + '?' + $.param(params);
                window.location = url;
            }
        },
    });

};
