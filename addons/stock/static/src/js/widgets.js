
function openerp_picking_widgets(instance){

    var module = instance.stock;
    var _t     = instance.web._t;
    var QWeb   = instance.web.qweb;

    // This widget makes sure that the scaling is disabled on mobile devices.
    // Widgets that want to display fullscreen on mobile phone need to extend this
    // widget.

    module.MobileWidget = instance.web.Widget.extend({
        start: function(){
            if(!$('#oe-mobilewidget-viewport').length){
                $('head').append('<meta id="oe-mobilewidget-viewport" name="viewport" content="initial-scale=1.0; maximum-scale=1.0; user-scalable=0;">');
            }
            return this._super();
        },
        destroy: function(){
            $('#oe-mobilewidget-viewport').remove();
            return this._super();
        },
    });

    module.PickingEditorWidget = instance.web.Widget.extend({
        template: 'PickingEditorWidget',
        init: function(parent,options){
            this._super(parent,options);
        },
        get_rows: function(){
            var model = this.getParent();
            var rows = [];

            _.each( model.movelines, function(moveline){
                rows.push({
                    cols: { product: moveline.product_id[1],
                            qty: moveline.product_uom_qty,
                            rem: moveline.remaining_qty,
                            uom: moveline.product_uom[1],
                            loc: moveline.location_id[1],
                            id:  moveline.product_id[0],
                    },
                    classes: (moveline.qty_remaining < 0 ? 'oe_invalid' : '')
                });
            });
            
            return rows;
        },
        renderElement: function(){
            var self = this;
            this._super();
            this.$('.js_pack_scan').click(function(){
                var id = parseInt($(this).attr('op-id'));
                console.log('Id:',id);
                self.getParent().scan_product_id(id);
            });

            //remove navigtion bar from default openerp GUI
            $('td.navbar').html('<div></div>');
        },
    });

    module.PackageEditorWidget = instance.web.Widget.extend({
        template: 'PackageEditorWidget',
        get_header: function(){
            var model = this.getParent();
            var current_package = model.get_selected_package();
            return current_package ? 'Operations for Package: ' + current_package.name : 'Current Operations';
        },
        get_rows: function(){
            var model = this.getParent();
            var rows = [];
            var ops = model.get_current_operations();
            _.each( ops, function(op){
                rows.push({
                    cols: {
                        product: (op.package_id ? op.package_id[1] : op.product_id[1]) + (op.lot_id ? ' Lot: ' + op.lot_id[1] : ''),
                        uom: op.product_uom ? product_uom[1] : '',
                        qty: op.product_qty,
                    },
                    classes: 'js_pack_op '+ (op.id === model.get_selected_operation() ? 'oe_selected' : ''),
                    att_op_id: op.id,
                });
            });

            return rows;
        },
        renderElement: function(){
            var self = this;
            this._super();
            var model = this.getParent();
            this.$('.js_pack_op').click(function(){
                if (!this.classList.contains('oe_selected')){
                    self.$('.js_pack_op').removeClass('oe_selected');
                    $(this).addClass('oe_selected');
                    model.set_selected_operation(parseInt($(this).attr('op-id')));
                } else {
                    $(this).removeClass('oe_selected');
                    model.set_selected_operation(null);
                };
            });
        },
    });

    module.PackageSelectorWidget = instance.web.Widget.extend({
        template: 'PackageSelectorWidget',
        get_header: function(){
            return this._header || 'Packages:';
        },
        get_rows: function(){
            var model = this.getParent();
            var current_package = model.get_selected_package();
            var rows = [];
            _.each( model.packages, function(pack){
                rows.push({
                    cols:{ pack: pack.name},
                    id: pack.id,
                    classes: pack === current_package ? ' oe_selected' : '' ,
                });
            });
            return rows;
        },
        renderElement: function(){
            this._super();
            var model = this.getParent();
            this.$('.js_pack_row').each(function(){
                var pack_id = parseInt($(this).attr('pack-id'));
                $('.js_pack_print', this).click(function(){ model.print_package(pack_id); });
                $('.js_pack_plus', this).click(function(){ model.copy_package_op(pack_id); });
                $('.js_pack_minus', this).click(function(){ model.delete_package_op(pack_id); });
                $('.js_pack_select', this).click(function(){ 
                    if(model.get_selected_package() && model.get_selected_package().id === pack_id){
                        model.deselect_package();
                    }else{
                        model.select_package(pack_id); 
                    }
                });
            });
        },
    });

    module.PickingMenuWidget = module.MobileWidget.extend({
        template: 'PickingMenuWidget',
        init: function(parent, params){
            this._super(parent,params);
            var self = this;

            this.picking_types = [];
            this.loaded = this.load();
            this.scanning_type = 0;
            this.barcode_scanner = new module.BarcodeScanner();
            this.pickings_by_type = {};
            this.pickings_by_id = {};
            this.picking_search_string = "";
            
        },
        load: function(){
            var self = this;
            return new instance.web.Model('stock.picking.type').get_func('search_read')([],[])
                .then(function(types){
                    self.picking_types = types;
                    
                    for(var i = 0; i < types.length; i++){
                        self.pickings_by_type[types[i].id] = [];
                    }
                    self.pickings_by_type[0] = [];

                    return new instance.web.Model('stock.picking').call('search_read',[ [['state','in', ['assigned', 'partially_available']]], [] ], {context: new instance.web.CompoundContext()});
                                                                  
                }).then(function(pickings){
                    self.pickings = pickings;

                    for(var i = 0; i < pickings.length; i++){
                        var picking = pickings[i];
                        self.pickings_by_type[picking.picking_type_id[0]].push(picking);
                        self.pickings_by_id[picking.id] = picking;
                        self.picking_search_string += '' + picking.id + ':' + picking.name.toUpperCase() + '\n'
                    }

                });
        },
        renderElement: function(){
            this._super();
            var self = this;
            this.$('.js_pick_quit').click(function(){ self.quit(); });
            this.$('.js_pick_scan').click(function(){ self.scan_picking($(this).data('id')); });
            this.$('.js_pick_last').click(function(){ self.goto_last_picking_of_type($(this).data('id')); });
            this.$('.oe_searchbox input').keyup(function(event){
                self.on_searchbox($(this).val());
            });
            //remove navigtion bar from default openerp GUI
            $('td.navbar').html('<div></div>');
        },
        start: function(){
            this._super();
            var self = this;
            this.barcode_scanner.connect(function(barcode){
                self.on_scan(barcode);
            });
            this.loaded.then(function(){
                self.renderElement();
            });
        },
        goto_picking: function(picking_id){
            this.do_action({
                type:   'ir.actions.client',
                tag:    'stock.ui',
                target: 'current',
                context: { picking_id: picking_id },
            },{
                clear_breadcrumbs: true,
            });
        },
        goto_last_picking_of_type: function(type_id){
            this.do_action({
                type:   'ir.actions.client',
                tag:    'stock.ui',
                target: 'current',
                context: { active_id: type_id },
            },{
                clear_breadcrumbs: true,
            });
        },
        search_picking: function(barcode){
            //TODO don't crash if a not supported char is given
            var re = RegExp("([0-9]+):.*?"+barcode.toUpperCase(),"gi");
            var results = [];
            for(var i = 0; i < 100; i++){
                r = re.exec(this.picking_search_string);
                if(r){
                    var picking = this.pickings_by_id[Number(r[1])];
                    if(picking){
                        results.push(picking);
                    }
                }else{
                    break;
                }
            }
            return results;
        },
        on_scan: function(barcode){
            var self = this;

            for(var i = 0, len = this.pickings.length; i < len; i++){
                var picking = this.pickings[i];
                if(picking.name.toUpperCase() === $.trim(barcode.toUpperCase())){
                    this.goto_picking(picking.id);
                    break;
                }
            }
            this.$('.oe_picking_not_found').removeClass('oe_hidden');

            clearTimeout(this.picking_not_found_timeout);
            this.picking_not_found_timeout = setTimeout(function(){
                self.$('.oe_picking_not_found').addClass('oe_hidden');
            },2000);

        },
        on_searchbox: function(query){
            var self = this;

            clearTimeout(this.searchbox_timeout);
            this.searchbox_timout = setTimeout(function(){
                if(query){
                    self.$('.oe_picking_not_found').addClass('oe_hidden');
                    self.$('.oe_picking_categories').addClass('oe_hidden');
                    self.$('.oe_picking_search_results').html(
                        QWeb.render('PickingSearchResults',{results:self.search_picking(query)})
                    );
                    self.$('.oe_picking_search_results .oe_picking').click(function(){
                        self.goto_picking($(this).data('id'));
                    });
                    self.$('.oe_picking_search_results').removeClass('oe_hidden');
                }else{
                    self.$('.oe_picking_categories').removeClass('oe_hidden');
                    self.$('.oe_picking_search_results').addClass('oe_hidden');
                }
            },100);
        },
        quit: function(){
            instance.webclient.set_content_full_screen(false);
            window.location = '/'; // FIXME Ask niv how to do it correctly
        },
        destroy: function(){
            this._super();
            this.barcode_scanner.disconnect();
            instance.webclient.set_content_full_screen(false);
        },
    });
    openerp.web.client_actions.add('stock.menu', 'instance.stock.PickingMenuWidget');

    module.PickingMainWidget = module.MobileWidget.extend({
        template: 'PickingMainWidget',
        init: function(parent,params){
            this._super(parent,params);
            var self = this;

            this.picking = null;
            this.pickings = [];
            this.movelines = null;
            this.operations = null;
            this.selected_operation = { id: null, picking_id: null};
            this.packages = null;
            this.barcode_scanner = new module.BarcodeScanner();
            this.picking_type_id = params.context.active_id || 0;

            if(params.context.picking_id){
                this.loaded =  this.load(params.context.picking_id);
            }else{
                this.loaded =  this.load();
            }

        },

        // load the picking data from the server. If picking_id is undefined, it will take the first picking
        // belonging to the category
        load: function(picking_id){
            var self = this;

       
            function load_picking_list(type_id){
                var pickings = new $.Deferred();
                new instance.web.Model('stock.picking')
                    .call('get_next_picking_for_ui',[{'default_picking_type_id':type_id}])
                    .then(function(picking_ids){
                        if(!picking_ids || picking_ids.length === 0){
                            (new instance.web.Dialog(self,{
                                title: _t('No Picking Available'),
                                buttons: [{ 
                                    text:_t('Ok'), 
                                    click: function(){
                                        self.menu();
                                    }
                                }]
                            }, _t('<p>We could not find a picking to display.</p>'))).open();

                            pickings.reject();
                        }else{
                            self.pickings = picking_ids;
                            pickings.resolve(picking_ids);
                        }
                    });

                return pickings;
            }

            // if we have a specified picking id, we load that one, and we load the picking of the same type as the active list
            if( picking_id ){
                var loaded_picking = new instance.web.Model('stock.picking')
                    .call('read',[[picking_id], [], new instance.web.CompoundContext()])
                    .then(function(picking){
                        self.picking = picking[0];

                        return load_picking_list(self.picking.picking_type_id[0]);
                    });
            }else{
                // if we don't have a specified picking id, we load the pickings belong to the specified type, and then we take 
                // the first one of that list as the active picking
                var loaded_picking = new $.Deferred();
                load_picking_list(self.picking_type_id)
                    .then(function(){
                        return new instance.web.Model('stock.picking').call('read',[self.pickings[0],[], new instance.web.CompoundContext()]);
                    })
                    .then(function(picking){
                        self.picking = picking;
                        self.picking_type_id = picking.picking_type_id[0];
                        loaded_picking.resolve();
                    });
            }

            return loaded_picking.then(function(){

                    return new instance.web.Model('stock.move').call('read',[self.picking.move_lines, [], new instance.web.CompoundContext()]);
                }).then(function(movelines){
                    self.movelines = movelines;

                    return new instance.web.Model('stock.pack.operation').call('read',[self.picking.pack_operation_ids, [], new instance.web.CompoundContext()]);
                }).then(function(operations){
                    self.operations = operations;
                    var package_ids = [];

                    for(var i = 0; i < operations.length; i++){
                        if(!_.contains(package_ids,operations[i].result_package_id[0])){
                            if (operations[i].result_package_id[0]){
                                package_ids.push(operations[i].result_package_id[0]);
                            }
                        }
                    }
                    return new instance.web.Model('stock.quant.package').call('read',[package_ids, [], new instance.web.CompoundContext()]);
                }).then(function(packages){
                    self.packages = packages;
                });

        },
        start: function(){
            this._super();
            var self = this;
            instance.webclient.set_content_full_screen(true);
            this.connect_numpad();
            this.barcode_scanner.connect(function(ean){
                self.scan(ean);
            });
            

            this.$('.js_pick_quit').click(function(){ self.quit(); });
            this.$('.js_pick_pack').click(function(){ self.pack(); });
            this.$('.js_pick_done').click(function(){ self.done(); });
            this.$('.js_pick_print').click(function(){ self.print_picking(); });
            this.$('.js_pick_prev').click(function(){ self.picking_prev(); });
            this.$('.js_pick_next').click(function(){ self.picking_next(); });
            this.$('.js_pick_menu').click(function(){ self.menu(); });

            this.hotkey_handler = function(event){
                if(event.keyCode === 37 ){  // Left Arrow
                    self.picking_prev();
                }else if(event.keyCode === 39){ // Right Arrow
                    self.picking_next();
                }
            };

            $('body').on('keyup',this.hotkey_handler);

            $.when(this.loaded).done(function(){
                self.picking_editor = new module.PickingEditorWidget(self);
                self.picking_editor.replace(self.$('.oe_placeholder_picking_editor'));

                self.package_editor = new module.PackageEditorWidget(self);
                self.package_editor.replace(self.$('.oe_placeholder_package_editor'));

                self.package_selector = new module.PackageSelectorWidget(self);
                self.package_selector.replace(self.$('.oe_placeholder_package_selector'));
                
                if( self.picking.id === self.pickings[0]){
                    self.$('.js_pick_prev').addClass('oe_disabled');
                }else{
                    self.$('.js_pick_prev').removeClass('oe_disabled');
                }
                
                if( self.picking.id === self.pickings[self.pickings.length-1] ){
                    self.$('.js_pick_next').addClass('oe_disabled');
                }else{
                    self.$('.js_pick_next').removeClass('oe_disabled');
                }

                self.$('.oe_pick_app_header').text(self.get_header());

            }).fail(function(error) {console.log(error);});

        },
        // reloads the data from the provided picking and refresh the ui. 
        // (if no picking_id is provided, gets the first picking in the db)
        refresh_ui: function(picking_id){
            var self = this;
            return this.load(picking_id)
                .then(function(){ 
                    self.picking_editor.renderElement();
                    self.package_editor.renderElement();
                    self.package_selector.renderElement();

                    if( self.picking.id === self.pickings[0]){
                        self.$('.js_pick_prev').addClass('oe_disabled');
                    }else{
                        self.$('.js_pick_prev').removeClass('oe_disabled');
                    }
                    
                    if( self.picking.id === self.pickings[self.pickings.length-1] ){
                        self.$('.js_pick_next').addClass('oe_disabled');
                    }else{
                        self.$('.js_pick_next').removeClass('oe_disabled');
                    }
                    self.$('.oe_pick_app_header').text(self.get_header());
                });
        },
        get_header: function(){
            if(this.picking){
                return this.picking.name;
            }else{
                return '';
            }
        },
        menu: function(){
            this.do_action({
                type:   'ir.actions.client',
                tag:    'stock.menu',
                target: 'current',
            },{
                clear_breadcrumbs: true,
            });

        },
        scan: function(ean){ //scans a barcode, sends it to the server, then reload the ui
            var self = this;
            new instance.web.Model('stock.picking')
                .call('process_barcode_from_ui', [self.picking.id, ean])
                .then(function(){
                    self.reset_selected_operation();
                    return self.refresh_ui(self.picking.id);
                });
        },
        scan_product_id: function(product_id){ //performs the same operation as a scan, but with product id instead
            var self = this;
            new instance.web.Model('stock.picking')
                .call('process_product_id_from_ui', [self.picking.id, product_id])
                .then(function(){
                    self.reset_selected_operation();
                    return self.refresh_ui(self.picking.id);
                });
        },
        pack: function(){
            var self = this;
            new instance.web.Model('stock.picking')
                .call('action_pack',[[[self.picking.id]]])
                .then(function(){
                    instance.session.user_context.current_package_id = false;

                    return self.refresh_ui(self.picking.id);
                });
        },
        done: function(){
            var self = this;
            new instance.web.Model('stock.picking')
                .call('action_done_from_ui',[self.picking.id, {'default_picking_type_id': self.picking_type_id}])
                .then(function(new_picking_ids){
                    if (new_picking_ids){
                        return self.refresh_ui(new_picking_ids[0]);
                    }
                    else {
                        return 0;
                    }
                });
        },
        print_package: function(package_id){
            var self = this;
            new instance.web.Model('stock.quant.package')
                .call('action_print',[[package_id]])
                .then(function(action){
                    return self.do_action(action);
                });
        },
        print_picking: function(){
            var self = this;
            new instance.web.Model('stock.picking.type').call('read', [[self.picking_type_id], ['code'], new instance.web.CompoundContext()])
                .then(function(pick_type){
                    if (pick_type[0]['code'] == 'outgoing'){
                        new instance.web.Model('stock.picking').call('do_print_delivery',[[self.picking.id]])
                           .then(function(action){
                                return self.do_action(action);
                           });
                    }
                    else {
                        new instance.web.Model('stock.picking').call('do_print_picking',[[self.picking.id]])
                           .then(function(action){
                                return self.do_action(action);
                           });
                    }
                });
        },
        picking_next: function(){
            for(var i = 0; i < this.pickings.length; i++){
                if(this.pickings[i] === this.picking.id){
                    if(i < this.pickings.length -1){
                        this.refresh_ui(this.pickings[i+1]);
                        return;
                    }
                }
            }
        },
        picking_prev: function(){
            for(var i = 0; i < this.pickings.length; i++){
                if(this.pickings[i] === this.picking.id){
                    if(i > 0){
                        this.refresh_ui(this.pickings[i-1]);
                        return;
                    }
                }
            }
        },
        copy_package_op: function(pack_id){
            var self = this;
            new instance.web.Model('stock.quant.package').call('copy_pack',[pack_id])
                .then(function(){
                    return self.refresh_ui(self.picking.id);
                });
        },
        delete_package_op: function(pack_id){
            var self = this;
            new instance.web.Model('stock.pack.operation').call('search', [[['result_package_id', '=', pack_id]]])
                .then(function(op_ids) {
                    new instance.web.Model('stock.pack.operation').call('unlink', [op_ids])
                        .then(function() {
                            return self.refresh_ui(self.picking.id);
                        });
                });
        },
        deselect_package: function(){
            instance.session.user_context.current_package_id = false;
            this.package_editor.renderElement();
            this.package_selector.renderElement();
        },
        select_package: function(package_id){
            instance.session.user_context.current_package_id = package_id;
            this.package_editor.renderElement();
            this.package_selector.renderElement();
        },
        get_selected_package: function(){
            var current_package;

            _.each( this.packages, function(pack){
                if(pack.id === instance.session.user_context.current_package_id){
                    current_package = pack;
                }
            });

            return current_package;
        },
        get_current_operations: function(){
            var current_package_id = instance.session.user_context.current_package_id;
            var ops = [];
            _.each( this.operations, function(op){
                if(!current_package_id){
                    if(op.result_package_id !== false){
                        return;
                    }
                }else if(op.result_package_id[0] !== current_package_id){
                    return;
                }
                ops.push(op);
            });
            console.log('Current Operations:',ops);
            return ops;
        },
        get_selected_operation: function(){
            if(   this.selected_operation.picking_id === this.picking.id && this.selected_operation.id ){
                return this.selected_operation.id;
            }else{
                return null;
            }
        },
        reset_selected_operation: function(){
            if(this.selected_operation.picking_id === this.picking.id){
                this.selected_operation.id = null;
            }
        },
        set_selected_operation: function(id){
            this.selected_operation.picking_id = this.picking.id;
            this.selected_operation.id = id;
        },
        set_operation_quantity: function(quantity){
            var self = this;
            var op = this.get_selected_operation();
            if( !op ){
                //TODO typing the ean of a product manually ?
                //(scanning the barcode is already handled somewhere else, and i don't know how to differenciate the 2 operations)
                // and the result is that if i uncomment the next line, scanning a product counts it twice
                //self.scan(quantity);
            }

            else {if(typeof quantity === 'number' && quantity >= 0){
                new instance.web.Model('stock.pack.operation')
                    .call('write',[[op],{'product_qty': quantity }])
                    .then(function(){
                        self.refresh_ui(self.picking.id);
                    });
            }}

        },
        connect_numpad: function(){
            var self = this;
            var numpad = [];
            var numpad_timestamp;
            
            this.numpad_handler = function(e){ 
                if(numpad_timestamp + 1500 < new Date().getTime()){
                    numpad = [];
                }
                if(e.keyCode === 27 || e.keyCode === 8){ // ESC or BACKSPACE
                    numpad = [];
                }else if(e.keyCode >= 48 && e.keyCode <= 57){ // NUMPAD NUMBERS
                    numpad.push(e.keyCode - 48);
                }else if(e.keyCode === 13){ // ENTER
                    console.log('enter');
                    if(numpad.length > 0){
                        self.set_operation_quantity(parseInt(numpad.join('')));
                    }
                    numpad = [];
                }else{
                    numpad = [];
                }
                numpad_timestamp = new Date().getTime();
            };
            $('body').on('keypress', this.numpad_handler);
        },
        disconnect_numpad: function(){
            $('body').off('keypress', this.numpad_handler);
        },
        quit: function(){
            this.destroy();
            window.location = '/'; // FIXME Ask niv how to do it correctly
        },
        destroy: function(){
            this._super();
            this.disconnect_numpad();
            this.barcode_scanner.disconnect();
            $('body').off('keyup',this.hotkey_handler);
            instance.webclient.set_content_full_screen(false);
        },
    });
    openerp.web.client_actions.add('stock.ui', 'instance.stock.PickingMainWidget');

    module.BarcodeScanner = instance.web.Class.extend({
        connect: function(callback){
            var code = "";
            var timeStamp = 0;
            var timeout = null;

            this.handler = function(e){
                if(e.which === 13){ //ignore returns
                    return;
                }

                if(timeStamp + 50 < new Date().getTime()){
                    code = "";
                }

                timeStamp = new Date().getTime();
                clearTimeout(timeout);

                code += String.fromCharCode(e.which);

                timeout = setTimeout(function(){
                    if(code.length >= 3){
                        callback(code);
                    }
                    code = "";
                },100);
            };

            $('body').on('keypress', this.handler);

        },
        disconnect: function(){
            $('body').off('keypress', this.handler);
        },
    });

}

openerp.stock = function(openerp) {
    openerp.stock = openerp.stock || {};
    openerp_picking_widgets(openerp);


}

