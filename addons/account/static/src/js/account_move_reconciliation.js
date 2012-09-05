openerp.account = function(instance) {
var _t = instance.web._t,
   _lt = instance.web._lt;
instance.web.views.add('form_clone', 'instance.account.extend_form_view');
 
instance.account.extend_viewmanager = instance.web.ViewManagerAction.include({
    start : function(){
        this._super()
        if(this.action.context && this.action.context.extended_view_id && this.action.context.extended_model)
            this.setup_exended_form_view(this.action.context.extended_model, this.action.context.extended_view_id);
    }, 
    setup_exended_form_view: function(view_model, view_id){
        var self = this;
        from_view = this.registry.get_object('form_clone');
        this.dataset_form = new instance.web.DataSetSearch(this, view_model, this.action.context, this.action.domain);
        this.dataset_loaded  = this.dataset_form.read_slice();
        obj_from_view = new from_view(self, self.dataset_form, view_id, options={});
        obj_from_view.template = 'ExtendedFormView';
        view_form = obj_from_view.appendTo(self.$el.find('.oe_extended_form_view'));
        $.when(view_form, this.dataset_loaded).then(function() {
                obj_from_view.on_pager_action('first');
        });
    } 
    
})
instance.account.extend_form_view = instance.web.FormView.extend({
    on_loaded: function(data) {
         this._super.apply(this,arguments);
         var self = this
         this.$el.find(".oe_reconcile").on('click', this.do_reconcilation)
         this.$el.find(".oe_nothing_to_reconcile").on('click', this.do_nothing_to_reconcile)
         this.$el.on('click','a[data-pager-action]',function() {
            var action = $(this).data('pager-action');
            self.on_pager_action(action);
        });
    },
    do_reconcilation:function(event){
        var self = this
        var list_view = this.getParent().views['list'].controller
        ids = list_view.get_selected_ids()
        if (ids.length == 0) {
            instance.web.dialog($("<div />").text(_t("You must choose at least one record.")), { title: _t("Warning"), modal: true });
            return false;
        }
        var additional_context = _.extend({
            active_id: ids[0],
            active_ids: ids,
            active_model: list_view.dataset.model
        });
        self.rpc("/web/action/load", {
            action_id: py.eval(event.target.name),
            context: additional_context
            }, function(result) {
                result.result.context = _.extend(result.result.context || {},
                    additional_context);
                result.result.flags = result.result.flags || {};
                result.result.flags.new_window = true;
                self.do_action(result.result, function () {
                    self.dataset.read_slice().done(function(){
                        self.on_pager_action('next');
                    });
            });
        });
    },

        
    do_nothing_to_reconcile:function(){
        var self = this;
        this.dataset.call(event.target.name, [[self.datarecord.id], self.dataset.context]).then(function() {
            self.dataset.read_slice().done(function(){
                self.on_pager_action('next');
            });
        });
    },
    
    do_update_pager: function(hide_index) {
        var index = this.dataset.index + 1
        if (this.dataset.ids.length == 0)
            index = 0;
        index = hide_index ? '-' : index;
        this.$el.find('span.oe_pager_index_extend').html(index).end()
                   .find('span.oe_pager_count_extend').html(this.dataset.ids.length);
    },

    do_search_move_line: function(partner_ids){
        var viewmanager = this.getParent();
        viewmanager.action.context.next_partner_only = true;
        viewmanager.action.context.partner_id = partner_ids;
        viewmanager.searchview.do_search();
    },
    
    on_pager_action: function(action) {
        var self = this
        if (this.dataset.ids.length == 0){
            self.datarecord = {}
            _(this.fields).each(function (field, f) {
                field.set_value(self.datarecord[f] || false);
            });
            self.do_update_pager();
            self.do_search_move_line([]);
        }
        else{        
            $.when(this._super(action)).then(function() {
                var id = self.get_fields_values().partner_id;
                self.do_search_move_line([id]);
            });
        }
    },
  })

}
