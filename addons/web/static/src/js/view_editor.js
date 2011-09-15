openerp.web.view_editor = function(openerp) {
var QWeb = openerp.web.qweb;
openerp.web.ViewEditor =   openerp.web.Widget.extend({
    init: function(parent, element_id, dataset, view, options) {
        this._super(parent);
        this.element_id = element_id
        this.parent = parent
        this.dataset = dataset;
        this.model = dataset.model;
        this.xml_id = 0;
    },
    start: function() {
        this.View_editor();
    },
    View_editor : function(){
        var self = this;
        var action = {
            name:'ViewEditor',
            context:this.session.user_context,
            domain: [["model", "=", this.dataset.model]],
            res_model: 'ir.ui.view',
            views : [[false, 'list']],
            type: 'ir.actions.act_window',
            target: "current",
            limit : 80,
            auto_search : true,
            flags: {
                sidebar: false,
                views_switcher: false,
                action_buttons:false,
                search_view:false,
                pager:false,
                radio:true
            },
        };
        var action_manager = new openerp.web.ActionManager(this);
        this.dialog = new openerp.web.Dialog(this,{
            modal: true,
            title: 'ViewEditor',
            width: 750,
            height: 500,
            buttons: {
                "Create": function(){
                    
                },
                "Edit": function(){
                    self.xml_id=0;
                    self.edit_view();
                },
                "Close": function(){
                 $(this).dialog('destroy');
                }
            },

        });
       this.dialog.start(); 
       this.dialog.open();
       action_manager.appendTo(this.dialog);
       action_manager.do_action(action);
    },
    check_attr:function(xml,tag){
        var obj = new Object();
        obj.child_id = [];
        obj.id = this.xml_id++;
        var att_list = [];
        var name1 = "<" + tag;
        $(xml).each(function() {
            att_list = this.attributes;
            att_list = _.select(att_list, function(attrs){
                if(attrs.nodeName == "string" || attrs.nodeName == "name" || attrs.nodeName == "index"){
                    name1 += ' ' +attrs.nodeName+'='+'"'+attrs.nodeValue+'"';} 
                });
                name1+= ">";
         });  
        obj.name = name1;
        return obj;
    },
    save_object : function(val,parent_list,child_obj_list){
        var self = this;
        var check_id = parent_list[0];
        var p_list = parent_list.slice(1);
        if(val.child_id.length != 0){
             $.each(val.child_id, function(key,val) {
                if(val.id==check_id){
                    if(p_list.length!=0){
                        self.save_object(val,p_list,child_obj_list);
                    }else{
                        val.child_id = child_obj_list;
                        return;
                    }
                }
            });
        }else{
            val.child_id = child_obj_list;
        }
    },
    children_function : function(xml,root,parent_list,parent_id,main_object){
        var self = this;
        var child_obj_list = [];
        var parent_list = parent_list;
        var main_object = main_object;
        var children_list = $(xml).filter(root).children();
        _.each(children_list, function(child_node){
            var string = self.check_attr(child_node,child_node.tagName.toLowerCase());
            child_obj_list.push(string);
        });
        if(children_list.length != 0){
            var parents = $(children_list[0]).parents().get();
            if(parents.length <= parent_list.length){
                parent_list.splice(parents.length-1);}
            parent_list.push(parent_id);
            $.each(main_object, function(key,val) {
                self.save_object(val,parent_list.slice(1),child_obj_list); 
            });
        }
        for(var i=0;i<children_list.length;i++){
            self.children_function
(children_list[i],children_list[i].tagName.toLowerCase(),parent_list,child_obj_list[i].id,main_object);
        }
        return main_object;
    },
    edit_view : function(){
            var self = this;
            var all_list =[];
            var view_id =(($("input[name='radiogroup']:checked").parent()).parent()).attr('data-id');
            var ve_dataset = new openerp.web.DataSet(this,'ir.ui.view');
            ve_dataset.read_ids([parseInt(view_id)],['arch'],function (arch) {
            var arch = arch[0].arch;
            var root = $(arch).filter(":first")[0];
            var tag = root.tagName.toLowerCase();
            var root_object = self.check_attr(root,tag);
            one_object = self.children_function(arch,tag,[],0,[root_object]);
            //render here
            });
            this.dialog = new openerp.web.Dialog(this,{
            modal: true,
            title: 'Edit Xml',
            width: 750,
            height: 500,
            buttons: {
                "Inherited View": function(){
                    
                },
                "Preview": function(){
                    
                },
                "Close": function(){
                    $(this).dialog('destroy');
                }
            },

        });
         
    }
        
});
};
