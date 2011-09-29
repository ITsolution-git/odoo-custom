openerp.web_process = function (openerp) {
    var QWeb = openerp.web.qweb;
    QWeb.add_template('/web_process/static/src/xml/web_process.xml');
    openerp.web.ViewManager.include({
        start: function() {
            this._super();
            var self = this;
            this.process_check();
            this.process_help = this.action ? this.action.help : 'Help: Not Defined';
        },
        process_check: function() {
            var self = this,
            grandparent = this.widget_parent && this.widget_parent.widget_parent,
            view = this.views[this.views_src[0].view_type],
            $process_view = this.$element.find('.oe-process-view');

            this.process_model = this.model;
            if (!(grandparent instanceof openerp.web.WebClient) ||
                !(view.view_type === this.views_src[0].view_type
                    && view.view_id === this.views_src[0].view_id)) {
                        $process_view.hide();
                        return;
            }
            $process_view.click(function() {
                $.when(self.load_process()).then(self.get_process_id());
            });
        },

        process_subflow : function() {
            var self = this;
            new openerp.web.DataSetSearch(this,
                "ir.actions.act_window",this.session.context,[])
            .read_slice(['help'],
                { domain:
                    [
                        ['res_model','=',this.process_action_model],
                        ['name','ilike', this.process_action_name]
                    ]
                },
                function(res) {
                    if (res.length) {
                        self.process_help = res[0]['help'] || 'Help: Not Defined';
                    }
                    $.when(self.load_process()).then(self.render_process_view());

            });
        },

        load_process: function() {
            var self = this;
            this.$element.html(QWeb.render("ProcessView", this));
            this.$element.find('#edit_process').click(function() {
                self.edit_process_view();
            });
        },
        
        edit_process_view: function() {
            var self = this;
            var action_manager = new openerp.web.ActionManager(this);
            var dialog = new openerp.web.Dialog(this, {
                width: 800,
                height: 600,
                buttons : {
                    Cancel : function() {
                        $(this).dialog('destroy');
                    },
                    Save : function() {
                        var form_view = action_manager.inner_viewmanager.views.form.controller;
    
                        form_view.do_save(function() {
                            self.process_renderer([[self.process_id]]);
                        });
                        $(this).dialog('destroy');
                    }
                }
            }).start().open();
            
            action_manager.appendTo(dialog.$element);
            action_manager.do_action({
                res_model : 'process.process',
                res_id: self.process_id,
                views : [[false, 'form']],
                type : 'ir.actions.act_window',
                auto_search : false,
                flags : {
                    search_view: false,
                    sidebar : false,
                    views_switcher : false,
                    action_buttons : false,
                    pager: false
                }
            });
        },

        get_process_id: function() {
            var self = this;
            this.process_dataset = new openerp.web.DataSetStatic(this, "process.process", this.session.context);
            this.process_dataset.call("search_by_model",
                    [self.process_model,self.session.context],
                    function(res) {self.process_renderer(res)});
        },
        process_renderer: function(res) {
            var self = this;
            if(!res.length) {
                this.process_model = false;
                this.get_process_id();
            } else {
                if(res.length > 1) {
                    this.selection = res;
                    $.when(this.load_process()).then(function() {
                        var $parent = self.widget_parent.$element;
                        $parent.find('#change_process').click(function() {
                            self.selection = false;
                            self.process_id = $parent.find('#select_process').val();
                            $.when(self.load_process()).then(self.render_process_view());
                        });
                    });
                } else {
                    this.process_id = res[0][0];
                    $.when(this.load_process()).then(this.render_process_view());
                }
            }
        },

        render_process_view: function() {
            var self = this;
            this.process_id = parseInt(this.process_id, 10);
            this.process_dataset.call("graph_get",
                    [self.process_id, self.model, false, [80,80,150,100]],
                    function(res) {
                        res['title'] = res.resource ? res.resource : res.name;
                        self.process_dataset.call("search_by_model",
                            [self.model,self.session.context],
                            function(r) {
                                res['related'] = r;
                            });
                        self.draw_process_graph(res);
                    }
            );
        },
        draw_process_graph: function(res) {
            var self = this;
            var process_graph = new Graph();

            var process_renderer = function(r, n) {
                var process_node,
                    process_node_text,
                    process_node_desc,
                    process_set;

                var node_button,
                    node_menu,
                    img_src;

                var bg = "node",
                    clip_rect = "".concat(n.node.x,",",n.node.y,",150,100"),
//                    text_position_x  = n.node.x + (n.node.y/2)

                //Image part
                bg = n.node.kind == "subflow" ? "node-subflow" : "node";
                bg = n.node.gray ? bg + "-gray" : bg;
                img_src = '/web_process/static/src/img/'+ bg + '.png';

                r['image'](img_src, n.node.x, n.node.y,150, 100)
                    .attr({"clip-rect": clip_rect})
                    .mousedown(function(){
                        return false;
                });

                //Node
                process_node = r['rect'](n.node.x, n.node.y, 150, 100).attr({stroke: "none"});
                // Node text
                process_node_text =  r.text(n.node.x, n.node.y, (n.node.name))
                    .attr({"fill": "#fff", "font-weight": "bold", "cursor": "pointer"});
                process_node_text.translate(n.node.x / 2, 10)
                if(n.node.subflow) {
                    process_node_text.click(function() {
                        self.process_id = n.node.subflow[0];
                        self.process_action_model =  n.node.model;
                        self.process_action_name = n.node.name;
                        self.process_subflow();
                    });
                }

                //Node Description
                new_notes = n.node.notes;
                if(n.node.notes.length > 25) {
                    var new_notes= temp_str = '';
                    var from = to = 0;
                    while (1){
                        from = 25;
                        temp_str = n.node.notes.substr(to ,25);
                        if (temp_str.lastIndexOf(" ") < 25 && temp_str.length >= 25) {
                            from  =  temp_str.lastIndexOf(" ");
                        }
                        new_notes += "\n" + n.node.notes.substr(to , from);
                        if(new_notes.length > n.node.notes.length) break;
                        to += from;
                    }
                }
                process_node_desc = r.text(n.node.x+85, n.node.y+50, (new_notes));
                r['image']('/web/static/src/img/icons/gtk-info.png', n.node.x+20, n.node.y+70, 16, 16)
                    .attr({"cursor": "pointer", "title": "Help"})
                    .click(function() {
                        window.open(n.node.url || "http://doc.openerp.com/v6.0/index.php?model=" + n.node.model);
                    });

                if(n.node.menu) {
                    r['image']('/web/static/src/img/icons/gtk-jump-to.png', n.node.x+115, n.node.y+70, 16, 16)
                    .attr({"cursor": "pointer", "title": n.node.menu.name})
                    .click(function() {
                        self.jump_to_view(n.node.res_model, n.node.menu.id);
                    });
                }

                process_set = r.set().push(process_node);
	            process_set.mousedown(function() {
                    return false;
                });
                return process_set;
            };

            _.each(res['nodes'],function(node, node_id) {
                node['res_model'] = self.model,
                node['res_id'] = false,
                node['id'] = node_id;
                process_graph.addNode(node['name'], {node: node,render: process_renderer});
            });

            _.each(res['transitions'], function(transitions) {
                var src = res['nodes'][transitions['source']];
                var dst = res['nodes'][transitions['target']];
                // make active
                transitions['active'] = src.active && !dst.gray;
                process_graph.addEdge(src['name'], dst['name'], {directed : true});
            });

            var layouter = new Graph.Layout.Ordered(process_graph);
            var render_process_graph = new Graph.Renderer.Raphael('process_canvas', process_graph, $('#process_canvas').width(), $('#process_canvas').height());
        },

        jump_to_view: function(model, id) {
            var self = this;
            var dataset = new openerp.web.DataSetStatic(this, 'ir.values', this.session.context);
            dataset.call('get',
                ['action', 'tree_but_open',[['ir.ui.menu', id]], dataset.context],
                function(res) {
                    self.$element.empty();
                    var action = res[0][res[0].length - 1];
                    self.rpc("/web/action/load", {
                        action_id: action.id,
                        context: dataset.context
                        }, function(result) {
                            var action_manager = new openerp.web.ActionManager(self);
                            action_manager.appendTo(self.widget_parent.$element);
                            action_manager.do_action(result.result);
                        });
                });
        }
    });
};


// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax:
