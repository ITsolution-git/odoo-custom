function openerp_pos_widgets(instance, module){ //module is instance.point_of_sale
    var QWeb = instance.web.qweb;

    module.NumpadWidget = instance.web.Widget.extend({
        template:'NumpadWidget',
        init: function(parent, options) {
            this._super(parent);
            this.state = new module.NumpadState();
        },
        start: function() {
            this.state.bind('change:mode', this.changedMode, this);
            this.changedMode();
            this.$element.find('button#numpad-backspace').click(_.bind(this.clickDeleteLastChar, this));
            this.$element.find('button#numpad-minus').click(_.bind(this.clickSwitchSign, this));
            this.$element.find('button.number-char').click(_.bind(this.clickAppendNewChar, this));
            this.$element.find('button.mode-button').click(_.bind(this.clickChangeMode, this));
        },
        clickDeleteLastChar: function() {
            return this.state.deleteLastChar();
        },
        clickSwitchSign: function() {
            return this.state.switchSign();
        },
        clickAppendNewChar: function(event) {
            var newChar;
            newChar = event.currentTarget.innerText || event.currentTarget.textContent;
            return this.state.appendNewChar(newChar);
        },
        clickChangeMode: function(event) {
            var newMode = event.currentTarget.attributes['data-mode'].nodeValue;
            return this.state.changeMode(newMode);
        },
        changedMode: function() {
            var mode = this.state.get('mode');
            $('.selected-mode').removeClass('selected-mode');
            $(_.str.sprintf('.mode-button[data-mode="%s"]', mode), this.$element).addClass('selected-mode');
        },
    });

    // The paypad allows to select the payment method (cashRegisters) 
    // used to pay the order.
    module.PaypadWidget = module.PosBaseWidget.extend({
        template: 'PaypadWidget',
        renderElement: function() {
            var self = this;
            this._super();
            console.log('PaypadWidget:',this);

            this.pos.get('cashRegisters').each(function(cashRegister) {
                var button = new module.PaypadButtonWidget(self,{
                    pos: self.pos,
                    pos_widget : self.pos_widget,
                    cashRegister: cashRegister,
                });
                button.appendTo(self.$element);
            });
        }
    });

    module.PaypadButtonWidget = module.PosBaseWidget.extend({
        template: 'PaypadButtonWidget',
        init: function(parent, options){
            this._super(parent, options);
            this.cashRegister = options.cashRegister;
        },
        renderElement: function() {
            var self = this;
            this._super();

            this.$element.click(function(){
                if (self.pos.get('selectedOrder').get('screen') === 'receipt'){  //TODO Why ?
                    console.log('TODO should not get there...?');
                    return;
                }
                self.pos.get('selectedOrder').addPaymentLine(self.cashRegister);
                self.pos_widget.screen_selector.set_current_screen('payment');
            });
        },
    });

// ---------- "Shopping Carts" ----------

    module.OrderlineWidget = module.PosBaseWidget.extend({
        template: 'OrderlineWidget',
        init: function(parent, options) {
            this._super(parent,options);
            this.model = options.model;
            this.model.bind('change', _.bind( function() {
                this.refresh();
            }, this));
            this.model.bind('remove', _.bind( function() {
                this.$element.remove();
            }, this));
            this.order = options.order;

            if(options.selected){
                this.select();
            }else{
                this.selected = false;
            }
        },
        clickHandler: function() {
            this.select();
        },
        renderElement: function() {
            this._super();
            this.$element.click(_.bind(this.clickHandler, this));
            if(this.selected){
                this.$element.addClass('selected');
            }
        },
        refresh: function(){
            this.renderElement();
        },
        select: function() {
            console.log('SELECT:',this);
            if(this.order.selected_widget){
                this.order.selected_widget.deselect();
            }
            this.selected = true;
            this.order.selected_widget = this;
            this.order.selected = this.model;
            this.on_selected();
            this.$element.addClass('selected');
        },
        deselect: function(){
            this.selected = false;
            this.order.selected_widget = null;
            this.order.selected = null;
            this.$element.removeClass('selected');
        },
        on_selected: function() {},
    });

    module.OrderWidget = module.PosBaseWidget.extend({
        template:'OrderWidget',
        init: function(parent, options) {
            this._super(parent,options);
            console.log('OrderWidget init:',options)
            this.set_numpad_state(options.numpadState);
            this.pos.bind('change:selectedOrder', this.change_selected_order, this);
            this.bind_orderline_events();
        },
        set_numpad_state: function(numpadState) {
        	if (this.numpadState) {
        		this.numpadState.unbind('set_value', this.set_value);
        	}
        	this.numpadState = numpadState;
        	if (this.numpadState) {
        		this.numpadState.bind('set_value', this.set_value, this);
        		this.numpadState.reset();
        	}
        },
        set_value: function(val) {
        	var param = {};
        	param[this.numpadState.get('mode')] = val;
        	var order = this.pos.get('selectedOrder');
        	if (order.get('orderLines').length !== 0) {
        	   order.selected.set(param);
        	} else {
        	    this.pos.get('selectedOrder').destroy();
        	}
        },
        change_selected_order: function() {
            this.currentOrderLines.unbind();
            this.bind_orderline_events();
            this.renderElement();
        },
        bind_orderline_events: function() {
            this.currentOrderLines = (this.pos.get('selectedOrder')).get('orderLines');
            this.currentOrderLines.bind('add', this.add_line, this);
            this.currentOrderLines.bind('remove', this.renderElement, this);
        },
        add_line: function(newLine) {
            var line = new module.OrderlineWidget(null, {
                    model: newLine,
                    pos: this.pos,
                    order: this.pos.get('selectedOrder'),
                    selected:true,
            });
            line.on_selected.add(_.bind(this.selected_line, this));
            this.selected_line();
            line.appendTo(this.$('.order'));
        },
        selected_line: function() {
        	var reset = false;
        	if (this.currentSelected !== this.pos.get('selectedOrder').selected) {
        		reset = true;
        	}
        	this.currentSelected = this.pos.get('selectedOrder').selected;
        	if (reset && this.numpadState)
        		this.numpadState.reset();
        },
        renderElement: function() {
            this._super();
            var $content = this.$('.order');
            $content.empty();
            this.currentOrderLines.each(_.bind( function(orderLine) {
                var line = new module.OrderlineWidget(null, {
                        model: orderLine,
                        order: this.pos.get('selectedOrder'),
                        selected:true,
                });
            	line.on_selected.add(_.bind(this.selected_line, this));
                line.appendTo($content);
            }, this));
        },
    });

// ---------- Product Screen ----------


    module.ProductWidget = module.PosBaseWidget.extend({
        template: 'ProductWidget',
        init: function(parent, options) {
            this._super(parent,options);
            this.model = options.model;
            this.model.attributes.weight = options.weight || undefined;
            this.next_screen = options.next_screen || undefined;
        },
        addToOrder: function(event) {
            /* Preserve the category URL */
            event.preventDefault();
            return (this.pos.get('selectedOrder')).addProduct(this.model);
        },
        set_weight: function(weight){
            this.model.attributes.weight = weight;
            this.renderElement();
        },
        set_next_screen: function(screen){
            this.next_screen = screen;
        },
        renderElement: function() {
            this._super();
            var self = this;
            $("a", this.$element).click(function(e){
                self.addToOrder(e);
                if(self.next_screen){
                    self.pos_widget.screen_selector.set_current_screen(self.next_screen);    //FIXME There ought to be a better way to do this ...
                }
            });
        },
    });

    module.PaymentlineWidget = module.PosBaseWidget.extend({
        template: 'PaymentlineWidget',
        init: function(parent, options) {
            this._super(parent,options);
            this.payment_line = options.payment_line;
            this.payment_line.bind('change', this.changedAmount, this);
        },
        on_delete: function() {},
        changeAmount: function(event) {
            var newAmount;
            newAmount = event.currentTarget.value;
            if (newAmount && !isNaN(newAmount)) {
            	this.amount = parseFloat(newAmount);
                this.payment_line.set({
                    amount: this.amount,
                });
            }
        },
        changedAmount: function() {
        	if (this.amount !== this.payment_line.get('amount'))
        		this.renderElement();
        },
        renderElement: function() {
            this.name =   this.payment_line.get('journal_id')[1];
            this._super();
            $('input', this.$element).keyup(_.bind(this.changeAmount, this));
            $('.delete-payment-line', this.$element).click(this.on_delete);
        },
    });

    module.OrderButtonWidget = module.PosBaseWidget.extend({
        template:'OrderButtonWidget',
        init: function(parent, options) {
            this._super(parent,options);
            this.order = options.order;
            this.order.bind('destroy', _.bind( function() {
                this.destroy();
            }, this));
            this.pos.bind('change:selectedOrder', _.bind( function(pos) {
                var selectedOrder;
                selectedOrder = pos.get('selectedOrder');
                if (this.order === selectedOrder) {
                    this.setButtonSelected();
                }
            }, this));
        },
        renderElement:function(){
            this._super();
            this.$('button.select-order').click(_.bind(this.selectOrder, this));
            this.$('button.close-order').click(_.bind(this.closeOrder, this));
        },
        selectOrder: function(event) {
            this.pos.set({
                selectedOrder: this.order
            });
        },
        setButtonSelected: function() {
            $('.selected-order').removeClass('selected-order');
            this.$element.addClass('selected-order');
        },
        closeOrder: function(event) {
            this.order.destroy();
        },
    });

    module.ActionButtonWidget = instance.web.Widget.extend({
        template:'ActionButtonWidget',
        init: function(parent, options){
            this._super(parent, options);
            this.label = options.label || 'button';
            this.rightalign = options.rightalign || false;
            this.click_action = options.click;
            if(options.icon){
                this.icon = options.icon;
                this.template = 'ActionButtonWidgetWithIcon';
            }
        },
        renderElement: function(){
            this._super();
            if(this.click_action){
                this.$element.click(_.bind(this.click_action, this));
            }
        },
    });

    module.ActionBarWidget = instance.web.Widget.extend({
        template:'ActionBarWidget',
        init: function(parent, options){
            this._super(parent,options);
            this.button_list = [];
            this.fake_buttons  = {};
            this.visibility = {};
            this.total_visibility = true;
            this.help_visibility  = true;
            this.logout_visibility  = true;
            this.close_visibility  = true;
        },
        set_element_visible: function(element, visible, action){
            if(visible != this.visibility[element]){
                this.visibility[element] = visible;
                if(visible){
                    this.$('.'+element).show();
                }else{
                    this.$('.'+element).hide();
                }
            }
            if(visible && action){
                this.$('.'+element).off('click').click(action);
            }
        },
        set_total_value: function(value){
            this.$('.value').html(value);
        },
        destroy_buttons:function(){
            for(var i = 0; i < this.button_list.length; i++){
                this.button_list[i].destroy();
            }
            this.button_list = [];
            return this;
        },
        add_new_button: function(button_options){
            if(arguments.length == 1){
                var button = new module.ActionButtonWidget(this,button_options);
                this.button_list.push(button);
                button.appendTo($('.pos-actionbar-button-list'));
                return button;
            }else{
                for(var i = 0; i < arguments.length; i++){
                    this.add_new_button(arguments[i]);
                }
            }
            return undefined;
        },
    });

    module.ProductCategoriesWidget = module.PosBaseWidget.extend({
        template: 'ProductCategoriesWidget',
        init: function(parent, options){
            var self = this;
            this._super(parent,options);
            this.product_type = options.product_type || 'all';  // 'all' | 'weightable'
            this.onlyWeightable = options.onlyWeightable || false;
            this.category = this.pos.root_category;
            this.breadcrumb = [];
            this.subcategories = [];
            this.set_category();
        },

        // changes the category. if undefined, sets to root category
        set_category : function(category){
            if(!category){
                this.category = this.pos.root_category;
            }else{
                this.category = category;
            }
            this.breadcrumb = [];
            for(var i = 1; i < this.category.ancestors.length; i++){
                this.breadcrumb.push(this.category.ancestors[i]);
            }
            if(this.category !== this.pos.root_category){
                this.breadcrumb.push(this.category);
            }
            if(this.product_type === 'weightable'){
                this.subcategories = [];
                for(var i = 0; i < this.category.childrens.length; i++){
                    if(this.category.childrens[i].weightable_product_list.length > 0){
                        this.subcategories.push( this.category.childrens[i]);
                    }
                }
            }else{
                this.subcategories = this.category.childrens || [];
            }
        },

        renderElement: function(){
            var self = this;
            this._super();
            this.$element.find(".oe-pos-categories-list a").click(function(event){
                var id = $(event.target).data("category-id");
                var category = self.pos.categories_by_id[id];
                self.set_category(category);
                self.renderElement();
                self.search_and_categories(category);
            });
            this.search_and_categories();
        },
        
        set_product_type: function(type){       // 'all' | 'weightable'
            this.product_type = type;
            this.reset_category();
        },

        // resets the current category to the root category
        reset_category: function(){
            this.set_category();
            this.renderElement();
            this.search_and_categories();
        },

        // filters the products, and sets up the search callbacks
        search_and_categories: function(category){
            var self = this;
            
            var all_products = this.pos.get('product_list');
            var all_packages = this.pos.get('product.packaging');

            // find all products belonging to the current category
            var products = [];
            if(this.product_type === 'weightable'){
                products = all_products.filter( function(product){
                    return self.category.weightable_product_set[product.id];
                });
            }else{
                products = all_products.filter( function(product){
                    return self.category.product_set[product.id];
                });
            }

            // product lists watch for reset events on 'products' to re-render. 
            // FIXME that means all productlist widget re-render... even the hidden ones ! 
            this.pos.get('products').reset(products);
            
            // find all the products whose name match the query in the searchbox
            this.$('.searchbox input').keyup(function(){
                var results, search_str;
                search_str = $(this).val().toLowerCase();
                if(search_str){
                    results = products.filter( function(p){
                        return p.name.toLowerCase().indexOf(search_str) != -1 || 
                               (p.ean13 && p.ean13.indexOf(search_str) != -1);
                    });
                    self.$element.find('.search-clear').fadeIn();
                }else{
                    results = products;
                    self.$element.find('.search-clear').fadeOut();
                }
                self.pos.get('products').reset(results);
            });
            this.$('.searchbox input').click(function(){
            });

            //reset the search when clicking on reset
            this.$('.search-clear').click(function(){
                self.pos.get('products').reset(products);
                self.$('.searchbox input').val('').focus();
                self.$('.search-clear').fadeOut();
            });
        },
    });

    module.ProductListWidget = module.ScreenWidget.extend({
        template:'ProductListWidget',
        init: function(parent, options) {
            var self = this;
            this._super(parent,options);
            this.model = options.model;
            this.product_list = [];
            this.weight = options.weight || 0;
            this.show_scale = options.show_scale || false;
            this.next_screen = options.next_screen || false;

            this.pos.get('products').bind('reset', function(){
                self.renderElement();
            });
        },
        set_weight: function(weight){
            for(var i = 0; i < this.product_list.length; i++){
                this.product_list[i].set_weight(weight);
            }
        },
        set_next_screen: function(screen){
            for(var i = 0; i < this.product_list.length; i++){
                this.product_list[i].set_next_screen(screen);
            }
        },
        renderElement: function() {
            var self = this;
            this._super();
            this.product_list = []; 
            this.pos.get('products')
                .chain()
                .map(function(product) {
                    var product = new module.ProductWidget(self, {
                            model: product,
                            weight: self.weight,
                    })
                    self.product_list.push(product);
                    return product;
                })
                .invoke('appendTo', this.$('.product-list'));

            this.scrollbar = new module.ScrollbarWidget(this,{
                target_widget:   this,
                target_selector: '.product-list',
            });

            this.scrollbar.replace(this.$('.placeholder-ScrollbarWidget'));

        },
    });

// ---------- Main Point of Sale Widget ----------

    // this is used to notify the user that data is being synchronized on the network
    module.SynchNotificationWidget = instance.web.Widget.extend({
        template: "SynchNotificationWidget",
        init: function(parent) {
            this._super(parent);
            this.nbr_pending = 0;
        },
        renderElement: function() {
            this._super();
            $('.oe_pos_synch-notification-button', this.$element).click(this.on_synch);
        },
        on_change_nbr_pending: function(nbr_pending) {
            this.nbr_pending = nbr_pending;
            this.renderElement();
        },
        on_synch: function() {}
    });

    // The PosWidget is the main widget that contains all other widgets in the PointOfSale.
    // It is mainly composed of :
    // - a header, containing the list of orders
    // - a leftpane, containing the list of bought products (orderlines) 
    // - a rightpane, containing the screens (see pos_screens.js)
    // - an actionbar on the bottom, containing various action buttons
    // - popups
    // - an onscreen keyboard
    // a screen_selector which controls the switching between screens and the showing/closing of popups

    module.PosWidget = module.PosBaseWidget.extend({
        template: 'PosWidget',
        init: function() { 
            console.log('PosArguments:',arguments);
            this._super(arguments[0],{});
            
            this.pos = new module.PosModel(this.session);
            window.pos = this.pos;
            window.pos_widget = this;
            this.pos_widget = this; //So that pos_widget's childs have pos_widget set automatically

            this.numpad_visible = true;
            this.leftpane_visible = true;
            this.leftpane_width   = '440px';
            this.cashier_controls_visible = true;
        },
      
        start: function() {
            var self = this;
            return self.pos.ready.then(function() {
                self.build_currency_template();
                self.renderElement();
                self.synch_notification = new module.SynchNotificationWidget(this);
                self.synch_notification.replace($('.placeholder-SynchNotificationWidget', self.$element));
                self.synch_notification.on_synch.add(_.bind(self.pos.flush, self.pos));
                
                self.pos.bind('change:nbr_pending_operations', self.changed_pending_operations, self);
                self.changed_pending_operations();
                
                self.$element.find("#loggedas button").click(function() {
                    self.try_close();
                });
                
                self.$('button#neworder-button').click(_.bind(self.create_new_order, self));
                
                //when a new order is created, add an order button widget
                self.pos.get('orders').bind('add', function(new_order){
                    var new_order_button = new module.OrderButtonWidget(null, {
                        order: new_order,
                        pos: self.pos
                    });
                    new_order_button.appendTo($('#orders'));
                    new_order_button.selectOrder();
                }, self);

                self.pos.get('orders').add(new module.Order({ pos: self.pos }));

                self.build_widgets();

                instance.webclient.set_content_full_screen(true);

                if (!self.pos.get('pos_session')) {
                    self.screen_selector.show_popup('error',
                        'Sorry, we could not create a user session');
                //}else if (!self.pos.get('bank_statements') || self.pos.get('bank_statements').length === 0){
                //    self.screen_selector.show_popup('error',
                //        'Sorry, we could not find any accounting journals in the configuration');
                }else if(!self.pos.get('pos_config')){
                    self.screen_selector.show_popup('error',
                        'Sorry, we could not find any PoS Configuration for this session');
                }
            
                $('.loader').animate({opacity:0},3000,'swing',function(){$('.loader').hide();});
                $('.loader img').hide();

            },function(){   // error when loading models data from the backend
                $('.loader img').hide();
                return new instance.web.Model("ir.model.data").get_func("search_read")([['name', '=', 'action_pos_session_opening']], ['res_id'])
                    .pipe( _.bind(function(res){
                        return instance.connection.rpc('/web/action/load', {'action_id': res[0]['res_id']})
                            .pipe(_.bind(function(result){
                                var action = result.result;
                                this.do_action(action);
                            }, this));
                    }, self));
            });
        },

        build_widgets: function() {

            // --------  Screens ---------

            this.search_product_screen = new module.SearchProductScreenWidget(this,{});
            this.search_product_screen.appendTo($('#rightpane'));

            this.scan_product_screen = new module.ScanProductScreenWidget(this,{});
            this.scan_product_screen.appendTo($('#rightpane'));

            this.receipt_screen = new module.ReceiptScreenWidget(this, {});
            this.receipt_screen.appendTo($('#rightpane'));

            this.payment_screen = new module.PaymentScreenWidget(this, {});
            this.payment_screen.appendTo($('#rightpane'));

            this.welcome_screen = new module.WelcomeScreenWidget(this,{});
            this.welcome_screen.appendTo($('#rightpane'));

            this.client_payment_screen = new module.ClientPaymentScreenWidget(this, {});
            this.client_payment_screen.appendTo($('#rightpane'));

            this.scale_invite_screen = new module.ScaleInviteScreenWidget(this, {});
            this.scale_invite_screen.appendTo($('#rightpane'));

            this.scale_product_screen = new module.ScaleProductScreenWidget(this, {});
            this.scale_product_screen.appendTo($('#rightpane'));

            // --------  Popups ---------

            this.help_popup = new module.HelpPopupWidget(this, {});
            this.help_popup.appendTo($('.point-of-sale'));

            this.receipt_popup = new module.ReceiptPopupWidget(this, {});
            this.receipt_popup.appendTo($('.point-of-sale'));

            this.error_popup = new module.ErrorPopupWidget(this, {});
            this.error_popup.appendTo($('.point-of-sale'));

            this.error_product_popup = new module.ErrorProductNotRecognizedPopupWidget(this, {});
            this.error_product_popup.appendTo($('.point-of-sale'));

            this.error_session_popup = new module.ErrorNoSessionPopupWidget(this, {});
            this.error_session_popup.appendTo($('.point-of-sale'));

            // --------  Misc ---------

            this.action_bar = new module.ActionBarWidget(this);
            this.action_bar.appendTo($(".point-of-sale #content"));

            this.paypad = new module.PaypadWidget(this, {});
            this.paypad.replace($('#placeholder-PaypadWidget'));

            this.numpad = new module.NumpadWidget(this);
            this.numpad.replace($('#placeholder-NumpadWidget'));

            this.order_widget = new module.OrderWidget(this, {});
            this.order_widget.replace($('#placeholder-OrderWidget'));

            this.onscreen_keyboard = new module.OnscreenKeyboardWidget(this, {
                'keyboard_model': 'simple'
            });
            this.onscreen_keyboard.appendTo($(".point-of-sale #content")); 
            
            // --------  Screen Selector ---------

            this.screen_selector = new module.ScreenSelector({
                pos: this.pos,
                screen_set:{
                    'products': this.search_product_screen,
                    'scan': this.scan_product_screen,
                    'payment' : this.payment_screen,
                    'client_payment' : this.client_payment_screen,
                    'scale_invite' : this.scale_invite_screen,
                    'scale_product' : this.scale_product_screen,
                    'receipt' : this.receipt_screen,
                    'welcome' : this.welcome_screen,
                },
                popup_set:{
                    'help': this.help_popup,
                    'error': this.error_popup,
                    'error-product': this.error_product_popup,
                    'error-session': this.error_session_popup,
                    'receipt': this.receipt_popup,
                },
                default_client_screen: 'welcome',
                default_cashier_screen: 'products',
                default_mode: this.pos.use_selfcheckout ?  'client' : 'cashier',
            });
            this.screen_selector.set_default_screen();

            window.screen_selector = this.screen_selector; //DEBUG

            this.pos.barcode_reader.connect();
            
        },

        //FIXME this method is probably not at the right place ... 
        scan_product: function(parsed_ean){
            var selectedOrder = this.pos.get('selectedOrder');
            var scannedProductModel = this.get_product_by_ean(parsed_ean);
            if (!scannedProductModel){
                return false;
            } else {
                selectedOrder.addProduct(new module.Product(scannedProductModel));
                return true;
            }
        },

        // returns a product that has a packaging with an EAN matching to provided parsed ean . 
        // returns undefined if no such product is found.
        get_product_by_ean: function(parsed_ean) {
            var allProducts = this.pos.get('product_list');
            var allPackages = this.pos.get('product.packaging');
            var scannedProductModel = undefined;

            if (parsed_ean.type === 'price') {
                var itemCode = parsed_ean.id;
                console.log('price! id:',itemCode);
                var scannedPackaging = _.detect(allPackages, function(pack) { 
                    return pack.ean && pack.ean.substring(0,7) === itemCode;
                });
                if (scannedPackaging) {
                    console.log('found matching package, finding matching product...');
                    scannedProductModel = _.detect(allProducts, function(pc) { return pc.id === scannedPackaging.product_id[0];});
                }else{
                    console.log('matching package not found, finding matching product...');
                    scannedProductModel = _.detect(allProducts, function(pc) { return pc.ean13  && (pc.ean13.substring(0,7) === parsed_ean.id);});   
                }
                if(scannedProductModel){
                    scannedProductModel.list_price = parsed_ean.value;
                }
            } else if (parsed_ean.type === 'weight') {
                var weight = parsed_ean.value;
                var itemCode = parsed_ean.id;
                var scannedPackaging = _.detect(allPackages, function(pack) { 
                    return pack.ean  && pack.ean.substring(0,7) === itemCode;
                });
                if (scannedPackaging){
                    console.log('found matching package, finding matching product...');
                    scannedProductModel = _.detect(allProducts, function(pc) { return pc.id === scannedPackaging.product_id[0];});
                }else{
                    console.log('matching package not found, finding matching product...');
                    scannedProductModel = _.detect(allProducts, function(pc) { return pc.ean13  && (pc.ean13.substring(0,7) === parsed_ean.id);});   
                }
                if(scannedProductModel){
                    scannedProductModel.list_price *= weight;
                    scannedProductModel.name += ' - ' + weight + ' Kg.';
                }
            } else if(parsed_ean.type === 'unit'){
                scannedProductModel = _.detect(allProducts, function(pc) { return pc.ean13 === parsed_ean.ean;});   //TODO DOES NOT SCALE
            }
            return scannedProductModel;
        },
        // creates a new order, and add it to the list of orders.
        create_new_order: function() {
            var new_order;
            new_order = new module.Order({ pos: this.pos });
            this.pos.get('orders').add(new_order);
            this.pos.set({ selectedOrder: new_order });
        },
        changed_pending_operations: function () {
            var self = this;
            this.synch_notification.on_change_nbr_pending(self.pos.get('nbr_pending_operations').length);
        },
        // shows or hide the numpad and related controls like the paypad.
        set_numpad_visible: function(visible){
            if(visible != this.numpad_visible){
                this.numpad_visible = visible;
                if(visible){
                    $('#numpad').show();
                    $('#paypad').show();
                    $('#current-order').css({'bottom':'271px'});
                }else{
                    $('#numpad').hide();
                    $('#paypad').hide();
                    $('#current-order').css({'bottom':'0px'});
                }
            }
        },
        //shows or hide the leftpane (contains the list of orderlines, the numpad, the paypad, etc.)
        set_leftpane_visible: function(visible){
            if(visible != this.leftpane_visible){
                this.leftpane_visible = visible;
                if(visible){
                    $('#leftpane').show().animate({'width':this.leftpane_width},500,'swing');
                    $('#rightpane').animate({'left':this.leftpane_width},500,'swing');
                }else{
                    var leftpane = $('#leftpane');
                    $('#leftpane').animate({'width':'0px'},500,'swing', function(){ leftpane.hide(); });
                    $('#rightpane').animate({'left':'0px'},500,'swing');
                }
            }
        },
        //shows or hide the controls in the PosWidget that are specific to the cashier ( Orders, close button, etc. ) 
        set_cashier_controls_visible: function(visible){
            if(visible != this.cashier_controls_visible){
                this.cashier_controls_visible = visible;
                if(visible){
                    $('#loggedas').show();
                    $('#rightheader').show();
                }else{
                    $('#loggedas').hide();
                    $('#rightheader').hide();
                }
            }
        },
        try_close: function() {
            var self = this;
            self.pos.flush().then(_.bind(function() {
                var close = _.bind(this.close, this);
                if (self.pos.get('nbr_pending_operations').length > 0) {
                    var confirm = false;
                    $(QWeb.render('PosCloseWarning')).dialog({
                        resizable: false,
                        height:160,
                        modal: true,
                        title: "Warning",
                        buttons: {
                            "Yes": function() {
                                confirm = true;
                                $( this ).dialog( "close" );
                            },
                            "No": function() {
                                $( this ).dialog( "close" );
                            }
                        },
                        close: function() {
                            if (confirm){
                                close();
                            }
                        }
                    });
                } else {
                    close();
                }
            }, this));
        },
        close: function() {
            this.pos.barcode_reader.disconnect();
            return new session.web.Model("ir.model.data").get_func("search_read")([['name', '=', 'action_pos_close_statement']], ['res_id']).pipe(
                    _.bind(function(res) {
                return this.rpc('/web/action/load', {'action_id': res[0]['res_id']}).pipe(_.bind(function(result) {
                    var action = result.result;
                    action.context = _.extend(action.context || {}, {'cancel_action': {type: 'ir.actions.client', tag: 'default_home'}});
                    this.do_action(action);
                }, this));
            }, this));
        },
        destroy: function() {
            instance.webclient.set_content_full_screen(false);
            self.pos = undefined;
            this._super();
        }
    });
}
