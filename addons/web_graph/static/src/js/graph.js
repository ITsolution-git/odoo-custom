/*---------------------------------------------------------
 * OpenERP web_graph
 *---------------------------------------------------------*/

/* jshint undef: false  */


openerp.web_graph = function (instance) {
'use strict';

var _lt = instance.web._lt;
var _t = instance.web._t;
var QWeb = instance.web.qweb;

instance.web.views.add('graph', 'instance.web_graph.GraphView');

 /**
  * GraphView view.  It mostly contains a widget (PivotTable), some data, and 
  * calls to charts function.
  */
instance.web_graph.GraphView = instance.web.View.extend({
    template: 'GraphView',
    display_name: _lt('Graph'),
    view_type: 'graph',

    events: {
        'click .graph_mode_selection li' : function (event) {
            event.preventDefault();
            var mode = event.target.attributes['data-mode'].nodeValue;
            this.mode = mode;
            this.display_data();
        },

        'click .graph_expand_selection li' : function (event) {
            event.preventDefault();
            switch (event.target.attributes['data-choice'].nodeValue) {
                case 'fold_columns':
                    this.pivot_table.fold_cols();
                    this.display_data();
                    break;
                case 'fold_rows':
                    this.pivot_table.fold_rows();
                    this.display_data();
                    break;
                case 'fold_all':
                    this.pivot_table.fold_all();
                    this.display_data();
                    break;
                case 'expand_all':
                    this.pivot_table.expand_all().then(this.proxy('display_data'));
                    break;
            }
        },

        'click .graph_options_selection li' : function (event) {
            event.preventDefault();
            switch (event.target.attributes['data-choice'].nodeValue) {
                case 'swap_axis':
                    this.pivot_table.swap_axis();
                    this.display_data();
                    break;
                case 'update_values':
                    this.pivot_table.update_values().then(this.proxy('display_data'));
                    break;
                case 'export_data':
                    // Export code...  To do...
                    break;
            }
        },

        'click .web_graph_click' : function (event) {
            event.preventDefault();
            var id = event.target.attributes['data-id'].nodeValue;
            this.handle_header_event({id:id, event:event});
        },

        'click a.field-selection' : function (event) {
            var id = event.target.attributes['data-id'].nodeValue,
                field_id = event.target.attributes['data-field-id'].nodeValue;
            event.preventDefault();
            this.dropdown.remove();
            this.pivot_table.expand(id, field_id)
                .then(this.proxy('display_data'));
        },
    },

    view_loading: function (fields_view_get) {
        var self = this,
            model = new instance.web.Model(fields_view_get.model, {group_by_no_leaf: true}),
            domain = [],
            measure = null,
            fields,
            important_fields = [],
            row_groupby = [];

        this.pivot_table = null;
        this.heat_map_mode = false;
        this.mode = 'pivot';

        // get the default groupbys and measure defined in the field view
        _.each(fields_view_get.arch.children, function (field) {
            if ('name' in field.attrs) {
                if ('operator' in field.attrs) {
                    measure = field.attrs.name;
                } else {
                    row_groupby.push(field.attrs.name);
                }
            }
        });

        // get the most important fields (of the model) by looking at the
        // groupby filters defined in the search view
        var load_view = instance.web.fields_view_get({
            model: model,
            view_type: 'search',
        });

        var important_fields_def = $.when(load_view).then(function (search_view) {
            var groups = _.select(search_view.arch.children, function (c) {
                return (c.tag == 'group') && (c.attrs.string != 'Display');
            });
            _.each(groups, function(g) {
                _.each(g.children, function (g) {
                    if (g.attrs.context) {
                        var field_id = py.eval(g.attrs.context).group_by;
                        important_fields.push(field_id);
                    }
                });
            });
        });

        // get the fields descriptions from the model
        var field_descr_def = model.call('fields_get', [])
            .then(function (fs) { fields = fs; });

        return $.when(important_fields_def, field_descr_def)
            .then(function () {
                self.data = {
                    model: model,
                    domain: domain,
                    fields: fields,
                    important_fields: important_fields,
                    measure: measure,
                    measure_label: fields[measure].string,
                    col_groupby: [],
                    row_groupby: row_groupby,
                    groups: [],
                    total: null,
                };
            });
    },

    start: function () {
        this.table = $('<table></table>');
        this.$('.graph_main_content').append(this.table);
        return this.load_view();
    },

    do_search: function (domain, context, group_by) {
        var self = this;
        this.data.domain = new instance.web.CompoundDomain(domain);

        if (!this.pivot_table) {
            self.pivot_table = new openerp.web_graph.PivotTable(self.data);
            self.pivot_table.start().then(self.proxy('display_data'));
        } else {
            this.pivot_table.domain = domain;
            this.pivot_table.update_values().done(function () {
                self.display_data();
            });
        }
    },

    do_show: function () {
        this.do_push_state({});
        return this._super();
    },

    display_data: function () {
        this.$('.graph_main_content svg').remove();
        this.table.empty();

        var table_modes = ['pivot', 'heatmap', 'row_heatmap', 'col_heatmap'];
        if (_.contains(table_modes, this.mode)) {
            this.draw_table();
        } else {
            this.$('.graph_main_content').append($('<div><svg></svg></div>'));
            var svg = this.$('.graph_main_content svg')[0];
            openerp.web_graph.draw_chart(this.mode, this.pivot_table, svg);
        }
    },

    handle_header_event: function (options) {
        var pivot = this.pivot_table,
            id = options.id,
            header = pivot.get_header(id);

        if (header.is_expanded) {
            pivot.fold(header);
            this.display_data();
        } else {
            if (header.path.length < header.root.groupby.length) {
                var field = header.root.groupby[header.path.length];
                pivot.expand(id, field).then(this.proxy('display_data'));
            } else {
                this.display_dropdown({id:header.id,
                                       target: $(options.event.target),
                                       x: options.event.pageX,
                                       y: options.event.pageY});
            }
        }
    },

    display_dropdown: function (options) {
        var self = this,
            pivot = this.pivot_table,
            already_grouped = pivot.rows.groupby.concat(pivot.cols.groupby),
            possible_groups = _.difference(self.data.important_fields, already_grouped),
            dropdown_options = {
                header_id: options.id,
                fields: _.map(possible_groups, function (field) {
                    return {id: field, value: self.data.fields[field].string};
            })};

        this.dropdown = $(QWeb.render('field_selection', dropdown_options));
        options.target.after(this.dropdown);
        this.dropdown.css({position:'absolute',
                           left:options.x,
                           top:options.y});
        $('.field-selection').next('.dropdown-menu').toggle();
    },

    draw_table: function () {
        this.draw_top_headers();
        _.each(this.pivot_table.rows.headers, this.proxy('draw_row'));
    },

    make_border_cell: function (colspan, rowspan) {
        return $('<td></td>').addClass('graph_border')
                             .attr('colspan', colspan)
                             .attr('rowspan', rowspan);
    },

    make_header_title: function (header) {
        return $('<span> </span>')
            .addClass('web_graph_click')
            .attr('href', '#')
            .addClass((header.is_expanded) ? 'icon-minus-sign' : 'icon-plus-sign')
            .append((header.title !== undefined) ? header.title : 'Undefined');
    },

    draw_top_headers: function () {
        var self = this,
            pivot = this.pivot_table,
            height = _.max(_.map(pivot.cols.headers, function(g) {return g.path.length;})),
            header_cells = [[this.make_border_cell(1, height)]];

        function set_dim (cols) {
            _.each(cols.children, set_dim);
            if (cols.children.length === 0) {
                cols.height = height - cols.path.length + 1;
                cols.width = 1;
            } else {
                cols.height = 1;
                cols.width = _.reduce(cols.children, function (sum,c) { return sum + c.width;}, 0);
            }
        }

        function make_col_header (col) {
            var cell = self.make_border_cell(col.width, col.height);
            return cell.append(self.make_header_title(col).attr('data-id', col.id));
        }

        function make_cells (queue, level) {
            var col = queue[0];
            queue = _.rest(queue).concat(col.children);
            if (col.path.length == level) {
                _.last(header_cells).push(make_col_header(col));
            } else {
                level +=1;
                header_cells.push([make_col_header(col)]);
            }
            if (queue.length !== 0) {
                make_cells(queue, level);
            }
        }

        set_dim(pivot.cols.main);  // add width and height info to columns headers
        if (pivot.cols.main.children.length === 0) {
            make_cells(pivot.cols.headers, 0);
        } else {
            make_cells(pivot.cols.main.children, 1);
            header_cells[0].push(self.make_border_cell(1, height).append('Total').css('font-weight', 'bold'));
        }

        _.each(header_cells, function (cells) {
            self.table.append($('<tr></tr>').append(cells));
        });
    },

    draw_row: function (row) {
        var self = this,
            pivot = this.pivot_table,
            html_row = $('<tr></tr>'),
            row_header = this.make_border_cell(1,1)
                .append(this.make_header_title(row).attr('data-id', row.id))
                .addClass('graph_border');

        for (var i in _.range(row.path.length)) {
            row_header.prepend($('<span/>', {class:'web_graph_indent'}));
        }

        html_row.append(row_header);

        _.each(pivot.cols.headers, function (col) {
            if (col.children.length === 0) {
                var value = pivot.get_value(row.id, col.id),
                    cell = $('<td></td>');

                cell.append((value === undefined) ? '' : value);
                if ((self.mode == 'heatmap') && (value !== undefined)) {
                    var color = Math.floor(50 + 205*(pivot.total - value)/pivot.total);
                    cell.css('background-color', 'rgb(255,' + color + ',' + color + ')');
                }
                if (row.is_expanded && (row.path.length <= 2)) {
                    var color = row.path.length *   5 + 240;
                    cell.css('background-color', 'rgb(' + [color, color, color].join() + ')');
                }
                html_row.append(cell);
            }
        });
        var total = pivot.get_value(row.id, pivot.cols.main.id);
        var cell = $('<td></td>')
            .append(total)
            .css('font-weight', 'bold');
        if (row.is_expanded && (row.path.length <= 2)) {
            var color = row.path.length *   5 + 240;
            cell.css('background-color', 'rgb(' + [color, color, color].join() + ')');
        } else if (self.heat_map_mode) {
            var color = Math.floor(50 + 205*(pivot.total - total)/pivot.total);
            cell.css('background-color', 'rgb(255,' + color + ',' + color + ')');
        }

        if (pivot.cols.main.children.length > 0) {
            html_row.append(cell);
        }

        this.table.append(html_row);
    }
});

};
