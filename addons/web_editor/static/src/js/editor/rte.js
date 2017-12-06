odoo.define('web_editor.rte', function (require) {
'use strict';

var concurrency = require('web.concurrency');
var core = require('web.core');
var Widget = require('web.Widget');
var weContext = require('web_editor.context');
var summernote = require('web_editor.summernote');
var weWidgets = require('web_editor.widget');

var _t = core._t;

// Summernote Lib (neek change to make accessible: method and object)
var dom = summernote.core.dom;
var range = summernote.core.range;

// Change History to have a global History for all summernote instances
var History = function History($editable) {
    var aUndo = [];
    var pos = 0;
    var toSnap;

    this.makeSnap = function (event, rng) {
        rng = rng || range.create();
        var elEditable = $(rng && rng.sc).closest('.o_editable')[0];
        if (!elEditable) {
            return false;
        }
        return {
            event: event,
            editable: elEditable,
            contents: elEditable.innerHTML,
            bookmark: rng && rng.bookmark(elEditable),
            scrollTop: $(elEditable).scrollTop()
        };
    };

    this.applySnap = function (oSnap) {
        var $editable = $(oSnap.editable);

        if (document.documentMode) {
            $editable.removeAttr('contentEditable').removeProp('contentEditable');
        }

        $editable.html(oSnap.contents).scrollTop(oSnap.scrollTop);
        $('.oe_overlay').remove();
        $('.note-control-selection').hide();

        $editable.trigger('content_changed');

        try {
            var r = oSnap.editable.innerHTML === '' ? range.create(oSnap.editable, 0) : range.createFromBookmark(oSnap.editable, oSnap.bookmark);
            r.select();
        } catch (e) {
            console.error(e);
            return;
        }

        $(document).trigger('click');
        $('.o_editable *').filter(function () {
            var $el = $(this);
            if ($el.data('snippet-editor')) {
                $el.removeData();
            }
        });


        _.defer(function () {
            var target = dom.isBR(r.sc) ? r.sc.parentNode : dom.node(r.sc);
            if (!target) {
                return;
            }

            $editable.trigger('applySnap');

            var evt = document.createEvent('MouseEvents');
            evt.initMouseEvent('click', true, true, window, 0, 0, 0, 0, 0, false, false, false, false, 0, target);
            target.dispatchEvent(evt);

            $editable.trigger('keyup');
        });
    };

    this.undo = function () {
        if (!pos) { return; }
        var _toSnap = toSnap;
        if (_toSnap) {
            this.saveSnap();
        }
        if (!aUndo[pos] && (!aUndo[pos] || aUndo[pos].event !== 'undo')) {
            var temp = this.makeSnap('undo');
            if (temp && (!pos || temp.contents !== aUndo[pos-1].contents)) {
                aUndo[pos] = temp;
            } else {
               pos--;
            }
        } else if (_toSnap) {
            pos--;
        }
        this.applySnap(aUndo[Math.max(--pos,0)]);
        while (pos && (aUndo[pos].event === 'blur' || (aUndo[pos+1].editable ===  aUndo[pos].editable && aUndo[pos+1].contents ===  aUndo[pos].contents))) {
            this.applySnap(aUndo[--pos]);
        }
    };

    this.hasUndo = function () {
        return (toSnap && (toSnap.event !== 'blur' && toSnap.event !== 'activate' && toSnap.event !== 'undo')) ||
            !!_.find(aUndo.slice(0, pos+1), function (undo) {
                return undo.event !== 'blur' && undo.event !== 'activate' && undo.event !== 'undo';
            });
    };

    this.getEditableHasUndo = function () {
        var editable = [];
        if ((toSnap && (toSnap.event !== 'blur' && toSnap.event !== 'activate' && toSnap.event !== 'undo'))) {
            editable.push(toSnap.editable);
        }
        _.each(aUndo.slice(0, pos+1), function (undo) {
            if (undo.event !== 'blur' && undo.event !== 'activate' && undo.event !== 'undo') {
                editable.push(undo.editable);
            }
        });
        return _.uniq(editable);
    };

    this.redo = function () {
        if (!aUndo[pos+1]) { return; }
        this.applySnap(aUndo[++pos]);
        while (aUndo[pos+1] && aUndo[pos].event === 'active') {
            this.applySnap(aUndo[pos++]);
        }
    };

    this.hasRedo = function () {
        return aUndo.length > pos+1;
    };

    this.recordUndo = function ($editable, event, internal_history) {
        var self = this;
        if (!$editable) {
            var rng = range.create();
            if (!rng) return;
            $editable = $(rng.sc).closest('.o_editable');
        }

        if (aUndo[pos] && (event === 'applySnap' || event === 'activate')) {
            return;
        }

        if (!internal_history) {
            if (!event || !toSnap || !aUndo[pos-1] || toSnap.event === 'activate') { // don't trigger change for all keypress
                setTimeout(function () {
                    $editable.trigger('content_changed');
                },0);
            }
        }

        if (aUndo[pos]) {
            pos = Math.min(pos, aUndo.length);
            aUndo.splice(Math.max(pos,1), aUndo.length);
        }

        // => make a snap when the user change editable zone (because: don't make snap for each keydown)
        if (toSnap && (toSnap.split || !event || toSnap.event !== event || toSnap.editable !== $editable[0])) {
            this.saveSnap();
        }

        if (pos && aUndo[pos-1].editable !== $editable[0]) {
            var snap = this.makeSnap('blur', range.create(aUndo[pos-1].editable, 0));
            pos++;
            aUndo.push(snap);
        }

        if (range.create()) {
            toSnap = self.makeSnap(event);
        } else {
            toSnap = false;
        }
    };

    this.splitNext = function () {
        if (toSnap) {
            toSnap.split = true;
        }
    };

    this.saveSnap = function () {
        if (toSnap) {
            if (!aUndo[pos]) {
                pos++;
            }
            aUndo.push(toSnap);
            delete toSnap.split;
            toSnap = null;
        }
    };
};
var history = new History();

// jQuery extensions
$.extend($.expr[':'], {
    o_editable: function (node, i, m) {
        while (node) {
            if (node.className && _.isString(node.className)) {
                if (node.className.indexOf('o_not_editable')!==-1 ) {
                    return false;
                }
                if (node.className.indexOf('o_editable')!==-1 ) {
                    return true;
                }
            }
            node = node.parentNode;
        }
        return false;
    },
});
$.fn.extend({
    focusIn: function () {
        if (this.length) {
            range.create(dom.firstChild(this[0]), 0).select();
        }
        return this;
    },
    focusInEnd: function () {
        if (this.length) {
            var last = dom.lastChild(this[0]);
            range.create(last, dom.nodeLength(last)).select();
        }
        return this;
    },
    selectContent: function () {
        if (this.length) {
            var next = dom.lastChild(this[0]);
            range.create(dom.firstChild(this[0]), 0, next, next.textContent.length).select();
        }
        return this;
    },
});

// RTE
var RTEWidget = Widget.extend({
    /**
     * @constructor
     */
    init: function (parent, getConfig) {
        var self = this;
        this._super.apply(this, arguments);

        this.init_bootstrap_carousel = $.fn.carousel;
        this.edit_bootstrap_carousel = function () {
            var res = self.init_bootstrap_carousel.apply(this, arguments);
            // off bootstrap keydown event to remove event.preventDefault()
            // and allow to change cursor position
            $(this).off('keydown.bs.carousel');
            return res;
        };

        this._getConfig = getConfig || this._getDefaultConfig;

        weWidgets.computeFonts();
    },
    /**
     * @override
     */
    start: function () {
        var self = this;

        this.saving_mutex = new concurrency.Mutex();

        $.fn.carousel = this.edit_bootstrap_carousel;

        $(document).on('mousedown.rte activate.rte', this, this._onMousedown.bind(this));
        $(document).on('mouseup.rte', this, this._onMouseup.bind(this));

        $('.o_not_editable').attr('contentEditable', false);

        var $editable = this.editable();

        $editable.addClass('o_editable')
        .data('rte', this)
        .each(function () {
            var $node = $(this);

            // add class to display inline-block for empty t-field
            if (window.getComputedStyle(this).display === 'inline' && $node.data('oe-type') !== 'image') {
                $node.addClass('o_is_inline_editable');
            }
        });

        // start element observation
        $(document).on('content_changed', '.o_editable', function (event) {
            self.trigger_up('rte_change', {target: event.target});
            $(this).addClass('o_dirty');
        });

        $('#wrapwrap, .o_editable').on('click.rte', '*', this, this._onClick.bind(this));

        $('body').addClass('editor_enable');

        $(document)
            .tooltip({
                selector: '[data-oe-readonly]',
                container: 'body',
                trigger: 'hover',
                delay: { 'show': 1000, 'hide': 100 },
                placement: 'bottom',
                title: _t("Readonly field")
            })
            .on('click', function () {
                $(this).tooltip('hide');
            });

        $(document).trigger('mousedown');
        this.trigger('rte:start');

        return this._super.apply(this, arguments);
    },
    /**
     * @override
     */
    destroy: function () {
        this.cancel();
        this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Stops the RTE.
     */
    cancel: function () {
        if (this.$last) {
            this.$last.destroy();
            this.$last = null;
        }

        $.fn.carousel = this.init_bootstrap_carousel;

        $(document).off('.rte');
        $('#wrapwrap, .o_editable').off('.rte');

        $('.o_not_editable').removeAttr('contentEditable');
        $(document).off('content_changed').removeClass('o_is_inline_editable').removeData('rte');
        $(document).tooltip('destroy');
        $('body').removeClass('editor_enable');
        this.trigger('rte:stop');
    },
    /**
     * Returns the editable areas on the page.
     *
     * @returns {jQuery}
     */
    editable: function () {
        return $('#wrapwrap [data-oe-model]')
            .not('.o_not_editable')
            .filter(function () {
                return !$(this).closest('.o_not_editable').length;
            })
            .not('link, script')
            .not('[data-oe-readonly]')
            .not('img[data-oe-field="arch"], br[data-oe-field="arch"], input[data-oe-field="arch"]')
            .not('.oe_snippet_editor')
            .add('.o_editable');
    },
    /**
     * Records the current state of the given $target to be able to undo future
     * changes.
     *
     * @see History.recordUndo
     * @param {jQuery} $target
     * @param {string} event
     * @param {boolean} internal_history
     */
    historyRecordUndo: function ($target, event, internal_history) {
        var rng = range.create();
        var $editable = $(rng && rng.sc).closest('.o_editable');
        if (!rng || !$editable.length) {
            $editable = $($target).closest('.o_editable');
            rng = range.create($target.closest('*')[0],0);
        } else {
            rng = $editable.data('range') || rng;
        }
        rng.select();
        history.recordUndo($editable, event, internal_history);
    },
    /**
     * Searches all the dirty element on the page and saves them one by one. If
     * one cannot be saved, this notifies it to the user and restarts rte
     * edition.
     *
     * @param {Object} [context] - the context to use for saving rpc, default to
     *                           the editor context found on the page
     * @return {Deferred} rejected if the save cannot be done
     */
    save: function (context) {
        var self = this;

        var $dirty = $('.o_dirty');
        $dirty
            .removeAttr('contentEditable')
            .removeClass('o_dirty oe_carlos_danger o_is_inline_editable');
        var defs = _.map($dirty, function (el) {
            var $el = $(el);

            $el.find('[class]').filter(function () {
                if (!this.getAttribute('class').match(/\S/)) {
                    this.removeAttribute('class');
                }
            });

            // TODO: Add a queue with concurrency limit in webclient
            // https://github.com/medikoo/deferred/blob/master/lib/ext/function/gate.js
            return self.saving_mutex.exec(function () {
                return self._saveElement($el, context || weContext.get())
                .then(function () {
                    $el.removeClass('o_dirty');
                }, function (response) {
                    // because ckeditor regenerates all the dom, we can't just
                    // setup the popover here as everything will be destroyed by
                    // the DOM regeneration. Add markings instead, and returns a
                    // new rejection with all relevant info
                    var id = _.uniqueId('carlos_danger_');
                    $el.addClass('o_dirty oe_carlos_danger ' + id);
                    var html = (response.data.exception_type === 'except_osv');
                    if (html) {
                        var msg = $('<div/>', {text: response.data.message}).html();
                        var data = msg.substring(3, msg.length  -2).split(/', u'/);
                        response.data.message = '<b>' + data[0] + '</b>' + data[1];
                    }
                    $('.o_editable.' + id)
                        .removeClass(id)
                        .popover({
                            html: html,
                            trigger: 'hover',
                            content: response.data.message,
                            placement: 'auto top',
                        })
                        .popover('show');
                });
            });
        });

        return $.when.apply($, defs).then(function () {
            window.onbeforeunload = null;
        }, function (failed) {
            // If there were errors, re-enable edition
            self.cancel();
            self.start();
        });
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * When the users clicks on an editable element, this function allows to add
     * external behaviors.
     *
     * @private
     * @param {jQuery} $editable
     */
    _enableEditableArea: function ($editable) {
        if ($editable.data('oe-type') === "monetary") {
            $editable.attr('contenteditable', false);
            $editable.find('.oe_currency_value').attr('contenteditable', true);
        }
        if ($editable.is('[data-oe-model]') && !$editable.is('[data-oe-model="ir.ui.view"]') && !$editable.is('[data-oe-type="html"]')) {
            $editable.data('layoutInfo').popover().find('.btn-group:not(.note-history)').remove();
        }
    },
    /**
     * When an element enters edition, summernote is initialized on it. This
     * function returns the default configuration for the summernote instance.
     *
     * @see _getConfig
     * @private
     * @param {jQuery} $editable
     * @returns {Object}
     */
    _getDefaultConfig: function ($editable) {
        return {
            'airMode' : true,
            'focus': false,
            'airPopover': [
                ['style', ['style']],
                ['font', ['bold', 'italic', 'underline', 'clear']],
                ['fontsize', ['fontsize']],
                ['color', ['color']],
                ['para', ['ul', 'ol', 'paragraph']],
                ['table', ['table']],
                ['insert', ['link', 'picture']],
                ['history', ['undo', 'redo']],
            ],
            'styleWithSpan': false,
            'inlinemedia' : ['p'],
            'lang': 'odoo',
            'onChange': function (html, $editable) {
                $editable.trigger('content_changed');
            }
        };
    },
    /**
     * Gets jQuery cloned element with internal text nodes escaped for XML
     * storage.
     *
     * @private
     * @param {jQuery} $el
     * @return {jQuery}
     */
    _getEscapedElement: function ($el) {
        var escaped_el = $el.clone();
        var to_escape = escaped_el.find('*').addBack();
        to_escape = to_escape.not(to_escape.filter('object,iframe,script,style,[data-oe-model][data-oe-model!="ir.ui.view"]').find('*').addBack());
        to_escape.contents().each(function () {
            if (this.nodeType === 3) {
                this.nodeValue = $('<div />').text(this.nodeValue).html();
            }
        });
        return escaped_el;
    },
    /**
     * Saves one (dirty) element of the page.
     *
     * @private
     * @param {jQuery} $el - the element to save
     * @param {Object} context - the context to use for the saving rpc
     * @param {boolean} [withLang=false]
     *        false if the lang must be omitted in the context (saving "master"
     *        page element)
     */
    _saveElement: function ($el, context, withLang) {
        return this._rpc({
            model: 'ir.ui.view',
            method: 'save',
            args: [
                $el.data('oe-id'),
                this._getEscapedElement($el).prop('outerHTML'),
                $el.data('oe-xpath') || null,
                withLang ? context : _.omit(context, 'lang')
            ],
        });
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Called when any editable element is clicked -> Prevents default browser
     * action for the element.
     *
     * @private
     * @param {Event} e
     */
    _onClick: function (e) {
        e.preventDefault();
    },
    /**
     * Called when the mouse is pressed on the document -> activate element
     * edition.
     *
     * @private
     * @param {Event} ev
     */
    _onMousedown: function (ev) {
        var $target = $(ev.target);
        var $editable = $target.closest('.o_editable');

        if (!$editable.length || $.summernote.core.dom.isContentEditableFalse($target)) {
            return;
        }

        if ($target.is('a')) {
            /**
             * Remove content editable everywhere and add it on the link only so that characters can be added
             * and removed at the start and at the end of it.
             */
            $target.attr('contenteditable', true);
            _.defer(function () {
                $editable.not($target).attr('contenteditable', false);
                $target.focus();
            });

            // Once clicked outside, remove contenteditable on link and reactive all
            $(document).on('mousedown.reactivate_contenteditable', function (e) {
                if ($target.is(e.target)) return;
                $target.removeAttr('contenteditable');
                $editable.attr('contenteditable', true);
                $(document).off('mousedown.reactivate_contenteditable');
            });
        }

        if (this && this.$last && (!$editable.length || this.$last[0] !== $editable[0])) {
            var $destroy = this.$last;
            history.splitNext();

            _.delay(function () {
                var id = $destroy.data('note-id');
                $destroy.destroy().removeData('note-id').removeAttr('data-note-id');
                $('#note-popover-'+id+', #note-handle-'+id+', #note-dialog-'+id+'').remove();
            }, 150); // setTimeout to remove flickering when change to editable zone (re-create an editor)
            this.$last = null;
        }
        if ($editable.length && (!this.$last || this.$last[0] !== $editable[0])) {
            $editable.summernote(this._getConfig($editable));

            $editable.data('NoteHistory', history);
            this.$last = $editable;

            // firefox & IE fix
            try {
                document.execCommand('enableObjectResizing', false, false);
                document.execCommand('enableInlineTableEditing', false, false);
                document.execCommand('2D-position', false, false);
            } catch (e) { /* */ }
            document.body.addEventListener('resizestart', function (evt) {evt.preventDefault(); return false;});
            document.body.addEventListener('movestart', function (evt) {evt.preventDefault(); return false;});
            document.body.addEventListener('dragstart', function (evt) {evt.preventDefault(); return false;});

            if (!range.create()) {
                $editable.focusIn();
            }

            if (dom.isImg($target[0])) {
                $target.trigger('mousedown'); // for activate selection on picture
            }

            this._enableEditableArea($editable);
        }
    },
    /**
     * Called when the mouse is unpressed on the document.
     *
     * @private
     * @param {Event} ev
     */
    _onMouseup: function (ev) {
        var $target = $(ev.target);
        var $editable = $target.closest('.o_editable');

        if (!$editable.length) {
            return;
        }

        var self = this;
        _.defer(function () {
            self.historyRecordUndo($target, 'activate',  true);
        });

        // To Fix Google Chrome Tripleclick Issue, which selects the ending
        // whitespace characters (so Tripleclicking then typing text will remove
        // the whole paragraph instead of its content).
        // http://stackoverflow.com/questions/38467334/why-does-google-chrome-always-add-space-after-selected-text
        if ($.browser.chrome === true && ev.originalEvent.detail === 3) {
            var currentSelection = range.create();
            if (currentSelection.sc.parentNode === currentSelection.ec) {
                _selectSC(currentSelection);
            } else if (currentSelection.eo === 0) {
                var $hasNext = $(currentSelection.sc).parent();
                while (!$hasNext.next().length && !$hasNext.is('body')) {
                    $hasNext = $hasNext.parent();
                }
                if ($hasNext.next()[0] === currentSelection.ec) {
                    _selectSC(currentSelection);
                }
            }
        }
        function _selectSC(selection) {
            range.create(selection.sc, selection.so, selection.sc, selection.sc.length).select();
        }
    },
});

return {
    Class: RTEWidget,
    history: history,
};
});
