(function () {
    'use strict';

    var website = openerp.website;
    // $.fn.data automatically parses value, '0'|'1' -> 0|1

    website.templates.push('/website/static/src/xml/website.editor.xml');
    website.dom_ready.done(function () {
        var is_smartphone = $(document.body)[0].clientWidth < 767;

        if (!is_smartphone) {
            website.ready().then(website.init_editor);
        }
    });

    function link_dialog(editor) {
        return new website.editor.LinkDialog(editor).appendTo(document.body);
    }
    function image_dialog(editor) {
        return new website.editor.RTEImageDialog(editor).appendTo(document.body);
    }

    // only enable editors manually
    CKEDITOR.disableAutoInline = true;
    // EDIT ALL THE THINGS
    CKEDITOR.dtd.$editable = $.extend(
        {}, CKEDITOR.dtd.$block, CKEDITOR.dtd.$inline);
    // Disable removal of empty elements on CKEDITOR activation. Empty
    // elements are used for e.g. support of FontAwesome icons
    CKEDITOR.dtd.$removeEmpty = {};

    website.init_editor = function () {
        CKEDITOR.plugins.add('customdialogs', {
//            requires: 'link,image',
            init: function (editor) {
                editor.on('doubleclick', function (evt) {
                    var element = evt.data.element;
                    if (element.is('img')
                            && !element.data('cke-realelement')
                            && !element.isReadOnly()
                            && (element.data('oe-model') !== 'ir.ui.view')) {
                        image_dialog(editor);
                        return;
                    }

                    element = get_selected_link(editor) || evt.data.element;
                    if (element.isReadOnly()
                        || !element.is('a')
                        || element.data('oe-model')) {
                        return;
                    }

                    editor.getSelection().selectElement(element);
                    link_dialog(editor);
                }, null, null, 500);

                //noinspection JSValidateTypes
                editor.addCommand('link', {
                    exec: function (editor) {
                        link_dialog(editor);
                        return true;
                    },
                    canUndo: false,
                    editorFocus: true,
                });
                //noinspection JSValidateTypes
                editor.addCommand('image', {
                    exec: function (editor) {
                        image_dialog(editor);
                        return true;
                    },
                    canUndo: false,
                    editorFocus: true,
                });

                editor.ui.addButton('Link', {
                    label: 'Link',
                    command: 'link',
                    toolbar: 'links,10',
                    icon: '/website/static/lib/ckeditor/plugins/link/icons/link.png',
                });
                editor.ui.addButton('Image', {
                    label: 'Image',
                    command: 'image',
                    toolbar: 'insert,10',
                    icon: '/website/static/lib/ckeditor/plugins/image/icons/image.png',
                });

                editor.setKeystroke(CKEDITOR.CTRL + 76 /*L*/, 'link');
            }
        });
        CKEDITOR.plugins.add( 'tablebutton', {
            requires: 'panelbutton,floatpanel',
            init: function( editor ) {
                var label = "Table";

                editor.ui.add('TableButton', CKEDITOR.UI_PANELBUTTON, {
                    label: label,
                    title: label,
                    // use existing 'table' icon
                    icon: 'table',
                    modes: { wysiwyg: true },
                    editorFocus: true,
                    // panel opens in iframe, @css is CSS file <link>-ed within
                    // frame document, @attributes are set on iframe itself.
                    panel: {
                        css: '/website/static/src/css/editor.css',
                        attributes: { 'role': 'listbox', 'aria-label': label, },
                    },

                    onBlock: function (panel, block) {
                        block.autoSize = true;
                        block.element.setHtml(openerp.qweb.render('website.editor.table.panel', {
                            rows: 5,
                            cols: 5,
                        }));

                        var $table = $(block.element.$).on('mouseenter', 'td', function (e) {
                            var $e = $(e.target);
                            var y = $e.index() + 1;
                            var x = $e.closest('tr').index() + 1;

                            $table
                                .find('td').removeClass('selected').end()
                                .find('tr:lt(' + String(x) + ')')
                                .children().filter(function () { return $(this).index() < y; })
                                .addClass('selected');
                        }).on('click', 'td', function (e) {
                            var $e = $(e.target);

                            //noinspection JSPotentiallyInvalidConstructorUsage
                            var table = new CKEDITOR.dom.element(
                                $(openerp.qweb.render('website.editor.table', {
                                    rows: $e.closest('tr').index() + 1,
                                    cols: $e.index() + 1,
                                }))[0]);

                            editor.insertElement(table);
                            setTimeout(function () {
                                //noinspection JSPotentiallyInvalidConstructorUsage
                                var firstCell = new CKEDITOR.dom.element(table.$.rows[0].cells[0]);
                                var range = editor.createRange();
                                range.moveToPosition(firstCell, CKEDITOR.POSITION_AFTER_START);
                                range.select();
                            }, 0);
                        });

                        block.element.getDocument().getBody().setStyle('overflow', 'hidden');
                        CKEDITOR.ui.fire('ready', this);
                    },
                });
            }
        });

        CKEDITOR.plugins.add('oeref', {
            requires: 'widget',

            init: function (editor) {
                editor.widgets.add('oeref', {
                    editables: { text: '*' },

                    upcast: function (el) {
                        return el.attributes['data-oe-type']
                            && el.attributes['data-oe-type'] !== 'monetary';
                    },
                });
                editor.widgets.add('monetary', {
                    editables: { text: 'span.oe_currency_value' },

                    upcast: function (el) {
                        return el.attributes['data-oe-type'] === 'monetary';
                    }
                });
            }
        });

        var editor = new website.EditorBar();
        var $body = $(document.body);
        editor.prependTo($body).then(function () {
            if (location.search.indexOf("enable_editor") >= 0) {
                editor.edit();
            }
        });
        $body.css('padding-top', '50px'); // Not working properly: editor.$el.outerHeight());
    };
        /* ----- TOP EDITOR BAR FOR ADMIN ---- */
    website.EditorBar = openerp.Widget.extend({
        template: 'website.editorbar',
        events: {
            'click button[data-action=edit]': 'edit',
            'click button[data-action=save]': 'save',
            'click button[data-action=cancel]': 'cancel',
        },
        container: 'body',
        customize_setup: function() {
            var self = this;
            var view_name = $(document.documentElement).data('view-xmlid');
            var menu = $('#customize-menu');
            this.$('#customize-menu-button').click(function(event) {
                menu.empty();
                openerp.jsonRpc('/website/customize_template_get', 'call', { 'xml_id': view_name }).then(
                    function(result) {
                        _.each(result, function (item) {
                            if (item.header) {
                                menu.append('<li class="dropdown-header">' + item.name + '</li>');
                            } else {
                                menu.append(_.str.sprintf('<li role="presentation"><a href="#" data-view-id="%s" role="menuitem"><strong class="icon-check%s"></strong> %s</a></li>',
                                    item.id, item.active ? '' : '-empty', item.name));
                            }
                        });
                        // Adding Static Menus
                        menu.append('<li class="divider"></li><li class="js_change_theme"><a href="/page/website.themes">Change Theme</a></li>');
                        menu.append('<li class="divider"></li><li><a data-action="ace" href="#">Advanced view editor</a></li>');
                        self.trigger('rte:customize_menu_ready');
                    }
                );
            });
            menu.on('click', 'a[data-action!=ace]', function (event) {
                var view_id = $(event.currentTarget).data('view-id');
                openerp.jsonRpc('/website/customize_template_toggle', 'call', {
                    'view_id': view_id
                }).then( function() {
                    window.location.reload();
                });
            });
        },
        start: function() {
            var self = this;

            this.saving_mutex = new openerp.Mutex();

            this.$('#website-top-edit').hide();
            this.$('#website-top-view').show();

            $('.dropdown-toggle').dropdown();
            this.customize_setup();

            this.$buttons = {
                edit: this.$('button[data-action=edit]'),
                save: this.$('button[data-action=save]'),
                cancel: this.$('button[data-action=cancel]'),
            };

            this.rte = new website.RTE(this);
            this.rte.on('change', this, this.proxy('rte_changed'));
            this.rte.on('rte:ready', this, function () {
                self.trigger('rte:ready');
            });

            return $.when(
                this._super.apply(this, arguments),
                this.rte.appendTo(this.$('#website-top-edit .nav.pull-right'))
            );
        },
        edit: function () {
            this.$buttons.edit.prop('disabled', true);
            this.$('#website-top-view').hide();
            this.$('#website-top-edit').show();
            $('.css_non_editable_mode_hidden').removeClass("css_non_editable_mode_hidden");

            this.rte.start_edition();
        },
        rte_changed: function () {
            this.$buttons.save.prop('disabled', false);
        },
        save: function () {
            var self = this;

            observer.disconnect();
            var editor = this.rte.editor;
            var root = editor.element.$;
            editor.destroy();
            // FIXME: select editables then filter by dirty?
            var defs = this.rte.fetch_editables(root)
                .filter('.oe_dirty')
                .removeAttr('contentEditable')
                .removeClass('oe_dirty oe_editable cke_focus oe_carlos_danger')
                .map(function () {
                    var $el = $(this);
                    // TODO: Add a queue with concurrency limit in webclient
                    // https://github.com/medikoo/deferred/blob/master/lib/ext/function/gate.js
                    return self.saving_mutex.exec(function () {
                        return self.saveElement($el)
                            .then(undefined, function (thing, response) {
                                // because ckeditor regenerates all the dom,
                                // we can't just setup the popover here as
                                // everything will be destroyed by the DOM
                                // regeneration. Add markings instead, and
                                // returns a new rejection with all relevant
                                // info
                                var id = _.uniqueId('carlos_danger_');
                                $el.addClass('oe_dirty oe_carlos_danger');
                                $el.addClass(id);
                                return $.Deferred().reject({
                                    id: id,
                                    error: response.data,
                                });
                            });
                    });
                }).get();
            return $.when.apply(null, defs).then(function () {
                website.reload();
            }, function (failed) {
                // If there were errors, re-enable edition
                self.rte.start_edition(true).then(function () {
                    // jquery's deferred being a pain in the ass
                    if (!_.isArray(failed)) { failed = [failed]; }

                    _(failed).each(function (failure) {
                        $(root).find('.' + failure.id)
                            .removeClass(failure.id)
                            .popover({
                                trigger: 'hover',
                                content: failure.error.message,
                                placement: 'auto top',
                            })
                            // Force-show popovers so users will notice them.
                            .popover('show');
                    })
                });
            });
        },
        /**
         * Saves an RTE content, which always corresponds to a view section (?).
         */
        saveElement: function ($el) {
            var markup = $el.prop('outerHTML');
            return openerp.jsonRpc('/web/dataset/call', 'call', {
                model: 'ir.ui.view',
                method: 'save',
                args: [$el.data('oe-id'), markup,
                       $el.data('oe-xpath') || null,
                       website.get_context()],
            });
        },
        cancel: function () {
            website.reload();
        },
    });

    var blocks_selector = _.keys(CKEDITOR.dtd.$block).join(',');
    /* ----- RICH TEXT EDITOR ---- */
    website.RTE = openerp.Widget.extend({
        tagName: 'li',
        id: 'oe_rte_toolbar',
        className: 'oe_right oe_rte_toolbar',
        // editor.ui.items -> possible commands &al
        // editor.applyStyle(new CKEDITOR.style({element: "span",styles: {color: "#(color)"},overrides: [{element: "font",attributes: {color: null}}]}, {color: '#ff0000'}));

        init: function (EditorBar) {
            this.EditorBar = EditorBar;
            this._super.apply(this, arguments);
        },

        /**
         * In Webkit-based browsers, triple-click will select a paragraph up to
         * the start of the next "paragraph" including any empty space
         * inbetween. When said paragraph is removed or altered, it nukes
         * the empty space and brings part of the content of the next
         * "paragraph" (which may well be e.g. an image) into the current one,
         * completely fucking up layouts and breaking snippets.
         *
         * Try to fuck around with selections on triple-click to attempt to
         * fix this garbage behavior.
         *
         * Note: for consistent behavior we may actually want to take over
         * triple-clicks, in all browsers in order to ensure consistent cross-
         * platform behavior instead of being at the mercy of rendering engines
         * & platform selection quirks?
         */
        webkitSelectionFixer: function (root) {
            root.addEventListener('click', function (e) {
                // only webkit seems to have a fucked up behavior, ignore others
                // FIXME: $.browser goes away in jquery 1.9...
                if (!$.browser.webkit) { return; }
                // http://www.w3.org/TR/DOM-Level-2-Events/events.html#Events-eventgroupings-mouseevents
                // The detail attribute indicates the number of times a mouse button has been pressed
                // we just want the triple click
                if (e.detail !== 3) { return; }
                e.preventDefault();

                // Get closest block-level element to the triple-clicked
                // element (using ckeditor's block list because why not)
                var $closest_block = $(e.target).closest(blocks_selector);

                // manually set selection range to the content of the
                // triple-clicked block-level element, to avoid crossing over
                // between block-level elements
                document.getSelection().selectAllChildren($closest_block[0]);
            });
        },
        tableNavigation: function (root) {
            var self = this;
            $(root).on('keydown', function (e) {
                // ignore non-TAB
                if (e.which !== 9) { return; }

                if (self.handleTab(e)) {
                    e.preventDefault();
                }
            });
        },
        /**
         * Performs whatever operation is necessary on a [TAB] hit, returns
         * ``true`` if the event's default should be cancelled (if the TAB was
         * handled by the function)
         */
        handleTab: function (event) {
            var forward = !event.shiftKey;

            var root = window.getSelection().getRangeAt(0).commonAncestorContainer;
            var $cell = $(root).closest('td,th');

            if (!$cell.length) { return false; }

            var cell = $cell[0];

            // find cell in same row
            var row = cell.parentNode;
            var sibling = row.cells[cell.cellIndex + (forward ? 1 : -1)];
            if (sibling) {
                document.getSelection().selectAllChildren(sibling);
                return true;
            }

            // find cell in previous/next row
            var table = row.parentNode;
            var sibling_row = table.rows[row.rowIndex + (forward ? 1 : -1)];
            if (sibling_row) {
                var new_cell = sibling_row.cells[forward ? 0 : sibling_row.cells.length - 1];
                document.getSelection().selectAllChildren(new_cell);
                return true;
            }

            // at edge cells, copy word/openoffice behavior: if going backwards
            // from first cell do nothing, if going forwards from last cell add
            // a row
            if (forward) {
                var row_size = row.cells.length;
                var new_row = document.createElement('tr');
                while(row_size--) {
                    var newcell = document.createElement('td');
                    // zero-width space
                    newcell.textContent = '\u200B';
                    new_row.appendChild(newcell);
                }
                table.appendChild(new_row);
                document.getSelection().selectAllChildren(new_row.cells[0]);
            }

            return true;
        },
        /**
         * Makes the page editable
         *
         * @param {Boolean} [restart=false] in case the edition was already set
         *                                  up once and is being re-enabled.
         * @returns {$.Deferred} deferred indicating when the RTE is ready
         */
        start_edition: function (restart) {
            var self = this;
            // create a single editor for the whole page
            var root = document.getElementById('wrapwrap');
            if (!restart) {
                $(root).on('dragstart', 'img', function (e) {
                    e.preventDefault();
                });
                this.webkitSelectionFixer(root);
                this.tableNavigation(root);
            }
            var def = $.Deferred();
            var editor = this.editor = CKEDITOR.inline(root, self._config());
            editor.on('instanceReady', function () {
                editor.setReadOnly(false);
                // ckeditor set root to editable, disable it (only inner
                // sections are editable)
                // FIXME: are there cases where the whole editor is editable?
                editor.editable().setReadOnly(true);

                self.setup_editables(root);

                // disable firefox's broken table resizing thing
                document.execCommand("enableObjectResizing", false, "false");
                document.execCommand("enableInlineTableEditing", false, "false");

                self.trigger('rte:ready');
                def.resolve();
            });
            return def;
        },

        setup_editables: function (root) {
            // selection of editable sub-items was previously in
            // EditorBar#edit, but for some unknown reason the elements were
            // apparently removed and recreated (?) at editor initalization,
            // and observer setup was lost.
            var self = this;
            // setup dirty-marking for each editable element
            this.fetch_editables(root)
                .addClass('oe_editable')
                .each(function () {
                    var node = this;
                    var $node = $(node);
                    // only explicitly set contenteditable on view sections,
                    // cke widgets system will do the widgets themselves
                    if ($node.data('oe-model') === 'ir.ui.view') {
                        node.contentEditable = true;
                    }

                    observer.observe(node, OBSERVER_CONFIG);
                    $node.one('content_changed', function () {
                        $node.addClass('oe_dirty');
                        self.trigger('change');
                    });
                });
        },

        fetch_editables: function (root) {
            return $(root).find('[data-oe-model]')
                // FIXME: propagation should make "meta" blocks non-editable in the first place...
                .not('link, script')
                .not('.oe_snippet_editor')
                .filter(function () {
                    var $this = $(this);
                    // keep view sections and fields which are *not* in
                    // view sections for top-level editables
                    return $this.data('oe-model') === 'ir.ui.view'
                       || !$this.closest('[data-oe-model = "ir.ui.view"]').length;
                });
        },

        _current_editor: function () {
            return CKEDITOR.currentInstance;
        },
        _config: function () {
            // base plugins minus
            // - magicline (captures mousein/mouseout -> breaks draggable)
            // - contextmenu & tabletools (disable contextual menu)
            // - bunch of unused plugins
            var plugins = [
                'a11yhelp', 'basicstyles', 'blockquote',
                'clipboard', 'colorbutton', 'colordialog', 'dialogadvtab',
                'elementspath', 'enterkey', 'entities', 'filebrowser',
                'find', 'floatingspace','format', 'htmlwriter', 'iframe',
                'indentblock', 'indentlist', 'justify',
                'list', 'pastefromword', 'pastetext', 'preview',
                'removeformat', 'resize', 'save', 'selectall', 'stylescombo',
                'table', 'templates', 'toolbar', 'undo', 'wysiwygarea'
            ];
            return {
                // FIXME
                language: 'en',
                // Disable auto-generated titles
                // FIXME: accessibility, need to generate user-sensible title, used for @title and @aria-label
                title: false,
                plugins: plugins.join(','),
                uiColor: '',
                // FIXME: currently breaks RTE?
                // Ensure no config file is loaded
                customConfig: '',
                // Disable ACF
                allowedContent: true,
                // Don't insert paragraphs around content in e.g. <li>
                autoParagraph: false,
                // Don't automatically add &nbsp; or <br> in empty block-level
                // elements when edition starts
                fillEmptyBlocks: false,
                filebrowserImageUploadUrl: "/website/attach",
                // Support for sharedSpaces in 4.x
                extraPlugins: 'sharedspace,customdialogs,tablebutton,oeref',
                // Place toolbar in controlled location
                sharedSpaces: { top: 'oe_rte_toolbar' },
                toolbar: [{
                    name: 'clipboard', items: [
                        "Undo"
                    ]},{
                        name: 'basicstyles', items: [
                        "Bold", "Italic", "Underline", "Strike", "Subscript",
                        "Superscript", "TextColor", "BGColor", "RemoveFormat"
                    ]},{
                    name: 'span', items: [
                        "Link", "Blockquote", "BulletedList",
                        "NumberedList", "Indent", "Outdent"
                    ]},{
                    name: 'justify', items: [
                        "JustifyLeft", "JustifyCenter", "JustifyRight", "JustifyBlock"
                    ]},{
                    name: 'special', items: [
                        "Image", "TableButton"
                    ]},{
                    name: 'styles', items: [
                        "Styles"
                    ]}
                ],
                // styles dropdown in toolbar
                stylesSet: [
                    {name: "Normal", element: 'p'},
                    {name: "Heading 1", element: 'h1'},
                    {name: "Heading 2", element: 'h2'},
                    {name: "Heading 3", element: 'h3'},
                    {name: "Heading 4", element: 'h4'},
                    {name: "Heading 5", element: 'h5'},
                    {name: "Heading 6", element: 'h6'},
                    {name: "Formatted", element: 'pre'},
                    {name: "Address", element: 'address'},
                    // emphasis
                    {name: "Muted", element: 'span', attributes: {'class': 'text-muted'}},
                    {name: "Primary", element: 'span', attributes: {'class': 'text-primary'}},
                    {name: "Warning", element: 'span', attributes: {'class': 'text-warning'}},
                    {name: "Danger", element: 'span', attributes: {'class': 'text-danger'}},
                    {name: "Success", element: 'span', attributes: {'class': 'text-success'}},
                    {name: "Info", element: 'span', attributes: {'class': 'text-info'}}
                ],
            };
        },
    });

    website.editor = { };
    website.editor.Dialog = openerp.Widget.extend({
        events: {
            'hidden.bs.modal': 'destroy',
            'click button.save': 'save',
        },
        init: function (editor) {
            this._super();
            this.editor = editor;
        },
        start: function () {
            var sup = this._super();
            this.$el.modal({backdrop: 'static'});
            return sup;
        },
        save: function () {
            this.close();
        },
        close: function () {
            this.$el.modal('hide');
        },
    });

    website.editor.LinkDialog = website.editor.Dialog.extend({
        template: 'website.editor.dialog.link',
        events: _.extend({}, website.editor.Dialog.prototype.events, {
            'change .url-source': function (e) { this.changed($(e.target)); },
            'mousedown': function (e) {
                var $target = $(e.target).closest('.list-group-item');
                if (!$target.length || $target.hasClass('active')) {
                    // clicked outside groups, or clicked in active groups
                    return;
                }

                this.changed($target.find('.url-source'));
            },
            'click button.remove': 'remove_link',
            'change input#link-text': function (e) {
                this.text = $(e.target).val()
            },
        }),
        init: function (editor) {
            this._super(editor);
            // url -> name mapping for existing pages
            this.pages = Object.create(null);
            this.text = null;
        },
        start: function () {
            var element;
            if ((element = this.get_selected_link()) && element.hasAttribute('href')) {
                this.editor.getSelection().selectElement(element);
            }
            this.element = element;
            if (element) {
                this.add_removal_button();
            }

            return $.when(
                this.fetch_pages().done(this.proxy('fill_pages')),
                this.fetch_menus().done(this.proxy('fill_menus')),
                this._super()
            ).done(this.proxy('bind_data'));
        },
        add_removal_button: function () {
            this.$('.modal-footer').prepend(
                openerp.qweb.render(
                    'website.editor.dialog.link.footer-button'));
        },
        remove_link: function () {
            var editor = this.editor;
            // same issue as in make_link
            setTimeout(function () {
                editor.removeStyle(new CKEDITOR.style({
                    element: 'a',
                    type: CKEDITOR.STYLE_INLINE,
                    alwaysRemoveElement: true,
                }));
            }, 0);
            this.close();
        },
        /**
         * Greatly simplified version of CKEDITOR's
         * plugins.link.dialogs.link.onOk.
         *
         * @param {String} url
         * @param {Boolean} [new_window=false]
         * @param {String} [label=null]
         */
        make_link: function (url, new_window, label) {
            var attributes = {href: url, 'data-cke-saved-href': url};
            var to_remove = [];
            if (new_window) {
                attributes['target'] = '_blank';
            } else {
                to_remove.push('target');
            }

            if (this.element) {
                this.element.setAttributes(attributes);
                this.element.removeAttributes(to_remove);
                if (this.text) { this.element.setText(this.text); }
            } else {
                var selection = this.editor.getSelection();
                var range = selection.getRanges(true)[0];

                if (range.collapsed) {
                    //noinspection JSPotentiallyInvalidConstructorUsage
                    var text = new CKEDITOR.dom.text(
                        this.text || label || url);
                    range.insertNode(text);
                    range.selectNodeContents(text);
                }

                //noinspection JSPotentiallyInvalidConstructorUsage
                new CKEDITOR.style({
                    type: CKEDITOR.STYLE_INLINE,
                    element: 'a',
                    attributes: attributes,
                }).applyToRange(range);

                // focus dance between RTE & dialog blow up the stack in Safari
                // and Chrome, so defer select() until dialog has been closed
                setTimeout(function () {
                    range.select();
                }, 0);
            }
        },
        save: function () {
            var self = this, _super = this._super.bind(this);
            var $e = this.$('.list-group-item.active .url-source');
            var val = $e.val();
            if (!val || !$e[0].checkValidity()) {
                // FIXME: error message
                $e.closest('.form-group').addClass('has-error');
                return;
            }

            var done = $.when();
            if ($e.hasClass('email-address')) {
                this.make_link('mailto:' + val, false, val);
            } else if ($e.hasClass('existing')) {
                self.make_link(val, false, this.pages[val]);
            } else if ($e.hasClass('pages')) {
                // Create the page, get the URL back
                done = $.get(_.str.sprintf(
                        '/pagenew/%s?noredirect', encodeURI(val)))
                    .then(function (response) {
                        self.make_link(response, false, val);
                        var parent_id = self.$('.add-to-menu').val();
                        if (parent_id) {
                            return openerp.jsonRpc('/web/dataset/call_kw', 'call', {
                                model: 'website.menu',
                                method: 'create',
                                args: [{
                                    'name': val,
                                    'url': response,
                                    'sequence': 0, // TODO: better tree widget
                                    'website_id': website.id,
                                    'parent_id': parent_id|0,
                                }],
                                kwargs: {
                                    context: website.get_context()
                                },
                            });
                        }
                    });
            } else {
                this.make_link(val, this.$('input.window-new').prop('checked'));
            }
            done.then(_super);
        },
        bind_data: function () {
            var href = this.element && (this.element.data( 'cke-saved-href')
                                    ||  this.element.getAttribute('href'));
            if (!href) { return; }

            var match, $control;
            if (match = /mailto:(.+)/.exec(href)) {
                $control = this.$('input.email-address').val(match[1]);
            } else if (href in this.pages) {
                $control = this.$('select.existing').val(href);
            } else if (match = /\/page\/(.+)/.exec(href)) {
                var actual_href = '/page/website.' + match[1];
                if (actual_href in this.pages) {
                    $control = this.$('select.existing').val(actual_href);
                }
            }
            if (!$control) {
                $control = this.$('input.url').val(href);
            }

            this.changed($control);

            this.$('input#link-text').val(this.element.getText());
            this.$('input.window-new').prop(
                'checked', this.element.getAttribute('target') === '_blank');
        },
        changed: function ($e) {
            this.$('.url-source').not($e).val('');
            $e.closest('.list-group-item')
                .addClass('active')
                .siblings().removeClass('active')
                .addBack().removeClass('has-error');
        },
        /**
         * CKEDITOR.plugins.link.getSelectedLink ignores the editor's root,
         * if the editor is set directly on a link it will thus not work.
         */
        get_selected_link: function () {
            return get_selected_link(this.editor);
        },
        fetch_pages: function () {
            return openerp.jsonRpc('/web/dataset/call_kw', 'call', {
                model: 'website',
                method: 'list_pages',
                args: [null],
                kwargs: {
                    context: website.get_context()
                },
            });
        },
        fill_pages: function (results) {
            var self = this;
            var pages = this.$('select.existing')[0];
            _(results).each(function (result) {
                self.pages[result.url] = result.name;

                pages.options[pages.options.length] =
                        new Option(result.name, result.url);
            });
        },
        fetch_menus: function () {
            var context = website.get_context();
            return openerp.jsonRpc('/web/dataset/call_kw', 'call', {
                model: 'website.menu',
                method: 'get_list',
                args: [[context.website_id]],
                kwargs: {
                    context: context
                },
            });
        },
        fill_menus: function (results) {
            var self = this;
            var menus = this.$('select.add-to-menu')[0];
            _(results).each(function (result) {
                var name = (new Array(result.level).join('|-')) + ' ' + result.name;
                menus.options[menus.options.length] =
                    new Option(name, result.id || 0);
            });
        },
    });
    /**
     * ImageDialog widget. Lets users change an image, including uploading a
     * new image in OpenERP or selecting the image style (if supported by
     * the caller).
     *
     * Initialized as usual, but the caller can hook into two events:
     *
     * @event start({url, style}) called during dialog initialization and
     *                            opening, the handler can *set* the ``url``
     *                            and ``style`` properties on its parameter
     *                            to provide these as default values to the
     *                            dialog
     * @event save({url, style}) called during dialog finalization, the handler
     *                           is provided with the image url and style
     *                           selected by the users (or possibly the ones
     *                           originally passed in)
     */
    website.editor.ImageDialog = website.editor.Dialog.extend({
        template: 'website.editor.dialog.image',
        events: _.extend({}, website.editor.Dialog.prototype.events, {
            'change .url-source': function (e) { this.changed($(e.target)); },
            'click button.filepicker': function () {
                this.$('input[type=file]').click();
            },
            'change input[type=file]': 'file_selection',
            'change input.url': 'preview_image',
            'click a[href=#existing]': 'browse_existing',
            'change select.image-style': 'preview_image',
        }),

        start: function () {
            var $options = this.$('.image-style').children();
            this.image_styles = $options.map(function () { return this.value; }).get();

            var o = { url: null, style: null, };
            // avoid typos, prevent addition of new properties to the object
            Object.preventExtensions(o);
            this.trigger('start', o);

            if (o.url) {
                if (o.style) {
                    this.$('.image-style').val(o.style);
                }
                this.set_image(o.url);
            }

            return this._super();
        },
        save: function () {
            this.trigger('save', {
                url: this.$('input.url').val(),
                style: this.$('.image-style').val(),
            });
            return this._super();
        },

        /**
         * Sets the provided image url as the dialog's value-to-save and
         * refreshes the preview element to use it.
         */
        set_image: function (url) {
            this.$('input.url').val(url);
            this.preview_image();
        },

        file_selection: function () {
            this.$('button.filepicker').removeClass('btn-danger btn-success');

            var self = this;
            var callback = _.uniqueId('func_');
            this.$('input[name=func]').val(callback);

            window[callback] = function (url, error) {
                delete window[callback];
                self.file_selected(url, error);
            };
            this.$('form').submit();
        },
        file_selected: function(url, error) {
            var $button = this.$('button.filepicker');
            if (error) {
                $button.addClass('btn-danger');
                return;
            }
            $button.addClass('btn-success');
            this.set_image(url);
        },
        preview_image: function () {
            var image = this.$('input.url').val();
            if (!image) { return; }

            this.$('img.image-preview')
                .attr('src', image)
                .removeClass(this.image_styles.join(' '))
                .addClass(this.$('select.image-style').val());
        },
        browse_existing: function (e) {
            e.preventDefault();
            new website.editor.ExistingImageDialog(this).appendTo(document.body);
        },
    });
    website.editor.RTEImageDialog = website.editor.ImageDialog.extend({
        init: function () {
            this._super.apply(this, arguments);

            this.on('start', this, this.proxy('started'));
            this.on('save', this, this.proxy('saved'));
        },
        started: function (holder) {
            var selection = this.editor.getSelection();
            var el = selection && selection.getSelectedElement();
            this.element = null;

            if (el && el.is('img')) {
                this.element = el;
                _(this.image_styles).each(function (style) {
                    if (el.hasClass(style)) {
                        holder.style = style;
                    }
                });
                holder.url = el.getAttribute('src');
            }
        },
        saved: function (data) {
            var element, editor = this.editor;
            if (!(element = this.element)) {
                element = editor.document.createElement('img');
                element.addClass('img');
                // focus event handler interactions between bootstrap (modal)
                // and ckeditor (RTE) lead to blowing the stack in Safari and
                // Chrome (but not FF) when this is done synchronously =>
                // defer insertion so modal has been hidden & destroyed before
                // it happens
                setTimeout(function () {
                    editor.insertElement(element);
                }, 0);
            }

            var style = data.style;
            element.setAttribute('src', data.url);
            element.removeAttribute('data-cke-saved-src');
            $(element.$).removeClass(this.image_styles.join(' '));
            if (style) { element.addClass(style); }
        },
    });

    var IMAGES_PER_ROW = 6;
    var IMAGES_ROWS = 4;
    website.editor.ExistingImageDialog = website.editor.Dialog.extend({
        template: 'website.editor.dialog.image.existing',
        events: _.extend({}, website.editor.Dialog.prototype.events, {
            'click .existing-attachments img': 'select_existing',
            'click .pager > li': function (e) {
                e.preventDefault();
                var $target = $(e.currentTarget);
                if ($target.hasClass('disabled')) {
                    return;
                }
                this.page += $target.hasClass('previous') ? -1 : 1;
                this.display_attachments();
            },
        }),
        init: function (parent) {
            this.image = null;
            this.page = 0;
            this.parent = parent;
            this._super(parent.editor);
        },

        start: function () {
            return $.when(
                this._super(),
                this.fetch_existing().then(this.proxy('fetched_existing')));
        },

        fetch_existing: function () {
            return openerp.jsonRpc('/web/dataset/call_kw', 'call', {
                model: 'ir.attachment',
                method: 'search_read',
                args: [],
                kwargs: {
                    fields: ['name', 'website_url'],
                    domain: [['res_model', '=', 'ir.ui.view']],
                    order: 'name',
                    context: website.get_context(),
                }
            });
        },
        fetched_existing: function (records) {
            this.records = records;
            this.display_attachments();
        },
        display_attachments: function () {
            var per_screen = IMAGES_PER_ROW * IMAGES_ROWS;

            var from = this.page * per_screen;
            var records = this.records;

            // Create rows of 3 records
            var rows = _(records).chain()
                .slice(from, from + per_screen)
                .groupBy(function (_, index) { return Math.floor(index / IMAGES_PER_ROW); })
                .values()
                .value();

            this.$('.existing-attachments').replaceWith(
                openerp.qweb.render(
                    'website.editor.dialog.image.existing.content', {rows: rows}));
            this.$('.pager')
                .find('li.previous').toggleClass('disabled', (from === 0)).end()
                .find('li.next').toggleClass('disabled', (from + per_screen >= records.length));

        },
        select_existing: function (e) {
            var link = $(e.currentTarget).attr('src');
            if (link) {
                this.parent.set_image(link);
            }
            this.close()
        },
    });

    function get_selected_link(editor) {
        var sel = editor.getSelection(),
            el = sel.getSelectedElement();
        if (el && el.is('a')) { return el; }

        var range = sel.getRanges(true)[0];
        if (!range) { return null; }

        range.shrink(CKEDITOR.SHRINK_TEXT);
        var commonAncestor = range.getCommonAncestor();
        var viewRoot = editor.elementPath(commonAncestor).contains(function (element) {
            return element.data('oe-model') === 'ir.ui.view'
        });
        if (!viewRoot) { return null; }
        // if viewRoot is the first link, don't edit it.
        return new CKEDITOR.dom.elementPath(commonAncestor, viewRoot)
                .contains('a', true);
    }


    website.Observer = window.MutationObserver || window.WebkitMutationObserver || window.JsMutationObserver;
    var OBSERVER_CONFIG = {
        childList: true,
        attributes: true,
        characterData: true,
        subtree: true,
        attributeOldValue: true,
    };
    var observer = new website.Observer(function (mutations) {
        // NOTE: Webkit does not fire DOMAttrModified => webkit browsers
        //       relying on JsMutationObserver shim (Chrome < 18, Safari < 6)
        //       will not mark dirty on attribute changes (@class, img/@src,
        //       a/@href, ...)
        _(mutations).chain()
            .filter(function (m) {
                switch(m.type) {
                case 'attributes': // ignore .cke_focus being added or removed
                    // if attribute is not a class, can't be .cke_focus change
                    if (m.attributeName !== 'class') { return true; }

                    // find out what classes were added or removed
                    var oldClasses = (m.oldValue || '').split(/\s+/);
                    var newClasses = m.target.className.split(/\s+/);
                    var change = _.union(_.difference(oldClasses, newClasses),
                                         _.difference(newClasses, oldClasses));
                    // ignore mutation if the *only* change is .cke_focus
                    return change.length !== 1 || change[0] === 'cke_focus';
                case 'childList':
                    // <br type="_moz"> appears when focusing RTE in FF, ignore
                    return m.addedNodes.length !== 1 || m.addedNodes[0].nodeName !== 'BR';
                default:
                    return true;
                }
            })
            .map(function (m) {
                var node = m.target;
                while (node && !$(node).hasClass('oe_editable')) {
                    node = node.parentNode;
                }
                $(m.target).trigger('node_changed');
                return node;
            })
            .compact()
            .uniq()
            .each(function (node) { $(node).trigger('content_changed'); })
    });
})();
