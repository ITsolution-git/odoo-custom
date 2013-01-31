/*---------------------------------------------------------
 * OpenERP web_linkedin (module)
 *---------------------------------------------------------*/

openerp.web_linkedin = function(instance) {
    var QWeb = instance.web.qweb;
    var _t = instance.web._t;
    
    /*
    * instance.web_linkedin.tester.test_authentication()
    * Call check if the Linkedin session is open or open a connection popup
    * return a deferrer :
    *   - resolve if the authentication is true
    *   - reject if the authentication is wrong or when the user logout
    */
    instance.web_linkedin.LinkedinTester = instance.web.Class.extend({
        init: function() {
            this.linkedin_added = false;
            this.linkedin_def = $.Deferred();
            this.auth_def = $.Deferred();
        },
        error_catcher: function (callback) {
            var self = this;
            if (!this.realError) {
                this.realError = Error;
                this.window_onerror = window.onerror;
            }
            if (!callback) {
                window.onerror = self.window_onerror;
                Error = self.realError;
            }
            this.callback = callback;
            Error = function (message, fileName, lineNumber) {
                this.name = message;
                this.message = message;
                this.fileName = fileName;
                this.lineNumber = lineNumber;
                if (Error.caller.toString().match(/API Key is invalid/)) {
                    self.callback.apply(self, [this]);
                    Error.prototype.catched = true;
                }
            };
            Error.prototype.toString = function () {return this.name;};
            Error.prototype.catched = false;
            window.onerror = function(message, fileName, lineNumber) {
                if (!Error.prototype.catched) {
                    self.window_onerror(message, fileName, lineNumber);
                }
                Error.prototype.catched = false;
            };
        },
        linkedin_disabled: function(error) {
            instance.web.dialog($(QWeb.render("LinkedIn.DisabledWarning", {'error': error})), {
                title: _t("LinkedIn is not enabled"),
                buttons: [
                    {text: _t("Ok"), click: function() { $(this).dialog("close"); }}
                ]
            });
        },
        test_linkedin: function() {
            var self = this;
            return this.test_api_key().then(function() {
                if (self.linkedin_added) {
                    return self.linkedin_def;
                }

                self.error_catcher(function (error) {
                    self.linkedin_disabled(error);
                    self.auth_def.reject();
                    self.linkedin_def.reject();
                    self.$linkedin.remove();
                    IN = false;
                    self.linkedin_added = false;
                    self.error_catcher(false);
                });

                self.$linkedin = $('<div class="oe_linkedin_login_hidden" style="display:none;"><script type="in/Login"></script></div>');
                $("body").append(self.$linkedin);
                var tag = document.createElement('script');
                tag.type = 'text/javascript';
                tag.src = "http://platform.linkedin.com/in.js";
                tag.innerHTML = 'api_key : ' + self.api_key + '\nauthorize : true\nscope: r_network r_basicprofile'; // r_contactinfo r_fullprofile r_emailaddress';
                
                document.getElementsByTagName('head')[0].appendChild(tag);
                self.linkedin_added = true;
                $(tag).load(function(event) {
                    console.debug("LinkedIn JavaScript inserted.");
                    IN.Event.on(IN, "frameworkLoaded", function() {
                        console.debug("LinkedIn DOM node inserted and frameworkLoaded.");
                    });
                    IN.Event.on(IN, "systemReady", function() {
                        self.linkedin_def.resolve();
                        console.debug("LinkedIn systemReady.");
                    });
                    IN.Event.on(IN, "auth", function() {
                        self.auth_def.resolve();
                    });
                    IN.Event.on(IN, "logout", function() {
                        self.auth_def.reject();
                        self.auth_def = $.Deferred();
                    });
                });
                return self.linkedin_def.promise();
            });
        },
        test_api_key: function() {
            var self = this;
            if (this.api_key) {
                return $.when();
            }
            return new instance.web.Model("ir.config_parameter").call("get_param", ["web.linkedin.apikey"]).then(function(a) {
                if (!!a) {
                    self.api_key = a;
                    return true;
                } else {
                    return $.Deferred().reject();
                }
            });
        },
        test_authentication: function() {
            var self = this;
           this.linkedin_def.done(function () {
                if (IN.User.isAuthorized()) {
                    self.auth_def.resolve();
                } else {
                    IN.User.authorize();
                }
            });
            return this.auth_def.promise();
        },
    });
    
    instance.web_linkedin.tester = new instance.web_linkedin.LinkedinTester();
    
    instance.web_linkedin.Linkedin = instance.web.form.FieldChar.extend({
        init: function() {
            this._super.apply(this, arguments);
            this.display_dm = new instance.web.DropMisordered(true);
        },
        initialize_content: function() {
            var $ht = $(QWeb.render("FieldChar.linkedin"));
            var $in = this.$("input");
            $in.replaceWith($ht);
            this.$(".oe_linkedin_input").append($in);
            this.$(".oe_linkedin_img").click(_.bind(this.search_linkedin, this));
            this._super();
        },
        search_linkedin: function() {
            var self = this;
            this.display_dm.add(instance.web_linkedin.tester.test_linkedin()).done(function() {
                var text = (self.get("value") || "").replace(/^\s+|\s+$/g, "").replace(/\s+/g, " ");
                instance.web_linkedin.tester.test_authentication().done(function() {
                    var pop = new instance.web_linkedin.LinkedinSearchPopup(self, text);
                    pop.open();
                    pop.on("selected", this, function(entity) {
                        self.selected_entity(entity);
                    });
                });
            });
        },
        selected_entity: function(entity) {
            var self = this;
            this.create_on_change(entity).done(function(to_change) {
                var values = self.view.get_fields_values();
                _.each(to_change, function (value, key) {
                    if (!/linkedin/.test(key) && !!values[key]) {
                        if(_.isArray(values[key])) {

                        } else {
                            delete to_change[key];
                        }
                    }
                })
                self.view.set_values(to_change);
            });
        },
        create_on_change: function(entity) {
            return entity.__type === "company" ? this.create_or_modify_company(entity) : this.create_or_modify_partner(entity);
        },
        create_or_modify_company: function (entity) {
            var self = this;
            var to_change = {};
            var defs = [];
            to_change.is_company = true;
            to_change.name = entity.name;
            to_change.image = false;
            if (entity.logoUrl) {
                defs.push(self.rpc('/web_linkedin/binary/url2binary',
                                   {'url': entity.logoUrl}).then(function(data){
                    to_change.image = data;
                }));
            }
            to_change.website = entity.websiteUrl;
            to_change.phone = false;
            _.each((entity.locations || {}).values || [], function(el) {
                to_change.phone = el.contactInfo.phone1;
            });
            to_change.linkedin_url = _.str.sprintf("http://www.linkedin.com/company/%d", entity.id);

            _.each(to_change, function (val, key) {
                if (self.field_manager.datarecord[key]) {
                    to_change[key] = self.field_manager.datarecord[key];
                }
            });

            to_change.child_ids = [];
            var children_def = $.Deferred();
            defs.push(children_def);
            IN.API.PeopleSearch().fields(commonPeopleFields).params({
                    "company-name" : entity.universalName,
                    "current-company": true,
                    "count": 50,
                }).result(function (result) {
                    console.debug("Linkedin pepople in this company found :", result.numResults, "=>", result.people._count, result.people.values);
                    result = _.reject(result.people.values || [], function(el) {
                        return ! el.formattedName;
                    });
                    var defs = [];
                    _.each(result, function (el) {
                        el.__type = "people";
                        el.parent_id = self.field_manager.datarecord.id || false;
                        defs.push(self.create_or_modify_partner(el, true).then(function (data) {
                            // [0,0,data] if it's a new partner
                            to_change.child_ids.push( data.id ? [1, data.id, data] : [0, 0, data] );
                        }));
                    });
                    $.when.apply($, defs).then(function () {
                        children_def.resolve();
                    });
                }).error(function () {
                    children_def.reject();
                });
            
            return $.when.apply($, defs).then(function () {
                return to_change;
            });
        },
        create_or_modify_partner: function (entity, rpc_search_similar_partner) {
            var self = this;
            var to_change = {};
            var defs = [];
            to_change.is_company = false;
            to_change.name = entity.formattedName;
            if (entity.pictureUrl) {
                defs.push(self.rpc('/web_linkedin/binary/url2binary',
                                   {'url': entity.pictureUrl}).then(function(data){
                    to_change.image = data;
                }));
            }
            _.each((entity.phoneNumbers || {}).values || [], function(el) {
                if (el.phoneType === "mobile") {
                    to_change.mobile = el.phoneNumber;
                } else {
                    to_change.phone = el.phoneNumber;
                }
            });
            var positions = (entity.positions || {}).values || [];
            if (positions.length && positions[0].isCurrent) {
                to_change.function = positions[0].title;
                if (!entity.parent_id) {
                    var company_name = positions[0].company ? positions[0].company.name : false;
                    if (company_name) {
                        defs.push(new instance.web.DataSetSearch(this, 'res.partner').call("search", [[["name", "=", company_name]]]).then(function (data) {
                            if(data[0]) to_change.parent_id = data[0];
                        }));
                    }
                }
            }
            if (entity.parent_id) {
                to_change.parent_id = entity.parent_id;
            }
            to_change.linkedin_url = to_change.linkedin_public_url = entity.publicProfileUrl || false;
            to_change.linkedin_id = entity.id || false;

            // find similar partners
            if (rpc_search_similar_partner) {
                defs.push(new instance.web.DataSetSearch(this, 'res.partner').call("search", [[ 
                        "|", ["linkedin_id", "=", to_change.linkedin_id], "&", ["linkedin_id", "=", false],
                        "|", ["name", "ilike", entity.firstName +"%"+ entity.lastName], ["name", "ilike", entity.lastName +"%"+ entity.firstName] 
                    ]]).then(function (data) {
                    to_change.id = data[0] || false;
                    if (to_change.id) {
                        // remove data if allready set
                        defs.push(new instance.web.DataSetSearch(this, 'res.partner').call("read", [[to_change.id], [
                            "image",
                            "mobile",
                            "phone",
                            "parent_id",
                            "name",
                            "email",
                            "function",
                            "linkedin_id",
                        ]]).then(function (partners) {
                            if (partners[0].linkedin_id && partners[0].linkedin_id != to_change.linkedin_id) {
                                delete to_change.id;
                            } else {
                                _.each(partners[0], function (val, key) {
                                    if (val) {
                                        to_change[key] = val;
                                    }
                                });
                            }
                        }));
                    }
                }));
            } else {
                _.each(to_change, function (val, key) {
                    if (self.field_manager.datarecord[key]) {
                        to_change[key] = self.field_manager.datarecord[key];
                    }
                });
            }
            
            return $.when.apply($, defs).then(function () {
                return to_change;
            });
        },
    });
    
    instance.web.form.widgets.add('linkedin', 'instance.web_linkedin.Linkedin');
    
    var commonPeopleFields = ["id", "picture-url", "public-profile-url", "first-name", "last-name",
                            "formatted-name", "location", "phone-numbers", "im-accounts",
                            "main-address", "headline", "positions", "summary", "specialties"];
    
    instance.web_linkedin.LinkedinSearchPopup = instance.web.Dialog.extend({
        template: "Linkedin.popup",
        init: function(parent, search) {
            var self = this;
            if (!IN.User.isAuthorized()) {
                this.$buttons = $("<div/>");
                this.destroy();
            }
            this._super(parent, { 'title': QWeb.render('LinkedIn.AdvancedSearch', {'title': _t("LinkedIn search")}) });
            this.search = search;
            this.limit = 5;
        },
        start: function() {
            this._super();
            this.bind_event();
            this.display_account();
            this.do_search();
        },
        bind_event: function() {
            var self = this;
            this.$el.parent().on("click", ".oe_linkedin_logout", function () {
                IN.User.logout();
                self.destroy();
            });
            this.$search = this.$el.parent().find(".oe_linkedin_advanced_search" );
            this.$url = this.$search.find("input[name='search']" );
            this.$button = this.$search.find("button");

            this.$button.on("click", function (e) {
                e.stopPropagation();
                self.do_search(self.$url.val() || '');
            });
            this.$url
                .on("click mousedown mouseup", function (e) {
                    e.stopPropagation();
                }).on("keydown", function (e) {
                    if(e.keyCode == 13) {
                        $(e.target).blur();
                        self.$button.click();
                    }
                });
        },
        display_account: function() {
            var self = this;
            IN.API.Profile("me")
                .fields(["firstName", "lastName"])
                .result(function (result) {
                    $(QWeb.render('LinkedIn.loginInformation', result.values[0])).appendTo(self.$el.parent().find(".ui-dialog-buttonpane"));   
            })
        },
        do_search: function(url) {
            if (!IN.User || !IN.User.isAuthorized()) {
                this.destroy();
            }
            var self = this;
            var deferrers = [];
            this.$(".oe_linkedin_pop_c, .oe_linkedin_pop_p").empty();

            if (url && url.length) {
                var deferrer_c = $.Deferred();
                var deferrer_p = $.Deferred();
                deferrers.push(deferrer_c, deferrer_p);

                var url = url.replace(/\/+$/, '');
                var uid = url.replace(/(.*linkedin\.com\/[a-z]+\/)|(^.*\/company\/)|(\&.*$)/gi, '');

                IN.API.Raw(_.str.sprintf(
                        "companies/universal-name=%s:(id,name,logo-url,description,industry,website-url,locations,universal-name)",
                        encodeURIComponent(uid.toLowerCase()))).result(function (result) {
                    self.do_result_companies({'companies': {'values': [result]}});
                    deferrer_c.resolve();
                }).error(function (error) {
                    self.do_result_companies({});
                    deferrer_c.resolve();
                });

                var url_public = "http://www.linkedin.com/pub/"+uid;
                IN.API.Profile("url="+ encodeURI(url_public).replace(/%2F/g, '/'))
                    .fields(commonPeopleFields)
                    .result(function(result) {
                        self.do_result_people({'people': result});
                        deferrer_p.resolve();
                }).error(function (error) {
                    self.do_warn( _t("LinkedIn error"), _t("LinkedIn is temporary down for the searches by url."));
                    self.do_result_people({});
                    deferrer_p.resolve();
                });

                this.search = url;
            }

            var deferrer_c_k = $.Deferred();
            var deferrer_p_k = $.Deferred();
            deferrers.push(deferrer_c_k, deferrer_p_k);
            IN.API.Raw(_.str.sprintf(
                    "company-search:(companies:" +
                    "(id,name,logo-url,description,industry,website-url,locations,universal-name))?keywords=%s&count=%d",
                    encodeURI(this.search), this.limit)).result(function (result) {
                self.do_result_companies(result);
                deferrer_c_k.resolve();
            });
            IN.API.PeopleSearch().fields(commonPeopleFields).params({"keywords": this.search, "count": this.limit}).result(function(result) {
                self.do_result_people(result);
                deferrer_p_k.resolve();
            });

            return $.when.apply($, deferrers);
        },
        do_result_companies: function(companies) {
            var lst = (companies.companies || {}).values || [];
            lst = _.first(lst, this.limit);
            lst = _.map(lst, function(el) {
                el.__type = "company";
                return el;
            });
            console.debug("Linkedin companies found:", (companies.companies || {})._total, '=>', lst.length, lst);
            return this.display_result(lst, this.$(".oe_linkedin_pop_c"));
        },
        do_result_people: function(people) {
            var plst = (people.people || {}).values || [];
            plst = _.first(plst, this.limit);
            plst = _.map(plst, function(el) {
                el.__type = "people";
                return el;
            });
            console.debug("Linkedin people found:", people.numResults, '=>', plst.length, plst);
            return this.display_result(plst, this.$(".oe_linkedin_pop_p"));
        },
        display_result: function(result, $elem) {
            var self = this;
            var $row;
            $elem.find(".oe_no_result").remove();
            _.each(result, function(el) {
                var pc = new instance.web_linkedin.EntityWidget(self, el);
                if (!$elem.find("div").size() || $elem.find(" > div:last > div").size() >= 5) {
                    $row = $("<div style='display: table-row;width:100%'/>");
                    $row.appendTo($elem);
                }
                pc.appendTo($row);
                pc.$el.css("display", "table-cell");
                pc.$el.css("width", "20%");
                pc.on("selected", self, function(data) {
                    self.trigger("selected", data);
                    self.destroy();
                });
            });
            if (!$elem.find("div").size()) {
                $elem.append($('<div class="oe_no_result">').text(_t("No results found")));
            }
        },
        
    });
    
    instance.web_linkedin.EntityWidget = instance.web.Widget.extend({
        template: "Linkedin.EntityWidget",
        init: function(parent, data) {
            this._super(parent);
            this.data = data;
        },
        start: function() {
            var self = this;
            this.$el.click(function() {
                self.trigger("selected", self.data);
            });
            if (this.data.__type === "company") {
                this.$("h3").text(this.data.name);
                self.$("img").attr("src", this.data.logoUrl);
                self.$(".oe_linkedin_entity_headline").text(this.data.industry);
            } else { // people
                this.$("h3").text(this.data.formattedName);
                self.$("img").attr("src", this.data.pictureUrl);
                self.$(".oe_linkedin_entity_headline").text(this.data.headline);
            }
        },
    });
};
// vim:et fdc=0 fdl=0:
