openerp.gamification = function(instance) {
    var QWeb = instance.web.qweb;

    instance.gamification.Sidebar = instance.web.Widget.extend({
        template: 'gamification.user_wall_sidebar',
        init: function (parent, action) {
            var self = this;
            this._super(parent, action);
            this.deferred = $.Deferred();
            this.res_user = new instance.web.DataSetSearch(this, 'res.users');
            this.goals_info = {};
            this.challenge_suggestions = {};
        },
        events: {
            'click a.oe_update_goal': function(event) {
                var self = this;
                var goal_id = parseInt(event.currentTarget.id, 10);
                var goal_updated = new instance.web.Model('gamification.goal').call('update', [[goal_id]]);
                $.when(goal_updated).done(function() {
                    self.get_goal_todo_info();
                });
            },
            'click a.oe_update_plan': function(event) {
                var self = this;
                var plan_id = parseInt(event.currentTarget.id, 10);
                var goals_updated = new instance.web.Model('gamification.goal.plan').call('quick_update', [plan_id]);
                $.when(goals_updated).done(function() {
                    self.get_goal_todo_info();
                });
            },
            'click a.oe_goal_action': function(event) {
                var self = this;
                var goal_id = parseInt(event.currentTarget.id, 10);
                var goal_action = new instance.web.Model('gamification.goal').call('get_action', [goal_id]).then(function(res) {
                    goal_action['action'] = res;
                });
                $.when(goal_action).done(function() {
                    var action_manager = new instance.web.ActionManager(this);
                    action_manager.do_action(goal_action.action).done(function () {
                        self.get_goal_todo_info();
                    });
                });
            },
            'click a.oe_challenge_reply': function(event) {
                var self = this;
                var plan_id = parseInt(event.currentTarget.id, 10);
                var plan_action = new instance.web.Model('gamification.goal.plan').call('reply_challenge_wizard', [plan_id]).then(function(res) {
                    plan_action['action'] = res;
                });
                $.when(plan_action).done(function() {
                    var action_manager = new instance.web.ActionManager(this);
                    action_manager.do_action(plan_action.action).done(function () {
                        self.get_goal_todo_info();
                    });
                });
            }
        },
        renderElement: function() {
            var self = this;
            this._super.apply(this, arguments);
            self.get_goal_todo_info();
            self.get_challenge_suggestions();
        },
        render_template: function(target,template) {
            var self = this;
            target.append(QWeb.render(template,{'widget': self}));
        },
        render_template_replace: function(target,template) {
            var self = this;
            target.html(QWeb.render(template,{'widget': self}));
        },
        get_goal_todo_info: function() {
            var self = this;
            var goals_info = this.res_user.call('get_goals_todo_info', {}).then(function(res) {
                self.goals_info['info'] = res;
            });
            $.when(goals_info).done(function() {
                if(self.goals_info.info.length > 0){
                    self.render_template_replace(self.$el.filter(".oe_gamification_goal"),'gamification.goal_list_to_do');
                    self.render_money_fields(self.goals_info.info[0].currency);
                    self.render_user_avatars();
                } else {
                    self.$el.filter(".oe_gamification_goal").hide();
                }
            });
        },
        get_challenge_suggestions: function() {
            var self = this;
            var challenge_suggestions = this.res_user.call('get_challenge_suggestions', {}).then(function(res) {
                self.challenge_suggestions['info'] = res;
            });
            $.when(challenge_suggestions).done(function() {
                if(self.challenge_suggestions.info.length > 0){
                    self.render_template_replace(self.$el.filter(".oe_gamification_suggestion"),'gamification.challenge_suggestions');
                } else {
                    self.$el.filter(".oe_gamification_suggestion").hide();
                }
            });
        },
        render_money_fields: function(currency_id) {
            var self = this;

            self.dfm = new instance.web.form.DefaultFieldManager(self);
            // Generate a FieldMonetary for each .oe_goal_field_monetary
            self.$(".oe_goal_field_monetary").each(function() {
                money_field = new instance.web.form.FieldMonetary(self.dfm, {
                    attrs: {
                        modifiers: '{"readonly": true}'
                    }
                });
                money_field.set('currency', currency_id);
                money_field.get_currency_info();
                money_field.set('value', parseInt($(this).text(), 10));
                money_field.replace($(this));
            });
        },
        render_user_avatars: function() {
            var self = this;
            self.$(".oe_user_avatar").each(function() {
                var user_id = parseInt( $(this).attr('data-id'), 10);
                var url = instance.session.url('/web/binary/image', {model: 'res.users', field: 'image_small', id: user_id});
                $(this).attr("src", url);
            });
        }
    });

    instance.mail.Widget.include({
        init: function (parent, action) {
            var self = this;
            this._super(parent, action);
        },
        start: function() {
            this._super();
            var self = this;
            var sidebar = new instance.gamification.Sidebar(self);
            sidebar.appendTo($('.oe_mail_wall_aside'));
        }
    });

    instance.web_kanban.KanbanRecord.include({
        start: function () {
            var rendering = this._super();
            var self = this;

            // add gauge in goal kanban views
            $.when(rendering).done(function() {
                if (self.view.dataset.model === 'gamification.goal' && self.$el.find('.oe_goal_gauge').length == 1) {
                    var unique_id = _.uniqueId("goal_gauge_");
                    self.$el.find('.oe_goal_gauge').attr('id', unique_id);
                    var g = new JustGage({
                        id: unique_id,
                        node: self.$('.oe_goal_gauge').empty().get(0),
                        value: self.record.current.raw_value,
                        min: 0,
                        max: self.record.target_goal.raw_value,
                        relativeGaugeSize: true,
                        humanFriendly: true,
                        label: self.record.type_suffix.raw_value,
                        levelColors: [
                            "#ff0000",
                            "#f9c802",
                            "#a9d70b"
                        ]
                    });
                }
            });
        },
        // open related goals when clicking on challenge kanban view
        on_card_clicked: function() {
            if (this.view.dataset.model === 'gamification.goal.plan') {
                this.$('.oe_kanban_project_list a').first().click();
            } else {
                this._super.apply(this, arguments);
            }
        }
    });
};
