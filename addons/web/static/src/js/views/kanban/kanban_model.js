odoo.define('web.KanbanModel', function (require) {
"use strict";

/**
 * The KanbanModel extends the BasicModel to add Kanban specific features like
 * moving a record from a group to another, resequencing records...
 */

var BasicModel = require('web.BasicModel');
var config = require('web.config');

var KanbanModel = BasicModel.extend({

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Adds a record to a group in the localData, and fetch the record.
     *
     * @param {string} groupID localID of the group
     * @param {integer} resId id of the record
     * @returns {Deferred<string>} resolves to the local id of the new record
     */
    addRecordToGroup: function (groupID, resId) {
        var group = this.localData[groupID];
        var new_record = this._makeDataPoint({
            res_id: resId,
            modelName: group.model,
            fields: group.fields,
            fieldsInfo: group.fieldsInfo,
            viewType: group.viewType,
        });
        group.data.unshift(new_record.id);
        group.res_ids.unshift(resId);
        group.count++;

        // update the res_ids and count of the parent
        this.localData[group.parentID].count++;
        this._updateParentResIDs(group);

        return this._fetchRecord(new_record).then(function (result) {
            return result.id;
        });
    },
    /**
     * Creates a new group from a name (performs a name_create).
     *
     * @param {string} name
     * @param {string} parentID localID of the parent of the group
     * @returns {Deferred<string>} resolves to the local id of the new group
     */
    createGroup: function (name, parentID) {
        var self = this;
        var parent = this.localData[parentID];
        var groupBy = parent.groupedBy[0];
        var groupByField = parent.fields[groupBy];
        if (!groupByField || groupByField.type !== 'many2one') {
            return $.Deferred().reject(); // only supported when grouped on m2o
        }
        return this._rpc({
                model: groupByField.relation,
                method: 'name_create',
                args: [name],
                context: parent.context, // todo: combine with view context
            })
            .then(function (result) {
                var newGroup = self._makeDataPoint({
                    modelName: parent.model,
                    context: parent.context,
                    domain: parent.domain.concat([[groupBy,"=",result[0]]]),
                    fields: parent.fields,
                    fieldsInfo: parent.fieldsInfo,
                    groupedBy: parent.groupedBy,
                    isOpen: true,
                    limit: parent.limit,
                    parentID: parent.id,
                    openGroupByDefault: true,
                    orderedBy: parent.orderedBy,
                    value: result,
                    viewType: parent.viewType,
                });

                // newGroup.is_open = true;
                parent.data.push(newGroup.id);
                return newGroup.id;
            });
    },
    /**
     * Add the key `tooltipData` (kanban specific) when performing a `geŧ`.
     *
     * @override
     * @see _readTooltipFields
     * @returns {Object}
     */
    get: function () {
        var result = this._super.apply(this, arguments);
        var dp = result && this.localData[result.id];
        if (dp && dp.tooltipData) {
            result.tooltipData = $.extend(true, {}, dp.tooltipData);
        }
        if (dp && dp.progressBarValues) {
            result.progressBarValues = $.extend(true, {}, dp.progressBarValues);
        }
        return result;
    },
    /**
     * Same as @see get but getting the parent element whose ID is given.
     *
     * @param {string} id
     * @returns {Object}
     */
    getColumn: function (id) {
        var element = this.localData[id];
        if (element) {
            return this.get(element.parentID);
        }
        return null;
    },
    /**
     * @override
     */
    load: function (params) {
        this.defaultGroupedBy = params.groupBy;
        params.groupedBy = (params.groupedBy && params.groupedBy.length) ? params.groupedBy : this.defaultGroupedBy;
        return this._super(params);
    },
    /**
     * Load more records in a group.
     *
     * @param {string} groupID localID of the group
     * @param {integer} offset optional offset override
     * @returns {Deferred<string>} resolves to the localID of the group
     */
    loadMore: function (groupID, offset) {
        var group = this.localData[groupID];
        offset = offset === 0 ? 0 : group.loadMoreOffset + group.limit;
        return this.reload(group.id, {
            loadMoreOffset: offset,
        });
    },
    /**
     * Moves a record from a group to another.
     *
     * @param {string} recordID localID of the record
     * @param {string} groupID localID of the new group of the record
     * @param {string} parentID localID of the parent
     * @returns {Deferred<string[]>} resolves to a pair [oldGroupID, newGroupID]
     */
    moveRecord: function (recordID, groupID, parentID) {
        var self = this;
        var parent = this.localData[parentID];
        var new_group = this.localData[groupID];
        var changes = {};
        var groupedFieldName = parent.groupedBy[0];
        var groupedField = parent.fields[groupedFieldName];
        if (groupedField.type === 'many2one') {
            changes[groupedFieldName] = {
                id: new_group.res_id,
                display_name: new_group.value,
            };
        } else if (groupedField.type === 'selection') {
            var value = _.findWhere(groupedField.selection, {1: new_group.value});
            changes[groupedFieldName] = value && value[0] || false;
        } else {
            changes[groupedFieldName] = new_group.value;
        }

        // Manually updates groups data. Note: this is done before the actual
        // save as it might need to perform a read group in some cases so those
        // updated data might be overriden again.
        var record = self.localData[recordID];
        var resID = record.res_id;
        // Remove record from its current group
        var old_group;
        for (var i = 0; i < parent.data.length; i++) {
            old_group = self.localData[parent.data[i]];
            var index = _.indexOf(old_group.data, recordID);
            if (index >= 0) {
                old_group.data.splice(index, 1);
                old_group.count--;
                old_group.res_ids = _.without(old_group.res_ids, resID);
                self._updateParentResIDs(old_group);
                break;
            }
        }
        // Add record to its new group
        new_group.data.push(recordID);
        new_group.res_ids.push(resID);
        new_group.count++;

        return this.notifyChanges(recordID, changes).then(function () {
            return self.save(recordID);
        }).then(function () {
            record.parentID = new_group.id;
            return [old_group.id, new_group.id];
        });
    },
    /**
     * @override
     */
    reload: function (id, options) {
        // if the groupBy is given in the options and if it is an empty array,
        // fallback on the default groupBy
        if (options && options.groupBy && !options.groupBy.length) {
            options.groupBy = this.defaultGroupedBy;
        }
        var def = this._super(id, options);
        return this._reloadProgressBarGroupFromRecord(id, def);
    },
    /**
     * @override
     */
    save: function (recordID) {
        var def = this._super.apply(this, arguments);
        return this._reloadProgressBarGroupFromRecord(recordID, def);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * @override
     */
    _makeDataPoint: function (params) {
        var dataPoint = this._super.apply(this, arguments);
        if (params.progressBar) {
            dataPoint.progressBar = params.progressBar;
        }
        return dataPoint;
    },
    /**
     * @override
     */
    _load: function (dataPoint, options) {
        if (dataPoint.progressBar) {
            return this._readProgressBarGroup(dataPoint, options);
        }
        return this._super.apply(this, arguments);
    },
    /**
     * Ensures that there is no nested groups in Kanban (only the first grouping
     * level is taken into account).
     *
     * @override
     * @private
     * @param {Object} list valid resource object
     */
    _readGroup: function (list) {
        var self = this;
        if (list.groupedBy.length > 1) {
            list.groupedBy = [list.groupedBy[0]];
        }
        // to prevent pre-loading data by default in mobile for kanban column
        // by setting openGroupByDefault to 'false' which will set column's isOpen property
        // to false and will ingore _load().
        if (config.isMobile) {
            list.openGroupByDefault = false;
        }
        return this._super.apply(this, arguments).then(function (result) {
            return self._readTooltipFields(list).then(_.constant(result));
        });
    },
    /**
     * @private
     * @param {Object} dataPoint
     * @returns {Deferred<Object>}
     */
    _readProgressBarGroup: function (list, options) {
        var self = this;
        var groupsDef = this._readGroup(list, options);
        var progressBarDef = this._rpc({
            model: list.model,
            method: 'read_progress_bar',
            kwargs: {
                domain: list.domain,
                group_by: list.groupedBy[0],
                progress_bar: list.progressBar,
                context: list.context,
            },
        });
        return $.when(groupsDef, progressBarDef).then(function (a, data) {
            _.each(list.data, function (groupID) {
                var group = self.localData[groupID];
                group.progressBarValues = _.extend({
                    counts: data[group.value] || {},
                }, list.progressBar);
            });
            return list;
        });
    },
    /**
     * Fetches tooltip specific fields on the group by relation and stores it in
     * the column datapoint in a special key `tooltipData`.
     * Data for the tooltips (group_by_tooltip) are fetched in batch for all
     * groups, to avoid doing multiple calls.
     * Data are stored in a special key `tooltipData` on the datapoint.
     * Note that the option `group_by_tooltip` is only for m2o fields.
     *
     * @private
     * @param {Object} list a list of groups
     * @returns {Deferred}
     */
    _readTooltipFields: function (list) {
        var self = this;
        var groupedByField = list.fields[list.groupedBy[0].split(':')[0]];
        if (groupedByField.type !== 'many2one') {
            return $.when();
        }
        var groupIds = _.reduce(list.data, function (groupIds, id) {
            var res_id = self.get(id, {raw: true}).res_id;
            // The field on which we are grouping might not be set on all records
            if (res_id) {
                groupIds.push(res_id);
            }
            return groupIds;
        }, []);
        var tooltipFields = [];
        var groupedByFieldInfo = list.fieldsInfo.kanban[list.groupedBy[0]];
        if (groupedByFieldInfo && groupedByFieldInfo.options) {
            tooltipFields = Object.keys(groupedByFieldInfo.options.group_by_tooltip || {});
        }
        if (groupIds.length && tooltipFields.length) {
            var fieldNames = _.union(['display_name'], tooltipFields);
            return this._rpc({
                model: groupedByField.relation,
                method: 'read',
                args: [groupIds, fieldNames],
                context: list.context,
            }).then(function (result) {
                _.each(list.data, function (id) {
                    var dp = self.localData[id];
                    dp.tooltipData = _.findWhere(result, {id: dp.res_id});
                });
            });
        }
        return $.when();
    },
    /**
     * Reloads all progressbar data if the given id is a record's one. This is
     * done after given deferred and insures that the given deferred's result is
     * not lost.
     *
     * @private
     * @param {string} recordID
     * @param {Deferred} def
     * @returns {Deferred}
     */
    _reloadProgressBarGroupFromRecord: function (recordID, def) {
        var element = this.localData[recordID];
        if (element.type !== 'record') {
            return def;
        }

        // If we updated a record, then we must potentially update columns'
        // progressbars, so we need to load groups info again
        var self = this;
        while (element) {
            if (element.progressBar) {
                return def.then(function (data) {
                    return self._load(element, {onlyGroups: true}).then(function () {
                        return data;
                    });
                });
            }
            element = this.localData[element.parentID];
        }
        return def;
    },
});
return KanbanModel;
});
