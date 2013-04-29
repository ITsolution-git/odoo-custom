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
            // update a plan and related goals
            'click a.oe_update_plan': function(event) {
                var self = this;
                var plan_id = parseInt(event.currentTarget.id, 10);
                var goals_updated = new instance.web.Model('gamification.goal.plan').call('quick_update', [plan_id]);
                $.when(goals_updated).done(function() {
                    self.get_goal_todo_info();
                });
            },
            // action to modify a goal
            'click a.oe_goal_action': function(event) {
                var self = this;
                var goal_id = parseInt(event.currentTarget.id, 10);
                var goal_action = new instance.web.Model('gamification.goal').call('get_action', [goal_id]).then(function(res) {
                    goal_action['action'] = res;
                });
                $.when(goal_action).done(function() {
                    var action_manager = new instance.web.ActionManager(this);
                    var action = action_manager.do_action(goal_action.action);
                    $.when(action).done(function () {
                        new instance.web.Model('gamification.goal').call('update', [[goal_id]]).then(function(res) {
                            self.get_goal_todo_info();
                        });
                    });
                });
            },
            // get more info about a challenge request
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
        // open related goals when clicking on challenge kanban view
        on_card_clicked: function() {
            if (this.view.dataset.model === 'gamification.goal.plan') {
                this.$('.oe_kanban_project_list a').first().click();
            } else {
                this._super.apply(this, arguments);
            }
        }
    });

    instance.gamification.GoalWidget = instance.web_kanban.AbstractField.extend({
        className: "oe_goal_gauge",
        start: function() {
            var self = this;
            var max = 100;
            if (this.options.max_field) {
                max = self.getParent().record[this.options.max_field].raw_value;
            }
            var label = "";
            if (this.options.label_field) {
                label = self.getParent().record[this.options.label_field].raw_value;
            }
            this.g = new JustGage({
                parentNode: self.$el[0],
                value: self.get("value"),
                min: 0,
                max: max,
                relativeGaugeSize: true,
                humanFriendly: true,
                label: label,
                levelColors: [
                    "#ff0000",
                    "#f9c802",
                    "#a9d70b"
                ]
            });
        },
    });
    instance.web_kanban.fields_registry.add("goal", "instance.gamification.GoalWidget");

    
};
