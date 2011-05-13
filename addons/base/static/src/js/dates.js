
openerp.base.dates = function(openerp) {

/**
 * Converts a string to a Date javascript object using OpenERP's
 * datetime string format (exemple: '2011-12-01 15:12:35').
 * 
 * The timezone is assumed to be UTC (standard for OpenERP 6.1)
 * and will be converted to the browser's timezone.
 * 
 * @param {String} str A string representing a datetime.
 * @returns {Date}
 */
openerp.base.parse_datetime = function(str) {
    if(!str) {
        return str;
    }
    var regex = /\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d/;
    var res = regex.exec(str);
    if ( res[0] != str ) {
        throw "'" + str + "' is not a valid datetime";
    }
    var obj = Date.parse(str + " GMT");
    if (! obj) {
        throw "'" + str + "' is not a valid datetime";
    }
    return obj;
};

/**
 * Converts a string to a Date javascript object using OpenERP's
 * date string format (exemple: '2011-12-01').
 * 
 * @param {String} str A string representing a date.
 * @returns {Date}
 */
openerp.base.parse_date = function(str) {
    if(!str) {
        return str;
    }
    var regex = /\d\d\d\d-\d\d-\d\d/;
    var res = regex.exec(str);
    if ( res[0] != str ) {
        throw "'" + str + "' is not a valid date";
    }
    var obj = Date.parse(str);
    if (! obj) {
        throw "'" + str + "' is not a valid date";
    }
    return obj;
};

/**
 * Converts a string to a Date javascript object using OpenERP's
 * time string format (exemple: '15:12:35').
 * 
 * @param {String} str A string representing a time.
 * @returns {Date}
 */
openerp.base.parse_time = function(str) {
    if(!str) {
        return str;
    }
    var regex = /\d\d:\d\d:\d\d/;
    var res = regex.exec(str);
    if ( res[0] != str ) {
        throw "'" + str + "' is not a valid time";
    }
    var obj = Date.parse(str);
    if (! obj) {
        throw "'" + str + "' is not a valid time";
    }
    return obj;
};

/*
 * Just a simple function to add some '0' if an integer it too small.
 */
var fts = function(str, size) {
    str = "" + str;
    var to_add = "";
    _.each(_.range(size - str.length), function() {
        to_add = to_add + "0";
    });
    return to_add + str;
};

/**
 * Converts a Date javascript object to a string using OpenERP's
 * datetime string format (exemple: '2011-12-01 15:12:35').
 * 
 * The timezone of the Date object is assumed to be the one of the
 * browser and it will be converted to UTC (standard for OpenERP 6.1).
 * 
 * @param {Date} obj
 * @returns {String} A string representing a datetime.
 */
openerp.base.format_datetime = function(obj) {
    if (!obj) {
        return false;
    }
    return fts(obj.getUTCFullYear(),4) + "-" + fts(obj.getUTCMonth() + 1,2) + "-"
        + fts(obj.getUTCDate(),2) + " " + fts(obj.getUTCHours(),2) + ":"
        + fts(obj.getUTCMinutes(),2) + ":" + fts(obj.getUTCSeconds(),2);
};

/**
 * Converts a Date javascript object to a string using OpenERP's
 * date string format (exemple: '2011-12-01').
 * 
 * @param {Date} obj
 * @returns {String} A string representing a date.
 */
openerp.base.format_date = function(obj) {
    if (!obj) {
        return false;
    }
    return fts(obj.getFullYear(),4) + "-" + fts(obj.getMonth() + 1,2) + "-"
        + fts(obj.getDate(),2);
};

/**
 * Converts a Date javascript object to a string using OpenERP's
 * time string format (exemple: '15:12:35').
 * 
 * @param {Date} obj
 * @returns {String} A string representing a time.
 */
openerp.base.format_time = function(obj) {
    if (!obj) {
        return false;
    }
    return fts(obj.getHours(),2) + ":" + fts(obj.getMinutes(),2) + ":"
        + fts(obj.getSeconds(),2);
};

};

