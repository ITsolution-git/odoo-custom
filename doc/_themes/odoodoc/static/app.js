$(function () {
    var $body = $(document.body);
    $body.scrollspy({ target: '.sphinxsidebarwrapper' });
    $(window).on('load', function () {
        $body.scrollspy('refresh');
    });

    // Sidenav affixing
    setTimeout(function () {
        var $sideBar = $('.sphinxsidebarwrapper');

        $sideBar.affix({
            offset: {
                top: function () {
                    var offsetTop = $sideBar.offset().top;
                    var sideBarMargin = parseInt($sideBar.children(0).css('margin-top'), 10);
                    var navOuterHeight = $('.docs-nav').height();

                    return (this.top = offsetTop - navOuterHeight - sideBarMargin);
                },
                bottom: function () {
                    return (this.bottom = $('div.footer').outerHeight(true));
                }
            }
        });
    }, 100);

    /*
    for clipboard:
    * add per-language setup code to document, hidden
    * adds button to each switchable language block except when they're setup
      stuff because fuck'em
    * per-language, add clipboard hook to prefix with setup bit on-copy
    * setup bit is... ?
    * actually not all blocks because we don't want to add the setup bits to
      the setup bits, so that's kinda shit
     */
    document.addEventListener('copy', function (e) {
        var target = $(e.target).closest('.switchable:not(.setup)').get(0);
        // not in a switchable
        if (!target) { return; }
        var lang = getHighlightLanguage(target);
        if (!lang) {
            // switchable without highlight (e.g. language-specific notes),
            // don't munge
            return;
        }
        e.preventDefault();

        // get generic setup code
        var prefix = document.querySelector('.setupcode.highlight-' + lang).textContent;

        // prepend setup code to current snippet, get all of current snippet
        // in case only part of it was selected
        var data = prefix + target.textContent;
        // sane browsers
        e.clipboardData.setData('text/plain', data);
        // MSIE
        e.clipboardData.setData('Text', data);
    });

    // stripe page stuff
    if ($('div.document-super').hasClass('stripe')) { (function () {
        // iterate on highlighted PL blocks (but not results because that'd
        // be gross), extract all switchable PLs in the document and add
        // clipboard-copy buttons
        var languages = {};
        $('div.switchable').each(function () {
            var language = getHighlightLanguage(this);
            if (language) {
                languages[language] = true;
            }
        });

        // if can't find CSS where base rule lives something's probably
        // broken, bail
        var sheet = findSheet(/style\.css$/);
        if (!sheet) { return; }
        // build PL switcher UI and hook toggle event
        $(buildSwitcher(Object.keys(languages)))
            .prependTo('div.documentwrapper')
            .on('click', 'li', function (e) {
                $(e.target).addClass('active')
                    .siblings().removeClass('active');
                var id = e.target.textContent;
                var lastIndex = sheet.cssRules.length - 1;
                var content = sheet.cssRules[lastIndex].style.cssText;
                // change rule in CSS because why not (also can add new
                // languages without having to e.g. change CSS or anything)
                var sel = [
                    '.stripe .only-', id, ', ',
                    '.stripe .highlight-', id, ' > .highlight'
                ].join('');
                sheet.deleteRule(lastIndex);
                sheet.insertRule(sel + '{' + content + '}', lastIndex);
        });
    })(); }

    /**
     * @param {Node} node highlight node to get the language of
     * @returns {String|null} either the highlight language or null
     */
    function getHighlightLanguage(node) {
        var classes = node.className.split(/\s+/);
        for (var i = 0; i < classes.length; ++i) {
            var cls = classes[i];
            if (/^highlight-/.test(cls)) {
                return cls.slice(10);
            }
        }
        return null;
    }
    // programming language switcher
    function findSheet(pattern, fromSheet) {
        if (fromSheet) {
            for(var i=0; i<fromSheet.cssRules.length; ++i) {
                var rule = fromSheet.cssRules[i];
                if (rule.type !== CSSRule.IMPORT_RULE) { continue; }
                if (pattern.test(rule.href)) {
                    return rule.styleSheet;
                }
            }
            return null;
        }
        var sheets = document.styleSheets;
        for(var j=0; j<sheets.length; ++j) {
            var sheet = sheets[j];
            if (pattern.test(sheet.href)) {
                return sheet;
            }
            var subSheet;
            if (subSheet = findSheet(pattern, sheet)) {
                return subSheet;
            }
        }
        return null;
    }
    function buildSwitcher(languages) {
        var root = document.createElement('ul');
        root.className = "switcher";
        for(var i=0; i<languages.length; ++i) {
            var item = document.createElement('li');
            item.textContent = languages[i];
            if (i === 0) {
                item.className = "active";
            }
            root.appendChild(item);
        }
        return root;
    }
});
