/*---------------------------------------------------------
 * OpenERP Web Mobile Form View
 *---------------------------------------------------------*/

openerp.web_mobile.form_mobile = function (openerp) {

openerp.web_mobile.FormView = openerp.web.Widget.extend({
    init: function(session, element_id, list_id, action, head_title, resmodel, viewid) {
        this._super(session, element_id);
        this.list_id = list_id;
        this.action = action;
        this.head_title = head_title;
        this.resmodel = resmodel;
        this.viewid = viewid;

    },
    start: function() {
        var self = this;
        var id = this.list_id;

        var model = this.action.res_model || this.resmodel;
        if(this.action){
            var view_id = this.action.views[1][0];
        }else{
            var view_id = this.viewid;
        }

        this.dataset = new openerp.web.DataSetSearch(this, model, null, null);
        var context = new openerp.web.CompoundContext(this.dataset.get_context());
        this.dataset.read_slice([],{}, function (result) {

            for (var i = 0; i < result.length; i++) {
                if (result[i].id == id) {
                    var data = result[i];
                }
            }
            self.rpc("/web/view/load", {"model": model, "view_id": view_id, "view_type": "form", context: context}, function (result) {
                var fields = result.fields;
                var view_fields = result.arch.children;
                var get_fields = self.get_fields(view_fields);
                var selection = new openerp.web_mobile.Selection();

                for (var j = 0; j < view_fields.length; j++) {
                    if (view_fields[j].tag == 'notebook') {
                        var notebooks = view_fields[j];
                    }
                }
                self.$element.html(QWeb.render("FormView", {'get_fields': get_fields, 'notebooks': notebooks || false, 'fields' : fields, 'values' : data ,'temp_flag':'1'}));

				for(var i=0;i<get_fields.length;i++)
				  {
					if(get_fields[i].attrs.widget=="progressbar")
						{
							$("#progress").progressbar({value:data[get_fields[i].attrs.name]})
						}
				  }
                    self.$element.find("[data-role=header]").find('h1').html(self.head_title);
                    self.$element.find("[data-role=header]").find('#home').click(function(){
                        $.mobile.changePage("#oe_menu", "slide", false, true);
                    });
                    self.$element.find("[data-role=footer]").find('#shrotcuts').click(function(){
                        if(!$('#oe_shortcuts').html().length){
                            this.shortcuts = new openerp.web_mobile.Shortcuts(self, "oe_shortcuts");
                            this.shortcuts.start();
                        }
                        else{
                            $.mobile.changePage("#oe_shortcuts", "slide", false, true);
                        }
                    });
                    self.$element.find("[data-role=footer]").find('#preference').click(function(){
                        if(!$('#oe_options').html().length){
                            this.options = new openerp.web_mobile.Options(self, "oe_options");
                            this.options.start();
                        }
                        else{
                            $.mobile.changePage("#oe_options", "slide", false, true);
                        }
                    });
                    self.$element.find('#formbutton').click(function(){
                        var head = $(this).prev().find('select').find("option:selected").text();
                        var selected_id = $(this).prev().find('select').val();
                        var select_model = $(this).prev().find('select').attr('for');
                        if(selected_id!="false"){
                            if(!$('[id^="oe_form_'+selected_id+select_model+'"]').html()){
                                $('<div id="oe_form_'+selected_id+select_model+'" data-role="page" data-url="oe_form_'+selected_id+select_model+'"> </div>').appendTo('#moe');
                                    this.formview = new openerp.web_mobile.FormView(self, "oe_form_"+selected_id+select_model, selected_id, '', head, select_model, false);
                                    this.formview.start();
                            }else{
                                $.mobile.changePage('#oe_form_'+selected_id+select_model, "slide", false, true);
                            }
                        }
                    });
                    self.$element.find('[data-role=collapsible-set]').find('[data-role=collapsible]').each(function(i){

                        for (var k = 0; k < notebooks.children.length; k++) {
                            if (notebooks.children[k].attrs.string == $(this).attr('id')) {
                                get_fields = self.get_fields(notebooks.children[k].children);
                                for (var i = 0; i < get_fields.length; i++) {
                                    if (fields[get_fields[i].attrs.name].type == 'one2many'){
                                        self.relational_fields = get_fields[i].attrs.name;
                                        if(fields[get_fields[i].attrs.name].views.form){
                                            var get_fields_test = self.get_fields(fields[get_fields[i].attrs.name].views.form.arch.children);
                                            var fields_test = fields[get_fields[i].attrs.name]['views'].form.fields;
                                            var notebook=fields[get_fields[i].attrs.name].views.form.arch;
                                        }
                                    }
                                }
                            }

                            if(notebook){
                                $(this).find('p').html(QWeb.render("FormView", {'get_fields': get_fields,'fields' : result.fields, 'values' : data,'til': notebook.attrs.string }));
                            }else{
                                $(this).find('p').html(QWeb.render("FormView", {'get_fields': get_fields,'fields' : result.fields, 'values' : data }));
                            }
                            $(this).find('p').find('#formbutton').click(function(){
                                var head = $(this).prev().find('select').find("option:selected").text();
                                var selected_id = $(this).prev().find('select').val();
                                var select_model = $(this).prev().find('select').attr('for');
                                if(selected_id!="false"){
                                    if(!$('[id^="oe_form_'+selected_id+select_model+'"]').html()){
                                        $('<div id="oe_form_'+selected_id+select_model+'" data-role="page" data-url="oe_form_'+selected_id+select_model+'"> </div>').appendTo('#moe');
                                        this.formview = new openerp.web_mobile.FormView(self, "oe_form_"+selected_id+select_model, selected_id, '', head, select_model, false);
                                        this.formview.start();
                                    }else{
                                        $.mobile.changePage('#oe_form_'+selected_id+select_model, "slide", false, true);
                                    }
                                }
                            });

                        }
                    });
                    self.$element.find('[data-role=collapsible-set]').find('[data-role=collapsible]').find('p').find('[data-role=content]').find('ul').find('li').click(function(ev){
                        ev.preventDefault();
                        ev.stopPropagation();
                        var latid,lastid;
                        $(this).parents().each(function(){
                            latid = $(this).attr('id');
                            self.$element.find('[data-role=collapsible-set]').find('[data-role=collapsible]').each(function(){
                                if(latid==$(this).attr('id')){
                                    lastid = $(this).attr('id');
                                }
                            });
                        });
                        var relational = $(this).attr('for');
                        if(result.fields[relational]){

                            var head = $.trim($(this).text());
                            var dataset = new openerp.web.DataSetStatic(self, result.fields[relational].relation, result.fields[relational].context);
                            dataset.domain=[['id', 'in', data[relational]]];
                            dataset.name_search('', dataset.domain, 'in',false ,function(res){
                                for(var i=0;i<res.length;i++){
                                    var splited_data = res[i][1].split(',');
                                    res[i][1] = splited_data[0];
                                }
                                if(!$('[id^="oe_list_'+relational+'_'+self.element_id+'"]').html()){
                                    $('<div id="oe_list_'+relational+'_'+self.element_id+'" data-role="page" data-url="oe_list_'+relational+'_'+self.element_id+'"> </div>').appendTo('#moe');
                                    $('[id^="oe_list_'+relational+'_'+self.element_id+'"]').html(QWeb.render("ListView", {'records' : res}));
                                    $('[id^="oe_list_'+relational+'_'+self.element_id+'"]').find("[data-role=header]").find('h1').html(head);
                                    $('[id^="oe_list_'+relational+'_'+self.element_id+'"]').find("[data-role=header]").find('#home').click(function(){
                                        $.mobile.changePage("#oe_menu", "slide", false, true);
                                    });
                                    $('[id^="oe_list_'+relational+'_'+self.element_id+'"]').find("[data-role=footer]").find('#shrotcuts').click(function(){
                                        if(!$('#oe_shortcuts').html().length){
                                            this.shortcuts = new openerp.web_mobile.Shortcuts(self, "oe_shortcuts");
                                            this.shortcuts.start();
                                        }
                                        else{
                                            $.mobile.changePage("#oe_shortcuts", "slide", false, true);
                                        }
                                    });
                                    $('[id^="oe_list_'+relational+'_'+self.element_id+'"]').find("[data-role=footer]").find('#preference').click(function(){
                                        if(!$('#oe_options').html().length){
                                            this.options = new openerp.web_mobile.Options(self, "oe_options");
                                            this.options.start();
                                        }
                                        else{
                                            $.mobile.changePage("#oe_options", "slide", false, true);
                                        }
                                    });
                                    $('[id^="oe_list_'+relational+'_'+self.element_id+'"]').find("a#list-id").click(function(ev){
                                        ev.preventDefault();
                                        ev.stopPropagation();
                                        var head_title = $(this).text();
                                        var listid = $(ev.currentTarget).data('id');
                                        dataset = new openerp.web.DataSetSearch(self, dataset.model, null, null);
                                        dataset.read_slice([],{}, function (result_relational) {
                                            for (var i = 0; i < result_relational.length; i++) {
                                                if (result_relational[i].id == listid) {
                                                    var data_relational = result_relational[i];
                                                }
                                            }
                                            if(!$('[id^="oe_form_'+listid+result.fields[relational].relation+'"]').html()){
                                                $('<div id="oe_form_'+listid+result.fields[relational].relation+'" data-role="page" data-url="oe_form_'+listid+result.fields[relational].relation+'"> </div>').appendTo('#moe');
                                                for (var k = 0; k < notebooks.children.length; k++) {
                                                    if (notebooks.children[k].attrs.string == lastid) {
                                                        get_fields = self.get_fields(notebooks.children[k].children);
                                                        for (var i = 0; i < get_fields.length; i++) {
                                                            if (fields[get_fields[i].attrs.name].type == 'one2many'){
                                                                self.relational_fields = get_fields[i].attrs.name;
                                                                if(fields[get_fields[i].attrs.name].views.form){
                                                                    var get_fields_test = self.get_fields(fields[get_fields[i].attrs.name].views.form.arch.children);
                                                                    var fields_test = fields[get_fields[i].attrs.name]['views'].form.fields;
                                                                    var notebook=fields[get_fields[i].attrs.name].views.form.arch;
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                                $('[id^="oe_form_'+listid+result.fields[relational].relation+'"]').html(QWeb.render("FormView", {'get_fields': get_fields_test, 'notebooks': false, 'fields' : fields_test, 'values' : data_relational, 'temp_flag':'1' }));

                                                $('[id^="oe_form_'+listid+result.fields[relational].relation+'"]').find("[data-role=header]").find('h1').html(head_title);
                                                $('[id^="oe_form_'+listid+result.fields[relational].relation+'"]').find("[data-role=header]").find('#home').click(function(){
                                                    $.mobile.changePage("#oe_menu", "slide", false, true);
                                                });
                                                $('[id^="oe_form_'+listid+result.fields[relational].relation+'"]').find("[data-role=footer]").find('#shrotcuts').click(function(){
                                                    if(!$('#oe_shortcuts').html().length){
                                                        this.shortcuts = new openerp.web_mobile.Shortcuts(self, "oe_shortcuts");
                                                        this.shortcuts.start();
                                                    }
                                                    else{
                                                        $.mobile.changePage("#oe_shortcuts", "slide", false, true);
                                                    }
                                                });
                                                $('[id^="oe_form_'+listid+result.fields[relational].relation+'"]').find("[data-role=footer]").find('#preference').click(function(){
                                                    if(!$('#oe_options').html().length){
                                                        this.options = new openerp.web_mobile.Options(self, "oe_options");
                                                        this.options.start();
                                                    }
                                                    else{
                                                        $.mobile.changePage("#oe_options", "slide", false, true);
                                                    }
                                                });
                                                $('[id^="oe_form_'+listid+result.fields[relational].relation+'"]').find('#formbutton').click(function(){
                                                    var head = $(this).prev().find('select').find("option:selected").text();
                                                    var selected_id = $(this).prev().find('select').val();
                                                    var select_model = $(this).prev().find('select').attr('for');
                                                    if(selected_id!="false"){
                                                        if(!$('[id^="oe_form_'+selected_id+select_model+'"]').html()){
                                                            $('<div id="oe_form_'+selected_id+select_model+'" data-role="page" data-url="oe_form_'+selected_id+select_model+'"> </div>').appendTo('#moe');
                                                            this.formview = new openerp.web_mobile.FormView(self, "oe_form_"+selected_id+select_model, selected_id, '', head, select_model, false);
                                                            this.formview.start();
                                                        }else{
                                                            $.mobile.changePage('#oe_form_'+selected_id+select_model, "slide", false, true);
                                                        }
                                                    }
                                                });
                                                $.mobile.changePage('#oe_form_'+listid+result.fields[relational].relation, "slide", false, true);
                                            }else{
                                                $.mobile.changePage('#oe_form_'+listid+result.fields[relational].relation, "slide", false, true);
                                            }
                                        });
                                    });
                                    $.mobile.changePage("#oe_list_"+relational+"_"+self.element_id, "slide", false, true);
                                }else{
                                    $.mobile.changePage("#oe_list_"+relational+"_"+self.element_id, "slide", false, true);
                                }
                            });
                        }
                    });
                    $.mobile.changePage("#"+self.element_id, "slide", false, true);
                });
        });
    },
    get_fields: function(view_fields, fields) {
        this.fields = fields || [];
        for (var i=0; i < view_fields.length; i++){
            if (view_fields[i].tag == 'field') {
                this.fields.push(view_fields[i]);
            }
            if (view_fields[i].tag == 'group') {
                this.get_fields(view_fields[i].children, this.fields);
            }
        }
        return this.fields;
    }
});
};
