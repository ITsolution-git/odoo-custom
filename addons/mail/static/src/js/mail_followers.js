openerp_mail_followers = function(session, mail) {
    var _t = session.web._t,
       _lt = session.web._lt;

    var mail_followers = session.mail_followers = {};

    /** 
     * ------------------------------------------------------------
     * mail_followers Widget
     * ------------------------------------------------------------
     *
     * This widget handles the display of a list of records as a vertical
     * list, with an image on the left. The widget itself is a floatting
     * right-sided box.
     * This widget is mainly used to display the followers of records
     * in OpenChatter.
     */

    /* Add the widget to registry */
    session.web.form.widgets.add('mail_followers', 'openerp.mail_followers.Followers');

    mail_followers.Followers = session.web.form.AbstractField.extend({
        template: 'mail.followers',

        init: function() {
            this._super.apply(this, arguments);
            this.options.image = this.node.attrs.image || 'image_small';
            this.options.title = this.node.attrs.title || 'Followers';
            this.options.comment = this.node.attrs.help || false;
            this.options.displayed_nb = this.node.attrs.displayed_nb || 10;
            this.ds_model = new session.web.DataSetSearch(this, this.view.model);
            this.ds_follow = new session.web.DataSetSearch(this, this.field.relation);
            this.ds_users = new session.web.DataSetSearch(this, 'res.users');
        },

        start: function() {
            // use actual_mode property on view to know if the view is in create mode anymore
            this.view.on("change:actual_mode", this, this._check_visibility);
            this._check_visibility();
            this.reinit();
            this.bind_events();
        },

        _check_visibility: function() {
            this.$el.toggle(this.view.get("actual_mode") !== "create");
        },

        reinit: function() {
            this.message_is_follower == undefined;
            this.display_buttons();
        },

        bind_events: function() {
            var self = this;
            // event: click on '(Un)Follow' button, that toggles the follow for uid
            this.$('.oe_follower').on('click', function (event) {
                if($(this).hasClass('oe_notfollow'))
                    self.do_follow();
                else
                    self.do_unfollow();
            });
            // event: click on a subtype, that (un)subscribe for this subtype
            this.$el.on('click', 'ul.oe_subtypes input', self.do_update_subscription);
            // event: click on 'invite' button, that opens the invite wizard
            this.$('.oe_invite').on('click', function (event) {
                action = {
                    type: 'ir.actions.act_window',
                    res_model: 'mail.wizard.invite',
                    view_mode: 'form',
                    view_type: 'form',
                    views: [[false, 'form']],
                    target: 'new',
                    context: {
                        'default_res_model': self.view.dataset.model,
                        'default_res_id': self.view.dataset.ids[0]
                    },
                }
                self.do_action(action, {
                    on_close: function() {
                        self.read_value();
                    },
                });
            });
        },

        read_value: function () {
            var self = this;
            return this.ds_model.read_ids([this.view.dataset.ids[0]], ['message_follower_ids']).pipe(function (results) {
                self.set_value(results[0].message_follower_ids);
            });
        },

        set_value: function (value_) {
            this._super(value_);
            // TDE FIXME: render_value is never called... ask to niv
            // TDE TODO: in start, call this._super(), should resolve this issue
            this.render_value();
        },

        render_value: function () {
            this.reinit();
            return this.fetch_followers(this.get("value"));
        },

        fetch_followers: function (value_) {
            this.value = value_ || {};
            return this.ds_follow.call('read', [this.value, ['name', 'user_ids']])
                .pipe(this.proxy('display_followers'), this.proxy('fetch_generic'))
                .pipe(this.proxy('display_buttons'))
                .pipe(this.proxy('fetch_subtypes'));
        },

        /** Read on res.partner failed: fall back on a generic case
            - fetch current user partner_id (call because no other smart solution currently) FIXME
            - then display a generic message about followers */
        fetch_generic: function (error, event) {
            var self = this;
            event.preventDefault();
            return this.ds_users.call('read', [this.session.uid, ['partner_id']]).pipe(function (results) {
                var pid = results['partner_id'][0];
                self.message_is_follower = (_.indexOf(self.get('value'), pid) != -1);
            }).pipe(self.proxy('display_generic'));
        },

        /* Display generic info about follower, for people not having access to res_partner */
        display_generic: function () {
            var self = this;
            var node_user_list = this.$('ul.oe_mail_followers_display').empty();
            // format content: Followers (You and 0 other) // Followers (3)
            var content = this.options.title;
            if (this.message_is_follower) {
                content += ' (You and ' + (this.get('value').length-1) + ' other)';
            }
            else {
                content += ' (' + this.get('value').length + ')'
            }
            this.$('div.oe_mail_recthread_followers h4').html(content);
        },

        /** Display the followers */
        display_followers: function (records) {
            var self = this;
            records = records || [];
            this.message_is_follower = this.set_is_follower(records);
            // clean and display title
            var node_user_list = this.$('ul.oe_mail_followers_display').empty();
            this.$('div.oe_mail_recthread_followers h4').html(this.options.title + ' (' + records.length + ')');
            // truncate number of displayed followers
            truncated = records.splice(0, this.options.displayed_nb);
            _(truncated).each(function (record) {
                record.avatar_url = mail.ChatterUtils.get_image(self.session, 'res.partner', 'image_small', record.id);
                $(session.web.qweb.render('mail.followers.partner', {'record': record})).appendTo(node_user_list);
            });
            if (truncated.length < records.length) {
                $('<li>And ' + (records.length - truncated.length) + ' more.</li>').appendTo(node_user_list);
            }
        },

        /** Computes whether the current user is in the followers */
        set_is_follower: function (records) {
            var user_ids = _.pluck(_.pluck(records, 'user_ids'), 0);
            return _.indexOf(user_ids, this.session.uid) != -1;
        },

        display_buttons: function () {
            if (this.message_is_follower) {
                this.$('button.oe_follower').removeClass('oe_notfollow').addClass('oe_following');
            }
            else {
                this.$('button.oe_follower').removeClass('oe_following').addClass('oe_notfollow');
            }

            if (this.view.is_action_enabled('edit'))
                this.$('span.oe_mail_invite_wrapper').hide();
            else
                this.$('span.oe_mail_invite_wrapper').show();
        },

        /** Fetch subtypes, only if current user is follower */
        fetch_subtypes: function () {
            var subtype_list_ul = this.$('.oe_subtypes').empty();
            if (! this.message_is_follower) return;
            var context = new session.web.CompoundContext(this.build_context(), {});
            this.ds_model.call('message_get_subscription_data', [[this.view.datarecord.id], context]).pipe(this.proxy('display_subtypes'));
        },

        /** Display subtypes: {'name': default, followed} */
        display_subtypes:function (data) {
            var self = this;
            var subtype_list_ul = this.$('.oe_subtypes');
            var records = data[this.view.datarecord.id].message_subtype_data;

            _(records).each(function (record, record_name) {
                record.name = record_name;
                record.followed = record.followed || undefined;
                $(session.web.qweb.render('mail.followers.subtype', {'record': record})).appendTo( self.$('ul.oe_subtypes') );
            });
        },

        do_follow: function () {
            _(this.$('.oe_msg_subtype_check')).each(function (record) {
                $(record).attr('checked', 'checked');
            });
            this.do_update_subscription();
        },
        
        do_unfollow: function () {
            _(this.$('.oe_msg_subtype_check')).each(function (record) {
                $(record).attr('checked',false);
            });
            var context = new session.web.CompoundContext(this.build_context(), {});
            return this.ds_model.call('message_unsubscribe_users', [[this.view.dataset.ids[0]], [this.session.uid], context]).pipe(this.proxy('read_value'));
        },

        do_update_subscription: function (event) {
            var self = this;

            var checklist = new Array();
            _(this.$('.oe_mail_recthread_actions input[type="checkbox"]')).each(function (record) {
                if ($(record).is(':checked')) {
                    checklist.push(parseInt($(record).data('id')));
                }
            });

            var context = new session.web.CompoundContext(this.build_context(), {});
            return this.ds_model.call('message_subscribe_users', [[this.view.datarecord.id], [this.session.uid], this.message_is_follower ? checklist:undefined, context])
                .pipe(this.proxy('read_value'));
        },
    });
};
