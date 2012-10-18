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
            this.ds_model = new session.web.DataSetSearch(this, this.view.model);
            this.sub_model = new session.web.DataSetSearch(this,'mail.message.subtype');
            this.ds_follow = new session.web.DataSetSearch(this, this.field.relation);
            this.follower_model = new session.web.DataSetSearch(this,'mail.followers');
        },

        start: function() {
            // use actual_mode property on view to know if the view is in create mode anymore
            this.view.on("change:actual_mode", this, this._check_visibility);
            this._check_visibility();
            this.reinit();
            this.bind_events();
            this.display_subtypes();
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
            this.$('button.oe_follower').on('click', function (event) {
                if($(this).hasClass('oe_notfollow'))
                    self.do_follow();
                else
                    self.do_unfollow();
            });
            this.$('ul.oe_subtypes input').on('click', self.do_update_subscription);
            this.$('button.oe_invite').on('click', function (event) {
                action = {
                    type: 'ir.actions.act_window',
                    res_model: 'mail.wizard.invite',
                    view_mode: 'form',
                    view_type: 'form',
                    views: [[false, 'form']],
                    target: 'new',
                    context: {
                        'default_res_model': self.view.dataset.model,
                        'default_res_id': self.view.datarecord.id
                    },
                }
                self.do_action(action, {
                    on_close: function() {
                        self.read_value();
                    },
                });
            });
        },

        read_value: function() {
            var self = this;
            return this.ds_model.read_ids([this.view.datarecord.id], ['message_follower_ids']).pipe(function (results) {
                self.set_value(results[0].message_follower_ids);
            });
        },

        render_value: function() {
            this.reinit();
            return this.fetch_followers(this.get("value"));
        },

        fetch_followers: function (value_) {
            this.value = value_ || {};
            if (value_)
                return this.ds_follow.call('read', [this.value, ['name', 'user_ids']])
                    .pipe(this.proxy('display_followers'), this.proxy('display_generic'))
                    .pipe(this.proxy('display_buttons'));
        },

        /* Display generic info about follower, for people not having access to res_partner */
        display_generic: function (error, event) {
            event.preventDefault();
            this.message_is_follower = false;
            var node_user_list = this.$('ul.oe_mail_followers_display').empty();
            // format content: Followers (You and 0 other) // Followers (3)
            var content = this.options.title;
            if (this.message_is_follower) {
                content += ' (You and ' + (this.value.length-1) + ' other)';
            }
            else {
                content += ' (' + this.value.length + ')'
            }
            this.$('div.oe_mail_recthread_followers h4').html(content);
        },

        /** Display the followers */
        display_followers: function (records) {
            var self = this;
            this.message_is_follower = this.set_is_follower(records);
            var node_user_list = this.$('ul.oe_mail_followers_display').empty();
            this.$('div.oe_mail_recthread_followers h4').html(this.options.title + (records.length>=5 ? ' (' + records.length + ')' : '') );
            for(var i=0; i<records.length&&i<5; i++) {
                var record=records[i];
                record.avatar_url = mail.ChatterUtils.get_image(self.session, 'res.partner', 'image_small', record.id);
                $(session.web.qweb.render('mail.followers.partner', {'record': record})).appendTo(node_user_list);
            }
        },

        /** Computes whether the current user is in the followers */
        set_is_follower: function(records) {
            for(var i in records) {
                if (records[i]['user_ids'][0] == this.session.uid) {
                    return true;
                }
            }
            return false;
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

        set_subtypes:function(data){
            var self = this;
            var records = (data[this.view.datarecord.id] || data[null]).message_subtype_data;

            _(records).each(function (record, record_name) {
                record.name = record_name;
                record.followed = record.followed || undefined;
                $(session.web.qweb.render('mail.followers.subtype', {'record': record})).appendTo( self.$('ul.oe_subtypes') );
            });
        },

        /** Display subtypes: {'name': default, followed} */
        display_subtypes: function (visible) {
            var self = this;
            var recthread_subtypes = self.$('.oe_recthread_subtypes');
            subtype_list_ul = self.$('ul.oe_subtypes');

            if(subtype_list_ul.is(":empty")) {
                var context = new session.web.CompoundContext(this.build_context(), {});
                this.ds_model.call('message_get_subscription_data',[[self.view.datarecord.id], context]).pipe(this.proxy('set_subtypes'));
            }
        },
        
        do_follow: function () {
            _(this.$('.oe_msg_subtype_check')).each(function(record){
                $(record).attr('checked','checked');
            });
            this.do_update_subscription();
        },
        
        do_unfollow: function () {
            _(this.$('.oe_msg_subtype_check')).each(function(record){
                $(record).attr('checked',false);
            });
            var context = new session.web.CompoundContext(this.build_context(), {});
            return this.ds_model.call('message_unsubscribe_users', [[this.view.datarecord.id], [this.session.uid], context]).pipe(this.proxy('read_value'));
        },

        do_update_subscription: function (event) {
            var self = this;

            var checklist = new Array();
            _(this.$('.oe_mail_recthread_actions input[type="checkbox"]')).each(function(record){
                if($(record).is(':checked')) {
                    checklist.push(parseInt($(record).data('id')))}
            });

            if(!checklist.length)
                return this.do_unfollow();
            else{
                var context = new session.web.CompoundContext(this.build_context(), {});
                return this.ds_model.call('message_subscribe_users', [[this.view.datarecord.id], [this.session.uid], undefined, context]).pipe(function(value_){
                        self.read_value(value_);
                        self.display_subtypes(true);
                    });
            }
        },

    });
};
