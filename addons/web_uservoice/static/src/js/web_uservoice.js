openerp.web_uservoice = function(instance) {

instance.web_uservoice.UserVoice = instance.web.Widget.extend({
    template: 'Systray.UserVoice',
    default_forum: '77459',

    init: function() {
        this._super.apply(this, arguments);
        this.uservoiceForums = {};
        this.uservoiceOptions = {
            key: 'openerpsa',
            host: 'feedback.openerp.com',
            forum: this.default_forum,
            lang: 'en',
            showTab: false
        };

        instance.webclient.menu.on('menuClicked', this, function(id, $clicked_menu) {
            var root = $clicked_menu.parents('div.oe_menu').length === 1;
            if (id && root) {
                this.uservoiceOptions.forum = this.uservoiceForums[id] || this.default_forum;
            }
        });
    },

    start: function() {
        this._super();

        var self = this;
        var forum_mapping = {
            'accounting': '87921',
            'administration': '87935',
            'human resources': '87923',
            'knowledge': '87927',
            'manufacturing': '87915',
            'marketing': '87925',
            'point of sale': '87929',
            'project': '87919',
            'purchases': '87911',
            'sales': '87907',
            'tools': '87933',
            'warehouse': '87913',
        };

        var ds = new instance.web.DataSetSearch(this, 'ir.ui.menu', {lang: 'NO_LANG'}, [['parent_id', '=', false]]);

        ds.read_slice(['name']).then(function(result) {
            _.each(result, function(menu) {
                self.uservoiceForums[menu.id] = forum_mapping[menu.name.toLowerCase()] || self.default_forum;
            });
        });

        this.$element.find('a').click(function(e) {
            e.preventDefault();
            UserVoice.Popin.show(self.uservoiceOptions);
            return false;
        });
    }
});

instance.web.UserMenu.include({
    do_update: function() {
        var self = this;
        this._super();
        this.update_promise.then(function() {
            if (self.uservoice) {
                self.uservoice.destroy();
            }
            self.uservoice = new instance.web_uservoice.UserVoice(self);
            self.uservoice.appendTo(instance.webclient.$element.find('.oe_systray'));
        });
    }
});

if (instance.webclient) {
    $(function() {
        var src = ("https:" == document.location.protocol ? "https://" : "http://") + "cdn.uservoice.com/javascripts/widgets/tab.js";
        $.getScript(src);
    });
}

};

