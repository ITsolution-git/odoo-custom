odoo.define('web.session', function (require) {
"use strict";

var Session = require('web.Session');
var modules = odoo._modules;

return new Session(undefined, undefined, {modules: modules, use_cors: false});

});
