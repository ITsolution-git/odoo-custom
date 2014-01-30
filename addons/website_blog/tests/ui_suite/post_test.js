var testRunner = require('../../../website/tests/ui_suite/ui_test_runner.js');

var waitFor = testRunner.waitFor;

testRunner.run(function blogTest (page, timeout) {
    page.evaluate(function () { localStorage.clear(); });
    waitFor(function clientReady () {
        return page.evaluate(function () {
            return window.$ && window.openerp && window.openerp.website
                && window.openerp.website.Tour
                && window.openerp.website.Tour.get('blog');
        });
    }, function executeTest () {
        page.evaluate(function () {
            window.openerp.website.Tour.test('blog').run(true, true);
        });
        waitFor(function testExecuted () {
            var after = page.evaluate(function () {
                return window.$ && $('button[data-action=edit]').is(":visible") && {
                    image: $('#wrap [data-snippet-id=image-text]').length,
                    text: $('#wrap [data-snippet-id=text-block]').length,
                };
            });
            var result = after && (after.image === 1) && (after.text === 1);
            return result;
        }, function finish () {
            console.log('{ "event": "success" }');
            phantom.exit();
        }, 4*timeout/5);
    }, timeout/5);
});