odoo.define('web.BasicModel', function (require) {
"use strict";

/**
 * Basic Model
 *
 * This class contains all the logic necessary to communicate between the
 * python models and the web client. More specifically, its job is to give a
 * simple unified API to the rest of the web client (in particular, the views and
 * the field widgets) to query and modify actual records in db.
 *
 * From a high level perspective, BasicModel is essentially a hashmap with
 * integer keys and some data and metadata object as value.  Each object in this
 * hashmap represents a piece of data, and can be reloaded and modified by using
 * its id as key in many methods.
 *
 * Here is a description of what those data point look like:
 *   var dataPoint = {
 *      _cache: {Object|undefined}
 *      _changes: {Object|null},
 *      aggregateValues: {Object},
 *      context: {Object},
 *      count: {integer},
 *      data: {Object|Object[]},
 *      domain: {*[]},
 *      fieldNames: {string[]},
 *      fields: {Object},
 *      fieldAttrs: {Object},
 *      getContext: {function},
 *      getDomain: {function},
 *      groupedBy: {string[]},
 *      id: {integer},
 *      isOpen: {boolean},
 *      limit: {integer},
 *      model: {string,
 *      offset: {integer},
 *      openGroupByDefault: {boolean},
 *      orderedBy: {string[]},
 *      parentID: {string},
 *      rawContext: {Object},
 *      relationField: {string},
 *      res_id: {integer|null},
 *      res_ids: {integer[]},
 *      specialData: {Object},
 *      _specialDataCache: {Object},
 *      static: {boolean},
 *      type: {string} 'record' | 'list'
 *      value: ?,
 *  };
 *
 * Notes:
 * - id: is totally unrelated to res_id.  id is a web client local concept
 * - res_id: if set to a number, it is an actual id for a record in the server
 *     database. If set to 'virtual_' + number, it is a record not yet saved (so,
 *     in create mode).
 * - res_ids: if set, it represent the context in which the data point is actually
 *     used.  For example, a given record in a form view (opened from a list view)
 *     might have a res_id = 2 and res_ids = [1,2,3]
 * - offset: this is mainly used for pagination.  Useful when we need to load
 *     another page, then we can simply change the offset and reload.
 * - count is basically the number of records being manipulated.  We can't use
 *     res_ids, because we might have a very large number of records, or a
 *     domain, and the res_ids would be the current page, not the full set.
 * - model is the actual name of a (odoo) model, such as 'res.partner'
 * - fields contains the description of all the fields from the model.  Note that
 *     these properties might have been modified by a view (for example, with
 *     required=true.  So, the fields kind of depends of the context of the
 *     data point.
 * - field_names: list of some relevant field names (string).  Usually, it
 *     denotes the fields present in the view.  Only those fields should be
 *     loaded.
 * - _cache and _changes are private, they should not leak out of the basicModel
 *   and be used by anyone else.
 *
 * Commands:
 *   commands are the base commands for x2many (0 -> 6), but with a
 *   slight twist: each [0, _, values] command is augmented with a virtual id:
 *   it means that when the command is added in basicmodel, it generates an id
 *   looking like this: 'virtual_' + number, and uses this id to identify the
 *   element, so it can be edited later.
 */

var AbstractModel = require('web.AbstractModel');
var concurrency = require('web.concurrency');
var Context = require('web.Context');
var Domain = require('web.Domain');
var fieldUtils = require('web.field_utils');
var session = require('web.session');

var x2ManyCommands = {
    // (0, _, {values})
    CREATE: 0,
    create: function (values) {
        return [x2ManyCommands.CREATE, false, values];
    },
    // (1, id, {values})
    UPDATE: 1,
    update: function (id, values) {
        return [x2ManyCommands.UPDATE, id, values];
    },
    // (2, id[, _])
    DELETE: 2,
    delete: function (id) {
        return [x2ManyCommands.DELETE, id, false];
    },
    // (3, id[, _]) removes relation, but not linked record itself
    FORGET: 3,
    forget: function (id) {
        return [x2ManyCommands.FORGET, id, false];
    },
    // (4, id[, _])
    LINK_TO: 4,
    link_to: function (id) {
        return [x2ManyCommands.LINK_TO, id, false];
    },
    // (5[, _[, _]])
    DELETE_ALL: 5,
    delete_all: function () {
        return [5, false, false];
    },
    // (6, _, ids) replaces all linked records with provided ids
    REPLACE_WITH: 6,
    replace_with: function (ids) {
        return [6, false, ids];
    }
};

var BasicModel = AbstractModel.extend({
    /**
     * @override
     */
    init: function () {
        // this mutex is necessary to make sure some operations are done
        // sequentially, for example, an onchange needs to be completed before a
        // save is performed.
        this.mutex = new concurrency.Mutex();

        this.localData = Object.create(null);
        this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Add a default record to a list object.  This method actually make a new
     * record with the makeDefaultRecord method, then add it to the list object.
     *
     * @param {string} listID a valid handle for a list object
     * @param {Object} [options]
     * @param {string} [options.position=top] if the new record should be added
     *   on top or on bottom of the list
     * @returns {Deferred<string>} resolves to the id of the new created record
     */
    addDefaultRecord: function (listID, options) {
        var list = this.localData[listID];
        var context = this._getContext(list);

        var position = (options && options.position) || 'top';
        var params = {
            context: context,
            fieldAttrs: list.fieldAttrs,
            fieldNames: list.fieldNames,
            fields: list.fields,
            parentID: list.id,
            relationField: list.relationField,
        };
        return this.makeDefaultRecord(list.model, params).then(function (id) {
            list.count++;
            if (position === 'top') {
                list.data.unshift(id);
            } else {
                list.data.push(id);
            }
            return id;
        });
    },
    /**
     * Delete a list of records, then, if a parentID is given, reload the
     * parent.
     *
     * @todo we should remove the deleted records from the localData
     * @todo is it really necessary to reload the data? it seems artificial, and
     *   the caller should be able to do that himself
     * @todo why can't we infer modelName?
     *
     * @param {string[]} recordIds list of local resources ids. They should all
     *   be of type 'record', and of the same model
     * @param {string} modelName
     * @param {string} parentID
     * @returns {Deferred}
     */
    deleteRecords: function (recordIds, modelName, parentID) {
        var self = this;
        var records = _.map(recordIds, function (id) { return self.localData[id]; });
        return this._rpc(modelName, 'unlink')
            .args([_.pluck(records, 'res_id')])
            .withContext(session.user_context) // todo: combine with view context
            .exec()
            .then(function () {
                _.each(records, function (record) {
                    record.res_ids.splice(record.offset, 1)[0];
                    record.res_id = record.res_ids[record.offset];
                    record.count--;
                });
                if (parentID) {
                    return self.reload(parentID);
                }
            });
    },
    /**
     * Discard all changes in a local resource.  Basically, it removes
     * everything that was stored in a _changes key.
     *
     * @param {string} id local resource id
     */
    discardChanges: function (id) {
        var element = this.localData[id];
        this._visitChildren(element, function (elem) {
            elem._changes = null;
        });
    },
    /**
     * Duplicate a record (by calling the 'copy' route)
     *
     * @param {string} recordID id for a local resource
     * @returns {Deferred -> string} resolves to the id of duplicate record
     */
    duplicateRecord: function (recordID) {
        var self = this;
        var record = this.localData[recordID];
        return this._rpc(record.model, 'copy')
            .args([record.data.id])
            .withContext(this._getContext(record))
            .exec()
            .then(function (res_id) {
                var index = record.res_ids.indexOf(record.res_id);
                record.res_ids.splice(index + 1, 0, res_id);
                return self.load({
                    fieldAttrs: record.fieldAttrs,
                    fieldNames: record.fieldNames,
                    fields: record.fields,
                    modelName: record.model,
                    res_id: res_id,
                    res_ids: record.res_ids.slice(0),
                });
            });
    },
    /**
     * The get method first argument is the handle returned by the load method.
     * It is optional (the handle can be undefined).  In some case, it makes
     * sense to use the handle as a key, for example the BasicModel holds the
     * data for various records, each with its local ID.
     *
     * synchronous method, it assumes that the resource has already been loaded.
     *
     * @param {string} id local id for the resource
     * @param {any} options
     * @param {boolean} [options.env=false] if true, will only  return res_id
     *   (if record) or res_ids (if list)
     * @param {boolean} [options.raw=false] if true, will not follow relations
     * @returns {Object}
     */
    get: function (id, options) {
        var self = this;
        options = options || {};

        if (!(id in this.localData)) {
            return null;
        }

        var record = this.localData[id];

        if (options.env) {
            var env = {
                ids: record.res_ids ? record.res_ids.slice(0) : [],
            };
            if (record.type === 'record') {
                env.currentId = this.isNew(record.id) ? undefined : record.res_id;
            }
            return env;
        }

        // do not copy fields: this has a really big performance cost, for views
        // with many records and lots of fields (for ex, kanban view contacts)
        var fields = record.fields;
        delete record.fields;
        var element = $.extend(true, {}, record);
        record.fields = fields;
        element.fields = fields;

        var field, relDataPoint;
        if (element.type === 'record') {
            // apply changes
            _.extend(element.data, element._changes);

            for (var fieldName in element.data) {
                field = element.fields[fieldName];
                if (element.data[fieldName] === null) {
                    element.data[fieldName] = false;
                }
                if (!field) {
                    continue;
                }

                // get relational datapoint
                if (field.type === 'many2one') {
                    if (options.raw) {
                        relDataPoint = this.localData[element.data[fieldName]];
                        element.data[fieldName] = relDataPoint ? relDataPoint.res_id : false;
                    } else {
                        element.data[fieldName] = this.get(element.data[fieldName]) || false;
                    }
                }
                if (field.type === 'one2many' || field.type === 'many2many') {
                    if (options.raw) {
                        relDataPoint = this.localData[element.data[fieldName]];
                        var ids = _.map(relDataPoint.data, function (id) {
                            return self.localData[id].res_id;
                        });
                        element.data[fieldName] = ids;
                    } else {
                        element.data[fieldName] = this.get(element.data[fieldName]) || [];
                    }
                }
            }

            // this is not strictly necessary, but it hides some implementation
            // details, and can easily be removed if needed.
            delete element.orderedBy;
            delete element.aggregateValues;
            delete element.groupedBy;
            if (this.isNew(element.id)) {
                delete element.res_id;
            }
        }
        if (element.type === 'list') {
            // apply changes if any
            if (element._changes) {
                element.data = element._changes;
                element.count = element._changes.length;
                element.res_ids = _.map(element._changes, function (elemID) {
                    return self.localData[elemID].res_id;
                });
            }
            // get relational datapoint
            element.data = _.map(element.data, function (elemID) {
                return self.get(elemID);
            });
        }

        delete element._cache;
        delete element._changes;
        delete element._forceM2MLink;
        delete element.static;
        delete element.parentID;
        delete element.relation_field;
        delete element.rawContext;

        return element;
    },
    /**
     * return true if a record is dirty. A record is considered dirty if it has
     * some unsaved changes. A list is considered dirty if its _changes key is
     * set to an array of its new datapoints (possibly empty)
     *
     * @param {string} id id for a local resource
     * @returns {boolean}
     */
    isDirty: function (id) {
        var isDirty = false;
        var record = this.localData[id];
        this._visitChildren(record, function (r) {
            if (r.type === "record" ? !_.isEmpty(r._changes) : r._changes) {
                isDirty = true;
            }
        });
        return isDirty;
    },
    /**
     * Check if a record is new, meaning if it is in the process of being
     * created and no actual record exists in db.
     *
     * @param {string} id id for a local resource
     * @returns {boolean}
     */
    isNew: function (id) {
        return typeof this.localData[id].res_id !== 'number';
    },
    /**
     * Main entry point, the goal of this method is to fetch and process all
     * data (following relations if necessary) for a given record/list.
     *
     * @todo document all params
     *
     * @param {any} params
     * @param {Object} [params.fieldAttrs={}] contains the attrs of each field
     * @param {Array} [params.fieldNames] the name of fields to load, the list
     *   of all fields by default
     * @param {Object} params.fields contains the description of each field
     * @param {string} [params.type] 'record' or 'list'
     * @param {string} [params.recordID] an ID for an existing resource.
     * @returns {Deferred -> string} resolves to a local id, or handle
     */
    load: function (params) {
        params.type = params.type || (params.res_id !== undefined ? 'record' : 'list');

        if (params.type === 'record' && params.res_id === undefined) {
            return this.makeDefaultRecord(params.modelName, params);
        }
        var dataPoint = this._makeDataPoint(params);
        return this._load(dataPoint).then(function () {
            return dataPoint.id;
        });
    },
    /**
     * When one needs to create a record from scratch, a not so simple process
     * needs to be done:
     * - call the /default_get route to get default values
     * - fetch all relational data
     * - apply all onchanges if necessary
     * - fetch all relational data
     *
     * This method tries to optimize the process as much as possible.  Also,
     * it is quite horrible and should be refactored at some point.
     *
     * @param {any} params
     * @param {string} modelName model name
     * @param {Object} params.context the context for the new record
     * @param {Object} [params.fieldAttrs={}] contains the attrs of each field
     * @param {Array} params.fieldNames the name of fields to load, the list
     *   of all fields by default
     * @param {Object} params.fields contains the description of each field
     * @param {Object} params.context the context for the new record
     * @returns {Deferred -> string} resolves to the id for the created resource
     */
    makeDefaultRecord: function (modelName, params) {
        var self = this;
        var fields_key = _.without(params.fieldNames, '__last_update');

        return this._rpc(modelName, 'default_get')
            .args([fields_key])
            .withContext(params.context)
            .exec()
            .then(function (result) {
                // fill default values for missing fields
                for (var i = 0; i < params.fieldNames.length; i++) {
                    var fieldName = params.fieldNames[i];
                    if (!(fieldName in result)) {
                        var field = params.fields[fieldName];
                        if (field.type === 'one2many' || field.type === 'many2many') {
                            result[fieldName] = [];
                        } else {
                            result[fieldName] = null;
                        }
                    }
                }

                var data = {};
                var record = self._makeDataPoint({
                    modelName: modelName,
                    data: data,
                    fields: params.fields,
                    fieldNames: params.fieldNames,
                    fieldAttrs: params.fieldAttrs,
                    context: params.context,
                    parentID: params.parentID,
                    relationField: params.relationField,
                    res_ids: params.res_ids,
                });

                var defs = [];  // FIXME: remove defs?
                _.each(params.fieldNames, function (name) {
                    var field = params.fields[name];
                    data[name] = null;
                    record._changes = record._changes || {};
                    if (field.type === 'many2one' && result[name]) {
                        var rec = self._makeDataPoint({
                            context: record.context,
                            data: {id: result[name]},
                            modelName: field.relation,
                        });
                        record._changes[name] = rec.id;
                    } else if (field.type === 'one2many' || field.type === 'many2many') {
                        var attrs = record.fieldAttrs[name];
                        var x2manyList = self._makeDataPoint({
                            context: record.context,
                            fieldAttrs: field.fieldAttrs,
                            fields: field.relatedFields,
                            limit: field.limit,
                            modelName: field.relation,
                            parentID: record.id,
                            rawContext: attrs && attrs.context,
                            relationField: field.relation_field,
                            res_ids: [],
                            static: true,
                            type: 'list',
                        });
                        record._changes[name] = x2manyList.id;
                        var many2ones = {};
                        var r;
                        _.each(result[name], function (value) {
                            if (_.isArray(value)) {
                                // value is a command
                                if (value[0] === 0) {
                                    // CREATE
                                    r = self._makeDataPoint({
                                        modelName: x2manyList.model,
                                        context: x2manyList.context,
                                        fields: field.relatedFields,
                                        fieldAttrs: field.fieldAttrs,
                                    });
                                    x2manyList._changes.push(r.id);
                                    r._changes = value[2];

                                    // this is necessary so the fields are initialized
                                    for (var fieldName in value[2]) {
                                        r.data[fieldName] = null;
                                    }

                                    for (var name in r._changes) {
                                        if (r.fields[name].type === 'many2one') {
                                            var rec = self._makeDataPoint({
                                                context: r.context,
                                                modelName: r.fields[name].relation,
                                                data: {id: r._changes[name]}
                                            });
                                            r._changes[name] = rec.id;
                                            many2ones[name] = true;
                                        }
                                    }
                                }
                                if (value[0] === 6) {
                                    // REPLACE_WITH
                                    x2manyList._changes = [];
                                }
                            } else {
                                // value is an id
                                r = self._makeDataPoint({
                                    modelName: x2manyList.model,
                                    context: x2manyList.context,
                                    fields: field.relatedFields,
                                    fieldAttrs: field.fieldAttrs,
                                    res_id: value,
                                });
                                if (!x2manyList._changes) {
                                    x2manyList._changes = [];
                                }
                                x2manyList._changes.push(r.id);
                            }
                        });

                        // fetch many2ones display_name
                        _.each(_.keys(many2ones), function (name) {
                            defs.push(self._fetchNameGets(x2manyList, name));
                        });
                    } else if (field.type === 'date') {
                        // process date: convert into a moment instance
                        record._changes[name] = fieldUtils.parse.date(result[name]);
                    } else if (field.type === 'datetime') {
                        // process datetime: convert into a moment instance
                        record._changes[name] = fieldUtils.parse.datetime(result[name]);
                    } else {
                        record._changes[name] = result[name];
                    }
                });
                return $.when.apply($, defs)
                    .then(function () {
                        var shouldApplyOnchange = false;
                        var field;
                        for (var field_name in record.data) {
                            field = record.fields[field_name];
                            if (field.onChange) {
                                shouldApplyOnchange = true;
                            }
                        }
                        if (shouldApplyOnchange) {
                            return self._applyOnChange(record, fields_key);
                        } else {
                            return $.when();
                        }
                    })
                    .then(function () {
                        return self._fetchRelationalData(record);
                    })
                    .then(function () {
                        return self._postprocess(record);
                    })
                    .then(function () {
                        return record.id;
                    });
            });
    },
    /**
     * This helper method is designed to help developpers that want to use a
     * field widget outside of a view.  In that case, we want a way to create
     * data without actually performing a fetch.
     *
     * @param {string} model name of the model
     * @param {Object[]} fields a description of field properties
     * @param {Object} [attrs] various field attrs that we want to set
     * @returns {string} the local id for the created resource
     */
    makeRecord: function (model, fields, attrs) {
        var self = this;
        var record_fields = {};
        _.each(fields, function (field) {
            record_fields[field.name] = _.pick(field, 'type', 'relation', 'domain');
        });
        var record = this._makeDataPoint({
            modelName: model,
            fields: record_fields,
            fieldAttrs: attrs,
        });
        _.each(fields, function (field) {
            if ('value' in field) {
                if (field.type === 'many2one') {
                    var id = field.value[0];
                    var display_name = field.value[1];
                    var relatedRecord = self._makeDataPoint({
                        modelName: field.relation,
                        data: {
                            id: id,
                            display_name: display_name,
                        }
                    });
                    record.data[field.name] = relatedRecord.id;
                } else {
                    record.data[field.name] = field.value;
                }
            }
        });
        return record.id;
    },
    /**
     * This is an extremely important method.  All changes in any field go
     * through this method.  It will then apply them in the local state, check
     * if onchanges needs to be applied, actually do them if necessary, then
     * resolves with the list of changed fields.
     *
     * @param {string} record_id
     * @param {Object} changes a map field => new value
     * @returns {string[]} list of changed fields
     */
    notifyChanges: function (record_id, changes) {
        var self = this;
        var record = this.localData[record_id];
        var onChangeFields = []; // the fields that have changed and that have an on_change
        var field;
        var defs = [];
        record._changes = record._changes || {};

        // apply changes to local data
        for (var fieldName in changes) {
            field = record.fields[fieldName];
            if (field.type === 'one2many' || field.type === 'many2many') {
                defs.push(this._applyX2ManyChange(record, fieldName, changes[fieldName]));
            } else if (field.type === 'many2one') {
                defs.push(this._applyMany2OneChange(record, fieldName, changes[fieldName]));
            } else {
                record._changes[fieldName] = changes[fieldName];
            }
            if (field.onChange) {
                onChangeFields.push(fieldName);
            }
        }

        return $.when.apply($, defs).then(function () {
            var onchangeDef;
            if (onChangeFields.length) {
                onchangeDef = self._applyOnChange(record, onChangeFields).then(function (result) {
                    return _.keys(changes).concat(Object.keys(result && result.value || {}));
                });
            } else {
                onchangeDef = $.Deferred().resolve(_.keys(changes));
            }
            return onchangeDef.then(function (fieldNames) {
                _.each(fieldNames, function (name) {
                    if (record._changes && record._changes[name] === record.data[name]) {
                        delete record._changes[name];
                    }
                });
                return self._fetchSpecialData(record).then(function (fieldNames2) {
                    // Return the names of the fields that changed (onchange or
                    // associated special data change)
                    return _.union(fieldNames, fieldNames2);
                });
            });
        });
    },
    /**
     * Reload all data for a given resource
     *
     * @param {string} id local id for a resource
     * @param {Object} [options]
     * @returns {Deferred -> string} resolves to the id of the resource
     */
    reload: function (id, options) {
        options = options || {};
        var element = this.localData[id];

        if (element.type === 'record') {
            if ('currentId' in options && !options.currentId) {
                var params = {
                    context: element.context,
                    fieldAttrs: element.fieldAttrs,
                    fieldNames: element.fieldNames,
                    fields: element.fields,
                };
                return this.makeDefaultRecord(element.model, params);
            }
            this.discardChanges(id);
        }

        if (options.context !== undefined) {
            element.context = options.context;
        }
        if (options.domain !== undefined) {
            element.domain = options.domain;
        }
        if (options.groupBy !== undefined) {
            element.groupedBy = options.groupBy;
        }
        if (options.limit !== undefined) {
            element.limit = options.limit;
        }
        if (options.offset !== undefined) {
            this._setOffset(element.id, options.offset);
        }
        if (options.currentId !== undefined) {
            element.res_id = options.currentId;
        }
        if (options.ids !== undefined) {
            element.res_ids = options.ids;
            element.count = element.res_ids.length;
        }
        if (element.type === 'record') {
            element.offset = _.indexOf(element.res_ids, element.res_id);
        }
        var loadOptions = _.pick(options, 'fieldNames');
        return this._load(element, loadOptions).then(function (result) {
            return result.id;
        });
    },
    /**
     * Save a local resource, if needed.  This is a complicated operation,
     * - it needs to check all changes,
     * - generate commands for x2many fields,
     * - call the /create or /write method according to the record status
     * - After that, it has to reload all data, in case something changed,
     *   server side.
     *
     * @param {string} record_id local resource
     * @param {Object} [options]
     * @param {boolean} [options.reload=true] if true, data will be reloaded
     * @param {boolean} [options.localSave=false] if true, the record will only
     *   be 'locally' saved: its changes will move from the _changes key to the
     *   data key
     * @returns {Deferred}
     */
    save: function (record_id, options) {
        var self = this;
        options = options || {};
        if (options.localSave) {
            var record = self.localData[record_id];
            if (record._changes) {
                _.extend(record.data, record._changes);
                record._changes = null;
            }
            return $.when();
        }
        var shouldReload = 'reload' in options ? options.reload : true;
        return this.mutex.exec(function () {
            var record = self.localData[record_id];
            var method = self.isNew(record_id) ? 'create' : 'write';
            var changes = _.extend({}, record._changes);
            var commands = self._generateX2ManyCommands(record);
            for (var fieldName in commands) {
                if (commands[fieldName] === null) {
                    delete changes[fieldName];
                } else {
                    changes[fieldName] = commands[fieldName];
                }
            }

            // replace local ids by actual ids in relational changes
            for (fieldName in changes) {
                var field = record.fields[fieldName];
                if (field.type === 'many2one') {
                    if (changes[fieldName]) {
                        var res_id = self.localData[changes[fieldName]].res_id;
                        changes[fieldName] = res_id;
                    } else {
                        changes[fieldName] = false;
                    }
                }
            }

            if (method === 'create') {
                _.each(record.fieldNames, function (name) {
                    changes[name] = changes[name] || record.data[name];
                    if (changes[name] === null) {
                        delete changes[name];
                    }
                });
            }
            // make sure we don't write an undefined id
            delete changes.id;

            // in the case of a write, only perform the RPC if there are changes to save
            if (method === 'create' || Object.keys(changes).length) {
                var args = method === 'write' ? [[record.data.id], changes] : [changes];
                return self._rpc(record.model, method)
                    .args(args)
                    .withContext(session.user_context) // todo: combine with view context
                    .exec()
                    .then(function (id) {
                        if (method === 'create') {
                            record.res_id = id;  // create returns an id, write returns a boolean
                            record.data.id = id;
                            record.offset = record.res_ids.length;
                            record.res_ids.push(id);
                            record.count++;
                        }
                        // erase changes as they have been applied
                        record._changes = {};

                        return shouldReload ? self._fetchRecord(record) : false;
                    });
            } else {
                return $.when(record_id);
            }
        });
    },
    /**
     * Set fieldNames.
     * Set fields on a record element (current fields as defaults)
     * Set fieldattrs.
     * It is mostly useful for the cases where a record element is shared
     * between various views, such as a one2many with a tree and a form view.
     *
     * @param {string} recordID a valid element ID
     * @param {Object} props
     * @param {Object} props.fieldNames
     * @param {Object} props.fields
     * @param {Object} props.fieldAttrs
     * @return {Object}
     * @return {Object} result.fieldNames the previous field names
     * @return {Object} result.fields the previous description fields
     * @return {Object} result.fieldattrs the previous field attrs
     */
    setFieldProps: function (recordID, props) {
        var record = this.localData[recordID];
        var result = {
            fieldNames: record.fieldNames,
            fields: record.fields,
            fieldAttrs: record.fieldAttrs,
        };
        record.fieldNames = props.fieldNames;
        record.fields = _.defaults(props.fields, record.fields);
        record.fieldAttrs = props.fieldAttrs;
        return result;
    },
    /**
     * For list resources, this changes the orderedBy key, then performs the
     * sort directly, in javascript.  This is used for sorting static datasets,
     * such as a one2many in a form view. For dynamic datasets, such as a list
     * view, this method will be called, but then the sort will be ignored since
     * we will reload data.
     *
     * @todo don't sort in js when we reload data anyway
     *
     * @param {string} list_id id for the list resource
     * @param {string} fieldName valid field name
     * @returns {this} so we can chain call this method
     */
    setSort: function (list_id, fieldName) {
        var list = this.localData[list_id];
        if (list.type === 'record') {
            return;
        }
        list.offset = 0;
        if (list.orderedBy.length === 0) {
            list.orderedBy.push({name: fieldName, asc: true});
        } else if (list.orderedBy[0].name === fieldName){
            list.orderedBy[0].asc = !list.orderedBy[0].asc;
        } else {
            var orderedBy = _.reject(list.orderedBy, function (o) {
                return o.name === fieldName;
            });
            list.orderedBy = [{name: fieldName, asc: true}].concat(orderedBy);
        }
        this._sortList(list);
        return this;
    },
    /**
     * Toggle the active value of given records (to archive/unarchive them)
     *
     * @param {Array} recordIDs local ids of the records to (un)archive
     * @param {boolean} value false to archive, true to unarchive (value of the active field)
     * @param {string} parentID id of the parent resource to reload
     * @returns {Deferred<string>} resolves to the parent id
     */
    toggleActive: function (recordIDs, value, parentID) {
        var self = this;
        var parent = this.localData[parentID];
        var resIDs = _.map(recordIDs, function (recordID) {
            return self.localData[recordID].res_id;
        });
        return this._rpc(parent.model, 'write')
            .args([resIDs, { active: value }])
            .exec()
            .then(this.reload.bind(this, parentID));

    },
    /**
     * Toggle (open/close) a group in a grouped list, then fetches relevant
     * data
     *
     * @param {string} groupId
     * @returns {Deferred -> string} resolves to the group id
     */
    toggleGroup: function (groupId) {
        var group = this.localData[groupId];
        if (group.isOpen) {
            group.isOpen = false;
            group.data = [];
            group.offset = 0;
            return $.when(groupId);
        }
        if (!group.isOpen) {
            group.isOpen = true;
            var def;
            if (group.count > 0) {
                def = this._fetchUngroupedList(group);
            }
            return $.when(def).then(function () {
                return groupId;
            });
        }
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Apply a many2one onchange.  There is a need for this function because the
     * server only gives an id when a onchange modifies a many2one field.  For
     * this reason, we need (sometimes) to do a /name_get to fetch a
     * display_name.
     *
     * @param {Object} record
     * @param {string} fieldName
     * @param {Object} [data]
     * @returns {Deferred}
     */
    _applyMany2OneChange: function (record, fieldName, data) {
        var self = this;
        if (!data) {
            record._changes[fieldName] = false;
            return $.when();
        }
        var rel_data = _.pick(data, 'id', 'display_name');
        var def;
        if (!('display_name' in rel_data)) {
            var field = record.fields[fieldName];
            def = this._rpc(field.relation, 'name_get')
                .args([data.id])
                .withContext(record.context)
                .exec()
                .then(function (result) {
                    rel_data.display_name = result[0][1];
                });
        }
        return $.when(def).then(function () {
            var rec = self._makeDataPoint({
                context: record.context,
                data: rel_data,
                fields: {},
                modelName: record.fields[fieldName].relation,
            });
            record._changes[fieldName] = rec.id;
        });
    },
    /**
     * This method is quite important: it is supposed to perform the /onchange
     * rpc and apply the result.
     *
     * @param {Object} record
     * @param {string[]} fields changed fields
     * @returns {Deferred} The returned deferred can fail, in which case the
     *   fail value will be the warning message received from the server
     */
    _applyOnChange: function (record, fields) {
        var self = this;
        var onchange_spec = this._buildOnchangeSpecs(record);
        var idList = record.data.id ? [record.data.id] : [];
        var context = this._getContext(record);

        var rawData = this.get(record.id, {raw: true}).data;
        var commands = this._generateX2ManyCommands(record);

        // compute field values
        var currentData = _.pick(_.extend(rawData, commands), record.fieldNames);
        if (record.relationField) {
            // if there is a relation field, this means that record is an elem
            // in a one2many.  The relation field is the corresponding many2one

            // parent is the list element containing all the records in the o2m
            // and parent.parentID is the ID of the main record
            var parent = this.localData[record.parentID];
            currentData[record.relationField] = this.get(parent.parentID, {raw:true}).data;
        }

        if (fields.length === 1) {
            fields = fields[0];
        }
        return this.mutex.exec(function () {
            return self._rpc(record.model, 'onchange')
                .args([idList, currentData, fields, onchange_spec, context])
                .exec()
                .then(function (result) {
                    if (result.warning) {
                        self.trigger_up('warning', {
                            message: result.warning.message,
                            title: result.warning.title,
                            type: 'dialog',
                        });
                    }
                    var defs = [];
                    _.each(result.value, function (val, name) {
                        var field = record.fields[name];
                        if (!field) { return; } // ignore changes of unknown fields

                        var rec;
                        if (field.type === 'many2one' ) {
                            // in some case, the value returned by the onchange can
                            // be false (no value), so we need to avoid creating a
                            // local record for that.
                            // FIXME: shouldn't we erase the value in that case?
                            if (val) {
                                // when the value isn't false, it can be either
                                // an array [id, display_name] or just an id.
                                var data = _.isArray(val) ?
                                    {id: val[0], display_name: val[1]} :
                                    {id: val};
                                rec = self._makeDataPoint({
                                    context: context,
                                    data: data,
                                    modelName: field.relation,
                                });
                                record._changes[name] = rec.id;
                            }
                        } else if (field.type === 'one2many' || field.type === 'many2many') {
                            record._changes = record._changes || {};
                            var listId = record._changes[name] || record.data[name];
                            var list = self.localData[listId];
                            _.each(val, function (command) {
                                if (command[0] === 0 || command[0] === 1) {
                                    // CREATE or UPDATE
                                    var params = {
                                        context: context,
                                        fields: list.fields,
                                        fieldAttrs: list.fieldAttrs,
                                        modelName: list.model,
                                        fieldNames: _.keys(command[2]),
                                    };
                                    if (command[0] === 1) {
                                        params.res_id = command[1];
                                    }
                                    rec = self._makeDataPoint(params);
                                    var data = command[2];
                                    _.each(rec.fieldNames, function (name) {
                                        var field = rec.fields[name];
                                        if (field.type === 'many2one') {
                                            var r = self._makeDataPoint({
                                                modelName: field.relation,
                                                data: {
                                                    id: data[name][0],
                                                    display_name: data[name][1],
                                                },
                                            });
                                            data[name] = r.id;
                                        }
                                    });
                                    rec._changes = data;
                                    for (var f in rec._changes) {
                                        rec.data[f] = null;
                                    }
                                    list._changes.push(rec.id);
                                }
                                if (command[0] === 5) {
                                    // DELETE ALL
                                    list._changes = [];
                                }
                            });
                        } else if (field.type === 'date') {
                            // process data: convert into a moment instance
                            record._changes[name] = fieldUtils.parse.date(val);
                        } else if (field.type === 'datetime') {
                            // process datetime: convert into a moment instance
                            record._changes[name] = fieldUtils.parse.datetime(val);
                        } else {
                            record._changes[name] = val;
                        }
                    });
                    return $.when.apply($, defs).then(function () {
                        return result;
                    });
                });
        });
    },
    /**
     * When an operation is applied to a x2many field, the field widgets
     * generate one (or more) command, which describes the exact operation.
     * This method tries to interpret these commands and apply them to the
     * localData.
     *
     * @param {Object} record
     * @param {string} fieldName
     * @param {Object} command A command object.  It should have a 'operation'
     *   key.  For example, it looks like {operation: ADD, id: 'partner_1'}
     * @returns {Deferred}
     */
    _applyX2ManyChange: function (record, fieldName, command) {
        var self = this;
        var list = this.localData[record._changes[fieldName] || record.data[fieldName]];
        var field = record.fields[fieldName];
        var rec;
        var defs = [];
        list._changes = list._changes || list.data;

        switch (command.operation) {
            case 'ADD':
                // for now, we are in the context of a one2many field
                // the command should look like this:
                // { operation: 'ADD', id: localID }
                // The corresponding record may contain value for fields that
                // are unknown in the list (e.g. fields that are in the
                // subrecord form view but not in the kanban or list view), so
                // to ensure that onchanges are correctly handled, we extend the
                // list's fields with those in the created record
                var newRecord = this.localData[command.id];
                _.defaults(list.fields, newRecord.fields);
                newRecord.fields = list.fields;
                list._changes.push(newRecord.id);
                break;
            case 'ADD_M2M':
                // force to use link command instead of create command
                list._forceM2MLink = true;
                // handle multiple add: command[2] may be a dict of values (1
                // record added) or an array of dict of values
                var data = _.isArray(command.ids) ? command.ids : [command.ids];
                var list_records = {};
                _.each(data, function (d) {
                    rec = self._makeDataPoint({
                        context: record.context,
                        modelName: field.relation,
                        fields: field.relatedFields,
                        fieldAttrs: field.fieldAttrs,
                        res_id: d.id,
                    });
                    list_records[d.id] = rec;
                    list._changes.push(rec.id);
                });
                // read list's records as we only have their ids and optionally their display_name
                // (we can't use function readUngroupedList because those records are only in the
                // _changes so this is a very specific case)
                // this could be optimized by registering the fetched records in the list's _cache
                // so that if a record is removed and then re-added, it won't be fetched twice
                var def = this._rpc(list.model, 'read')
                    .args([_.pluck(data, 'id'), list.fieldNames])
                    .exec()
                    .then(function (records) {
                        _.each(records, function (record) {
                            list_records[record.id].data = record;
                            self._parseServerData(list.fieldNames, list.fields, record);
                        });
                    });
                defs.push(def);
                break;
            case 'CREATE':
                defs.push(this.addDefaultRecord(list.id));
                break;
            case 'UPDATE':
                defs.push(this.notifyChanges(command.id, command.data));
                break;
            case 'REMOVE':
                list._changes = _.without(list._changes, command.id);
                break;
            case 'REPLACE_WITH':
                // this is certainly not optimal... and not sure that it is
                // correct if some ids are added and some other are removed
                var currentIds = _.map(list._changes, function (localId) {
                    return self.localData[localId].res_id;
                });
                var newIds = _.difference(command.ids, currentIds);
                var removedIds = _.difference(currentIds, command.ids);
                var addDef, removedDef;
                if (newIds.length) {
                    var values = _.map(newIds, function (id) {
                        return {id: id};
                    });

                    addDef = this._applyX2ManyChange(record, fieldName, {
                        operation: 'ADD_M2M',
                        ids: values
                    });
                }
                if (removedIds.length) {
                    removedDef = this._applyX2ManyChange(record, fieldName, {
                        operation: 'REMOVE',
                        ids: removedIds
                    });
                }
                return $.when(addDef, removedDef);
        }

        return $.when.apply($, defs);
    },
    /**
     * Helper method to build a 'spec', that is a description of all fields in
     * the view that have a onchange defined on them.
     *
     * An onchange spec is necessary as an argument to the /onchange route. It
     * looks like this: { field: "1", anotherField: "", relation.subField: "1"}
     *
     * @see _applyOnChange
     *
     * @param {Object} record resource object of type 'record'
     * @returns {Object} an onchange spec
     */
    _buildOnchangeSpecs: function (record) {
        // TODO: replace this function by some generic tree function in utils
        var specs = {};
        _.each(record.fieldNames, function (name) {
            var field = record.fields[name];
            specs[name] = (field.onChange) || "";
            _.each(field.views, function (view) {
                _.each(view.fields, function (field, subname) {
                    specs[name + '.' + subname] = (field.onChange) || "";
                });
            });
        });
        return specs;
    },
    /**
     * Fetch all name_gets for the many2ones in a group
     *
     * @param {Object} group a valid resource object
     * @returns {Deferred}
     */
    _fetchMany2OneGroup: function (group) {
        var ids = _.uniq(_.pluck(group, 'res_id'));

        return this._rpc(group[0].model, 'name_get')
            .args([ids])
            .withContext(group[0].context)
            .exec()
            .then(function (name_gets) {
                _.each(group, function (record) {
                    var nameGet = _.find(name_gets, function (n) { return n[0] === record.res_id;});
                    record.data.display_name = nameGet[1];
                });
            });
    },
    _fetchNameGets: function (list, fieldName) {
        var self = this;
        var model;
        var records = [];
        var ids = _.map(list._changes || list.data, function (localId) {
            var record = self.localData[localId];
            var data = record._changes || record.data;
            var many2oneId = data[fieldName];
            var many2oneRecord = self.localData[many2oneId];
            records.push(many2oneRecord);
            model = many2oneRecord.model;
            return many2oneRecord.res_id;
        });
        return this._rpc(model, 'name_get')
            .args([ids])
            .withContext(list.context)
            .exec()
            .then(function (name_gets) {
                for (var i = 0; i < name_gets.length; i++) {
                    records[i].data.display_name = name_gets[i][1];
                }
            });
    },
    /**
     * For a given resource of type 'record', fetch all data.
     *
     * @param {Object} record local resource
     * @param {string[]} [fieldNames] the list of fields to fetch. If not given,
     *   fetch all the fields in record.fieldNames (+ display_name)
     * @returns {Deferred -> Object} resolves to the record
     */
    _fetchRecord: function (record, fieldNames) {
        var self = this;
        fieldNames = fieldNames || _.uniq(record.fieldNames.concat(['display_name']));
        var oldData = record.data;
        return this._rpc(record.model, 'read')
            .args([[record.res_id], fieldNames])
            // .withContext({ bin_size: true })  // FIXME: when editing a subrecord in the partner form view, it tries to write the bin_size on the image field
            .exec()
            .then(function (result) {
                result = result[0];
                record.data = _.extend({}, record.data, result);
            })
            .then(function () {
                self._parseServerData(fieldNames, record.fields, record.data);
            })
            .then(function () {
                return self._fetchX2Manys(record, oldData, fieldNames).then(function () {
                    return self._postprocess(record);
                });
            });
    },
    /**
     * This method is incorrectly named.  It should be named something like
     * _fetchMany2OneData.
     *
     * For a given record, this method fetches all many2ones information,
     * batching the requests if possible (for example, if 3 many2ones are in
     * relation on the same model, then we can probably fetch them in one rpc)
     *
     * This method is currently only called by makeDefaultRecord, it should be
     * called by the onchange methods at some point.
     *
     * @todo fix bug: returns a list of deferred, not a deferred
     *
     * @param {Object} record a valid resource object
     * @returns {Deferred}
     */
    _fetchRelationalData: function (record) {
        var self = this;
        var toBeFetched = [];

        // find all many2one related records to be fetched
        _.each(record.fieldNames, function (name) {
            var field = record.fields[name];
            if (field.type === 'many2one') {
                var localId = (record._changes && record._changes[name]) || record.data[name];
                var relatedRecord = self.localData[localId];
                if (!relatedRecord) {
                    return;
                }
                toBeFetched.push(relatedRecord);
            }
        });

        // group them by model and context. Using the context as key is
        // necessary to make sure the correct context is used for the rpc;
        var groups = _.groupBy(toBeFetched, function (rec) {
            return [rec.model, JSON.stringify(rec.context)].join();
        });

        return $.when.apply($, _.map(groups, this._fetchMany2OneGroup.bind(this)));
    },
    /**
     * Check the AbstractField specializations that are (will be) used by the
     * given record and fetch the special data they will need. Special data are
     * data that the rendering of the record won't need if it was not using
     * particular widgets (example of these can be found at the methods which
     * start with _fetchSpecial).
     *
     * @param {Object} record - an element from the localData
     * @returns {Deferred<Array>}
     *          The deferred is resolved with an array containing the names of
     *          the field whose special data has been changed.
     */
    _fetchSpecialData: function (record) {
        var self = this;
        var fieldNames = [];
        return $.when.apply($, _.map(record.fieldNames, function (name) {
            var attrs = record.fieldAttrs[name] || {};
            var Widget = attrs.Widget;
            if (Widget && Widget.prototype.specialData) {
                return self[Widget.prototype.specialData](record, name).then(function (data) {
                    if (data === undefined) {
                        return;
                    }
                    record.specialData[name] = data;
                    fieldNames.push(name);
                });
            }
        })).then(function () {
            return fieldNames;
        });
    },
    /**
     * Fetches all the m2o records associated to the given fieldName. If the
     * given fieldName is not a m2o field, nothing is done.
     *
     * @param {Object} record - an element from the localData
     * @param {Object} fieldName - the name of the field
     * @param {string[]} [fieldsToRead] - the m2os fields to read (id and
     *                                  display_name are automatic).
     * @returns {Deferred<any>}
     *          The deferred is resolved with the fetched special data. If this
     *          data is the same as the previously fetched one (for the given
     *          parameters), no RPC is done and the deferred is resolved with
     *          the undefined value.
     */
    _fetchSpecialMany2ones: function (record, fieldName, fieldsToRead) {
        var field = record.fields[fieldName];
        if (field.type !== "many2one") {
            return $.when();
        }

        var context = record.getContext({fieldName: fieldName});
        var domain = record.getDomain({fieldName: fieldName});
        if (domain.length) {
            var localID = record.data[fieldName];
            var element = this.localData[localID];
            domain = ["|", ["id", "=", element.data.id]].concat(domain);
        }

        // avoid rpc if not necessary
        var specialDataCache = {context: context, domain: domain};
        if (_.isEqual(record._specialDataCache[fieldName], specialDataCache)) {
            return $.when();
        }
        record._specialDataCache[fieldName] = specialDataCache;

        var self = this;
        return this._rpc(field.relation, 'search_read')
            .withFields(["id"].concat(fieldsToRead || []))
            .withContext(context)
            .withDomain(domain)
            .exec()
            .then(function (result) {
                var ids = _.pluck(result.records, 'id');
                return self._rpc(field.relation, 'name_get')
                    .args([ids])
                    .withContext(context)
                    .exec()
                    .then(function (name_gets) {
                        _.each(result.records, function (rec) {
                            var name_get = _.find(name_gets, function (n) {
                                return n[0] === rec.id;
                            });
                            rec.display_name = name_get[1];
                        });
                        return result.records;
                    });
            });
    },
    /**
     * Fetches all the relation records associated to the given fieldName. If
     * the given fieldName is not a relational field, nothing is done.
     *
     * @param {Object} record - an element from the localData
     * @param {Object} fieldName - the name of the field
     * @returns {Deferred<any>}
     *          The deferred is resolved with the fetched special data. If this
     *          data is the same as the previously fetched one (for the given
     *          parameters), no RPC is done and the deferred is resolved with
     *          the undefined value.
     */
    _fetchSpecialRelation: function (record, fieldName) {
        var field = record.fields[fieldName];
        if (!_.contains(["many2one", "many2many", "one2many"], field.type)) {
            return $.when();
        }

        var context = record.getContext({fieldName: fieldName});
        var domain = record.getDomain({fieldName: fieldName});

        // avoid rpc if not necessary
        var specialDataCache = {context: context, domain: domain};
        if (_.isEqual(record._specialDataCache[fieldName], specialDataCache)) {
            return $.when();
        }
        record._specialDataCache[fieldName] = specialDataCache;

        return this._rpc(field.relation, "name_search")
            .args(["", domain])
            .withContext(context)
            .exec();
    },
    /**
     * Fetches all the m2o records associated to the given fieldName. If the
     * given fieldName is not a m2o field, nothing is done. The difference with
     * _fetchSpecialMany2ones is that the field given by options.fold_field is
     * also fetched.
     *
     * @param {Object} record - an element from the localData
     * @param {Object} fieldName - the name of the field
     * @returns {Deferred<any>}
     *          The deferred is resolved with the fetched special data. If this
     *          data is the same as the previously fetched one (for the given
     *          parameters), no RPC is done and the deferred is resolved with
     *          the undefined value.
     */
    _fetchSpecialStatus: function (record, fieldName) {
        var foldField = record.fieldAttrs[fieldName].options.fold_field;
        var fieldsToRead = foldField ? [foldField] : [];
        return this._fetchSpecialMany2ones(record, fieldName, fieldsToRead);
    },
    /**
     * Fetch all data in a ungrouped list
     *
     * @param {Object} list a valid resource object
     * @returns {Deferred -> Object} resolves to the fecthed list
     */
    _fetchUngroupedList: function (list) {
        var self = this;
        var def;
        if (list.static) {
            def = this._readUngroupedList(list);
        } else {
            def = this._searchReadUngroupedList(list);
        }
        return def.then(function () {
            return self._fetchX2ManysBatched(list);
        }).then(function () {
            return list;
        });
    },
    /**
     * X2Manys have to be fetched by separate rpcs (their data are stored on
     * different models). This method takes a record, look at its x2many fields,
     * then, if necessary, create a local resource and fetch the corresponding
     * data.
     *
     * It also tries to reuse data, if it can find an existing list, to prevent
     * useless rpcs.
     *
     * @param {Object} record local resource
     * @param {Object} oldData the data fetched previously
     * @param {string[]} [fieldNames] list of fields to fetch
     * @returns {Deferred}
     */
    _fetchX2Manys: function (record, oldData, fieldNames) {
        var self = this;
        var defs = [];
        fieldNames = fieldNames || record.fieldNames;
        _.each(fieldNames, function (fieldName) {
            var field = record.fields[fieldName];
            if (field.type === 'one2many' || field.type === 'many2many') {
                var list;

                // a previously loaded list exists
                if (oldData[fieldName]) {
                    list = self.localData[oldData[fieldName]];
                    list.res_ids = record.data[fieldName];
                    list.count = list.res_ids.length;
                    list.offset = list.offset < list.count ? list.offset : 0;
                } else {
                    // need to create a list from scratch
                    var attrs = record.fieldAttrs[fieldName];
                    var rawContext = attrs && attrs.context;
                    var ids = record.data[fieldName] || [];
                    list = self._makeDataPoint({
                        count: ids.length,
                        fieldAttrs: field.fieldAttrs,
                        fields: field.relatedFields,
                        limit: field.limit,
                        modelName: field.relation,
                        res_ids: ids,
                        static: true,
                        type: 'list',
                        parentID: record.id,
                        rawContext: rawContext,
                        relationField: field.relation_field,
                    });
                }
                record.data[fieldName] = list.id;
                if (!field.__no_fetch) {
                    defs.push(self._readUngroupedList(list));
                }
            }
        });
        return $.when.apply($, defs);
    },
    /**
     * batch requests for 1 x2m in list
     *
     * @see _fetchX2ManysBatched
     * @param {Object} list
     * @param {string} fieldName
     * @returns {Deferred}
     */
    _fetchX2ManyBatched: function (list, fieldName) {
        var self = this;
        var field = list.fields[fieldName];

        // step 1: collect ids
        var ids = [];
        _.each(list.data, function (dataPoint) {
            var record = self.localData[dataPoint];
            ids = _.unique(ids.concat(record.data[fieldName] || []));
            var m2mList = self._makeDataPoint({
                fieldAttrs: field.fieldAttrs,
                fields: field.relatedFields,
                modelName: field.relation,
                res_ids: record.data[fieldName],
                static: true,
                type: 'list',
            });
            record.data[fieldName] = m2mList.id;
        });

        if (!ids.length || field.__no_fetch) {
            return $.when();
        }

        // step 2: fetch data from server
        return this._rpc(field.relation, 'read')
            .args([ids, _.keys(field.relatedFields)])
            .withContext({}) // FIXME
            .exec()
            .then(function (results) {
                // step 3: assign values to correct datapoints
                var dataPoints = _.map(results, function (result) {
                    return self._makeDataPoint({
                        modelName: field.relation,
                        data: result,
                        fields: field.relatedFields,
                        fieldAttrs: field.fieldAttrs,
                    });
                });

                _.each(list.data, function (dataPoint) {
                    var record = self.localData[dataPoint];
                    var m2mList = self.localData[record.data[fieldName]];

                    m2mList.data = [];
                    _.each(m2mList.res_ids, function (res_id) {
                        var dataPoint = _.find(dataPoints, function (d) {
                            return d.res_id === res_id;
                        });
                        m2mList.data.push(dataPoint.id);
                        m2mList.count++;
                    });
                });
            });
    },
    /**
     * batch request for x2ms for datapoint of type list
     *
     * @param {Object} list
     * @returns {Deferred}
     */
    _fetchX2ManysBatched: function (list) {
        var defs = [];
        for (var i = 0; i < list.fieldNames.length; i++) {
            var field = list.fields[list.fieldNames[i]];
            if (field.type === 'many2many' || field.type === 'one2many') {
                defs.push(this._fetchX2ManyBatched(list, list.fieldNames[i]));
            }
        }
        return $.when.apply($, defs);
    },
    /**
     * Read all x2many fields and generate the commands for the server to create
     * or write them...
     *
     * @param {Object} record
     * @returns {Object} a map from some field names to commands
     */
    _generateX2ManyCommands: function (record) {
        var self = this;
        var commands = {};
        var type, list, relData, relIds, removedIds, addedIds, keptIds, relRecord, i;

        var data = _.extend({}, record.data, record._changes);

        for (var fieldName in record.fields) {
            type = record.fields[fieldName].type;

            if (type === 'many2many' || type === 'one2many') {
                // skip if this field is empty
                if (!data[fieldName]) {
                    commands[fieldName] = null;
                    continue;
                }
                list = this.localData[data[fieldName]];
                if (!list._changes) {
                    commands[fieldName] = null;
                    // skip if this field hasn't changed
                    continue;
                }
                relData = _.map(list._changes, function (localId) {
                    return self.localData[localId];
                });
                relIds = _.pluck(relData, 'res_id');
                commands[fieldName] = [];

                if (type === 'many2many' || list._forceM2MLink) {
                    // deliberately generate a single 'replace' command instead
                    // of a 'delete' and a 'link' commands with the exact diff
                    // because 1) performance-wise it doesn't change anything
                    // and 2) to guard against concurrent updates (policy: force
                    // an complete override of the actual value of the m2m)
                    commands[fieldName].push(x2ManyCommands.replace_with(relIds));
                } else if (type === 'one2many') {
                    removedIds = _.difference(list.res_ids, relIds);
                    addedIds = _.difference(relIds, list.res_ids);
                    keptIds = _.intersection(list.res_ids, relIds);
                    for (i = 0; i < keptIds.length; i++) {
                        commands[fieldName].push(x2ManyCommands.link_to(keptIds[i]));
                    }
                    for (i = 0; i < removedIds.length; i++) {
                        commands[fieldName].push(x2ManyCommands.delete(removedIds[i]));
                    }
                    for (i = 0; i < addedIds.length; i++) {
                        relRecord = _.findWhere(relData, {res_id: addedIds[i]});
                        relRecord = this.get(relRecord.id, {raw: true});
                        commands[fieldName].push(x2ManyCommands.create(_.omit(relRecord.data, 'id')));
                    }
                    // FIXME: update of records temporarily disabled as it doesn't work if we updated
                    // the record in a form view, as the _changes contains all the fields of the
                    // form view instead of the one that have changed
                    // _.each(relData, function (relRecord) {
                    //     var new_values = relRecord._changes;
                    //     if (!_.isEmpty(new_values)) {
                    //         commands[fieldName].push(x2ManyCommands.update(relRecord.res_id, new_values));
                    //     }
                    // });
                }
            }
        }

        return commands;
    },
    /**
     * Every RPC done by the model need to add some context, which is a
     * combination of the context of the session, of the record/list, and/or of
     * the concerned field. This method combines all these contexts and evaluate
     * them with the proper evalcontext.
     *
     * @param {Object} element an element from the localData
     * @param {Object} [options]
     * @param {string} [options.fieldName]
     *        the name of the field whose context needs to be added to the
     *        result (and evaluated)
     * @returns {Object} the evaluated context
     */
    _getContext: function (element, options) {
        var context = new Context(session.user_context, element.context);
        context.set_eval_context(this._getEvalContext(element));

        if (options && options.fieldName) {
            var attrs = element.fieldAttrs[options.fieldName];
            if (attrs && attrs.context) {
                context.add(attrs.context);
            } else {
                var fieldParams = element.fields[options.fieldName];
                if (fieldParams.context) {
                    context.add(fieldParams.context);
                }
            }
        }
        if (element.rawContext) {
            var rawContext = new Context(element.rawContext);
            var evalContext = this._getEvalContext(this.localData[element.parentID]);
            evalContext.id = evalContext.id || false;
            rawContext.set_eval_context(evalContext);
            context.add(rawContext);
        }

        return context.eval();
    },
    /**
     * Some records are associated to a/some domain(s). This method allows to
     * retrieve them, evaluated.
     *
     * @param {Object} element an element from the localData
     * @param {Object} [options]
     * @param {string} [options.fieldName]
     *        the name of the field whose domain needs to be returned
     * @returns {Array} the evaluated domain
     */
    _getDomain: function (element, options) {
        if (options && options.fieldName) {
            var attrs = element.fieldAttrs[options.fieldName];
            if (attrs && attrs.domain) {
                return Domain.prototype.stringToArray(
                    attrs.domain,
                    this._getEvalContext(element)
                );
            }
            var fieldParams = element.fields[options.fieldName];
            if (fieldParams.domain) {
                return Domain.prototype.stringToArray(
                    fieldParams.domain,
                    this._getEvalContext(element)
                );
            }
            return [];
        }

        return Domain.prototype.stringToArray(
            element.domain,
            this._getEvalContext(element)
        );
    },
    /**
     * Returns the evaluation context that should be used when evaluating the
     * context/domain associated to a given element from the localData.
     *
     * @param {Object} element - an element from the localData
     * @returns {Object}
     */
    _getEvalContext: function (element) {
        var evalContext = this.get(element.id, {raw: true}).data;
        evalContext.active_model = element.model;
        if (evalContext.id) {
            evalContext.active_id = evalContext.id;
            evalContext.active_ids = [evalContext.id];
        }
        if (element.parentID) {
            var parent = this.get(element.parentID, {raw: true});
            if (parent.type === 'list' && this.localData[element.parentID].parentID) {
                parent = this.get(this.localData[element.parentID].parentID, {raw: true});
            }
            _.extend(evalContext, {parent: parent.data});
        }
        return evalContext;
    },
    /**
     * Helper method for the load entry point.
     *
     * @see load
     *
     * @param {Object} dataPoint some local resource
     * @param {Object} [options]
     * @param {string[]} [options.fieldNames] the fields to fetch for a record
     * @returns {Deferred}
     */
    _load: function (dataPoint, options) {
        if (dataPoint.type === 'record') {
            return this._fetchRecord(dataPoint, options && options.fieldNames);
        }
        if (dataPoint.type === 'list' && dataPoint.groupedBy.length) {
            return this._readGroup(dataPoint);
        }
        if (dataPoint.type === 'list' && !dataPoint.groupedBy.length) {
            return this._fetchUngroupedList(dataPoint);
        }
    },
    /**
     * Turns a bag of properties into a valid local resource.  Also, register
     * the resource in the localData object.
     *
     * @param {Object} params
     * @param {Object} [params.fieldAttrs={}] contains the attrs of each field
     * @param {Array} [params.fieldNames] the name of fields to load, the list
     *   of all fields by default
     * @param {Object} params.fields contains the description of each field
     * @returns {Object} the resource created
     */
    _makeDataPoint: function (params) {
        var type = params.type || ('domain' in params && 'list') || 'record';

        var res_id, value;
        var res_ids = params.res_ids || [];
        if (type === 'record') {
            res_id = params.res_id || (params.data && params.data.id) || _.uniqueId('virtual_');
        } else {
            var isValueArray = params.value instanceof Array;
            res_id = isValueArray ? params.value[0] : undefined;
            value = isValueArray ? params.value[1] : params.value;
        }

        var fields = _.extend({
            display_name: {type: 'char'},
            id: {type: 'integer'},
        }, params.fields);

        var dataPoint = {
            _cache: type === 'list' ? {} : undefined,
            _changes: null,
            aggregateValues: params.aggregateValues || {},
            context: params.context || {},
            count: params.count || res_ids.length,
            data: params.data || (type === 'record' ? {} : []),
            domain: params.domain || [],
            fieldNames: params.fieldNames || Object.keys(fields),
            fields: fields,
            fieldAttrs: params.fieldAttrs || {},
            groupedBy: params.groupedBy || [],
            id: _.uniqueId(params.modelName + '_'),
            isOpen: params.isOpen,
            limit: type === 'record' ? 1 : params.limit,
            model: params.modelName,
            offset: params.offset || (type === 'record' ? _.indexOf(res_ids, res_id) : 0),
            openGroupByDefault: params.openGroupByDefault,
            orderedBy: params.orderedBy || [],
            parentID: params.parentID,
            rawContext: params.rawContext,
            relationField: params.relationField,
            res_id: res_id,
            res_ids: res_ids,
            specialData: {},
            _specialDataCache: {},
            static: params.static || false,
            type: type,  // 'record' | 'list'
            value: value,
        };

        dataPoint.getContext = this._getContext.bind(this, dataPoint);
        dataPoint.getDomain = this._getDomain.bind(this, dataPoint);

        this.localData[dataPoint.id] = dataPoint;

        return dataPoint;
    },
    /**
     * parse the server values to javascript framwork
     *
     * @param {[string]} fieldNames
     * @param {Object} fields
     * @param {Object} record
     */
    _parseServerData: function (fieldNames, fields, record) {
        var self = this;
        _.each(fieldNames, function (fieldName) {
            var field = fields[fieldName];
            var val = record[fieldName];
            if (field.type === 'many2one') {
                // process many2one: split [id, nameget] and create corresponding record
                if (val !== false) {
                    // the many2one value is of the form [id, display_name]
                    var r = self._makeDataPoint({
                        modelName: field.relation,
                        data: {
                            display_name: val[1],
                            id: val[0],
                        },
                    });
                    record[fieldName] = r.id;
                } else {
                    // no value for the many2one
                    record[fieldName] = false;
                }
            } else if (field.type === 'date') {
                // process data: convert into a moment instance
                record[fieldName] = fieldUtils.parse.date(val);
            } else if (field.type === 'datetime') {
                // process datetime: convert into a moment instance
                record[fieldName] = fieldUtils.parse.datetime(val);
            }
        });
    },
    /**
     * Once a record is created and some data has been fetched, we need to do
     * quite a lot of computations to determine what needs to be fetched. This
     * method is doing that.
     *
     * @see _fetchRecord @see makeDefaultRecord
     *
     * @param {any} record
     * @returns {Deferred -> Object} resolves to the finished resource
     */
    _postprocess: function (record) {
        var self = this;
        var defs = [];
        _.each(record.fieldNames, function (name) {
            var field = record.fields[name];
            var attrs = record.fieldAttrs[name] || {};
            var options = attrs.options || {};
            if (options.always_reload) {
                if (record.fields[name].type === 'many2one' && record.data[name]) {
                    var element = self.localData[record.data[name]];
                    defs.push(self._rpc(field.relation, 'name_get')
                        .args([element.data.id])
                        .withContext(self._getContext(record, {fieldName: name}))
                        .exec()
                        .then(function (result) {
                            element.data.display_name = result[0][1];
                        }));
                }
            }
        });

        defs.push(this._fetchSpecialData(record));

        return $.when.apply($, defs).then(function () {
            return record;
        });
    },
    /**
     * For a grouped list resource, this method fetches all group data by
     * performing a /read_group. It also tries to read open subgroups if they
     * were open before.
     *
     * @param {Object} list valid resource object
     * @returns {Deferred<Object>} resolves to the fetched group object
     */
    _readGroup: function (list) {
        var self = this;
        var fields = _.uniq(list.fieldNames.concat(list.groupedBy));
        return this._rpc(list.model, 'read_group')
            .withFields(fields)
            .withContext(list.context)
            .groupBy(list.groupedBy)
            .lazy(true)
            .exec()
            .then(function (groups) {
                var rawGroupBy = list.groupedBy[0].split(':')[0];
                var previousGroups = _.map(list.data, function (groupID) {
                    return self.localData[groupID];
                });
                list.data = [];
                list.count = groups.length;
                var defs = [];

                _.each(groups, function (group) {
                    var aggregateValues = {};
                    _.each(group, function (value, key) {
                        if (_.contains(fields, key) && key !== list.groupedBy[0]) {
                            aggregateValues[key] = value;
                        }
                    });
                    var newGroup = self._makeDataPoint({
                        modelName: list.model,
                        count: group[rawGroupBy + '_count'],
                        domain: group.__domain,
                        context: list.context,
                        fields: list.fields,
                        fieldNames: list.fieldNames,
                        fieldAttrs: list.fieldAttrs,
                        value: group[rawGroupBy],
                        aggregateValues: aggregateValues,
                        groupedBy: list.groupedBy.slice(1),
                        orderedBy: list.orderedBy,
                        limit: list.limit,
                        openGroupByDefault: list.openGroupByDefault,
                        type: 'list', // nested groupedBys not handled yet
                    });
                    list.data.push(newGroup.id);
                    var old_group = _.find(previousGroups, function (g) {
                        return g.res_id === newGroup.res_id && g.value === newGroup.value;
                    });
                    if (old_group) {
                        newGroup.isOpen = old_group.isOpen;
                    } else if (!newGroup.openGroupByDefault) {
                        newGroup.isOpen = false;
                    } else {
                        newGroup.isOpen = '__fold' in group ? !group.__fold : true;
                    }
                    if (newGroup.isOpen && newGroup.count > 0) {
                        defs.push(self._fetchUngroupedList(newGroup));
                    }
                });
                return $.when.apply($, defs).then(function () {
                    // generate the res_ids of the main list, being the concatenation
                    // of the fetched res_ids in each group
                    list.res_ids = _.flatten(_.map(arguments, function (group) {
                        return group ? group.res_ids : [];
                    }));
                    return list;
                });
            });
    },
    /**
     * For 'static' list, such as one2manys in a form view, we can do a /read
     * instead of a /search_read.
     *
     * @param {Object} list a valid resource object
     * @returns {Deferred -> Object} resolves to the fetched list object
     */
    _readUngroupedList: function (list) {
        var self = this;
        var def;
        var ids = [];
        var missingIds = [];
        var upper_bound = list.limit ? Math.min(list.offset + list.limit, list.count) : list.count;
        for (var i = list.offset; i < upper_bound; i++) {
            var id = list.res_ids[i];
            ids.push(id);
            if (!list._cache[id]) {
                missingIds.push(id);
            }
        }
        if (missingIds.length) {
            def = this._rpc(list.model, 'read')
                .args([missingIds, list.fieldNames])
                .withContext({}) // FIXME
                .exec();
        } else {
            def = $.when();
        }
        return def.then(function (records) {
            list.data = [];
            _.each(ids, function (id) {
                var dataPoint;
                if (id in list._cache) {
                    dataPoint = self.localData[list._cache[id]];
                } else {
                    dataPoint = self._makeDataPoint({
                        data: _.findWhere(records, {id: id}),
                        fieldAttrs: list.fieldAttrs,
                        fieldNames: list.fieldNames,
                        fields: list.fields,
                        modelName: list.model,
                        parentID: list.id,
                    });

                    // add many2one records
                    self._parseServerData(list.fieldNames, dataPoint.fields, dataPoint.data);
                    list._cache[id] = dataPoint.id;
                }
                list.data.push(dataPoint.id);
            });
            self._sortList(list);
            return list;
        });
    },
    /**
     * Do a /search_read to get data for a list resource.  This does a
     * /search_read because the data may not be static (for ex, a list view).
     *
     * @param {Object} list
     * @returns {Deferred}
     */
    _searchReadUngroupedList: function (list) {
        var self = this;
        return this._rpc(list.model, 'search_read')
            .withFields(list.fieldNames)
            .withDomain(list.domain || [])
            .withLimit(list.limit)
            .withOffset(list.offset)
            .orderBy(list.orderedBy)
            .exec()
            .then(function (result) {
                list.count = result.length;
                var data = _.map(result.records, function (record) {
                    var dataPoint = self._makeDataPoint({
                        data: record,
                        fields: list.fields,
                        fieldNames: list.fieldNames,
                        fieldAttrs: list.fieldAttrs,
                        modelName: list.model,
                        parentID: list.id,
                    });

                    // add many2one records
                    self._parseServerData(list.fieldNames, dataPoint.fields, dataPoint.data);
                    return dataPoint.id;
                });
                list.data = data;
                list.res_ids = _.pluck(result.records, 'id');
                return list;
            });
    },
    /**
     * Change the offset of a record. Note that this does not reload the data.
     * The offset is used to load a different record in a list of record (for
     * example, a form view with a pager.  Clicking on next/previous actually
     * changes the offset through this method).
     *
     * @param {string} elementId local id for the resource
     * @param {number} offset
     */
    _setOffset: function (elementId, offset) {
        var element = this.localData[elementId];
        element.offset = offset;
        if (element.type === 'record' && element.res_ids.length) {
            element.res_id = element.res_ids[offset];
        }
    },
    /**
     * Do a in-memory sort of a list resource data points. This method assumes
     * that the list data has already been fetched.  Its intended use is for
     * static datasets, such as a one2many in a form view.
     *
     * @param {Object} list
     */
    _sortList: function (list) {
        var self = this;
        if (list.orderedBy.length) {
            // sort records according to ordered_by[0]
            var order = list.orderedBy[0];
            list.data.sort(function (r1, r2) {
                var data1 = self.localData[r1].data;
                var data2 = self.localData[r2].data;
                if (data1[order.name] < data2[order.name]) {
                    return order.asc ? -1 : 1;
                }
                if (data1[order.name] > data2[order.name]) {
                    return order.asc ? 1 : -1;
                }
                return 0;
            });
        }
    },
    /**
     * Helper method.  Recursively traverses the data, starting from the element
     * record (or list), then following all relations.  This is useful when one
     * want to determine a property for the current record.
     *
     * For example, isDirty need to check all relations to find out if something
     * has been modified, or not.
     *
     * @param {Object} element a valid local resource
     * @param {callback} fn a function to be called on each visited element
     */
    _visitChildren: function (element, fn) {
        var self = this;
        fn(element);
        if (element.type === 'record') {
            for (var fieldName in element.data) {
                var field = element.fields[fieldName];
                if (!field) {
                    continue;
                }
                if (_.contains(['one2many', 'many2one', 'many2many'], field.type)) {
                    var relationalElement = this.localData[element.data[fieldName]];

                    // relationalElement could be empty in the case of a many2one
                    if (relationalElement) {
                        self._visitChildren(relationalElement, fn);
                    }
                }
            }
        }
        if (element.type === 'list') {
            _.each(element.data, function (elemId) {
                var elem = self.localData[elemId];
                self._visitChildren(elem, fn);
            });
        }
    },
});

return BasicModel;
});
