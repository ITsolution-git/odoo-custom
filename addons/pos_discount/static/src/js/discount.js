openerp.pos_discount = function(instance){
    var module   = instance.point_of_sale;
    var round_pr = instance.web.round_precision

    module.DiscountButton = module.ActionButtonWidget.extend({
        template: 'DiscountButton',
        button_click: function(){
            var self = this;
            this.gui.show_popup('number',{
                'title': 'Discount Percentage',
                'value': this.pos.config.discount_pc,
                'confirm': function(val) {
                    val = Math.round(Math.max(0,Math.min(100,val)));
                    self.apply_discount(val);
                },
            });
        },
        apply_discount: function(pc) {
            var order    = this.pos.get_order();
            var lines    = order.get_orderlines();
            var product  = this.pos.db.get_product_by_id(this.pos.config.discount_product_id[0]);

            // Remove existing discounts
            var i = 0;
            do {
                if (lines[i].get_product() === product) {
                    order.remove_orderline(lines[i]);
                } else {
                    i++;
                }
            } while ( i < lines.length );

            // Add discount
            var discount = - pc / 100.0 * order.get_total_with_tax();

            if( discount < 0 ){
                order.add_product(product, { price: discount });
            }
        },
    });

    module.define_action_button({
        'name': 'discount',
        'widget': module.DiscountButton,
        'condition': function(){
            return this.pos.config.iface_discount && this.pos.config.discount_product_id;
        },
    });

};

