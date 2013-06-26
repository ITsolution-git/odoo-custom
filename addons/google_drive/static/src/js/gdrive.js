openerp.google_drive = function (instance, m) {
    var _t = instance.web._t,
        QWeb = instance.web.qweb;

    instance.web.Sidebar.include({
        start: function () {
            var self = this;
            var ids
            this._super.apply(this, arguments);
            var view = self.getParent();
            var result;
            if (view.fields_view.type == "form") {
                ids = []
                view.on("load_record", self, function (r) {
                    ids = [r.id]
                    self.add_gdoc_items(view, r.id)
                });
            }
        },
        add_gdoc_items: function (view, res_id) {
            var self = this;
            var gdoc_item = _.indexOf(_.pluck(self.items.other, 'classname'), 'oe_share_gdoc');
            if (gdoc_item !== -1) {
                self.items.other.splice(gdoc_item, 1);
            }
            if (res_id) {
                view.sidebar_eval_context().done(function (context) {
                    var ds = new instance.web.DataSet(this, 'google.drive.config', context);
                    ds.call('get_google_drive_config', [view.dataset.model, res_id, context]).done(function (r) {
                        if (!_.isEmpty(r)) {
                            _.each(r, function (res) {
                                var g_item = _.indexOf(_.pluck(self.items.other, 'label'), res.name);
                                if (g_item !== -1) {
                                    self.items.other.splice(g_item, 1);
                                }
                                self.add_items('other', [{
                                        label: res.name+ '<img style="position:absolute;right:5px;height:20px;width:20px;" title="Google Drive" src="google_drive/static/src/img/drive_icon.png"/>',
                                        config_id: res.id,
                                        res_id: res_id,
                                        res_model: view.dataset.model,
                                        callback: self.on_google_doc,
                                        classname: 'oe_share_gdoc'
                                    },
                                ]);
                            })
                        }
                    });
                });
            }
        },

        fetch: function (model, fields, domain, ctx) {
            return new instance.web.Model(model).query(fields).filter(domain).context(ctx).all()
        },

        on_google_doc: function (doc_item) {
            var self = this;
            self.config = doc_item;
            var loaded = self.fetch('google.drive.config', ['google_drive_resource_id', 'google_drive_client_id'], [['id', '=', doc_item.config_id]])
                .then(function (configs) {
                var ds = new instance.web.DataSet(self, 'google.drive.config');
                ds.call('get_google_doc_name', [[doc_item.config_id], doc_item.res_id,configs[0].google_drive_resource_id]).done(function (r) {
                    if (!_.isEmpty(r)) {
                        _.each(r, function (res) {
                            if(res.url)
                                {
                                    window.open(res.url, '_blank');
                                }
                        });
                    }
                });
            });
        },

    });
};