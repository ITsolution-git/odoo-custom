var py = require('../lib/py.js'),
    expect = require('expect.js');

var ev = function (str, context) {
    return py.evaluate(py.parse(py.tokenize(str)), context);
};

describe('Literals', function () {
    describe('Number', function () {
        it('should have the right type', function () {
            expect(ev('1')).to.be.a(py.float);
        });
        it('should yield the corresponding JS value', function () {
            expect(py.eval('1')).to.be(1);
            expect(py.eval('42')).to.be(42);
            expect(py.eval('9999')).to.be(9999);
        });
        it('should correctly handle negative literals', function () {
            expect(py.eval('-1')).to.be(-1);
            expect(py.eval('-42')).to.be(-42);
            expect(py.eval('-9999')).to.be(-9999);
        });
        it('should correctly handle float literals', function () {
            expect(py.eval('.42')).to.be(0.42);
            expect(py.eval('1.2')).to.be(1.2);
        });
    });
    describe('Booleans', function () {
        it('should have the right type', function () {
            expect(ev('False')).to.be.a(py.bool);
            expect(ev('True')).to.be.a(py.bool);
        });
        it('should yield the corresponding JS value', function () {
            expect(py.eval('False')).to.be(false);
            expect(py.eval('True')).to.be(true);
        });
    });
    describe('None', function () {
        it('should have the right type', function () {
            expect(ev('None')).to.be.a(py.object)
        });
        it('should yield a JS null', function () {
            expect(py.eval('None')).to.be(null);
        });
    });
    describe('String', function () {
        it('should have the right type', function () {
            expect(ev('"foo"')).to.be.a(py.str);
            expect(ev("'foo'")).to.be.a(py.str);
        });
        it('should yield the corresponding JS string', function () {
            expect(py.eval('"somestring"')).to.be('somestring');
            expect(py.eval("'somestring'")).to.be('somestring');
        });
    });
    describe('Tuple', function () {
        it('shoud have the right type', function () {
            expect(ev('()')).to.be.a(py.tuple);
        });
        it('should map to a JS array', function () {
            expect(py.eval('()')).to.eql([]);
            expect(py.eval('(1, 2, 3)')).to.eql([1, 2, 3]);
        });
    });
    describe('List', function () {
        it('shoud have the right type', function () {
            expect(ev('[]')).to.be.a(py.list);
        });
        it('should map to a JS array', function () {
            expect(py.eval('[]')).to.eql([]);
            expect(py.eval('[1, 2, 3]')).to.eql([1, 2, 3]);
        });
    });
    describe('Dict', function () {
        it('shoud have the right type', function () {
            expect(ev('{}')).to.be.a(py.dict);
        });
        it('should map to a JS object', function () {
            expect(py.eval("{}")).to.eql({});
            expect(py.eval("{'foo': 1, 'bar': 2}"))
                .to.eql({foo: 1, bar: 2});
        });
    });
});
describe('Free variables', function () {
    it('should return its identity', function () {
        expect(py.eval('foo', {foo: 1})).to.be(1);
        expect(py.eval('foo', {foo: true})).to.be(true);
        expect(py.eval('foo', {foo: false})).to.be(false);
        expect(py.eval('foo', {foo: null})).to.be(null);
        expect(py.eval('foo', {foo: 'bar'})).to.be('bar');
    });
});
describe('Comparisons', function () {
    describe('equality', function () {
        it('should work with literals', function () {
            expect(py.eval('1 == 1')).to.be(true);
            expect(py.eval('"foo" == "foo"')).to.be(true);
            expect(py.eval('"foo" == "bar"')).to.be(false);
        });
        it('should work with free variables', function () {
            expect(py.eval('1 == a', {a: 1})).to.be(true);
            expect(py.eval('foo == "bar"', {foo: 'bar'})).to.be(true);
            expect(py.eval('foo == "bar"', {foo: 'qux'})).to.be(false);
        });
    });
    describe('inequality', function () {
        it('should work with literals', function () {
            expect(py.eval('1 != 2')).to.be(true);
            expect(py.eval('"foo" != "foo"')).to.be(false);
            expect(py.eval('"foo" != "bar"')).to.be(true);
        });
        it('should work with free variables', function () {
            expect(py.eval('1 != a', {a: 42})).to.be(true);
            expect(py.eval('foo != "bar"', {foo: 'bar'})).to.be(false);
            expect(py.eval('foo != "bar"', {foo: 'qux'})).to.be(true);
            expect(py.eval('foo != bar', {foo: 'qux', bar: 'quux'}))
                .to.be(true);
        });
    });
    describe('rich comparisons', function () {
        it('should work with numbers', function () {
            expect(py.eval('3 < 5')).to.be(true);
            expect(py.eval('5 >= 3')).to.be(true);
            expect(py.eval('3 >= 3')).to.be(true);
            expect(py.eval('3 > 5')).to.be(false);
        });
        it('should support comparison chains', function () {
            expect(py.eval('1 < 3 < 5')).to.be(true);
            expect(py.eval('5 > 3 > 1')).to.be(true);
            expect(py.eval('1 < 3 > 2 == 2 > -2')).to.be(true);
        });
        it('should compare strings', function () {
            expect(py.eval('date >= current',
                           {date: '2010-06-08', current: '2010-06-05'}))
                .to.be(true);

        });
    });
});
describe('Boolean operators', function () {
    it('should work', function () {
        expect(py.eval("foo == 'foo' or foo == 'bar'",
                       {foo: 'bar'}))
            .to.be(true);;
        expect(py.eval("foo == 'foo' and bar == 'bar'",
                       {foo: 'foo', bar: 'bar'}))
            .to.be(true);;
    });
    it('should be lazy', function () {
        // second clause should nameerror if evaluated
        expect(py.eval("foo == 'foo' or bar == 'bar'",
                       {foo: 'foo'}))
            .to.be(true);;
        expect(py.eval("foo == 'foo' and bar == 'bar'",
                       {foo: 'bar'}))
            .to.be(false);;
    });
    it('should return the actual object', function () {
        expect(py.eval('"foo" or "bar"')).to.be('foo');
        expect(py.eval('None or "bar"')).to.be('bar');
        expect(py.eval('False or None')).to.be(null);
        expect(py.eval('0 or 1')).to.be(1);
    });
});
describe('Containment', function () {
    describe('in sequences', function () {
        it('should match collection items', function () {
            expect(py.eval("'bar' in ('foo', 'bar')"))
                .to.be(true);
            expect(py.eval('1 in (1, 2, 3, 4)'))
                .to.be(true);;
            expect(py.eval('1 in (2, 3, 4)'))
                .to.be(false);;
            expect(py.eval('"url" in ("url",)'))
                .to.be(true);
            expect(py.eval('"foo" in ["foo", "bar"]'))
                .to.be(true);
        });
        it('should not be recursive', function () {
            expect(py.eval('"ur" in ("url",)'))
                .to.be(false);;
        });
        it('should be negatable', function () {
            expect(py.eval('1 not in (2, 3, 4)')).to.be(true);
            expect(py.eval('"ur" not in ("url",)')).to.be(true);
            expect(py.eval('-2 not in (1, 2, 3)')).to.be(true);
        });
    });
    describe('in dict', function () {
        // TODO
    });
    describe('in strings', function () {
        it('should match the whole string', function () {
            expect(py.eval('"view" in "view"')).to.be(true);
            expect(py.eval('"bob" in "view"')).to.be(false);
        });
        it('should match substrings', function () {
            expect(py.eval('"ur" in "url"')).to.be(true);
        });
    });
});
describe('Conversions', function () {
    describe('to bool', function () {
        describe('strings', function () {
            it('should be true if non-empty', function () {
                expect(py.eval('bool(date_deadline)',
                               {date_deadline: '2008'}))
                    .to.be(true);
            });
            it('should be false if empty', function () {
                expect(py.eval('bool(s)', {s: ''})) .to.be(false);
            });
        });
    });
});
describe('Attribute access', function () {
    it("should return the attribute's value", function () {
        var o = new py.object();
        o.bar = py.True;
        expect(py.eval('foo.bar', {foo: o})).to.be(true);
        o.bar = py.False;
        expect(py.eval('foo.bar', {foo: o})).to.be(false);
    });
    it("should work with functions", function () {
        var o = new py.object();
        o.bar = new py.def(function () {
            return new py.str("ok");
        });
        expect(py.eval('foo.bar()', {foo: o})).to.be('ok');
    });
    it('should work on instance attributes', function () {
        var typ = py.type(function MyType() {
            this.attr = new py.float(3);
        }, py.object, {});
        expect(py.eval('MyType().attr', {MyType: typ})).to.be(3);
    });
    it('should work on class attributes', function () {
        var typ = py.type(function MyType() {}, py.object, {
            attr: new py.float(3)
        });
        expect(py.eval('MyType().attr', {MyType: typ})).to.be(3);
    });
    it('should work with methods', function () {
        var typ = py.type(function MyType() {
            this.attr = new py.float(3);
        }, py.object, {
            some_method: function () { return new py.str('ok'); },
            get_attr: function () { return this.attr; }
        });
        expect(py.eval('MyType().some_method()', {MyType: typ})).to.be('ok');
        expect(py.eval('MyType().get_attr()', {MyType: typ})).to.be(3);
    });
});
describe('Callables', function () {
    it('should wrap JS functions', function () {
        expect(py.eval('foo()', {foo: function foo() { return new py.float(3); }}))
            .to.be(3);
    });
    it('should work on custom types', function () {
        var typ = py.type(function MyType() {}, py.object, {
            toJSON: function () { return true; }
        });
        expect(py.eval('MyType()', {MyType: typ})).to.be(true);
    });
});
describe('issubclass', function () {
    it('should say a type is its own subclass', function () {
        expect(py.issubclass.__call__(py.dict, py.dict).toJSON())
            .to.be(true);
        expect(py.eval('issubclass(dict, dict)'))
            .to.be(true);
    });
    it('should work with subtypes', function () {
        expect(py.issubclass.__call__(py.bool, py.object).toJSON())
            .to.be(true);
    });
});
describe('builtins', function () {
    it('should aways be available', function () {
        expect(py.eval('bool("foo")')).to.be(true);
    });
});