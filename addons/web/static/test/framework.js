(function() {

var ropenerp = window.openerp;

var openerp = ropenerp.declare($, _, QWeb2);

ropenerp.testing.section('class', {
    dependencies: ['web.corelib']
}, function (test) {
    test('Basic class creation', function (instance) {
        var C = instance.web.Class.extend({
            foo: function () {
                return this.somevar;
            }
        });
        var i = new C();
        i.somevar = 3;

        ok(i instanceof C);
        strictEqual(i.foo(), 3);
    });
    test('Class initialization', function (instance) {
        var C1 = instance.web.Class.extend({
            init: function () {
                this.foo = 3;
            }
        });
        var C2 = instance.web.Class.extend({
            init: function (arg) {
                this.foo = arg;
            }
        });

        var i1 = new C1(),
            i2 = new C2(42);

        strictEqual(i1.foo, 3);
        strictEqual(i2.foo, 42);
    });
    test('Inheritance', function (instance) {
        var C0 = instance.web.Class.extend({
            foo: function () {
                return 1;
            }
        });
        var C1 = C0.extend({
            foo: function () {
                return 1 + this._super();
            }
        });
        var C2 = C1.extend({
            foo: function () {
                return 1 + this._super();
            }
        });

        strictEqual(new C0().foo(), 1);
        strictEqual(new C1().foo(), 2);
        strictEqual(new C2().foo(), 3);
    });
    test('In-place extension', function (instance) {
        var C0 = instance.web.Class.extend({
            foo: function () {
                return 3;
            },
            qux: function () {
                return 3;
            },
            bar: 3
        });
        C0.include({
            foo: function () {
                return 5;
            },
            qux: function () {
                return 2 + this._super();
            },
            bar: 5,
            baz: 5
        });

        strictEqual(new C0().bar, 5);
        strictEqual(new C0().baz, 5);
        strictEqual(new C0().foo(), 5);
        strictEqual(new C0().qux(), 5);
    });
    test('In-place extension and inheritance', function (instance) {
        var C0 = instance.web.Class.extend({
            foo: function () { return 1; },
            bar: function () { return 1; }
        });
        var C1 = C0.extend({
            foo: function () { return 1 + this._super(); }
        });
        strictEqual(new C1().foo(), 2);
        strictEqual(new C1().bar(), 1);

        C1.include({
            foo: function () { return 2 + this._super(); },
            bar: function () { return 1 + this._super(); }
        });
        strictEqual(new C1().foo(), 4);
        strictEqual(new C1().bar(), 2);
    });
    test('In-place extensions alter existing instances', function (instance) {
        var C0 = instance.web.Class.extend({
            foo: function () { return 1; },
            bar: function () { return 1; }
        });
        var i = new C0();
        strictEqual(i.foo(), 1);
        strictEqual(i.bar(), 1);

        C0.include({
            foo: function () { return 2; },
            bar: function () { return 2 + this._super(); }
        });
        strictEqual(i.foo(), 2);
        strictEqual(i.bar(), 3);
    });
    test('In-place extension of subclassed types', function (instance) {
        var C0 = instance.web.Class.extend({
            foo: function () { return 1; },
            bar: function () { return 1; }
        });
        var C1 = C0.extend({
            foo: function () { return 1 + this._super(); },
            bar: function () { return 1 + this._super(); }
        });
        var i = new C1();
        strictEqual(i.foo(), 2);
        C0.include({
            foo: function () { return 2; },
            bar: function () { return 2 + this._super(); }
        });
        strictEqual(i.foo(), 3);
        strictEqual(i.bar(), 4);
    });
});


ropenerp.testing.section('Widget.proxy', {
}, function (test) {
    test('(String)', function () {
        var W = openerp.web.Widget.extend({
            exec: function () {
                this.executed = true;
            }
        });
        var w = new W();
        var fn = w.proxy('exec');
        fn();
        ok(w.executed, 'should execute the named method in the right context');
    });
    test('(String)(*args)', function () {
        var W = openerp.web.Widget.extend({
            exec: function (arg) {
                this.executed = arg;
            }
        });
        var w = new W();
        var fn = w.proxy('exec');
        fn(42);
        ok(w.executed, "should execute the named method in the right context");
        equal(w.executed, 42, "should be passed the proxy's arguments");
    });
    test('(String), include', function () {
        // the proxy function should handle methods being changed on the class
        // and should always proxy "by name", to the most recent one
        var W = openerp.web.Widget.extend({
            exec: function () {
                this.executed = 1;
            }
        });
        var w = new W();
        var fn = w.proxy('exec');
        W.include({
            exec: function () { this.executed = 2; }
        });

        fn();
        equal(w.executed, 2, "should be lazily resolved");
    });

    test('(Function)', function () {
        var w = new (openerp.web.Widget.extend({ }))();

        var fn = w.proxy(function () { this.executed = true; });
        fn();
        ok(w.executed, "should set the function's context (like Function#bind)");
    });
    test('(Function)(*args)', function () {
        var w = new (openerp.web.Widget.extend({ }))();

        var fn = w.proxy(function (arg) { this.executed = arg; });
        fn(42);
        equal(w.executed, 42, "should be passed the proxy's arguments");
    });
});
ropenerp.testing.section('Widget.renderElement', {
    setup: function () {
        openerp.web.qweb = new QWeb2.Engine();
        openerp.web.qweb.add_template(
            '<no>' +
                '<t t-name="test.widget.template">' +
                    '<ol>' +
                        '<li t-foreach="5" t-as="counter" ' +
                            't-attf-class="class-#{counter}">' +
                            '<input/>' +
                            '<t t-esc="counter"/>' +
                        '</li>' +
                    '</ol>' +
                '</t>' +
                '<t t-name="test.widget.template-value">' +
                    '<p><t t-esc="widget.value"/></p>' +
                '</t>' +
            '</no>');
    }
}, function (test) {
    test('no template, default', function () {
        var w = new (openerp.web.Widget.extend({ }))();

        var $original = w.$el;
        ok($original, "should initially have a root element");
        w.renderElement();
        ok(w.$el, "should have generated a root element");
        ok($original !== w.$el, "should have generated a new root element");
        strictEqual(w.$el, w.$el, "should provide $el alias");
        ok(w.$el.is(w.el), "should provide raw DOM alias");

        equal(w.el.nodeName, 'DIV', "should have generated the default element");
        equal(w.el.attributes.length, 0, "should not have generated any attribute");
        ok(_.isEmpty(w.$el.html(), "should not have generated any content"));
    });
    test('no template, custom tag', function () {
        var w = new (openerp.web.Widget.extend({
            tagName: 'ul'
        }))();
        w.renderElement();

        equal(w.el.nodeName, 'UL', "should have generated the custom element tag");
    });
    test('no template, @id', function () {
        var w = new (openerp.web.Widget.extend({
            id: 'foo'
        }))();
        w.renderElement();

        equal(w.el.attributes.length, 1, "should have one attribute");
        equal(w.$el.attr('id'), 'foo', "should have generated the id attribute");
        equal(w.el.id, 'foo', "should also be available via property");
    });
    test('no template, @className', function () {
        var w = new (openerp.web.Widget.extend({
            className: 'oe_some_class'
        }))();
        w.renderElement();

        equal(w.el.className, 'oe_some_class', "should have the right property");
        equal(w.$el.attr('class'), 'oe_some_class', "should have the right attribute");
    });
    test('no template, bunch of attributes', function () {
        var w = new (openerp.web.Widget.extend({
            attributes: {
                'id': 'some_id',
                'class': 'some_class',
                'data-foo': 'data attribute',
                'clark': 'gable',
                'spoiler': 'snape kills dumbledore'
            }
        }))();
        w.renderElement();

        equal(w.el.attributes.length, 5, "should have all the specified attributes");

        equal(w.el.id, 'some_id');
        equal(w.$el.attr('id'), 'some_id');

        equal(w.el.className, 'some_class');
        equal(w.$el.attr('class'), 'some_class');

        equal(w.$el.attr('data-foo'), 'data attribute');
        equal(w.$el.data('foo'), 'data attribute');

        equal(w.$el.attr('clark'), 'gable');
        equal(w.$el.attr('spoiler'), 'snape kills dumbledore');
    });

    test('template', function () {
        var w = new (openerp.web.Widget.extend({
            template: 'test.widget.template'
        }))();
        w.renderElement();

        equal(w.el.nodeName, 'OL');
        equal(w.$el.children().length, 5);
        equal(w.el.textContent, '01234');
    });
    test('repeated', { asserts: 4 }, function (_unused, $fix) {
        var w = new (openerp.web.Widget.extend({
            template: 'test.widget.template-value'
        }))();
        w.value = 42;
        return w.appendTo($fix)
            .done(function () {
                equal($fix.find('p').text(), '42', "DOM fixture should contain initial value");
                equal(w.$el.text(), '42', "should set initial value");
                w.value = 36;
                w.renderElement();
                equal($fix.find('p').text(), '36', "DOM fixture should use new value");
                equal(w.$el.text(), '36', "should set new value");
            });
    });
});
ropenerp.testing.section('Widget.$', {
    setup: function () {
        openerp.web.qweb = new QWeb2.Engine();
        openerp.web.qweb.add_template(
            '<no>' +
                '<t t-name="test.widget.template">' +
                    '<ol>' +
                        '<li t-foreach="5" t-as="counter" ' +
                            't-attf-class="class-#{counter}">' +
                            '<input/>' +
                            '<t t-esc="counter"/>' +
                        '</li>' +
                    '</ol>' +
                '</t>' +
            '</no>');
    }
}, function (test) {
    test('basic-alias', function () {
        var w = new (openerp.web.Widget.extend({
            template: 'test.widget.template'
        }))();
        w.renderElement();

        ok(w.$('li:eq(3)').is(w.$el.find('li:eq(3)')),
           "should do the same thing as calling find on the widget root");
    });
});
ropenerp.testing.section('Widget.events', {
    setup: function () {
        openerp.web.qweb = new QWeb2.Engine();
        openerp.web.qweb.add_template(
            '<no>' +
                '<t t-name="test.widget.template">' +
                    '<ol>' +
                        '<li t-foreach="5" t-as="counter" ' +
                            't-attf-class="class-#{counter}">' +
                            '<input/>' +
                            '<t t-esc="counter"/>' +
                        '</li>' +
                    '</ol>' +
                '</t>' +
            '</no>');
    }
}, function (test) {
    test('delegate', function () {
        var a = [];
        var w = new (openerp.web.Widget.extend({
            template: 'test.widget.template',
            events: {
                'click': function () {
                    a[0] = true;
                    strictEqual(this, w, "should trigger events in widget");
                },
                'click li.class-3': 'class3',
                'change input': function () { a[2] = true; }
            },
            class3: function () { a[1] = true; }
        }))();
        w.renderElement();

        w.$el.click();
        w.$('li:eq(3)').click();
        w.$('input:last').val('foo').change();

        for(var i=0; i<3; ++i) {
            ok(a[i], "should pass test " + i);
        }
    });
    test('undelegate', function () {
        var clicked = false, newclicked = false;
        var w = new (openerp.web.Widget.extend({
            template: 'test.widget.template',
            events: { 'click li': function () { clicked = true; } }
        }))();
        w.renderElement();
        w.$el.on('click', 'li', function () { newclicked = true; });

        w.$('li').click();
        ok(clicked, "should trigger bound events");
        ok(newclicked, "should trigger bound events");
        clicked = newclicked = false;

        w.undelegateEvents();
        w.$('li').click();
        ok(!clicked, "undelegate should unbind events delegated");
        ok(newclicked, "undelegate should only unbind events it created");
    });
});

})();
