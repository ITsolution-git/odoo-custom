
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
     * content of the current grouping level, and
     * :js:func:`~openerp.base.DataGroup.get`, which is used to fetch an item
     * of the current grouping level.
     *
     * @constructs
     * @extends openerp.base.Controller
     *
     * @param {openerp.base.Session} session Current OpenERP session
     * @param {String} model name of the model managed by this DataGroup
     * @param {Array} domain search domain for this DataGroup
     * @param {Object} context context of the DataGroup's searches
     * @param {Array} group_by sequence of fields by which to group
     */
    init: function(session, model, domain, context, group_by) {
        this._super(session, null);
        this.model = model;
        this.context = context;
        this.domain = domain;

        this.group_by = group_by;

        this.groups = null;
    },
    fetch: function () {
        // internal method
        var d = new $.Deferred();
        var self = this;

        if (this.groups) {
            d.resolveWith(this, [this.groups]);
        } else {
            this.rpc('/base/group/read', {
                model: this.model,
                context: this.context,
                domain: this.domain,
                group_by_fields: this.group_by
            }, function () { }).then(function (response) {
                self.groups = response.result;
                // read_group results are annoying: they use the name of the
                // field grouped on to hold the value and the count, so no
                // generic access to those values is possible.
                // Alias them to `value` and `length`.
                d.resolveWith(self, [_(response.result).map(function (group) {
                    var field_name = self.group_by[0];
                    return _.extend({}, group, {
                        // provide field used for grouping
                        grouped_on: field_name,
                        length: group[field_name + '_count'],
                        value: group[field_name]
                    });
                })]);
            }, function () {
                d.rejectWith.apply(d, self, [arguments]);
            });
        }
        return d.promise();
    },
    /**
     * Retrieves the content of an item in the DataGroup, which results in
     * either a DataSet or new DataGroup instance.
     *
     * Calling :js:func:`~openerp.base.DataGroup.get` without having called
     * :js:func:`~openerp.base.DataGroup.list` beforehand will likely result
     * in an error.
     *
     * The resulting :js:class:`~openerp.base.DataGroup` or
     * :js:class:`~openerp.base.DataSet` will be provided through the relevant
     * callback function. In both functions, the current DataGroup will be
     * provided as context (``this``)
     *
     * @param {Number} index the index of the group to open in the datagroup's collection
     * @param {Function} ifDataSet executed if the item results in a DataSet, provided with the new dataset as parameter
     * @param {Function} ifDataGroup executed if the item results in a DataSet, provided with the new datagroup as parameter
     */
    get: function (index, ifDataSet, ifDataGroup) {
        var group = this.groups[index];
        if (!group) {
            throw new Error("No group at index " + index);
        }

        var child_context = _.extend({}, this.context, group.__context);
        if (group.__context.group_by.length) {
            var datagroup = new openerp.base.DataGroup(
                this.session, this.model, group.__domain, child_context,
                group.__context.group_by);
            ifDataGroup.call(this, datagroup);
        } else {
            var dataset = new openerp.base.DataSetSearch(this.session, this.model);
            dataset.domain = group.__domain;
            dataset.context = child_context;
            ifDataSet.call(this, dataset);
        }
    },
    /**
     * Gathers the content of the current data group (the current grouping
     * level), and provides it via a promise object to which callbacks should
     * be added::
     *
     *     datagroup.list().then(function (list) {
     *         // manipulate list here
     *     });
     *
     * The argument to the callback is the list of elements fetched, the
     * context (``this``) is the datagroup itself.
     *
     * The items of a list are the standard objects returned by ``read_group``
     * with three properties added:
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
     *
     * @returns {$.Deferred}
     */
    list: function () {
        return this.fetch();
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
    init: function(session, model) {
        this._super(session);
        this.model = model;
        this.context = {};
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
        this.rpc('/base/dataset/get', {
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
            callback([]);
        } else {
            fields = fields || false;
            this.read_ids([this.ids[this.index]], fields, function(records) {
                callback(records[0]);
            });
        }
    },
    default_get: function(fields, callback) {
        return this.rpc('/base/dataset/default_get', {
            model: this.model,
            fields: fields,
            context: this.context
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
        this.notification.notify("Unlink", ids);
    },
    call: function (method, ids, args, callback) {
        this.notification.notify(
            "Calling", this.model + '#' + method + '(' + ids + ')');
        ids = ids || [];
        args = args || [];
        return this.rpc('/base/dataset/call', {
            model: this.model,
            method: method,
            ids: ids,
            args: args
        }, callback);
    },
    name_search: function (search_str, callback) {
        search_str = search_str || '';
        return this.rpc('/base/dataset/name_search', {
            model: this.model,
            search_str: search_str,
            domain: this.domain || [],
            context: this.context
        }, callback);
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
    init: function(session, model) {
        this._super(session, model);
        // all local records
        this.ids = [];
        this.count = 0;
    },
    read_slice: function (fields, offset, limit, callback) {
        this.read_ids(this.ids.slice(offset, offset + limit));
    }
});

openerp.base.DataSetSearch =  openerp.base.DataSet.extend({
    init: function(session, model) {
        this._super(session, model);
        this.domain = [];
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

openerp.base.DataSetRelational =  openerp.base.DataSet.extend( /** @lends openerp.base.DataSet# */{
});

openerp.base.DataSetMany2Many = openerp.base.DataSetStatic.extend({
    /* should extend DataSetStatic instead, but list view still does not support it
     */

    unlink: function(ids) {
        // just do nothing
    },
});

};

// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax:
