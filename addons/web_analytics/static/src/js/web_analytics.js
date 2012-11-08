
var _gaq = _gaq || [];  // asynchronous stack used by google analytics

openerp.web_analytics = function(instance) {

    /** The Google Analytics Module inserts the Google Analytics JS Snippet
     *  at the top of the page, and sends to google an url each time the
     *  openerp url is changed.
     *  The pushes of the urls is made by triggering the 'state_pushed' event in the
     *  web_client.do_push_state() method which is responsible of changing the openerp current url
     */

    // Google Analytics Code snippet
    (function() {
        var ga   = document.createElement('script');
        ga.type  = 'text/javascript';
        ga.async = true
        ga.src   = ('https:' == document.location.protocol ? 'https://ssl' : 'http://www') + '.google-analytics.com/ga.js';
        var s = document.getElementsByTagName('script')[0];
        s.parentNode.insertBefore(ga,s);
    })();

    if (instance.webclient) {

        // Set the account and domain to start tracking
        _gaq.push(['_setAccount', 'UA-7333765-1']);    // vta@openerp.com localhost
        _gaq.push(['_setDomainName', 'none']);  // Change for the real domain

        // Track user types
        if (instance.session.uid !== 1) {
            if ((/\.demo.openerp.com/).test(instance.session.server)) {
                _gaq.push(['_setCustomVar', 1, 'User Type', 'Demo User', 1]);
            } else {
                _gaq.push(['_setCustomVar', 1, 'User Type', 'Normal User', 1]);
            }
        } else {
            _gaq.push(['_setCustomVar', 1, 'User Type', 'Admin User', 1]);
        }

        // Track object usage 
        _gaq.push(['_setCustomVar', 2, 'Object', 'no_model', 3]);
        // Tack view usage
        _gaq.push(['_setCustomVar', 3, 'View Type', 'default', 3]);

        _gaq.push(['_trackPageview']);

        var self = this;
        instance.webclient.on('state_pushed', self, function(state) {
            // Track only pages corresponding to a 'normal' view of OpenERP, views
            // related to client actions are tracked by the action manager
            if (state.model && state.view_type) {                
                // Track object usage 
                _gaq.push(['_setCustomVar', 2, 'Object', state.model, 3]);
                // Tack view usage
                _gaq.push(['_setCustomVar', 3, 'View Type', state.view_type, 3]);
                // Track the page
                var url = instance.web_analytics.parseUrl({'model': state.model, 'view_type': state.view_type});
                _gaq.push(['_trackPageview', url]);
            }
        });
    }

    // Track the events related with the creation and the  modification of records
    instance.web.FormView = instance.web.FormView.extend({
        init: function(parent, dataset, view_id, options) {
            this._super.apply(this, arguments);
            var self = this;
            this.on('record_created', self, function(r) {
                var url = instance.web_analytics.parseUrl({'model': this.model, 'view_type': 'form'});
                _gaq.push(['_trackEvent', this.model, 'on_button_create_save', url]);
            });
            this.on('record_saved', self, function(r) {
                var url = instance.web_analytics.parseUrl({'model': this.model, 'view_type': 'form'});
                _gaq.push(['_trackEvent', this.model, 'on_button_edit_save', url]);
            });
        }
    });

    // Track client actions
    instance.web.ActionManager.include({
        ir_actions_client: function (action, options) {
            var url = instance.web_analytics.parseUrl({'action': action.tag});
            _gaq.push(['_trackPageview', url]);
            return this._super.apply(this, arguments);
        },
    });

    // Track button events
    instance.web.View.include({
        do_execute_action: function(action_data, dataset, record_id, on_closed) {
            console.log(action_data);
            var category = this.model || dataset.model || '';
            var action;
            if (action_data.name && _.isNaN(action_data.name-0)) {
                action = action_data.name;                
            } else {
                action = action_data.string || action_data.special || '';
            }
            var label = instance.web_analytics.parseUrl({'model': category, 'view_type': this.view_type});
            _gaq.push(['_trackEvent', category, action, label]);
            return this._super.apply(this, arguments);
        },
    });

    // Track error events
    instance.web.CrashManager = instance.web.CrashManager.extend({
        show_error: function(error) {
            var hash = window.location.hash;
            var params = $.deparam(hash.substr(hash.indexOf('#')+1));
            var options = {};
            if (params.model && params.view_type) {
                options = {'model': params.model, 'view_type': params.view_type};
            } else {
                options = {'action': params.action};
            }
            var label = instance.web_analytics.parseUrl(options);
            if (error.code) {
                _gaq.push(['_trackEvent', error.message, error.data.fault_code, label, ,true]);
            } else {
                _gaq.push(['_trackEvent', error.type, error.data.debug, label, ,true]);
            }
            this._super.apply(this, arguments);
        },
    });

    instance.web_analytics.parseUrl = function(options) {
        var url = '';
        _.each(options, function(value, key) {
            url += '/' + key + '=' + value;
        });
        return url;
    };

};