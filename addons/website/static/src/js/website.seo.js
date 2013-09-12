(function () {
    'use strict';

    var website = openerp.website;
    website.templates.push('/website/static/src/xml/website.seo.xml');

    website.EditorBar.include({
        events: _.extend({}, website.EditorBar.prototype.events, {
            'click a[data-action=promote-current-page]': 'promotePage',
        }),
        promotePage: function () {
            (new website.seo.Configurator()).appendTo($(document.body));
        },
    });

    website.seo = {};

    website.seo.Suggestion = openerp.Widget.extend({
        template: 'website.seo_suggestion',
        init: function (parent, keyword) {
            this.keyword = keyword;
            // cf. http://getbootstrap.com/components/#labels
            // default, primary, success, info, warning, danger
            this.type = 'default';
            this._super(parent);
        },
    });

    website.seo.SuggestionList = openerp.Widget.extend({
        template: 'website.seo_list',
        init: function (parent, word) {
            this.word = word;
            this._super(parent);
        },
        start: function () {
            this.refresh();
        },
        refresh: function () {
            var self = this;
            self.$el.append("Loading...");
            function addSuggestions (list) {
                self.$el.empty();
                // TODO Improve algorithm + Ajust based on custom user keywords
                var nameRegex = new RegExp(self.companyName, "gi");
                var cleanList = _.map(list, function removeCompanyName (word) {
                    return word.replace(nameRegex, "").trim();
                });
                // TODO Order properly ?
                _.each(_.uniq(cleanList), function (keyword) {
                    if (keyword) {
                        var suggestion = new website.seo.Suggestion(self, keyword);
                        suggestion.appendTo(self.$el);
                    }
                });
            }
            $.getJSON("http://seo.eu01.aws.af.cm/suggest/"+encodeURIComponent(this.word + " "), addSuggestions);
        },
    });

    website.seo.Keyword = openerp.Widget.extend({
        template: 'website.seo_keyword',
        events: {
            'click a[data-action=remove-keyword]': 'destroy',
        },
        maxWordsPerKeyword: 4, // TODO Check
        init: function (parent, keyword) {
            this.keyword = keyword;
            // cf. http://getbootstrap.com/components/#labels
            // default, primary, success, info, warning, danger
            this.type = 'warning';
            this._super(parent);
        },
        start: function () {
            this.suggestionList = new website.seo.SuggestionList(this, this.keyword);
            this.suggestionList.appendTo(this.$('.js_seo_keyword_suggestion'));
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
            this.$('.js_seo_keyword').each(function () {
                result.push($(this).data('keyword'));
            });
            return result;
        },
        isKeywordListFull: function () {
            return this.keywords().length >= this.maxKeywords;
        },
        isExistingKeyword: function (word) {
            return _.contains(this.keywords(), word);
        },
        add: function (candidate, suggested) {
            var self = this;
            // TODO Refine
            var word = candidate ? candidate.replace(/[,;.:<>]+/g, " ").replace(/ +/g, " ").trim() : "";
            if (word && !self.isKeywordListFull() && !self.isExistingKeyword(word)) {
                var type = suggested ? 'advised' : 'custom';
                var keyword = new website.seo.Keyword(self, word);
                keyword.on('removed', null, function () {
                   self.trigger('list-not-full');
                   self.trigger('removed', word);
                });
                keyword.appendTo(self.$el);
            }
            if (self.isKeywordListFull()) {
                self.trigger('list-full');
            }
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
            this.$('input').each(function () {
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
            return $('#wrap '+tag).map(function () {
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
            var self = this;
            var $modal = this.$el;
            var pageParser = new website.seo.PageParser();
            $modal.find('.js_seo_page_url').text(pageParser.url());
            $modal.find('input[name=seo_page_title]').val(pageParser.title());
            this.suggestImprovements(pageParser);
            this.imageList = new website.seo.ImageList(this);
            this.imageList.appendTo($modal.find('.js_seo_image_list'));
            this.keywordList = new website.seo.KeywordList(this);
            this.keywordList.on('list-full', self, function () {
                $modal.find('input[name=seo_page_keywords]')
                    .attr('readonly', "readonly")
                    .attr('placeholder', "Remove a keyword first");
                $modal.find('button[data-action=add]')
                    .prop('disabled', true).addClass('disabled');
            });
            this.keywordList.on('list-not-full', self, function () {
                $modal.find('input[name=seo_page_keywords]')
                    .removeAttr('readonly').attr('placeholder', "");
                $modal.find('button[data-action=add]')
                    .prop('disabled', false).removeClass('disabled');
            });
            this.keywordList.appendTo($modal.find('.js_seo_keywords_list'));
            var companyName = pageParser.company().toLowerCase();
            this.addKeyword(companyName);
            $modal.modal();
        },
        suggestImprovements: function (parser) {
            var tips = [];
            var self = this;
            function displayTip(message, type) {
                new website.seo.Tip(self, {
                   message: message,
                   type: type,
                }).appendTo(self.$('.js_seo_tips'));
            }
            var pageParser = parser || new website.seo.PageParser();
            if (pageParser.headers('h1').length === 0) {
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
        confirmKeyword: function (e) {
            if (e.keyCode == 13) {
                this.addKeyword();
            }
        },
        addKeyword: function (word) {
            var $input = this.$('input[name=seo_page_keywords]');
            var keyword = _.isString(word) ? word : $input.val();
            this.keywordList.add(keyword, false);
            $input.val("");
        },
        update: function () {
            var data = {
                title: this.$('input[name=seo_page_title]').val(),
                description: this.$('input[name=seo_page_title]').val(),
                keywords: this.keywordList.keywords(),
                images: this.imageList.images(),
            };
            console.log(data);
            // TODO Persist changes
        },
    });
})();
