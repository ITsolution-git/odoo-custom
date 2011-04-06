
openerp.base.list = function (openerp) {

openerp.base.views.add('list', 'openerp.base.ListView');
openerp.base.ListView = openerp.base.Controller.extend({
    init: function(view_manager, session, element_id, dataset, view_id) {
        this._super(session, element_id);
        this.view_manager = view_manager;
        this.dataset = dataset;
        this.model = dataset.model;
        this.view_id = view_id;
        this.name = "";
        // TODO: default to action.limit
        // TODO: decide if limit is a property of DataSet and thus global to all views (calendar ?)
        this.limit = 80;

        this.cols = [];

        this.$table = null;
        this.colnames = [];
        this.colmodel = [];

        this.event_loading = false; // TODO in the future prevent abusive click by masking
    },
    start: function() {
        //this.log('Starting ListView '+this.model+this.view_id)
        return this.rpc("/base/listview/load", {"model": this.model, "view_id":this.view_id}, this.on_loaded);
    },
    on_loaded: function(data) {
        this.fields_view = data.fields_view;
        //this.log(this.fields_view);
        this.name = "" + this.fields_view.arch.attrs.string;
        this.$element.html(QWeb.render("ListView", {"fields_view": this.fields_view}));
        this.$table = this.$element.find("table");
        this.cols = [];
        this.colnames = [];
        this.colmodel = [];
        // TODO uss a object for each col, fill it with view and fallback to dataset.model_field
        var tree = this.fields_view.arch.children;
        for(var i = 0; i < tree.length; i++)  {
            var col = tree[i];
            if(col.tag == "field") {
                this.cols.push(col.attrs.name);
                this.colnames.push(col.attrs.name);
                this.colmodel.push({ name: col.attrs.name, index: col.attrs.name });
            }
        }
        this.dataset.fields = this.cols;

        var width = this.$element.width();
        this.$table.jqGrid({
            datatype: "local",
            height: "100%",
            rowNum: 100,
            //rowList: [10,20,30],
            colNames: this.colnames,
            colModel: this.colmodel,
            //pager: "#plist47",
            viewrecords: true,
            caption: this.name
        }).setGridWidth(width);

        var self = this;
        $(window).bind('resize', function() {
            self.$element.children().hide();
            self.$table.setGridWidth(self.$element.width());
            self.$element.children().show();
        }).trigger('resize');
        
        // sidebar stuff
        if (this.view_manager.sidebar)
            this.view_manager.sidebar.load_multi_actions();
    },
    do_fill_table: function(records) {
        this.$table
            .clearGridData()
            .addRowData('id', records);
    },
    do_show: function () {
        // TODO: re-trigger search
        this.$element.show();
    },
    do_hide: function () {
        this.$element.hide();
    },
    do_search: function (domains, contexts, groupbys) {
        var self = this;
        this.rpc('/base/session/eval_domain_and_context', {
            domains: domains,
            contexts: contexts,
            group_by_seq: groupbys
        }, function (results) {
            // TODO: handle non-empty results.group_by with read_group
            self.dataset.context = results.context;
            self.dataset.domain = results.domain;
            self.dataset.read_slice(self.dataset.fields, 0, self.limit, self.do_fill_table);
        });
    },
    do_update: function () {
        var self = this;
        self.dataset.read(self.dataset.ids, self.dataset.fields, self.do_fill_table);
    }
});

openerp.base.TreeView = openerp.base.Controller.extend({
});

};

// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax:
