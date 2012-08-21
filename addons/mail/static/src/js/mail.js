openerp.mail = function(session) {
    var _t = session.web._t,
       _lt = session.web._lt;

    var mail = session.mail = {};

    openerp_mail_followers(session, mail);        // import mail_followers.js

    /**
     * ------------------------------------------------------------
     * FormView
     * ------------------------------------------------------------
     * 
     * Override of formview do_action method, to catch all return action about
     * mail.compose.message. The purpose is to bind 'Send by e-mail' buttons
     * and redirect them to the Chatter.
     */

    session.web.FormView = session.web.FormView.extend({
        do_action: function(action, on_close) {
            if (action.res_model == 'mail.compose.message' && this.fields && this.fields.message_ids && this.fields.message_ids.view.get("actual_mode") != 'create') {
                var record_thread = this.fields.message_ids;
                var thread = record_thread.thread;
                thread.instantiate_composition_form('comment', true, false, 0, action.context);
                return false;
            }
            else {
                return this._super(action, on_close);
            }
        },
    });


    /**
     * ------------------------------------------------------------
     * ChatterUtils
     * ------------------------------------------------------------
     * 
     * This class holds a few tools method that will be used by
     * the various Chatter widgets.
     *
     * Some regular expressions not used anymore, kept because I want to
     * - (^|\s)@((\w|@|\.)*): @login@log.log, supports inner '@' for
     *   logins that are emails
     *      1. '(void)'
     *      2. login@log.log
     * - (^|\s)\[(\w+).(\w+),(\d)\|*((\w|[@ .,])*)\]: [ir.attachment,3|My Label],
     *   for internal links to model ir.attachment, id=3, and with
     *   optional label 'My Label'. Note that having a '|Label' is not
     *   mandatory, because the regex should still be correct.
     *      1. '(void)'
     *      2. 'ir'
     *      3. 'attachment'
     *      4. '3'
     *      5. 'My Label'
     */

    mail.ChatterUtils = {

        /** get an image in /web/binary/image?... */
        get_image: function(session_prefix, session_id, model, field, id) {
            return session_prefix + '/web/binary/image?session_id=' + session_id + '&model=' + model + '&field=' + field + '&id=' + (id || '');
        },

        /** checks if tue current user is the message author */
        is_author: function (widget, message_user_id) {
            return (widget.session && widget.session.uid != 0 && widget.session.uid == message_user_id);
        },

        /** Replaces some expressions
         * - :name - shortcut to an image
         */
        do_replace_expressions: function (string) {
            var self = this;
            var icon_list = ['al', 'pinky']
            /* special shortcut: :name, try to find an icon if in list */
            var regex_login = new RegExp(/(^|\s):((\w)*)/g);
            var regex_res = regex_login.exec(string);
            while (regex_res != null) {
                var icon_name = regex_res[2];
                if (_.include(icon_list, icon_name))
                    string = string.replace(regex_res[0], regex_res[1] + '<img src="/mail/static/src/img/_' + icon_name + '.png" width="22px" height="22px" alt="' + icon_name + '"/>');
                regex_res = regex_login.exec(string);
            }
            return string;
        },
    };


    /**
     * ------------------------------------------------------------
     * ComposeMessage widget
     * ------------------------------------------------------------
     * 
     * This widget handles the display of a form to compose a new message.
     * This form is an OpenERP form_view, build on a mail.compose.message
     * wizard.
     */

    mail.ComposeMessage = session.web.Widget.extend({
        template: 'mail.compose_message',
        
        /**
         * @param {Object} parent parent
         * @param {Object} [options]
         * @param {String} [options.res_model] res_model of document [REQUIRED]
         * @param {Number} [options.res_id] res_id of record [REQUIRED]
         * @param {Number} [options.email_mode] true/false, tells whether
         *      we are in email sending mode
         * @param {Number} [options.formatting] true/false, tells whether
         *      we are in advance formatting mode
         * @param {String} [options.model] mail.compose.message.mode (see
         *      composition wizard)
         * @param {Number} [options.msg_id] id of a message in case we are in
         *      reply mode
         */
        init: function(parent, options) {
            var self = this;
            this._super(parent);
            // options
            this.options = options || {};
            this.options.context = options.context || {};
            this.options.email_mode = options.email_mode || false;
            this.options.formatting = options.formatting || false;
            this.options.mode = options.mode || 'comment';
            this.options.form_xml_id = options.form_xml_id || 'email_compose_message_wizard_form_chatter';
            this.options.form_view_id = false;
            if (this.options.mode == 'reply') {
                this.options.active_id = this.options.msg_id;
            } else {
                this.options.active_id = this.options.res_id;
            }
            this.email_mode = false;
            this.formatting = false;
            // debug
            console.groupCollapsed('New ComposeMessage: model', this.options.res_model, ', id', this.options.res_id);
            console.log('context:', this.options.context);
            console.groupEnd();
        },

        /**
         * Reinitialize the widget field values to the default values. The
         * purpose is to avoid to destroy and re-build a form view. Default
         * values are therefore given as for an onchange. */
        reinit: function() {
            var self = this;
            if (! this.form_view) return;
            var call_defer = this.ds_compose.call('default_get', [['subject', 'body', 'body_html', 'dest_partner_ids'], this.ds_compose.get_context()]).then(
                function (result) {
                    self.form_view.on_processed_onchange({'value': result}, []);
                });
            return call_defer;
        },

        /**
         * Override-hack of do_action: clean the form */
        do_action: function(action, on_close) {
            // this.init_comments();
            return this._super(action, on_close);
        },

        /**
         * Widget start function
         * - builds and initializes the form view */
        start: function() {
            var self = this;
            this._super.apply(this, arguments);
            // customize display: add avatar, clean previous content
            var user_avatar = mail.ChatterUtils.get_image(this.session.prefix,
                this.session.session_id, 'res.users', 'image_small', this.session.uid);
            this.$element.find('img.oe_mail_icon').attr('src', user_avatar);
            this.$element.find('div.oe_mail_msg_content').empty();
            // create a context for the default_get of the compose form
            var widget_context = {
                'active_model': this.options.res_model,
                'active_id': this.options.active_id,
                'mail.compose.message.mode': this.options.mode,
            };
            var context = _.extend({}, this.options.context, widget_context);
            this.ds_compose = new session.web.DataSetSearch(this, 'mail.compose.message', context);
            // find the id of the view to display in the chatter form
            var data_ds = new session.web.DataSetSearch(this, 'ir.model.data');
            var deferred_form_id =data_ds.call('get_object_reference', ['mail', this.options.form_xml_id]).then( function (result) {
                if (result) {
                    self.options.form_view_id = result[1];
                }
            }).pipe(this.proxy('create_form_view'));
            return deferred_form_id;
        },

        /**
         * Create a FormView, then append it to the to widget DOM. */
        create_form_view: function () {
            var self = this;
            // destroy previous form_view if any
            if (this.form_view) { this.form_view.destroy(); }
            // create the FormView
            this.form_view = new session.web.FormView(this, this.ds_compose, this.options.form_view_id, {
                action_buttons: false,
                pager: false,
                initial_mode: 'edit',
                disable_autofocus: true,
            });
            // add the form, bind events, activate the form
            var msg_node = this.$element.find('div.oe_mail_msg_content');
            return $.when(this.form_view.appendTo(msg_node)).pipe(function() {
                self.bind_events();
                self.form_view.do_show();
                if (self.options.email_mode) { self.toggle_email_mode(); }
                if (self.options.formatting) { self.toggle_formatting_mode(); }
            });
        },

        destroy: function() {
            this._super.apply(this, arguments);
        },

        /**
         * Bind events in the widget. Each event is slightly described
         * in the function. */
        bind_events: function() {
            var self = this;
            this.$element.find('button.oe_form_button').click(function (event) {
                event.preventDefault();
            });
            // event: click on 'Send an Email' link that toggles the form for
            // sending an email (partner_ids)
            this.$element.find('a.oe_mail_compose_message_email').click(function (event) {
                event.preventDefault();
                self.toggle_email_mode();
            });
            // event: click on 'Formatting' icon-link that toggles the advanced
            // formatting options for writing a message (subject, body_html)
            this.$element.find('a.oe_mail_compose_message_formatting').click(function (event) {
                event.preventDefault();
                self.toggle_formatting_mode();
            });
            // event: click on 'Attachment' icon-link that opens the dialog to
            // add an attachment.
            this.$element.find('a.oe_mail_compose_message_attachment').click(function (event) {
                event.preventDefault();
                // not yet implemented
                self.set_body_value('attachment', 'attachment');
            });
            // event: click on 'Checklist' icon-link that toggles the options
            // for adding checklist.
            this.$element.find('a.oe_mail_compose_message_checklist').click(function (event) {
                event.preventDefault();
                // not yet implemented
                self.set_body_value('checklist', 'checklist');
            });
        },

        /**
         * Toggle the formatting mode. */
        toggle_formatting_mode: function() {
            var self = this;
            this.formatting = ! this.formatting;
            // calls onchange
            var call_defer = this.ds_compose.call('onchange_formatting', [[], this.formatting, this.options.res_model, this.options.res_id]).then(
                function (result) {
                    self.form_view.on_processed_onchange(result, []);
                });
            // update context of datasetsearch
            this.ds_compose.context.formatting = this.formatting;
            // toggle display
            this.$element.find('span.oe_mail_compose_message_subject').toggleClass('oe_mail_compose_message_invisible');
            this.$element.find('div.oe_mail_compose_message_body').toggleClass('oe_mail_compose_message_invisible');
            this.$element.find('div.oe_mail_compose_message_body_html').toggleClass('oe_mail_compose_message_invisible');
        },

        /**
         * Toggle the email mode. */
        toggle_email_mode: function() {
            var self = this;
            this.email_mode = ! this.email_mode;
            // calls onchange
            var call_defer = this.ds_compose.call('onchange_email_mode', [[], this.email_mode, this.options.res_model, this.options.res_id]).then(
                function (result) {
                    self.form_view.on_processed_onchange(result, []);
                });
            // update context of datasetsearch
            this.ds_compose.context.email_mode = this.email_mode;
            // update 'Post' button -> 'Send'
            // update 'Send an Email' link -> 'Post a comment'
            if (this.email_mode) {
                this.$element.find('button.oe_mail_compose_message_button_send').html('<span>Send</span>');
                this.$element.find('a.oe_mail_compose_message_email').html('Comment');
            } else {
                this.$element.find('button.oe_mail_compose_message_button_send').html('<span>Post</span>');
                this.$element.find('a.oe_mail_compose_message_email').html('Send an Email');
            }
            // toggle display
            this.$element.find('div.oe_mail_compose_message_partner_ids').toggleClass('oe_mail_compose_message_invisible');
        },

        /**
         * Update the values of the composition form; with possible different
         * values for body and body_html. */
        set_body_value: function(body, body_html) {
            this.form_view.fields.body.set_value(body);
            this.form_view.fields.body_html.set_value(body_html);
        },
    }),

    /** 
     * ------------------------------------------------------------
     * Thread Widget
     * ------------------------------------------------------------
     *
     * This widget handles the display of a thread of messages. The
     * [thread_level] parameter sets the thread level number:
     * - root message
     * - - sub message (parent_id = root message)
     * - - - sub sub message (parent id = sub message)
     * - - sub message (parent_id = root message)
     * This widget has 2 ways of initialization, either you give records
     * to be rendered, either it will fetch [limit] messages related to
     * [res_model]:[res_id].
     */

    mail.Thread = session.web.Widget.extend({
        template: 'mail.thread',

        /**
         * @param {Object} parent parent
         * @param {Object} [options]
         * @param {String} [options.res_model] res_model of document [REQUIRED]
         * @param {Number} [options.res_id] res_id of record [REQUIRED]
         * @param {Number} [options.uid] user id [REQUIRED]
         * @param {Bool}   [options.parent_id=false] parent_id of message
         * @param {Number} [options.thread_level=0] number of levels in the thread
         *      (only 0 or 1 currently)
         * @param {Bool}   [options.is_wall=false] thread is displayed in the wall
         * @param {Number} [options.msg_more_limit=150] number of character to
         *      display before having a "show more" link; note that the text
         *      will not be truncated if it does not have 110% of the parameter
         *      (ex: 110 characters needed to be truncated and be displayed as
         *      a 100-characters message)
         * @param {Number} [options.limit=100] maximum number of messages to fetch
         * @param {Number} [options.offset=0] offset for fetching messages
         * @param {Number} [options.records=null] records to show instead of fetching messages
         */
        init: function(parent, options) {
            this._super(parent);
            // options
            this.options = options || {};
            this.options.domain = options.domain || [];
            this.options.context = options.context || {};
            // check in parents, should not define multiple times
            this.options.context.res_model = options.context.res_model || 'mail.thread';
            this.options.context.res_id = options.context.res_id || false;
            this.options.context.parent_id = options.context.parent_id || false;
            this.options.thread_level = options.thread_level || 0;
            this.options.fetch_limit = options.fetch_limit || 100;
            // TDE: not sure, here for testing / compatibility
            this.options.records = options.records || null;
            this.options.ids = options.ids || null;
            // datasets and internal vars
            // this.ds = new session.web.DataSetSearch(this, this.options.res_model);
            this.ds_msg = new session.web.DataSetSearch(this, 'mail.message');
            // display customization vars
            this.display = {};
            this.display.truncate_limit = options.truncate_limit || 250;
            this.display.show_header_compose = options.show_header_compose || true;
            this.display.show_reply = options.show_reply || true;
            this.display.show_delete = options.show_delete || true;
            this.display.show_hide = options.show_hide || true;
            this.display.show_reply_by_email = options.show_reply_by_email || true;
            this.display.show_more = options.show_more || true;
            // for search view
            this.search = {'domain': [], 'context': {}, 'groupby': {}}
            this.search_results = {'domain': [], 'context': {}, 'groupby': {}}
            // debug
            console.group('New Thread: model', this.options.context.res_model, 'id', this.options.context.res_id, 'thread level', this.options.thread_level);
            console.log('records:', this.options.records, 'ids:', this.options.ids);
            console.log('options:', this.options);
            console.log('display:', this.display);
            console.groupEnd();
        },
        
        start: function() {
            this._super.apply(this, arguments);
            // bind events
            this.bind_events();
            // display user, fetch comments
            this.display_current_user();

            // if (this.options.records) var display_done = this.display_comments_from_parameters(this.options.records);
            if (this.options.records) var display_done = this.display_comments(this.options.records);

            else var display_done = this.init_comments();

            // customize display
            $.when(display_done).then(this.proxy('do_customize_display'));            
            // add message composition form view
            if (this.display.show_header_compose) {
                var compose_done = this.instantiate_composition_form();
            }
            return display_done && compose_done;
        },

        /**
         * Override-hack of do_action: automatically reload the chatter.
         * Normally it should be called only when clicking on 'Post/Send'
         * in the composition form. */
        do_action: function(action, on_close) {
            this.init_comments();
            if (this.compose_message_widget) {
                this.compose_message_widget.reinit(); }
            return this._super(action, on_close);
        },

        instantiate_composition_form: function(mode, email_mode, formatting, msg_id, context) {
            if (this.compose_message_widget) {
                this.compose_message_widget.destroy();
            }
            this.compose_message_widget = new mail.ComposeMessage(this, {
                'extended_mode': false, 'uid': this.options.uid, 'res_model': this.options.res_model,
                'res_id': this.options.res_id, 'mode': mode || 'comment', 'msg_id': msg_id,
                'email_mode': email_mode || false, 'formatting': formatting || false,
                'context': context || false } );
            var composition_node = this.$element.find('div.oe_mail_thread_action');
            composition_node.empty();
            var compose_done = this.compose_message_widget.appendTo(composition_node);
            return compose_done;
        },

        do_customize_display: function() {
            if (this.display.show_post_comment) { this.$element.find('div.oe_mail_thread_action').eq(0).show(); }
        },

        /**
         * Bind events in the widget. Each event is slightly described
         * in the function. */
        bind_events: function() {
            var self = this;
            // event: click on 'more' at bottom of thread
            this.$element.find('button.oe_mail_button_more').click(function () {
                self.do_more();
            });
            // event: writing in basic textarea of composition form (quick reply)
            this.$element.find('textarea.oe_mail_compose_textarea').keyup(function (event) {
                var charCode = (event.which) ? event.which : window.event.keyCode;
                if (event.shiftKey && charCode == 13) { this.value = this.value+"\n"; }
                else if (charCode == 13) { return self.do_comment(); }
            });
            // event: click on 'Reply' in msg
            this.$element.find('div.oe_mail_thread_display').delegate('a.oe_mail_msg_reply', 'click', function (event) {
                var act_dom = $(this).parents('div.oe_mail_thread_display').find('div.oe_mail_thread_action:first');
                act_dom.toggle();
                event.preventDefault();
            });
            // event: click on 'attachment(s)' in msg
            this.$element.delegate('a.oe_mail_msg_view_attachments', 'click', function (event) {
                var act_dom = $(this).parent().parent().parent().find('.oe_mail_msg_attachments');
                act_dom.toggle();
                event.preventDefault();
            });
            // event: click on 'Delete' in msg side menu
            this.$element.find('div.oe_mail_thread_display').delegate('a.oe_mail_msg_delete', 'click', function (event) {
                if (! confirm(_t("Do you really want to delete this message?"))) { return false; }
                var msg_id = event.srcElement.dataset.id;
                if (! msg_id) return false;
                var call_defer = self.ds_msg.unlink([parseInt(msg_id)]);
                $(event.srcElement).parents('li.oe_mail_thread_msg').eq(0).hide();
                if (self.params.thread_level > 0) {
                    $(event.srcElement).parents('.oe_mail_thread').eq(0).hide();
                }
                event.preventDefault();
                return call_defer;
            });
            // event: click on 'Hide' in msg side menu
            this.$element.find('div.oe_mail_thread_display').delegate('a.oe_mail_msg_hide', 'click', function (event) {
                if (! confirm(_t("Do you really want to hide this thread ?"))) { return false; }
                var msg_id = event.srcElement.dataset.id;
                if (! msg_id) return false;
                var call_defer = self.ds.call('message_remove_pushed_notifications', [[self.params.res_id], [parseInt(msg_id)], true]);
                $(event.srcElement).parents('li.oe_mail_thread_msg').eq(0).hide();
                if (self.params.thread_level > 0) {
                    $(event.srcElement).parents('.oe_mail_thread').eq(0).hide();
                }
                event.preventDefault();
                return call_defer;
            });
            // event: click on "Reply" in msg side menu (email style)
            this.$element.find('div.oe_mail_thread_display').delegate('a.oe_mail_msg_reply_by_email', 'click', function (event) {
                var msg_id = event.srcElement.dataset.msg_id;
                var email_mode = (event.srcElement.dataset.type == 'email');
                var formatting = (event.srcElement.dataset.formatting == 'html');
                if (! msg_id) return false;
                self.instantiate_composition_form('reply', email_mode, formatting, msg_id);
                event.preventDefault();
            });
        },
        
        init_comments: function() {
            var self = this;
            // TDE: not necessary
            // this.params.offset = 0;
            // this.comments_structure = {'root_ids': [], 'new_root_ids': [], 'msgs': {}, 'tree_struct': {}, 'model_to_root_ids': {}};

            this.$element.find('div.oe_mail_thread_display').empty();
            // var domain = this.get_fetch_domain(this.comments_structure);
            return this.message_fetch(this.options.domain || []).then();
        },

        /** Fetch messages
         * @param {Array} domain
         * @param {Array} context
         */
        message_fetch: function (additional_domain, additional_context) {
            var self = this;

            this.search['domain'] = _.union(this.options.domain, this.search_results.domain);
            this.search['context'] = _.extend(this.options.context, this.search_results.context);
            if (additional_domain) var fetch_domain = this.search['domain'].concat(additional_domain);
            else var fetch_domain = this.search['domain'];
            if (additional_context) var fetch_context = _.extend(this.search['context'], additional_context);
            else var fetch_context = this.search['context'];

            // first use: use IDS, otherwise set false
            var read_defer = this.ds_msg.call('message_read',
                [false, fetch_domain, this.options.thread_level, fetch_context]
                ).then(function (records) {
                    // if (records.length <= self.options.limit) self.display.show_more = false;
                    // else { self.display.show_more = true; records.pop(); }
                    // else { self.display.show_more = true; records.splice(0, 1); }
                    // else { self.display.show_more = true; }
                    self.display_comments(records);
                    // TODO: move to customize display
                    // if (self.display.show_more == true) self.$element.find('div.oe_mail_thread_more:last').show();
                    // else  self.$element.find('div.oe_mail_thread_more:last').hide();
                });
            return read_defer;
        },

        /* TDE: not necessary as we can read on ids or false */
        // display_comments_from_parameters: function (records) {
        //     if (records.length > 0 && records.length < (records[0].child_ids.length+1) ) this.display.show_more = true;
        //     else this.display.show_more = false;
        //     var defer = this.display_comments(records);
        //     // TODO: move to customize display
        //     if (this.display.show_more == true) $('div.oe_mail_thread_more').eq(-2).show();
        //     else $('div.oe_mail_thread_more').eq(-2).hide();
        //     return defer;
        // },

        /** Display comments
         * @param {Array} records tree structure of records
         */
        // display_comments: function (records) {
        //     console.log(records);
        //     // debugger
        //     var self = this;
        //     var _expendable = false;
        //     _(records).each(function (root_record) {
        //         /* expandable type: add a 'Show more button' */
        //         if (root_record.type == 'expandable') {
        //             _expendable = true;
        //             self.update_fetch_more(true);
        //             self.fetch_more_domain = root_record.domain;
        //             self.fetch_more_context = root_record.context;
        //         }
        //         // display classic root record
        //         else {
        //             var render_res = session.web.qweb.render('mail.wall_thread_container', {});
        //             $('<li class="oe_mail_wall_thread">').html(render_res).appendTo(self.$element.find('ul.oe_mail_wall_threads'));
        //             var thread = new mail.Thread(self, {
        //                 'res_model': root_record.model, 'res_id': root_record.res_id,
        //                 'uid': self.session.uid, 'records': [root_record],
        //                 'parent_id': false, 'thread_level': self.options.thread_level,
        //                 'show_hide': true, 'is_wall': true
        //                 }
        //             );
        //             self.thread_list.push(thread);
        //             thread.appendTo(self.$element.find('li.oe_mail_wall_thread:last'));
        //         }
        //     });
        //     if (! _expendable) {
        //         self.update_fetch_more(false);
        //     }
        // },
        


        display_comments: function (records) {
            var self = this;
            // sort the records
            // mail.ChatterUtils.records_struct_add_records(this.comments_structure, records, this.params.parent_id);
            //build attachments download urls and compute time-relative from dates
            for (var k in records) {
                records[k].timerelative = $.timeago(records[k].date);
                if (records[k].attachments) {
                    for (var l in records[k].attachments) {
                        var url = self.session.origin + '/web/binary/saveas?session_id=' + self.session.session_id + '&model=ir.attachment&field=datas&filename_field=datas_fname&id='+records[k].attachments[l].id;
                        records[k].attachments[l].url = url;
                    }
                }
            }
            _(records).each(function (record) {
                var sub_msgs = [];
                if (record.type == 'expandable') {
                    // TDE: do something :)
                }
                else if ((record.parent_id == undefined || record.parent_id == false || record.parent_id[0] == self.options.parent_id) && self.options.thread_level > 0 ) {
                    // var sub_list = self.comments_structure['tree_struct'][record.id]['direct_childs'];
                    // _(records).each(function (record) {
                    //     //if (record.parent_id == false || record.parent_id[0] == self.params.parent_id) return;
                    //     if (_.indexOf(sub_list, record.id) != -1) {
                    //         sub_msgs.push(record);
                    //     }
                    // });
                    self.display_comment(record);
                    self.thread = new mail.Thread(self, {'res_model': self.options.res_model, 'res_id': self.options.res_id, 'uid': self.options.uid,
                                                            'records': record.child_ids, 'thread_level': (self.options.thread_level-1), 'parent_id': record.id,
                                                            'is_wall': self.options.is_wall});
                    self.$element.find('li.oe_mail_thread_msg:last').append('<div class="oe_mail_thread_subthread"/>');
                    self.thread.appendTo(self.$element.find('div.oe_mail_thread_subthread:last'));
                }
                else if (self.options.thread_level == 0) {
                    self.display_comment(record);
                }
            });
            // mail.ChatterUtils.records_struct_update_after_display(this.comments_structure);
            // update offset for "More" buttons
            if (this.options.thread_level == 0) this.options.offset += records.length;
        },

        /** Displays a record, performs text/link formatting */
        display_comment: function (record) {
            // if (record.type == 'email' && record.state == 'received') {
            if (record.type == 'email') {
                record.mini_url = ('/mail/static/src/img/email_icon.png');
            } else {
                record.mini_url = mail.ChatterUtils.get_image(this.session.prefix, this.session.session_id, 'res.partner', 'image_small', record.author_id[0]);
            }
            // record.body = mail.ChatterUtils.do_replace_expressions(record.body);
            // format date according to the user timezone
            record.date = session.web.format_value(record.date, {type:"datetime"});
            // is the user the author ?
            record.is_author = mail.ChatterUtils.is_author(this, record.author_id[0]);
            // render
            var rendered = session.web.qweb.render('mail.thread.message', {'record': record, 'thread': this, 'params': this.options, 'display': this.display});
            // expand feature
            $(rendered).appendTo(this.$element.children('div.oe_mail_thread_display:first'));
            this.$element.find('div.oe_mail_msg_record_body').expander({
                slicePoint: this.options.msg_more_limit,
                expandText: 'read more',
                userCollapseText: '[^]',
                detailClass: 'oe_mail_msg_tail',
                moreClass: 'oe_mail_expand',
                lessClass: 'oe_mail_reduce',
                });
        },


        /** Display 'show more' button */
        update_fetch_more: function (new_value) {
            if (new_value) {
                    this.$element.find('div.oe_mail_wall_more:last').show();
            } else {
                    this.$element.find('div.oe_mail_wall_more:last').hide();
            }
        },
        
        /** Action: 'shows more' to fetch new messages */
        do_fetch_more: function () {
            return this.message_fetch(this.fetch_more_domain, this.fetch_more_context);
        },



        display_current_user: function () {
            var avatar = mail.ChatterUtils.get_image(this.session.prefix, this.session.session_id, 'res.users', 'image_small', this.options.uid);
            return this.$element.find('img.oe_mail_icon').attr('src', avatar);
        },
        
        do_comment: function () {
            var comment_node = this.$element.find('textarea');
            var body = comment_node.val();
            comment_node.val('');
            return this.ds.call('message_post', [[this.options.res_id], body], {parent_id: this.options.parent_id, mtype: 'comment'}).then(
                this.proxy('init_comments'));
        },
        
        // TDE: not necessary, rewritten above
        // /**
        //  * Create a domain to fetch new comments according to
        //  * comment already present in comments_structure
        //  * @param {Object} comments_structure (see chatter utils)
        //  * @returns {Array} fetch_domain (OpenERP domain style)
        //  */
        // get_fetch_domain: function (comments_structure) {
        //     var domain = [];
        //     var ids = comments_structure.root_ids.slice();
        //     var ids2 = [];
        //     // must be child of current parent
        //     if (this.options.parent_id) { domain.push(['id', 'child_of', this.options.parent_id]); }
        //     _(comments_structure.root_ids).each(function (id) { // each record
        //         ids.push(id);
        //         ids2.push(id);
        //     });
        //     if (this.options.parent_id != false) {
        //         ids2.push(this.options.parent_id);
        //     }
        //     // must not be children of already fetched messages
        //     if (ids.length > 0) {
        //         domain.push('&');
        //         domain.push('!');
        //         domain.push(['id', 'child_of', ids]);
        //     }
        //     if (ids2.length > 0) {
        //         domain.push(['id', 'not in', ids2]);
        //     }
        //     return domain;
        // },
        
        // do_more: function () {
        //     domain = this.get_fetch_domain(this.comments_structure);
        //     return this.fetch_comments(domain);
        // },
    });


    /** 
     * ------------------------------------------------------------
     * mail_thread Widget
     * ------------------------------------------------------------
     *
     * This widget handles the display of the Chatter on documents.
     */

    /* Add mail_thread widget to registry */
    session.web.form.widgets.add('mail_thread', 'openerp.mail.RecordThread');

    /** mail_thread widget: thread of comments */
    mail.RecordThread = session.web.form.AbstractField.extend({
        // QWeb template to use when rendering the object
        template: 'mail.record_thread',

        init: function() {
            this._super.apply(this, arguments);
            this.params = this.options || {};
            this.params.thread_level = this.params.thread_level || 0;
            this.thread = null;
        },
        
        start: function() {
            // NB: all the widget should be modified to check the actual_mode property on view, not use
            // any other method to know if the view is in create mode anymore
            this.view.on("change:actual_mode", this, this._check_visibility);
            this._check_visibility();
        },
        
        _check_visibility: function() {
            this.$element.toggle(this.view.get("actual_mode") !== "create");
        },
        
        set_value: function() {
            this._super.apply(this, arguments);
            if (! this.view.datarecord.id ||
                session.web.BufferedDataSet.virtual_id_regex.test(this.view.datarecord.id)) {
                this.$element.find('.oe_mail_thread').hide();
                return;
            }
            // create and render Thread widget
            this.$element.find('div.oe_mail_recthread_main').empty();
            if (this.thread) this.thread.destroy();
            this.thread = new mail.Thread(this, {'res_model': this.view.model, 'res_id': this.view.datarecord.id, 'uid': this.session.uid,
                                                'thread_level': this.params.thread_level, 'show_post_comment': true, 'limit': 15});
            var thread_done = this.thread.appendTo(this.$element.find('div.oe_mail_recthread_main'));
            return thread_done;
        },
    });


    /** 
     * ------------------------------------------------------------
     * WallView Widget
     * ------------------------------------------------------------
     *
     * This widget handles the display of the Chatter on the Wall.
     */

    /* Add WallView widget to registry */
    session.web.client_actions.add('mail.wall', 'session.mail.Wall');

    /* WallView widget: a wall of messages */
    mail.Wall = session.web.Widget.extend({
        template: 'mail.wall',

        /**
         * @param {Object} parent parent
         * @param {Object} [params]
         * @param {Number} [params.limit=20] number of messages to show and fetch
         * @var {Array} comments_structure (see chatter utils)
         */
        init: function (parent, options) {
            this._super(parent);
            this.options = options || {};
            this.options.domain = options.domain || [];
            this.options.context = options.context || {};
            // TDE: default values in thread
            // this.options.context.res_model = options.res_model || 'mail.thread';
            // this.options.context.parent_id = options.parent_id || false;
            // this.options.context.res_id = options.res_id || false;
            this.options.thread_level = options.thread_level || 1;
            this.thread_list = [];
            this.ds_msg = new session.web.DataSet(this, 'mail.message');
            // for search view
            this.search = {'domain': [], 'context': {}, 'groupby': {}}
            this.search_results = {'domain': [], 'context': {}, 'groupby': {}}
        },

        start: function () {
            this._super.apply(this, arguments);
            // this.bind_events();
            // load mail.message search view
            var search_view_ready = this.load_search_view({}, false);
            // load composition form
            // var compose_done = this.instantiate_composition_form();
            // fetch first threads
            // var messages_fetched = this.message_fetch();
            var thread_displayed = this.display_thread();
            // return (search_view_ready && compose_done && messages_fetched);
            return (search_view_ready && thread_displayed);
        },

        destroy: function () {
            this._super.apply(this, arguments);
            if (this.thread_list) {
                // #TODO: destroy threads
            }

        },

        // TDE: move to thread
        // instantiate_composition_form: function(mode, msg_id) {
        //     if (this.compose_message_widget) {
        //         this.compose_message_widget.destroy();
        //     }
        //     this.compose_message_widget = new mail.ComposeMessage(this, {
        //         'extended_mode': false, 'uid': this.session.uid, 'res_model': this.options.res_model,
        //         'res_id': this.options.res_id, 'mode': mode || 'comment', 'msg_id': msg_id });
        //     var composition_node = this.$element.find('div.oe_mail_wall_action');
        //     composition_node.empty();
        //     var compose_done = this.compose_message_widget.appendTo(composition_node);
        //     return compose_done;
        // },

        /**
         * Override-hack of do_action: automatically reload the chatter.
         * Normally it should be called only when clicking on 'Post/Send'
         * in the composition form. */
        do_action: function(action, on_close) {
            if (this.compose_message_widget) {
                this.compose_message_widget.reinit(); }
            this.message_clean();
            this.message_fetch();
            return this._super(action, on_close);
        },

        // TDE: move to thread
        // /** Bind events */
        // bind_events: function () {
        //     var self = this;
        //     // Click on 'show more'
        //     this.$element.find('button.oe_mail_wall_button_more').click(function () {
        //         return self.do_fetch_more(); 
        //     });
        // },

        /**
         * Load the mail.message search view
         * @param {Object} defaults ??
         * @param {Boolean} hidden some kind of trick we do not care here
         */
        load_search_view: function (defaults, hidden) {
            var self = this;
            this.searchview = new session.web.SearchView(this, this.ds_msg, false, defaults || {}, hidden || false);
            return this.searchview.appendTo(this.$element.find('.oe_view_manager_view_search')).then(function () {
                self.searchview.on_search.add(self.do_searchview_search);
            });
        },

        /**
         * Aggregate the domains, contexts and groupbys in parameter
         * with those from search form, and then calls fetch_comments
         * to actually fetch comments
         * @param {Array} domains
         * @param {Array} contexts
         * @param {Array} groupbys
         */
        do_searchview_search: function(domains, contexts, groupbys) {
            var self = this;
            this.rpc('/web/session/eval_domain_and_context', {
                domains: domains || [],
                contexts: contexts || [],
                group_by_seq: groupbys || []
            }, function (results) {
                self.search_results['context'] = results.context;
                self.search_results['domain'] = results.domain;
                self.search_results['groupby'] = results.group_by;
                self.message_clean();
                return self.display_thread();
            });
        },

        /** Clean the wall */
        message_clean: function() {
            this.$element.find('ul.oe_mail_wall_threads').empty();
        },

        // TDE: move to thread
        // /** Fetch messages
        //  * @param {Array} domain
        //  * @param {Array} context
        //  */
        // message_fetch: function (additional_domain, additional_context) {
        //     this.search['domain'] = _.union(this.options.domain, this.search_results.domain);
        //     this.search['context'] = _.extend(this.options.context, this.search_results.context);
        //     if (additional_domain) var fetch_domain = this.search['domain'].concat(additional_domain);
        //     else var fetch_domain = this.search['domain'];
        //     if (additional_context) var fetch_context = _.extend(this.search['context'], additional_context);
        //     else var fetch_context = this.search['context'];
        //     return this.ds_msg.call('message_read',
        //         [false, fetch_domain, this.options.thread_level, fetch_context]
        //         ).then(this.proxy('display_comments'));
        // },

        /** Display comments
         * @param {Array} records tree structure of records
         */
        display_thread: function () {
            var render_res = session.web.qweb.render('mail.wall_thread_container', {});
            $('<li class="oe_mail_wall_thread">').html(render_res).appendTo(this.$element.find('ul.oe_mail_wall_threads'));
            var thread = new mail.Thread(self, {
                'domain': this.options.domain, 'context': this.options.context,
                'uid': this.session.uid, 'thread_level': this.options.thread_level,
                // display options
                'show_hide': true, 'show_delete': false,
                }
            );
            thread.appendTo(this.$element.find('li.oe_mail_wall_thread:last'));
            this.thread_list.push(thread);
        },

        // TDE: move to thread
        // /** Display comments
        //  * @param {Array} records tree structure of records
        //  */
        // display_comments: function (records) {
        //     console.log(records);
        //     // debugger
        //     var self = this;
        //     var _expendable = false;
        //     _(records).each(function (root_record) {
        //         /* expandable type: add a 'Show more button' */
        //         if (root_record.type == 'expandable') {
        //             _expendable = true;
        //             self.update_fetch_more(true);
        //             self.fetch_more_domain = root_record.domain;
        //             self.fetch_more_context = root_record.context;
        //         }
        //         // display classic root record
        //         else {
        //             var render_res = session.web.qweb.render('mail.wall_thread_container', {});
        //             $('<li class="oe_mail_wall_thread">').html(render_res).appendTo(self.$element.find('ul.oe_mail_wall_threads'));
        //             var thread = new mail.Thread(self, {
        //                 'res_model': root_record.model, 'res_id': root_record.res_id,
        //                 'uid': self.session.uid, 'records': [root_record],
        //                 'parent_id': false, 'thread_level': self.options.thread_level,
        //                 'show_hide': true, 'is_wall': true
        //                 }
        //             );
        //             self.thread_list.push(thread);
        //             thread.appendTo(self.$element.find('li.oe_mail_wall_thread:last'));
        //         }
        //     });
        //     if (! _expendable) {
        //         self.update_fetch_more(false);
        //     }
        // },
        
        // TDE: move to thread
        // /** Display 'show more' button */
        // update_fetch_more: function (new_value) {
        //     if (new_value) {
        //             this.$element.find('div.oe_mail_wall_more:last').show();
        //     } else {
        //             this.$element.find('div.oe_mail_wall_more:last').hide();
        //     }
        // },
        
        // /** Action: 'shows more' to fetch new messages */
        // do_fetch_more: function () {
        //     return this.message_fetch(this.fetch_more_domain, this.fetch_more_context);
        // },
    });
};
