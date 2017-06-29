odoo.define('web_editor.ace', function (require) {
'use strict';

var ajax = require('web.ajax');
var core = require('web.core');
var Dialog = require('web.Dialog');
var Widget = require('web.Widget');
var weContext = require('web_editor.context');
var localStorage = require('web.local_storage');
var session = require('web.session');

var _t = core._t;

/**
 * Formats a content-check result (@see checkXML, checkLESS).
 *
 * @param {boolean} isValid
 * @param {integer} [errorLine] needed if isValid is false
 * @param {string} [errorMessage] needed if isValid is false
 * @returns {Object}
 */
function _getCheckReturn(isValid, errorLine, errorMessage) {
    return {
        isValid: isValid,
        error: isValid ? null : {
            line: errorLine,
            message: errorMessage,
        },
    };
}
/**
 * Checks the syntax validity of some XML.
 *
 * @param {string} xml
 * @returns {Object} @see _getCheckReturn
 */
function checkXML(xml) {
    if (typeof window.DOMParser != 'undefined') {
        var xmlDoc = (new window.DOMParser()).parseFromString(xml, 'text/xml');
        var error = xmlDoc.getElementsByTagName('parsererror');
        if (error.length > 0) {
            return _getCheckReturn(false, parseInt(error[0].innerHTML.match(/[Ll]ine[^\d]+(\d+)/)[1], 10), error[0].innerHTML);
        }
    } else if (typeof window.ActiveXObject != 'undefined' && new window.ActiveXObject('Microsoft.XMLDOM')) {
        var xmlDocIE = new window.ActiveXObject('Microsoft.XMLDOM');
        xmlDocIE.async = 'false';
        xmlDocIE.loadXML(xml);
        if (xmlDocIE.parseError.line > 0) {
            return _getCheckReturn(false, xmlDocIE.parseError.line, xmlDocIE.parseError.reason);
        }
    }
    return _getCheckReturn(true);
}
/**
 * Formats some XML so that it has proper indentation and structure.
 *
 * @param {string} xml
 * @returns {string} formatted xml
 */
function formatXML(xml) {
    return window.vkbeautify.xml(xml, 4);
}
/**
 * Checks the syntax validity of some LESS.
 *
 * @param {string} less
 * @returns {Object} @see _getCheckReturn
 */
var checkLESS = (function () {
    var mapping = {
        '{': '}', '}': '{',
        '(': ')', ')': '(',
        '[': ']', ']': '[',
    };
    var openings = ['{', '(', '['];
    var closings = ['}', ')', ']'];

    return function (less) {
        var stack = [];
        var line = 1;
        for (var i = 0 ; i < less.length ; i++) {
            if (_.contains(openings, less[i])) {
                stack.push(less[i]);
            } else if (_.contains(closings, less[i])) {
                if (stack.pop() !== mapping[less[i]]) {
                    return _getCheckReturn(false, line, _t("Unexpected ") + less[i]);
                }
            } else if (less[i] === '\n') {
                line++;
            }
        }
        if (stack.length > 0) {
            return _getCheckReturn(false, line, _t("Expected ") + mapping[stack.pop()]);
        }
        return _getCheckReturn(true);
    };
})();
/**
 * Formats some LESS so that it has proper indentation and structure.
 *
 * @todo Right now, this does return the given LESS content, untouched.
 * @param {string} less
 * @returns {string} formatted less
 */
function formatLESS(less) {
    return less;
}

/**
 * Allows to visualize resources (by default, XML views) and edit them.
 */
var ViewEditor = Widget.extend({
    template: 'web_editor.ace_view_editor',
    xmlDependencies: ['/web_editor/static/src/xml/ace.xml'],
    events: {
        'click .o_ace_type_switcher_choice': '_onTypeChoice',
        'change .o_res_list': '_onResChange',
        'click .js_include_bundles': '_onIncludeBundlesChange',
        'click .js_include_all_less': '_onIncludeAllLessChange',
        'click button[data-action=save]': '_onSaveClick',
        'click button[data-action=reset]': '_onResetClick',
        'click button[data-action=format]': '_onFormatClick',
        'click button[data-action=close]': '_onCloseClick',
    },

    /**
     * Initializes the parameters so that the ace editor knows which information
     * it has to load.
     *
     * @constructor
     * @param {Widget} parent
     * @param {string|integer} viewKey
     *        xml_id or id of the view whose linked resources have to be loaded.
     * @param {Object} [options]
     * @param {string|integer} [options.initialResID]
     *        a specific view ID / LESS URL to load on start (otherwise the main
     *        view ID associated with the specified viewKey will be used)
     * @param {string} [options.position=right]
     * @param {boolean} [options.doNotLoadViews=false]
     * @param {boolean} [options.doNotLoadLess=false]
     * @param {boolean} [options.includeBundles=false]
     * @param {boolean} [options.includeAllLess=false]
     * @param {string[]} [options.defaultBundlesRestriction]
     */
    init: function (parent, viewKey, options) {
        this._super.apply(this, arguments);

        this.viewKey = viewKey;
        this.options = _.defaults({}, options, {
            position: 'right',
            doNotLoadViews: false,
            doNotLoadLess: false,
            includeBundles: false,
            includeAllLess: false,
            defaultBundlesRestriction: [],
        });

        this.resources = {xml: {}, less: {}};
        this.editingSessions = {xml: {}, less: {}};
        this.currentType = 'xml';

        // Alias
        this.views = this.resources.xml;
        this.less = this.resources.less;
    },
    /**
     * Loads everything the ace library needs to work.
     * It also loads the resources to visualize (@see _loadResources).
     *
     * @override
     */
    willStart: function () {
        var js_def = ajax.loadJS('/web/static/lib/ace/ace.odoo-custom.js').then(function () {
            return $.when(
                ajax.loadJS('/web/static/lib/ace/mode-xml.js'),
                ajax.loadJS('/web/static/lib/ace/mode-less.js'),
                ajax.loadJS('/web/static/lib/ace/theme-monokai.js')
            );
        });
        return $.when(this._super.apply(this, arguments), js_def, this._loadResources());
    },
    /**
     * Initializes the library and initial view once the DOM is ready. It also
     * initializes the resize feature of the ace editor.
     *
     * @override
     */
    start: function () {
        this.$viewEditor = this.$('#ace-view-editor');
        this.$editor = this.$('.ace_editor');

        this.$typeSwitcherChoices = this.$('.o_ace_type_switcher_choice');
        this.$typeSwitcherBtn = this.$('.o_ace_type_switcher > .dropdown-toggle');

        this.$lists = {
            xml: this.$('#ace-view-list'),
            less: this.$('#ace-less-list')
        };
        this.$includeBundlesArea = this.$('.oe_include_bundles');
        this.$includeAllLessArea = this.$('.o_include_all_less');
        this.$viewID = this.$('#ace-view-id > span');

        this.$formatButton = this.$('button[data-action=format]');
        this.$resetButton = this.$('button[data-action=reset]');

        this.aceEditor = window.ace.edit(this.$viewEditor[0]);
        this.aceEditor.setTheme('ace/theme/monokai');

        var refX = 0;
        var resizing = false;
        var minWidth = 400;
        var debounceStoreEditorWidth = _.debounce(storeEditorWidth, 500);

        this._updateViewSelectDOM();

        var initResID;
        var initType;
        if (this.options.initialResID) {
            initResID = this.options.initialResID;
            initType = (_.isString(initResID) && initResID[0] === '/') ? 'less' : 'xml';
        } else {
            if (!this.options.doNotLoadLess) {
                initResID = this.sorted_less[0][1][0].url; // first bundle, less files, first one
                initType = 'less';
            }
            if (!this.options.doNotLoadViews) {
                initResID = (typeof this.viewKey === 'number' ? this.viewKey : _.findWhere(this.views, {xml_id: this.viewKey}).id);
                initType = 'xml';
            }
        }
        if (initResID) {
            this._displayResource(initResID, initType);
        }

        if (!this.sorted_views.length || !this.sorted_less.length) {
            _.defer((function () {
                this._switchType(this.sorted_views.length ? 'xml' : 'less');
                this.$typeSwitcherBtn.parent('.btn-group').addClass('hidden');
            }).bind(this));
        }

        $(document).on('mouseup.ViewEditor', stopResizing.bind(this)).on('mousemove.ViewEditor', updateWidth.bind(this));
        if (this.options.position === 'left') {
            this.$('.ace_scroller').after($('<div>').addClass('ace_resize_bar'));
            this.$('.ace_gutter').css({'cursor': 'default'});
            this.$el.on('mousedown.ViewEditor', '.ace_resize_bar', startResizing.bind(this));
        } else {
            this.$el.on('mousedown.ViewEditor', '.ace_gutter', startResizing.bind(this));
        }

        resizeEditor.call(this, readEditorWidth.call(this));

        return this._super.apply(this, arguments);

        function resizeEditor(target) {
            var width = Math.min(document.body.clientWidth, Math.max(parseInt(target, 10), minWidth));
            this.$editor.width(width);
            this.aceEditor.resize();
            this.$el.width(width);
        }
        function storeEditorWidth() {
            localStorage.setItem('ace_editor_width', this.$el.width());
        }
        function readEditorWidth() {
            var width = localStorage.getItem('ace_editor_width');
            return parseInt(width || 720, 10);
        }
        function startResizing(e) {
            refX = e.pageX;
            resizing = true;
        }
        function stopResizing() {
            resizing = false;
        }
        function updateWidth(e) {
            if (!resizing) return;

            var offset = e.pageX - refX;
            if (this.options.position === 'left') {
                offset = - offset;
            }
            var width = this.$el.width() - offset;
            refX = e.pageX;
            resizeEditor.call(this, width);
            debounceStoreEditorWidth.call(this);
        }
    },
    /**
     * @override
     */
    destroy: function () {
        this._super.apply(this, arguments);
        this.$el.off('.ViewEditor');
        $(document).off('.ViewEditor');
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Initializes a text editor for the specified resource.
     *
     * @private
     * @param {integer|string} resID - the ID/URL of the view/less file
     * @param {string} [type] (default to the currently selected one)
     * @returns {ace.EditSession}
     */
    _buildEditingSession: function (resID, type) {
        var self = this;
        type = type || this.currentType;
        var editingSession = new window.ace.EditSession(this.resources[type][resID].arch);
        editingSession.setUseWorker(false);
        editingSession.setMode('ace/mode/' + (type || this.currentType));
        editingSession.setUndoManager(new window.ace.UndoManager());
        editingSession.on('change', function () {
            _.defer(function () {
                self._toggleDirtyInfo(resID);
                self._showErrorLine();
            });
        });
        return editingSession;
    },
    /**
     * Forces the view/less file identified by its ID/URL to be displayed in the
     * editor. The method will update the resource select DOM element as well if
     * necessary.
     *
     * @private
     * @param {integer|string} resID
     * @param {string} [type] - the type of resource (either 'xml' or 'less')
     */
    _displayResource: function (resID, type) {
        if (type) {
            this._switchType(type);
        }

        var editingSession = this.editingSessions[this.currentType][resID];
        if (!editingSession) {
            editingSession = this.editingSessions[this.currentType][resID] = this._buildEditingSession(resID);
        }
        this.aceEditor.setSession(editingSession);

        if (this.currentType === 'xml') {
            this.$viewID.text(_.str.sprintf(_t("Template ID: %s"), this.views[resID].xml_id));
        } else {
            this.$viewID.text(_.str.sprintf(_t("Less file: %s"), resID));
        }
        this.$lists[this.currentType].select2('val', resID);

        this.$resetButton.toggleClass('hidden', this.currentType === 'xml' || !this.less[resID].customized);
    },
    /**
     * Formats the current resource being vizualized.
     * (@see formatXML, formatLESS)
     *
     * @private
     */
    _formatResource: function () {
        var res = this.aceEditor.getValue();
        var check = (this.currentType === 'xml' ? checkXML : checkLESS)(res);
        if (check.isValid) {
            this.aceEditor.setValue((this.currentType === 'xml' ? formatXML : formatLESS)(res));
        } else {
            this._showErrorLine(check.error.line, check.error.message, this._getSelectedResource());
        }
    },
    /**
     * Returns the currently selected resource data.
     *
     * @private
     * @returns {integer|string} view ID or less file URL
     */
    _getSelectedResource: function () {
        return this.$lists[this.currentType].select2('val');
    },
    /**
     * Loads data the ace editor will vizualize and process it. Default behavior
     * is loading the activate views, index them and build their hierarchy.
     *
     * @private
     * @returns {Deferred}
     */
    _loadResources: function () {
        // Reset resources
        this.resources = {xml: {}, less: {}};
        this.editingSessions = {xml: {}, less: {}};
        this.views = this.resources.xml;
        this.less = this.resources.less;

        // Load resources
        return this._rpc({
            route: '/web_editor/get_assets_editor_resources',
            params: {
                key: this.viewKey,
                get_views: !this.options.doNotLoadViews,
                get_less: !this.options.doNotLoadLess,
                bundles: this.options.includeBundles,
                bundles_restriction: this.options.includeAllLess ? [] : this.options.defaultBundlesRestriction,
            },
        }).then((function (resources) {
            _process_views.call(this, resources.views);
            _process_less.call(this, resources.less);
        }).bind(this));

        function _process_views(views) {
            // Only keep the active views and index them by ID.
            _.extend(this.views, _.indexBy(_.filter(views, function (view) {
                return view.active;
            }), 'id'));

            // Initialize a 0 level for each view and assign them an array containing their children.
            var self = this;
            var roots = [];
            _.each(this.views, function (view) {
                view.level = 0;
                view.children = [];
            });
            _.each(this.views, function (view) {
                var parentId = view.inherit_id[0];
                var parent = parentId && self.views[parentId];
                if (parent) {
                    parent.children.push(view);
                } else {
                    roots.push(view);
                }
            });

            // Assign the correct level based on children key and save a sorted array where
            // each view is followed by their children.
            this.sorted_views = [];
            function visit(view, level) {
                view.level = level;
                self.sorted_views.push(view);
                _.each(view.children, function (child) {
                    visit(child, level + 1);
                });
            }
            _.each(roots, function (root) {
                visit(root, 0);
            });
        }

        function _process_less(less) {
            // The received less data is already sorted by bundle and DOM order
            this.sorted_less = less;

            // Store the URL ungrouped by bundle and use the URL as key (resource ID)
            var self = this;
            _.each(less, function (bundleInfos) {
                _.each(bundleInfos[1], function (info) { info.bundle_xmlid = bundleInfos[0].xmlid; });
                _.extend(self.less, _.indexBy(bundleInfos[1], 'url'));
            });
        }
    },
    /**
     * Forces the view/less file identified by its ID/URL to be reset to the way
     * it was before the user started editing it.
     *
     * @todo views reset is not supported yet
     *
     * @private
     * @param {integer|string} [resID] (default to the currently selected one)
     * @param {string} [type] (default to the currently selected one)
     * @returns {Deferred}
     */
    _resetResource: function (resID, type) {
        resID = resID || this._getSelectedResource();
        type = type || this.currentType;

        if (this.currentType === 'xml') {
            return $.Defered().reject(_t("Reseting views is not supported yet"));
        } else {
            return this._rpc({
                route: '/web_editor/reset_less',
                params: {
                    url: resID,
                    bundle_xmlid: this.less[resID].bundle_xmlid,
                },
            });
        }
    },
    /**
     * Saves an unique LESS file.
     *
     * @private
     * @param {Object} session - contains the 'id' (url) and the 'text' of the
     *                         LESS file to save.
     * @return {Deferred} status indicates if the save is finished or if an
     *                    error occured.
     */
    _saveLess: function (session) {
        var def = $.Deferred();

        var self = this;
        this._rpc({
            route: '/web_editor/save_less',
            params: {
                url: session.id,
                bundle_xmlid: this.less[session.id].bundle_xmlid,
                content: session.text,
            },
        }).then(function () {
            self._toggleDirtyInfo(session.id, 'less', false);
            def.resolve();
        }, function (source, error) {
            def.reject(session, error);
        });

        return def;
    },
    /**
     * Saves every resource that has been modified. If one cannot be saved, none
     * is saved and an error message is displayed.
     *
     * @private
     * @return {Deferred} status indicates if the save is finished or if an
     *                    error occured.
     */
    _saveResources: function () {
        var toSave = {};
        var errorFound = false;
        _.each(this.editingSessions, (function (editingSessions, type) {
            if (errorFound) return;

            var dirtySessions = _.pick(editingSessions, function (session) {
                return session.getUndoManager().hasUndo();
            });
            toSave[type] = _.map(dirtySessions, function (session, resID) {
                return {
                    id: parseInt(resID, 10) || resID,
                    text: session.getValue(),
                };
            });

            this._showErrorLine();
            for (var i = 0 ; i < toSave[type].length && !errorFound ; i++) {
                var check = (type === 'xml' ? checkXML : checkLESS)(toSave[type][i].text);
                if (!check.isValid) {
                    this._showErrorLine(check.error.line, check.error.message, toSave[type][i].id, type);
                    errorFound = toSave[type][i];
                }
            }
        }).bind(this));
        if (errorFound) return $.Deferred().reject(errorFound);

        var defs = [];
        _.each(toSave, (function (_toSave, type) {
            defs = defs.concat(_.map(_toSave, (type === 'xml' ? this._saveView : this._saveLess).bind(this)));
        }).bind(this));

        return $.when.apply($, defs).fail((function (session, error) {
            Dialog.alert(this, '', {
                title: _t("Server error"),
                $content: $('<div/>').html(
                    _t("A server error occured. Please check you correctly signed in and that the file you are saving is well-formed.")
                    + '<br/>'
                    + error
                )
            });
        }).bind(this));
    },
    /**
     * Saves an unique XML view.
     *
     * @private
     * @param {Object} session - the 'id' and the 'text' of the view to save.
     * @returns {Deferred} status indicates if the save is finished or if an
     *                     error occured.
     */
    _saveView: function (session) {
        var def = $.Deferred();

        var self = this;
        this._rpc({
            model: 'ir.ui.view',
            method: 'write',
            args: [[session.id], {arch: session.text}, _.extend(weContext.get(), {lang: null})],
        }).then(function () {
            self._toggleDirtyInfo(session.id, 'xml', false);
            def.resolve();
        }, function (source, error) {
            def.reject(session, error);
        });

        return def;
    },
    /**
     * Shows a line which produced an error. Red color is added to the editor,
     * the cursor move to the line and a message is opened on click on the line
     * number. If called without argument, the effects are removed.
     *
     * @private
     * @param {integer} [line] - the line number to highlight
     * @param {string} [message] - to show on click on the line number
     * @param {integer|string} [resID]
     * @param {string} [type]
     */
    _showErrorLine: function (line, message, resID, type) {
        if (line === undefined || line <= 0) {
            if (this.$errorLine) {
                this.$errorLine.removeClass('o_error');
                this.$errorLine.off('.o_error');
                this.$errorLine = undefined;
                this.$errorContent.removeClass('o_error');
                this.$errorContent = undefined;
            }
            return;
        }

        if (type) this._switchType(type);

        if (this._getSelectedResource() === resID) {
            __showErrorLine.call(this, line);
        } else {
            var onChangeSession = (function () {
                this.aceEditor.off('changeSession', onChangeSession);
                _.delay(__showErrorLine.bind(this, line), 400);
            }).bind(this);
            this.aceEditor.on('changeSession', onChangeSession);
            this._displayResource(resID, this.currentType);
        }

        function __showErrorLine(line) {
            this.aceEditor.gotoLine(line);
            this.$errorLine = this.$viewEditor.find('.ace_gutter-cell').filter(function () {
                return parseInt($(this).text()) === line;
            }).addClass('o_error');
            this.$errorLine.addClass('o_error').on('click.o_error', function () {
                var $message = $('<div/>').html(message);
                $message.text($message.text());
                Dialog.alert(this, "", {$content: $message});
            });
            this.$errorContent = this.$viewEditor.find('.ace_scroller').addClass('o_error');
        }
    },
    /**
     * Switches to the LESS or XML edition. Calling this method will adapt all
     * DOM elements to keep the editor consistent.
     *
     * @private
     * @param {string} type - either 'xml' or 'less'
     */
    _switchType: function (type) {
        this.currentType = type;
        this.$typeSwitcherBtn.html(this.$typeSwitcherChoices.filter('[data-type=' + type + ']').html());
        _.each(this.$lists, function ($list, _type) { $list.toggleClass('hidden', type !== _type); });
        this.$lists[type].change();

        this.$includeBundlesArea.toggleClass('hidden', this.currentType === 'less' || !session.debug);
        this.$includeAllLessArea.toggleClass('hidden', this.currentType === 'xml' || !session.debug || this.options.defaultBundlesRestriction.length === 0);
        this.$formatButton.toggleClass('hidden', this.currentType === 'less');
    },
    /**
     * Updates the select option DOM element associated with a particular resID
     * to indicate if the option is dirty or not.
     *
     * @private
     * @param {integer|string} resID
     * @param {string} [type] (default to the currently selected one)
     * @param {boolean} [isDirty] true if the view is dirty, default to content
     *                            of UndoManager
     */
    _toggleDirtyInfo: function (resID, type, isDirty) {
        type = type || this.currentType;

        if (!resID || !this.editingSessions[type][resID]) return;

        var $option = this.$lists[type].find('[value=' + resID + ']');
        if (isDirty === undefined) {
            isDirty = this.editingSessions[type][resID].getUndoManager().hasUndo();
        }
        $option.data('dirty', isDirty);
    },
    /**
     * Renders the content of the view/file <select/> DOM element according to
     * current widget data.
     *
     * @private
     */
    _updateViewSelectDOM: function () {
        var currentId = this._getSelectedResource();

        var self = this;
        this.$lists.xml.empty();
        _.each(this.sorted_views, function (view) {
            self.$lists.xml.append($('<option/>', {
                value: view.id,
                text: view.name,
                selected: currentId === view.id,
                'data-level': view.level,
                'data-debug': view.xml_id,
            }));
        });

        this.$lists.less.empty();
        _.each(this.sorted_less, function (bundleInfos) {
            var $optgroup = $('<optgroup/>', {
                label: bundleInfos[0].name,
            }).appendTo(self.$lists.less);
            _.each(bundleInfos[1], function (lessInfo) {
                var name = lessInfo.url.substring(_.lastIndexOf(lessInfo.url, '/') + 1, lessInfo.url.length - 5);
                $optgroup.append($('<option/>', {
                    value: lessInfo.url,
                    text: name,
                    selected: currentId === lessInfo.url,
                    'data-debug': lessInfo.url,
                    'data-customized': lessInfo.customized
                }));
            });
        });

        this.$lists.xml.select2('destroy');
        this.$lists.xml.select2({
            formatResult: _formatDisplay,
            formatSelection: _formatDisplay,
        });
        this.$lists.less.select2('destroy');
        this.$lists.less.select2({
            formatResult: _formatDisplay,
            formatSelection: _formatDisplay,
        });

        function _formatDisplay(data) {
            var $elem = $(data.element);

            var $div = $('<div/>',  {
                text: data.text || '',
                style: 'padding: 0 0 0 ' + (24 * $elem.data('level')) + 'px',
            });

            if ($elem.data('dirty') || $elem.data('customized')) {
                $div.prepend($('<span/>', {
                    class: 'fa fa-floppy-o ' + ($elem.data('dirty') ? 'text-warning' : 'text-success'),
                    style: 'margin-right: 8px;',
                }));
            }

            if (session.debug && $elem.data('debug')) {
                $div.append($('<span/>', {
                    text: ' (' + $elem.data('debug') + ')',
                    class: 'text-muted',
                    style: 'font-size: 80%',
                }));
            }

            return $div;
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Called when the close button is clicked -> hides the ace editor.
     *
     * @private
     */
    _onCloseClick: function () {
        this.do_hide();
    },
    /**
     * Called when the format button is clicked -> format the current resource.
     *
     * @private
     */
    _onFormatClick: function () {
        this._formatResource();
    },
    /**
     * Called when the checkbox which indicates if all LESS should be included
     * is toggled -> reloads the resources accordingly.
     *
     * @private
     * @param {Event}
     */
    _onIncludeAllLessChange: function (ev) {
        this.options.includeAllLess = $(ev.target).prop('checked');
        this._loadResources().then(this._updateViewSelectDOM.bind(this));
    },
    /**
     * Called when the checkbox which indicates if assets bundles should be
     * included is toggled -> reloads the resources accordingly.
     *
     * @private
     * @param {Event}
     */
    _onIncludeBundlesChange: function (ev) {
        this.options.includeBundles = $(ev.target).prop('checked');
        this._loadResources().then(this._updateViewSelectDOM.bind(this));
    },
    /**
     * Called when another resource is selected -> displays it.
     *
     * @private
     */
    _onResChange: function () {
        this._displayResource(this._getSelectedResource());
    },
    /**
     * Called when the reset button is clicked -> resets the resources to its
     * original standard odoo state.
     *
     * @private
     */
    _onResetClick: function () {
        var self = this;
        Dialog.confirm(this, _t("If you reset this file, all your customizations will be lost as it will be reverted to the default file."), {
            title: _t("Careful !"),
            confirm_callback: function () {
                self._resetResource(self._getSelectedResource());
            },
        });
    },
    /**
     * Called when the save button is clicked -> saves the dirty resources and
     * reloads.
     *
     * @private
     */
    _onSaveClick: function () {
        this._saveResources();
    },
    /**
     * Called when the user wants to switch from xml to less or vice-versa ->
     * adapt resources choices and displays a resource of that type.
     *
     * @private
     * @param {Event} ev
     */
    _onTypeChoice: function (ev) {
        ev.preventDefault();
        this._switchType($(ev.target).data('type'));
    },
});

return ViewEditor;
});
