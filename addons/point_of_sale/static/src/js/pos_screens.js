
// this file contains the screens definitions. Screens are the
// content of the right pane of the pos, containing the main functionalities. 
// screens are contained in the PosWidget, in pos_widget.js
// all screens are present in the dom at all time, but only one is shown at the
// same time. 
//
// transition between screens is made possible by the use of the screen_selector,
// which is responsible of hiding and showing the screens, as well as maintaining
// the state of the screens between different orders.
//
// all screens inherit from ScreenWidget. the only addition from the base widgets
// are show() and hide() which shows and hides the screen but are also used to 
// bind and unbind actions on widgets and devices. The screen_selector guarantees
// that only one screen is shown at the same time and that show() is called after all
// hide()s

function openerp_pos_screens(instance, module){ //module is instance.point_of_sale
    var QWeb = instance.web.qweb;

    module.ScreenSelector = instance.web.Class.extend({
        init: function(options){
            this.pos = options.pos;

            this.screen_set = options.screen_set || {};

            this.popup_set = options.popup_set || {};

            this.default_client_screen = options.default_client_screen;
            this.default_cashier_screen = options.default_cashier_screen;

            this.current_client_screen = this.screen_set[this.default_client_screen];
            
            this.current_cashier_screen = this.screen_set[this.default_cashier_screen];

            this.current_popup = null;

            this.current_mode = options.default_mode || 'client';

            this.current_screen = this.current_mode === 'client' ? 
                this.current_client_screen:
                this.current_cashier_screen;

            var current = null;
            for(screen_name in this.screen_set){
                var screen = this.screen_set[screen_name];
                if(screen === this.current_screen){
                    current = screen;
                }else{
                    screen.hide();
                }
            }
            
            for(popup_name in this.popup_set){
                this.popup_set[popup_name].hide();
            }

            if(current){
                current.show();
            }

            this.selected_order = this.pos.get('selectedOrder');
            this.selected_order.set({ 
                user_mode : this.current_mode,
                client_screen: this.default_client_screen,
                cashier_screen: this.default_cashier_screen,
            });

            this.pos.bind('change:selectedOrder', this.load_saved_screen, this);
        },
        add_screen: function(screen_name, screen){
            screen.hide();
            this.screen_set[screen_name] = screen;
            return this;
        },
        show_popup: function(name,message){
            console.log('show_popup:',message);
            if(this.current_popup){
                this.close_popup();
            }
            this.current_popup = this.popup_set[name];
            this.current_popup.set_message(message);
            this.current_popup.show();
        },
        close_popup: function(){
            if(this.current_popup){
                this.current_popup.hide();
                this.current_popup = null;
            }
        },
        load_saved_screen:  function(){
            this.close_popup();

            var selectedOrder = this.pos.get('selectedOrder');
            
            if(this.current_mode === 'client'){
                this.set_current_screen(selectedOrder.get('client_screen') || this.default_client_screen);
            }else if(this.current_mode === 'cashier'){
                this.set_current_screen(selectedOrder.get('cashier_screen') || this.default_cashier_screen);
            }
            this.selected_order = selectedOrder;
        },
        set_user_mode: function(user_mode){
            if(user_mode !== this.current_mode){
                this.close_popup();
                this.current_mode = user_mode;
                this.load_saved_screen();
            }
        },
        get_user_mode: function(){
            return this.current_mode;
        },
        set_current_screen: function(screen_name){
            var screen = this.screen_set[screen_name];

            this.close_popup();
            var selectedOrder = this.pos.get('selectedOrder');
            if(this.current_mode === 'client'){
                selectedOrder.set({'client_screen': screen_name});
            }else{
                selectedOrder.set({'cashier_screen': screen_name});
            }

            if(screen && screen !== this.current_screen){
                if(this.current_screen){
                    this.current_screen.hide();
                }
                this.current_screen = screen;
                this.current_screen.show();
            }
        },
    });

    module.ScreenWidget = module.PosBaseWidget.extend({
        show: function(){
            if(this.$element){
                this.$element.show();
            }
        },
        hide: function(){
            if(this.$element){
                this.$element.hide();
            }
            if(this.pos.barcode_reader){
                this.pos.barcode_reader.reset_action_callbacks();
            }
            if(this.pos_widget.action_bar){
                this.pos_widget.action_bar.destroy_buttons();
            }
        },
    });

    module.PopUpWidget = module.ScreenWidget.extend({
        hide: function(){
            if(this.$element){
                this.$element.hide();
            }
        },
        set_message: function(message){
            this.message = message || '';
            this.renderElement();
        },
    });

    module.HelpPopupWidget = module.PopUpWidget.extend({
        template:'HelpPopupWidget',
        show: function(){
            this._super();
            this.pos.proxy.help_needed();
            var self = this;
            
            this.$element.find('.button').off('click').click(function(){
                self.pos_widget.screen_selector.close_popup();
                self.pos.proxy.help_canceled();
            });
        },
    });

    module.ReceiptPopupWidget = module.PopUpWidget.extend({
        template:'ReceiptPopupWidget',
        show: function(){
            this._super();
            var self = this;
            this.$element.find('.receipt').off('click').click(function(){
                console.log('receipt!');     //TODO
                self.pos_widget.screen_selector.set_current_screen('scan');
            });
            this.$element.find('.invoice').off('click').click(function(){
                console.log('invoice!');     //TODO
                self.pos_widget.screen_selector.set_current_screen('scan');
            });
        },
    });

    module.ErrorPopupWidget = module.PopUpWidget.extend({
        template:'ErrorPopupWidget',
        show: function(){
            var self = this;
            this._super();
            this.pos.proxy.help_needed();
            this.pos.proxy.scan_item_error_unrecognized();

            this.pos.barcode_reader.save_callbacks();
            this.pos.barcode_reader.reset_action_callbacks();
            this.pos.barcode_reader.set_action_callbacks({
                'cashier': function(ean){
                    clearInterval(this.intervalID);
                    self.pos.proxy.cashier_mode_activated();
                    self.pos_widget.screen_selector.set_user_mode('cashier');
                },
            });
        },
        hide:function(){
            this._super();
            this.pos.proxy.help_canceled();
            this.pos.barcode_reader.restore_callbacks();
        },
    });

    module.ErrorProductNotRecognizedPopupWidget = module.ErrorPopupWidget.extend({
        template:'ErrorProductNotRecognizedPopupWidget',
    });

    module.ErrorNoSessionPopupWidget = module.ErrorPopupWidget.extend({
        template:'ErrorNoSessionPopupWidget',
    });

    module.ScaleInviteScreenWidget = module.ScreenWidget.extend({
        template:'ScaleInviteScreenWidget',
        show: function(){
            this._super();
            var self = this;

            this.pos_widget.set_numpad_visible(false);
            this.pos_widget.set_leftpane_visible(true);
            this.pos_widget.set_cashier_controls_visible(false);
            this.pos_widget.action_bar.set_total_visible(true);
            this.pos_widget.action_bar.set_help_visible(true,function(){self.pos_widget.screen_selector.show_popup('help');});
            this.pos_widget.action_bar.set_logout_visible(false);

            self.pos.proxy.weighting_start();

            this.intervalID = setInterval(function(){
                var weight = self.pos.proxy.weighting_read_kg();
                if(weight > 0.001){
                    clearInterval(this.intervalID);
                    self.pos_widget.screen_selector.set_current_screen('scale_product');
                }
            },500);

            this.pos_widget.action_bar.add_new_button(
                {
                    label: 'back',
                    icon: '/point_of_sale/static/src/img/icons/png48/go-previous.png',
                    click: function(){  
                        clearInterval(this.intervalID);
                        self.pos.proxy.weighting_end();
                        self.pos_widget.screen_selector.set_current_screen('scan');
                    }
                }
            );

            this.pos.barcode_reader.set_action_callbacks({
                'cashier': function(ean){
                    self.pos.proxy.cashier_mode_activated();
                    self.pos_widget.screen_selector.set_user_mode('cashier');
                },
                'product': function(ean){
                    if(self.pos_widget.scan_product(ean)){
                        self.pos.proxy.scan_item_success();
                        self.pos_widget.screen_selector.set_current_screen('scan');
                    }else{
                        self.pos_widget.screen_selector.show_popup('error');
                    }
                },
            });
        },
        hide: function(){
            this._super();
            clearInterval(this.intervalID);
        },
    });

    module.ScaleProductScreenWidget = module.ScreenWidget.extend({
        template:'ScaleProductSelectionScreenWidget',
        start: function(){
            this.product_categories_widget = new module.ProductCategoriesWidget(null,{
                pos:this.pos,
            });
            this.product_categories_widget.replace($('.placeholder-ProductCategoriesWidget'));

            this.product_list_widget = new module.ProductListWidget(null,{
                pos:this.pos,
                pos_widget:this.pos_widget,
                weight: this.pos.proxy.weighting_read_kg(),
            });
            this.product_list_widget.replace($('.placeholder-ProductListWidget'));
        },
        show: function(){
            this._super();
            var self = this;
            if(this.pos_widget.screen_selector.get_user_mode() === 'client'){
                this.pos_widget.set_numpad_visible(false);
                this.pos_widget.set_leftpane_visible(true);
                this.pos_widget.set_cashier_controls_visible(false);
                this.pos_widget.action_bar.set_total_visible(true);
                this.pos_widget.action_bar.set_help_visible(true,function(){self.pos_widget.screen_selector.show_popup('help');});
                this.pos_widget.action_bar.set_logout_visible(false);
                this.pos_widget.onscreen_keyboard.connect();

                this.product_categories_widget.reset_category();

                this.pos_widget.order_widget.set_numpad_state(this.pos_widget.numpad.state);
                this.pos_widget.action_bar.add_new_button(
                    {
                        label: 'back',
                        icon: '/point_of_sale/static/src/img/icons/png48/go-previous.png',
                        click: function(){
                            self.pos_widget.screen_selector.set_current_screen('scan');
                        }
                    }
                );
                this.pos.barcode_reader.set_action_callbacks({
                    'cashier': function(ean){
                        self.pos.proxy.cashier_mode_activated();
                        self.pos_widget.screen_selector.set_user_mode('cashier');
                    },
                    'product': function(ean){
                        if(self.pos_widget.scan_product(ean)){
                            self.pos.proxy.scan_item_success();
                            self.pos_widget.screen_selector.set_current_screen('scan');
                        }else{
                            self.pos_widget.screen_selector.show_popup('error');
                    }
                },
                });
                this.product_list_widget.set_next_screen('scan');
            }else{  // user_mode === 'cashier'
                this.pos_widget.set_numpad_visible(true);
                this.pos_widget.set_leftpane_visible(true);
                this.pos_widget.set_cashier_controls_visible(true);
                this.pos_widget.action_bar.set_total_visible(true);
                this.pos_widget.action_bar.set_help_visible(false);
                this.pos_widget.onscreen_keyboard.connect();
                
                this.pos_widget.order_widget.set_numpad_state(this.pos_widget.numpad.state);
                this.pos_widget.action_bar.add_new_button(
                    {
                        label: 'back',
                        icon: '/point_of_sale/static/src/img/icons/png48/go-previous.png',
                        click: function(){
                            self.pos_widget.screen_selector.set_current_screen('products');
                        }
                    }
                );
                this.product_list_widget.set_next_screen('undefined');
            }

            this.pos.proxy.weighting_start();
            this.last_weight = this.product_list_widget.weight;
            this.intervalID = setInterval(function(){
                var weight = self.pos.proxy.weighting_read_kg();
                if(weight != self.last_weight){
                    self.product_list_widget.set_weight(weight);
                    self.last_weight = weight;
                }
            },500);
        },
        hide: function(){
            this._super();
            this.pos_widget.order_widget.set_numpad_state(null);
            this.pos_widget.payment_screen.set_numpad_state(null);
            clearInterval(this.intervalID);
            this.pos.proxy.weighting_end();
        },
    });

    module.ClientPaymentScreenWidget =  module.ScreenWidget.extend({
        template:'ClientPaymentScreenWidget',
        show: function(){
            this._super();
            var self = this;

            this.pos_widget.set_numpad_visible(false);
            this.pos_widget.set_leftpane_visible(true);
            this.pos_widget.set_cashier_controls_visible(false);
            this.pos_widget.action_bar.set_total_visible(true);
            this.pos_widget.action_bar.set_help_visible(true,function(){self.pos_widget.screen_selector.show_popup('help');});
            this.pos_widget.action_bar.set_logout_visible(false);

            this.pos.proxy.payment_request(this.pos.get('selectedOrder').getTotal(),'card','info');    //TODO TOTAL

            this.intervalID = setInterval(function(){
                var payment = self.pos.proxy.is_payment_accepted();
                if(payment === 'payment_accepted'){
                    clearInterval(this.intervalID);
                    var currentOrder = self.pos.get('selectedOrder');
                    self.pos.push_order(currentOrder.exportAsJSON()).then(function() {
                        currentOrder.destroy();
                        self.pos.proxy.transaction_end();
                        self.pos_widget.screen_selector.set_current_screen('welcome');
                    });
                }else if(payment === 'payment_rejected'){
                    clearInterval(this.intervalID);
                    //TODO show a tryagain thingie ? 
                }
            },500);

            this.pos_widget.action_bar.add_new_button(
                {
                    label: 'back',
                    icon: '/point_of_sale/static/src/img/icons/png48/go-previous.png',
                    click: function(){  //TODO Go to ask for weighting screen
                        clearInterval(this.intervalID);
                        self.pos.proxy.payment_canceled();
                        self.pos_widget.screen_selector.set_current_screen('scan');
                    }
                }
            );

            this.pos.barcode_reader.set_action_callbacks({
                'cashier': function(ean){
                    clearInterval(this.intervalID);
                    self.pos.proxy.cashier_mode_activated();
                    self.pos_widget.screen_selector.set_user_mode('cashier');
                },
            });
        },
        hide: function(){
            this._super();
            clearInterval(this.intervalID);
        },
    });

    module.WelcomeScreenWidget = module.ScreenWidget.extend({
        template:'WelcomeScreenWidget',
        show: function(){
            this._super();
            var self = this;

            this.pos_widget.set_numpad_visible(false);
            this.pos_widget.set_leftpane_visible(false);
            this.pos_widget.set_cashier_controls_visible(false);
            this.pos_widget.action_bar.set_total_visible(false);
            this.pos_widget.action_bar.set_help_visible(true,function(){self.pos_widget.screen_selector.show_popup('help');});
            this.pos_widget.action_bar.set_logout_visible(false);

            this.pos_widget.action_bar.add_new_button(
                {
                    label:'scan',
                    click: function(){
                        self.pos_widget.screen_selector.set_current_screen('scan');
                    }
                },{
                    label: 'weight',
                    icon: '/point_of_sale/static/src/img/icons/png48/scale.png',
                    click: function(){  
                        self.pos_widget.screen_selector.set_current_screen('scale_invite');
                    }
                }
            );
            this.pos.barcode_reader.set_action_callbacks({
                'product': function(ean){
                    self.pos.proxy.transaction_start(); 
                    if(self.pos_widget.scan_product(ean)){
                        self.pos.proxy.scan_item_success();
                        self.pos_widget.screen_selector.set_current_screen('scan');
                    }else{
                        self.pos_widget.screen_selector.show_popup('error');
                    }
                },
                'cashier': function(ean){
                    self.pos.proxy.cashier_mode_activated();
                    self.pos_widget.screen_selector.set_user_mode('cashier');
                },
                'client': function(ean){
                    self.pos.proxy.transaction_start(); 
                    //TODO 'log the client'
                    self.pos_widget.screen_selector.show_popup('receipt');
                },
                'discount': function(ean){
                    var currentOrder = self.pos.get('selectedOrder');
                    var last_orderline = currentOrder.last_orderline;
                    if(last_orderline){
                        last_orderline.set_discount(ean.value)
                    }
                },
            });
        },
        hide: function(){
            this._super();
            this.pos.barcode_reader.reset_action_callbacks();
            this.pos_widget.action_bar.destroy_buttons();
        },
    });

    module.ScanProductScreenWidget = module.ScreenWidget.extend({
        template:'ScanProductScreenWidget',
        show: function(){
            this._super();
            var self = this;

            this.pos_widget.set_numpad_visible(false);
            this.pos_widget.set_leftpane_visible(true);
            this.pos_widget.set_cashier_controls_visible(false);
            this.pos_widget.action_bar.set_total_visible(true);
            this.pos_widget.action_bar.set_help_visible(true,function(){self.pos_widget.screen_selector.show_popup('help');});
            this.pos_widget.action_bar.set_logout_visible(false);

            this.pos_widget.action_bar.add_new_button(
                {
                    label: 'weight',
                    icon: '/point_of_sale/static/src/img/icons/png48/scale.png',
                    click: function(){  //TODO Go to ask for weighting screen
                        self.pos_widget.screen_selector.set_current_screen('scale_invite');
                    }
                },{
                    label: 'pay',
                    icon: '/point_of_sale/static/src/img/icons/png48/go-next.png',
                    click: function(){
                        self.pos_widget.screen_selector.set_current_screen('client_payment'); //TODO what stuff ?
                    }
                }
            );
            this.pos.barcode_reader.set_action_callbacks({
                'product': function(ean){
                    if(self.pos_widget.scan_product(ean)){
                        self.pos.proxy.scan_item_success();
                    }else{
                        self.pos_widget.screen_selector.show_popup('error');
                    }
                },
                'cashier': function(ean){
                    self.pos.proxy.cashier_mode_activated();
                    self.pos_widget.screen_selector.set_user_mode('cashier');
                },
                'discount': function(ean){
                    var currentOrder = self.pos.get('selectedOrder');
                    var last_orderline = currentOrder.last_orderline;
                    if(last_orderline){
                        last_orderline.set_discount(ean.value)
                    }
                },
            });
        },
    });
    
    module.SearchProductScreenWidget = module.ScreenWidget.extend({
        template:'SearchProductScreenWidget',
        start: function(){
            this.product_categories_widget = new module.ProductCategoriesWidget(null,{
                pos:this.pos,
            });
            this.product_categories_widget.replace($('.placeholder-ProductCategoriesWidget'));

            this.product_list_widget = new module.ProductListWidget(null,{
                pos:this.pos,
                pos_widget:this.pos_widget,
            });
            this.product_list_widget.replace($('.placeholder-ProductListWidget'));
        },
        show: function(){
            this._super();
            var self = this;

            this.pos_widget.set_numpad_visible(true);
            this.pos_widget.set_leftpane_visible(true);
            this.pos_widget.set_cashier_controls_visible(true);
            this.pos_widget.action_bar.set_total_visible(true);
            this.pos_widget.action_bar.set_help_visible(false);
            this.pos_widget.action_bar.set_logout_visible(true, function(){ 
                self.pos_widget.screen_selector.set_user_mode('client');
            });
            this.product_categories_widget.reset_category();
            this.pos_widget.onscreen_keyboard.connect();

            this.pos_widget.order_widget.set_numpad_state(this.pos_widget.numpad.state);
            this.pos_widget.action_bar.add_new_button(
                {
                    label: 'weight',
                    icon: '/point_of_sale/static/src/img/icons/png48/scale.png',
                    click: function(){  
                        self.pos_widget.screen_selector.set_current_screen('scale_product');
                    }
                }
            );
            this.pos.barcode_reader.set_action_callbacks({
                'product': function(ean){
                    if(self.pos_widget.scan_product(ean)){
                        self.pos.proxy.scan_item_success();
                    }else{
                        self.pos_widget.screen_selector.show_popup('error');
                    }
                },
                'cashier': function(ean){
                    self.pos.proxy.cashier_mode_activated();
                    self.pos_widget.screen_selector.set_user_mode('cashier');
                },
                'discount': function(ean){
                    var currentOrder = self.pos.get('selectedOrder');
                    var last_orderline = currentOrder.last_orderline;
                    if(last_orderline){
                        last_orderline.set_discount(ean.value)
                    }
                },
            });
        },
        hide: function(){
            this._super();
            this.pos_widget.order_widget.set_numpad_state(null);
            this.pos_widget.payment_screen.set_numpad_state(null);
        },

    });

    module.ReceiptScreenWidget = module.ScreenWidget.extend({
        template: 'ReceiptScreenWidget',
        init: function(parent, options) {
            this._super(parent,options);
            this.model = options.model;
            this.user = this.pos.get('user');
            this.company = this.pos.get('company');
            this.shop_obj = this.pos.get('shop');
        },
        start: function() {
            this.pos.bind('change:selectedOrder', this.change_selected_order, this);
            this.change_selected_order();
            $('button#pos-finish-order', this.$element).click(_.bind(this.finishOrder, this));
            $('button#print-the-ticket', this.$element).click(_.bind(this.print, this));
        },
        show: function(){
            this._super();
            var self = this;

            this.pos_widget.set_numpad_visible(true);
            this.pos_widget.set_leftpane_visible(true);
            this.pos_widget.set_cashier_controls_visible(true);
            this.pos_widget.action_bar.set_total_visible(true);
            this.pos_widget.action_bar.set_help_visible(false);
            this.pos_widget.action_bar.set_logout_visible(true, function(){ 
                self.pos_widget.screen_selector.set_user_mode('client');
            });
        },
        print: function() {
            window.print();
        },
        finishOrder: function() {
            this.pos.get('selectedOrder').destroy();
        },
        change_selected_order: function() {
            if (this.currentOrderLines)
                this.currentOrderLines.unbind();
            this.currentOrderLines = (this.pos.get('selectedOrder')).get('orderLines');
            this.currentOrderLines.bind('add', this.refresh, this);
            this.currentOrderLines.bind('change', this.refresh, this);
            this.currentOrderLines.bind('remove', this.refresh, this);
            if (this.currentPaymentLines)
                this.currentPaymentLines.unbind();
            this.currentPaymentLines = (this.pos.get('selectedOrder')).get('paymentLines');
            this.currentPaymentLines.bind('all', this.refresh, this);
            this.refresh();
        },
        refresh: function() {
            this.currentOrder = this.pos.get('selectedOrder');
            $('.pos-receipt-container', this.$element).html(QWeb.render('PosTicket',{widget:this}));
        },
    });

    module.PaymentScreenWidget = module.ScreenWidget.extend({
        template: 'PaymentScreenWidget',
        init: function(parent, options) {
            this._super(parent,options);
            this.model = options.model;
            this.pos.bind('change:selectedOrder', this.change_selected_order, this);
            this.bindPaymentLineEvents();
            this.bind_orderline_events();
        },
        show: function(){
            this._super();
            var self = this;
            console.log('Payment Screen!');

            this.pos_widget.set_numpad_visible(true);
            this.pos_widget.set_leftpane_visible(true);
            this.pos_widget.set_cashier_controls_visible(true);
            this.pos_widget.action_bar.set_total_visible(true);
            this.pos_widget.action_bar.set_help_visible(false);
            this.pos_widget.action_bar.set_logout_visible(true, function(){ 
                self.pos_widget.screen_selector.set_user_mode('client');
            });

            this.set_numpad_state(this.pos_widget.numpad.state);
        },
        hide: function(){
            this._super();
            this.pos_widget.order_widget.set_numpad_state(null);
            this.pos_widget.payment_screen.set_numpad_state(null);
        },
        back: function() {
            this.pos_widget.screen_selector.set_current_screen('products');
        },
        validateCurrentOrder: function() {
            var self = this;
            var currentOrder = this.pos.get('selectedOrder');

            $('button#validate-order', this.$element).attr('disabled', 'disabled');

            this.pos.push_order(currentOrder.exportAsJSON()).then(function() {
                $('button#validate-order', self.$element).removeAttr('disabled');
                self.pos_widget.screen_selector.set_current_screen('receipt');
            });
        },
        bindPaymentLineEvents: function() {
            this.currentPaymentLines = (this.pos.get('selectedOrder')).get('paymentLines');
            this.currentPaymentLines.bind('add', this.addPaymentLine, this);
            this.currentPaymentLines.bind('remove', this.renderElement, this);
            this.currentPaymentLines.bind('all', this.updatePaymentSummary, this);
        },
        bind_orderline_events: function() {
            this.currentOrderLines = (this.pos.get('selectedOrder')).get('orderLines');
            this.currentOrderLines.bind('all', this.updatePaymentSummary, this);
        },
        change_selected_order: function() {
            console.log('change_selected_order');
            this.currentPaymentLines.unbind();
            this.bindPaymentLineEvents();
            this.currentOrderLines.unbind();
            this.bind_orderline_events();
            this.renderElement();
        },
        addPaymentLine: function(newPaymentLine) {
            console.log('addPaymentLine:',newPaymentLine);
            var x = new module.PaymentlineWidget(null, {
                    payment_line: newPaymentLine
                });
            x.on_delete.add(_.bind(this.deleteLine, this, x));
            x.appendTo(this.$('#paymentlines'));
        },
        renderElement: function() {
            this._super();
            this.$('#paymentlines').empty();
            this.currentPaymentLines.each(_.bind( function(paymentLine) {
                this.addPaymentLine(paymentLine);
            }, this));
            this.updatePaymentSummary();
            $('button#validate-order', this.$element).click(_.bind(this.validateCurrentOrder, this));
            $('.oe-back-to-products', this.$element).click(_.bind(this.back, this));
        },
        deleteLine: function(lineWidget) {
        	this.currentPaymentLines.remove([lineWidget.model]);
        },
        updatePaymentSummary: function() {
            var currentOrder, dueTotal, paidTotal, remaining, remainingAmount;
            currentOrder = this.pos.get('selectedOrder');
            paidTotal = currentOrder.getPaidTotal();
            dueTotal = currentOrder.getTotal();
            this.$element.find('#payment-due-total').html(dueTotal.toFixed(2));
            this.$element.find('#payment-paid-total').html(paidTotal.toFixed(2));
            remainingAmount = dueTotal - paidTotal;
            remaining = remainingAmount > 0 ? 0 : (-remainingAmount).toFixed(2);
            $('#payment-remaining').html(remaining);
        },
        set_numpad_state: function(numpadState) {
        	if (this.numpadState) {
        		this.numpadState.unbind('set_value', this.set_value);
        		this.numpadState.unbind('change:mode', this.setNumpadMode);
        	}
        	this.numpadState = numpadState;
        	if (this.numpadState) {
        		this.numpadState.bind('set_value', this.set_value, this);
        		this.numpadState.bind('change:mode', this.setNumpadMode, this);
        		this.numpadState.reset();
        		this.setNumpadMode();
        	}
        },
    	setNumpadMode: function() {
    		this.numpadState.set({mode: 'payment'});
    	},
        set_value: function(val) {
        	this.currentPaymentLines.last().set({amount: val});
        },
    });

}
