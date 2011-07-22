openerp.base.export = function(openerp) {
openerp.base.Export = openerp.base.Dialog.extend({

    init: function(parent, dataset, views){
        this._super(parent);
        this.dataset = dataset
        this.views = views
        this.views_id = {};
        for (var key in this.views) {
            this.views_id[key] = this.views[key].view_id
        }
    },

    start: function() {
        var self = this
        self._super(false);
        self.template = 'ExportTreeView';
        self.dialog_title = "Export Data "
        self.open({
                    modal: true,
                    width: '55%',
                    height: 'auto',
                    position: 'top',
                    buttons : {
                        "Close" : function() {
                            self.close();
                          },
                        "Export To File" : function() {
                            self.on_click_export_data();
                          }
                       },
                    close: function(event, ui){ self.close();}
                   });
        this.on_show_exists_export_list();
        jQuery(this.$dialog).removeClass('ui-dialog-content ui-widget-content');
        $('#add_field').click(function(){
            if($("#field-tree-structure tr.ui-selected")){
                var fld = $("#field-tree-structure tr.ui-selected").find('a');
                for (var i=0;i<fld.length; i++){
                    var id = $(fld[i]).attr('id').split("-")[1];
                    var string = $(fld[i]).attr('string');
                    self.add_field(id,string);
                }
                $("#field-tree-structure tr").removeClass("ui-selected");
            }
        });
        $('#remove_field').click(function(){
            $("#fields_list option:selected").remove();
        });
        $('#remove_all_field').click(function(){
            $("#fields_list option").remove();
        });
        $('#export_new_list').click(function(){
            self.on_show_save_list();
        });
        import_comp = $("#import_compat option:selected").val()
        var params = {"import_compat":parseInt(import_comp), "views_id": this.views_id}
        this.rpc("/base/export/get_fields", {"model": this.dataset.model, "params": params}, this.on_show_data);

        $("#import_compat").change(function(){
            $("#fields_list option").remove();
            $("#field-tree-structure").remove();
            import_comp = $("#import_compat option:selected").val();
            if(import_comp){
                var params = {"import_compat":parseInt(import_comp), "views_id": this.views_id}
                self.rpc("/base/export/get_fields", {"model": self.dataset.model, "params": params}, self.on_show_data);
            }
        });
    },

    on_show_exists_export_list: function(){
        var self = this;
        if($("#saved_export_list").is(":hidden")){
            $("#ExistsExportList").show();
        }
        else{
            this.rpc("/base/export/exist_export_lists", {"model": this.dataset.model}, function(export_list){
                if(export_list.length){
                    $("#ExistsExportList").append(QWeb.render('Exists.ExportList', {'existing_exports':export_list}));
                    $("#saved_export_list").change(function(){
                        $("#fields_list option").remove();
                        export_id = $("#saved_export_list option:selected").val();
                        if (export_id){
                            self.rpc("/base/export/namelist", {"model": self.dataset.model, export_id: parseInt(export_id)}, self.do_load_export_field);
                        }
                    });
                    $('#delete_export_list').click(function(){
                        select_exp = $("#saved_export_list option:selected")
                        if (select_exp.val()){
                            self.rpc("/base/export/delete_export", {"export_id": parseInt(select_exp.val())}, {});
                            select_exp.remove();
                            if($("#saved_export_list option").length <= 1){
                                $("#ExistsExportList").hide();
                            }
                        }
                    });
                }
            });
        }
    },

    do_load_export_field: function(field_list){
        var export_node = $("#fields_list");
        for (var key in field_list) {
            export_node.append(new Option(field_list[key], key));
        }
    },

    on_show_save_list: function(){
        var self = this;
        var current_node = $("#savenewlist");
        if(!(current_node.find("label")).length){
            current_node.append(QWeb.render('ExportNewList'));
            current_node.find("#add_export_list").click(function(){
                var value = current_node.find("#savelist_name").val();
                if (value){
                    self.do_save_export_list(value);
                }
                else{
                    alert("Pleae Enter Save Field List Name");
                }
            });
        }
        else{
            if (current_node.is(':hidden')){
                current_node.show();
            }
            else{
               current_node.hide();
            }
        }
    },

    do_save_export_list: function(value){
        var self = this;
        var export_field = self.get_fields()
        if(export_field.length){
            self.rpc("/base/export/save_export_lists", {"model": self.dataset.model, "name":value, "field_list":export_field}, function(exp_id){
                if(exp_id){
                    if($("#saved_export_list").length > 0){
                        $("#saved_export_list").append( new Option(value, exp_id));
                    }
                    else{
                        self.on_show_exists_export_list();
                    }
                    if($("#saved_export_list").is(":hidden")){
                        self.on_show_exists_export_list();
                    }
                }
            });
            self.on_show_save_list()
            $("#fields_list option").remove();
        }
    },

    on_click: function(id, result) {
        var self = this
        self.field_id = id.split("-")[1];
        var model = ''
        var prefix = ''
        var name = ''
        var is_loaded = 0;
        _.each(result, function(record) {
            if(record['id'] == self.field_id && (record['children']).length >= 1){
                model = record['params']['model']
                prefix = record['params']['prefix']
                name = record['params']['name']
                $(record['children']).each (function(e, childid) {
                    if ($("tr[id='treerow-" + childid +"']").length > 0) {
                        if ($("tr[id='treerow-" + childid +"']").is(':hidden')) {
                            is_loaded = -1;
                        } else {
                            is_loaded++;
                        }
                    }
                });
                if (is_loaded == 0) {
                    if ($("tr[id='treerow-" + self.field_id +"']").find('img').attr('src') == '/base/static/src/img/expand.gif') {
                        if (model){
                            import_comp = $("#import_compat option:selected").val()
                            var params = {"import_compat":parseInt(import_comp), "views_id": this.views_id, "parent_field_type" : record['field_type']}
                            self.rpc("/base/export/get_fields", {"model": model, "prefix": prefix, "name": name,  "field_parent" : self.field_id, "params":params}, function (results) {
                                self.on_show_data(results);
                            });
                        }
                    }
                } else if (is_loaded > 0) {
                    self.showcontent(self.field_id, true);
                } else {
                    self.showcontent(self.field_id, false);
                }
            }

        });
    },

    on_show_data: function(result) {
        var self = this;
        var current_tr = $("tr[id='treerow-" + self.field_id + "']");
        if (current_tr.length >= 1){
            current_tr.find('img').attr('src','/base/static/src/img/collapse.gif');
            current_tr.after(QWeb.render('ExportTreeView-Secondary.children', {'fields': result}));
        }
        else{
            $('#left_field_panel').append(QWeb.render('ExportTreeView-Secondary',  {'fields': result}));
        }
        _.each(result, function(record) {
            if(record.field_type == "one2many"){
                var o2m_fld = $("tr[id^='treerow-" + record.id + "']").find('#tree-column');
                o2m_fld.addClass("readonlyfield");
            }
            if ((record.required == true) || record.required == "True"){
                var required_fld = $("tr[id^='treerow-" + record.id + "']").find('#tree-column');
                required_fld.addClass("requiredfield");
            }
            $("img[id ^='parentimg-" + record.id +"']").click(function(){
                self.on_click(this.id, result);
            });

            $("tr[id^='treerow-" + record.id + "']").click(function(e){
                if (e.shiftKey == true){
                    var frst_click,scnd_click = '';
                    if (self.row_index == 0){
                        self.row_index = this.rowIndex;
                        frst_click = $("tr[id^='treerow-']")[self.row_index-1];
                        $(frst_click).addClass("ui-selected");
                    }else{
                        if (this.rowIndex >=self.row_index){
                            for (i = (self.row_index-1); i < this.rowIndex; i++) {
                                scnd_click = $("tr[id^='treerow-']")[i];
                                if(!$(scnd_click).find('#tree-column').hasClass("readonlyfield")){
                                    $(scnd_click).addClass("ui-selected");
                                }
                            }
                        }else{
                            for (i = (self.row_index-1); i >= (this.rowIndex-1); i--) {
                                scnd_click = $("tr[id^='treerow-']")[i];
                                if(!$(scnd_click).find('#tree-column').hasClass("readonlyfield")){
                                    $(scnd_click).addClass("ui-selected");
                                }
                            }
                        }
                    }
                }
                self.row_index = this.rowIndex;

                $("tr[id^='treerow-" + record.id + "']").keyup(function (e) {
                        self.row_index = 0;
                });
                var o2m_selection = $("tr[id^='treerow-" + record.id + "']").find('#tree-column');
                if ($(o2m_selection).hasClass("readonlyfield")){
                    return false;
                }
                var selected = $("tr.ui-selected");
                if ($(this).hasClass("ui-selected") && (e.ctrlKey == true)){
                    $(this).find('a').blur();
                    $(this).removeClass("ui-selected");
                }else if($(this).hasClass("ui-selected") && (e.ctrlKey == false) && (e.shiftKey == false)){
                    selected.find('a').blur();
                    selected.removeClass("ui-selected");
                    $(this).find('a').focus();
                    $(this).addClass("ui-selected");
                }else if(!$(this).hasClass("ui-selected") && (e.ctrlKey == false) && (e.shiftKey == false)){
                    selected.find('a').blur();
                    selected.removeClass("ui-selected");
                    $(this).find('a').focus();
                    $(this).addClass("ui-selected");
                }else if(!$(this).hasClass("ui-selected") && (e.ctrlKey == true)){
                    $(this).find('a').focus();
                    $(this).addClass("ui-selected");
                }
                return false;
            });

            $("tr[id^='treerow-" + record.id + "']").keydown(function (e) {
                var keyCode = e.keyCode || e.which;
                arrow = {left: 37, up: 38, right: 39, down: 40 };
                switch (keyCode) {
                    case arrow.left:
                        if( jQuery(this).find('img').attr('src') == '/base/static/src/img/collapse.gif'){
                            self.on_click(this.id, result);
                        }
                    break;
                    case arrow.up:
                        var elem = this;
                        $(elem).removeClass("ui-selected");
                        while($(elem).prev().is(":visible") == false){
                            elem = $(elem).prev();
                        }
                        if(!$(elem).prev().find('#tree-column').hasClass("readonlyfield")){
                            $(elem).prev().addClass("ui-selected");
                        }
                        $(elem).prev().find('a').focus();
                    break;
                    case arrow.right:
                        if( jQuery(this).find('img').attr('src') == '/base/static/src/img/expand.gif'){
                            self.on_click(this.id, result);
                        }
                    break;
                    case arrow.down:
                        var elem = this;
                        $(elem).removeClass("ui-selected");
                        while($(elem).next().is(":visible") == false){
                            elem = $(elem).next();
                        }
                        if(!$(elem).next().find('#tree-column').hasClass("readonlyfield")){
                            $(elem).next().addClass("ui-selected");
                        }
                        $(elem).next().find('a').focus();
                    break;
                }
            });
            $("tr[id^='treerow-" + record.id + "']").dblclick(function (e) {
                var o2m_selection = $("tr[id^='treerow-" + record.id + "']").find('#tree-column');
                if (! $(o2m_selection).hasClass("readonlyfield")){
                    var field_id =  $(this).find("a").attr("id");
                    if(field_id){
                       self.add_field(field_id.split('-')[1], $(this).find("a").attr("string"))
                   }
                }
            });
        });
        $('#fields_list').mouseover(function(event){
            if(event.relatedTarget){
                if (event.relatedTarget.attributes['id'] && event.relatedTarget.attributes['string']){
                    field_id = event.relatedTarget.attributes["id"]["value"]
                    if (field_id && field_id.split("-")[0] == 'export'){
                        if(!$("tr[id^='treerow-" + field_id.split("-")[1] + "']").find('#tree-column').hasClass("readonlyfield")){
                            self.add_field(field_id.split("-")[1], event.relatedTarget.attributes["string"]["value"]);
                        }
                    }
                }
            }
        });
    },

    // show & hide the contents
    showcontent: function (id, flag) {
        var first_child = $("tr[id='treerow-" + id + "']").find('img')
        if (flag) {
            first_child.attr('src', '/base/static/src/img/expand.gif');
        }
        else {
            first_child.attr('src', '/base/static/src/img/collapse.gif');
        }
        var child_field = $("tr[id^='treerow-" + id +"/']")
        var child_len = (id.split("/")).length + 1
        for (var i = 0; i < child_field.length; i++) {
            if (flag) {
                $(child_field[i]).hide();
            }
            else {
                if(child_len ==  (child_field[i].id.split("/")).length){
                    if( jQuery(child_field[i]).find('img').attr('src') == '/base/static/src/img/collapse.gif'){
                        jQuery(child_field[i]).find('img').attr('src', '/base/static/src/img/expand.gif')
                    }
                    $(child_field[i]).show();
                }
            }
        }
    },

    add_field: function(field_id, string) {
        var field_list = $('#fields_list')
        if ( $("#fields_list option[value='" + field_id + "']") && !$("#fields_list option[value='" + field_id + "']").length){
            field_list.append( new Option(string, field_id));
        }
    },

    get_fields: function (){
        var export_field = [];
        $("#fields_list option").each(function(){
            export_field.push(jQuery(this).val());
        });
        if (! export_field.length){
            alert('Please select fields to save export list...');
        }
        return export_field;
    },
    on_click_export_data: function(){
        var self = this;
        var export_field = {};
        var flag = true;
        $("#fields_list option").each(function(){
            export_field[jQuery(this).val()] = jQuery(this).text();
            flag = false;
        });
        if (flag){
            alert('Please select fields to export...');
            return;
        }

        import_comp = $("#import_compat option:selected").val()
        export_format = $("#export_format").val()

        self.rpc("/base/export/export_data", {"model": self.dataset.model, "fields":export_field, 'ids': self.dataset.ids, 'domain': self.dataset.domain, "import_compat":parseInt(import_comp), "export_format" :export_format}, function(data){
            window.location="data:text/csv/excel;charset=utf8," + data
            self.close();
        });
    },

    close: function() {
        jQuery(this.$dialog).remove();
        this._super();
    },

});

};
