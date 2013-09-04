(function () {
    'use strict';
    // TODO l10n ?

    var website = openerp.website;
    website.EditorBar.include({
        events: _.extend({}, website.EditorBar.prototype.events, {
            'click a[data-action=promote-current-page]': 'promotePage',
        }),
        promotePage: function () {
            (new website.seo.Configurator()).appendTo($(document.body));
        },
    });

    website.seo = {};

    website.seo.PageParser = openerp.Class.extend({
        url: function () {
            var url = window.location.href;
            var hashIndex = url.indexOf('#');
            return hashIndex >= 0 ? url.substring(0, hashIndex) : url;
        },
        title: function () {
            return $(document.title).text();
        },
        headers: function (tag) {
            return $('h1').map(function () {
                    return $(this).text();
            });
        },
        images: function () {
            return $('#wrap img').map(function () {
                var $img = $(this);
                return  {
                    src: $img.attr('src'),
                    alt: $img.attr('alt'),
                };
            });
        },
        company: function () {
            return $('meta[name="openerp.company"]').attr('value');
        },
    });

    website.seo.Tip = openerp.Widget.extend({
        template: 'website.seo_tip',
        events: {
            'closed.bs.alert': 'destroy',
        },
        init: function (parent, options) {
            this.message = options.message;
            // cf. http://getbootstrap.com/components/#alerts
            // success, info, warning or danger
            this.type = options.type || 'info';
            this._super(parent);
        },
    });

    website.seo.Keyword = openerp.Widget.extend({
        template: 'website.seo_keyword',
        events: {
            'click a[data-action=remove-keyword]': 'destroy',
        },
        maxWordsPerKeyword: 4, // TODO Check
        types: {
            // cf. http://getbootstrap.com/components/#labels
            // default, primary, success, info, warning, danger
            perfect: 'success',
            advised: 'primary',
            used: 'warning',
            new: 'default',
        },
        init: function (parent, options) {
            this.keyword = options.keyword;
            this.type = this.types[options.type || 'default'];
            this._super(parent);
        },
        destroy: function () {
            this.trigger('removed');
            this._super();
        },
    });

    website.seo.KeywordList = openerp.Widget.extend({
        template: 'website.seo_list',
        maxKeywords: 10,
        keywords: function () {
            var result = [];
            this.$el.find('.js_seo_keyword').each(function () {
                result.push($(this).data('keyword'));
            });
            return result;
        },
        suggestions: function () {
            // TODO Refactor (Ugly)
            return $('.js_seo_suggestion').map(function () {
                return $(this).data('keyword');
            });
        },
        isKeywordListFull: function () {
            return this.keywords().length >= this.maxKeywords;
        },
        isExistingKeyword: function (word) {
            return _.contains(this.keywords(), word);
        },
        add: function (candidate) {
            var self = this;
            // TODO Refine
            var word = candidate ? candidate.replace(/[,;.:<>]+/g, " ").replace(/ +/g, " ").trim() : "";
            if (word && !this.isKeywordListFull() && !this.isExistingKeyword(word)) {
                var type = _.contains(this.suggestions(), word) ? 'advised' : 'new';
                var keyword = new website.seo.Keyword(this, {
                    keyword: word,
                    type: type,
                });
                keyword.on('removed', null, function () {
                   self.trigger('list-not-full');
                });
                keyword.appendTo(this.$el);
            }
            if (this.isKeywordListFull()) {
                self.trigger('list-full');
            }
        },
    });

    website.seo.Suggestion = openerp.Widget.extend({
        template: 'website.seo_suggestion',
        events: {
            'click .js_seo_suggestion': 'select'
        },
        types: {
            // cf. http://getbootstrap.com/components/#labels
            // default, primary, success, info, warning, danger
            primary: 'primary',
            secondary: 'info',

        },
        init: function (parent, options) {
            this.keyword = options.keyword;
            this.type = this.types[options.type || 'primary'];
            this._super(parent);
        },
        select: function () {
            this.trigger('selected');
        },
    });

    website.seo.Image = openerp.Widget.extend({
        template: 'website.seo_image',
        init: function (parent, options) {
            this.src = options.src;
            this.alt = options.alt;
            this._super(parent);
        },
    });


    website.seo.ImageList = openerp.Widget.extend({
        start: function () {
            var self = this;
            new website.seo.PageParser().images().each(function (index, image) {
                new website.seo.Image(self, image).appendTo(self.$el);
            });
        },
        images: function () {
            var result = [];
            this.$el.find('input').each(function () {
               var $input = $(this);
               result.push({
                   src: $input.attr('src'),
                   alt: $input.val(),
               });
            });
            return result;
        },
        add: function (image) {
            new website.seo.Image(this, image).appendTo(this.$el);
        },
    });

    website.seo.Configurator = openerp.Widget.extend({
        template: 'website.seo_configuration',
        events: {
            'keypress input[name=seo_page_keywords]': 'confirmKeyword',
            'click button[data-action=add]': 'addKeyword',
            'click button[data-action=update]': 'update',
            'hidden.bs.modal': 'destroy'
        },
        maxTitleSize: 65,
        maxDescriptionSize: 155,
        start: function () {
            var $modal = this.$el;
            var pageParser = new website.seo.PageParser();
            $modal.find('.js_seo_page_url').text(pageParser.url());
            $modal.find('input[name=seo_page_title]').val(pageParser.title());
            this.suggestImprovements(pageParser);
            this.displayKeywordSuggestions(pageParser);
            this.imageList = new website.seo.ImageList(this);
            this.imageList.appendTo($modal.find('.js_seo_image_list'));
            this.keywordList = new website.seo.KeywordList(this);
            this.keywordList.appendTo($modal.find('.js_seo_keywords_list'));
            this.keywordList.on('list-full', null, function () {
                $modal.find('input[name=seo_page_keywords]')
                    .attr('readonly', "readonly")
                    .attr('placeholder', "Remove a keyword first");
                $modal.find('button[data-action=add]')
                    .prop('disabled', true).addClass('disabled');
            });
            this.keywordList.on('list-not-full', null, function () {
                $modal.find('input[name=seo_page_keywords]')
                    .removeAttr('readonly').attr('placeholder', "");
                $modal.find('button[data-action=add]')
                    .prop('disabled', false).removeClass('disabled');
            });
            $modal.modal();
        },
        suggestImprovements: function (parser) {
            var tips = [];
            var self = this;
            function displayTip(message, type) {
                new website.seo.Tip(this, {
                   message: message,
                   type: type
                }).appendTo(self.$el.find('.js_seo_tips'));
            }
            var pageParser = parser || new website.seo.PageParser();
            if (!pageParser.headers('h1').length === 0) {
                tips.push({
                    type: 'warning',
                    message: "You don't have an &lt;h1&gt; tag on your page.",
                });
            }
            if (pageParser.headers('h1').length > 1) {
                tips.push({
                    type: 'warning',
                    message: "You have more than one &lt;h1&gt; tag on your page.",
                });
            }
            if (tips.length > 0) {
                _.each(tips, function (tip) {
                    displayTip(tip.message, tip.type);
                });
            } else {
                displayTip("Your page makup is appropriate for search engines.", 'success');
            }
        },
        displayKeywordSuggestions: function (pageParser) {
            var $modal = this.$el;
            var self = this;
            $modal.find('.js_seo_company_suggestions').append("Loading...");
            var companyName = pageParser.company().toLowerCase();
            // cf. https://github.com/ddm/seo
            // TODO Try with /recommend/
            $.getJSON("http://seo.eu01.aws.af.cm/suggest/"+encodeURIComponent(companyName), function (list) {
                $modal.find('.js_seo_company_suggestions').empty();
                // TODO Improve algorithm + Ajust based on custom user keywords
                var nameRegex = new RegExp(companyName, "gi");
                var cleanList = _.map(list, function removeCompanyName (word) {
                    return word.replace(nameRegex, "").trim();
                });
                // TODO Order properly ?
                cleanList.push(companyName);
                _.each(_.uniq(cleanList), function (keyword) {
                    if (keyword) {
                        var suggestion = new website.seo.Suggestion(self, {
                            keyword: keyword
                        });
                        suggestion.on('selected', self, function () {
                           self.addKeyword(keyword);
                        });
                        suggestion.appendTo($modal.find('.js_seo_company_suggestions'));
                    }
                });
            });
        },
        confirmKeyword: function (e) {
            if (e.keyCode == 13) {
                this.addKeyword(this.$el.find('input[name=seo_page_keywords]').val());
            }
        },
        addKeyword: function (word) {
            var $input = this.$el.find('input[name=seo_page_keywords]');
            var keyword = _.isString(word) ? word : $input.val();
            this.keywordList.add(keyword);
            $input.val("");
        },
        update: function () {
            var data = {
                title: this.$el.find('input[name=seo_page_title]').val(),
                description: this.$el.find('input[name=seo_page_title]').val(),
                keywords: this.keywordList.keywords(),
                images: this.imageList.images(),
            };
            console.log(data);
            // TODO Persist changes
        },
    });
})();
