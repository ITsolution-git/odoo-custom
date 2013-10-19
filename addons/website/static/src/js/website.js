(function() {
    "use strict";

    var website = {};
    // The following line can be removed in 2017
    openerp.website = website;

    var templates = website.templates = [
        '/website/static/src/xml/website.xml'
    ];

    website.get_context = function (dict) {
        var html = document.documentElement;
        return _.extend({
            lang: html.getAttribute('lang').replace('-', '_')
        }, dict);
    };

    /* ----- TEMPLATE LOADING ---- */
    website.add_template = function(template) {
        templates.push(template);
    };
    website.load_templates = function(templates) {
        var def = $.Deferred();
        var count = templates.length;

        var dones = _(templates).map(function (t) {
            return new $.Deferred(function (d) {
                openerp.qweb.add_template(t, function(err) {
                    if (err) {
                        d.reject(err);
                    } else {
                        d.resolve();
                    }
                });
            });
        });
        return $.when.apply(null, dones);
    };
    website.reload = function () {
        location.hash = "scrollTop=" + window.document.body.scrollTop;
        if (location.search.indexOf("unable_editor") > -1) {
            window.location.href = window.location.href.replace(/unable_editor(=[^&]*)?/g, '');
        } else {
            window.location.reload();
        }
    };

    var all_ready = null;
    var dom_ready = website.dom_ready = $.Deferred();
    $(dom_ready.resolve);

    website.init_kanban = function ($kanban) {
        $('.js_kanban_col', $kanban).each(function () {
            var $col = $(this);
            var $pagination = $('.pagination', $col);
            if(!$pagination.size()) {
                return;
            }

            var page_count =  $col.data('page_count');
            var scope = $pagination.last().find("li").size()-2;
            var kanban_url_col = $pagination.find("li a:first").attr("href").replace(/[0-9]+$/, '');

            var data = {
                'domain': $col.data('domain'),
                'model': $col.data('model'),
                'template': $col.data('template'),
                'step': $col.data('step'),
                'orderby': $col.data('orderby')
            };

            $pagination.on('click', 'a', function (ev) {
                ev.preventDefault();
                var $a = $(ev.target);
                if($a.parent().hasClass('active')) {
                    return;
                }

                var page = +$a.attr("href").split(",").pop().split('-')[1];
                data['page'] = page;

                $.post('/website/kanban/', data, function (col) {
                    $col.find("> .thumbnail").remove();
                    $pagination.last().before(col);
                });

                var page_start = page - parseInt(Math.floor((scope-1)/2), 10);
                if (page_start < 1 ) page_start = 1;
                var page_end = page_start + (scope-1);
                if (page_end > page_count ) page_end = page_count;

                if (page_end - page_start < scope) {
                    page_start = page_end - scope > 0 ? page_end - scope : 1;
                }

                $pagination.find('li.prev a').attr("href", kanban_url_col+(page-1 > 0 ? page-1 : 1));
                $pagination.find('li.next a').attr("href", kanban_url_col+(page < page_end ? page+1 : page_end));
                for(var i=0; i < scope; i++) {
                    $pagination.find('li:not(.prev):not(.next):eq('+i+') a').attr("href", kanban_url_col+(page_start+i)).html(page_start+i);
                }
                $pagination.find('li.active').removeClass('active');
                $pagination.find('li:has(a[href="'+kanban_url_col+page+'"])').addClass('active');

            });

        });
    };

    /**
     * Returns a deferred resolved when the templates are loaded
     * and the Widgets can be instanciated.
     */
    website.ready = function() {
        if (!all_ready) {
            var tpl = website.load_templates(templates);
            all_ready = dom_ready.then(function () {
                if ($('html').data('editable')) {
                    website.session = new openerp.Session();
                    var modules = ['website'];
                    return openerp._t.database.load_translations(website.session, modules, website.get_context().lang);
                }
            }).then(tpl).promise();
        }
        return all_ready;
    };

    dom_ready.then(function () {

        /* ----- PUBLISHING STUFF ---- */
        $('[data-publish]:has(.js_publish)').each(function () {
            var $pub = $("[data-publish]", this);
            if($pub.size())
                $(this).attr("data-publish", $pub.attr("data-publish"));
            else
                $(this).removeAttr("data-publish");
        });

        $('[data-publish]:has(.js_publish_management)').each(function () {
            $(this).attr("data-publish", $(".js_publish_management .btn-success", this).size() ? "on" : 'off');
            $(this).attr("data-publish", $(".js_publish_management .btn-success", this).size() ? "on" : 'off');
        });

        $(document).on('click', '.js_publish', function (e) {
            e.preventDefault();
            var $data = $(":first", this).parents("[data-publish]");
            $data.attr("data-publish", $data.first().attr("data-publish") == 'off' ? 'on' : 'off');
            openerp.jsonRpc('/website/publish', 'call', {'id': $(this).data('id'), 'object': $(this).data('object')})
                .then(function (result) {
                    $data.attr("data-publish", +result ? 'on' : 'off');
                });
        });

        // $.stellar();

        $(document).on('click', '.js_publish_management .js_publish_btn', function (e) {
            var $data = $(this).parents(".js_publish_management:first");
            var $btn = $data.find('.btn:first');
            var publish = $btn.hasClass("btn-success");

            $data.toggleClass("css_unpublish css_publish");
            $btn.removeClass("btn-default btn-success");

            openerp.jsonRpc('/website/publish', 'call', {'id': +$data.data('id'), 'object': $data.data('object')})
                .then(function (result) {
                    $btn.toggleClass("btn-default", !result).toggleClass("btn-success", result);
                    $data.toggleClass("css_unpublish", !result).toggleClass("css_publish", result);
                    $data.parents("[data-publish]").attr("data-publish", +result ? 'on' : 'off');
                });
        });

        /* ----- KANBAN WEBSITE ---- */
        $('.js_kanban').each(function () {
            website.init_kanban(this);
        });

        setTimeout(function () {
            if (window.location.hash.indexOf("scrollTop=") > -1) {
                window.document.body.scrollTop = +location.hash.match(/scrollTop=([0-9]+)/)[1];
            }
        },0);
    });

    return website;
})();
