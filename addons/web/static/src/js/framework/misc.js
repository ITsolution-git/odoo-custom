odoo.define('web.framework', ['web.core', 'web.crash_manager', 'web.session', 'web.utils', 'web.Widget'], function (require) {
"use strict";

var core = require('web.core');
var crash_manager = require('web.crash_manager');
var session = require('web.session');
var utils = require('web.utils');
var Widget = require('web.Widget');

var _t = core._t;
var Spinner = window.Spinner;

var messages_by_seconds = function() {
    return [
        [0, _t("Loading...")],
        [20, _t("Still loading...")],
        [60, _t("Still loading...<br />Please be patient.")],
        [120, _t("Don't leave yet,<br />it's still loading...")],
        [300, _t("You may not believe it,<br />but the application is actually loading...")],
        [420, _t("Take a minute to get a coffee,<br />because it's loading...")],
        [3600, _t("Maybe you should consider reloading the application by pressing F5...")]
    ];
};

var Throbber = Widget.extend({
    template: "Throbber",
    start: function() {
        var opts = {
          lines: 13, // The number of lines to draw
          length: 7, // The length of each line
          width: 4, // The line thickness
          radius: 10, // The radius of the inner circle
          rotate: 0, // The rotation offset
          color: '#FFF', // #rgb or #rrggbb
          speed: 1, // Rounds per second
          trail: 60, // Afterglow percentage
          shadow: false, // Whether to render a shadow
          hwaccel: false, // Whether to use hardware acceleration
          className: 'spinner', // The CSS class to assign to the spinner
          zIndex: 2e9, // The z-index (defaults to 2000000000)
          top: 'auto', // Top position relative to parent in px
          left: 'auto' // Left position relative to parent in px
        };
        this.spin = new Spinner(opts).spin(this.$el[0]);
        this.start_time = new Date().getTime();
        this.act_message();
    },
    act_message: function() {
        var self = this;
        setTimeout(function() {
            if (self.isDestroyed())
                return;
            var seconds = (new Date().getTime() - self.start_time) / 1000;
            var mes;
            _.each(messages_by_seconds(), function(el) {
                if (seconds >= el[0])
                    mes = el[1];
            });
            self.$(".oe_throbber_message").html(mes);
            self.act_message();
        }, 1000);
    },
    destroy: function() {
        if (this.spin)
            this.spin.stop();
        this._super();
    },
});


// special tweak for the web client
var old_async_when = $.async_when;
$.async_when = function() {
    if (session.synch)
        return $.when.apply(this, arguments);
    else
        return old_async_when.apply(this, arguments);
};


/** Setup blockui */
if ($.blockUI) {
    $.blockUI.defaults.baseZ = 1100;
    $.blockUI.defaults.message = '<div class="openerp oe_blockui_spin_container" style="background-color: transparent;">';
    $.blockUI.defaults.css.border = '0';
    $.blockUI.defaults.css["background-color"] = '';
}


var throbbers = [];

function blockUI () {
    var tmp = $.blockUI.apply($, arguments);
    var throbber = new Throbber();
    throbbers.push(throbber);
    throbber.appendTo($(".oe_blockui_spin_container"));
    return tmp;
}

function unblockUI () {
    _.invoke(throbbers, 'destroy');
    throbbers = [];
    return $.unblockUI.apply($, arguments);
}

/**
 * Redirect to url by replacing window.location
 * If wait is true, sleep 1s and wait for the server i.e. after a restart.
 */
function redirect (url, wait) {
    // Dont display a dialog if some xmlhttprequest are in progress
    crash_manager.disable();

    var load = function() {
        var old = "" + window.location;
        var old_no_hash = old.split("#")[0];
        var url_no_hash = url.split("#")[0];
        location.assign(url);
        if (old_no_hash === url_no_hash) {
            location.reload(true);
        }
    };

    var wait_server = function() {
        session.rpc("/web/webclient/version_info", {}).done(load).fail(function() {
            setTimeout(wait_server, 250);
        });
    };

    if (wait) {
        setTimeout(wait_server, 1000);
    } else {
        load();
    }
}

//  * Client action to reload the whole interface.
//  * If params.menu_id, it opens the given menu entry.
//  * If params.wait, reload will wait the openerp server to be reachable before reloading
 
function Reload(parent, action) {
    var params = action.params || {};
    var menu_id = params.menu_id || false;
    var l = window.location;

    var sobj = $.deparam(l.search.substr(1));
    if (params.url_search) {
        sobj = _.extend(sobj, params.url_search);
    }
    var search = '?' + $.param(sobj);

    var hash = l.hash;
    if (menu_id) {
        hash = "#menu_id=" + menu_id;
    }
    var url = l.protocol + "//" + l.host + l.pathname + search + hash;

    redirect(url, params.wait);
}

core.action_registry.add("reload", Reload);


/**
 * Client action to go back home.
 */
function Home (parent, action) {
    var url = '/' + (window.location.search || '');
    redirect(url, action && action.params && action.params.wait);
}
core.action_registry.add("home", Home);

/**
 * Client action to go back in breadcrumb history.
 * If can't go back in history stack, will go back to home.
 */
function HistoryBack (parent) {
    parent.history_back().fail(function () {
        Home(parent);
    });
}
core.action_registry.add("history_back", HistoryBack);

function login() {
    redirect('/web/login');
}
core.action_registry.add("login", login);

function logout() {
    redirect('/web/session/logout');
}
core.action_registry.add("logout", logout);

/**
 * Client action to refresh the session context (making sure
 * HTTP requests will have the right one) then reload the
 * whole interface.
 */
function ReloadContext (parent, action) {
    // side-effect of get_session_info is to refresh the session context
    session.rpc("/web/session/get_session_info", {}).then(function() {
        Reload(parent, action);
    });
}
core.action_registry.add("reload_context", ReloadContext);

// nvd3 customization
//-------------------------------------------------------------------------
nv.dev = false;  // sets nvd3 library in production mode

// monkey patch nvd3 to allow removing eventhandler on windowresize events
// see https://github.com/novus/nvd3/pull/396 for more details

// Adds a resize listener to the window.
nv.utils.onWindowResize = function(fun) {
    if (fun === null) return;
    window.addEventListener('resize', fun);
};

// Backwards compatibility with current API.
nv.utils.windowResize = nv.utils.onWindowResize;

// Removes a resize listener from the window.
nv.utils.offWindowResize = function(fun) {
    if (fun === null) return;
    window.removeEventListener('resize', fun);
};

// monkey patch nvd3 to prevent crashes when user changes view and nvd3 tries
// to remove tooltips after 500 ms...  seriously nvd3, what were you thinking?
nv.tooltip.cleanup = function () {
    $('.nvtooltip').remove();
};

// Bootstrap customization
//-------------------------------------------------------------------------
/* Bootstrap defaults overwrite */
$.fn.tooltip.Constructor.DEFAULTS.placement = 'auto top';
$.fn.tooltip.Constructor.DEFAULTS.html = true;
$.fn.tooltip.Constructor.DEFAULTS.trigger = 'hover focus click';
$.fn.tooltip.Constructor.DEFAULTS.container = 'body';
//overwrite bootstrap tooltip method to prevent showing 2 tooltip at the same time
var bootstrap_show_function = $.fn.tooltip.Constructor.prototype.show;
$.fn.modal.Constructor.prototype.enforceFocus = function () { };
$.fn.tooltip.Constructor.prototype.show = function () {
    $('.tooltip').remove();
    //the following fix the bug when using placement
    //auto and the parent element does not exist anymore resulting in
    //an error. This should be remove once we updade bootstrap to a version that fix the bug
    //edit: bug has been fixed here : https://github.com/twbs/bootstrap/pull/13752
    var e = $.Event('show.bs.' + this.type);
    var inDom = $.contains(document.documentElement, this.$element[0]);
    if (e.isDefaultPrevented() || !inDom) return;
    return bootstrap_show_function.call(this);
};

// jquery customization
//-------------------------------------------------------------------------
jQuery.expr[":"].Contains = jQuery.expr.createPseudo(function(arg) {
    return function( elem ) {
        return jQuery(elem).text().toUpperCase().indexOf(arg.toUpperCase()) >= 0;
    };
});

/** Custom jQuery plugins */
$.fn.getAttributes = function() {
    var o = {};
    if (this.length) {
        for (var attr, i = 0, attrs = this[0].attributes, l = attrs.length; i < l; i++) {
            attr = attrs.item(i);
            o[attr.nodeName] = attr.value;
        }
    }
    return o;
};
$.fn.openerpClass = function(additionalClass) {
    // This plugin should be applied on top level elements
    additionalClass = additionalClass || '';
    if (!!$.browser.msie) {
        additionalClass += ' openerp_ie';
    }
    return this.each(function() {
        $(this).addClass('openerp ' + additionalClass);
    });
};
$.fn.openerpBounce = function() {
    return this.each(function() {
        $(this).css('box-sizing', 'content-box').effect('bounce', {distance: 18, times: 5}, 250);
    });
};

// jquery autocomplete tweak to allow html and classnames
var proto = $.ui.autocomplete.prototype,
    initSource = proto._initSource;

function filter( array, term ) {
    var matcher = new RegExp( $.ui.autocomplete.escapeRegex(term), "i" );
    return $.grep( array, function(value_) {
        return matcher.test( $( "<div>" ).html( value_.label || value_.value || value_ ).text() );
    });
}

$.extend( proto, {
    _initSource: function() {
        if ( this.options.html && $.isArray(this.options.source) ) {
            this.source = function( request, response ) {
                response( filter( this.options.source, request.term ) );
            };
        } else {
            initSource.call( this );
        }
    },

    _renderItem: function( ul, item) {
        return $( "<li></li>" )
            .data( "item.autocomplete", item )
            .append( $( "<a></a>" )[ this.options.html ? "html" : "text" ]( item.label ) )
            .appendTo( ul )
            .addClass(item.classname);
    }
});




return {
    blockUI: blockUI,
    unblockUI: unblockUI,
    redirect: redirect,
};

});

odoo.define('web.session', ['web.Session'], function (require) {
    var Session = require('web.Session');
    var modules = odoo._modules;
    return new Session(undefined, undefined, {modules:modules});
});

