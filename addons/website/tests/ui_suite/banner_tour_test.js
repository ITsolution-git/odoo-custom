var testRunner = require('./ui_test_runner.js');

var waitFor = testRunner.waitFor;

testRunner.run(function testBannerTour (page) {
    page.evaluate(function () { localStorage.clear(); });
    waitFor(function () {
        return page.evaluate(function () {
            return window.openerp && window.openerp.website
                && window.openerp.website.TestConsole
                && window.openerp.website.TestConsole.test('banner');
        });
    }, function () {
        var before = page.evaluate(function () {
            var result = {
                carousel: $('#wrap [data-snippet-id=carousel]').length,
                columns: $('#wrap [data-snippet-id=three-columns]').length,
            };
            window.openerp.website.TestConsole.test('banner').run(true);
            return result;
        });
        waitFor(function () {
            var after = page.evaluate(function () {
                if ($('button[data-action=edit]').is(":visible")) {
                    console.error("why?");
                    return {
                        carousel: $('#wrap [data-snippet-id=carousel]').length,
                        columns: $('#wrap [data-snippet-id=three-columns]').length,
                    };
                }
            });
            return after && after.carousel === before.carousel + 1 && after.columns === before.columns + 1;
        }, function () {
            console.log('{ "event": "success" }');
            phantom.exit();
        });
    });
});