function openerp_pos_models(instance, module){ //module is instance.point_of_sale
    var QWeb = instance.web.qweb;

    module.LocalStorageDAO = instance.web.Class.extend({
        add_operation: function(operation) {
            var self = this;
            return $.async_when().pipe(function() {
                var tmp = self._get('oe_pos_operations', []);
                var last_id = self._get('oe_pos_operations_sequence', 1);
                tmp.push({'id': last_id, 'data': operation});
                self._set('oe_pos_operations', tmp);
                self._set('oe_pos_operations_sequence', last_id + 1);
            });
        },
        remove_operation: function(id) {
            var self = this;
            return $.async_when().pipe(function() {
                var tmp = self._get('oe_pos_operations', []);
                tmp = _.filter(tmp, function(el) {
                    return el.id !== id;
                });
                self._set('oe_pos_operations', tmp);
            });
        },
        get_operations: function() {
            var self = this;
            return $.async_when().pipe(function() {
                return self._get('oe_pos_operations', []);
            });
        },
        _get: function(key, default_) {
            var txt = localStorage['oe_pos_dao_'+key];
            if (! txt)
                return default_;
            return JSON.parse(txt);
        },
        _set: function(key, value) {
            localStorage['oe_pos_dao_'+key] = JSON.stringify(value);
        },
        reset_stored_data: function(){
            for(key in localStorage){
                if(key.indexOf('oe_pos_dao_') === 0){
                    delete localStorage[key];
                }
            }
        },
    });

    var fetch = function(model, fields, domain, ctx){
        return new instance.web.Model(model).query(fields).filter(domain).context(ctx).all()
    };
    
    // The PosModel contains the Point Of Sale's representation of the backend.
    // Since the PoS must work in standalone ( Without connection to the server ) 
    // it must contains a representation of the server's PoS backend. 
    // (taxes, product list, configuration options, etc.)  this representation
    // is fetched and stored by the PosModel at the initialisation. 
    // this is done asynchronously, a ready deferred alows the GUI to wait interactively 
    // for the loading to be completed 
    // There is a single instance of the PosModel for each Front-End instance, it is usually called
    // 'pos' and is available to almost all widgets.

    module.PosModel = Backbone.Model.extend({
        initialize: function(session, attributes) {
            Backbone.Model.prototype.initialize.call(this, attributes);
            var  self = this;
            this.session = session;                 
            this.dao = new module.LocalStorageDAO();            // used to store the order's data on the Hard Drive
            this.ready = $.Deferred();                          // used to notify the GUI that the PosModel has loaded all resources
            this.flush_mutex = new $.Mutex();                   // used to make sure the orders are sent to the server once at time

            this.barcode_reader = new module.BarcodeReader({'pos': this});  // used to read barcodes
            this.proxy = new module.ProxyDevice();              // used to communicate to the hardware devices via a local proxy
            this.db = new module.PosLS();                       // a database used to store the products and categories
            this.db.clear();

            window.db = this.db;

            // pos settings
            this.use_scale              = false;
            this.use_proxy_printer      = false;
            this.use_virtual_keyboard   = false;
            this.use_websql             = false;
            this.use_barcode_scanner    = false;

            // default attributes values. If null, it will be loaded below.
            this.set({
                'nbr_pending_operations': 0,    

                'currency':         {symbol: '$', position: 'after'},
                'shop':             null, 
                'company':          null,
                'user':             null,   // the user that loaded the pos
                'user_list':        null,   // list of all users
                'cashier':          null,   // the logged cashier, if different from user

                'orders':           new module.OrderCollection(),
                //this is the product list as seen by the product list widgets, it will change based on the category filters
                'products':         new module.ProductCollection(), 
                'cashRegisters':    null, 

                'bank_statements':  null,
                'taxes':            null,
                'pos_session':      null,
                'pos_config':       null,

                'selectedOrder':    undefined,
            });

            this.get('orders').bind('remove', function(){ self.on_removed_order(); });
            
            // We fetch the backend data on the server asynchronously. this is done only when the pos user interface is launched,
            // Any change on this data made on the server is thus not reflected on the point of sale until it is relaunched. 

            var user_def = fetch('res.users',['name','company_id'],[['id','=',this.session.uid]]) 
                .pipe(function(users){
                    var user = users[0];
                    self.set('user',user);

                    return fetch('res.company',
                    [
                        'currency_id',
                        'email',
                        'website',
                        'company_registry',
                        //TODO contact_address
                        'vat',
                        'name',
                        'phone'
                    ],
                    [['id','=',user.company_id[0]]])
                }).pipe(function(companies){
                    var company = companies[0];
                    self.set('company',company);

                    return fetch('res.currency',['symbol','position'],[['id','=',company.currency_id[0]]]);
                }).pipe(function (currencies){
                    self.set('currency',currencies[0]);
                });


            var uom_def = fetch(    //unit of measure
                'product.uom',
                null,
                null
                ).then(function(result){
                    self.set({'units': result});
                    var units_by_id = {};
                    for(var i = 0, len = result.length; i < len; i++){
                        units_by_id[result[i].id] = result[i];
                    }
                    self.set({'units_by_id':units_by_id});
                });

            var pack_def = fetch(
                'product.packaging',
                null,
                null
                ).then(function(packaging){
                    self.set('product.packaging',packaging);
                });

            var users_def = fetch(
                'res.users',
                ['name','ean13'],
                [['ean13', '!=', false]]
                ).then(function(result){
                    self.set({'user_list':result});
                });

            var tax_def = fetch('account.tax', ['amount','price_include','type'])
                .then(function(result){
                    self.set({'taxes': result});
                });

            var session_def = fetch(    // loading the PoS Session.
                    'pos.session',
                    ['id', 'journal_ids','name','user_id','config_id','start_at','stop_at'],
                    [['state', '=', 'opened'], ['user_id', '=', this.session.uid]]
                ).pipe(function(result) {

                    // some data are associated with the pos session, like the pos config and bank statements.
                    // we must have a valid session before we can read those. 
                    
                    var session_data_def = new $.Deferred();

                    if( result.length !== 0 ) {
                        var pos_session = result[0];

                        self.set({'pos_session': pos_session});

                        var pos_config_def = fetch(
                                'pos.config',
                                ['name','journal_ids','shop_id','journal_id',
                                 'iface_self_checkout', 'iface_websql', 'iface_led', 'iface_cashdrawer',
                                 'iface_payment_terminal', 'iface_electronic_scale', 'iface_barscan', 'iface_vkeyboard',
                                 'iface_print_via_proxy','iface_cashdrawer','state','sequence_id','session_ids'],
                                [['id','=', pos_session.config_id[0]]]
                            ).pipe(function(result){
                                var pos_config = result[0]
                                
                                self.set({'pos_config': pos_config});
                                self.use_scale              = pos_config.iface_electronic_scale  || false;
                                self.use_proxy_printer      = pos_config.iface_print_via_proxy   || false;
                                self.use_virtual_keyboard   = pos_config.iface_vkeyboard         || false;
                                self.use_websql             = pos_config.iface_websql            || false;
                                self.use_barcode_scanner    = pos_config.iface_barscan           || false;
                                self.use_selfcheckout       = pos_config.iface_self_checkout     || false;
                                self.use_cashbox            = pos_config.iface_cashdrawer        || false;

                                return fetch('sale.shop',[], [['id','=',pos_config.shop_id[0]]])
                            }).pipe(function(shops){
                                self.set('shop',shops[0]);
                                return fetch('pos.category', ['id','name', 'parent_id', 'child_id', 'category_image_small'])
                            }).pipe( function(categories){
                                self.db.add_categories(categories);
                                return fetch( 
                                    'product.product', 
                                    ['name', 'list_price','price','pos_categ_id', 'taxes_id','product_image_small', 'ean13', 'to_weight', 'uom_id', 'uos_id', 'uos_coeff', 'mes_type'],
                                    [['pos_categ_id','!=', false]],
                                    {pricelist: self.get('shop').pricelist_id[0]} // context for price
                                );
                            }).pipe( function(products){
                                self.db.add_products(products);
                            });

                        var bank_def = fetch(
                            'account.bank.statement',
                            ['account_id','currency','journal_id','state','name','user_id','pos_session_id'],
                            [['state','=','open'],['pos_session_id', '=', pos_session.id]]
                            ).then(function(result){
                                self.set({'bank_statements':result});
                            });

                        var journal_def = fetch(
                            'account.journal',
                            undefined,
                            [['user_id','=',pos_session.user_id[0]]]
                            ).then(function(result){
                                self.set({'journals':result});
                            });

                        // associate the bank statements with their journals. 
                        var bank_process_def = $.when(bank_def, journal_def)
                            .then(function(){
                                var bank_statements = self.get('bank_statements');
                                var journals = self.get('journals');
                                for(var i = 0, ilen = bank_statements.length; i < ilen; i++){
                                    for(var j = 0, jlen = journals.length; j < jlen; j++){
                                        if(bank_statements[i].journal_id[0] === journals[j].id){
                                            bank_statements[i].journal = journals[j];
                                            bank_statements[i].self_checkout_payment_method = journals[j].self_checkout_payment_method;
                                        }
                                    }
                                }
                            });

                        session_data_def = $.when(pos_config_def,bank_def,journal_def,bank_process_def);

                    }else{
                        session_data_def.reject();
                    }
                    return session_data_def;
                });

            // when all the data has loaded, we compute some stuff, and declare the Pos ready to be used. 
            $.when(pack_def, user_def, users_def, uom_def, session_def, tax_def, user_def, this.flush())
                .then(function(){ 
                    self.set({'cashRegisters' : new module.CashRegisterCollection(self.get('bank_statements'))});
                    //self.log_loaded_data(); //Uncomment if you want to log the data to the console for easier debugging
                    self.ready.resolve();
                },function(){
                    //we failed to load some backend data, or the backend was badly configured.
                    //the error messages will be displayed in PosWidget
                    self.ready.reject();
                });
        },

        // logs the usefull posmodel data to the console for debug purposes
        log_loaded_data: function(){
            console.log('PosModel data has been loaded:');
            console.log('PosModel: categories:',this.get('categories'));
            console.log('PosModel: units:',this.get('units'));
            console.log('PosModel: bank_statements:',this.get('bank_statements'));
            console.log('PosModel: journals:',this.get('journals'));
            console.log('PosModel: taxes:',this.get('taxes'));
            console.log('PosModel: pos_session:',this.get('pos_session'));
            console.log('PosModel: pos_config:',this.get('pos_config'));
            console.log('PosModel: cashRegisters:',this.get('cashRegisters'));
            console.log('PosModel: shop:',this.get('shop'));
            console.log('PosModel: company:',this.get('company'));
            console.log('PosModel: currency:',this.get('currency'));
            console.log('PosModel: user_list:',this.get('user_list'));
            console.log('PosModel: user:',this.get('user'));
            console.log('PosModel.session:',this.session);
            console.log('PosModel end of data log.');
        },
        
        // this is called when an order is removed from the order collection. It ensures that there is always an existing
        // order and a valid selected order
        on_removed_order: function(removed_order){
            if( this.get('orders').isEmpty()){
                this.add_new_order();
            }
            if( this.get('selectedOrder') === removed_order){
                this.set({ selectedOrder: this.get('orders').last() });
            }
        },

        // saves the order locally and try to send it to the backend. 'record' is a bizzarely defined JSON version of the Order
        push_order: function(record) {
            var self = this;
            return this.dao.add_operation(record).pipe(function(){
                return self.flush();
            });
        },

        //creates a new empty order and sets it as the current order
        add_new_order: function(){
            var order = new module.Order({pos:this});
            this.get('orders').add(order);
            this.set('selectedOrder', order);
        },

        // attemps to send all pending orders ( stored in the DAO ) to the server.
        // it will do it one by one, and remove the successfully sent ones from the DAO once
        // it has been confirmed that they have been received.
        flush: function() {
            //this makes sure only one _int_flush is called at the same time
            return this.flush_mutex.exec(_.bind(function() {
                return this._int_flush();
            }, this));
        },
        _int_flush : function() {
            var self = this;

            this.dao.get_operations().pipe(function(operations) {
                // operations are really Orders that are converted to json.
                // they are saved to disk and then we attempt to send them to the backend so that they can
                // be applied. 
                // since the network is not reliable we potentially have many 'pending operations' that have not been sent.
                self.set( {'nbr_pending_operations':operations.length} );
                if(operations.length === 0){
                    return $.when();
                }
                var order = operations[0];

                 // we prevent the default error handler and assume errors
                 // are a normal use case, except we stop the current iteration

                 return (new instance.web.Model('pos.order')).get_func('create_from_ui')([order])
                            .fail(function(unused, event){
                                // wtf ask niv
                                event.preventDefault();
                            })
                            .pipe(function(){
                                // success: remove the successfully sent operation, and try to send the next one 
                                self.dao.remove_operation(operations[0].id).pipe(function(){
                                    return self._int_flush();
                                });
                            }, function(){
                                // in case of error we just sit there and do nothing. wtf ask niv
                                return $.when();
                            });
            });
        },

        scan_product: function(parsed_ean){
            var self = this;
            var def  = new $.Deferred();
            this.db.get_product_by_ean13(parsed_ean.base_ean, function(product){
                var selectedOrder = this.get('selectedOrder');
                if(!product){
                    def.reject('product-not-found: '+parsed_ean.base_ean);
                    return;
                }
                if(parsed_ean.type === 'price'){
                    selectedOrder.addProduct(new module.Product(product), {price:parsed_ean.value});
                }else if(parsed_ean.type === 'weight'){
                    selectedOrder.addProduct(new module.Product(product), {quantity:parsed_ean.value, merge:false});
                }else{
                    selectedOrder.addProduct(new module.Product(product));
                }
                def.resolve();
            });
            return def;
        },
    });

    module.CashRegister = Backbone.Model.extend({
    });

    module.CashRegisterCollection = Backbone.Collection.extend({
        model: module.CashRegister,
    });

    module.Product = Backbone.Model.extend({
    });

    module.ProductCollection = Backbone.Collection.extend({
        model: module.Product,
    });

    // An orderline represent one element of the content of a client's shopping cart.
    // An orderline contains a product, its quantity, its price, discount. etc. 
    // An Order contains zero or more Orderlines.
    module.Orderline = Backbone.Model.extend({
        initialize: function(attr,options){
            this.pos = options.pos;
            this.order = options.order;
            this.product = options.product;
            this.price   = options.product.get('list_price');
            this.quantity = 1;
            this.discount = 0;
            this.type = 'unit';
            this.selected = false;
        },
        // sets a discount [0,100]%
        set_discount: function(discount){
            this.discount = Math.max(0,Math.min(100,discount));
            this.trigger('change');
        },
        // returns the discount [0,100]%
        get_discount: function(){
            return this.discount;
        },
        // FIXME
        get_product_type: function(){
            return this.type;
        },
        // sets the quantity of the product. The quantity will be rounded according to the 
        // product's unity of measure properties. Quantities greater than zero will not get 
        // rounded to zero
        set_quantity: function(quantity){
            if(_.isNaN(quantity)){
                this.order.removeOrderline(this);
            }else if(quantity !== undefined){
                this.quantity = Math.max(0,quantity);
                var unit = this.get_unit();
                if(unit && this.quantity > 0 ){
                    this.quantity = Math.max(unit.rounding, Math.round(quantity / unit.rounding) * unit.rounding);
                }
            }
            this.trigger('change');
        },
        // return the quantity of product
        get_quantity: function(){
            return this.quantity;
        },
        // return the unit of measure of the product
        get_unit: function(){
            var unit_id = (this.product.get('uos_id') || this.product.get('uom_id'));
            if(!unit_id){
                return undefined;
            }
            unit_id = unit_id[0];
            if(!this.pos){
                return undefined;
            }
            return this.pos.get('units_by_id')[unit_id];
        },
        // return the product of this orderline
        get_product: function(){
            return this.product;
        },
        // return the base price of this product (for this orderline)
        get_list_price: function(){
            return this.price;
        },
        // changes the base price of the product for this orderline
        set_list_price: function(price){
            this.price = price;
            this.trigger('change');
        },
        // selects or deselects this orderline
        set_selected: function(selected){
            this.selected = selected;
            this.trigger('change');
        },
        // returns true if this orderline is selected
        is_selected: function(){
            return this.selected;
        },
        // when we add an new orderline we want to merge it with the last line to see reduce the number of items
        // in the orderline. This returns true if it makes sense to merge the two
        can_be_merged_with: function(orderline){
            if( this.get_product().get('id') !== orderline.get_product().get('id')){    //only orderline of the same product can be merged
                return false;
            }else if(this.get_product_type() !== orderline.get_product_type()){
                return false;
            }else if(this.get_discount() > 0){             // we don't merge discounted orderlines
                return false;
            }else if(this.price !== orderline.price){
                return false;
            }else{ 
                return true;
            }
        },
        merge: function(orderline){
            this.set_quantity(this.get_quantity() + orderline.get_quantity());
        },
        export_as_JSON: function() {
            return {
                qty: this.get_quantity(),
                price_unit: this.get_list_price(),
                discount: this.get_discount(),
                product_id: this.get_product().get('id'),
            };
        },
        //used to create a json of the ticket, to be sent to the printer
        export_for_printing: function(){
            return {
                quantity:           this.get_quantity(),
                unit_name:          this.get_unit().name,
                list_price:         this.get_list_price(),
                discount:           this.get_discount(),
                product_name:       this.get_product().get('name'),
                price_with_tax :    this.get_price_with_tax(),
                price_without_tax:  this.get_price_without_tax(),
                tax:                this.get_tax(),
            };
        },
        get_price_without_tax: function(){
            return this.get_all_prices().priceWithoutTax;
        },
        get_price_with_tax: function(){
            return this.get_all_prices().priceWithTax;
        },
        get_tax: function(){
            return this.get_all_prices().tax;
        },
        get_all_prices: function() {
            var self = this;
            var base = this.get_quantity() * this.price * (1 - (this.get_discount() / 100));
            var totalTax = base;
            var totalNoTax = base;
            
            var product_list = this.pos.get('product_list');
            var product =  this.get_product(); 
            var taxes_ids = product.taxes_id;
            var taxes =  self.pos.get('taxes');
            var taxtotal = 0;
            _.each(taxes_ids, function(el) {
                var tax = _.detect(taxes, function(t) {return t.id === el;});
                if (tax.price_include) {
                    var tmp;
                    if (tax.type === "percent") {
                        tmp =  base - (base / (1 + tax.amount));
                    } else if (tax.type === "fixed") {
                        tmp = tax.amount * self.get_quantity();
                    } else {
                        throw "This type of tax is not supported by the point of sale: " + tax.type;
                    }
                    taxtotal += tmp;
                    totalNoTax -= tmp;
                } else {
                    var tmp;
                    if (tax.type === "percent") {
                        tmp = tax.amount * base;
                    } else if (tax.type === "fixed") {
                        tmp = tax.amount * self.get_quantity();
                    } else {
                        throw "This type of tax is not supported by the point of sale: " + tax.type;
                    }
                    taxtotal += tmp;
                    totalTax += tmp;
                }
            });
            return {
                "priceWithTax": totalTax,
                "priceWithoutTax": totalNoTax,
                "tax": taxtotal,
            };
        },
    });

    module.OrderlineCollection = Backbone.Collection.extend({
        model: module.Orderline,
    });

    // Every PaymentLine contains a cashregister and an amount of money.
    module.Paymentline = Backbone.Model.extend({
        initialize: function(attributes, options) {
            this.amount = 0;
            this.cashregister = options.cashRegister;
        },
        //sets the amount of money on this payment line
        set_amount: function(value){
            this.amount = value;
            this.trigger('change');
        },
        // returns the amount of money on this paymentline
        get_amount: function(){
            return this.amount;
        },
        // returns the associated cashRegister
        get_cashregister: function(){
            return this.cashregister;
        },
        //exports as JSON for server communication
        export_as_JSON: function(){
            return {
                name: instance.web.datetime_to_str(new Date()),
                statement_id: this.cashregister.get('id'),
                account_id: (this.cashregister.get('account_id'))[0],
                journal_id: (this.cashregister.get('journal_id'))[0],
                amount: this.get_amount()
            };
        },
        //exports as JSON for receipt printing
        export_for_printing: function(){
            return {
                amount: this.get_amount(),
                journal: this.cashregister.get('journal_id')[1],
            };
        },
    });

    module.PaymentlineCollection = Backbone.Collection.extend({
        model: module.Paymentline,
    });
    

    // An order more or less represents the content of a client's shopping cart (the OrderLines) 
    // plus the associated payment information (the PaymentLines) 
    // there is always an active ('selected') order in the Pos, a new one is created
    // automaticaly once an order is completed and sent to the server.
    module.Order = Backbone.Model.extend({
        initialize: function(attributes){
            Backbone.Model.prototype.initialize.apply(this, arguments);
            this.set({
                creationDate:   new Date(),
                orderLines:     new module.OrderlineCollection(),
                paymentLines:   new module.PaymentlineCollection(),
                name:           "Order " + this.generateUniqueId(),
                client:         null,
            });
            this.pos =     attributes.pos; 
            this.selected_orderline = undefined;
            this.screen_data = {};  // see ScreenSelector
            return this;
        },
        generateUniqueId: function() {
            return new Date().getTime();
        },
        addProduct: function(product, options){
            options = options || {};
            var attr = product.toJSON();
            attr.pos = this.pos;
            attr.order = this;
            var line = new module.Orderline({}, {pos: this.pos, order: this, product: product});

            if(options.quantity !== undefined){
                line.set_quantity(options.quantity);
            }
            if(options.price !== undefined){
                line.set_list_price(options.price);
            }

            var last_orderline = this.getLastOrderline();
            if( last_orderline && last_orderline.can_be_merged_with(line) && options.merge !== false){
                last_orderline.merge(line);
            }else{
                this.get('orderLines').add(line);
            }
            this.selectLine(this.getLastOrderline());
        },
        removeOrderline: function( line ){
            this.get('orderLines').remove(line);
            this.selectLine(this.getLastOrderline());
        },
        getLastOrderline: function(){
            return this.get('orderLines').at(this.get('orderLines').length -1);
        },
        addPaymentLine: function(cashRegister) {
            var paymentLines = this.get('paymentLines');
            var newPaymentline = new module.Paymentline({},{cashRegister:cashRegister});
            if(cashRegister.get('journal').type !== 'cash'){
                newPaymentline.set_amount( this.getDueLeft() );
            }
            paymentLines.add(newPaymentline);
        },
        getName: function() {
            return this.get('name');
        },
        getTotal: function() {
            return (this.get('orderLines')).reduce((function(sum, orderLine) {
                return sum + orderLine.get_price_with_tax();
            }), 0);
        },
        getTotalTaxExcluded: function() {
            return (this.get('orderLines')).reduce((function(sum, orderLine) {
                return sum + orderLine.get_price_without_tax();
            }), 0);
        },
        getTax: function() {
            return (this.get('orderLines')).reduce((function(sum, orderLine) {
                return sum + orderLine.get_tax();
            }), 0);
        },
        getPaidTotal: function() {
            return (this.get('paymentLines')).reduce((function(sum, paymentLine) {
                return sum + paymentLine.get_amount();
            }), 0);
        },
        getChange: function() {
            return this.getPaidTotal() - this.getTotal();
        },
        getDueLeft: function() {
            return this.getTotal() - this.getPaidTotal();
        },
        // the client related to the current order.
        set_client: function(client){
            this.set('client',client);
        },
        get_client: function(){
            return this.get('client');
        },
        // the order also stores the screen status, as the PoS supports
        // different active screens per order. This method is used to
        // store the screen status.
        set_screen_data: function(key,value){
            if(arguments.length === 2){
                this.screen_data[key] = value;
            }else if(arguments.length === 1){
                for(key in arguments[0]){
                    this.screen_data[key] = arguments[0][key];
                }
            }
        },
        //see set_screen_data
        get_screen_data: function(key){
            return this.screen_data[key];
        },
        // exports a JSON for receipt printing
        export_for_printing: function(){
            var orderlines = [];
            this.get('orderLines').each(function(orderline){
                orderlines.push(orderline.export_for_printing());
            });

            var paymentlines = [];
            this.get('paymentLines').each(function(paymentline){
                paymentlines.push(paymentline.export_for_printing());
            });
            var client  = this.get('client');
            var cashier = this.pos.get('cashier') || this.pos.get('user');
            var company = this.pos.get('company');
            var shop    = this.pos.get('shop');
            var date = new Date();

            return {
                orderlines: orderlines,
                paymentlines: paymentlines,
                total_with_tax: this.getTotal(),
                total_without_tax: this.getTotalTaxExcluded(),
                total_tax: this.getTax(),
                total_paid: this.getPaidTotal(),
                change: this.getChange(),
                name : this.getName(),
                client: client ? client.name : null ,
                cashier: cashier ? cashier.name : null,
                date: { 
                    year: date.getFullYear(), 
                    month: date.getMonth(), 
                    date: date.getDate(),       // day of the month 
                    day: date.getDay(),         // day of the week 
                    hour: date.getHours(), 
                    minute: date.getMinutes() 
                }, 
                company:{
                    email: company.email,
                    website: company.website,
                    company_registry: company.company_registry,
                    contact_address: null,  //TODO
                    vat: company.vat,
                    name: company.name,
                    phone: company.phone,
                },
                shop:{
                    name: shop.name,
                },
                currency: this.pos.get('currency'),
            };
        },
        exportAsJSON: function() {
            var orderLines, paymentLines;
            orderLines = [];
            (this.get('orderLines')).each(_.bind( function(item) {
                return orderLines.push([0, 0, item.export_as_JSON()]);
            }, this));
            paymentLines = [];
            (this.get('paymentLines')).each(_.bind( function(item) {
                return paymentLines.push([0, 0, item.export_as_JSON()]);
            }, this));
            return {
                name: this.getName(),
                amount_paid: this.getPaidTotal(),
                amount_total: this.getTotal(),
                amount_tax: this.getTax(),
                amount_return: this.getChange(),
                lines: orderLines,
                statement_ids: paymentLines,
                pos_session_id: this.pos.get('pos_session').id,
                partner_id: this.pos.get('client') ? this.pos.get('client').id : undefined,
                user_id: this.pos.get('cashier') ? this.pos.get('cashier').id : this.pos.get('user').id,
            };
        },
        getSelectedLine: function(){
            return this.selected_orderline;
        },
        selectLine: function(line){
            if(line){
                if(line !== this.selected_orderline){
                    if(this.selected_orderline){
                        this.selected_orderline.set_selected(false);
                    }
                    this.selected_orderline = line;
                    this.selected_orderline.set_selected(true);
                }
            }else{
                this.selected_orderline = undefined;
            }
        },
    });

    module.OrderCollection = Backbone.Collection.extend({
        model: module.Order,
    });

    /*
     The numpad handles both the choice of the property currently being modified
     (quantity, price or discount) and the edition of the corresponding numeric value.
     */
    module.NumpadState = Backbone.Model.extend({
        defaults: {
            buffer: "0",
            mode: "quantity"
        },
        appendNewChar: function(newChar) {
            var oldBuffer;
            oldBuffer = this.get('buffer');
            if (oldBuffer === '0') {
                this.set({
                    buffer: newChar
                });
            } else if (oldBuffer === '-0') {
                this.set({
                    buffer: "-" + newChar
                });
            } else {
                this.set({
                    buffer: (this.get('buffer')) + newChar
                });
            }
            this.updateTarget();
        },
        deleteLastChar: function() {
            var tempNewBuffer = this.get('buffer').slice(0, -1);

            if(!tempNewBuffer){
                this.set({ buffer: "0" });
                this.killTarget();
            }else{
                if (isNaN(tempNewBuffer)) {
                    tempNewBuffer = "0";
                }
                this.set({ buffer: tempNewBuffer });
                this.updateTarget();
            }
        },
        switchSign: function() {
            var oldBuffer;
            oldBuffer = this.get('buffer');
            this.set({
                buffer: oldBuffer[0] === '-' ? oldBuffer.substr(1) : "-" + oldBuffer
            });
            this.updateTarget();
        },
        changeMode: function(newMode) {
            this.set({
                buffer: "0",
                mode: newMode
            });
        },
        reset: function() {
            this.set({
                buffer: "0",
                mode: "quantity"
            });
        },
        updateTarget: function() {
            var bufferContent, params;
            bufferContent = this.get('buffer');
            if (bufferContent && !isNaN(bufferContent)) {
            	this.trigger('set_value', parseFloat(bufferContent));
            }
        },
        killTarget: function(){
            this.trigger('set_value',Number.NaN);
        },
    });
}
