openerp.point_of_sale = function(db) {
    db.point_of_sale = {};

    /* Some utility functions defined by Coffee script */
    var __bind = function(fn, me) {
        return function() {
            return fn.apply(me, arguments);
        };
    };
    var __hasProp = Object.prototype.hasOwnProperty;
    var __extends = function(child, parent) {
        for (var key in parent) {
            if (__hasProp.call(parent, key))
                child[key] = parent[key];
        }
        function ctor() {
            this.constructor = child;
        }

        ctor.prototype = parent.prototype;
        child.prototype = new ctor;
        child.__super__ = parent.prototype;
        return child;
    };
    var __indexOf = Array.prototype.indexOf ||
    function(item) {
        for (var i = 0, l = this.length; i < l; i++) {
            if (this[i] === item)
                return i;
        }
        return -1;
    };
    /* end */

    var QWeb = db.web.qweb;
    QWeb.add_template("/point_of_sale/static/src/xml/pos.xml");
    var qweb_template = function(template) {
        return function(ctx) {
            return QWeb.render(template, ctx);
        };
    };

    /*
     Local store access. Read once from localStorage upon construction and persist on every change.
     There should only be one store active at any given time to ensure data consistency.
     */
    var Store = (function() {
        function Store() {
            var store;
            store = localStorage['pos'];
            this.data = (store && JSON.parse(store)) || {};
        }

        Store.prototype.get = function(key) {
            return this.data[key];
        };
        Store.prototype.set = function(key, value) {
            this.data[key] = value;
            return localStorage['pos'] = JSON.stringify(this.data);
        };
        return Store;
    })();
    /*
     Gets all the necessary data from the OpenERP web client (session, shop data etc.)
     */
    var Pos = (function() {
        function Pos(session) {
            this.build_tree = __bind(this.build_tree, this);
            this.session = session;
            $.when(this.fetch('pos.category', ['name', 'parent_id', 'child_id']),
                this.fetch('product.product', ['name', 'list_price', 'pos_categ_id', 'taxes_id', 'img'], [['pos_categ_id', '!=', 'false']]),
                this.fetch('account.bank.statement', ['account_id', 'currency', 'journal_id', 'state', 'name']),
                this.fetch('account.journal', ['auto_cash', 'check_dtls', 'currency', 'name', 'type']))
                .then(this.build_tree);
        }

        Pos.prototype.ready = $.Deferred();
        Pos.prototype.store = new Store;
        Pos.prototype.fetch = function(osvModel, fields, domain) {
            var dataSetSearch;
            var self = this;
            var callback = function(result) {
                return self.store.set(osvModel, result);
            };
            dataSetSearch = new db.web.DataSetSearch(this, osvModel, {}, domain);
            return dataSetSearch.read_slice(fields, 0).then(callback);
        };
        Pos.prototype.push = function(osvModel, record, callback, errorCallback) {
            var dataSet;
            dataSet = new db.web.DataSet(this, osvModel, null);
            return dataSet.create(record, callback, errorCallback);
        };
        Pos.prototype.categories = {};
        Pos.prototype.build_tree = function() {
            var c, id, _i, _len, _ref, _ref2;
            _ref = this.store.get('pos.category');
            for (_i = 0, _len = _ref.length; _i < _len; _i++) {
                c = _ref[_i];
                this.categories[c.id] = {
                    id: c.id,
                    name: c.name,
                    children: c.child_id,
                    parent: c.parent_id[0],
                    ancestors: [c.id],
                    subtree: [c.id]
                };
            }
            _ref2 = this.categories;
            for (id in _ref2) {
                c = _ref2[id];
                this.current_category = c;
                this.build_ancestors(c.parent);
                this.build_subtree(c);
            }
            this.categories[0] = {
                ancestors: [],
                children: (function() {
                    var _j, _len2, _ref3, _results;
                    _ref3 = this.store.get('pos.category');
                    _results = [];
                    for (_j = 0, _len2 = _ref3.length; _j < _len2; _j++) {
                        c = _ref3[_j];
                        if (!(c.parent_id[0] != null)) {
                            _results.push(c.id);
                        }
                    }
                    return _results;
                }).call(this),
                subtree: (function() {
                    var _j, _len2, _ref3, _results;
                    _ref3 = this.store.get('pos.category');
                    _results = [];
                    for (_j = 0, _len2 = _ref3.length; _j < _len2; _j++) {
                        c = _ref3[_j];
                        _results.push(c.id);
                    }
                    return _results;
                }).call(this)
            };
            return this.ready.resolve();
        };
        Pos.prototype.build_ancestors = function(parent) {
            if (parent != null) {
                this.current_category.ancestors.unshift(parent);
                return this.build_ancestors(this.categories[parent].parent);
            }
        };
        Pos.prototype.build_subtree = function(category) {
            var c, _i, _len, _ref, _results;
            _ref = category.children;
            _results = [];
            for (_i = 0, _len = _ref.length; _i < _len; _i++) {
                c = _ref[_i];
                this.current_category.subtree.push(c);
                _results.push(this.build_subtree(this.categories[c]));
            }
            return _results;
        };
        return Pos;
    })();

    /* global variable */
    var pos;

    var App, CashRegister, CashRegisterCollection, Category, CategoryCollection, CategoryView,
    NumpadState, NumpadWidget, Order, OrderButtonView, OrderCollection, OrderWidget, Orderline,
    OrderlineCollection, OrderlineWidget, PaymentButtonWidget, PaymentView, Paymentline,
    PaymentlineCollection, PaymentlineView, PaypadWidget, Product, ProductCollection,
    ProductListView, ProductView, ReceiptLineView, ReceiptView, Shop, ShopView, StepsWidget;

    /*
     ---
     Models
     ---
     */
    CashRegister = (function() {
        __extends(CashRegister, Backbone.Model);
        function CashRegister() {
            CashRegister.__super__.constructor.apply(this, arguments);
        }

        return CashRegister;
    })();
    CashRegisterCollection = (function() {
        __extends(CashRegisterCollection, Backbone.Collection);
        function CashRegisterCollection() {
            CashRegisterCollection.__super__.constructor.apply(this, arguments);
        }

        CashRegisterCollection.prototype.model = CashRegister;
        return CashRegisterCollection;
    })();
    Product = (function() {
        __extends(Product, Backbone.Model);
        function Product() {
            Product.__super__.constructor.apply(this, arguments);
        }

        return Product;
    })();
    ProductCollection = (function() {
        __extends(ProductCollection, Backbone.Collection);
        function ProductCollection() {
            ProductCollection.__super__.constructor.apply(this, arguments);
        }

        ProductCollection.prototype.model = Product;
        return ProductCollection;
    })();
    Category = (function() {
        __extends(Category, Backbone.Model);
        function Category() {
            Category.__super__.constructor.apply(this, arguments);
        }

        return Category;
    })();
    CategoryCollection = (function() {
        __extends(CategoryCollection, Backbone.Collection);
        function CategoryCollection() {
            CategoryCollection.__super__.constructor.apply(this, arguments);
        }

        CategoryCollection.prototype.model = Category;
        return CategoryCollection;
    })();
    /*
     Each Order contains zero or more Orderlines (i.e. the content of the "shopping cart".)
     There should only ever be one Orderline per distinct product in an Order.
     To add more of the same product, just update the quantity accordingly.
     The Order also contains payment information.
     */
    Orderline = (function() {
        __extends(Orderline, Backbone.Model);
        function Orderline() {
            Orderline.__super__.constructor.apply(this, arguments);
        }

        Orderline.prototype.defaults = {
            quantity: 1,
            list_price: 0,
            discount: 0
        };
        Orderline.prototype.incrementQuantity = function() {
            return this.set({
                quantity: (this.get('quantity')) + 1
            });
        };
        Orderline.prototype.getTotal = function() {
            return (this.get('quantity')) * (this.get('list_price')) * (1 - (this.get('discount')) / 100);
        };
        Orderline.prototype.exportAsJSON = function() {
            var result;
            result = {
                qty: this.get('quantity'),
                price_unit: this.get('list_price'),
                discount: this.get('discount'),
                product_id: this.get('id')
            };
            return result;
        };
        return Orderline;
    })();
    OrderlineCollection = (function() {
        __extends(OrderlineCollection, Backbone.Collection);
        function OrderlineCollection() {
            OrderlineCollection.__super__.constructor.apply(this, arguments);
        }

        OrderlineCollection.prototype.model = Orderline;
        return OrderlineCollection;
    })();
    /*
     Every PaymentLine has all the attributes of the corresponding CashRegister.
     */
    Paymentline = (function() {
        __extends(Paymentline, Backbone.Model);
        function Paymentline() {
            Paymentline.__super__.constructor.apply(this, arguments);
        }

        Paymentline.prototype.defaults = {
            amount: 0
        };
        Paymentline.prototype.getAmount = function() {
            return this.get('amount');
        };
        Paymentline.prototype.exportAsJSON = function() {
            var result;
            result = {
                name: "Payment line",
                statement_id: this.get('id'),
                account_id: (this.get('account_id'))[0],
                journal_id: (this.get('journal_id'))[0],
                amount: this.getAmount()
            };
            return result;
        };
        return Paymentline;
    })();
    PaymentlineCollection = (function() {
        __extends(PaymentlineCollection, Backbone.Collection);
        function PaymentlineCollection() {
            PaymentlineCollection.__super__.constructor.apply(this, arguments);
        }

        PaymentlineCollection.prototype.model = Paymentline;
        return PaymentlineCollection;
    })();
    Order = (function() {
        __extends(Order, Backbone.Model);
        function Order() {
            Order.__super__.constructor.apply(this, arguments);
        }

        Order.prototype.defaults = {
            validated: false
        };
        Order.prototype.initialize = function() {
            this.set({
                orderLines: new OrderlineCollection
            });
            this.set({
                paymentLines: new PaymentlineCollection
            });
            this.bind('change:validated', this.validatedChanged);
            return this.set({
                name: "Order " + this.generateUniqueId()
            });
        };
        Order.prototype.events = {
            'change:validated': 'validatedChanged'
        };
        Order.prototype.validatedChanged = function() {
            if (this.get("validated") && !this.previous("validated")) {
                $('.step-screen').hide();
                $('#receipt-screen').show();
            }
        }
        Order.prototype.generateUniqueId = function() {
            return new Date().getTime();
        };
        Order.prototype.addProduct = function(product) {
            var existing;
            existing = (this.get('orderLines')).get(product.id);
            if (existing != null) {
                return existing.incrementQuantity();
            } else {
                return (this.get('orderLines')).add(new Orderline(product.toJSON()));
            }
        };
        Order.prototype.addPaymentLine = function(cashRegister) {
            var newPaymentline;
            newPaymentline = new Paymentline(cashRegister);
            /* TODO: Should be 0 for cash-like accounts */
            newPaymentline.set({
                amount: this.getDueLeft()
            });
            return (this.get('paymentLines')).add(newPaymentline);
        };
        Order.prototype.getName = function() {
            return this.get('name');
        };
        Order.prototype.getTotal = function() {
            return (this.get('orderLines')).reduce((function(sum, orderLine) {
                return sum + orderLine.getTotal();
            }), 0);
        };
        Order.prototype.getTotalTaxExcluded = function() {
            return this.getTotal() / 1.21;
        };
        Order.prototype.getTax = function() {
            return this.getTotal() / 1.21 * 0.21;
        };
        Order.prototype.getPaidTotal = function() {
            return (this.get('paymentLines')).reduce((function(sum, paymentLine) {
                return sum + paymentLine.getAmount();
            }), 0);
        };
        Order.prototype.getChange = function() {
            return this.getPaidTotal() - this.getTotal();
        };
        Order.prototype.getDueLeft = function() {
            return this.getTotal() - this.getPaidTotal();
        };
        Order.prototype.exportAsJSON = function() {
            var orderLines, paymentLines, result;
            orderLines = [];
            (this.get('orderLines')).each(__bind( function(item) {
                return orderLines.push([0, 0, item.exportAsJSON()]);
            }, this));
            paymentLines = [];
            (this.get('paymentLines')).each(__bind( function(item) {
                return paymentLines.push([0, 0, item.exportAsJSON()]);
            }, this));
            result = {
                name: this.getName(),
                amount_paid: this.getPaidTotal(),
                amount_total: this.getTotal(),
                amount_tax: this.getTax(),
                amount_return: this.getChange(),
                lines: orderLines,
                statement_ids: paymentLines
            };
            return result;
        };
        return Order;
    })();
    OrderCollection = (function() {
        __extends(OrderCollection, Backbone.Collection);
        function OrderCollection() {
            OrderCollection.__super__.constructor.apply(this, arguments);
        }

        OrderCollection.prototype.model = Order;
        return OrderCollection;
    })();
    Shop = (function() {
        __extends(Shop, Backbone.Model);
        function Shop() {
            Shop.__super__.constructor.apply(this, arguments);
        }

        Shop.prototype.initialize = function() {
            this.set({
                orders: new OrderCollection(),
                products: new ProductCollection()
            });
            this.set({
                cashRegisters: new CashRegisterCollection(pos.store.get('account.bank.statement')),
            });
            return (this.get('orders')).bind('remove', __bind( function(removedOrder) {
                if ((this.get('orders')).isEmpty()) {
                    this.addAndSelectOrder(new Order);
                }
                if ((this.get('selectedOrder')) === removedOrder) {
                    return this.set({
                        selectedOrder: (this.get('orders')).last()
                    });
                }
            }, this));
        };
        Shop.prototype.addAndSelectOrder = function(newOrder) {
            (this.get('orders')).add(newOrder);
            return this.set({
                selectedOrder: newOrder
            });
        };
        return Shop;
    })();
    /*
     The numpad handles both the choice of the property currently being modified
     (quantity, price or discount) and the edition of the corresponding numeric value.
     */
    NumpadState = (function() {
        __extends(NumpadState, Backbone.Model);
        function NumpadState() {
            NumpadState.__super__.constructor.apply(this, arguments);
        }

        NumpadState.prototype.defaults = {
            buffer: "0",
            mode: "quantity"
        };
        NumpadState.prototype.initialize = function(options) {
            this.shop = options.shop;
            return this.shop.bind('change:selectedOrder', this.reset, this);
        };
        NumpadState.prototype.appendNewChar = function(newChar) {
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
            return this.updateTarget();
        };
        NumpadState.prototype.deleteLastChar = function() {
            var tempNewBuffer;
            tempNewBuffer = (this.get('buffer')).slice(0, -1) || "0";
            if (isNaN(tempNewBuffer)) {
                tempNewBuffer = "0";
            }
            this.set({
                buffer: tempNewBuffer
            });
            return this.updateTarget();
        };
        NumpadState.prototype.switchSign = function() {
            var oldBuffer;
            oldBuffer = this.get('buffer');
            this.set({
                buffer: oldBuffer[0] === '-' ? oldBuffer.substr(1) : "-" + oldBuffer
            });
            return this.updateTarget();
        };
        NumpadState.prototype.changeMode = function(newMode) {
            return this.set({
                buffer: "0",
                mode: newMode
            });
        };
        NumpadState.prototype.reset = function() {
            return this.set({
                buffer: "0"
            });
        };
        NumpadState.prototype.updateTarget = function() {
            var bufferContent, params;
            bufferContent = this.get('buffer');
            if (bufferContent && !isNaN(bufferContent)) {
                params = {};
                params[this.get('mode')] = parseFloat(bufferContent);
                return (this.shop.get('selectedOrder')).selected.set(params);
            }
        };
        return NumpadState;
    })();
    /*
     ---
     Views
     ---
     */
    NumpadWidget = db.web.Widget.extend({
        init: function(parent, element_id, options) {
            this._super(parent, element_id);
            this.state = options.state;
        },
        start: function() {
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
            newChar = event.currentTarget.innerText;
            return this.state.appendNewChar(newChar);
        },
        clickChangeMode: function(event) {
            var newMode;
            $('.selected-mode').removeClass('selected-mode');
            $(event.currentTarget).addClass('selected-mode');
            newMode = event.currentTarget.attributes['data-mode'].nodeValue;
            return this.state.changeMode(newMode);
        }
    });
    /*
     Gives access to the payment methods (aka. 'cash registers')
     */
    PaypadWidget = db.web.Widget.extend({
        init: function(parent, element_id, options) {
            this._super(parent, element_id);
            this.shop = options.shop;
        },
        start: function() {
            this.$element.find('button').click(_.bind(this.performPayment, this));
        },
        performPayment: function(event) {
            var cashRegister, cashRegisterCollection, cashRegisterId;
            /* set correct view */
            $('.step-screen').hide();
            $('#payment-screen').show();

            cashRegisterId = event.currentTarget.attributes['cash-register-id'].nodeValue;
            cashRegisterCollection = this.shop.get('cashRegisters');
            cashRegister = cashRegisterCollection.find(__bind( function(item) {
                return (item.get('id')) === parseInt(cashRegisterId, 10);
            }, this));
            return (this.shop.get('selectedOrder')).addPaymentLine(cashRegister);
        },
        render_element: function() {
            this.$element.empty();
            return (this.shop.get('cashRegisters')).each(__bind( function(cashRegister) {
                var button = new PaymentButtonWidget();
                button.model = cashRegister;
                button.appendTo(this.$element);
            }, this));
        }
    });
    PaymentButtonWidget = db.web.Widget.extend({
        template_fct: qweb_template('pos-payment-button-template'),
        render_element: function() {
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
    StepsWidget = db.web.Widget.extend({
        init: function(parent, element_id) {
            this._super(parent, element_id);
            this.step = "products";
        },
        start: function() {
            this.$element.find('input.step-button').click(_.bind(this.clickChangeStep, this));
        },
        clickChangeStep: function(event) {
            var newStep;
            newStep = event.currentTarget.attributes['data-step'].nodeValue;
            $('.step-screen').hide();
            $('#' + newStep + '-screen').show();
            return this.step = newStep;
        }
    });
    /*
     Shopping carts.
     */
    OrderlineWidget = db.web.Widget.extend({
        tagName: 'tr',
        template_fct: qweb_template('pos-orderline-template'),
        init: function(parent, element_id, options) {
            this._super(parent, element_id);
            this.model = options.model;
            this.model.bind('change', __bind( function() {
                this.$element.hide();
                this.render_element();
            }, this));
            this.model.bind('remove', __bind( function() {
                return this.$element.remove();
            }, this));
            this.order = options.order;
            this.numpadState = options.numpadState;
        },
        start: function() {
            this.$element.click(_.bind(this.clickHandler, this));
        },
        clickHandler: function() {
            this.numpadState.reset();
            return this.select();
        },
        render_element: function() {
            this.select();
            return this.$element.html(this.template_fct(this.model.toJSON())).fadeIn(400, function() {
                return $('#current-order').scrollTop($(this).offset().top);
            });
        },
        select: function() {
            $('tr.selected').removeClass('selected');
            this.$element.addClass('selected');
            return this.order.selected = this.model;
        },
    });
    OrderWidget = db.web.Widget.extend({
        init: function(parent, element_id, options) {
            this._super(parent, element_id);
            this.shop = options.shop;
            this.numpadState = options.numpadState;
            this.shop.bind('change:selectedOrder', this.changeSelectedOrder, this);
            this.bindOrderLineEvents();
        },
        changeSelectedOrder: function() {
            this.currentOrderLines.unbind();
            this.bindOrderLineEvents();
            return this.render_element();
        },
        bindOrderLineEvents: function() {
            this.currentOrderLines = (this.shop.get('selectedOrder')).get('orderLines');
            this.currentOrderLines.bind('add', this.addLine, this);
            this.currentOrderLines.bind('change', this.render_element, this);
            return this.currentOrderLines.bind('remove', this.render, this);
        },
        addLine: function(newLine) {
            var line = new OrderlineWidget(null, null, {
                    model: newLine,
                    order: this.shop.get('selectedOrder'),
                    numpadState: this.numpadState
            });
            line.appendTo(this.$element);
            return this.updateSummary();
        },
        render_element: function() {
            this.$element.empty();
            this.currentOrderLines.each(__bind( function(orderLine) {
                var line = new OrderlineWidget(null, null, {
                        model: orderLine,
                        order: this.shop.get('selectedOrder'),
                        numpadState: this.numpadState
                });
                line.appendTo(this.$element);
            }, this));
            return this.updateSummary();
        },
        updateSummary: function() {
            var currentOrder, tax, total, totalTaxExcluded;
            currentOrder = this.shop.get('selectedOrder');
            total = currentOrder.getTotal();
            totalTaxExcluded = currentOrder.getTotalTaxExcluded();
            tax = currentOrder.getTax();
            $('#subtotal').html(totalTaxExcluded.toFixed(2)).hide().fadeIn();
            $('#tax').html(tax.toFixed(2)).hide().fadeIn();
            return $('#total').html(total.toFixed(2)).hide().fadeIn();
        },
    });
    /*
     "Products" step.
     */
    CategoryView = (function() {
        __extends(CategoryView, Backbone.View);
        function CategoryView() {
            CategoryView.__super__.constructor.apply(this, arguments);
        }
        
        CategoryView.prototype.events = {
            'click .oe-pos-categories-list a': 'changeCategory'
        };

        CategoryView.prototype.template = qweb_template('pos-category-template');
        CategoryView.prototype.render = function(ancestors, children) {
            var c;
            return $(this.el).html(this.template({
                breadcrumb: (function() {
                    var _i, _len, _results;
                    _results = [];
                    for (_i = 0, _len = ancestors.length; _i < _len; _i++) {
                        c = ancestors[_i];
                        _results.push(pos.categories[c]);
                    }
                    return _results;
                })(),
                categories: (function() {
                    var _i, _len, _results;
                    _results = [];
                    for (_i = 0, _len = children.length; _i < _len; _i++) {
                        c = children[_i];
                        _results.push(pos.categories[c]);
                    }
                    return _results;
                })()
            }));
        };
        CategoryView.prototype.changeCategory = function(a) {
            var id = $(a.target).data("category-id");
            this.trigger("changeCategory", id);
        };
        return CategoryView;
    })();
    ProductView = (function() {
        __extends(ProductView, Backbone.View);
        function ProductView() {
            ProductView.__super__.constructor.apply(this, arguments);
        }

        ProductView.prototype.tagName = 'li';
        ProductView.prototype.className = 'product';
        ProductView.prototype.template = qweb_template('pos-product-template');
        ProductView.prototype.events = {
            'click a': 'addToOrder'
        };
        ProductView.prototype.initialize = function(options) {
            return this.shop = options.shop;
        };
        ProductView.prototype.addToOrder = function(event) {
            /* Preserve the category URL */
            event.preventDefault();
            return (this.shop.get('selectedOrder')).addProduct(this.model);
        };
        ProductView.prototype.render = function() {
            return $(this.el).html(this.template(this.model.toJSON()));
        };
        return ProductView;
    })();
    ProductListView = (function() {
        __extends(ProductListView, Backbone.View);
        function ProductListView() {
            ProductListView.__super__.constructor.apply(this, arguments);
        }

        ProductListView.prototype.tagName = 'ol';
        ProductListView.prototype.className = 'product-list';
        ProductListView.prototype.initialize = function(options) {
            this.shop = options.shop;
            return (this.shop.get('products')).bind('reset', this.render, this);
        };
        ProductListView.prototype.render = function() {
            $(this.el).empty();
            (this.shop.get('products')).each(__bind( function(product) {
                return $(this.el).append((new ProductView({
                        model: product,
                        shop: this.shop
                    })).render());
            }, this));
            return $('#products-screen').append(this.el);
        };
        return ProductListView;
    })();
    /*
     "Payment" step.
     */
    PaymentlineView = (function() {
        __extends(PaymentlineView, Backbone.View);
        function PaymentlineView() {
            PaymentlineView.__super__.constructor.apply(this, arguments);
        }

        PaymentlineView.prototype.tagName = 'tr';
        PaymentlineView.prototype.className = 'paymentline';
        PaymentlineView.prototype.template = qweb_template('pos-paymentline-template');
        PaymentlineView.prototype.initialize = function() {
            return this.model.bind('change', this.render, this);
        };
        PaymentlineView.prototype.events = {
            'keyup input': 'changeAmount'
        };
        PaymentlineView.prototype.changeAmount = function(event) {
            var newAmount;
            newAmount = event.currentTarget.value;
            if (newAmount && !isNaN(newAmount)) {
                return this.model.set({
                    amount: parseFloat(newAmount)
                });
            }
        };
        PaymentlineView.prototype.render = function() {
            return $(this.el).html(this.template({
                name: (this.model.get('journal_id'))[1],
                amount: this.model.get('amount')
            }));
        };
        return PaymentlineView;
    })();
    PaymentView = (function() {
        __extends(PaymentView, Backbone.View);
        function PaymentView() {
            PaymentView.__super__.constructor.apply(this, arguments);
        }

        PaymentView.prototype.initialize = function(options) {
            this.shop = options.shop;
            this.shop.bind('change:selectedOrder', this.changeSelectedOrder, this);
            this.bindPaymentLineEvents();
            return this.bindOrderLineEvents();
        };
        PaymentView.prototype.paymentLineList = function() {
            return $(this.el).find('#paymentlines');
        };
        PaymentView.prototype.events = {
            'click button#validate-order': 'validateCurrentOrder'
        };
        PaymentView.prototype.validateCurrentOrder = function() {
            var callback, currentOrder;
            currentOrder = this.shop.get('selectedOrder');
            callback = __bind( function() {
                return currentOrder.set({
                    validated: true
                });
            }, this);
            return pos.push('pos.order', currentOrder.exportAsJSON(), callback);
        };
        PaymentView.prototype.bindPaymentLineEvents = function() {
            this.currentPaymentLines = (this.shop.get('selectedOrder')).get('paymentLines');
            this.currentPaymentLines.bind('add', this.addPaymentLine, this);
            this.currentPaymentLines.bind('change', this.render, this);
            this.currentPaymentLines.bind('remove', this.render, this);
            return this.currentPaymentLines.bind('all', this.updatePaymentSummary, this);
        };
        PaymentView.prototype.bindOrderLineEvents = function() {
            this.currentOrderLines = (this.shop.get('selectedOrder')).get('orderLines');
            return this.currentOrderLines.bind('all', this.updatePaymentSummary, this);
        };
        PaymentView.prototype.changeSelectedOrder = function() {
            this.currentPaymentLines.unbind();
            this.bindPaymentLineEvents();
            this.currentOrderLines.unbind();
            this.bindOrderLineEvents();
            return this.render();
        };
        PaymentView.prototype.addPaymentLine = function(newPaymentLine) {
            return this.paymentLineList().append((new PaymentlineView({
                    model: newPaymentLine
                })).render());
        };
        PaymentView.prototype.render = function() {
            this.paymentLineList().empty();
            this.currentPaymentLines.each(__bind( function(paymentLine) {
                return this.paymentLineList().append((new PaymentlineView({
                        model: paymentLine
                    })).render());
            }, this));
            return this.updatePaymentSummary();
        };
        PaymentView.prototype.updatePaymentSummary = function() {
            var currentOrder, dueTotal, paidTotal, remaining, remainingAmount;
            currentOrder = this.shop.get('selectedOrder');
            paidTotal = currentOrder.getPaidTotal();
            dueTotal = currentOrder.getTotal();
            $(this.el).find('#payment-due-total').html(dueTotal.toFixed(2));
            $(this.el).find('#payment-paid-total').html(paidTotal.toFixed(2));
            remainingAmount = dueTotal - paidTotal;
            remaining = remainingAmount > 0 ? 0 : (-remainingAmount).toFixed(2);
            return $('#payment-remaining').html(remaining);
        };
        return PaymentView;
    })();
    /*
     "Receipt" step.
     */
    ReceiptLineView = (function() {
        __extends(ReceiptLineView, Backbone.View);
        function ReceiptLineView() {
            ReceiptLineView.__super__.constructor.apply(this, arguments);
        }

        ReceiptLineView.prototype.tagName = 'tr';
        ReceiptLineView.prototype.className = 'receiptline';
        ReceiptLineView.prototype.template = qweb_template('pos-receiptline-template');
        ReceiptLineView.prototype.initialize = function() {
            return this.model.bind('change', this.render, this);
        };
        ReceiptLineView.prototype.render = function() {
            return $(this.el).html(this.template(this.model.toJSON()));
        };
        return ReceiptLineView;
    })();
    ReceiptView = (function() {
        __extends(ReceiptView, Backbone.View);
        function ReceiptView() {
            ReceiptView.__super__.constructor.apply(this, arguments);
        }

        ReceiptView.prototype.initialize = function(options) {
            this.shop = options.shop;
            this.shop.bind('change:selectedOrder', this.changeSelectedOrder, this);
            this.bindOrderLineEvents();
            return this.bindPaymentLineEvents();
        };
        ReceiptView.prototype.events = {
            "click button#pos-finish-order": "finishOrder"
        };
        ReceiptView.prototype.finishOrder = function() {
            $('.step-screen').hide();
            $('#products-screen').show();
            this.shop.get('selectedOrder').destroy();
        };
        ReceiptView.prototype.receiptLineList = function() {
            return $(this.el).find('#receiptlines');
        };
        ReceiptView.prototype.bindOrderLineEvents = function() {
            this.currentOrderLines = (this.shop.get('selectedOrder')).get('orderLines');
            this.currentOrderLines.bind('add', this.addReceiptLine, this);
            this.currentOrderLines.bind('change', this.render, this);
            return this.currentOrderLines.bind('remove', this.render, this);
        };
        ReceiptView.prototype.bindPaymentLineEvents = function() {
            this.currentPaymentLines = (this.shop.get('selectedOrder')).get('paymentLines');
            return this.currentPaymentLines.bind('all', this.updateReceiptSummary, this);
        };
        ReceiptView.prototype.changeSelectedOrder = function() {
            this.currentOrderLines.unbind();
            this.bindOrderLineEvents();
            this.currentPaymentLines.unbind();
            this.bindPaymentLineEvents();
            return this.render();
        };
        ReceiptView.prototype.addReceiptLine = function(newOrderItem) {
            this.receiptLineList().append((new ReceiptLineView({
                    model: newOrderItem
                })).render());
            return this.updateReceiptSummary();
        };
        ReceiptView.prototype.render = function() {
            this.receiptLineList().empty();
            this.currentOrderLines.each(__bind( function(orderItem) {
                return this.receiptLineList().append((new ReceiptLineView({
                        model: orderItem
                    })).render());
            }, this));
            return this.updateReceiptSummary();
        };
        ReceiptView.prototype.updateReceiptSummary = function() {
            var change, currentOrder, tax, total;
            currentOrder = this.shop.get('selectedOrder');
            total = currentOrder.getTotal();
            tax = currentOrder.getTax();
            change = currentOrder.getPaidTotal() - total;
            $('#receipt-summary-tax').html(tax.toFixed(2));
            $('#receipt-summary-total').html(total.toFixed(2));
            return $('#receipt-summary-change').html(change.toFixed(2));
        };
        return ReceiptView;
    })();
    OrderButtonView = (function() {
        __extends(OrderButtonView, Backbone.View);
        function OrderButtonView() {
            OrderButtonView.__super__.constructor.apply(this, arguments);
        }

        OrderButtonView.prototype.tagName = 'li';
        OrderButtonView.prototype.className = 'order-selector-button';
        OrderButtonView.prototype.template = qweb_template('pos-order-selector-button-template');
        OrderButtonView.prototype.initialize = function(options) {
            this.order = options.order;
            this.shop = options.shop;
            this.order.bind('destroy', __bind( function() {
                return $(this.el).remove();
            }, this));
            return this.shop.bind('change:selectedOrder', __bind( function(shop) {
                var selectedOrder;
                selectedOrder = shop.get('selectedOrder');
                if (this.order === selectedOrder) {
                    return this.setButtonSelected();
                }
            }, this));
        };
        OrderButtonView.prototype.events = {
            'click button.select-order': 'selectOrder',
            'click button.close-order': 'closeOrder'
        };
        OrderButtonView.prototype.selectOrder = function(event) {
            return this.shop.set({
                selectedOrder: this.order
            });
        };
        OrderButtonView.prototype.setButtonSelected = function() {
            $('.selected-order').removeClass('selected-order');
            return $(this.el).addClass('selected-order');
        };
        OrderButtonView.prototype.closeOrder = function(event) {
            return this.order.destroy();
        };
        OrderButtonView.prototype.render = function() {
            return $(this.el).html(this.template(this.order.toJSON()));
        };
        return OrderButtonView;
    })();
    ShopView = (function() {
        __extends(ShopView, Backbone.View);
        function ShopView() {
            ShopView.__super__.constructor.apply(this, arguments);
        }

        ShopView.prototype.initialize = function(options) {
            this.shop = options.shop;
            (this.shop.get('orders')).bind('add', this.orderAdded, this);
            (this.shop.get('orders')).add(new Order);
            this.numpadState = new NumpadState({
                shop: this.shop
            });
            this.productListView = new ProductListView({
                shop: this.shop
            });
            this.paypadView = new PaypadWidget(null, 'paypad', {
                shop: this.shop
            });
            this.paypadView.render_element();
            this.paypadView.start();
            this.orderView = new OrderWidget(null, 'current-order-content', {
                shop: this.shop,
                numpadState: this.numpadState
            });
            this.orderView.start();
            this.paymentView = new PaymentView({
                shop: this.shop,
                el: $('#payment-screen')
            });
            this.receiptView = new ReceiptView({
                shop: this.shop,
                el: $('#receipt-screen')
            });
            this.numpadView = new NumpadWidget(null, 'numpad', {
                state: this.numpadState
            });
            this.numpadView.start();
            this.stepsView = new StepsWidget(null, 'steps');
            this.stepsView.start();
        };
        ShopView.prototype.events = {
            'click button#neworder-button': 'createNewOrder'
        };
        ShopView.prototype.createNewOrder = function() {
            var newOrder;
            newOrder = new Order;
            (this.shop.get('orders')).add(newOrder);
            return this.shop.set({
                selectedOrder: newOrder
            });
        };
        ShopView.prototype.orderAdded = function(newOrder) {
            var newOrderButton;
            newOrderButton = new OrderButtonView({
                order: newOrder,
                shop: this.shop
            });
            $('#orders').append(newOrderButton.render());
            return newOrderButton.selectOrder();
        };
        return ShopView;
    })();
    App = (function() {
        function App($element) {
            this.initialize($element);
        }

        App.prototype.initialize = function($element) {
            this.shop = new Shop;
            this.shopView = new ShopView({
                shop: this.shop,
                el: $element
            });
            this.categoryView = new CategoryView;
            this.categoryView.bind("changeCategory", this.category, this);
            this.category();
            return this.categoryView;
        };
        App.prototype.category = function(id) {
            var c, products;
            if (id == null) {
                id = 0;
            }
            c = pos.categories[id];
            $('#products-screen').html(this.categoryView.render(c.ancestors, c.children));
            this.categoryView.delegateEvents();
            products = pos.store.get('product.product').filter( function(p) {
                var _ref;
                return _ref = p.pos_categ_id[0], __indexOf.call(c.subtree, _ref) >= 0;
            });
            (this.shop.get('products')).reset(products);
            var self = this;
            $('.searchbox input').keyup(function() {
                var m, s;
                s = $(this).val().toLowerCase();
                if (s) {
                    m = products.filter( function(p) {
                        return p.name.toLowerCase().indexOf(s);
                    });
                    $('.search-clear').fadeIn();
                } else {
                    m = products;
                    $('.search-clear').fadeOut();
                }
                return (self.shop.get('products')).reset(m);
            });
            return $('.search-clear').click( function() {
                (this.shop.get('products')).reset(products);
                $('.searchbox input').val('').focus();
                return $('.search-clear').fadeOut();
            });
        };
        return App;
    })();

    db.web.client_actions.add('pos.ui', 'db.point_of_sale.PointOfSale');
    db.point_of_sale.PointOfSale = db.web.Widget.extend({
        template: "PointOfSale",
        start: function() {
            var self = this;
            this.$element.find("#loggedas button").click(function() {
                self.stop();
            });

            if (pos)
                throw "It is not possible to instantiate multiple instances "+
                    "of the point of sale at the same time.";
            pos = new Pos(this.session);

            this.$element.find('#steps').buttonset();

            return pos.ready.then( function() {
                pos.app = new App(self.$element);
            });
        },
        stop: function() {
            pos = undefined;
            this._super();
        }
    });
}
