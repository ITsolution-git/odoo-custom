
define(["openerp", "underscore", "require", "jquery",
        "jquery.achtung"], function(openerp, _, require, $) {
    /* jshint es3: true */
    "use strict";
    
    var livesupport = {};

    _.extend(openerp.qweb.default_dict, {
        'toUrl': _.bind(require.toUrl, require)
    });

    var connection;

    var defaultInputPlaceholder;
    var userName;

    livesupport.main = function(server_url, db, login, password, channel, options) {
        var defs = [];
        options = options || {};
        _.defaults(options, {
            buttonText: "Chat with one of our collaborators",
            inputPlaceholder: "How may I help you?",
            defaultMessage: null,
            auto: false,
            userName: "Anonymous"
        });
        defaultInputPlaceholder = options.inputPlaceholder;
        userName = options.userName;
        // TODO : load QwebTemplates
        defs.push(add_css("../css/livesupport.css"));
        defs.push(add_css("./jquery.achtung.css"));

        $.when.apply($, defs).then(function() {
            console.log("starting live support customer app");
            connection = new openerp.Session(null, server_url, { override_session: true });
            return connection.session_authenticate(db, login, password);
        }).then(function() {
            connection.rpc("/im_livechat/available", {db: db, channel: channel}).then(function(activated) {
                if (! activated & ! options.auto)
                    return;
                var button = new livesupport.ChatButton(null, channel, options);
                button.appendTo($("body"));
                if (options.auto)
                    button.click();
            });
        });
    };

    var add_css = function(relative_file_name) {
        var css_def = $.Deferred();
        $('<link rel="stylesheet" href="' + require.toUrl(relative_file_name) + '"></link>')
                .appendTo($("head")).ready(function() {
            css_def.resolve();
        });
        return css_def.promise();
    };

    var notification = function(message) {
        $.achtung({message: message, timeout: 0, showEffects: false, hideEffects: false});
    };

    var ERROR_DELAY = 5000;

    livesupport.ChatButton = openerp.Widget.extend({
        className: "openerp_style oe_chat_button",
        events: {
            "click": "click"
        },
        init: function(parent, channel, options) {
            this._super(parent);
            this.channel = channel;
            this.options = options;
            this.text = options.buttonText;
        },
        render: function() {
            this.$().append(templateEngine.chatButton({widget: this}));
        },
        click: function() {
            if (! this.manager) {
                this.manager = new livesupport.ConversationManager(null);
                this.activated_def = this.manager.start_polling();
            }
            var def = $.Deferred();
            $.when(this.activated_def).then(function() {
                def.resolve();
            }, function() {
                def.reject();
            });
            setTimeout(function() {
                def.reject();
            }, 5000);
            def.then(_.bind(this.chat, this), function() {
                notification("It seems the connection to the server is encountering problems, please try again later.");
            });
        },
        chat: function() {
            var self = this;
            if (this.manager.conversations.length > 0)
                return;
            connection.model("im_livechat.channel").call("get_available_user", [this.channel]).then(function(user_id) {
                if (! user_id) {
                    notification("None of our collaborators seems to be available, please try again later.");
                    return;
                }
                self.manager.ensure_users([user_id]).then(function() {
                    var conv = self.manager.activate_user(self.manager.get_user(user_id), true);
                    if (self.options.defaultMessage) {
                        conv.received_message({message: self.options.defaultMessage, 
                            date: openerp.datetime_to_str(new Date())});
                    }
                });
            });
        }
    });

    livesupport.ImUser = openerp.Class.extend(openerp.PropertiesMixin, {
        init: function(parent, user_rec) {
            openerp.PropertiesMixin.init.call(this, parent);
            user_rec.image_url = require.toUrl("../img/avatar/avatar.jpeg");
            if (user_rec.image)
                user_rec.image_url = "data:image/png;base64," + user_rec.image;
            this.set(user_rec);
            this.set("watcher_count", 0);
            this.on("change:watcher_count", this, function() {
                if (this.get("watcher_count") === 0)
                    this.destroy();
            });
        },
        destroy: function() {
            this.trigger("destroyed");
            openerp.PropertiesMixin.destroy.call(this);
        },
        add_watcher: function() {
            this.set("watcher_count", this.get("watcher_count") + 1);
        },
        remove_watcher: function() {
            this.set("watcher_count", this.get("watcher_count") - 1);
        }
    });

    livesupport.ConversationManager = openerp.Class.extend(openerp.PropertiesMixin, {
        init: function(parent) {
            openerp.PropertiesMixin.init.call(this, parent);
            this.set("right_offset", 0);
            this.conversations = [];
            this.users = {};
            this.on("change:right_offset", this, this.calc_positions);
            this.set("window_focus", true);
            this.set("waiting_messages", 0);
            this.focus_hdl = _.bind(function() {
                this.set("window_focus", true);
            }, this);
            $(window).bind("focus", this.focus_hdl);
            this.blur_hdl = _.bind(function() {
                this.set("window_focus", false);
            }, this);
            $(window).bind("blur", this.blur_hdl);
            this.on("change:window_focus", this, this.window_focus_change);
            this.window_focus_change();
            this.on("change:waiting_messages", this, this.messages_change);
            this.messages_change();
            this.create_ting();
            this.activated = false;
            this.users_cache = {};
            this.last = null;
            this.unload_event_handler = _.bind(this.unload, this);
        },
        start_polling: function() {
            var self = this;

            var uuid = localStorage["oe_livesupport_uuid"];
            var def = $.when(uuid);

            if (! uuid) {
                def = connection.connector.call("/longpolling/im/gen_uuid", {});
            }
            return def.then(function(uuid) {
                localStorage["oe_livesupport_uuid"] = uuid;
                return connection.model("im.user").call("get_by_user_id", [uuid]);
            }).then(function(my_id) {
                self.my_id = my_id["id"];
                return connection.model("im.user").call("assign_name", [uuid, userName]);
            }).then(function() {
                return self.ensure_users([self.my_id]);
            }).then(function() {
                var me = self.users_cache[self.my_id];
                delete self.users_cache[self.my_id];
                self.me = me;
                me.set("name", "You");
                return connection.connector.call("/longpolling/im/activated", {});
            }).then(function(activated) {
                if (activated) {
                    self.activated = true;
                    $(window).on("unload", self.unload_event_handler);
                    self.poll();
                } else {
                    return $.Deferred().reject();
                }
            });
        },
        unload: function() {
            connection.model("im.user").call("im_disconnect", [], {uuid: this.me.get("uuid"), context: {}});
        },
        ensure_users: function(user_ids) {
            var no_cache = {};
            _.each(user_ids, function(el) {
                if (! this.users_cache[el])
                    no_cache[el] = el;
            }, this);
            var self = this;
            if (_.size(no_cache) === 0)
                return $.when();
            else
                return connection.model("im.user").call("read", [_.values(no_cache), []]).then(function(users) {
                    self.add_to_user_cache(users);
                });
        },
        add_to_user_cache: function(user_recs) {
            _.each(user_recs, function(user_rec) {
                if (! this.users_cache[user_rec.id]) {
                    var user = new livesupport.ImUser(this, user_rec);
                    this.users_cache[user_rec.id] = user;
                    user.on("destroyed", this, function() {
                        delete this.users_cache[user_rec.id];
                    });
                }
            }, this);
        },
        get_user: function(user_id) {
            return this.users_cache[user_id];
        },
        poll: function() {
            console.debug("live support beggin polling");
            var self = this;
            var user_ids = _.map(this.users_cache, function(el) {
                return el.get("id");
            });
            connection.connector.call("/longpolling/im/poll", {
                last: this.last,
                users_watch: user_ids,
                db: connection.database,
                uid: connection.userId,
                password: connection.password,
                uuid: self.me.get("uuid")
            }).then(function(result) {
                _.each(result.users_status, function(el) {
                    if (self.get_user(el.id))
                        self.get_user(el.id).set(el);
                });
                self.last = result.last;
                var user_ids = _.pluck(_.pluck(result.res, "from_id"), 0);
                self.ensure_users(user_ids).then(function() {
                    _.each(result.res, function(mes) {
                        var user = self.get_user(mes.from_id[0]);
                        self.received_message(mes, user);
                    });
                    self.poll();
                });
            }, function() {
                setTimeout(_.bind(self.poll, self), ERROR_DELAY);
            });
        },
        get_activated: function() {
            return this.activated;
        },
        create_ting: function() {
            if (typeof(Audio) === "undefined") {
                this.ting = {play: function() {}};
                return;
            }
            this.ting = new Audio(new Audio().canPlayType("audio/ogg; codecs=vorbis") ?
                require.toUrl("../audio/Ting.ogg") :
                require.toUrl("../audio/Ting.mp3")
            );
        },
        window_focus_change: function() {
            if (this.get("window_focus")) {
                this.set("waiting_messages", 0);
            }
        },
        messages_change: function() {
            //if (! instance.webclient.set_title_part)
            //    return;
            //instance.webclient.set_title_part("im_messages", this.get("waiting_messages") === 0 ? undefined :
            //    _.str.sprintf(_t("%d Messages"), this.get("waiting_messages")));
        },
        activate_user: function(user, focus) {
            var conv = this.users[user.get('id')];
            if (! conv) {
                conv = new livesupport.Conversation(this, user, this.me);
                conv.appendTo($("body"));
                conv.on("destroyed", this, function() {
                    this.conversations = _.without(this.conversations, conv);
                    delete this.users[conv.user.get('id')];
                    this.calc_positions();
                });
                this.conversations.push(conv);
                this.users[user.get('id')] = conv;
                this.calc_positions();
            }
            if (focus)
                conv.focus();
            return conv;
        },
        received_message: function(message, user) {
            if (! this.get("window_focus")) {
                this.set("waiting_messages", this.get("waiting_messages") + 1);
                this.ting.play();
                this.create_ting();
            }
            var conv = this.activate_user(user);
            conv.received_message(message);
        },
        calc_positions: function() {
            var current = this.get("right_offset");
            _.each(_.range(this.conversations.length), function(i) {
                this.conversations[i].set("right_position", current);
                current += this.conversations[i].$().outerWidth(true);
            }, this);
        },
        destroy: function() {
            $(window).off("unload", this.unload_event_handler);
            $(window).unbind("blur", this.blur_hdl);
            $(window).unbind("focus", this.focus_hdl);
            openerp.PropertiesMixin.destroy.call(this);
        }
    });

    livesupport.Conversation = openerp.Widget.extend({
        className: "openerp_style oe_im_chatview",
        events: {
            "keydown input": "send_message",
            "click .oe_im_chatview_close": "destroy",
            "click .oe_im_chatview_header": "show_hide"
        },
        init: function(parent, user, me) {
            this._super(parent);
            this.me = me;
            this.user = user;
            this.user.add_watcher();
            this.set("right_position", 0);
            this.shown = true;
            this.set("pending", 0);
            this.inputPlaceholder = defaultInputPlaceholder;
        },
        render: function() {
            this.$().append(templateEngine.conversation({widget: this}));
            var change_status = function() {
                this.$().toggleClass("oe_im_chatview_disconnected_status", this.user.get("im_status") === false);
                this.$(".oe_im_chatview_online").toggle(this.user.get("im_status") === true);
                this._go_bottom();
            };
            this.user.on("change:im_status", this, change_status);
            change_status.call(this);

            this.on("change:right_position", this, this.calc_pos);
            this.full_height = this.$().height();
            this.calc_pos();
            this.on("change:pending", this, _.bind(function() {
                if (this.get("pending") === 0) {
                    this.$(".oe_im_chatview_nbr_messages").text("");
                } else {
                    this.$(".oe_im_chatview_nbr_messages").text("(" + this.get("pending") + ")");
                }
            }, this));
        },
        show_hide: function() {
            if (this.shown) {
                this.$().animate({
                    height: this.$(".oe_im_chatview_header").outerHeight()
                });
            } else {
                this.$().animate({
                    height: this.full_height
                });
            }
            this.shown = ! this.shown;
            if (this.shown) {
                this.set("pending", 0);
            }
        },
        calc_pos: function() {
            this.$().css("right", this.get("right_position"));
        },
        received_message: function(message) {
            if (this.shown) {
                this.set("pending", 0);
            } else {
                this.set("pending", this.get("pending") + 1);
            }
            this._add_bubble(this.user, message.message, openerp.str_to_datetime(message.date));
        },
        send_message: function(e) {
            if(e && e.which !== 13) {
                return;
            }
            var mes = this.$("input").val();
            if (! mes.trim()) {
                return;
            }
            this.$("input").val("");
            var send_it = _.bind(function() {
                var model = connection.model("im.message");
                return model.call("post", [mes, this.user.get('id')], {uuid: this.me.get("uuid"), context: {}});
            }, this);
            var tries = 0;
            send_it().then(_.bind(function() {
                this._add_bubble(this.me, mes, new Date());
            }, this), function(error, e) {
                tries += 1;
                if (tries < 3)
                    return send_it();
            });
        },
        _add_bubble: function(user, item, date) {
            var items = [item];
            if (user === this.last_user) {
                this.last_bubble.remove();
                items = this.last_items.concat(items);
            }
            this.last_user = user;
            this.last_items = items;
            var zpad = function(str, size) {
                str = "" + str;
                return new Array(size - str.length + 1).join('0') + str;
            };
            date = "" + zpad(date.getHours(), 2) + ":" + zpad(date.getMinutes(), 2);
            
            this.last_bubble = $(templateEngine.conversation_bubble({"items": items, "user": user, "time": date}));
            $(this.$(".oe_im_chatview_content").children()[0]).append(this.last_bubble);
            this._go_bottom();
        },
        _go_bottom: function() {
            this.$(".oe_im_chatview_content").scrollTop($(this.$(".oe_im_chatview_content").children()[0]).height());
        },
        focus: function() {
            this.$(".oe_im_chatview_input").focus();
        },
        destroy: function() {
            this.user.remove_watcher();
            this.trigger("destroyed");
            return this._super();
        }
    });



    return livesupport;
});
