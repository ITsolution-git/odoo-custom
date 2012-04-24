function pos_widgets(module, instance){
    var QWeb = instance.web.qweb;

    var qweb_template = function(template,posmodel){
        return function(ctx){
            if(!posmodel){  //this is a huge hack that needs to be removed ... TODO
                var HackPosModel = Backbone.Model.extend({
                    initialize:function(){
                        this.set({
                            'currency': {symbol: '$', position: 'after'},
                        });
                    },
                });
                posmodel = new HackPosModel();
            }
            return QWeb.render(template, _.extend({}, ctx,{
                'currency': posmodel.get('currency'),
                'format_amount': function(amount) {
                    if (posmodel.get('currency').position == 'after') {
                        return amount + ' ' + posmodel.get('currency').symbol;
                    } else {
                        return posmodel.get('currency').symbol + ' ' + amount;
                    }
                },
                }));
        };
    };

    module.NumpadWidget = instance.web.OldWidget.extend({
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
    /*
     Gives access to the payment methods (aka. 'cash registers')
     */
    module.PaypadWidget = instance.web.OldWidget.extend({
        init: function(parent, options) {
            this._super(parent);
            this.shop = options.shop;
        },
        start: function() {
            this.$element.find('button').click(_.bind(this.performPayment, this));
        },
        performPayment: function(event) {
            if (this.shop.get('selectedOrder').get('step') === 'receipt')
                return;
            var cashRegister, cashRegisterCollection, cashRegisterId;
            /* set correct view */
            this.shop.get('selectedOrder').set({'step': 'payment'});

            cashRegisterId = event.currentTarget.attributes['cash-register-id'].nodeValue;
            cashRegisterCollection = this.shop.get('cashRegisters');
            cashRegister = cashRegisterCollection.find(_.bind( function(item) {
                return (item.get('id')) === parseInt(cashRegisterId, 10);
            }, this));
            return (this.shop.get('selectedOrder')).addPaymentLine(cashRegister);
        },
        renderElement: function() {
            this.$element.empty();
            return (this.shop.get('cashRegisters')).each(_.bind( function(cashRegister) {
                var button = new module.PaymentButtonWidget();
                button.model = cashRegister;
                button.appendTo(this.$element);
            }, this));
        }
    });

    module.PaymentButtonWidget = instance.web.OldWidget.extend({
        template_fct: qweb_template('pos-payment-button-template'),
        renderElement: function() {
            this.$element.html(this.template_fct({
                id: this.model.get('id'),
                name: (this.model.get('journal_id'))[1]
            }));
            return this;
        }
    });
    /*
     There are 3 steps in a POS workflow:
     1. prepare the order (i.e. chose products, quantities etc.)
     2. choose payment method(s) and amount(s)
     3. validae order and print receipt
     It should be possible to go back to any step as long as step 3 hasn't been completed.
     Modifying an order after validation shouldn't be allowed.
     */
    module.StepSwitcher = instance.web.OldWidget.extend({
        init: function(parent, options) {
            this._super(parent);
            this.shop = options.shop;
            this.change_order();
            this.shop.bind('change:selectedOrder', this.change_order, this);
        },
        change_order: function() {
            if (this.selected_order) {
                this.selected_order.unbind('change:step', this.change_step);
            }
            this.selected_order = this.shop.get('selectedOrder');
            if (this.selected_order) {
                this.selected_order.bind('change:step', this.change_step, this);
            }
            this.change_step();
        },
        change_step: function() {
            var new_step = this.selected_order ? this.selected_order.get('step') : 'products';
            $('.step-screen').hide();
            $('#' + new_step + '-screen').show();
        },
    });
    /*
     Shopping carts.
     */
    module.OrderlineWidget = instance.web.OldWidget.extend({
        tagName: 'tr',
        template_fct: qweb_template('pos-orderline-template'),
        init: function(parent, options) {
            this._super(parent);
            this.model = options.model;
            this.model.bind('change', _.bind( function() {
                this.refresh();
            }, this));
            this.model.bind('remove', _.bind( function() {
                this.$element.remove();
            }, this));
            this.order = options.order;
        },
        start: function() {
            this.$element.click(_.bind(this.clickHandler, this));
            this.refresh();
        },
        clickHandler: function() {
            this.select();
        },
        renderElement: function() {
            this.$element.html(this.template_fct(this.model.toJSON()));
            this.select();
        },
        refresh: function() {
            this.renderElement();
            var heights = _.map(this.$element.prevAll(), function(el) {return $(el).outerHeight();});
            heights.push($('#current-order thead').outerHeight());
            var position = _.reduce(heights, function(memo, num){ return memo + num; }, 0);
            $('#current-order').scrollTop(position);
        },
        select: function() {
            $('tr.selected').removeClass('selected');
            this.$element.addClass('selected');
            this.order.selected = this.model;
            this.on_selected();
        },
        on_selected: function() {},
    });

    module.OrderWidget = instance.web.OldWidget.extend({
        init: function(parent, options) {
            this._super(parent);
            this.shop = options.shop;
            this.setNumpadState(options.numpadState);
            this.shop.bind('change:selectedOrder', this.changeSelectedOrder, this);
            this.bindOrderLineEvents();
        },
        setNumpadState: function(numpadState) {
        	if (this.numpadState) {
        		this.numpadState.unbind('setValue', this.setValue);
        	}
        	this.numpadState = numpadState;
        	if (this.numpadState) {
        		this.numpadState.bind('setValue', this.setValue, this);
        		this.numpadState.reset();
        	}
        },
        setValue: function(val) {
        	var param = {};
        	param[this.numpadState.get('mode')] = val;
        	var order = this.shop.get('selectedOrder');
        	if (order.get('orderLines').length !== 0) {
        	   order.selected.set(param);
        	} else {
        	    this.shop.get('selectedOrder').destroy();
        	}
        },
        changeSelectedOrder: function() {
            this.currentOrderLines.unbind();
            this.bindOrderLineEvents();
            this.renderElement();
        },
        bindOrderLineEvents: function() {
            this.currentOrderLines = (this.shop.get('selectedOrder')).get('orderLines');
            this.currentOrderLines.bind('add', this.addLine, this);
            this.currentOrderLines.bind('remove', this.renderElement, this);
        },
        addLine: function(newLine) {
            var line = new module.OrderlineWidget(null, {
                    model: newLine,
                    order: this.shop.get('selectedOrder')
            });
            line.on_selected.add(_.bind(this.selectedLine, this));
            this.selectedLine();
            line.appendTo(this.$element);
            this.updateSummary();
        },
        selectedLine: function() {
        	var reset = false;
        	if (this.currentSelected !== this.shop.get('selectedOrder').selected) {
        		reset = true;
        	}
        	this.currentSelected = this.shop.get('selectedOrder').selected;
        	if (reset && this.numpadState)
        		this.numpadState.reset();
            this.updateSummary();
        },
        renderElement: function() {
            this.$element.empty();
            this.currentOrderLines.each(_.bind( function(orderLine) {
                var line = new module.OrderlineWidget(null, {
                        model: orderLine,
                        order: this.shop.get('selectedOrder')
                });
            	line.on_selected.add(_.bind(this.selectedLine, this));
                line.appendTo(this.$element);
            }, this));
            this.updateSummary();
        },
        updateSummary: function() {
            var currentOrder, tax, total, totalTaxExcluded;
            currentOrder = this.shop.get('selectedOrder');
            total = currentOrder.getTotal();
            totalTaxExcluded = currentOrder.getTotalTaxExcluded();
            tax = currentOrder.getTax();
            $('#subtotal').html(totalTaxExcluded.toFixed(2)).hide().fadeIn();
            $('#tax').html(tax.toFixed(2)).hide().fadeIn();
            $('#total').html(total.toFixed(2)).hide().fadeIn();
        },
    });

    /*
     "Products" step.
     */
    module.CategoryWidget = instance.web.OldWidget.extend({
        init: function(parent, options){
            this._super(parent,options.element_id);
            this.posmodel = options.posmodel;
        },
        start: function() {
            this.$element.find(".oe-pos-categories-list a").click(_.bind(this.changeCategory, this));
        },
        template_fct: qweb_template('pos-category-template'),
        renderElement: function() {
            var self = this;
            var c;
            this.$element.html(this.template_fct({
                breadcrumb: (function() {
                    var _i, _len, _results;
                    _results = [];
                    for (_i = 0, _len = self.ancestors.length; _i < _len; _i++) {
                        c = self.ancestors[_i];
                        _results.push(self.posmodel.categories[c]);
                    }
                    return _results;
                })(),
                categories: (function() {
                    var _i, _len, _results;
                    _results = [];
                    for (_i = 0, _len = self.children.length; _i < _len; _i++) {
                        c = self.children[_i];
                        _results.push(self.posmodel.categories[c]);
                    }
                    return _results;
                })()
            }));
        },
        changeCategory: function(a) {
            var id = $(a.target).data("category-id");
            this.on_change_category(id);
        },
        on_change_category: function(id) {},
    });

    module.ProductWidget = instance.web.OldWidget.extend({
        tagName:'li',
        template_fct: qweb_template('pos-product-template'),
        init: function(parent, options) {
            this._super(parent);
            this.model = options.model;
            this.shop = options.shop;
        },
        start: function(options) {
            $("a", this.$element).click(_.bind(this.addToOrder, this));
        },
        addToOrder: function(event) {
            /* Preserve the category URL */
            event.preventDefault();
            return (this.shop.get('selectedOrder')).addProduct(this.model);
        },
        renderElement: function() {
            this.$element.addClass("product");
            this.$element.html(this.template_fct(this.model.toJSON()));
            return this;
        },
    });

    module.ProductListWidget = instance.web.OldWidget.extend({
        init: function(parent, options) {
            this._super(parent);
            this.model = options.model;
            this.shop = options.shop;
            this.shop.get('products').bind('reset', this.renderElement, this);
        },
        renderElement: function() {
            this.$element.empty();
            (this.shop.get('products')).each(_.bind( function(product) {
                var p = new module.ProductWidget(null, {
                        model: product,
                        shop: this.shop
                });
                p.appendTo(this.$element);
            }, this));
            return this;
        },
    });
    /*
     "Payment" step.
     */
    module.PaymentlineWidget = instance.web.OldWidget.extend({
        tagName: 'tr',
        template_fct: qweb_template('pos-paymentline-template'),
        init: function(parent, options) {
            this._super(parent);
            this.model = options.model;
            this.model.bind('change', this.changedAmount, this);
        },
        on_delete: function() {},
        changeAmount: function(event) {
            var newAmount;
            newAmount = event.currentTarget.value;
            if (newAmount && !isNaN(newAmount)) {
            	this.amount = parseFloat(newAmount);
                this.model.set({
                    amount: this.amount,
                });
            }
        },
        changedAmount: function() {
        	if (this.amount !== this.model.get('amount'))
        		this.renderElement();
        },
        renderElement: function() {
        	this.amount = this.model.get('amount');
            this.$element.html(this.template_fct({
                name: (this.model.get('journal_id'))[1],
                amount: this.amount,
            }));
            this.$element.addClass('paymentline');
            $('input', this.$element).keyup(_.bind(this.changeAmount, this));
            $('.delete-payment-line', this.$element).click(this.on_delete);
        },
    });

    module.PaymentWidget = instance.web.OldWidget.extend({
        init: function(parent, options) {
            this._super(parent);
            this.model = options.model;
            this.shop = options.shop;
            this.posmodel = options.posmodel;
            this.shop.bind('change:selectedOrder', this.changeSelectedOrder, this);
            this.bindPaymentLineEvents();
            this.bindOrderLineEvents();
        },
        paymentLineList: function() {
            return this.$element.find('#paymentlines');
        },
        start: function() {
            $('button#validate-order', this.$element).click(_.bind(this.validateCurrentOrder, this));
            $('.oe-back-to-products', this.$element).click(_.bind(this.back, this));
        },
        back: function() {
            this.shop.get('selectedOrder').set({"step": "products"});
        },
        validateCurrentOrder: function() {
            var callback, currentOrder;
            currentOrder = this.shop.get('selectedOrder');
            $('button#validate-order', this.$element).attr('disabled', 'disabled');
            this.posmodel.push_order(currentOrder.exportAsJSON()).then(_.bind(function() {
                $('button#validate-order', this.$element).removeAttr('disabled');
                return currentOrder.set({
                    validated: true
                });
            }, this));
        },
        bindPaymentLineEvents: function() {
            this.currentPaymentLines = (this.shop.get('selectedOrder')).get('paymentLines');
            this.currentPaymentLines.bind('add', this.addPaymentLine, this);
            this.currentPaymentLines.bind('remove', this.renderElement, this);
            this.currentPaymentLines.bind('all', this.updatePaymentSummary, this);
        },
        bindOrderLineEvents: function() {
            this.currentOrderLines = (this.shop.get('selectedOrder')).get('orderLines');
            this.currentOrderLines.bind('all', this.updatePaymentSummary, this);
        },
        changeSelectedOrder: function() {
            this.currentPaymentLines.unbind();
            this.bindPaymentLineEvents();
            this.currentOrderLines.unbind();
            this.bindOrderLineEvents();
            this.renderElement();
        },
        addPaymentLine: function(newPaymentLine) {
            var x = new module.PaymentlineWidget(null, {
                    model: newPaymentLine
                });
            x.on_delete.add(_.bind(this.deleteLine, this, x));
            x.appendTo(this.paymentLineList());
        },
        renderElement: function() {
            this.paymentLineList().empty();
            this.currentPaymentLines.each(_.bind( function(paymentLine) {
                this.addPaymentLine(paymentLine);
            }, this));
            this.updatePaymentSummary();
        },
        deleteLine: function(lineWidget) {
        	this.currentPaymentLines.remove([lineWidget.model]);
        },
        updatePaymentSummary: function() {
            var currentOrder, dueTotal, paidTotal, remaining, remainingAmount;
            currentOrder = this.shop.get('selectedOrder');
            paidTotal = currentOrder.getPaidTotal();
            dueTotal = currentOrder.getTotal();
            this.$element.find('#payment-due-total').html(dueTotal.toFixed(2));
            this.$element.find('#payment-paid-total').html(paidTotal.toFixed(2));
            remainingAmount = dueTotal - paidTotal;
            remaining = remainingAmount > 0 ? 0 : (-remainingAmount).toFixed(2);
            $('#payment-remaining').html(remaining);
        },
        setNumpadState: function(numpadState) {
        	if (this.numpadState) {
        		this.numpadState.unbind('setValue', this.setValue);
        		this.numpadState.unbind('change:mode', this.setNumpadMode);
        	}
        	this.numpadState = numpadState;
        	if (this.numpadState) {
        		this.numpadState.bind('setValue', this.setValue, this);
        		this.numpadState.bind('change:mode', this.setNumpadMode, this);
        		this.numpadState.reset();
        		this.setNumpadMode();
        	}
        },
    	setNumpadMode: function() {
    		this.numpadState.set({mode: 'payment'});
    	},
        setValue: function(val) {
        	this.currentPaymentLines.last().set({amount: val});
        },
    });

    module.ReceiptWidget = instance.web.OldWidget.extend({
        init: function(parent, options) {
            this._super(parent);
            this.model = options.model;
            this.shop = options.shop;
            this.posmodel = options.posmodel;
            this.user = this.posmodel.get('user');
            this.company = this.posmodel.get('company');
            this.shop_obj = this.posmodel.get('shop');
        },
        start: function() {
            this.shop.bind('change:selectedOrder', this.changeSelectedOrder, this);
            this.changeSelectedOrder();
        },
        renderElement: function() {
            this.$element.html(qweb_template('pos-receipt-view'));
            $('button#pos-finish-order', this.$element).click(_.bind(this.finishOrder, this));
            $('button#print-the-ticket', this.$element).click(_.bind(this.print, this));
        },
        print: function() {
            window.print();
        },
        finishOrder: function() {
            this.shop.get('selectedOrder').destroy();
        },
        changeSelectedOrder: function() {
            if (this.currentOrderLines)
                this.currentOrderLines.unbind();
            this.currentOrderLines = (this.shop.get('selectedOrder')).get('orderLines');
            this.currentOrderLines.bind('add', this.refresh, this);
            this.currentOrderLines.bind('change', this.refresh, this);
            this.currentOrderLines.bind('remove', this.refresh, this);
            if (this.currentPaymentLines)
                this.currentPaymentLines.unbind();
            this.currentPaymentLines = (this.shop.get('selectedOrder')).get('paymentLines');
            this.currentPaymentLines.bind('all', this.refresh, this);
            this.refresh();
        },
        refresh: function() {
            this.currentOrder = this.shop.get('selectedOrder');
            $('.pos-receipt-container', this.$element).html(qweb_template('pos-ticket')({widget:this}));
        },
    });

    module.OrderButtonWidget = instance.web.OldWidget.extend({
        tagName: 'li',
        template_fct: qweb_template('pos-order-selector-button-template'),
        init: function(parent, options) {
            this._super(parent);
            this.order = options.order;
            this.shop = options.shop;
            this.order.bind('destroy', _.bind( function() {
                this.destroy();
            }, this));
            this.shop.bind('change:selectedOrder', _.bind( function(shop) {
                var selectedOrder;
                selectedOrder = shop.get('selectedOrder');
                if (this.order === selectedOrder) {
                    this.setButtonSelected();
                }
            }, this));
        },
        start: function() {
            $('button.select-order', this.$element).click(_.bind(this.selectOrder, this));
            $('button.close-order', this.$element).click(_.bind(this.closeOrder, this));
        },
        selectOrder: function(event) {
            this.shop.set({
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
        renderElement: function() {
            this.$element.html(this.template_fct({widget:this}));
            this.$element.addClass('order-selector-button');
        }
    });

    module.ActionButtonWidget = instance.web.Widget.extend({
        template:'pos-action-button',
        init: function(parent, options){
            this._super(parent, options);
            this.label = options.label || 'button';
            this.rightalign = options.rightalign || false;
            if(options.icon){
                this.icon = options.icon;
                this.template = 'pos-action-button-with-icon';
            }
        },
    });

    module.ActionbarWidget = instance.web.Widget.extend({
        template:'pos-actionbar',
        init: function(parent, options){
            this._super(parent,options);
            this.left_button_list = [];
            this.right_button_list = [];
        },
        start: function(){
            console.log('hello world!');
            window.actionbarwidget = this;
        },
        destroyButtons:function(position){
            var button_list;
            if(position === 'left'){
                button_list = this.left_button_list;
                this.left_button_list = [];
            }else if (position === 'right'){
                button_list = this.right_button_list;
                this.right_button_list = [];
            }else{
                return this;
            }
            for(var i = 0; i < button_list.length; i++){
                button_list[i].destroy();
            }
            return this;
        },
        addNewButton: function(position,button_options){
            if(arguments.length == 2){
                var button_list;
                var $button_list;
                if(position === 'left'){ 
                    button_list = this.left_button_list;
                    $button_list = $('.pos-actionbar-left-region');
                }else if(position === 'right'){
                    button_list = this.right_button_list;
                    $button_list = $('.pos-actionbar-right-region');
                }
                var button = new module.ActionButtonWidget(this,button_options);
                button_list.push(button);
                button.appendTo($button_list);
            }else{
                for(var i = 1; i < arguments.length; i++){
                    this.addNewButton(position,arguments[i]);
                }
            }
            return this;
        }
        /*
        renderElement: function() {
            //this.$element.html(this.template_fct());
        },*/
    });

    // A Widget that displays an onscreen keyboard.
    // There are two options when creating the widget :
    // 
    // * 'keyboard_model' : 'simple' | 'full' (default) 
    //   The 'full' emulates a PC keyboard, while 'simple' emulates an 'android' one.
    //
    // * 'input_selector  : (default: '.searchbox input') 
    //   defines the dom element that the keyboard will write to.
    // 
    // The widget is initially hidden. It can be shown with this.show(), and is 
    // automatically shown when the input_selector gets focused.
    module.OnscreenKeyboardWidget = instance.web.Widget.extend({
        tagName: 'div',
        
        init: function(parent, options){
            var self = this;

            this._super(parent,options);
            
            function get_option(opt,default_value){ 
                if(options){
                    return options[opt] || default_value;
                }else{
                    return default_value;
                }
            }

            this.keyboard_model = get_option('keyboard_model','full');
            this.template_simple = qweb_template('pos-onscreen-keyboard-simple-template');
            this.template_full   = qweb_template('pos-onscreen-keyboard-full-template');

            this.template_fct = function(){ 
                if( this.keyboard_model == 'full' ){
                    return this.template_full.apply(this,arguments);
                }else{
                    return this.template_simple.apply(this,arguments);
                }
            };

            this.input_selector = get_option('input_selector','.searchbox input');

            //show the keyboard when the input zone is clicked.
            $(this.input_selector).focus(function(){self.show();});

            //Keyboard state
            this.capslock = false;
            this.shift    = false;
            this.numlock  = false;
        },
        
        // Write a character to the input zone
        writeCharacter: function(character){
            var $input = $(this.input_selector);
            $input[0].value += character;
            $input.keydown();
            $input.keyup();
        },
        
        // Sends a 'return' character to the input zone. TODO
        sendReturn: function(){
        },
        
        // Removes the last character from the input zone.
        deleteCharacter: function(){
            var $input = $(this.input_selector);
            var input_value = $input[0].value;
            $input[0].value = input_value.substr(0, input_value.length - 1);
            $input.keydown();
            $input.keyup();
        },
        
        // Clears the content of the input zone.
        deleteAllCharacters: function(){
            var $input = $(this.input_selector);
            $input[0].value = "";
            $input.keydown();
            $input.keyup();
        },
        renderElement: function(){
            this.$element.html(this.template_fct());
        },
        
        // Makes the keyboard show and slide from the bottom of the screen.
        show:  function(){
            $('.keyboard_frame').show().animate({'height':'235px'}, 500, 'swing');
        },
        
        // Makes the keyboard hide by sliding to the bottom of the screen.
        hide:  function(){
            var self = this;
            var frame = $('.keyboard_frame');
            frame.animate({'height':'0'}, 500, 'swing', function(){ frame.hide(); self.reset(); });
        },
        
        //What happens when the shift key is pressed : toggle case, remove capslock
        toggleShift: function(){
            $('.letter').toggleClass('uppercase');
            $('.symbol span').toggle();
            
            self.shift = (self.shift === true) ? false : true;
            self.capslock = false;
        },
        
        //what happens when capslock is pressed : toggle case, set capslock
        toggleCapsLock: function(){
            $('.letter').toggleClass('uppercase');
            self.capslock = true;
        },
        
        //What happens when numlock is pressed : toggle symbols and numlock label 
        toggleNumLock: function(){
            $('.symbol span').toggle();
            $('.numlock span').toggle();
            self.numlock = (self.numlock === true ) ? false : true;
        },

        //After a key is pressed, shift is disabled. 
        removeShift: function(){
            if (self.shift === true) {
                $('.symbol span').toggle();
                if (this.capslock === false) $('.letter').toggleClass('uppercase');
                
                self.shift = false;
            }
        },

        // Resets the keyboard to its original state; capslock: false, shift: false, numlock: false
        reset: function(){
            if(this.shift){
                this.toggleShift();
            }
            if(this.capslock){
                this.toggleCapsLock();
            }
            if(this.numlock){
                this.toggleNumLock();
            }
        },

        //called after the keyboard is in the DOM, sets up the key bindings.
        start: function(){
            var self = this;

            //this.show();


            $('.close_button').click(function(){ 
                self.deleteAllCharacters();
                self.hide(); 
            });

            // Keyboard key click handling
            $('.keyboard li').click(function(){
                
                var $this = $(this),
                    character = $this.html(); // If it's a lowercase letter, nothing happens to this variable
                
                if ($this.hasClass('left-shift') || $this.hasClass('right-shift')) {
                    self.toggleShift();
                    return false;
                }
                
                if ($this.hasClass('capslock')) {
                    self.toggleCapsLock();
                    return false;
                }
                
                if ($this.hasClass('delete')) {
                    self.deleteCharacter();
                    return false;
                }

                if ($this.hasClass('numlock')){
                    self.toggleNumLock();
                    return false;
                }
                
                // Special characters
                if ($this.hasClass('symbol')) character = $('span:visible', $this).html();
                if ($this.hasClass('space')) character = ' ';
                if ($this.hasClass('tab')) character = "\t";
                if ($this.hasClass('return')) character = "\n";
                
                // Uppercase letter
                if ($this.hasClass('uppercase')) character = character.toUpperCase();
                
                // Remove shift once a key is clicked.
                self.removeShift();

                self.writeCharacter(character);
            });
        },
    });

    module.ShopWidget = instance.web.OldWidget.extend({
        init: function(parent, options) {
            this._super(parent);
            this.shop = options.shop;
            this.posmodel = options.posmodel;
        },
        start: function() {
            $('button#neworder-button', this.$element).click(_.bind(this.createNewOrder, this));

            (this.shop.get('orders')).bind('add', this.orderAdded, this);
            (this.shop.get('orders')).add(new module.Order({'posmodel':this.posmodel}));
            this.productListView = new module.ProductListWidget(null, {
                shop: this.shop
            });
            this.productListView.$element = $("#products-screen-ol");
            this.productListView.renderElement();
            this.productListView.start();
            this.paypadView = new module.PaypadWidget(null, {
                shop: this.shop
            });
            this.paypadView.$element = $('#paypad');
            this.paypadView.renderElement();
            this.paypadView.start();
            this.numpadView = new module.NumpadWidget(null);
            this.numpadView.$element = $('#numpad');
            this.numpadView.start();
            this.orderView = new module.OrderWidget(null, {
                shop: this.shop,
            });
            this.orderView.$element = $('#current-order-content');
            this.orderView.start();
            this.paymentView = new module.PaymentWidget(null, {
                shop: this.shop,
                posmodel: this.posmodel,
            });
            this.paymentView.$element = $('#payment-screen');
            this.paymentView.renderElement();
            this.paymentView.start();
            this.receiptView = new module.ReceiptWidget(null, {
                shop: this.shop,
                posmodel: this.posmodel,
            });
            this.receiptView.replace($('#receipt-screen'));
            this.stepSwitcher = new module.StepSwitcher(this, {shop: this.shop});
            this.shop.bind('change:selectedOrder', this.changedSelectedOrder, this);
            this.changedSelectedOrder();
        },
        createNewOrder: function() {
            var newOrder;
            newOrder = new module.Order({'posmodel': this.posmodel});
            (this.shop.get('orders')).add(newOrder);
            this.shop.set({
                selectedOrder: newOrder
            });
        },
        orderAdded: function(newOrder) {
            var newOrderButton;
            newOrderButton = new module.OrderButtonWidget(null, {
                order: newOrder,
                shop: this.shop
            });
            newOrderButton.appendTo($('#orders'));
            newOrderButton.selectOrder();
        },
        changedSelectedOrder: function() {
        	if (this.currentOrder) {
        		this.currentOrder.unbind('change:step', this.changedStep);
        	}
        	this.currentOrder = this.shop.get('selectedOrder');
        	this.currentOrder.bind('change:step', this.changedStep, this);
        	this.changedStep();
        },
        changedStep: function() {
        	var step = this.currentOrder.get('step');
        	this.orderView.setNumpadState(null);
        	this.paymentView.setNumpadState(null);
        	if (step === 'products') {
        		this.orderView.setNumpadState(this.numpadView.state);
        	} else if (step === 'payment') {
        		this.paymentView.setNumpadState(this.numpadView.state);
        	}
        },
    });

    namespace.SynchNotification = instance.web.OldWidget.extend({
        template: "pos-synch-notification",
        init: function() {
            this._super.apply(this, arguments);
            this.nbr_pending = 0;
        },
        renderElement: function() {
            this._super.apply(this, arguments);
            $('.oe_pos_synch-notification-button', this.$element).click(this.on_synch);
        },
        on_change_nbr_pending: function(nbr_pending) {
            this.nbr_pending = nbr_pending;
            this.renderElement();
        },
        on_synch: function() {}
    });

    namespace.POSWidget = instance.web.OldWidget.extend({
        init: function() {
            this._super.apply(this, arguments);

            this.posmodel = new namespace.PosModel(this.session);

        },
        start: function() {
            var self = this;
            return self.posmodel.ready.then(_.bind(function() {
                this.renderElement();
                this.synch_notification = new namespace.SynchNotification(this);
                this.synch_notification.replace($('.oe_pos_synch-notification', this.$element));
                this.synch_notification.on_synch.add(_.bind(self.posmodel.flush, self.posmodel));
                
                self.posmodel.bind('change:nbr_pending_operations', this.changed_pending_operations, this);
                this.changed_pending_operations();
                
                this.$element.find("#loggedas button").click(function() {
                    self.try_close();
                });

                self.posmodel.app = new namespace.App(self.$element, self.posmodel);
                instance.webclient.set_content_full_screen(true);
                
                if (self.posmodel.get('bank_statements').length === 0)
                    return new instance.web.Model("ir.model.data").get_func("search_read")([['name', '=', 'action_pos_open_statement']], ['res_id']).pipe(
                            _.bind(function(res) {
                        return this.rpc('/web/action/load', {'action_id': res[0]['res_id']}).pipe(_.bind(function(result) {
                            var action = result.result;
                            this.do_action(action);
                        }, this));
                    }, this));
            }, this));
        },
        render: function() {
            return qweb_template("POSWidget")();
        },
        changed_pending_operations: function () {
            var self = this;
            this.synch_notification.on_change_nbr_pending(self.posmodel.get('nbr_pending_operations').length);
        },
        try_close: function() {
            var self = this;
            self.posmodel.flush().then(_.bind(function() {
                var close = _.bind(this.close, this);
                if (self.posmodel.get('nbr_pending_operations').length > 0) {
                    var confirm = false;
                    $(QWeb.render('pos-close-warning')).dialog({
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
                            if (confirm)
                                close();
                        }
                    });
                } else {
                    close();
                }
            }, this));
        },
        close: function() {
            // remove barcode reader event listener
            $('body').undelegate('', 'keyup')

            return new instance.web.Model("ir.model.data").get_func("search_read")([['name', '=', 'action_pos_close_statement']], ['res_id']).pipe(
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
            self.posmodel = undefined;
            this._super();
        }
    });

}
