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
        test_linkedin: function() {
            var self = this;
            return this.test_api_key().then(function() {
                if (self.linkedin_added) {
                    if (IN.User.isAuthorized()) {
                        self.auth_def.resolve();
                    }
                    return self.linkedin_def.resolve();
                }

                $login = $('<div class="oe_linkedin_login_hidden" style="display:none;"><script type="in/Login"></script></div>');
                $login.appendTo("body");
                $login.on("DOMNodeInserted", function (e) {
                    $login.off("DOMNodeInserted");
                    self.linkedin_def.resolve();
                    console.debug("LinkedIn DOM node is inserted.");
                });

                var tag = document.createElement('script');
                tag.type = 'text/javascript';
                tag.src = "http://platform.linkedin.com/in.js";
                tag.innerHTML = 'api_key : ' + self.api_key + '\nauthorize : true\nscope: r_network r_contactinfo r_fullprofile r_emailaddress';
                document.getElementsByTagName('head')[0].appendChild(tag);
                self.linkedin_added = true;
                $(tag).load(function() {
                    IN.Event.on(IN, "auth", function() {
                        self.auth_def.resolve();
                    });
                    IN.Event.on(IN, "logout", function() {
                        self.auth_def.reject();
                        //self.auth_def = $.Deferred();
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
           this.linkedin_def.done(function () {
                IN.User.authorize();
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
                if (text !== "") {
                    instance.web_linkedin.tester.test_authentication().done(function() {
                        var pop = new instance.web_linkedin.LinkedinPopup(self, self.get("value"));
                        pop.open();
                        pop.on("selected", this, function(entity) {
                            self.selected_entity(entity);
                        });
                    });
                } else {
                    self.focus();
                }
            }).fail(_.bind(this.linkedin_disabled, this));
        },
        linkedin_disabled: function() {
            instance.web.dialog($(QWeb.render("LinkedIn.DisabledWarning")), {
                title: _t("LinkedIn is not enabled"),
                buttons: [
                    {text: _t("Ok"), click: function() { $(this).dialog("close"); }}
                ]
            });
        },
        selected_entity: function(entity) {
            var self = this;
            this.create_on_change(entity).done(function(to_change) {
                self.view.set_values(to_change);
            });
        },
        create_on_change: function(entity) {
            var self = this;
            var to_change = {};
            var defs = [];
            if (entity.__type === "company") {
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
                var children_def = $.Deferred();
                IN.API.PeopleSearch().fields(commonPeopleFields).params({
                        "company-name" : entity.name,
                        "current-company": true,
                        "count": 25,
                    }).result(function(result) {
                        children_def.resolve(result);
                    }).error(function() {
                        children_def.reject();
                    });
                defs.push(children_def.then(function(result) {
                    result = _.reject(result.people.values || [], function(el) {
                        return ! el.formattedName;
                    });
                    var defs = _.map(result, function(el) {
                        el.__type = "people";
                        return self.create_on_change(el);
                    });
                    return $.when.apply($, defs).then(function() {
                        var p_to_change = _.toArray(arguments);
                        to_change.child_ids = p_to_change;
                    });
                }, function() {
                    return $.when();
                }));

                to_change.linkedinUrl = _.str.sprintf("http://www.linkedin.com/company/%d", entity.id);
            } else { // people
                to_change.is_company = false;
                to_change.name = entity.formattedName;
                to_change.image = false;
                if (entity.pictureUrl) {
                    defs.push(self.rpc('/web_linkedin/binary/url2binary',
                                       {'url': entity.pictureUrl}).then(function(data){
                        to_change.image = data;
                    }));
                }
                to_change.mobile = false;
                to_change.phone = false;
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
                    var company_name = positions[0].company ? positions[0].company.name : false;
                    if (company_name) {
                        defs.push(new instance.web.DataSetSearch(this, 'res.partner').call("search", [[["name", "=", company_name]]]).then(function (data) {
                            to_change.parent_id = data[0] || false;
                        }));
                    }
                }

                to_change.linkedinUrl = entity.publicProfileUrl;
                to_change.linkedinId = entity.id;
                to_change.linkedinId = entity.id;
                var country_code = (entity.location && entity.location.country && entity.location.country.code) || false;
                if (country_code) {
                    defs.push(new instance.web.DataSetSearch(this, 'res.country').call("search", [[["code", "=", country_code.toUpperCase()]]]).then(function (data) {
                        to_change.country_id = data[0] || false;
                    }));
                }
                to_change.comment = entity.summary;
                
            }
            return $.when.apply($, defs).then(function() {
                return to_change;
            });
        },
    });
    
    instance.web.form.widgets.add('linkedin', 'instance.web_linkedin.Linkedin');
    
    var commonPeopleFields = ["id", "picture-url", "public-profile-url",
                            "formatted-name", "location", "phone-numbers", "im-accounts",
                            "main-address", "headline", "positions", "summary", "specialties",
                            "email-address",
                            "languages", "skills", "certifications", "educations", "three-current-positions", "three-past-positions",
                            "date-of-birth", "twitter-accounts"];
    
    instance.web_linkedin.LinkedinPopup = instance.web.Dialog.extend({
        template: "Linkedin.popup",
        init: function(parent, text) {
            var self = this;
            if (!IN.User.isAuthorized()) {
                this.destroy();
            }
            this._super(parent, { 'title':_t("LinkedIn search")});
            this.text = text;
            this.limit = 5;
        },
        start: function() {
            this._super();
            var self = this;
            self.$el.parent().on("click", ".oe_linkedin_logout", function () {
                IN.User.logout();
                self.destroy();
            });
            this.display_linkedin_account();
            this.do_search();
        },
        display_linkedin_account: function() {
            var self = this;
            IN.API.Profile("me")
                .fields(["firstName", "lastName"])
                .result(function (result) {
                    $(QWeb.render('LinkedIn.loginInformation', result.values[0])).appendTo(self.$el.parent().find(".ui-dialog-buttonpane"));   
            })
        },
        do_search: function() {
            var self = this;
            var deferrers = [];
            var deferrer = $.Deferred();
            deferrers.push(deferrer);
            IN.API.Raw(_.str.sprintf(
                    "company-search:(companies:" +
                    "(id,name,logo-url,description,industry,website-url,locations))?keywords=%s&count=%d",
                    encodeURI(this.text), this.limit)).result(function (result) {
                self.do_result_companies(result);
                deferrer.resolve();
            });
            var deferrer = $.Deferred();
            deferrers.push(deferrer);
            IN.API.PeopleSearch().fields(commonPeopleFields).
                params({"keywords": this.text, "facet": ["network,F,S,A,O"], "count": this.limit}).result(function(result) {
                self.do_result_people(result);
                deferrer.resolve();
            });
            // new search for pass the restriction on LinkedIn (2012: search only on first and second level if it's not the last-name and first-name search)
            var deferrer = $.Deferred();
            deferrers.push(deferrer);
            IN.API.PeopleSearch().fields(commonPeopleFields).
                params({"first-name": this.text.split(' ')[0], "last-name": this.text.split(' ').slice(1).join(' '), "facet": ["network,F,S,A,O"], "count": this.limit}).result(function(result) {
                self.do_result_people(result);
                deferrer.resolve();
            });
            return $.when.apply($, deferrers);
        },
        do_result_companies: function(companies) {
            var lst = companies.companies.values || [];
            lst = _.first(lst, this.limit);
            lst = _.map(lst, function(el) {
                el.__type = "company";
                return el;
            });
            console.debug("Linkedin companies found:", companies.companies._total, '=>', lst.length, lst);
            return this.display_result(lst, this.$(".oe_linkedin_pop_c"));
        },
        do_result_people: function(people) {
            var plst = people.people.values || [];
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
            } else { // people
                this.$("h3").text(this.data.formattedName);
                self.$("img").attr("src", this.data.pictureUrl);
                self.$(".oe_linkedin_entity_headline").text(this.data.headline);
            }
        },
    });
};
// vim:et fdc=0 fdl=0:
