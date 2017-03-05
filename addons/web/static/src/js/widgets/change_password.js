odoo.define('web.ChangePassword', function (require) {
"use strict";

/**
 * This file defines a client action that opens in a dialog (target='new') and
 * allows the user to change his password.
 */

var core = require('web.core');
var Dialog = require('web.Dialog');
var Widget = require('web.Widget');
var web_client = require('web.web_client');

var _t = core._t;

var ChangePassword = Widget.extend({
    template: "ChangePassword",

    /**
     * @fixme: weird interaction with the parent for the $buttons handling
     *
     * @override
     * @returns {Deferred}
     */
    start: function () {
        var self = this;
        web_client.set_title(_t("Change Password"));
        var $button = self.$('.oe_form_button');
        $button.appendTo(this.getParent().$footer);
        $button.eq(1).click(function () {
            self.$el.parents('.modal').modal('hide');
        });
        $button.eq(0).click(function () {
            self.performRPC('/web/session/change_password', {
                fields: $('form[name=change_password_form]').serializeArray(),
            }).done(function (result) {
                if (result.error) {
                    self._display_error(result);
                } else {
                   self.do_action('logout');
                }
            });
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Displays the error in a dialog
     *
     * @private
     * @param {Object} error
     * @param {string} error.error
     * @param {string} error.title
     */
    _display_error: function (error) {
        return new Dialog(this, {
            size: 'medium',
            title: error.title,
            $content: $('<div>').html(error.error)
        }).open();
    },
});

core.action_registry.add("change_password", ChangePassword);

return ChangePassword;

});
