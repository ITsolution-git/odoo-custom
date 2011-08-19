
openerp.base.formats = function(openerp) {

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
openerp.base.format_value = function (value, descriptor, value_if_empty) {
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
            var dec_part = Math.floor((value % 1) * Math.pow(10, precision));
            return _.sprintf('%d' + openerp.base._t.database.parameters.decimal_point + '%d', int_part, dec_part);
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
                value = openerp.base.str_to_datetime(value);
            try {
                return value.strftime(_.sprintf("%s %s", openerp.base._t.database.parameters.date_format, 
                    openerp.base._t.database.parameters.time_format));
            } catch (e) {
                return openerp.base.datetime_to_str(value);
            }
            return value;
        case 'date':
            if (typeof(value) == "string")
                value = openerp.base.str_to_date(value);
            try {
                return value.strftime(openerp.base._t.database.parameters.date_format);
            } catch (e) {
                return openerp.base.date_to_str(value);
            }
        case 'datetime':
            if (typeof(value) == "string")
                value = openerp.base.str_to_time(value);
            try {
                return value.strftime(openerp.base._t.database.parameters.time_format);
            } catch (e) {
                return openerp.base.time_to_str(value);
            }
        default:
            return value;
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
 */
openerp.base.format_cell = function (row_data, column, value_if_empty) {
    var attrs = column.modifiers_for(row_data);
    if (attrs.invisible) { return ''; }
    if (column.tag === 'button') {
        return [
            '<button type="button" title="', column.string || '', '">',
                '<img src="/base/static/src/img/icons/', column.icon, '.png"',
                    ' alt="', column.string || '', '"/>',
            '</button>'
        ].join('')
    }

    return openerp.base.format_value(
            row_data[column.id].value, column, value_if_empty);
}
    
};
