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
                    self.xml_id = 0 ;
                    self.get_data();

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

    check_attr:function(xml,tag,level){
        var obj = new Object();
        obj.child_id = [];
        obj.id = this.xml_id++;
        obj.level = level;
        var att_list = [];
        var name1 = "<" + tag;
        var xml_tag = "<" + tag;
        $(xml).each(function() {
            att_list = this.attributes;
            att_list = _.select(att_list, function(attrs){
                xml_tag += ' ' +attrs.nodeName+'='+'"'+attrs.nodeValue+'"';
                if (tag != 'button'){
                   if(attrs.nodeName == "string" || attrs.nodeName == "name" || attrs.nodeName == "index"){
                        name1 += ' ' +attrs.nodeName+'='+'"'+attrs.nodeValue+'"';}
                }else{
                    if(attrs.nodeName == "name"){
                        name1 += ' ' +attrs.nodeName+'='+'"'+attrs.nodeValue+'"';}
                }
                });
                name1+= ">";
                xml_tag+= ">";
         });
        obj.main_xml = xml_tag;
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

    children_function : function(xml,root,parent_list,parent_id,main_object,parent_child_id){
        var self = this;
        var child_obj_list = [];
        var parent_child_id = parent_child_id;
        var parent_list = parent_list;
        var main_object = main_object;
        var children_list = $(xml).filter(root).children();
        var parents = $(children_list[0]).parents().get();
        _.each(children_list, function(child_node){
            var string = self.check_attr(child_node,child_node.tagName.toLowerCase(),parents.length);
            child_obj_list.push(string);
        });
        if(children_list.length != 0){
            var child_ids = _.map(child_obj_list ,function(num){return num.id;});
            parent_child_id.push({'key': parent_id, 'value': child_ids});
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
      (children_list[i],children_list[i].tagName.toLowerCase(),parent_list,child_obj_list[i].id,main_object,parent_child_id);
        }
        return {"main_object":main_object,"parent_child_id":parent_child_id};
    },
    parse_xml :function(arch){
        var self = this;
        var root = $(arch).filter(":first")[0];
        var tag = root.tagName.toLowerCase();
        var root_object = self.check_attr(root,tag,0);
        return self.children_function(arch,tag,[],0,[root_object],[]);
    },
    get_data : function(){
            var self = this;
            var inherited_view =[];
            var result;
            var view_id =(($("input[name='radiogroup']:checked").parent()).parent()).attr('data-id');
            var ve_dataset = new openerp.web.DataSet(this,'ir.ui.view');
            dataset = new openerp.web.DataSetSearch(self,'ir.ui.view', null, null);
            dataset.read_slice([],{domain : [['inherit_id','=',parseInt(view_id)]]},function (result) {
                return result;
            });
            ve_dataset.read_ids([parseInt(view_id)],['arch'],function (arch){
                var one_object = self.parse_xml(arch[0].arch);
                return self.edit_view(one_object);
            });
            
    },
    edit_view : function(one_object){
        var self = this;
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
                }
        });
        this.dialog.start().open();
        this.dialog.$element.html(QWeb.render('view_editor', {
        'data': one_object['main_object'],
        }));

        $("tr[id^='viewedit-']").click(function() {
            $("tr[id^='viewedit-']").removeClass('ui-selected');
            $(this).addClass('ui-selected');
        });

        $("img[id^='parentimg-']").click(function() {
            if ($(this).attr('src') == '/web/static/src/img/collapse.gif'){
                $(this).attr('src', '/web/static/src/img/expand.gif');
                self.on_expand(this);
            }else{
                $(this).attr('src', '/web/static/src/img/collapse.gif');
                self.on_collapse(this,one_object['parent_child_id']);
            }
        });
    $("img[id^='side-']").click(function() {
        var side = $(this).closest("tr[id^='viewedit-']")
        var id_tr = (side.attr('id')).split('-')[1];
        switch (this.id)
        {
        case "side-add":
          break;
        case "side-remove":
          break;
        case "side-edit":
          break;
        case "side-up":
            var img = side.find("img[id='parentimg-"+id_tr+"']").attr('src');
            var level = side.attr('level');
            var list_shift =[];
            var last_tr;
            var next_tr;
            list_shift.push(side);
            var cur_tr = side;
            while(1){
                var prev_tr = cur_tr.prev();
                if(level >= prev_tr.attr('level') || prev_tr.length==0){
                    last_tr = prev_tr;
                    break;
                    }
                cur_tr = prev_tr;
            }
            if(img){
                while(1){
                    var next_tr = side.next();
                        if(next_tr.attr('level') <= level || next_tr.length==0){
                            break;
                        }else{
                        list_shift.push(next_tr);
                        side = next_tr;
                        } 
                }
            }
            if(last_tr.length!=0 && last_tr.attr('level') == level){
                 _.each(list_shift,function(rec){
                        $(last_tr).before(rec); 
                  });
            }
          break;
        case "side-down":
            var img = side.find("img[id='parentimg-"+id_tr+"']").attr('src');
            var level = side.attr('level');
            var list_shift =[];
            var last_tr;
            var next_tr;
            var cur_tr = side;
            list_shift.push(side);
            if(img){
                while(1){
                    var next_tr = cur_tr.next();
                        if(next_tr.attr('level') <= level || next_tr.length==0){
                            last_tr = next_tr;
                            break;
                        }else{
                        list_shift.push(next_tr);
                        cur_tr = next_tr;
                        } 
                }
            }else{last_tr = cur_tr.next();}
            if(last_tr.length != 0 && last_tr.attr('level')==level){
                var last_tr_id = (last_tr.attr('id')).split('-')[1];  
                img = last_tr.find("img[id='parentimg-"+last_tr_id+"']").attr('src');
                if(img){
                    $("img[id='parentimg-"+last_tr_id+"']").attr('src', '/web/static/src/img/expand.gif');
                    while(1){
                        var next_tr = last_tr.next();
                        if (next_tr.attr('level') <= level || next_tr.length==0){break;}
                            next_tr.hide();
                            last_tr = next_tr;
                    }
                 }
                list_shift.reverse();
                _.each(list_shift,function(rec){
                        $(last_tr).after(rec); 
                  });
            }
          break;
        }
    });
    },
    on_expand: function(self){
        var level = $(self).closest("tr[id^='viewedit-']").attr('level');
        var cur_tr = $(self).closest("tr[id^='viewedit-']");
        while (1){
            var nxt_tr = cur_tr.next();
            if (nxt_tr.attr('level') > level){
                cur_tr = nxt_tr;
                nxt_tr.hide();
            }else return nxt_tr;
        }
    },
    on_collapse: function(self,parent_child_id,id){
        var id = self.id.split('-')[1];
        var datas = _.detect(parent_child_id,function(res){
            return res.key == id;
        });
        _.each(datas.value,function(rec){
            var tr = $("tr[id='viewedit-"+rec+"']");
            tr.find("img[id='parentimg-"+rec+"']").attr('src','/web/static/src/img/expand.gif');
            tr.show();
        });
    }
});
};
