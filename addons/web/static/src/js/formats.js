
openerp.web.formats = function(openerp) {

/**
 * Formats a single atomic value based on a field descriptor
 *
 * @param {Object} value read from OpenERP
 * @param {Object} descriptor union of orm field and view field
 * @param {Object} [descriptor.widget] widget to use to display the value
 * @param {Object} descriptor.type fallback if no widget is provided, or if the provided widget is unknown
 * @param {Object} [descriptor.digits] used for the formatting of floats
 * @param {String} [value_if_empty=''] returned if the ``value`` argument is considered empty
 */
openerp.web.format_value = function (value, descriptor, value_if_empty) {
    // If NaN value, display as with a `false` (empty cell)
    if (typeof value === 'number' && isNaN(value)) {
        value = false;
    }
    switch (value) {
        case false:
        case Infinity:
        case -Infinity:
            return value_if_empty === undefined ?  '' : value_if_empty;
    }
    switch (descriptor.widget || descriptor.type) {
        case 'integer':
            return _.sprintf('%d', value);
        case 'float':
            var precision = descriptor.digits ? descriptor.digits[1] : 2;
            var int_part = Math.floor(value);
            var dec_part = Math.abs(Math.floor((value % 1) * Math.pow(10, precision)));
            return _.sprintf('%d%s%d',
                        int_part,
                        openerp.web._t.database.parameters.decimal_point, dec_part);
        case 'float_time':
            return _.sprintf("%02d:%02d",
                    Math.floor(value),
                    Math.round((value % 1) * 60));
        case 'progressbar':
            return _.sprintf(
                '<progress value="%.2f" max="100.0">%.2f%%</progress>',
                    value, value);
        case 'many2one':
            // name_get value format
            return value[1];
        case 'datetime':
            if (typeof(value) == "string")
                value = openerp.web.auto_str_to_date(value);
            try {
                return value.toString(_.sprintf("%s %s", Date.CultureInfo.formatPatterns.shortDate,
                    Date.CultureInfo.formatPatterns.longTime));
            } catch (e) {
                return value.format("%m/%d/%Y %H:%M:%S");
            }
            return value;
        case 'date':
            if (typeof(value) == "string")
                value = openerp.web.auto_str_to_date(value);
            try {
                return value.toString(Date.CultureInfo.formatPatterns.shortDate);
            } catch (e) {
                return value.format("%m/%d/%Y");
            }
        case 'time':
            if (typeof(value) == "string")
                value = openerp.web.auto_str_to_date(value);
            try {
                return value.toString(Date.CultureInfo.formatPatterns.longTime);
            } catch (e) {
                return value.format("%H:%M:%S");
            }
        case 'selection':
            // Each choice is [value, label]
            var result = _(descriptor.selection).detect(function (choice) {
                return choice[0] === value;
            });
            if (result) { return result[1]; }
            return;
        default:
            return value;
    }
};

openerp.web.parse_value = function (value, descriptor, value_if_empty) {
    switch (value) {
        case false:
        case "":
            return value_if_empty === undefined ?  false : value_if_empty;
    }
    switch (descriptor.widget || descriptor.type) {
        case 'integer':
            var tmp;
            do {
                tmp = value;
                value = value.replace(openerp.web._t.database.parameters.thousands_sep, "");
            } while(tmp !== value);
            tmp = Number(value);
            if (isNaN(tmp))
                throw value + " is not a correct integer";
            return tmp;
        case 'float':
            var tmp = Number(value);
            if (!isNaN(tmp))
                return tmp;
            tmp = value.replace(openerp.web._t.database.parameters.decimal_point, ".");
            var tmp2 = tmp;
            do {
                tmp = tmp2;
                tmp2 = tmp.replace(openerp.web._t.database.parameters.thousands_sep, "");
            } while(tmp !== tmp2);
            tmp = Number(tmp);
            if (isNaN(tmp))
                throw value + " is not a correct float";
            return tmp;
        case 'float_time':
            var tmp = value.split(":");
            if (tmp.length != 2)
                throw value + " is not a correct float_time";
            var tmp1 = openerp.web.parse_value(tmp[0], {type: "integer"});
            var tmp2 = openerp.web.parse_value(tmp[1], {type: "integer"});
            return tmp1 + (tmp2 / 60);
        case 'progressbar':
            return openerp.web.parse_value(value, {type: "float"});
        case 'datetime':
            var tmp = Date.parseExact(value, _.sprintf("%s %s", Date.CultureInfo.formatPatterns.shortDate,
                    Date.CultureInfo.formatPatterns.longTime));
            if (tmp !== null)
                return openerp.web.datetime_to_str(tmp);
            tmp = Date.parse(value);
            if (tmp !== null)
                return openerp.web.datetime_to_str(tmp);
            throw value + " is not a valid datetime";
        case 'date':
            var tmp = Date.parseExact(value, Date.CultureInfo.formatPatterns.shortDate);
            if (tmp !== null)
                return openerp.web.date_to_str(tmp);
            tmp = Date.parse(value);
            if (tmp !== null)
                return openerp.web.date_to_str(tmp);
            throw value + " is not a valid date";
        case 'time':
            var tmp = Date.parseExact(value, Date.CultureInfo.formatPatterns.longTime);
            if (tmp !== null)
                return openerp.web.time_to_str(tmp);
            tmp = Date.parse(value);
            if (tmp !== null)
                return openerp.web.time_to_str(tmp);
            throw value + " is not a valid time";
    }
    return value;
};

openerp.web.auto_str_to_date = function(value, type) {
    try {
        return openerp.web.str_to_datetime(value);
    } catch(e) {}
    try {
        return openerp.web.str_to_date(value);
    } catch(e) {}
    try {
        return openerp.web.str_to_time(value);
    } catch(e) {}
    throw "'" + value + "' is not a valid date, datetime nor time"
};

openerp.web.auto_date_to_str = function(value, type) {
    switch(type) {
        case 'datetime':
            return openerp.web.datetime_to_str(value);
        case 'date':
            return openerp.web.date_to_str(value);
        case 'time':
            return openerp.web.time_to_str(value);
        default:
            throw type + " is not convertible to date, datetime nor time"
    }
};

/**
 * Formats a provided cell based on its field type
 *
 * @param {Object} row_data record whose values should be displayed in the cell
 * @param {Object} column column descriptor
 * @param {"button"|"field"} column.tag base control type
 * @param {String} column.type widget type for a field control
 * @param {String} [column.string] button label
 * @param {String} [column.icon] button icon
 * @param {String} [value_if_empty=''] what to display if the field's value is ``false``
 * @param {Boolean} [process_modifiers=true] should the modifiers be computed ?
 */
openerp.web.format_cell = function (row_data, column, value_if_empty, process_modifiers) {
    var attrs = {};
    if (process_modifiers !== false) {
        attrs = column.modifiers_for(row_data);
    }
    if (attrs.invisible) { return ''; }
    if (column.tag === 'button') {
        return [
            '<button type="button" title="', column.string || '', '">',
                '<img src="/web/static/src/img/icons/', column.icon, '.png"',
                    ' alt="', column.string || '', '"/>',
            '</button>'
        ].join('')
    }

    if (!row_data[column.id]) {
        return value_if_empty === undefined ? '' : value_if_empty;
    }
    return openerp.web.format_value(
            row_data[column.id].value, column, value_if_empty);
}
    
};
