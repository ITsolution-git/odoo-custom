(function () {
    'use strict';

    var website = openerp.website;
    website.templates.push('/website/static/src/xml/website.translator.xml');
    var nodialog = 'website_translator_nodialog';

    website.EditorBar.include({
        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                self.$('button[data-action=edit]').text("Translate");
                self.$('[data-action=snippet]').hide();
                self.$('#customize-menu-button').hide();
            });
        },
        edit: function () {
            var self = this;
            var mysuper = this._super;
            if (!localStorage[nodialog]) {
                var dialog = new website.TranslatorDialog();
                dialog.appendTo($(document.body));
                dialog.on('activate', this, function () {
                    localStorage[nodialog] = dialog.$('input[name=do_not_show]').prop('checked') || '';
                    dialog.$el.modal('hide');
                    this.translate();
                });
            } else {
                this.translate().then(function () {
                    // Disable non translatable t-fields
                    $('[data-oe-type][data-oe-translate=0]').removeAttr('data-oe-type');
                    mysuper.call(self);
                });
            }
        },
        translate: function () {
            var self = this;
            this.translations = null;
            return openerp.jsonRpc('/website/get_view_translations', 'call', {
                'xml_id': $(document.documentElement).data('view-xmlid'),
                'lang': website.get_context().lang,
            }).then(function (translations) {
                self.translations = translations;
                self.processTranslatableNodes();
            });
        },
        processTranslatableNodes: function () {
            var self = this;
            var $editables = $('[data-oe-model="ir.ui.view"]')
                    .not('link, script')
                    .not('.oe_snippets,.oe_snippet, .oe_snippet *')
                    .not('[data-oe-type]');

            $editables.each(function () {
                var $node = $(this);
                var view_id = $node.attr('data-oe-source-id') || $node.attr('data-oe-id');
                self.transNode(this, view_id|0);
            });
            $('.oe_translatable_text').on('paste', function () {
                var node = $(this);
                setTimeout(function () {
                    self.sanitizeNode(node);
                }, 0);
            });
            $(document).on('blur keyup paste', '.oe_translatable_text[contenteditable]', function(ev) {
                var $node = $(this);
                setTimeout(function () {
                    // Doing stuff next tick because paste and keyup events are
                    // fired before the content is changed
                    if (ev.type == 'paste') {
                        self.sanitizeNode($node[0]);
                    }
                    if ($node.data('initial_content') !== $node.text()) {
                        $node.addClass('oe_dirty').removeClass('oe_translatable_todo');
                    }
                }, 0);
            });
        },
        sanitizeNode: function (node) {
            node.text(node.text());
        },
        isTextNode: function (node) {
            return node.nodeType === 3 || node.nodeType === 4;
        },
        isTranslatable: function (text) {
            return text && _.str.trim(text) !== '';
        },
        markTranslatableNode: function (node, view_id) {
            // TODO: link nodes with same content
            node.className += ' oe_translatable_text';
            node.setAttribute('data-oe-translation-view-id', view_id);
            var content = node.childNodes[0].data.trim();
            var trans = this.translations.filter(function (t) {
                return t.res_id === view_id && t.value === content;
            });
            if (trans.length) {
                node.setAttribute('data-oe-translation-id', trans[0].id);
            } else {
                node.className += ' oe_translatable_todo';
            }
            node.contentEditable = true;
            $(node).data('initial_content', content);
        },
        save: function () {
            var trans = {};
            // this._super.apply(this, arguments);
            $('.oe_translatable_text.oe_dirty').each(function () {
                var $node = $(this);
                var data = $node.data();
                if (!trans[data.oeTranslationViewId]) {
                    trans[data.oeTranslationViewId] = [];
                }
                trans[data.oeTranslationViewId].push({
                    initial_content: data.initial_content,
                    new_content: $node.text(),
                    translation_id: data.oeTranslationId || null
                });
            });
            openerp.jsonRpc('/website/set_translations', 'call', {
                'data': trans,
                'lang': website.get_context()['lang'],
            }).then(function () {
                website.reload();
            }).fail(function () {
                // TODO: bootstrap alert with error message
                alert("Could not save translation");
            });
        },
        transNode: function (node, view_id) {
            // Mostly handling text and cdata nodes here
            // so avoid jquery usage in this function
            if (node.attributes['data-oe-type']) {
                if (node.attributes['data-oe-translate'].value == '1') {
                    node.className += ' oe_translatable_field';
                }
                return;
            } else if (node.childNodes.length === 1
                    && this.isTextNode(node.childNodes[0])
                    && !node.getAttribute('data-oe-model')) {
                this.markTranslatableNode(node, view_id);
            } else {
                for (var i = 0, l = node.childNodes.length; i < l; i ++) {
                    var n = node.childNodes[i];
                    if (this.isTextNode(n)) {
                        if (this.isTranslatable(n.data)) {
                            var container = document.createElement('span');
                            node.insertBefore(container, n);
                            container.appendChild(n);
                            this.markTranslatableNode(container, view_id);
                        }
                    } else {
                        this.transNode(n, view_id);
                    }
                }
            }
        },
    });

    website.RTE.include({
        start: function () {
            this._super.apply(this, arguments);
            this.$el.hide();
        },
        fetch_editables: function (root) {
            $(root).click(function (ev) {
                ev.preventDefault();
            });
            return $('[data-oe-translate=1]');
        }
    });

    website.TranslatorDialog = openerp.Widget.extend({
        events: _.extend({}, website.EditorBar.prototype.events, {
            'hidden.bs.modal': 'destroy',
            'click button[data-action=activate]': function (ev) {
                this.trigger('activate');
            },
        }),
        template: 'website.TranslatorDialog',
        start: function () {
            this.$el.modal();
        },
    });
})();
