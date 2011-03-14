/*---------------------------------------------------------
 * John Resig Class, to be moved to openerp.base.Class
 *---------------------------------------------------------*/

(function() {
  var initializing = false, fnTest = /xyz/.test(function(){xyz;}) ? /\b_super\b/ : /.*/;
  // The base Class implementation (does nothing)
  this.Class = function(){};

  // Create a new Class that inherits from this class
  Class.extend = function(prop) {
    var _super = this.prototype;

    // Instantiate a base class (but only create the instance,
    // don't run the init constructor)
    initializing = true;
    var prototype = new this();
    initializing = false;

    // Copy the properties over onto the new prototype
    for (var name in prop) {
      // Check if we're overwriting an existing function
      prototype[name] = typeof prop[name] == "function" && 
        typeof _super[name] == "function" && fnTest.test(prop[name]) ?
        (function(name, fn){
          return function() {
            var tmp = this._super;

            // Add a new ._super() method that is the same method
            // but on the super-class
            this._super = _super[name];

            // The method only need to be bound temporarily, so we
            // remove it when we're done executing
            var ret = fn.apply(this, arguments);
            this._super = tmp;

            return ret;
          };
        })(name, prop[name]) :
        prop[name];
    }

    // The dummy class constructor
    function Class() {
      // All construction is actually done in the init method
      if ( !initializing && this.init )
        this.init.apply(this, arguments);
    }

    // Populate our constructed prototype object
    Class.prototype = prototype;

    // Enforce the constructor to be what we expect
    Class.constructor = Class;

    // And make this class extendable
    Class.extend = arguments.callee;

    return Class;
  };
})();

//---------------------------------------------------------
// OpenERP initialisation and black magic about the pool
//---------------------------------------------------------

(function(){

if(this.openerp)
    return;

var openerp = this.openerp = function() {
    // create a new pool instance
    var o = {};

    // links to the global openerp
    o._openerp = openerp;

    // Only base will be loaded, the rest will be by loaded by
    // openerp.base.Connection on the first connection
    o._modules_loaded = false;

    // this unique id will be replaced by hostname_databasename by
    // openerp.base.Connection on the first connection
    o._session_id = "session" + openerp.sessions.length;
    openerp.sessions[o._session_id] = o;

    o.screen = openerp.screen;
    o.sessions = openerp.sessions;
    o.base = {};
    openerp.base(o);

    return o;
};

// element_ids registry linked to all controllers on the page
// TODO rename to elements, or keep gtk naming?
this.openerp.screen = {};

// Per session namespace
// openerp.<module> will map to
// openerp.sessions.servername_port_dbname_login.<module> using a closure
this.openerp.sessions = {};

})();

// vim:et fdc=0 fdl=0 foldnestmax=3 fdm=syntax:
