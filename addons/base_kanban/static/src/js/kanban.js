openerp.base_kanban = function (openerp) {
QWeb.add_template('/base_kanban/static/src/xml/base_kanban.xml');
openerp.base.views.add('kanban', 'openerp.base_kanban.KanbanView');
openerp.base_kanban.KanbanView = openerp.base.View.extend({

    init: function (parent, element_id, dataset, view_id) {
        this._super(parent, element_id);
        this.view_manager = parent;
        this.dataset = dataset;
        this.domain = dataset.domain;
        this.context = dataset.context;
        this.model = this.dataset.model;
        this.view_id = view_id;
        this.group_by_field = false;
        this.source_index = {};
        this.all_display_data = false;
        this.groups = [];
    },
    start: function () {
        this.rpc("/base_kanban/kanbanview/load",
        {"model": this.model, "view_id": this.view_id}, this.on_loaded);
    },
    on_loaded: function (data) {
        var self = this;
        this.template_xml = '';
        this.columns = data.all_fields;
        _.each(data.fields_view.arch.children, function(child) {
            if (child.tag == "template"){
                self.template_xml = openerp.base.json_node_to_xml(child, true);
            }
        });
        if (this.template_xml) {
            self.dataset.read_slice({
                context: self.dataset.get_context(),
                domain: self.dataset.get_domain()}, function (records) {
                self.all_display_data = [{'records': records, 'value':false, 'header': false, 'ids': self.dataset.ids}];
                self.on_show_data(self.all_display_data);
            });
        }
    },
    on_show_data: function (datas) {
        var self = this;
        var new_qweb = new QWeb2.Engine();
        self.$element.html(QWeb.render("KanbanBiew", {"datas" :datas}));

        this.on_reload_kanban();
        var drag_handel = false;
        if (this.$element.find(".oe-kanban-draghandle").length > 0) {
            drag_handel = ".oe-kanban-draghandle";
        }
        this.$element.find(".oe_column").sortable({
            connectWith: ".oe_column",
            handle : drag_handel,
            start: function(event, ui) {
                self.source_index['index'] = ui.item.index();
                self.source_index['column'] = ui.item.parent().attr('id');
            },
            stop: self.on_recieve_record,
        });
        this.$element.find(".record").addClass( "ui-widget ui-widget-content ui-corner-all" )
        this.$element.find(".oe_column").disableSelection()
        this.$element.find('button.oe_kanban_button_new').click(this.do_add_record);
    },
    on_button_click: function (button_attrs, record_id) {
        var self = this;
        if (this.groups.length) {
            _.each(this.groups, function (group) {
                group.list([],
                    function (groups) {},
                    function (dataset) {
                        dataset.read_slice({}, function(records) {
                            var index = parseInt(_.indexOf(dataset.ids, record_id));
                            if(index >= 0) {
                                self.on_confirm_click(dataset, button_attrs, index, record_id);
                            }
                        });
                    }
                );
            });
        } else {
            var index = parseInt(_.indexOf(self.dataset.ids, record_id));
            if (index >= 0) {
                _.extend(self.dataset, {domain: self.domain, context: self.context});
                self.on_confirm_click(self.dataset, button_attrs, index, record_id);
            }
        }
    },
    on_confirm_click: function (dataset, button_attrs, index, record_id) {
        if (button_attrs.type == 'edit') {
            this.do_edit_record(dataset, index);
        } else {
            this.on_execute_button_click(dataset, button_attrs, record_id);
        }
    },
    do_add_record: function () {
        this.do_edit_record(this.dataset, null);
    },
    do_edit_record: function (dataset, index) {
        var self = this;
        _.extend(this.dataset, {
            domain: dataset.domain,
            context: dataset.get_context()
        }).read_slice({}, function () {
            self.dataset.index = index;
            self.do_switch_view('form');
        });
    },
    do_delete: function (id) {
        var self = this;
        return $.when(this.dataset.unlink([id])).then(function () {
            self.drop_records(id);
        });
    },
    drop_records: function (id) {
        var self = this;
        _.each(self.all_display_data, function(data, index) {
            _.each(data.records, function(record, index_row) {
                if (parseInt(record.id) == id) {
                    self.all_display_data[index]['records'].splice(index_row, 1);
                    self.all_display_data[index]['ids'].splice(index_row, 1);
                    return false;
                }
            });
        });
        self.$element.find("#main_" + id).remove();
    },
    on_execute_button_click: function (dataset, button_attrs, record_id) {
        var self = this;
        this.execute_action(
            button_attrs, dataset,
            record_id, function () {
                var count = 1;
                _.each(self.all_display_data, function(data, index) {
                    self.dataset.read_ids( data.ids, [], function(records){
                        self.all_display_data[index].records = records;
                        if(self.all_display_data.length == count) {
                            self.on_reload_kanban();
                        }
                        count++;
                    });
                });
            }
        );
    },
    on_recieve_record: function (event, ui) {
        var self = this;
        var from = ui.item.index();
        var search_action = false;
        var to = ui.item.prev().index() || 0;
        if (!ui.item.attr("id")) {
            return false;
        }
        if (self.columns.sequence && (self.source_index.index >= 0 && self.source_index.index != from) ||
                (self.source_index.column && self.source_index.column != ui.item.parent().attr('id'))) {
            var child_record = ui.item.parent().children();
            var data, sequence = 1, index = to;
            child_record.splice(0, to);
            var flag = false;
            if (to >= 0 && child_record) {
                var record_id = parseInt($(child_record).attr("id").split("_")[1]);
                if (record_id) {
                    _.each(self.all_display_data, function(data, index) {
                        _.each(data.records, function(record, index_row) {
	                        if(record_id == record.id && record.sequence) {
	                            sequence = record.sequence;
	                            flag = true;
	                            return false;
	                        }
                        });
                        if(flag) {return false;}
                    });
                }
            }
            _.each(child_record, function (child) {
                var child_id = parseInt($(child).attr("id").split("_")[1]);
                if (child_id) {
                    flag = false;
                    _.each(self.all_display_data, function(data, index) {
                        _.each(data.records, function(record, index_row) {
                            if(parseInt(record.id) == child_id) {
                                self.all_display_data[index]['records'][index_row]['sequence'] = sequence;
                                flag = true;
                                return false;
                            }
                        });
                        if (flag) {return false;}
                    });
                    self.dataset.write(child_id, {sequence: sequence});
                    sequence++;
                    search_action = true;
                }
            });
        }
        if (self.group_by_field && self.source_index.column && self.source_index.column != ui.item.parent().attr('id')) {
            var value = ui.item.closest("td").attr("id");
            if (value) {
                var data_val = {};
                var wirte_id = parseInt(ui.item.attr("id").split("_")[1]);
                value = value.split("_")[1];
                if (value == 'false') {
                    value = false;
                }
                var update_record = false;
                _.each(self.all_display_data, function(data, index) {
                    _.each(data.records, function(record, index_row) {
                        if(parseInt(record.id) == wirte_id) {
                            self.all_display_data[index]['records'][index_row][self.group_by_field] = value;
                            update_record = self.all_display_data[index]['records'].splice(index_row,1)
                            return false;
                        }
                    });
                    if (update_record) {return false;}
                });
                _.each(self.all_display_data, function(data, index) {
                    if (data.value == value || (data.value == 'false' && value == false)) {
                        self.all_display_data[index]['records'].push(update_record[0]);
                    }
                });
                data_val[self.group_by_field] = value;
                self.dataset.write(wirte_id, data_val);
                search_action = true;
            }
        }
        if (search_action) {
            self.on_reload_kanban();
        }
        this.source_index = {};
    },
    on_reload_kanban: function (){
        var self = this;
        var new_qweb = new QWeb2.Engine();
        new_qweb.add_template('<templates><t t-name="custom_template">' + this.template_xml + '</t></templates>');
        _.each(self.all_display_data, function(data, index) {
            if (data.records.length > 0){
                _.each(data.records, function(record) {
                    self.$element.find("#main_" + record.id).children().remove();
                    self.$element.find("#main_" + record.id).append(new_qweb.render('custom_template', record));
                });
            } else {
                self.$element.find("#column_" + data.value).remove();
                self.all_display_data.splice(index, 1);
            }
        });
        this.$element.find( ".oe_table_column " ).css("width", 99 / self.all_display_data.length +"%");
        this.$element.find('button').click(function() {
            var record_id = $(this).closest(".record").attr("id");
            if (record_id) {
                record_id = parseInt(record_id.split("_")[1])
                if (record_id) {
                    if ($(this).data("type") == "delete") {
                        self.do_delete(record_id);
                    } else {
                        var button_attrs = $(this).data()
                        self.on_button_click(button_attrs, record_id);
                    }
                }
            }
        });
    },

    do_search: function (domains, contexts, group_by) {
        var self = this;
        this.rpc('/base/session/eval_domain_and_context', {
            domains: domains,
            contexts: contexts,
            group_by_seq: group_by
        }, function (results) {
            self.group_by_field = false;
            self.datagroup = new openerp.base.DataGroup(self, self.model, results.domain, results.context, results.group_by || []);
            self.dataset.context = results.context;
            self.dataset.domain = results.domain;
            self.datagroup.list([],
                function (groups) {
                    self.groups = groups;
                    if (group_by.length >= 1) {
                        self.group_by_field = group_by[0].group_by;
                        self.do_render_group(groups);
                    }
                },
                function (dataset) {
                    self.domain = dataset.domain;
                    self.context = dataset.context;
                    self.groups = [];
                    self.dataset.read_slice({}, function(records) {
                        self.all_display_data = [{'records': records, 'value':false, 'header' : false, 'ids': self.dataset.ids}];
                        self.$element.find("#kanbanview").remove();
                        self.on_show_data(self.all_display_data);
                    });
                }
            );

        });
    },
    do_render_group : function (datagroups) {
        this.all_display_data = [];
        var self = this;
        _.each(datagroups, function (group) {
            self.dataset.context = group.context;
            self.dataset.domain = group.domain;
            var group_name = group.value;
            var group_value = group.value;
            if (!group.value) {
                group_name = "Undefined";
                group_value = 'false';
            } else if (group.value instanceof Array) {
                group_name = group.value[1];
                group_value = group.value[0];
            }
            self.dataset.read_slice({}, function(records) {
                self.all_display_data.push({"value" : group_value, "records": records, 'header':group_name, 'ids': self.dataset.ids});
                if (datagroups.length == self.all_display_data.length) {
                    self.$element.find("#kanbanview").remove();
                    self.on_show_data(self.all_display_data);
                }
            });
        });
    },

    do_show: function () {
        this.$element.show();
    },

    do_hide: function () {
        this.$element.hide();
    },

});
};

// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax:
