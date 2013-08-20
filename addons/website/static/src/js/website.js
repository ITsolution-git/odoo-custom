$(function(){

    // Ugly. I'll clean this monday
    if ($('html').attr('data-editable') !== '1'){
        return;
    }

    // TODO fme: put everything in openerp.website scope and load templates on
    // next tick or document ready
    // Also check with xmo if jquery.keypress.js is still needed.

    /* ----- TEMPLATE LOADING ---- */

    function loadTemplates(templates) {
        var def = $.Deferred();
        var count = templates.length;
        templates.forEach(function(t) {
            openerp.qweb.add_template(t, function(err) {
                if (err) {
                    def.reject();
                } else {
                    count--;
                    if (count < 1) {
                        def.resolve();
                    }
                }
            });
        });
        return def;
    }

    var templates = [
        '/website/static/src/xml/website.xml'
    ];

    loadTemplates(templates).then(function(){
        var editor = new EditorBar();
        editor.prependTo($('body'));
        $('body').css('padding-top', '50px'); // Not working properly: editor.$el.outerHeight());
        // TODO: Create an openerp.Widget out of this
    });

    /* ----- PUBLISHING STUFF ---- */

    $(document).on('click', '.js_publish, .js_unpublish', function (e) {
        e.preventDefault();
        var $link = $(this).parent();
        $link.find('.js_publish, .js_unpublish').addClass("hidden");
        var $unp = $link.find(".js_unpublish");
        var $p = $link.find(".js_publish");
        $.post('/website/publish', {'id': $link.data('id'), 'object': $link.data('object')}, function (result) {
            if (+result) {
                $p.addClass("hidden");
                $unp.removeClass("hidden");
            } else {
                $p.removeClass("hidden");
                $unp.addClass("hidden");
            }
        });
    });

    /* ----- TOP EDITOR BAR FOR ADMIN ---- */

    var EditorBar = openerp.Widget.extend({
        template: 'Website.EditorBar',
        events: {
            'click button[data-action=edit]': 'edit',
            'click button[data-action=save]': 'save',
            'click button[data-action=cancel]': 'cancel',
            'click button[data-action=snippet]': 'snippet',
        },
        container: 'body',
        customize_setup: function() {
            var self = this;
            var view_name = $('html').data('view-xmlid');
            var menu = $('#customize-menu');
            this.$('#customize-menu-button').click(function(event) {
                menu.empty();
                openerp.jsonRpc('/website/customize_template_get', 'call', { 'xml_id': view_name }).then(
                    function(result) {
                        _.each(result, function (item) {
                            if (item.header) {
                                menu.append('<li class="nav-header">' + item.name + '</li>');
                            } else {
                                menu.append(_.str.sprintf('<li><a href="#" data-view-id="%s"><strong class="icon-check%s"></strong> %s</a></li>',
                                    item.id, item.active ? '' : '-empty', item.name));
                            }
                        });
                    }
                );
            });
            menu.on('click', 'a', function (event) {
                var view_id = $(event.target).data('view-id');
                openerp.jsonRpc('/website/customize_template_toggle', 'call', {
                    'view_id': view_id
                }).then( function(result) {
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
                snippet: this.$('button[data-action=snippet]'),
            };

            this.rte = new RTE(this);
            this.rte.on('change', this, this.proxy('rte_changed'));

            this.snippets = new Snippets();
            this.snippets.appendTo($("body"));
            window.snippets = this.snippets;

            return $.when(
                this._super.apply(this, arguments),
                this.rte.insertBefore(this.$buttons.snippet.parent())
            );
        },
        edit: function () {
            this.$buttons.edit.prop('disabled', true);
            this.$('#website-top-view').hide();
            this.$('#website-top-edit').show();

            // this.$buttons.cancel.add(this.$buttons.snippet).prop('disabled', false)
            //     .add(this.$buttons.save)
            //     .parent().show();
            //
            // TODO: span edition changing edition state (save button)
            var $editables = $('[data-oe-model]')
                    .not('link, script')
                    // FIXME: propagation should make "meta" blocks non-editable in the first place...
                    .not('.oe_snippet_editor')
                    .prop('contentEditable', true)
                    .addClass('oe_editable');
            var $rte_ables = $editables.not('[data-oe-type]');
            var $raw_editables = $editables.not($rte_ables);

            // temporary fix until we fix ckeditor
            $raw_editables.each(function () {
                $(this).parents().add($(this).find('*')).on('click', function(ev) {
                    ev.preventDefault();
                    ev.stopPropagation();
                });
            });

            this.rte.start_edition($rte_ables);
            $raw_editables.on('keydown keypress cut paste', function (e) {
                var $target = $(e.target);
                if ($target.hasClass('oe_dirty')) {
                    return;
                }

                $target.addClass('oe_dirty');
                this.$buttons.save.prop('disabled', false);
            }.bind(this));
        },
        rte_changed: function () {
            this.$buttons.save.prop('disabled', false);
        },
        save: function () {
            var self = this;
            var defs = [];
            $('.oe_dirty').each(function (i, v) {
                var $el = $(this);
                // TODO: Add a queue with concurrency limit in webclient
                // https://github.com/medikoo/deferred/blob/master/lib/ext/function/gate.js
                var def = self.saving_mutex.exec(function () {
                    return self.saveElement($el).then(function () {
                        $el.removeClass('oe_dirty');
                    }).fail(function () {
                        var data = $el.data();
                        console.error(_.str.sprintf('Could not save %s#%d#%s', data.oeModel, data.oeId, data.oeField));
                    });
                });
                defs.push(def);
            });
            return $.when.apply(null, defs).then(function () {
                window.location.reload();
            });
        },
        saveElement: function ($el) {
            var data = $el.data();
            var html = $el.html();
            var xpath = data.oeXpath;
            if (xpath) {
                var $w = $el.clone();
                $w.removeClass('oe_dirty');
                _.each(['model', 'id', 'field', 'xpath'], function(d) {$w.removeAttr('data-oe-' + d);});
                $w
                    .removeClass('oe_editable')
                    .prop('contentEditable', false);
                html = $w.wrap('<div>').parent().html();
            }
            return openerp.jsonRpc('/web/dataset/call', 'call', {
                model: 'ir.ui.view',
                method: 'save',
                args: [data.oeModel, data.oeId, data.oeField, html, xpath]
            });
        },
        cancel: function () {
            window.location.reload();
        },
        snippet: function (ev) {
            this.snippets.toggle();
        },
    });

    /* ----- RICH TEXT EDITOR ---- */

    var RTE = openerp.Widget.extend({
        tagName: 'li',
        id: 'oe_rte_toolbar',
        className: 'oe_right oe_rte_toolbar',
        // editor.ui.items -> possible commands &al
        // editor.applyStyle(new CKEDITOR.style({element: "span",styles: {color: "#(color)"},overrides: [{element: "font",attributes: {color: null}}]}, {color: '#ff0000'}));

        start_edition: function ($elements) {
            var self = this;
            this.snippet_carousel();
            $elements
                .not('span, [data-oe-type]')
                .each(function () {
                    var $this = $(this);
                    CKEDITOR.inline(this, self._config()).on('change', function () {
                        $this.addClass('oe_dirty');
                        self.trigger('change', this, null);
                    });
                });
        },

        _current_editor: function () {
            return CKEDITOR.currentInstance;
        },
        _config: function () {
            var removed_plugins = [
                    // remove custom context menu
                    'contextmenu,tabletools,liststyle',
                    // magicline captures mousein/mouseout => draggable does not work
                    'magicline'
            ];
            return {
                // Disable auto-generated titles
                // FIXME: accessibility, need to generate user-sensible title, used for @title and @aria-label
                title: false,
                removePlugins: removed_plugins.join(','),
                uiColor: '',
                // Ensure no config file is loaded
                customConfig: '',
                // Disable ACF
                allowedContent: true,
                // Don't insert paragraphs around content in e.g. <li>
                autoParagraph: false,
                filebrowserImageUploadUrl: "/website/attach",
                // Support for sharedSpaces in 4.x
                extraPlugins: 'sharedspace',
                // Place toolbar in controlled location
                sharedSpaces: { top: 'oe_rte_toolbar' },
                toolbar: [
                    {name: 'basicstyles', items: [
                        "Bold", "Italic", "Underline", "Strike", "Subscript",
                        "Superscript", "TextColor", "BGColor", "RemoveFormat"
                    ]},{
                    name: 'span', items: [
                        "Link", "Unlink", "Blockquote", "BulletedList",
                        "NumberedList", "Indent", "Outdent",
                    ]},{
                    name: 'justify', items: [
                        "JustifyLeft", "JustifyCenter", "JustifyRight", "JustifyBlock"
                    ]},{
                    name: 'special', items: [
                        "Image", "Table"
                    ]},{
                    name: 'styles', items: [
                        "Format", "Styles"
                    ]}
                ],
                // styles dropdown in toolbar
                stylesSet: [
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
        // TODO clean
        snippet_carousel: function () {
            var self = this;
            $('.carousel .js_carousel_options .label').on('click', function (e) {
                e.preventDefault();
                var $button = $(e.currentTarget);
                var $c = $button.parents(".carousel:first");

                if($button.hasClass("js_add")) {
                    var cycle = $c.find(".carousel-inner .item").size();
                    $c.find(".carousel-inner").append(QWeb.render("Website.Snipped.carousel"));
                    $c.carousel(cycle);
                }
                else {
                    var cycle = $c.find(".carousel-inner .item.active").remove();
                    $c.find(".carousel-inner .item:first").addClass("active");
                    $c.carousel(0);
                    self.trigger('change', self, null);
                }
            });
            $('.carousel .js_carousel_options').show();
        }
    });

    /* ----- SNIPPET SELECTOR ---- */

    var Snippets = openerp.Widget.extend({
        template: 'website.snippets',
        init: function () {
            this._super.apply(this, arguments);
        },
        start: function() {
            var self = this;

            $.ajax({
                type: "GET",
                url:  "/page/website.snippets",
                dataType: "text",
                success: function(snippets){
                    self.$el.html(snippets);
                    self.start_snippets();
                },
            });

        },
        // setup widget and drag and drop
        start_snippets: function(){
            var self = this;
            
            this.$('.oe_snippet').draggable({
                helper: 'clone',
                start: function(){
                    var snippet = $(this);
                 
                    self.activate_drop_zones({
                        siblings: snippet.data('selector-siblings'),
                        childs:   snippet.data('selector-childs')
                    });

                    $('.oe_drop_zone').droppable({
                        hoverClass: "oe_hover",
                        drop:   function(event,ui){
                            $(this).replaceWith(snippet.find('.oe_snippet_body').clone());
                        },
                    });
                },
                stop: function(){
                    self.deactivate_drop_zones();
                }
            });
        },
        // A generic drop zone generator. two css selectors can be provided
        // selector.childs -> will insert drop zones as direct child of the selected elements
        //   in case the selected elements have children themselves, dropzones will be interleaved
        //   with them.
        // selector.siblings -> will insert drop zones after and before selected elements
        activate_drop_zones: function(selector){
            var self = this;
            var child_selector   =  selector.childs   || '';
            var sibling_selector =  selector.siblings || '';
            var zone_template = "<div class='oe_drop_zone'></div>";
            
            $('.oe_drop_zone').remove();

            if(child_selector){
                var $zones = $(child_selector);
                for( var i = 0, len = $zones.length; i < len; i++ ){
                    $zones.eq(i).find('> *:not(.oe_drop_zone)').after(zone_template);
                    $zones.eq(i).prepend(zone_template);
                }
            }
            
            if(sibling_selector){
                var $zones = $(sibling_selector);
                for( var i = 0, len = $zones.length; i < len; i++ ){
                    if($zones.eq(i).prev('.oe_drop_zone').length === 0){
                        $zones.eq(i).before(zone_template);
                    }
                    if($zones.eq(i).next('.oe_drop_zone').length === 0){
                        $zones.eq(i).after(zone_template);
                    }
                }
            }

            // Cleaning up unnecessary zones
            $('.oe_snippets .oe_drop_zone').remove();   // no zone in the snippet selector ...
            $('#website-top-view .oe_drop_zone').remove();   // no zone in the top bars ...
            $('#website-top-edit .oe_drop_zone').remove();
            do {
                var count = 0;
                var $zones = $('.oe_drop_zone + .oe_drop_zone');    // no two consecutive zones
                count += $zones.length;
                $zones.remove();

                $zones = $('.oe_drop_zone > .oe_drop_zone').remove();   // no recusrive zones
                count += $zones.length;
                $zones.remove();
            }while(count > 0);

            // Cleaning up zones placed between floating or inline elements
            var $zones = $('.oe_drop_zone');
            for( i = 0, len = $zones.length; i < len; i++ ){
                var zone = $zones.eq(i);
                var prev = zone.prev();
                var next = zone.next();
                var float_prev = zone.prev().css('float')   || 'none';
                var float_next = zone.next().css('float')   || 'none';
                var disp_prev  = zone.prev().css('display') ||  null;
                var disp_next  = zone.next().css('display') ||  null;
                if(     (float_prev === 'left' || float_prev === 'right')
                    &&  (float_next === 'left' || float_next === 'right')  ){
                    zone.remove();
                    continue;
                }else if( !(    disp_prev === null
                             || disp_next === null
                             || disp_prev === 'block'
                             || disp_next === 'block'
                            ) ){
                    zone.remove();
                    continue;
                }
            }
        },
        deactivate_drop_zones: function(){
            $('.oe_drop_zone').remove();
        },
        toggle: function(){
            if(this.$el.hasClass('oe_hidden')){
                this.$el.removeClass('oe_hidden');
            }else{
                this.$el.addClass('oe_hidden');
            }
        },
        snippet_start: function () {
            var self = this;
            $('.oe_snippet').draggable().click(function(ev) {
                self.setup_droppable();
                $(".oe_snippet_drop").show();
                $('.oe_selected').removeClass('oe_selected');
                $(ev.currentTarget).addClass('oe_selected');
            });

        },
    });

});

