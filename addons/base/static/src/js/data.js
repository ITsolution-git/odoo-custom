
openerp.base.data = function(openerp) {

/**
 * Serializes the sort criterion array of a dataset into a form which can be
 * consumed by OpenERP's RPC APIs.
 *
 * @param {Array} criterion array of fields, from first to last criteria, prefixed with '-' for reverse sorting
 * @returns {String} SQL-like sorting string (``ORDER BY``) clause
 */
openerp.base.serialize_sort = function (criterion) {
    return _.map(criterion,
        function (criteria) {
            if (criteria[0] === '-') {
                return criteria.slice(1) + ' DESC';
            }
            return criteria + ' ASC';
        }).join(', ');
};

openerp.base.DataGroup =  openerp.base.Controller.extend( /** @lends openerp.base.DataGroup# */{
    /**
     * Management interface between views and grouped collections of OpenERP
     * records.
     *
     * The root DataGroup is instantiated with the relevant information
     * (a session, a model, a domain, a context and a group_by sequence), the
     * domain and context may be empty. It is then interacted with via
     * :js:func:`~openerp.base.DataGroup.list`, which is used to read the
     * content of the current grouping level.
     *
     * @constructs
     * @extends openerp.base.Controller
     *
     * @param {openerp.base.Session} session Current OpenERP session
     * @param {String} model name of the model managed by this DataGroup
     * @param {Array} domain search domain for this DataGroup
     * @param {Object} context context of the DataGroup's searches
     * @param {Array} group_by sequence of fields by which to group
     * @param {Number} [level=0] nesting level of the group
     */
    init: function(session, model, domain, context, group_by, level) {
        if (group_by) {
            if (group_by.length || context['group_by_no_leaf']) {
                return new openerp.base.ContainerDataGroup(
                        session, model, domain, context, group_by, level);
            } else {
                return new openerp.base.GrouplessDataGroup(
                        session, model, domain, context, level);
            }
        }

        this._super(session, null);
        this.model = model;
        this.context = context;
        this.domain = domain;

        this.level = level || 0;
    },
    cls: 'DataGroup'
});
openerp.base.ContainerDataGroup = openerp.base.DataGroup.extend(
    /** @lends openerp.base.ContainerDataGroup# */ {
    /**
     *
     * @constructs
     * @extends openerp.base.DataGroup
     *
     * @param session
     * @param model
     * @param domain
     * @param context
     * @param group_by
     * @param level
     */
    init: function (session, model, domain, context, group_by, level) {
        this._super(session, model, domain, context, null, level);

        this.group_by = group_by;
    },
    /**
     * The format returned by ``read_group`` is absolutely dreadful:
     *
     * * A ``__context`` key provides future grouping levels
     * * A ``__domain`` key provides the domain for the next search
     * * The current grouping value is provided through the name of the
     *   current grouping name e.g. if currently grouping on ``user_id``, then
     *   the ``user_id`` value for this group will be provided through the
     *   ``user_id`` key.
     * * Similarly, the number of items in the group (not necessarily direct)
     *   is provided via ``${current_field}_count``
     * * Other aggregate fields are just dumped there
     *
     * This function slightly improves the grouping records by:
     *
     * * Adding a ``grouped_on`` property providing the current grouping field
     * * Adding a ``value`` and a ``length`` properties which replace the
     *   ``$current_field`` and ``${current_field}_count`` ones
     * * Moving aggregate values into an ``aggregates`` property object
     *
     * Context and domain keys remain as-is, they should not be used externally
     * but in case they're needed...
     *
     * @param {Object} group ``read_group`` record
     */
    transform_group: function (group) {
        var field_name = this.group_by[0];
        // In cases where group_by_no_leaf and no group_by, the result of
        // read_group has aggregate fields but no __context or __domain.
        // Create default (empty) values for those so that things don't break
        var fixed_group = _.extend(
                {__context: {group_by: []}, __domain: []},
                group);

        var aggregates = {};
        _(fixed_group).each(function (value, key) {
            if (key.indexOf('__') === 0
                    || key === field_name
                    || key === field_name + '_count') {
                return;
            }
            aggregates[key] = value || 0;
        });

        return {
            __context: fixed_group.__context,
            __domain: fixed_group.__domain,

            grouped_on: field_name,
            // if terminal group (or no group) and group_by_no_leaf => use group.__count
            length: fixed_group[field_name + '_count'] || fixed_group.__count,
            value: fixed_group[field_name],

            openable: !(this.context['group_by_no_leaf']
                       && fixed_group.__context.group_by.length === 0),

            aggregates: aggregates
        };
    },
    fetch: function (fields) {
        // internal method
        var d = new $.Deferred();
        var self = this;

        this.rpc('/base/group/read', {
            model: this.model,
            context: this.context,
            domain: this.domain,
            fields: _.uniq(this.group_by.concat(fields)),
            group_by_fields: this.group_by,
            sort: openerp.base.serialize_sort(this.sort)
        }, function () { }).then(function (response) {
            var data_groups = _(response).map(
                    _.bind(self.transform_group, self));
            self.groups = data_groups;
            d.resolveWith(self, [data_groups]);
        }, function () {
            d.rejectWith.apply(d, [self, arguments]);
        });
        return d.promise();
    },
    /**
     * The items of a list have the following properties:
     *
     * ``length``
     *     the number of records contained in the group (and all of its
     *     sub-groups). This does *not* provide the size of the "next level"
     *     of the group, unless the group is terminal (no more groups within
     *     it).
     * ``grouped_on``
     *     the name of the field this level was grouped on, this is mostly
     *     used for display purposes, in order to know the name of the current
     *     level of grouping. The ``grouped_on`` should be the same for all
     *     objects of the list.
     * ``value``
     *     the value which led to this group (this is the value all contained
     *     records have for the current ``grouped_on`` field name).
     * ``aggregates``
     *     a mapping of other aggregation fields provided by ``read_group``
     *
     * @param {Array} fields the list of fields to aggregate in each group, can be empty
     * @param {Function} ifGroups function executed if any group is found (DataGroup.group_by is non-null and non-empty), called with a (potentially empty) list of groups as parameters.
     * @param {Function} ifRecords function executed if there is no grouping left to perform, called with a DataSet instance as parameter
     */
    list: function (fields, ifGroups, ifRecords) {
        var self = this;
        this.fetch(fields).then(function (group_records) {
            ifGroups(_(group_records).map(function (group) {
                var child_context = _.extend({}, self.context, group.__context);
                return _.extend(
                    new openerp.base.DataGroup(
                        self.session, self.model, group.__domain,
                        child_context, child_context.group_by,
                        self.level + 1),
                    group, {sort: self.sort});
            }));
        });
    }
});
openerp.base.GrouplessDataGroup = openerp.base.DataGroup.extend(
    /** @lends openerp.base.GrouplessDataGroup# */ {
    /**
     *
     * @constructs
     * @extends openerp.base.DataGroup
     *
     * @param session
     * @param model
     * @param domain
     * @param context
     * @param level
     */
    init: function (session, model, domain, context, level) {
        this._super(session, model, domain, context, null, level);
    },
    list: function (fields, ifGroups, ifRecords) {
        ifRecords(_.extend(
            new openerp.base.DataSetSearch(this.session, this.model),
            {domain: this.domain, context: this.context, _sort: this.sort}));
    }
});

openerp.base.StaticDataGroup = openerp.base.GrouplessDataGroup.extend(
    /** @lends openerp.base.StaticDataGroup# */ {
    /**
     * A specialization of groupless data groups, relying on a single static
     * dataset as its records provider.
     *
     * @constructs
     * @extends openerp.base.GrouplessDataGroup
     * @param {openep.base.DataSetStatic} dataset a static dataset backing the groups
     */
    init: function (dataset) {
        this.dataset = dataset;
    },
    list: function (fields, ifGroups, ifRecords) {
        ifRecords(this.dataset);
    }
});

openerp.base.DataSet =  openerp.base.Controller.extend( /** @lends openerp.base.DataSet# */{
    /**
     * DateaManagement interface between views and the collection of selected
     * OpenERP records (represents the view's state?)
     *
     * @constructs
     * @extends openerp.base.Controller
     *
     * @param {openerp.base.Session} session current OpenERP session
     * @param {String} model the OpenERP model this dataset will manage
     */
    init: function(session, model, context) {
        this._super(session);
        this.model = model;
        this.context = context || {};
        this.index = null;
    },
    start: function() {
    },
    previous: function () {
        this.index -= 1;
        if (this.index < 0) {
            this.index = this.ids.length - 1;
        }
        return this;
    },
    next: function () {
        this.index += 1;
        if (this.index >= this.ids.length) {
            this.index = 0;
        }
        return this;
    },
    /**
     * Read records.
     */
    read_ids: function (ids, fields, callback) {
        var self = this;
        return this.rpc('/base/dataset/get', {
            model: this.model,
            ids: ids,
            fields: fields,
            context: this.get_context()
        }, callback);
    },
    /**
     * Read a slice of the records represented by this DataSet, based on its
     * domain and context.
     *
     * @param {Number} [offset=0] The index from which selected records should be returned
     * @param {Number} [limit=null] The maximum number of records to return
     */
    read_slice: function (fields, offset, limit, callback) {
    },
    /**
     * Read the indexed record.
     */
    read_index: function (fields, callback) {
        if (_.isEmpty(this.ids)) {
            return $.Deferred().reject().promise();
        } else {
            fields = fields || false;
            return this.read_ids([this.ids[this.index]], fields, function(records) {
                callback(records[0]);
            });
        }
    },
    default_get: function(fields, callback) {
        return this.rpc('/base/dataset/default_get', {
            model: this.model,
            fields: fields,
            context: this.get_context()
        }, callback);
    },
    create: function(data, callback, error_callback) {
        return this.rpc('/base/dataset/create', {
            model: this.model,
            data: data,
            context: this.get_context()
        }, callback, error_callback);
    },
    write: function (id, data, callback) {
        return this.rpc('/base/dataset/save', {
            model: this.model,
            id: id,
            data: data,
            context: this.get_context()
        }, callback);
    },
    unlink: function(ids, callback, error_callback) {
        var self = this;
        return this.call_and_eval("unlink", [ids, this.get_context()], null, 1,
            callback, error_callback);
    },
    call: function (method, args, callback, error_callback) {
        return this.rpc('/base/dataset/call', {
            model: this.model,
            method: method,
            args: args || []
        }, callback, error_callback);
    },
    call_and_eval: function (method, args, domain_id, context_id, callback, error_callback) {
        return this.rpc('/base/dataset/call', {
            model: this.model,
            method: method,
            domain_id: domain_id || null,
            context_id: context_id || null,
            args: args || []
        }, callback, error_callback);
    },
    call_button: function (method, args, callback, error_callback) {
        return this.rpc('/base/dataset/call_button', {
            model: this.model,
            method: method,
            domain_id: null,
            context_id: 1,
            args: args || []
        }, callback, error_callback);
    },
    name_get: function(ids, callback) {
        return this.call_and_eval('name_get', [ids, this.get_context()], null, 1, callback);
    },
    /*
     * args = domain
     */
    name_search: function (name, args, operator, limit, callback) {
        return this.call_and_eval('name_search',
            [name || '', args || false, operator || 'ilike', this.get_context(), limit || 100],
            1, 3, callback);
    },
    name_create: function(name, callback) {
        return this.call_and_eval('name_create', [name, this.get_context()], null, 1, callback);
    },
    exec_workflow: function (id, signal, callback) {
        return this.rpc('/base/dataset/exec_workflow', {
            model: this.model,
            id: id,
            signal: signal
        }, callback);
    },
    get_context: function() {
        return this.context;
    }
});

openerp.base.DataSetStatic =  openerp.base.DataSet.extend({
    init: function(session, model, context, ids) {
        this._super(session, model, context);
        // all local records
        this.ids = ids || [];
    },
    read_slice: function (fields, offset, limit, callback) {
        var self = this;
        offset = offset || 0;
        var end_pos = limit && limit !== -1 ? offset + limit : undefined;
        return this.read_ids(this.ids.slice(offset, end_pos), fields, callback);
    },
    set_ids: function (ids) {
        this.ids = ids;
        if (this.index !== null) {
            this.index = this.index <= this.ids.length - 1 ?
                this.index : (this.ids.length > 0 ? this.length - 1 : 0);
        }
    },
    unlink: function(ids) {
        this.on_unlink(ids);
        return $.Deferred().resolve({result: true});
    },
    on_unlink: function(ids) {
        this.set_ids(_.without.apply(null, [this.ids].concat(ids)));
    }
});

openerp.base.DataSetSearch =  openerp.base.DataSet.extend({
    init: function(session, model, context, domain) {
        this._super(session, model, context);
        this.domain = domain || [];
        this._sort = [];
        this.offset = 0;
        // subset records[offset:offset+limit]
        // is it necessary ?
        this.ids = [];
    },
    read_slice: function (fields, offset, limit, callback) {
        var self = this;
        offset = offset || 0;
        // cached search, not sure it's a good idea
        if(this.offset <= offset) {
            var start = offset - this.offset;
            if(this.ids.length - start >= limit) {
                // TODO: check if this could work do only read if possible
                // return read_ids(ids.slice(start,start+limit),fields,callback)
            }
        }
        return this.rpc('/base/dataset/search_read', {
            model: this.model,
            fields: fields,
            domain: this.domain,
            context: this.get_context(),
            sort: this.sort(),
            offset: offset,
            limit: limit
        }, function (result) {
            self.ids = result.ids;
            self.offset = offset;
            if (callback) {
                callback(result.records);
            }
        });
    },
    /**
     * Reads or changes sort criteria on the dataset.
     *
     * If not provided with any argument, serializes the sort criteria to
     * an SQL-like form usable by OpenERP's ORM.
     *
     * If given a field, will set that field as first sorting criteria or,
     * if the field is already the first sorting criteria, will reverse it.
     *
     * @param {String} [field] field to sort on, reverses it (toggle from ASC to DESC) if already the main sort criteria
     * @param {Boolean} [force_reverse=false] forces inserting the field as DESC
     * @returns {String|undefined}
     */
    sort: function (field, force_reverse) {
        if (!field) {
            return openerp.base.serialize_sort(this._sort);
        }
        var reverse = force_reverse || (this._sort[0] === field);
        this._sort.splice.apply(
            this._sort, [0, this._sort.length].concat(
                _.without(this._sort, field, '-' + field)));

        this._sort.unshift((reverse ? '-' : '') + field);
        return undefined;
    },
    unlink: function(ids, callback, error_callback) {
        var self = this;
        return this._super(ids, function(result) {
            self.ids = _.without.apply(_, [self.ids].concat(ids));
            if (this.index !== null) {
                self.index = self.index <= self.ids.length - 1 ?
                    self.index : (self.ids.length > 0 ? self.ids.length -1 : 0);
            }
            if (callback)
                callback(result);
        }, error_callback);
    }
});

openerp.base.BufferedDataSet = openerp.base.DataSetStatic.extend({
    virtual_id_prefix: "one2many_v_id_",
    virtual_id_regex: /one2many_v_id_.*/,
    debug_mode: true,
    init: function() {
        this._super.apply(this, arguments);
        this.reset_ids([]);
    },
    create: function(data, callback, error_callback) {
        var cached = {id:_.uniqueId(this.virtual_id_prefix), values: data};
        this.to_create.push(cached);
        this.cache.push(cached);
        var to_return =  $.Deferred().then(callback);
        setTimeout(function() {to_return.resolve({result: cached.id});}, 0);
        return to_return.promise();
    },
    write: function (id, data, callback) {
        var self = this;
        var record = _.detect(this.to_create, function(x) {return x.id === id;});
        record = record || _.detect(this.to_write, function(x) {return x.id === id;});
        if (record) {
            $.extend(record.values, data);
        } else {
            record = {id: id, values: data};
            self.to_write.push(record);
        }
        var cached = _.detect(this.cache, function(x) {return x.id === id;});
        $.extend(cached.values, record.values);
        this.on_change();
        var to_return = $.Deferred().then(callback);
        setTimeout(function () {to_return.resolve({result: true});}, 0);
        return to_return.promise();
    },
    unlink: function(ids, callback, error_callback) {
        var self = this;
        _.each(ids, function(id) {
            if (! _.detect(self.to_create, function(x) { return x.id === id; })) {
                self.to_delete.push({id: id})
            }
        });
        this.to_create = _.reject(this.to_create, function(x) { return _.include(ids, x.id);});
        this.to_write = _.reject(this.to_write, function(x) { return _.include(ids, x.id);});
        this.cache = _.reject(this.cache, function(x) { return _.include(ids, x.id);});
        this.set_ids(_.without.apply(_, [this.ids].concat(ids)));
        this.on_change();
        var to_return = $.Deferred().then(callback);
        setTimeout(function () {to_return.resolve({result: true});}, 0);
        return to_return.promise();
    },
    reset_ids: function(ids) {
        this.set_ids(ids);
        this.to_delete = [];
        this.to_create = [];
        this.to_write = [];
        this.cache = [];
        this.delete_all = false;
    },
    on_change: function() {},
    read_ids: function (ids, fields, callback) {
        var self = this;
        var to_get = [];
        _.each(ids, function(id) {
            var cached = _.detect(self.cache, function(x) {return x.id === id;});
            var created = _.detect(self.to_create, function(x) {return x.id === id;});
            if (created) {
                _.each(fields, function(x) {if (cached.values[x] === undefined) cached.values[x] = false;});
            } else {
                if (!cached || !_.all(fields, function(x) {return cached.values[x] !== undefined}))
                    to_get.push(id);
            }
        });
        var completion = $.Deferred().then(callback);
        var return_records = function() {
            var records = _.map(ids, function(id) {
                return _.extend({}, _.detect(self.cache, function(c) {return c.id === id;}).values, {"id": id});
            });
            if (self.debug_mode) {
                if (_.include(records, undefined)) {
                    throw "Record not correctly loaded";
                }
            }
            setTimeout(function () {completion.resolve(records);}, 0);
        }
        if(to_get.length > 0) {
            var rpc_promise = this._super(to_get, fields, function(records) {
                _.each(records, function(record, index) {
                    var id = to_get[index];
                    var cached = _.detect(self.cache, function(x) {return x.id === id;});
                    if (!cached) {
                        self.cache.push({id: id, values: record});
                    } else {
                        // I assume cache value is prioritary
                        _.defaults(cached.values, record);
                    }
                });
                return_records();
            });
            $.when(rpc_promise).fail(function() {completion.reject();});
        } else {
            return_records();
        }
        return completion.promise();
    }
});

openerp.base.ReadOnlyDataSetSearch = openerp.base.DataSetSearch.extend({
    create: function(data, callback, error_callback) {
        this.on_create(data);
        var to_return = $.Deferred().then(callback);
        setTimeout(function () {to_return.resolve({"result": undefined});}, 0);
        return to_return.promise();
    },
    on_create: function(data) {},
    write: function (id, data, callback) {
        this.on_write(id, data);
        var to_return = $.Deferred().then(callback);
        setTimeout(function () {to_return.resolve({"result": true});}, 0);
        return to_return.promise();
    },
    on_write: function(id, data) {},
    unlink: function(ids, callback, error_callback) {
        this.on_unlink(ids);
        var to_return = $.Deferred().then(callback);
        setTimeout(function () {to_return.resolve({"result": true});}, 0);
        return to_return.promise();
    },
    on_unlink: function(ids) {}
});

openerp.base.CompoundContext = function() {
    this.__ref = "compound_context";
    this.__contexts = [];
    this.__eval_context = null;
    var self = this;
    _.each(arguments, function(x) {
        self.add(x);
    });
};
openerp.base.CompoundContext.prototype.add = function(context) {
    this.__contexts.push(context);
    return this;
};
openerp.base.CompoundContext.prototype.set_eval_context = function(eval_context) {
    this.__eval_context = eval_context;
    return this;
};
openerp.base.CompoundContext.prototype.get_eval_context = function() {
    return this.__eval_context;
};

openerp.base.CompoundDomain = function() {
    this.__ref = "compound_domain";
    this.__domains = [];
    this.__eval_context = null;
    var self = this;
    _.each(arguments, function(x) {
        self.add(x);
    });
};
openerp.base.CompoundDomain.prototype.add = function(domain) {
    this.__domains.push(domain);
    return this;
};
openerp.base.CompoundDomain.prototype.set_eval_context = function(eval_context) {
    this.__eval_context = eval_context;
    return this;
};
openerp.base.CompoundDomain.prototype.get_eval_context = function() {
    return this.__eval_context;
};

};

// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax:
