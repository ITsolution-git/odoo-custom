
openerp.base.data = function(openerp) {

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
    fetch: function () {
        // internal method
        var d = new $.Deferred();
        var self = this;

        // disable caching for now, not sure what I should do there
        if (false && this.groups) {
            d.resolveWith(this, [this.groups]);
        } else {
            this.rpc('/base/group/read', {
                model: this.model,
                context: this.context,
                domain: this.domain,
                group_by_fields: this.group_by
            }, function () { }).then(function (response) {
                var data_groups = _(response.result).map(
                        _.bind(self.transform_group, self));
                self.groups = data_groups;
                d.resolveWith(self, [data_groups]);
            }, function () {
                d.rejectWith.apply(d, self, [arguments]);
            });
        }
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
     */
    list: function (ifGroups, ifRecords) {
        var self = this;
        this.fetch().then(function (group_records) {
            ifGroups(_(group_records).map(function (group) {
                var child_context = _.extend({}, self.context, group.__context);
                return _.extend(
                    new openerp.base.DataGroup(
                        self.session, self.model, group.__domain,
                        child_context, child_context.group_by,
                        self.level + 1),
                    group);
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
    list: function (ifGroups, ifRecords) {
        ifRecords(_.extend(
                new openerp.base.DataSetSearch(this.session, this.model),
                {domain: this.domain, context: this.context}));
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
    list: function (ifGroups, ifRecords) {
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
        this.index = 0;
        this.count = 0;
    },
    start: function() {
    },
    previous: function () {
        this.index -= 1;
        if (this.index < 0) {
            this.index = this.count - 1;
        }
        return this;
    },
    next: function () {
        this.index += 1;
        if (this.index >= this.count) {
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
            fields: fields
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
    default_get: function(fields, context, callback) {
        context = context || this.context;
        return this.rpc('/base/dataset/default_get', {
            model: this.model,
            fields: fields,
            context: context
        }, callback);
    },
    create: function(data, callback, error_callback) {
        return this.rpc('/base/dataset/create', {
            model: this.model,
            data: data,
            context: this.context
        }, callback, error_callback);
    },
    write: function (id, data, callback) {
        return this.rpc('/base/dataset/save', {
            model: this.model,
            id: id,
            data: data,
            context: this.context
        }, callback);
    },
    unlink: function(ids) {
        // to implement in children
        this.notification.notify("Unlink", ids);
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
    /**
     * Arguments:
     * name='', args=[], operator='ilike', context=None, limit=100
     */
    name_search: function (args, callback, error_callback) {
        return this.call_and_eval('name_search',
            args, 1, 3,
            callback, error_callback);
    },
    exec_workflow: function (id, signal, callback) {
        return this.rpc('/base/dataset/exec_workflow', {
            model: this.model,
            id: id,
            signal: signal
        }, callback);
    }
});

openerp.base.DataSetStatic =  openerp.base.DataSet.extend({
    init: function(session, model, ids) {
        this._super(session, model);
        // all local records
        this.ids = ids || [];
        this.count = this.ids.length;
    },
    read_slice: function (fields, offset, limit, callback) {
        var end_pos = limit && limit !== -1 ? offset + limit : undefined;
        this.read_ids(this.ids.slice(offset, end_pos), fields, callback);
    },
    set_ids: function (ids) {
        this.ids = ids;
        this.count = this.ids.length;
    },
    unlink: function(ids) {
        this.on_unlink(ids);
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
        this.rpc('/base/dataset/search_read', {
            model: this.model,
            fields: fields,
            domain: this.domain,
            context: this.context,
            sort: this.sort(),
            offset: offset,
            limit: limit
        }, function (records) {
            self.ids.splice(0, self.ids.length);
            self.offset = offset;
            self.count = records.length;    // TODO: get real count
            for (var i=0; i < records.length; i++ ) {
                self.ids.push(records[i].id);
            }
            callback(records);
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
            return _.map(this._sort, function (criteria) {
                if (criteria[0] === '-') {
                    return criteria.slice(1) + ' DESC';
                }
                return criteria + ' ASC';
            }).join(', ');
        }

        var reverse = force_reverse || (this._sort[0] === field);
        this._sort = _.without(this._sort, field, '-' + field);

        this._sort.unshift((reverse ? '-' : '') + field);
        return undefined;
    }
});

openerp.base.CompoundContext = function() {
    this.__ref = "compound_context";
    this.__contexts = [];
    var self = this;
    _.each(arguments, function(x) {
        self.add(x);
    });
};
openerp.base.CompoundContext.prototype.add = function(context) {
    if (context.__ref === "compound_context")
        this.__contexts = this.__contexts.concat(context.__contexts);
    else
        this.__contexts.push(context);
    return this;
};

openerp.base.CompoundDomain = function() {
    this.__ref = "compound_domain";
    this.__domains = [];
    _.each(arguments, function(x) {
        self.add(x);
    });
};
openerp.base.CompoundDomain.prototype.add = function(domain) {
    if (domain.__ref === "compound_domain")
        this.__domains = this.__domains.concat(domain.__domains);
    else
        this.__domains.push(domain);
    return this;
};

};

// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax:
