
/* jshint undef: false  */

(function () {
'use strict';

openerp.web_graph.PivotTable = openerp.web.Class.extend(openerp.EventDispatcherMixin, {

	// PivotTable require a 'update_data' after init to be ready
	// to do: add an option to enable/disable update_data at the end of init
	init: function (model, domain) {
        openerp.EventDispatcherMixin.init.call(this);
		this.rows = { groupby: [], main: null, headers: null };
		this.cols = { groupby: [], main: null, headers: null };
		this.cells = [];
		this.domain = domain;
		this.measures = ['__count'];

		this.data_loader = new openerp.web_graph.DataLoader(model);

		this.no_data = true;
	},

	visible_fields: function () {
		var result = this.rows.groupby.concat(this.cols.groupby, this.measures);
		return _.without(result, '__count');
	},

	config: function (options) {
		var changed = false;
		var groupby_changed = false;
		var default_options = {
				update:true,
				domain:this.domain,
				col_groupby: this.cols.groupby,
				row_groupby: this.rows.groupby,
				measures: this.measures,
				silent:false
			};
		options = _.extend(default_options, options);

		if (options.fields) {
			this.data_loader.fields = options.fields;
		}

		if (!_.isEqual(options.domain, this.domain)) {
			this.domain = options.domain;
			changed = true;
		}
		if (!_.isEqual(options.measures, this.measures)) {
			this.measures = options.measures;
			changed = true;
		}
		if (!_.isEqual(options.col_groupby, this.cols.groupby)) {
			this.cols.groupby = options.col_groupby;
			changed = true;
			this.cols.headers = null;
			groupby_changed = true;
		}
		if (!_.isEqual(options.row_groupby, this.rows.groupby)) {
			this.rows.groupby = options.row_groupby;
			this.rows.headers = null;
			changed = true;
			groupby_changed = true;
		}

		if (!options.silent && groupby_changed) { this.trigger('groupby_changed'); }
		if (options.update && changed) { this.update_data(); }
	},

	set_value: function (id1, id2, values) {
		var x = Math.min(id1, id2),
			y = Math.max(id1, id2),
			cell = _.find(this.cells, function (c) {
			return ((c.x == x) && (c.y == y));
		});
		if (cell) {
			cell.values = values;
		} else {
			this.cells.push({x: x, y: y, values: values});
		}
	},

	get_value: function (id1, id2, default_values) {
		var x = Math.min(id1, id2),
			y = Math.max(id1, id2),
			cell = _.find(this.cells, function (c) {
			return ((c.x == x) && (c.y == y));
		});
		return (cell === undefined) ? default_values : cell.values;
	},

	is_row: function (id) {
		return !!_.find(this.rows.headers, function (header) {
			return header.id == id;
		});
	},

	is_col: function (id) {
		return !!_.find(this.cols.headers, function (header) {
			return header.id == id;
		});
	},

	get_header: function (id) {
		return _.find(this.rows.headers.concat(this.cols.headers), function (header) {
			return header.id == id;
		});
	},

	// return all columns with a path length of 'depth'
	get_columns_depth: function (depth) {
		return _.filter(this.cols.headers, function (hdr) {
			return hdr.path.length === depth;
		});
	},

	// return all rows with a path length of 'depth'
	get_rows_depth: function (depth) {
		return _.filter(this.rows.headers, function (hdr) {
			return hdr.path.length === depth;
		});
	},

	// return all non expanded rows
	get_rows_leaves: function () {
		return _.filter(this.rows.headers, function (hdr) {
			return !hdr.is_expanded;
		});
	},
	
	// return all non expanded cols
	get_cols_leaves: function () {
		return _.filter(this.cols.headers, function (hdr) {
			return !hdr.is_expanded;
		});
	},
	
	fold: function (header) {
		var list = [];
		function tree_traversal(tree) {
			list.push(tree);
			_.each(tree.children, tree_traversal);
		}
		tree_traversal(header);
		var ids_to_remove = _.map(_.rest(list), function (h) { return h.id;});

		header.root.headers = _.difference(header.root.headers, _.rest(list));
		header.is_expanded = false;
        var fold_lvls = _.map(header.root.headers, function(g) {return g.path.length;});
        var new_groupby_length = _.max(fold_lvls);

        header.children = [];
        this.cells = _.reject(this.cells, function (cell) {
            return (_.contains(ids_to_remove, cell.x) || _.contains(ids_to_remove, cell.y));
        });
        if (new_groupby_length < header.root.groupby.length) {
			header.root.groupby.splice(new_groupby_length);
			this.trigger('groupby_changed');
        }
        this.trigger('redraw_required');
	},

	expand: function (header_id, field_id) {
        var self = this,
            header = this.get_header(header_id);

        if (header.path.length == header.root.groupby.length) {
            header.root.groupby.push(field_id);
            this.trigger('groupby_changed');
        }

        var otherDim = (header.root === this.cols) ? this.rows : this.cols;
        return this.data_loader.get_groups(this.visible_fields(), header.domain, otherDim.groupby, {first_groupby:field_id, add_path:true})
            .then(function (groups) {
                _.each(groups.reverse(), function (group) {
                    var new_header_id = self.make_header(group, header);
                    _.each(group, function (data) {
						var other = _.find(otherDim.headers, function (h) {
							if (header.root === self.cols) {
								return _.isEqual(data.path.slice(1), h.path);
                            } else {
                                return _.isEqual(_.rest(data.path), h.path);
                            }
                        });
                        if (other) {
							self.set_value(new_header_id, other.id, _.map(self.measures, function (measure) {
								return (measure === '__count') ? data.attributes.length : data.attributes.aggregates[measure];
							}));
                        }
                    });
                });
                header.is_expanded = true;
                self.trigger('redraw_required');
            });
	},

	make_header: function (groups, parent) {
		var name = groups[0].attributes.value,
            new_header = {
				id: _.uniqueId(),
				path: parent.path.concat(name),
				title: name,
				is_expanded: false,
				parent: parent.id,
				children: [],
				domain: groups[0].model._domain,
				root: parent.root,
			};
		parent.children.splice(0,0, new_header);
		parent.root.headers.splice(parent.root.headers.indexOf(parent) + 1, 0, new_header);
		return new_header.id;
	},

	swap_axis: function () {
		var temp = this.rows;
		this.rows = this.cols;
		this.cols = temp;
		this.trigger('groupby_changed');
		this.trigger('redraw_required');
	},

	get_total: function (header) {
		if (header) {
			var main = (header.root === this.rows) ? this.cols.main : this.rows.main;
			return this.get_value(header.id, main.id);
		} else {
			return this.rows.main.total;
		}
	},

	update_data: function () {
		var self = this,
			options = {
				col_groupby: this.cols.groupby,
				row_groupby: this.rows.groupby,
				measures: this.measures,
				domain: this.domain,
			};

		return this.data_loader.load_data(options).then (function (result) {
			if (result) {
				self.no_data = false;
				if (self.cols.headers) {
					self.update_headers(self.cols, result.col_headers);
				} else {
					self.expand_headers(self.cols, result.col_headers);
				}
				if (self.rows.headers) {
					self.update_headers(self.rows, result.row_headers);
				} else {
					self.expand_headers(self.rows, result.row_headers);
				}
				self.cells = result.cells;
			} else {
				self.no_data = true;
			}
			self.trigger('redraw_required');
		});
	},

	expand_headers: function (root, new_headers) {
		root.headers = new_headers;
		root.main = new_headers[0];
		_.each(root.headers, function (header) {
			header.root = root;
			header.is_expanded = (header.children.length > 0);
		});
	},

	update_headers: function (root, new_headers) {
		_.each(root.headers, function (header) {
			var corresponding_header = _.find(new_headers, function (h) {
				return _.isEqual(h.path, header.path);
			});
			if (corresponding_header && (header.is_expanded)) {
				corresponding_header.is_expanded = true;
				_.each(corresponding_header.children, function (c) {
					c.is_expanded = false;
				});
			}
			if (corresponding_header && (!header.is_expanded)) {
				corresponding_header.is_expanded = false;
			}
		});
		var updated_headers = _.filter(new_headers, function (header) {
			return (header.is_expanded !== undefined);
		});
		_.each(updated_headers, function (hdr) {
			if (!hdr.is_expanded) {
				hdr.children = [];
			}
			hdr.root = root;
		});
		root.headers = updated_headers;
		root.main = root.headers[0];
	},

});

openerp.web_graph.DataLoader = openerp.web.Class.extend({
	init: function (model) {
		this.model = model;
		this.fields = null;
	},

	get_groups: function (fields, domain, groupbys, options) {
		var self = this,
			groupings = ((options || {}).first_groupby) ? [(options || {}).first_groupby].concat(groupbys) : groupbys;

		return this.query_db(fields, domain, groupings).then(function (groups) {
			return _.map(groups, function (group) {
				return ((options || {}).add_path) ? self.add_path(group, []) : group;
			});
		});

	},

	query_db: function (fields, domain, groupbys) {
		var self = this;
		return this.model.query(fields)
			.filter(domain)
			.group_by(groupbys)
			.then(function (results) {
				var non_empty_results = _.filter(results, function (group) {
					return group.attributes.length > 0;
				});
				_.each(non_empty_results, self.sanitize_value.bind(self));
				if (groupbys.length <= 1) {
					return non_empty_results;
				} else {
					var get_subgroups = $.when.apply(null, _.map(non_empty_results, function (result) {
						var new_domain = result.model._domain;
						var new_groupings = groupbys.slice(1);
						return self.query_db(fields,new_domain, new_groupings).then(function (subgroups) {
							result.subgroups_data = subgroups;
						});
					}));
					return get_subgroups.then(function () {
						return non_empty_results;
					});
				}
			});
	},

	sanitize_value: function (group) {
		var value = group.attributes.value;

		if (this.fields &&
			group.attributes.grouped_on &&
			this.fields[group.attributes.grouped_on].type === 'selection') {
			var selection = this.fields[group.attributes.grouped_on].selection;
			var value_lookup = _.find(selection, function (val) {
				return val[0] === value;
			});
			group.attributes.value = (value_lookup) ? value_lookup[1] : 'undefined';
			return;
		}
		if (value === false) {
			group.attributes.value = 'undefined';
		} else if (value instanceof Array) {
			group.attributes.value = value[1];
		} else {
			group.attributes.value = value;
		}
	},

	add_path: function (group, current_path) {
		var self = this;

		group.path = current_path.concat(group.attributes.value);
		var result = [group];
		_.each(group.subgroups_data, function (subgroup) {
			result = result.concat(self.add_path(subgroup, group.path));
		});
		return result;
	},

	// To obtain all the values required to draw the full table, we have to do 
	// at least      2 + min(row.groupby.length, col.groupby.length)
	// calls to readgroup. To simplify the code, we will always do 
	// 2 + row.groupby.length calls. For example, if row.groupby = [r1, r2, r3] 
	// and col.groupby = [c1, c2], then we will make the call with the following 
	// groupbys: [r1,r2,r3], [c1,r1,r2,r3], [c1,c2,r1,r2,r3], [].
	load_data: function (options) {
		var self = this,
			cols = options.col_groupby,
			rows = options.row_groupby,
			visible_fields = _.without(rows.concat(cols, options.measures), '__count');

		// if (options.measure) { visible_fields = visible_fields.concat(options.measure); }

		var groupbys = _.map(_.range(cols.length + 1), function (i) {
			return cols.slice(0, i).concat(rows);
		});
		groupbys.push([]);

		var def_array = _.map(groupbys, function (groupby) {
			return self.get_groups(visible_fields, options.domain, groupby);
		});

		return $.when.apply(null, def_array).then(function () {
			var data = Array.prototype.slice.call(arguments),
				row_data = data[0],
				col_data = (cols.length !== 0) ? data[data.length - 2] : [],
				total = data[data.length - 1][0];

			options.total = total;
			return (total === undefined) ? undefined
                    : self.format_data(total, col_data, row_data, data, options);
		});
	},

	get_value: function (data, measures) {
		var attr = data.attributes;
		var result = _.map(measures, function (measure) {
			return (measure === '__count') ? attr.length : attr.aggregates[measure];
		});
		return result;
		// return (measure) ? attr.aggregates[measure] : attr.length;
	},

	format_data: function (total, col_data, row_data, cell_data, options) {
		var self = this,
			dim_row = options.row_groupby.length,
			dim_col = options.col_groupby.length,
			col_headers = make_list(this.make_headers(col_data, dim_col, options)),
			row_headers = make_list(this.make_headers(row_data, dim_row, options)),
			cells = [];

		_.each(cell_data, function (data, index) {
			self.make_cells(data, index, [], cells, row_headers, col_headers, options);
		}); // make it more functional?

		return {col_headers: col_headers,
                row_headers: row_headers,
                cells: cells};

        function make_list (tree) {
			return [].concat.apply([tree], _.map(tree.children, make_list));
        }
	},

	make_headers: function (data, depth, options, parent) {
		var self = this,
			main = {
				id: _.uniqueId(),
				path: (parent) ? parent.path.concat(data.attributes.value) : [],
				parent: parent,
				children: [],
				title: (parent) ? data.attributes.value : '',
				domain: (parent) ? data.model._domain : options.domain,
				total: this.get_value(options.total, options.measures),
			};

		if (main.path.length < depth) {
			main.children = _.map(data.subgroups_data || data, function (data_pt) {
				return self.make_headers (data_pt, depth, options, main);
			});
		}
		return main;
	},

	make_cells: function (data, index, current_path, current_cells, rows, cols, options) {
		var self = this;
		_.each(data, function (group) {
			var attr = group.attributes,
				group_val = (attr.value instanceof Array) ? attr.value[1] : attr.value,
				path = current_path,
				values = _.map(options.measures, function (measure) {
					return (measure === '__count') ? attr.length : attr.aggregates[measure];
				});

			group_val = (group_val === false) ? undefined : group_val;

			if (attr.grouped_on !== undefined) {
				path = path.concat((attr.value === false) ? 'undefined' : group_val);
			}
			var row = _.find(rows, function (header) {
				return _.isEqual(header.path, path.slice(index));
			});
			var col = _.find(cols, function (header) {
				return _.isEqual(header.path, path.slice(0, index));
			});
			current_cells.push({x: Math.min(row.id, col.id),
						y: Math.max(row.id, col.id),
						values: values});

			if (attr.has_children) {
				self.make_cells (group.subgroups_data, index, path, current_cells, rows, cols, options);
			}
		});
	},

});

})();