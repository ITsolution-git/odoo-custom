# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

#
# Object relationnal mapping to postgresql module
#    . Hierarchical structure
#    . Constraints consistency, validations
#    . Object meta Data depends on its status
#    . Optimised processing by complex query (multiple actions at once)
#    . Default fields value
#    . Permissions optimisation
#    . Persistant object: DB postgresql
#    . Datas conversions
#    . Multi-level caching system
#    . 2 different inheritancies
#    . Fields:
#         - classicals (varchar, integer, boolean, ...)
#         - relations (one2many, many2one, many2many)
#         - functions
#
#
import calendar
import copy
import datetime
import logging
import operator
import pickle
import re
import string
import time
import traceback
import types

import netsvc
from lxml import etree
from tools.config import config
from tools.translate import _

import fields
import tools
from tools.safe_eval import safe_eval as eval

regex_order = re.compile('^(([a-z0-9_]+|"[a-z0-9_]+")( *desc| *asc)?( *, *|))+$', re.I)


POSTGRES_CONFDELTYPES = {
    'RESTRICT': 'r',
    'NO ACTION': 'a',
    'CASCADE': 'c',
    'SET NULL': 'n',
    'SET DEFAULT': 'd',
}

def last_day_of_current_month():
    today = datetime.date.today()
    last_day = str(calendar.monthrange(today.year, today.month)[1])
    return time.strftime('%Y-%m-' + last_day)

def intersect(la, lb):
    return filter(lambda x: x in lb, la)

class except_orm(Exception):
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.args = (name, value)

class BrowseRecordError(Exception):
    pass

# Readonly python database object browser
class browse_null(object):

    def __init__(self):
        self.id = False

    def __getitem__(self, name):
        return None

    def __getattr__(self, name):
        return None  # XXX: return self ?

    def __int__(self):
        return False

    def __str__(self):
        return ''

    def __nonzero__(self):
        return False

    def __unicode__(self):
        return u''


#
# TODO: execute an object method on browse_record_list
#
class browse_record_list(list):

    def __init__(self, lst, context=None):
        if not context:
            context = {}
        super(browse_record_list, self).__init__(lst)
        self.context = context


class browse_record(object):
    logger = netsvc.Logger()

    def __init__(self, cr, uid, id, table, cache, context=None, list_class = None, fields_process={}):
        '''
        table : the object (inherited from orm)
        context : dictionary with an optional context
        '''
        if not context:
            context = {}
        self._list_class = list_class or browse_record_list
        self._cr = cr
        self._uid = uid
        self._id = id
        self._table = table
        self._table_name = self._table._name
        self.__logger = logging.getLogger(
            'osv.browse_record.' + self._table_name)
        self._context = context
        self._fields_process = fields_process

        cache.setdefault(table._name, {})
        self._data = cache[table._name]

        if not (id and isinstance(id, (int, long,))):
            raise BrowseRecordError(_('Wrong ID for the browse record, got %r, expected an integer.') % (id,))
#        if not table.exists(cr, uid, id, context):
#            raise BrowseRecordError(_('Object %s does not exists') % (self,))

        if id not in self._data:
            self._data[id] = {'id': id}

        self._cache = cache

    def __getitem__(self, name):
        if name == 'id':
            return self._id

        if name not in self._data[self._id]:
            # build the list of fields we will fetch

            # fetch the definition of the field which was asked for
            if name in self._table._columns:
                col = self._table._columns[name]
            elif name in self._table._inherit_fields:
                col = self._table._inherit_fields[name][2]
            elif hasattr(self._table, str(name)):
                attr = getattr(self._table, name)

                if isinstance(attr, (types.MethodType, types.LambdaType, types.FunctionType)):
                    return lambda *args, **argv: attr(self._cr, self._uid, [self._id], *args, **argv)
                else:
                    return attr
            else:
                self.logger.notifyChannel("browse_record", netsvc.LOG_WARNING,
                    "Field '%s' does not exist in object '%s': \n%s" % (
                        name, self, ''.join(traceback.format_exc())))
                raise KeyError("Field '%s' does not exist in object '%s'" % (
                    name, self))

            # if the field is a classic one or a many2one, we'll fetch all classic and many2one fields
            if col._prefetch:
                # gen the list of "local" (ie not inherited) fields which are classic or many2one
                fields_to_fetch = filter(lambda x: x[1]._classic_write, self._table._columns.items())
                # gen the list of inherited fields
                inherits = map(lambda x: (x[0], x[1][2]), self._table._inherit_fields.items())
                # complete the field list with the inherited fields which are classic or many2one
                fields_to_fetch += filter(lambda x: x[1]._classic_write, inherits)
            # otherwise we fetch only that field
            else:
                fields_to_fetch = [(name, col)]
            ids = filter(lambda id: name not in self._data[id], self._data.keys())
            # read the results
            field_names = map(lambda x: x[0], fields_to_fetch)
            field_values = self._table.read(self._cr, self._uid, ids, field_names, context=self._context, load="_classic_write")
            if self._fields_process:
                lang = self._context.get('lang', 'en_US') or 'en_US'
                lang_obj_ids = self.pool.get('res.lang').search(self._cr, self._uid,[('code','=',lang)])
                if not lang_obj_ids:
                    raise Exception(_('Language with code "%s" is not defined in your system !\nDefine it through the Administration menu.') % (lang,))
                lang_obj = self.pool.get('res.lang').browse(self._cr, self._uid,lang_obj_ids[0])

                for field_name, field_column in fields_to_fetch:
                    if field_column._type in self._fields_process:
                        for result_line in field_values:
                            result_line[field_name] = self._fields_process[field_column._type](result_line[field_name])
                            if result_line[field_name]:
                                result_line[field_name].set_value(self._cr, self._uid, result_line[field_name], self, field_column, lang_obj)

            if not field_values:
                # Where did those ids come from? Perhaps old entries in ir_model_dat?
                self.__logger.warn("No field_values found for ids %s in %s", ids, self)
                raise KeyError('Field %s not found in %s'%(name,self))
            # create browse records for 'remote' objects
            for result_line in field_values:
                new_data = {}
                for field_name, field_column in fields_to_fetch:
                    if field_column._type in ('many2one', 'one2one'):
                        if result_line[field_name]:
                            obj = self._table.pool.get(field_column._obj)
                            if isinstance(result_line[field_name], (list,tuple)):
                                value = result_line[field_name][0]
                            else:
                                value = result_line[field_name]
                            if value:
                                # FIXME: this happen when a _inherits object
                                #        overwrite a field of it parent. Need
                                #        testing to be sure we got the right
                                #        object and not the parent one.
                                if not isinstance(value, browse_record):
                                    new_data[field_name] = browse_record(self._cr,
                                        self._uid, value, obj, self._cache,
                                        context=self._context,
                                        list_class=self._list_class,
                                        fields_process=self._fields_process)
                                else:
                                    new_data[field_name] = value
                            else:
                                new_data[field_name] = browse_null()
                        else:
                            new_data[field_name] = browse_null()
                    elif field_column._type in ('one2many', 'many2many') and len(result_line[field_name]):
                        new_data[field_name] = self._list_class([browse_record(self._cr, self._uid, id, self._table.pool.get(field_column._obj), self._cache, context=self._context, list_class=self._list_class, fields_process=self._fields_process) for id in result_line[field_name]], self._context)
                    elif field_column._type in ('reference'):
                        if result_line[field_name]:
                            if isinstance(result_line[field_name], browse_record):
                                new_data[field_name] = result_line[field_name]
                            else:
                                ref_obj, ref_id = result_line[field_name].split(',')
                                ref_id = long(ref_id)
                                obj = self._table.pool.get(ref_obj)
                                new_data[field_name] = browse_record(self._cr, self._uid, ref_id, obj, self._cache, context=self._context, list_class=self._list_class, fields_process=self._fields_process)
                        else:
                            new_data[field_name] = browse_null()
                    else:
                        new_data[field_name] = result_line[field_name]
                self._data[result_line['id']].update(new_data)

        if not name in self._data[self._id]:
            #how did this happen?
            self.logger.notifyChannel("browse_record", netsvc.LOG_ERROR,
                    "Fields to fetch: %s, Field values: %s"%(field_names, field_values))
            self.logger.notifyChannel("browse_record", netsvc.LOG_ERROR,
                    "Cached: %s, Table: %s"%(self._data[self._id], self._table))
            raise KeyError(_('Unknown attribute %s in %s ') % (name, self))
        return self._data[self._id][name]

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError, e:
            raise AttributeError(e)

    def __contains__(self, name):
        return (name in self._table._columns) or (name in self._table._inherit_fields) or hasattr(self._table, name)

    def __hasattr__(self, name):
        return name in self

    def __int__(self):
        return self._id

    def __str__(self):
        return "browse_record(%s, %d)" % (self._table_name, self._id)

    def __eq__(self, other):
        if not isinstance(other, browse_record):
            return False
        return (self._table_name, self._id) == (other._table_name, other._id)

    def __ne__(self, other):
        if not isinstance(other, browse_record):
            return True
        return (self._table_name, self._id) != (other._table_name, other._id)

    # we need to define __unicode__ even though we've already defined __str__
    # because we have overridden __getattr__
    def __unicode__(self):
        return unicode(str(self))

    def __hash__(self):
        return hash((self._table_name, self._id))

    __repr__ = __str__


def get_pg_type(f):
    '''
    returns a tuple
    (type returned by postgres when the column was created, type expression to create the column)
    '''

    type_dict = {
            fields.boolean: 'bool',
            fields.integer: 'int4',
            fields.integer_big: 'int8',
            fields.text: 'text',
            fields.date: 'date',
            fields.time: 'time',
            fields.datetime: 'timestamp',
            fields.binary: 'bytea',
            fields.many2one: 'int4',
            }
    if type(f) in type_dict:
        f_type = (type_dict[type(f)], type_dict[type(f)])
    elif isinstance(f, fields.float):
        if f.digits:
            f_type = ('numeric', 'NUMERIC')
        else:
            f_type = ('float8', 'DOUBLE PRECISION')
    elif isinstance(f, (fields.char, fields.reference)):
        f_type = ('varchar', 'VARCHAR(%d)' % (f.size,))
    elif isinstance(f, fields.selection):
        if isinstance(f.selection, list) and isinstance(f.selection[0][0], (str, unicode)):
            f_size = reduce(lambda x, y: max(x, len(y[0])), f.selection, f.size or 16)
        elif isinstance(f.selection, list) and isinstance(f.selection[0][0], int):
            f_size = -1
        else:
            f_size = getattr(f, 'size', None) or 16

        if f_size == -1:
            f_type = ('int4', 'INTEGER')
        else:
            f_type = ('varchar', 'VARCHAR(%d)' % f_size)
    elif isinstance(f, fields.function) and eval('fields.'+(f._type),globals()) in type_dict:
        t = eval('fields.'+(f._type), globals())
        f_type = (type_dict[t], type_dict[t])
    elif isinstance(f, fields.function) and f._type == 'float':
        if f.digits:
            f_type = ('numeric', 'NUMERIC')
        else:
            f_type = ('float8', 'DOUBLE PRECISION')
    elif isinstance(f, fields.function) and f._type == 'selection':
        f_type = ('text', 'text')
    elif isinstance(f, fields.function) and f._type == 'char':
        f_type = ('varchar', 'VARCHAR(%d)' % (f.size))
    else:
        logger = netsvc.Logger()
        logger.notifyChannel("init", netsvc.LOG_WARNING, '%s type not supported!' % (type(f)))
        f_type = None
    return f_type


class orm_template(object):
    _name = None
    _columns = {}
    _constraints = []
    _defaults = {}
    _rec_name = 'name'
    _parent_name = 'parent_id'
    _parent_store = False
    _parent_order = False
    _date_name = 'date'
    _order = 'id'
    _sequence = None
    _description = None
    _inherits = {}
    _table = None
    _invalids = set()
    _log_create = False

    CONCURRENCY_CHECK_FIELD = '__last_update'
    def log(self, cr, uid, id, message, secondary=False, context=None):
        return self.pool.get('res.log').create(cr, uid, {
            'name': message,
            'res_model': self._name,
            'secondary': secondary,
            'res_id': id},
                context=context
        )

    def view_init(self, cr , uid , fields_list, context=None):
        """Override this method to do specific things when a view on the object is opened."""
        pass

    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None):
        raise NotImplementedError(_('The read_group method is not implemented on this object !'))

    def _field_create(self, cr, context={}):
        cr.execute("SELECT id FROM ir_model WHERE model=%s", (self._name,))
        if not cr.rowcount:
            cr.execute('SELECT nextval(%s)', ('ir_model_id_seq',))
            model_id = cr.fetchone()[0]
            cr.execute("INSERT INTO ir_model (id,model, name, info,state) VALUES (%s, %s, %s, %s, %s)", (model_id, self._name, self._description, self.__doc__, 'base'))
        else:
            model_id = cr.fetchone()[0]
        if 'module' in context:
            name_id = 'model_'+self._name.replace('.','_')
            cr.execute('select * from ir_model_data where name=%s and res_id=%s and module=%s', (name_id,model_id,context['module']))
            if not cr.rowcount:
                cr.execute("INSERT INTO ir_model_data (name,date_init,date_update,module,model,res_id) VALUES (%s, now(), now(), %s, %s, %s)", \
                    (name_id, context['module'], 'ir.model', model_id)
                )

        cr.commit()

        cr.execute("SELECT * FROM ir_model_fields WHERE model=%s", (self._name,))
        cols = {}
        for rec in cr.dictfetchall():
            cols[rec['name']] = rec

        for (k, f) in self._columns.items():
            vals = {
                'model_id': model_id,
                'model': self._name,
                'name': k,
                'field_description': f.string.replace("'", " "),
                'ttype': f._type,
                'relation': f._obj or '',
                'view_load': (f.view_load and 1) or 0,
                'select_level': tools.ustr(f.select or 0),
                'readonly':(f.readonly and 1) or 0,
                'required':(f.required and 1) or 0,
                'selectable' : (f.selectable and 1) or 0,
                'relation_field': (f._type=='one2many' and isinstance(f,fields.one2many)) and f._fields_id or '',
            }
            # When its a custom field,it does not contain f.select
            if context.get('field_state','base') == 'manual':
                if context.get('field_name','') == k:
                    vals['select_level'] = context.get('select','0')
                #setting value to let the problem NOT occur next time
                else:
                    vals['select_level'] = cols[k]['select_level']

            if k not in cols:
                cr.execute('select nextval(%s)', ('ir_model_fields_id_seq',))
                id = cr.fetchone()[0]
                vals['id'] = id
                cr.execute("""INSERT INTO ir_model_fields (
                    id, model_id, model, name, field_description, ttype,
                    relation,view_load,state,select_level,relation_field
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                )""", (
                    id, vals['model_id'], vals['model'], vals['name'], vals['field_description'], vals['ttype'],
                     vals['relation'], bool(vals['view_load']), 'base',
                    vals['select_level'],vals['relation_field']
                ))
                if 'module' in context:
                    name1 = 'field_' + self._table + '_' + k
                    cr.execute("select name from ir_model_data where name=%s", (name1,))
                    if cr.fetchone():
                        name1 = name1 + "_" + str(id)
                    cr.execute("INSERT INTO ir_model_data (name,date_init,date_update,module,model,res_id) VALUES (%s, now(), now(), %s, %s, %s)", \
                        (name1, context['module'], 'ir.model.fields', id)
                    )
            else:
                for key, val in vals.items():
                    if cols[k][key] != vals[key]:
                        cr.execute('update ir_model_fields set field_description=%s where model=%s and name=%s', (vals['field_description'], vals['model'], vals['name']))
                        cr.commit()
                        cr.execute("""UPDATE ir_model_fields SET
                            model_id=%s, field_description=%s, ttype=%s, relation=%s,
                            view_load=%s, select_level=%s, readonly=%s ,required=%s, selectable=%s, relation_field=%s
                        WHERE
                            model=%s AND name=%s""", (
                                vals['model_id'], vals['field_description'], vals['ttype'],
                                vals['relation'], bool(vals['view_load']),
                                vals['select_level'], bool(vals['readonly']),bool(vals['required']),bool(vals['selectable']),vals['relation_field'],vals['model'], vals['name']
                            ))
                        continue
        cr.commit()

    def _auto_init(self, cr, context={}):
        self._field_create(cr, context)

    def __init__(self, cr):
        if not self._name and not hasattr(self, '_inherit'):
            name = type(self).__name__.split('.')[0]
            msg = "The class %s has to have a _name attribute" % name

            logger = netsvc.Logger()
            logger.notifyChannel('orm', netsvc.LOG_ERROR, msg )
            raise except_orm('ValueError', msg )

        if not self._description:
            self._description = self._name
        if not self._table:
            self._table = self._name.replace('.', '_')

    def browse(self, cr, uid, select, context=None, list_class=None, fields_process={}):
        """
        Fetch records as objects allowing to use dot notation to browse fields and relations

        :param cr: database cursor
        :param user: current user id
        :param select: id or list of ids
        :param context: context arguments, like lang, time zone
        :rtype: object or list of objects requested

        """
        if not context:
            context = {}
        self._list_class = list_class or browse_record_list
        cache = {}
        # need to accepts ints and longs because ids coming from a method
        # launched by button in the interface have a type long...
        if isinstance(select, (int, long)):
            return browse_record(cr, uid, select, self, cache, context=context, list_class=self._list_class, fields_process=fields_process)
        elif isinstance(select, list):
            return self._list_class([browse_record(cr, uid, id, self, cache, context=context, list_class=self._list_class, fields_process=fields_process) for id in select], context)
        else:
            return browse_null()

    def __export_row(self, cr, uid, row, fields, context=None):
        if context is None:
            context = {}

        def check_type(field_type):
            if field_type == 'float':
                return 0.0
            elif field_type == 'integer':
                return 0
            elif field_type == 'boolean':
                return False
            return ''

        def selection_field(in_field):
            col_obj = self.pool.get(in_field.keys()[0])
            if f[i] in col_obj._columns.keys():
                return  col_obj._columns[f[i]]
            elif f[i] in col_obj._inherits.keys():
                selection_field(col_obj._inherits)
            else:
                return False


        lines = []
        data = map(lambda x: '', range(len(fields)))
        done = []
        for fpos in range(len(fields)):
            f = fields[fpos]
            if f:
                r = row
                i = 0
                while i < len(f):
                    if f[i] == 'db_id':
                        r = r['id']
                    elif f[i] == 'id':
                        model_data = self.pool.get('ir.model.data')
                        data_ids = model_data.search(cr, uid, [('model','=',r._table_name),('res_id','=',r['id'])])
                        if len(data_ids):
                            d = model_data.read(cr, uid, data_ids, ['name','module'])[0]
                            if d['module']:
                                r = '%s.%s'%(d['module'],d['name'])
                            else:
                                r = d['name']
                        else:
                            break
                    else:
                        r = r[f[i]]
                        # To display external name of selection field when its exported
                        if not context.get('import_comp',False):# Allow external name only if its not import compatible
                            cols = False
                            if f[i] in self._columns.keys():
                                cols = self._columns[f[i]]
                            elif f[i] in self._inherit_fields.keys():
                                cols = selection_field(self._inherits)
                            if cols and cols._type == 'selection':
                                sel_list = cols.selection
                                if r and type(sel_list) == type([]):
                                    r = [x[1] for x in sel_list if r==x[0]]
                                    r = r and r[0] or False
                    if not r:
                        if f[i] in self._columns:
                            r = check_type(self._columns[f[i]]._type)
                        elif f[i] in self._inherit_fields:
                            r = check_type(self._inherit_fields[f[i]][2]._type)
                        data[fpos] = r
                        break
                    if isinstance(r, (browse_record_list, list)):
                        first = True
                        fields2 = map(lambda x: (x[:i+1]==f[:i+1] and x[i+1:]) \
                                or [], fields)
                        if fields2 in done:
                            break
                        done.append(fields2)
                        for row2 in r:
                            lines2 = self.__export_row(cr, uid, row2, fields2,
                                    context)
                            if first:
                                for fpos2 in range(len(fields)):
                                    if lines2 and lines2[0][fpos2]:
                                        data[fpos2] = lines2[0][fpos2]
                                if not data[fpos]:
                                    dt = ''
                                    for rr in r :
                                        if isinstance(rr.name, browse_record):
                                            rr = rr.name
                                        rr_name = self.pool.get(rr._table_name).name_get(cr, uid, [rr.id], context=context)
                                        rr_name = rr_name and rr_name[0] and rr_name[0][1] or ''
                                        dt += tools.ustr(rr_name or '') + ','
                                    data[fpos] = dt[:-1]
                                    break
                                lines += lines2[1:]
                                first = False
                            else:
                                lines += lines2
                        break
                    i += 1
                if i == len(f):
                    if isinstance(r, browse_record):
                        r = self.pool.get(r._table_name).name_get(cr, uid, [r.id], context=context)
                        r = r and r[0] and r[0][1] or ''
                    data[fpos] = tools.ustr(r or '')
        return [data] + lines

    def export_data(self, cr, uid, ids, fields_to_export, context=None):
        """
        Export fields for selected objects

        :param cr: database cursor
        :param uid: current user id
        :param ids: list of ids
        :param fields_to_export: list of fields
        :param context: context arguments, like lang, time zone, may contain import_comp(default: False) to make exported data compatible with import_data()
        :rtype: dictionary with a *datas* matrix

        This method is used when exporting data via client menu

        """
        if context is None:
            context = {}
        imp_comp = context.get('import_comp',False)
        cols = self._columns.copy()
        for f in self._inherit_fields:
            cols.update({f: self._inherit_fields[f][2]})
        fields_to_export = map(lambda x: x.split('/'), fields_to_export)
        fields_export = fields_to_export+[]
        warning = ''
        warning_fields = []
        for field in fields_export:
            if imp_comp and len(field)>1:
                warning_fields.append('/'.join(map(lambda x:x in cols and cols[x].string or x,field)))
            elif len (field) <=1:
                if imp_comp and cols.get(field and field[0],False):
                    if ((isinstance(cols[field[0]], fields.function) and not cols[field[0]].store) \
                                     or isinstance(cols[field[0]], fields.related)\
                                     or isinstance(cols[field[0]], fields.one2many)):
                        warning_fields.append('/'.join(map(lambda x:x in cols and cols[x].string or x,field)))
        datas = []
        if imp_comp and len(warning_fields):
            warning = 'Following columns cannot be exported since you select to be import compatible.\n%s' %('\n'.join(warning_fields))
            cr.rollback()
            return {'warning' : warning}
        for row in self.browse(cr, uid, ids, context):
            datas += self.__export_row(cr, uid, row, fields_to_export, context)
        return {'datas':datas}

    def import_data(self, cr, uid, fields, datas, mode='init', current_module='', noupdate=False, context=None, filename=None):
        """
        Import given data in given module

        :param cr: database cursor
        :param uid: current user id
        :param ids: list of ids
        :param fields: list of fields
        :param data: data to import
        :param mode: 'init' or 'update' for record creation
        :param current_module: module name
        :param noupdate: flag for record creation
        :param context: context arguments, like lang, time zone,
        :param filename: optional file to store partial import state for recovery
        :rtype: tuple

        This method is used when importing data via client menu

        """
        if not context:
            context = {}
        fields = map(lambda x: x.split('/'), fields)
        logger = netsvc.Logger()
        ir_model_data_obj = self.pool.get('ir.model.data')

        def _check_db_id(self, model_name, db_id):
            obj_model = self.pool.get(model_name)
            ids = obj_model.search(cr, uid, [('id','=',int(db_id))])
            if not len(ids):
                raise Exception(_("Database ID doesn't exist: %s : %s") %(model_name, db_id))
            return True

        def process_liness(self, datas, prefix, current_module, model_name, fields_def, position=0):
            line = datas[position]
            row = {}
            translate = {}
            todo = []
            warning = []
            data_id = False
            data_res_id = False
            is_xml_id = False
            is_db_id = False
            ir_model_data_obj = self.pool.get('ir.model.data')
            #
            # Import normal fields
            #
            for i in range(len(fields)):
                if i >= len(line):
                    raise Exception(_('Please check that all your lines have %d columns.') % (len(fields),))
                if not line[i]:
                    continue

                field = fields[i]
                if prefix and not prefix[0] in field:
                    continue

                if (len(field)==len(prefix)+1) and field[len(prefix)].endswith(':db_id'):
                        # Database ID
                        res = False
                        if line[i]:
                            field_name = field[0].split(':')[0]
                            model_rel =  fields_def[field_name]['relation']

                            if fields_def[field[len(prefix)][:-6]]['type']=='many2many':
                                res_id = []
                                for db_id in line[i].split(config.get('csv_internal_sep')):
                                    try:
                                        _check_db_id(self, model_rel, db_id)
                                        res_id.append(db_id)
                                    except Exception,e:
                                        warning += [tools.exception_to_unicode(e)]
                                        logger.notifyChannel("import", netsvc.LOG_ERROR,
                                                  tools.exception_to_unicode(e))
                                if len(res_id):
                                    res = [(6, 0, res_id)]
                            else:
                                try:
                                    _check_db_id(self, model_rel, line[i])
                                    res = line[i]
                                except Exception,e:
                                    warning += [tools.exception_to_unicode(e)]
                                    logger.notifyChannel("import", netsvc.LOG_ERROR,
                                              tools.exception_to_unicode(e))
                        row[field_name] = res or False
                        continue

                if (len(field)==len(prefix)+1) and field[len(prefix)].endswith(':id'):
                    res_id = False
                    if line[i]:
                        if fields_def[field[len(prefix)][:-3]]['type']=='many2many':
                            res_id = []
                            for word in line[i].split(config.get('csv_internal_sep')):
                                if '.' in word:
                                    module, xml_id = word.rsplit('.', 1)
                                else:
                                    module, xml_id = current_module, word
                                id = ir_model_data_obj._get_id(cr, uid, module,
                                        xml_id)
                                res_id2 = ir_model_data_obj.read(cr, uid, [id],
                                        ['res_id'])[0]['res_id']
                                if res_id2:
                                    res_id.append(res_id2)
                            if len(res_id):
                                res_id = [(6, 0, res_id)]
                        else:
                            if '.' in line[i]:
                                module, xml_id = line[i].rsplit('.', 1)
                            else:
                                module, xml_id = current_module, line[i]
                            record_id = ir_model_data_obj._get_id(cr, uid, module, xml_id)
                            ir_model_data = ir_model_data_obj.read(cr, uid, [record_id], ['res_id'])
                            if ir_model_data:
                                res_id = ir_model_data[0]['res_id']
                            else:
                                raise ValueError('No references to %s.%s' % (module, xml_id))
                    row[field[-1][:-3]] = res_id or False
                    continue
                if (len(field) == len(prefix)+1) and \
                        len(field[len(prefix)].split(':lang=')) == 2:
                    f, lang = field[len(prefix)].split(':lang=')
                    translate.setdefault(lang, {})[f]=line[i] or False
                    continue
                if (len(field) == len(prefix)+1) and \
                        (prefix == field[0:len(prefix)]):
                    if field[len(prefix)] == "id":
                        # XML ID
                        db_id = False
                        is_xml_id = data_id = line[i]
                        d =  data_id.split('.')
                        module = len(d)>1 and d[0] or ''
                        name = len(d)>1 and d[1] or d[0]
                        data_ids = ir_model_data_obj.search(cr, uid, [('module','=',module),('model','=',model_name),('name','=',name)])
                        if len(data_ids):
                            d = ir_model_data_obj.read(cr, uid, data_ids, ['res_id'])[0]
                            db_id = d['res_id']
                        if is_db_id and not db_id:
                           data_ids = ir_model_data_obj.search(cr, uid, [('module','=',module),('model','=',model_name),('res_id','=',is_db_id)])
                           if not len(data_ids):
                               ir_model_data_obj.create(cr, uid, {'module':module, 'model':model_name, 'name':name, 'res_id':is_db_id})
                               db_id = is_db_id
                        if is_db_id and int(db_id) != int(is_db_id):
                            warning += [_("Id is not the same than existing one: %s")%(is_db_id)]
                            logger.notifyChannel("import", netsvc.LOG_ERROR,
                                    _("Id is not the same than existing one: %s")%(is_db_id))
                        continue

                    if field[len(prefix)] == "db_id":
                        # Database ID
                        try:
                            _check_db_id(self, model_name, line[i])
                            data_res_id = is_db_id = int(line[i])
                        except Exception,e:
                            warning += [tools.exception_to_unicode(e)]
                            logger.notifyChannel("import", netsvc.LOG_ERROR,
                                      tools.exception_to_unicode(e))
                            continue
                        data_ids = ir_model_data_obj.search(cr, uid, [('model','=',model_name),('res_id','=',line[i])])
                        if len(data_ids):
                            d = ir_model_data_obj.read(cr, uid, data_ids, ['name','module'])[0]
                            data_id = d['name']
                            if d['module']:
                                data_id = '%s.%s'%(d['module'],d['name'])
                            else:
                                data_id = d['name']
                        if is_xml_id and not data_id:
                            data_id = is_xml_id
                        if is_xml_id and is_xml_id!=data_id:
                            warning += [_("Id is not the same than existing one: %s")%(line[i])]
                            logger.notifyChannel("import", netsvc.LOG_ERROR,
                                    _("Id is not the same than existing one: %s")%(line[i]))

                        continue
                    if fields_def[field[len(prefix)]]['type'] == 'integer':
                        res = line[i] and int(line[i])
                    elif fields_def[field[len(prefix)]]['type'] == 'boolean':
                        res = line[i].lower() not in ('0', 'false', 'off')
                    elif fields_def[field[len(prefix)]]['type'] == 'float':
                        res = line[i] and float(line[i])
                    elif fields_def[field[len(prefix)]]['type'] == 'selection':
                        res = False
                        if isinstance(fields_def[field[len(prefix)]]['selection'],
                                (tuple, list)):
                            sel = fields_def[field[len(prefix)]]['selection']
                        else:
                            sel = fields_def[field[len(prefix)]]['selection'](self,
                                    cr, uid, context)
                        for key, val in sel:
                            if line[i] in [tools.ustr(key),tools.ustr(val)]: #Acepting key or value for selection field
                                res = key
                                break
                        if line[i] and not res:
                            logger.notifyChannel("import", netsvc.LOG_WARNING,
                                    _("key '%s' not found in selection field '%s'") % \
                                            (line[i], field[len(prefix)]))

                            warning += [_("Key/value '%s' not found in selection field '%s'")%(line[i],field[len(prefix)])]

                    elif fields_def[field[len(prefix)]]['type']=='many2one':
                        res = False
                        if line[i]:
                            relation = fields_def[field[len(prefix)]]['relation']
                            res2 = self.pool.get(relation).name_search(cr, uid,
                                    line[i], [], operator='=', context=context)
                            res = (res2 and res2[0][0]) or False
                            if not res:
                                warning += [_("Relation not found: %s on '%s'")%(line[i],relation)]
                                logger.notifyChannel("import", netsvc.LOG_WARNING,
                                        _("Relation not found: %s on '%s'")%(line[i],relation))
                    elif fields_def[field[len(prefix)]]['type']=='many2many':
                        res = []
                        if line[i]:
                            relation = fields_def[field[len(prefix)]]['relation']
                            for word in line[i].split(config.get('csv_internal_sep')):
                                res2 = self.pool.get(relation).name_search(cr,
                                        uid, word, [], operator='=', context=context)
                                res3 = (res2 and res2[0][0]) or False
                                if not res3:
                                    warning += [_("Relation not found: %s on '%s'")%(line[i],relation)]
                                    logger.notifyChannel("import",
                                            netsvc.LOG_WARNING,
                                            _("Relation not found: %s on '%s'")%(line[i],relation))
                                else:
                                    res.append(res3)
                            if len(res):
                                res = [(6, 0, res)]
                    else:
                        res = line[i] or False
                    row[field[len(prefix)]] = res
                elif (prefix==field[0:len(prefix)]):
                    if field[0] not in todo:
                        todo.append(field[len(prefix)])
            #
            # Import one2many, many2many fields
            #
            nbrmax = 1
            for field in todo:
                relation_obj = self.pool.get(fields_def[field]['relation'])
                newfd = relation_obj.fields_get(
                        cr, uid, context=context)
                res = process_liness(self, datas, prefix + [field], current_module, relation_obj._name, newfd, position)
                (newrow, max2, w2, translate2, data_id2, data_res_id2) = res
                nbrmax = max(nbrmax, max2)
                warning = warning + w2
                reduce(lambda x, y: x and y, newrow)
                row[field] = (reduce(lambda x, y: x or y, newrow.values()) and \
                        [(0, 0, newrow)]) or []
                i = max2
                while (position+i)<len(datas):
                    ok = True
                    for j in range(len(fields)):
                        field2 = fields[j]
                        if (len(field2) <= (len(prefix)+1)) and datas[position+i][j]:
                            ok = False
                    if not ok:
                        break

                    (newrow, max2, w2, translate2, data_id2, data_res_id2) = process_liness(
                            self, datas, prefix+[field], current_module, relation_obj._name, newfd, position+i)
                    warning = warning+w2
                    if reduce(lambda x, y: x or y, newrow.values()):
                        row[field].append((0, 0, newrow))
                    i += max2
                    nbrmax = max(nbrmax, i)

            if len(prefix)==0:
                for i in range(max(nbrmax, 1)):
                    #if datas:
                    datas.pop(0)
            result = (row, nbrmax, warning, translate, data_id, data_res_id)
            return result

        fields_def = self.fields_get(cr, uid, context=context)
        done = 0

        initial_size = len(datas)
        if config.get('import_partial', False) and filename:
            data = pickle.load(file(config.get('import_partial')))
            original_value =  data.get(filename, 0)
        counter = 0
        while len(datas):
            counter += 1
            res = {}
            #try:
            (res, other, warning, translate, data_id, res_id) = \
                    process_liness(self, datas, [], current_module, self._name, fields_def)
            if len(warning):
                cr.rollback()
                return (-1, res, 'Line ' + str(counter) +' : ' + '!\n'.join(warning), '')

            try:
                id = ir_model_data_obj._update(cr, uid, self._name,
                     current_module, res, xml_id=data_id, mode=mode,
                     noupdate=noupdate, res_id=res_id, context=context)
            except Exception, e:
                import psycopg2
                import osv
                cr.rollback()
                if isinstance(e,psycopg2.IntegrityError):
                    msg= _('Insertion Failed! ')
                    for key in self.pool._sql_error.keys():
                        if key in e[0]:
                            msg = self.pool._sql_error[key]
                            break
                    return (-1, res, 'Line ' + str(counter) +' : ' + msg, '' )
                if isinstance(e, osv.orm.except_orm ):
                    msg = _('Insertion Failed! ' + e[1])
                    return (-1, res, 'Line ' + str(counter) +' : ' + msg, '' )
                #Raising Uncaught exception
                return (-1, res, 'Line ' + str(counter) +' : ' + str(e), '' )

            for lang in translate:
                context2 = context.copy()
                context2['lang'] = lang
                self.write(cr, uid, [id], translate[lang], context2)
            if config.get('import_partial', False) and filename and (not (counter%100)) :
                data = pickle.load(file(config.get('import_partial')))
                data[filename] = initial_size - len(datas) + original_value
                pickle.dump(data, file(config.get('import_partial'),'wb'))
                if context.get('defer_parent_store_computation'):
                    self._parent_store_compute(cr)
                cr.commit()

            #except Exception, e:
            #    logger.notifyChannel("import", netsvc.LOG_ERROR, e)
            #    cr.rollback()
            #    try:
            #        return (-1, res, e[0], warning)
            #    except:
            #        return (-1, res, e[0], '')
            done += 1
        #
        # TODO: Send a request with the result and multi-thread !
        #
        if context.get('defer_parent_store_computation'):
            self._parent_store_compute(cr)
        return (done, 0, 0, 0)

    def read(self, cr, user, ids, fields=None, context=None, load='_classic_read'):
        raise NotImplementedError(_('The read method is not implemented on this object !'))

    def get_invalid_fields(self,cr,uid):
        return list(self._invalids)

    def _validate(self, cr, uid, ids, context=None):
        context = context or {}
        lng = context.get('lang', False) or 'en_US'
        trans = self.pool.get('ir.translation')
        error_msgs = []
        for constraint in self._constraints:
            fun, msg, fields = constraint
            if not fun(self, cr, uid, ids):
                # Check presence of __call__ directly instead of using
                # callable() because it will be deprecated as of Python 3.0
                if hasattr(msg, '__call__'):
                    txt_msg, params = msg(self, cr, uid, ids)
                    tmp_msg = trans._get_source(cr, uid, self._name, 'constraint', lng, source=txt_msg) or txt_msg
                    translated_msg = tmp_msg % params
                else:
                    translated_msg = trans._get_source(cr, uid, self._name, 'constraint', lng, source=msg) or msg
                error_msgs.append(
                        _("Error occurred while validating the field(s) %s: %s") % (','.join(fields), translated_msg)
                )
                self._invalids.update(fields)
        if error_msgs:
            cr.rollback()
            raise except_orm('ValidateError', '\n'.join(error_msgs))
        else:
            self._invalids.clear()

    def default_get(self, cr, uid, fields_list, context=None):
        """
        Returns default values for the fields in fields_list.

        :param fields_list: list of fields to get the default values for (example ['field1', 'field2',])
        :type fields_list: list
        :param context: usual context dictionary - it may contains keys in the form ``default_XXX``,
                        where XXX is a field name to set or override a default value.
        :return: dictionary of the default values (set on the object model class, through user preferences, or in the context)
        """
        # trigger view init hook
        self.view_init(cr, uid, fields_list, context)

        if not context:
            context = {}
        defaults = {}

        # get the default values for the inherited fields
        for t in self._inherits.keys():
            defaults.update(self.pool.get(t).default_get(cr, uid, fields_list,
                context))

        # get the default values defined in the object
        for f in fields_list:
            if f in self._defaults:
                if callable(self._defaults[f]):
                    defaults[f] = self._defaults[f](self, cr, uid, context)
                else:
                    defaults[f] = self._defaults[f]

            fld_def = ((f in self._columns) and self._columns[f]) \
                    or ((f in self._inherit_fields) and self._inherit_fields[f][2]) \
                    or False

            if isinstance(fld_def, fields.property):
                property_obj = self.pool.get('ir.property')
                prop_value = property_obj.get(cr, uid, f, self._name, context=context)
                if prop_value:
                    if isinstance(prop_value, (browse_record, browse_null)):
                        defaults[f] = prop_value.id
                    else:
                        defaults[f] = prop_value
                else:
                    if f not in defaults:
                        defaults[f] = False

        # get the default values set by the user and override the default
        # values defined in the object
        ir_values_obj = self.pool.get('ir.values')
        res = ir_values_obj.get(cr, uid, 'default', False, [self._name])
        for id, field, field_value in res:
            if field in fields_list:
                fld_def = (field in self._columns) and self._columns[field] or self._inherit_fields[field][2]
                if fld_def._type in ('many2one', 'one2one'):
                    obj = self.pool.get(fld_def._obj)
                    if not obj.search(cr, uid, [('id', '=', field_value or False)]):
                        continue
                if fld_def._type in ('many2many'):
                    obj = self.pool.get(fld_def._obj)
                    field_value2 = []
                    for i in range(len(field_value)):
                        if not obj.search(cr, uid, [('id', '=',
                            field_value[i])]):
                            continue
                        field_value2.append(field_value[i])
                    field_value = field_value2
                if fld_def._type in ('one2many'):
                    obj = self.pool.get(fld_def._obj)
                    field_value2 = []
                    for i in range(len(field_value)):
                        field_value2.append({})
                        for field2 in field_value[i]:
                            if field2 in obj._columns.keys() and obj._columns[field2]._type in ('many2one', 'one2one'):
                                obj2 = self.pool.get(obj._columns[field2]._obj)
                                if not obj2.search(cr, uid,
                                        [('id', '=', field_value[i][field2])]):
                                    continue
                            elif field2 in obj._inherit_fields.keys() and obj._inherit_fields[field2][2]._type in ('many2one', 'one2one'):
                                obj2 = self.pool.get(obj._inherit_fields[field2][2]._obj)
                                if not obj2.search(cr, uid,
                                        [('id', '=', field_value[i][field2])]):
                                    continue
                            # TODO add test for many2many and one2many
                            field_value2[i][field2] = field_value[i][field2]
                    field_value = field_value2
                defaults[field] = field_value

        # get the default values from the context
        for key in context or {}:
            if key.startswith('default_') and (key[8:] in fields_list):
                defaults[key[8:]] = context[key]
        return defaults


    def perm_read(self, cr, user, ids, context=None, details=True):
        raise NotImplementedError(_('The perm_read method is not implemented on this object !'))

    def unlink(self, cr, uid, ids, context=None):
        raise NotImplementedError(_('The unlink method is not implemented on this object !'))

    def write(self, cr, user, ids, vals, context=None):
        raise NotImplementedError(_('The write method is not implemented on this object !'))

    def create(self, cr, user, vals, context=None):
        raise NotImplementedError(_('The create method is not implemented on this object !'))

    def fields_get_keys(self, cr, user, context=None):
        res = self._columns.keys()
        for parent in self._inherits:
            res.extend(self.pool.get(parent).fields_get_keys(cr, user, context))
        return res

    # returns the definition of each field in the object
    # the optional fields parameter can limit the result to some fields
    def fields_get(self, cr, user, allfields=None, context=None, write_access=True):
        if context is None:
            context = {}
        res = {}
        translation_obj = self.pool.get('ir.translation')
        for parent in self._inherits:
            res.update(self.pool.get(parent).fields_get(cr, user, allfields, context))

        if self._columns.keys():
            for f in self._columns.keys():
                if allfields and f not in allfields:
                    continue
                res[f] = {'type': self._columns[f]._type}
                # This additional attributes for M2M and function field is added
                # because we need to display tooltip with this additional information
                # when client is started in debug mode.
                if isinstance(self._columns[f], fields.function):
                    res[f]['function'] = self._columns[f]._fnct and self._columns[f]._fnct.func_name or False
                    res[f]['store'] = self._columns[f].store
                    if isinstance(self._columns[f].store, dict):
                        res[f]['store'] = str(self._columns[f].store)
                    res[f]['fnct_search'] = self._columns[f]._fnct_search and self._columns[f]._fnct_search.func_name or False
                    res[f]['fnct_inv'] = self._columns[f]._fnct_inv and self._columns[f]._fnct_inv.func_name or False
                    res[f]['fnct_inv_arg'] = self._columns[f]._fnct_inv_arg or False
                    res[f]['func_obj'] = self._columns[f]._obj or False
                    res[f]['func_method'] = self._columns[f]._method
                if isinstance(self._columns[f], fields.many2many):
                    res[f]['related_columns'] = list((self._columns[f]._id1, self._columns[f]._id2))
                    res[f]['third_table'] = self._columns[f]._rel
                for arg in ('string', 'readonly', 'states', 'size', 'required', 'group_operator',
                        'change_default', 'translate', 'help', 'select', 'selectable'):
                    if getattr(self._columns[f], arg):
                        res[f][arg] = getattr(self._columns[f], arg)
                if not write_access:
                    res[f]['readonly'] = True
                    res[f]['states'] = {}
                for arg in ('digits', 'invisible','filters'):
                    if getattr(self._columns[f], arg, None):
                        res[f][arg] = getattr(self._columns[f], arg)

                res_trans = translation_obj._get_source(cr, user, self._name + ',' + f, 'field', context.get('lang', False) or 'en_US', self._columns[f].string)
                if res_trans:
                    res[f]['string'] = res_trans
                help_trans = translation_obj._get_source(cr, user, self._name + ',' + f, 'help', context.get('lang', False) or 'en_US')
                if help_trans:
                    res[f]['help'] = help_trans

                if hasattr(self._columns[f], 'selection'):
                    if isinstance(self._columns[f].selection, (tuple, list)):
                        sel = self._columns[f].selection
                        # translate each selection option
                        sel2 = []
                        for (key, val) in sel:
                            val2 = None
                            if val:
                                val2 = translation_obj._get_source(cr, user, self._name + ',' + f, 'selection', context.get('lang', False) or 'en_US', val)
                            sel2.append((key, val2 or val))
                        sel = sel2
                        res[f]['selection'] = sel
                    else:
                        # call the 'dynamic selection' function
                        res[f]['selection'] = self._columns[f].selection(self, cr,
                                user, context)
                if res[f]['type'] in ('one2many', 'many2many', 'many2one', 'one2one'):
                    res[f]['relation'] = self._columns[f]._obj
                    res[f]['domain'] = self._columns[f]._domain
                    res[f]['context'] = self._columns[f]._context
        else:
            #TODO : read the fields from the database
            pass

        if allfields:
            # filter out fields which aren't in the fields list
            for r in res.keys():
                if r not in allfields:
                    del res[r]
        return res

    #
    # Overload this method if you need a window title which depends on the context
    #
    def view_header_get(self, cr, user, view_id=None, view_type='form', context=None):
        return False

    def __view_look_dom(self, cr, user, node, view_id, context=None):
        if not context:
            context = {}
        result = False
        fields = {}
        childs = True

        def encode(s):
            if isinstance(s, unicode):
                return s.encode('utf8')
            return s

        # return True if node can be displayed to current user
        def check_group(node):
            if node.get('groups'):
                groups = node.get('groups').split(',')
                access_pool = self.pool.get('ir.model.access')
                can_see = any(access_pool.check_groups(cr, user, group) for group in groups)
                if not can_see:
                    node.set('invisible', '1')
                    if 'attrs' in node.attrib:
                        del(node.attrib['attrs']) #avoid making field visible later
                del(node.attrib['groups'])
                return can_see
            else:
                return True

        if node.tag in ('field', 'node', 'arrow'):
            if node.get('object'):
                attrs = {}
                views = {}
                xml = "<form>"
                for f in node:
                    if f.tag in ('field'):
                        xml += etree.tostring(f, encoding="utf-8")
                xml += "</form>"
                new_xml = etree.fromstring(encode(xml))
                ctx = context.copy()
                ctx['base_model_name'] = self._name
                xarch, xfields = self.pool.get(node.get('object',False)).__view_look_dom_arch(cr, user, new_xml, view_id, ctx)
                views[str(f.tag)] = {
                    'arch': xarch,
                    'fields': xfields
                }
                attrs = {'views': views}
                view = False
                fields = views.get('field',False) and views['field'].get('fields',False)
            if node.get('name'):
                attrs = {}
                try:
                    if node.get('name') in self._columns:
                        column = self._columns[node.get('name')]
                    else:
                        column = self._inherit_fields[node.get('name')][2]
                except:
                    column = False

                if column:
                    relation = self.pool.get(column._obj)

                    childs = False
                    views = {}
                    for f in node:
                        if f.tag in ('form', 'tree', 'graph'):
                            node.remove(f)
                            ctx = context.copy()
                            ctx['base_model_name'] = self._name
                            xarch, xfields = relation.__view_look_dom_arch(cr, user, f, view_id, ctx)
                            views[str(f.tag)] = {
                                'arch': xarch,
                                'fields': xfields
                            }
                    attrs = {'views': views}
                    if node.get('widget') and node.get('widget') == 'selection':
                        # Prepare the cached selection list for the client. This needs to be
                        # done even when the field is invisible to the current user, because
                        # other events could need to change its value to any of the selectable ones
                        # (such as on_change events, refreshes, etc.)

                        # If domain and context are strings, we keep them for client-side, otherwise
                        # we evaluate them server-side to consider them when generating the list of
                        # possible values
                        # TODO: find a way to remove this hack, by allow dynamic domains
                        dom = []
                        if column._domain and not isinstance(column._domain, basestring):
                            dom = column._domain
                        dom += eval(node.get('domain','[]'), {'uid':user, 'time':time})
                        search_context = dict(context)
                        if column._context and not isinstance(column._context, basestring):
                            search_context.update(column._context)
                        attrs['selection'] = relation._name_search(cr, user, '', dom, context=search_context, limit=None, name_get_uid=1)
                        if (node.get('required') and not int(node.get('required'))) or not column.required:
                            attrs['selection'].append((False,''))
                fields[node.get('name')] = attrs

        elif node.tag in ('form', 'tree'):
            result = self.view_header_get(cr, user, False, node.tag, context)
            if result:
                node.set('string', result)

        elif node.tag == 'calendar':
            for additional_field in ('date_start', 'date_delay', 'date_stop', 'color'):
                if node.get(additional_field):
                    fields[node.get(additional_field)] = {}

        if 'groups' in node.attrib:
            check_group(node)

        # translate view
        if ('lang' in context) and not result:
            if node.get('string'):
                trans = self.pool.get('ir.translation')._get_source(cr, user, self._name, 'view', context['lang'], node.get('string').encode('utf8'))
                if not trans and ('base_model_name' in context):
                    trans = self.pool.get('ir.translation')._get_source(cr, user, context['base_model_name'], 'view', context['lang'], node.get('string').encode('utf8'))
                if trans:
                    node.set('string', trans)
            if node.get('sum'):
                trans = self.pool.get('ir.translation')._get_source(cr, user, self._name, 'view', context['lang'], node.get('sum').encode('utf8'))
                if trans:
                    node.set('sum', trans)

        if childs:
            for f in node:
                fields.update(self.__view_look_dom(cr, user, f, view_id, context))

        return fields

    def __view_look_dom_arch(self, cr, user, node, view_id, context=None):
        fields_def = self.__view_look_dom(cr, user, node, view_id, context=context)

        rolesobj = self.pool.get('res.roles')
        usersobj = self.pool.get('res.users')

        buttons = (n for n in node.getiterator('button') if n.get('type') != 'object')
        for button in buttons:
            can_click = True
            if user != 1:   # admin user has all roles
                user_roles = usersobj.read(cr, user, [user], ['roles_id'])[0]['roles_id']
                # TODO handle the case of more than one workflow for a model
                cr.execute("""SELECT DISTINCT t.role_id
                                FROM wkf
                          INNER JOIN wkf_activity a ON a.wkf_id = wkf.id
                          INNER JOIN wkf_transition t ON (t.act_to = a.id)
                               WHERE wkf.osv = %s
                                 AND t.signal = %s
                           """, (self._name, button.get('name'),))
                roles = cr.fetchall()

                # draft -> valid = signal_next (role X)
                # draft -> cancel = signal_cancel (no role)
                #
                # valid -> running = signal_next (role Y)
                # valid -> cancel = signal_cancel (role Z)
                #
                # running -> done = signal_next (role Z)
                # running -> cancel = signal_cancel (role Z)

                # As we don't know the object state, in this scenario,
                #   the button "signal_cancel" will be always shown as there is no restriction to cancel in draft
                #   the button "signal_next" will be show if the user has any of the roles (X Y or Z)
                # The verification will be made later in workflow process...
                if roles:
                    can_click = any((not role) or rolesobj.check(cr, user, user_roles, role) for (role,) in roles)

            button.set('readonly', str(int(not can_click)))

        arch = etree.tostring(node, encoding="utf-8").replace('\t', '')

        fields={}
        if node.tag=='diagram':
            if node.getchildren()[0].tag=='node':
               node_fields=self.pool.get(node.getchildren()[0].get('object')).fields_get(cr, user, fields_def.keys(), context)
            if node.getchildren()[1].tag=='arrow':
               arrow_fields = self.pool.get(node.getchildren()[1].get('object')).fields_get(cr, user, fields_def.keys(), context)
            for key,value in node_fields.items():
                fields[key]=value
            for key,value in arrow_fields.items():
                fields[key]=value
        else:
            fields = self.fields_get(cr, user, fields_def.keys(), context)
        for field in fields_def:
            if field == 'id':
                # sometime, the view may containt the (invisible) field 'id' needed for a domain (when 2 objects have cross references)
                fields['id'] = {'readonly': True, 'type': 'integer', 'string': 'ID'}
            elif field in fields:
                fields[field].update(fields_def[field])
            else:
                cr.execute('select name, model from ir_ui_view where (id=%s or inherit_id=%s) and arch like %s', (view_id, view_id, '%%%s%%' % field))
                res = cr.fetchall()[:]
                model = res[0][1]
                res.insert(0, ("Can't find field '%s' in the following view parts composing the view of object model '%s':" % (field, model), None))
                msg = "\n * ".join([r[0] for r in res])
                msg += "\n\nEither you wrongly customised this view, or some modules bringing those views are not compatible with your current data model"
                netsvc.Logger().notifyChannel('orm', netsvc.LOG_ERROR, msg)
                raise except_orm('View error', msg)
        return arch, fields

    def __get_default_calendar_view(self):
        """Generate a default calendar view (For internal use only).
        """

        arch = ('<?xml version="1.0" encoding="utf-8"?>\n'
                '<calendar string="%s"') % (self._description)

        if (self._date_name not in self._columns):
                date_found = False
                for dt in ['date','date_start','x_date','x_date_start']:
                    if dt in self._columns:
                        self._date_name = dt
                        date_found = True
                        break

                if not date_found:
                    raise except_orm(_('Invalid Object Architecture!'),_("Insufficient fields for Calendar View!"))

        if self._date_name:
            arch +=' date_start="%s"' % (self._date_name)

        for color in ["user_id","partner_id","x_user_id","x_partner_id"]:
            if color in self._columns:
                arch += ' color="' + color + '"'
                break

        dt_stop_flag = False

        for dt_stop in ["date_stop","date_end","x_date_stop","x_date_end"]:
            if dt_stop in self._columns:
                arch += ' date_stop="' + dt_stop + '"'
                dt_stop_flag = True
                break

        if not dt_stop_flag:
            for dt_delay in ["date_delay","planned_hours","x_date_delay","x_planned_hours"]:
               if dt_delay in self._columns:
                   arch += ' date_delay="' + dt_delay + '"'
                   break

        arch += ('>\n'
                 '  <field name="%s"/>\n'
                 '</calendar>') % (self._rec_name)

        return arch

    def __get_default_search_view(self, cr, uid, context={}):

        def encode(s):
            if isinstance(s, unicode):
                return s.encode('utf8')
            return s

        view = self.fields_view_get(cr, uid, False, 'form', context)

        root = etree.fromstring(encode(view['arch']))
        res = etree.XML("""<search string="%s"></search>""" % root.get("string", ""))
        node = etree.Element("group")
        res.append(node)

        fields = root.xpath("//field[@select=1]")
        for field in fields:
            node.append(field)

        return etree.tostring(res, encoding="utf-8").replace('\t', '')

    #
    # if view_id, view_type is not required
    #
    def fields_view_get(self, cr, user, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Get the detailed composition of the requested view like fields, model, view architecture

        :param cr: database cursor
        :param user: current user id
        :param view_id: id of the view or None
        :param view_type: type of the view to return if view_id is None ('form', tree', ...)
        :param context: context arguments, like lang, time zone
        :param toolbar: true to include contextual actions
        :param submenu: example (portal_project module)
        :return: dictionary describing the composition of the requested view (including inherited views and extensions)
        :raise AttributeError:
                            * if the inherited view has unknown position to work with other than 'before', 'after', 'inside', 'replace'
                            * if some tag other than 'position' is found in parent view
        :raise Invalid ArchitectureError: if there is view type other than form, tree, calendar, search etc defined on the structure

        """
        if not context:
            context = {}

        def encode(s):
            if isinstance(s, unicode):
                return s.encode('utf8')
            return s

        def _inherit_apply(src, inherit):
            def _find(node, node2):
                if node2.tag == 'xpath':
                    res = node.xpath(node2.get('expr'))
                    if res:
                        return res[0]
                    else:
                        return None
                else:
                    for n in node.getiterator(node2.tag):
                        res = True
                        for attr in node2.attrib:
                            if attr == 'position':
                                continue
                            if n.get(attr):
                                if n.get(attr) == node2.get(attr):
                                    continue
                            res = False
                        if res:
                            return n
                return None

            # End: _find(node, node2)

            doc_dest = etree.fromstring(encode(inherit))
            toparse = [ doc_dest ]

            while len(toparse):
                node2 = toparse.pop(0)
                if node2.tag == 'data':
                    toparse += [ c for c in doc_dest ]
                    continue
                node = _find(src, node2)
                if node is not None:
                    pos = 'inside'
                    if node2.get('position'):
                        pos = node2.get('position')
                    if pos == 'replace':
                        parent = node.getparent()
                        if parent is None:
                            src = copy.deepcopy(node2[0])
                        else:
                            for child in node2:
                                node.addprevious(child)
                            node.getparent().remove(node)
                    elif pos == 'attributes':
                        for child in node2.getiterator('attribute'):
                            attribute = (child.get('name'), child.text and child.text.encode('utf8') or None)
                            if attribute[1]:
                                node.set(attribute[0], attribute[1])
                            else:
                                del(node.attrib[attribute[0]])
                    else:
                        sib = node.getnext()
                        for child in node2:
                            if pos == 'inside':
                                node.append(child)
                            elif pos == 'after':
                                if sib is None:
                                    node.addnext(child)
                                else:
                                    sib.addprevious(child)
                            elif pos == 'before':
                                node.addprevious(child)
                            else:
                                raise AttributeError(_('Unknown position in inherited view %s !') % pos)
                else:
                    attrs = ''.join([
                        ' %s="%s"' % (attr, node2.get(attr))
                        for attr in node2.attrib
                        if attr != 'position'
                    ])
                    tag = "<%s%s>" % (node2.tag, attrs)
                    raise AttributeError(_("Couldn't find tag '%s' in parent view !") % tag)
            return src
        # End: _inherit_apply(src, inherit)

        result = {'type': view_type, 'model': self._name}

        ok = True
        model = True
        sql_res = False
        while ok:
            view_ref = context.get(view_type + '_view_ref', False)
            if view_ref and not view_id:
                if '.' in view_ref:
                    module, view_ref = view_ref.split('.', 1)
                    cr.execute("SELECT res_id FROM ir_model_data WHERE model='ir.ui.view' AND module=%s AND name=%s", (module, view_ref))
                    view_ref_res = cr.fetchone()
                    if view_ref_res:
                        view_id = view_ref_res[0]

            if view_id:
                query = "SELECT arch,name,field_parent,id,type,inherit_id FROM ir_ui_view WHERE id=%s"
                params = (view_id,)
                if model:
                    query += " AND model=%s"
                    params += (self._name,)
                cr.execute(query, params)
            else:
                cr.execute('''SELECT
                        arch,name,field_parent,id,type,inherit_id
                    FROM
                        ir_ui_view
                    WHERE
                        model=%s AND
                        type=%s AND
                        inherit_id IS NULL
                    ORDER BY priority''', (self._name, view_type))
            sql_res = cr.fetchone()

            if not sql_res:
                break

            ok = sql_res[5]
            view_id = ok or sql_res[3]
            model = False

        # if a view was found
        if sql_res:
            result['type'] = sql_res[4]
            result['view_id'] = sql_res[3]
            result['arch'] = sql_res[0]

            def _inherit_apply_rec(result, inherit_id):
                # get all views which inherit from (ie modify) this view
                cr.execute('select arch,id from ir_ui_view where inherit_id=%s and model=%s order by priority', (inherit_id, self._name))
                sql_inherit = cr.fetchall()
                for (inherit, id) in sql_inherit:
                    result = _inherit_apply(result, inherit)
                    result = _inherit_apply_rec(result, id)
                return result

            inherit_result = etree.fromstring(encode(result['arch']))
            result['arch'] = _inherit_apply_rec(inherit_result, sql_res[3])

            result['name'] = sql_res[1]
            result['field_parent'] = sql_res[2] or False
        else:

            # otherwise, build some kind of default view
            if view_type == 'form':
                res = self.fields_get(cr, user, context=context)
                xml = '<?xml version="1.0" encoding="utf-8"?> ' \
                     '<form string="%s">' % (self._description,)
                for x in res:
                    if res[x]['type'] not in ('one2many', 'many2many'):
                        xml += '<field name="%s"/>' % (x,)
                        if res[x]['type'] == 'text':
                            xml += "<newline/>"
                xml += "</form>"

            elif view_type == 'tree':
                _rec_name = self._rec_name
                if _rec_name not in self._columns:
                    _rec_name = self._columns.keys()[0]
                xml = '<?xml version="1.0" encoding="utf-8"?>' \
                       '<tree string="%s"><field name="%s"/></tree>' \
                       % (self._description, self._rec_name)

            elif view_type == 'calendar':
                xml = self.__get_default_calendar_view()

            elif view_type == 'search':
                xml = self.__get_default_search_view(cr, user, context)

            else:
                xml = '<?xml version="1.0"?>' # what happens here, graph case?
                raise except_orm(_('Invalid Architecture!'),_("There is no view of type '%s' defined for the structure!") % view_type)
            result['arch'] = etree.fromstring(encode(xml))
            result['name'] = 'default'
            result['field_parent'] = False
            result['view_id'] = 0

        xarch, xfields = self.__view_look_dom_arch(cr, user, result['arch'], view_id, context=context)
        result['arch'] = xarch
        result['fields'] = xfields

        if submenu:
            if context and context.get('active_id',False):
                data_menu = self.pool.get('ir.ui.menu').browse(cr, user, context['active_id'], context).action
                if data_menu:
                    act_id = data_menu.id
                    if act_id:
                        data_action = self.pool.get('ir.actions.act_window').browse(cr, user, [act_id], context)[0]
                        result['submenu'] = getattr(data_action,'menus', False)
        if toolbar:
            def clean(x):
                x = x[2]
                for key in ('report_sxw_content', 'report_rml_content',
                        'report_sxw', 'report_rml',
                        'report_sxw_content_data', 'report_rml_content_data'):
                    if key in x:
                        del x[key]
                return x
            ir_values_obj = self.pool.get('ir.values')
            resprint = ir_values_obj.get(cr, user, 'action',
                    'client_print_multi', [(self._name, False)], False,
                    context)
            resaction = ir_values_obj.get(cr, user, 'action',
                    'client_action_multi', [(self._name, False)], False,
                    context)

            resrelate = ir_values_obj.get(cr, user, 'action',
                    'client_action_relate', [(self._name, False)], False,
                    context)
            resprint = map(clean, resprint)
            resaction = map(clean, resaction)
            resaction = filter(lambda x: not x.get('multi', False), resaction)
            resprint = filter(lambda x: not x.get('multi', False), resprint)
            resrelate = map(lambda x: x[2], resrelate)

            for x in resprint+resaction+resrelate:
                x['string'] = x['name']

            result['toolbar'] = {
                'print': resprint,
                'action': resaction,
                'relate': resrelate
            }
        if result['type']=='form' and result['arch'].count("default_focus")>1:
                msg = "Form View contain more than one default_focus attribute"
                netsvc.Logger().notifyChannel('orm', netsvc.LOG_ERROR, msg)
                raise except_orm('View Error !',msg)
        return result

    _view_look_dom_arch = __view_look_dom_arch

    def search_count(self, cr, user, args, context=None):
        if not context:
            context = {}
        res = self.search(cr, user, args, context=context, count=True)
        if isinstance(res, list):
            return len(res)
        return res

    def search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False):
        """
        Search for records based on a search domain.

        :param cr: database cursor
        :param user: current user id
        :param args: list of tuples specifying the search domain [('field_name', 'operator', value), ...]. Pass an empty list to match all records.
        :param offset: optional number of results to skip in the returned values (default: 0)
        :param limit: optional max number of records to return (default: **None**)
        :param order: optional columns to sort by (default: self._order=id )
        :param context: optional context arguments, like lang, time zone
        :type context: dictionary
        :param count: optional (default: **False**), if **True**, returns only the number of records matching the criteria, not their ids
        :return: id or list of ids of records matching the criteria
        :rtype: integer or list of integers
        :raise AccessError: * if user tries to bypass access rules for read on the requested object.

        **Expressing a search domain (args)**

        Each tuple in the search domain needs to have 3 elements, in the form: **('field_name', 'operator', value)**, where:

            * **field_name** must be a valid name of field of the object model, possibly following many-to-one relationships using dot-notation, e.g 'street' or 'partner_id.country' are valid values.
            * **operator** must be a string with a valid comparison operator from this list: ``=, !=, >, >=, <, <=, like, ilike, in, not in, child_of, parent_left, parent_right``
              The semantics of most of these operators are obvious.
              The ``child_of`` operator will look for records who are children or grand-children of a given record,
              according to the semantics of this model (i.e following the relationship field named by
              ``self._parent_name``, by default ``parent_id``.
            * **value** must be a valid value to compare with the values of **field_name**, depending on its type.

        Domain criteria can be combined using 3 logical operators than can be added between tuples:  '**&**' (logical AND, default), '**|**' (logical OR), '**!**' (logical NOT).
        These are **prefix** operators and the arity of the '**&**' and '**|**' operator is 2, while the arity of the '**!**' is just 1.
        Be very careful about this when you combine them the first time.

        Here is an example of searching for Partners named *ABC* from Belgium and Germany whose language is not english ::

            [('name','=','ABC'),'!',('language.code','=','en_US'),'|',('country_id.code','=','be'),('country_id.code','=','de'))

        The '&' is omitted as it is the default, and of course we could have used '!=' for the language, but what this domain really represents is::

            (name is 'ABC' AND (language is NOT english) AND (country is Belgium OR Germany))

        """
        return self._search(cr, user, args, offset=offset, limit=limit, order=order, context=context, count=count)

    def _search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False, access_rights_uid=None):
        """
        Private implementation of search() method, allowing specifying the uid to use for the access right check. 
        This is useful for example when filling in the selection list for a drop-down and avoiding access rights errors,
        by specifying ``access_rights_uid=1`` to bypass access rights check, but not ir.rules!
        
        :param access_rights_uid: optional user ID to use when checking access rights
                                  (not for ir.rules, this is only for ir.model.access)
        """
        raise NotImplementedError(_('The search method is not implemented on this object !'))

    def name_get(self, cr, user, ids, context=None):
        raise NotImplementedError(_('The name_get method is not implemented on this object !'))

    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        raise NotImplementedError(_('The name_search method is not implemented on this object !'))

    def copy(self, cr, uid, id, default=None, context=None):
        raise NotImplementedError(_('The copy method is not implemented on this object !'))

    def exists(self, cr, uid, id, context=None):
        raise NotImplementedError(_('The exists method is not implemented on this object !'))

    def read_string(self, cr, uid, id, langs, fields=None, context=None):
        res = {}
        res2 = {}
        self.pool.get('ir.model.access').check(cr, uid, 'ir.translation', 'read', context=context)
        if not fields:
            fields = self._columns.keys() + self._inherit_fields.keys()
        #FIXME: collect all calls to _get_source into one SQL call.
        for lang in langs:
            res[lang] = {'code': lang}
            for f in fields:
                if f in self._columns:
                    res_trans = self.pool.get('ir.translation')._get_source(cr, uid, self._name+','+f, 'field', lang)
                    if res_trans:
                        res[lang][f] = res_trans
                    else:
                        res[lang][f] = self._columns[f].string
        for table in self._inherits:
            cols = intersect(self._inherit_fields.keys(), fields)
            res2 = self.pool.get(table).read_string(cr, uid, id, langs, cols, context)
        for lang in res2:
            if lang in res:
                res[lang]['code'] = lang
            for f in res2[lang]:
                res[lang][f] = res2[lang][f]
        return res

    def write_string(self, cr, uid, id, langs, vals, context=None):
        self.pool.get('ir.model.access').check(cr, uid, 'ir.translation', 'write', context=context)
        #FIXME: try to only call the translation in one SQL
        for lang in langs:
            for field in vals:
                if field in self._columns:
                    src = self._columns[field].string
                    self.pool.get('ir.translation')._set_ids(cr, uid, self._name+','+field, 'field', lang, [0], vals[field], src)
        for table in self._inherits:
            cols = intersect(self._inherit_fields.keys(), vals)
            if cols:
                self.pool.get(table).write_string(cr, uid, id, langs, vals, context)
        return True

    def _check_removed_columns(self, cr, log=False):
        raise NotImplementedError()

    def _add_missing_default_values(self, cr, uid, values, context=None):
        missing_defaults = []
        avoid_tables = [] # avoid overriding inherited values when parent is set
        for tables, parent_field in self._inherits.items():
            if parent_field in values:
                avoid_tables.append(tables)
        for field in self._columns.keys():
            if not field in values:
                missing_defaults.append(field)
        for field in self._inherit_fields.keys():
            if (field not in values) and (self._inherit_fields[field][0] not in avoid_tables):
                missing_defaults.append(field)

        if len(missing_defaults):
            # override defaults with the provided values, never allow the other way around
            defaults = self.default_get(cr, uid, missing_defaults, context)
            for dv in defaults:
                # FIXME: also handle inherited m2m
                if dv in self._columns and self._columns[dv]._type == 'many2many' \
                     and defaults[dv] and isinstance(defaults[dv][0], (int, long)):
                        defaults[dv] = [(6, 0, defaults[dv])]
            defaults.update(values)
            values = defaults
        return values

class orm_memory(orm_template):

    _protected = ['read', 'write', 'create', 'default_get', 'perm_read', 'unlink', 'fields_get', 'fields_view_get', 'search', 'name_get', 'distinct_field_get', 'name_search', 'copy', 'import_data', 'search_count', 'exists']
    _inherit_fields = {}
    _max_count = 200
    _max_hours = 1
    _check_time = 20

    def __init__(self, cr):
        super(orm_memory, self).__init__(cr)
        self.datas = {}
        self.next_id = 0
        self.check_id = 0
        cr.execute('delete from wkf_instance where res_type=%s', (self._name,))

    def _check_access(self, uid, object_id, mode):
        if uid != 1 and self.datas[object_id]['internal.create_uid'] != uid:
            raise except_orm(_('AccessError'), '%s access is only allowed on your own records for osv_memory objects except for the super-user' % mode.capitalize())

    def vaccum(self, cr, uid):
        self.check_id += 1
        if self.check_id % self._check_time:
            return True
        tounlink = []
        max = time.time() - self._max_hours * 60 * 60
        for id in self.datas:
            if self.datas[id]['internal.date_access'] < max:
                tounlink.append(id)
        self.unlink(cr, 1, tounlink)
        if len(self.datas)>self._max_count:
            sorted = map(lambda x: (x[1]['internal.date_access'], x[0]), self.datas.items())
            sorted.sort()
            ids = map(lambda x: x[1], sorted[:len(self.datas)-self._max_count])
            self.unlink(cr, uid, ids)
        return True

    def read(self, cr, user, ids, fields_to_read=None, context=None, load='_classic_read'):
        if not context:
            context = {}
        if not fields_to_read:
            fields_to_read = self._columns.keys()
        result = []
        if self.datas:
            ids_orig = ids
            if isinstance(ids, (int, long)):
                ids = [ids]
            for id in ids:
                r = {'id': id}
                for f in fields_to_read:
                    record = self.datas.get(id)
                    if record:
                        self._check_access(user, id, 'read')
                        r[f] = record.get(f, False)
                        if r[f] and isinstance(self._columns[f], fields.binary) and context.get('bin_size', False):
                            r[f] = len(r[f])
                result.append(r)
                if id in self.datas:
                    self.datas[id]['internal.date_access'] = time.time()
            fields_post = filter(lambda x: x in self._columns and not getattr(self._columns[x], load), fields_to_read)
            for f in fields_post:
                res2 = self._columns[f].get_memory(cr, self, ids, f, user, context=context, values=result)
                for record in result:
                    record[f] = res2[record['id']]
            if isinstance(ids_orig, (int, long)):
                return result[0]
        return result

    def write(self, cr, user, ids, vals, context=None):
        if not ids:
            return True
        vals2 = {}
        upd_todo = []
        for field in vals:
            if self._columns[field]._classic_write:
                vals2[field] = vals[field]
            else:
                upd_todo.append(field)
        for object_id in ids:
            self._check_access(user, object_id, mode='write')
            self.datas[object_id].update(vals2)
            self.datas[object_id]['internal.date_access'] = time.time()
            for field in upd_todo:
                self._columns[field].set_memory(cr, self, object_id, field, vals[field], user, context)
        self._validate(cr, user, [object_id], context)
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_write(user, self._name, object_id, cr)
        return object_id

    def create(self, cr, user, vals, context=None):
        self.vaccum(cr, user)
        self.next_id += 1
        id_new = self.next_id

        vals = self._add_missing_default_values(cr, user, vals, context)

        vals2 = {}
        upd_todo = []
        for field in vals:
            if self._columns[field]._classic_write:
                vals2[field] = vals[field]
            else:
                upd_todo.append(field)
        self.datas[id_new] = vals2
        self.datas[id_new]['internal.date_access'] = time.time()
        self.datas[id_new]['internal.create_uid'] = user

        for field in upd_todo:
            self._columns[field].set_memory(cr, self, id_new, field, vals[field], user, context)
        self._validate(cr, user, [id_new], context)
        if self._log_create and not (context and context.get('no_store_function', False)):
            message = self._description + \
                " '" + \
                self.name_get(cr, user, [id_new], context=context)[0][1] + \
                "' "+ _("created.")
            self.log(cr, user, id_new, message, True, context=context)
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_create(user, self._name, id_new, cr)
        return id_new

    def _where_calc(self, cr, user, args, active_test=True, context=None):
        if not context:
            context = {}
        args = args[:]
        res=[]
        # if the object has a field named 'active', filter out all inactive
        # records unless they were explicitely asked for
        if 'active' in self._columns and (active_test and context.get('active_test', True)):
            if args:
                active_in_args = False
                for a in args:
                    if a[0] == 'active':
                        active_in_args = True
                if not active_in_args:
                    args.insert(0, ('active', '=', 1))
            else:
                args = [('active', '=', 1)]
        if args:
            import expression
            e = expression.expression(args)
            e.parse(cr, user, self, context)
            res = e.exp
        return res or []

    def _search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False, access_rights_uid=None):
        if not context:
            context = {}

        # implicit filter on current user except for superuser
        if user != 1:
            if not args:
                args = []
            args.insert(0, ('internal.create_uid', '=', user))

        result = self._where_calc(cr, user, args, context=context)
        if result==[]:
            return self.datas.keys()

        res=[]
        counter=0
        #Find the value of dict
        f=False
        if result:
            for id, data in self.datas.items():
                counter=counter+1
                data['id'] = id
                if limit and (counter > int(limit)):
                    break
                f = True
                for arg in result:
                    if arg[1] == '=':
                        val = eval('data[arg[0]]'+'==' +' arg[2]', locals())
                    elif arg[1] in ['<','>','in','not in','<=','>=','<>']:
                        val = eval('data[arg[0]]'+arg[1] +' arg[2]', locals())
                    elif arg[1] in ['ilike']:
                        val = (str(data[arg[0]]).find(str(arg[2]))!=-1)

                    f = f and val

                if f:
                    res.append(id)
        if count:
            return len(res)
        return res or []

    def unlink(self, cr, uid, ids, context=None):
        for id in ids:
            self._check_access(uid, id, 'unlink')
            self.datas.pop(id, None)
        if len(ids):
            cr.execute('delete from wkf_instance where res_type=%s and res_id IN %s', (self._name, tuple(ids)))
        return True

    def perm_read(self, cr, user, ids, context=None, details=True):
        result = []
        credentials = self.pool.get('res.users').name_get(cr, user, [user])[0]
        create_date = time.strftime('%Y-%m-%d %H:%M:%S')
        for id in ids:
            self._check_access(user, id, 'read')
            result.append({
                'create_uid': credentials,
                'create_date': create_date,
                'write_uid': False,
                'write_date': False,
                'id': id
            })
        return result

    def _check_removed_columns(self, cr, log=False):
        # nothing to check in memory...
        pass

    def exists(self, cr, uid, id, context=None):
        return id in self.datas

class orm(orm_template):
    _sql_constraints = []
    _table = None
    _protected = ['read','write','create','default_get','perm_read','unlink','fields_get','fields_view_get','search','name_get','distinct_field_get','name_search','copy','import_data','search_count', 'exists']

    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None):
        """
        Get the list of records in list view grouped by the given ``groupby`` fields

        :param cr: database cursor
        :param uid: current user id
        :param domain: list specifying search criteria [['field_name', 'operator', 'value'], ...]
        :param fields: list of fields present in the list view specified on the object
        :param groupby: list of fields on which to groupby the records
        :type fields_list: list (example ['field_name_1', ...])
        :param offset: optional number of records to skip
        :param limit: optional max number of records to return
        :param context: context arguments, like lang, time zone
        :return: list of dictionaries(one dictionary for each record) containing:

                    * the values of fields grouped by the fields in ``groupby`` argument
                    * __domain: list of tuples specifying the search criteria
                    * __context: dictionary with argument like ``groupby``
        :rtype: [{'field_name_1': value, ...]
        :raise AccessError: * if user has no read rights on the requested object
                            * if user tries to bypass access rules for read on the requested object

        """
        context = context or {}
        self.pool.get('ir.model.access').check(cr, uid, self._name, 'read', context=context)
        if not fields:
            fields = self._columns.keys()

        # compute the where, order by, limit and offset clauses
        (where_clause, where_clause_params, tables) = self._where_calc(cr, uid, domain, context=context)

        # apply direct ir.rules from current model
        self._apply_ir_rules(cr, uid, where_clause, where_clause_params, tables, 'read', context=context)

        # then apply the ir.rules from the parents (through _inherits), adding the appropriate JOINs if needed
        for inherited_model in self._inherits:
            previous_tables = list(tables)
            if self._apply_ir_rules(cr, uid, where_clause, where_clause_params, tables, 'read', model_name=inherited_model, context=context):
                # if some rules were applied, need to add the missing JOIN for them to make sense, passing the previous
                # list of table in case the inherited table was not in the list before (as that means the corresponding 
                # JOIN(s) was(were) not present)
                self._inherits_join_add(inherited_model, previous_tables, where_clause)
                tables = list(set(tables).union(set(previous_tables)))

        # Take care of adding join(s) if groupby is an '_inherits'ed field
        groupby_list = groupby
        if groupby:
            if groupby and isinstance(groupby, list):
                groupby = groupby[0]
            tables, where_clause, qfield = self._inherits_join_calc(groupby,tables,where_clause)

        if len(where_clause):
            where_clause = ' where '+string.join(where_clause, ' and ')
        else:
            where_clause = ''
        limit_str = limit and ' limit %d' % limit or ''
        offset_str = offset and ' offset %d' % offset or ''

        fget = self.fields_get(cr, uid, fields)
        float_int_fields = filter(lambda x: fget[x]['type'] in ('float','integer'), fields)
        sum = {}

        flist = ''
        group_by = groupby
        if groupby:
            if fget.get(groupby,False) and fget[groupby]['type'] in ('date','datetime'):
                flist = "to_char(%s,'yyyy-mm') as %s "%(groupby,groupby)
                groupby = "to_char(%s,'yyyy-mm')"%(groupby)
            else:
                flist = groupby


        fields_pre = [f for f in float_int_fields if
                   f == self.CONCURRENCY_CHECK_FIELD
                or (f in self._columns and getattr(self._columns[f], '_classic_write'))]
        for f in fields_pre:
            if f not in ['id','sequence']:
                operator = fget[f].get('group_operator','sum')
                if flist:
                    flist += ','
                flist += operator+'('+f+') as '+f

        if groupby:
            gb = ' group by '+groupby
        else:
            gb = ''
        cr.execute('select min(%s.id) as id,' % self._table + flist + ' from ' + ','.join(tables) + where_clause + gb + limit_str + offset_str, where_clause_params)
        alldata = {}
        groupby = group_by
        for r in cr.dictfetchall():
            for fld,val in r.items():
                if val == None:r[fld] = False
            alldata[r['id']] = r
            del r['id']
        data = self.read(cr, uid, alldata.keys(), groupby and [groupby] or ['id'], context=context)
        for d in data:
            if groupby:
                d['__domain'] = [(groupby,'=',alldata[d['id']][groupby] or False)] + domain
                if not isinstance(groupby_list,(str, unicode)):
                    if groupby or not context.get('group_by_no_leaf', False):
                        d['__context'] = {'group_by':groupby_list[1:]}
            if groupby and fget.has_key(groupby):
                if d[groupby] and fget[groupby]['type'] in ('date','datetime'):
                    dt = datetime.datetime.strptime(alldata[d['id']][groupby][:7],'%Y-%m')
                    days = calendar.monthrange(dt.year, dt.month)[1]

                    d[groupby] = datetime.datetime.strptime(d[groupby][:10],'%Y-%m-%d').strftime('%B %Y')
                    d['__domain'] = [(groupby,'>=',alldata[d['id']][groupby] and datetime.datetime.strptime(alldata[d['id']][groupby][:7] + '-01','%Y-%m-%d').strftime('%Y-%m-%d') or False),\
                                     (groupby,'<=',alldata[d['id']][groupby] and datetime.datetime.strptime(alldata[d['id']][groupby][:7] + '-' + str(days),'%Y-%m-%d').strftime('%Y-%m-%d') or False)] + domain
                del alldata[d['id']][groupby]
            d.update(alldata[d['id']])
            del d['id']
        return data

    def _inherits_join_add(self, parent_model_name, tables, where_clause):
        """
        Add missing table SELECT and JOIN clause for reaching the parent table (no duplicates)

        :param parent_model_name: name of the parent model for which the clauses should be added
        :param tables: list of table._table names enclosed in double quotes as returned
                       by _where_calc()
        :param where_clause: current list of WHERE clause params
        """
        inherits_field = self._inherits[parent_model_name]
        parent_model = self.pool.get(parent_model_name)
        parent_table_name = parent_model._table
        quoted_parent_table_name = '"%s"' % parent_table_name
        if quoted_parent_table_name not in tables:
            tables.append(quoted_parent_table_name)
            where_clause.append('("%s".%s = %s.id)' % (self._table, inherits_field, parent_table_name))
        return (tables, where_clause)

    def _inherits_join_calc(self, field, tables, where_clause):
        """
        Adds missing table select and join clause(s) for reaching
        the field coming from an '_inherits' parent table (no duplicates).

        :param tables: list of table._table names enclosed in double quotes as returned
                        by _where_calc()
        :param where_clause: current list of WHERE clause params
        :return: (table, where_clause, qualified_field) where ``table`` and ``where_clause`` are the updated
                 versions of the parameters, and ``qualified_field`` is the qualified name of ``field``
                 in the form ``table.field``, to be referenced in queries. 
        """
        current_table = self
        while field in current_table._inherit_fields and not field in current_table._columns:
            parent_model_name = current_table._inherit_fields[field][0]
            parent_table = self.pool.get(parent_model_name)
            self._inherits_join_add(parent_model_name, tables, where_clause)
            current_table = parent_table
        return (tables, where_clause, '"%s".%s' % (current_table._table, field))

    def _parent_store_compute(self, cr):
        if not self._parent_store:
            return
        logger = netsvc.Logger()
        logger.notifyChannel('orm', netsvc.LOG_INFO, 'Computing parent left and right for table %s...' % (self._table, ))
        def browse_rec(root, pos=0):
# TODO: set order
            where = self._parent_name+'='+str(root)
            if not root:
                where = self._parent_name+' IS NULL'
            if self._parent_order:
                where += ' order by '+self._parent_order
            cr.execute('SELECT id FROM '+self._table+' WHERE '+where)
            pos2 = pos + 1
            childs = cr.fetchall()
            for id in childs:
                pos2 = browse_rec(id[0], pos2)
            cr.execute('update '+self._table+' set parent_left=%s, parent_right=%s where id=%s', (pos,pos2,root))
            return pos2+1
        query = 'SELECT id FROM '+self._table+' WHERE '+self._parent_name+' IS NULL'
        if self._parent_order:
            query += ' order by '+self._parent_order
        pos = 0
        cr.execute(query)
        for (root,) in cr.fetchall():
            pos = browse_rec(root, pos)
        return True

    def _update_store(self, cr, f, k):
        logger = netsvc.Logger()
        logger.notifyChannel('orm', netsvc.LOG_INFO, "storing computed values of fields.function '%s'" % (k,))
        ss = self._columns[k]._symbol_set
        update_query = 'UPDATE "%s" SET "%s"=%s WHERE id=%%s' % (self._table, k, ss[0])
        cr.execute('select id from '+self._table)
        ids_lst = map(lambda x: x[0], cr.fetchall())
        while ids_lst:
            iids = ids_lst[:40]
            ids_lst = ids_lst[40:]
            res = f.get(cr, self, iids, k, 1, {})
            for key,val in res.items():
                if f._multi:
                    val = val[k]
                # if val is a many2one, just write the ID
                if type(val)==tuple:
                    val = val[0]
                if (val<>False) or (type(val)<>bool):
                    cr.execute(update_query, (ss[1](val), key))

    def _check_removed_columns(self, cr, log=False):
        logger = netsvc.Logger()
        # iterate on the database columns to drop the NOT NULL constraints
        # of fields which were required but have been removed (or will be added by another module)
        columns = [c for c in self._columns if not (isinstance(self._columns[c], fields.function) and not self._columns[c].store)]
        columns += ('id', 'write_uid', 'write_date', 'create_uid', 'create_date') # openerp access columns
        cr.execute("SELECT a.attname, a.attnotnull"
                   "  FROM pg_class c, pg_attribute a"
                   " WHERE c.relname=%s"
                   "   AND c.oid=a.attrelid"
                   "   AND a.attisdropped=%s"
                   "   AND pg_catalog.format_type(a.atttypid, a.atttypmod) NOT IN ('cid', 'tid', 'oid', 'xid')"
                   "   AND a.attname NOT IN %s" ,(self._table, False, tuple(columns))),

        for column in cr.dictfetchall():
            if log:
                logger.notifyChannel("orm", netsvc.LOG_DEBUG, "column %s is in the table %s but not in the corresponding object %s" % (column['attname'], self._table, self._name))
            if column['attnotnull']:
                cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" DROP NOT NULL' % (self._table, column['attname']))

    def _auto_init(self, cr, context={}):
        store_compute =  False
        logger = netsvc.Logger()
        create = False
        todo_end = []
        self._field_create(cr, context=context)
        if getattr(self, '_auto', True):
            cr.execute("SELECT relname FROM pg_class WHERE relkind IN ('r','v') AND relname=%s" ,( self._table,))
            if not cr.rowcount:
                cr.execute('CREATE TABLE "%s" (id SERIAL NOT NULL, PRIMARY KEY(id)) WITHOUT OIDS' % (self._table,))
                cr.execute("COMMENT ON TABLE \"%s\" IS '%s'" % (self._table, self._description.replace("'","''")))
                create = True
            cr.commit()
            if self._parent_store:
                cr.execute("""SELECT c.relname
                    FROM pg_class c, pg_attribute a
                    WHERE c.relname=%s AND a.attname=%s AND c.oid=a.attrelid
                    """, (self._table, 'parent_left'))
                if not cr.rowcount:
                    if 'parent_left' not in self._columns:
                        logger.notifyChannel('orm', netsvc.LOG_ERROR, 'create a column parent_left on object %s: fields.integer(\'Left Parent\', select=1)' % (self._table, ))
                    if 'parent_right' not in self._columns:
                        logger.notifyChannel('orm', netsvc.LOG_ERROR, 'create a column parent_right on object %s: fields.integer(\'Right Parent\', select=1)' % (self._table, ))
                    if self._columns[self._parent_name].ondelete != 'cascade':
                        logger.notifyChannel('orm', netsvc.LOG_ERROR, "The column %s on object %s must be set as ondelete='cascade'" % (self._parent_name, self._name))
                    cr.execute('ALTER TABLE "%s" ADD COLUMN "parent_left" INTEGER' % (self._table,))
                    cr.execute('ALTER TABLE "%s" ADD COLUMN "parent_right" INTEGER' % (self._table,))
                    cr.commit()
                    store_compute = True

            if self._log_access:
                logs = {
                    'create_uid': 'INTEGER REFERENCES res_users ON DELETE SET NULL',
                    'create_date': 'TIMESTAMP',
                    'write_uid': 'INTEGER REFERENCES res_users ON DELETE SET NULL',
                    'write_date': 'TIMESTAMP'
                }
                for k in logs:
                    cr.execute("""
                        SELECT c.relname
                          FROM pg_class c, pg_attribute a
                         WHERE c.relname=%s AND a.attname=%s AND c.oid=a.attrelid
                        """, (self._table, k))
                    if not cr.rowcount:
                        cr.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (self._table, k, logs[k]))
                        cr.commit()

            self._check_removed_columns(cr, log=False)

            # iterate on the "object columns"
            todo_update_store = []
            update_custom_fields = context.get('update_custom_fields', False)
            for k in self._columns:
                if k in ('id', 'write_uid', 'write_date', 'create_uid', 'create_date'):
                    continue
                    #raise _('Can not define a column %s. Reserved keyword !') % (k,)
                #Not Updating Custom fields
                if k.startswith('x_') and not update_custom_fields:
                    continue
                f = self._columns[k]

                if isinstance(f, fields.one2many):
                    cr.execute("SELECT relname FROM pg_class WHERE relkind='r' AND relname=%s", (f._obj,))

                    if self.pool.get(f._obj):
                        if f._fields_id not in self.pool.get(f._obj)._columns.keys():
                            if not self.pool.get(f._obj)._inherits or (f._fields_id not in self.pool.get(f._obj)._inherit_fields.keys()):
                                raise except_orm('Programming Error', ("There is no reference field '%s' found for '%s'") % (f._fields_id,f._obj,))

                    if cr.fetchone():
                        cr.execute("SELECT count(1) as c FROM pg_class c,pg_attribute a WHERE c.relname=%s AND a.attname=%s AND c.oid=a.attrelid", (f._obj, f._fields_id))
                        res = cr.fetchone()[0]
                        if not res:
                            cr.execute('ALTER TABLE "%s" ADD FOREIGN KEY (%s) REFERENCES "%s" ON DELETE SET NULL' % (self._obj, f._fields_id, f._table))
                elif isinstance(f, fields.many2many):
                    cr.execute("SELECT relname FROM pg_class WHERE relkind IN ('r','v') AND relname=%s", (f._rel,))
                    if not cr.dictfetchall():
                        if not self.pool.get(f._obj):
                            raise except_orm('Programming Error', ('There is no reference available for %s') % (f._obj,))
                        ref = self.pool.get(f._obj)._table
#                        ref = f._obj.replace('.', '_')
                        cr.execute('CREATE TABLE "%s" ("%s" INTEGER NOT NULL REFERENCES "%s" ON DELETE CASCADE, "%s" INTEGER NOT NULL REFERENCES "%s" ON DELETE CASCADE) WITH OIDS' % (f._rel, f._id1, self._table, f._id2, ref))
                        cr.execute('CREATE INDEX "%s_%s_index" ON "%s" ("%s")' % (f._rel, f._id1, f._rel, f._id1))
                        cr.execute('CREATE INDEX "%s_%s_index" ON "%s" ("%s")' % (f._rel, f._id2, f._rel, f._id2))
                        cr.execute("COMMENT ON TABLE \"%s\" IS 'RELATION BETWEEN %s AND %s'" % (f._rel, self._table, ref))
                        cr.commit()
                else:
                    cr.execute("SELECT c.relname,a.attname,a.attlen,a.atttypmod,a.attnotnull,a.atthasdef,t.typname,CASE WHEN a.attlen=-1 THEN a.atttypmod-4 ELSE a.attlen END as size " \
                               "FROM pg_class c,pg_attribute a,pg_type t " \
                               "WHERE c.relname=%s " \
                               "AND a.attname=%s " \
                               "AND c.oid=a.attrelid " \
                               "AND a.atttypid=t.oid", (self._table, k))
                    res = cr.dictfetchall()
                    if not res and hasattr(f,'oldname'):
                        cr.execute("SELECT c.relname,a.attname,a.attlen,a.atttypmod,a.attnotnull,a.atthasdef,t.typname,CASE WHEN a.attlen=-1 THEN a.atttypmod-4 ELSE a.attlen END as size " \
                            "FROM pg_class c,pg_attribute a,pg_type t " \
                            "WHERE c.relname=%s " \
                            "AND a.attname=%s " \
                            "AND c.oid=a.attrelid " \
                            "AND a.atttypid=t.oid", (self._table, f.oldname))
                        res_old = cr.dictfetchall()
                        logger.notifyChannel('orm', netsvc.LOG_DEBUG, 'trying to rename %s(%s) to %s'% (self._table, f.oldname, k))
                        if res_old and len(res_old)==1:
                            cr.execute('ALTER TABLE "%s" RENAME "%s" TO "%s"' % ( self._table,f.oldname, k))
                            res = res_old
                            res[0]['attname'] = k


                    if len(res)==1:
                        f_pg_def = res[0]
                        f_pg_type = f_pg_def['typname']
                        f_pg_size = f_pg_def['size']
                        f_pg_notnull = f_pg_def['attnotnull']
                        if isinstance(f, fields.function) and not f.store and\
                                not getattr(f, 'nodrop', False):
                            logger.notifyChannel('orm', netsvc.LOG_INFO, 'column %s (%s) in table %s removed: converted to a function !\n' % (k, f.string, self._table))
                            cr.execute('ALTER TABLE "%s" DROP COLUMN "%s" CASCADE'% (self._table, k))
                            cr.commit()
                            f_obj_type = None
                        else:
                            f_obj_type = get_pg_type(f) and get_pg_type(f)[0]

                        if f_obj_type:
                            ok = False
                            casts = [
                                ('text', 'char', 'VARCHAR(%d)' % (f.size or 0,), '::VARCHAR(%d)'%(f.size or 0,)),
                                ('varchar', 'text', 'TEXT', ''),
                                ('int4', 'float', get_pg_type(f)[1], '::'+get_pg_type(f)[1]),
                                ('date', 'datetime', 'TIMESTAMP', '::TIMESTAMP'),
                                ('timestamp', 'date', 'date', '::date'),
                                ('numeric', 'float', get_pg_type(f)[1], '::'+get_pg_type(f)[1]),
                                ('float8', 'float', get_pg_type(f)[1], '::'+get_pg_type(f)[1]),
                            ]
                            if f_pg_type == 'varchar' and f._type == 'char' and f_pg_size < f.size:
                                logger.notifyChannel('orm', netsvc.LOG_INFO, "column '%s' in table '%s' changed size" % (k, self._table))
                                cr.execute('ALTER TABLE "%s" RENAME COLUMN "%s" TO temp_change_size' % (self._table, k))
                                cr.execute('ALTER TABLE "%s" ADD COLUMN "%s" VARCHAR(%d)' % (self._table, k, f.size))
                                cr.execute('UPDATE "%s" SET "%s"=temp_change_size::VARCHAR(%d)' % (self._table, k, f.size))
                                cr.execute('ALTER TABLE "%s" DROP COLUMN temp_change_size CASCADE' % (self._table,))
                                cr.commit()
                            for c in casts:
                                if (f_pg_type==c[0]) and (f._type==c[1]):
                                    if f_pg_type != f_obj_type:
                                        if f_pg_type != f_obj_type:
                                            logger.notifyChannel('orm', netsvc.LOG_INFO, "column '%s' in table '%s' changed type to %s." % (k, self._table, c[1]))
                                        ok = True
                                        cr.execute('ALTER TABLE "%s" RENAME COLUMN "%s" TO temp_change_size' % (self._table, k))
                                        cr.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (self._table, k, c[2]))
                                        cr.execute(('UPDATE "%s" SET "%s"=temp_change_size'+c[3]) % (self._table, k))
                                        cr.execute('ALTER TABLE "%s" DROP COLUMN temp_change_size CASCADE' % (self._table,))
                                        cr.commit()
                                    break

                            if f_pg_type != f_obj_type:
                                if not ok:
                                    i = 0
                                    while True:
                                        newname = self._table + '_moved' + str(i)
                                        cr.execute("SELECT count(1) FROM pg_class c,pg_attribute a " \
                                            "WHERE c.relname=%s " \
                                            "AND a.attname=%s " \
                                            "AND c.oid=a.attrelid ", (self._table, newname))
                                        if not cr.fetchone()[0]:
                                            break
                                        i+=1
                                    logger.notifyChannel('orm', netsvc.LOG_WARNING, "column '%s' in table '%s' has changed type (DB=%s, def=%s), data moved to table %s !" % (k, self._table, f_pg_type, f._type, newname))
                                    if f_pg_notnull:
                                        cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" DROP NOT NULL' % (self._table, k))
                                    cr.execute('ALTER TABLE "%s" RENAME COLUMN "%s" TO "%s"' % (self._table, k, newname))
                                    cr.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (self._table, k, get_pg_type(f)[1]))
                                    cr.execute("COMMENT ON COLUMN %s.%s IS '%s'" % (self._table, k, f.string.replace("'","''")))

                            # if the field is required and hasn't got a NOT NULL constraint
                            if f.required and f_pg_notnull == 0:
                                # set the field to the default value if any
                                if k in self._defaults:
                                    if callable(self._defaults[k]):
                                        default = self._defaults[k](self, cr, 1, context)
                                    else:
                                        default = self._defaults[k]

                                    if (default is not None):
                                        ss = self._columns[k]._symbol_set
                                        query = 'UPDATE "%s" SET "%s"=%s WHERE "%s" is NULL' % (self._table, k, ss[0], k)
                                        cr.execute(query, (ss[1](default),))
                                # add the NOT NULL constraint
                                cr.commit()
                                try:
                                    cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" SET NOT NULL' % (self._table, k))
                                    cr.commit()
                                except Exception:
                                    logger.notifyChannel('orm', netsvc.LOG_WARNING, 'unable to set a NOT NULL constraint on column %s of the %s table !\nIf you want to have it, you should update the records and execute manually:\nALTER TABLE %s ALTER COLUMN %s SET NOT NULL' % (k, self._table, self._table, k))
                                cr.commit()
                            elif not f.required and f_pg_notnull == 1:
                                cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" DROP NOT NULL' % (self._table, k))
                                cr.commit()

                            # Verify index
                            indexname = '%s_%s_index' % (self._table, k)
                            cr.execute("SELECT indexname FROM pg_indexes WHERE indexname = %s and tablename = %s", (indexname, self._table))
                            res2 = cr.dictfetchall()
                            if not res2 and f.select:
                                cr.execute('CREATE INDEX "%s_%s_index" ON "%s" ("%s")' % (self._table, k, self._table, k))
                                cr.commit()
                                if f._type == 'text':
                                    # FIXME: for fields.text columns we should try creating GIN indexes instead (seems most suitable for an ERP context)
                                    logger.notifyChannel('orm', netsvc.LOG_WARNING, "Adding (b-tree) index for text column '%s' in table '%s'."\
                                        "This is probably useless (does not work for fulltext search) and prevents INSERTs of long texts because there is a length limit for indexable btree values!\n"\
                                        "Use a search view instead if you simply want to make the field searchable." % (k, f._type, self._table))
                            if res2 and not f.select:
                                cr.execute('DROP INDEX "%s_%s_index"' % (self._table, k))
                                cr.commit()
                                logger.notifyChannel('orm', netsvc.LOG_WARNING, "Dropping index for column '%s' of type '%s' in table '%s' as it is not required anymore" % (k, f._type, self._table))

                            if isinstance(f, fields.many2one):
                                ref = self.pool.get(f._obj)._table
                                if ref != 'ir_actions':
                                    cr.execute('SELECT confdeltype, conname FROM pg_constraint as con, pg_class as cl1, pg_class as cl2, '
                                                'pg_attribute as att1, pg_attribute as att2 '
                                            'WHERE con.conrelid = cl1.oid '
                                                'AND cl1.relname = %s '
                                                'AND con.confrelid = cl2.oid '
                                                'AND cl2.relname = %s '
                                                'AND array_lower(con.conkey, 1) = 1 '
                                                'AND con.conkey[1] = att1.attnum '
                                                'AND att1.attrelid = cl1.oid '
                                                'AND att1.attname = %s '
                                                'AND array_lower(con.confkey, 1) = 1 '
                                                'AND con.confkey[1] = att2.attnum '
                                                'AND att2.attrelid = cl2.oid '
                                                'AND att2.attname = %s '
                                                "AND con.contype = 'f'", (self._table, ref, k, 'id'))
                                    res2 = cr.dictfetchall()
                                    if res2:
                                        if res2[0]['confdeltype'] != POSTGRES_CONFDELTYPES.get(f.ondelete.upper(), 'a'):
                                            cr.execute('ALTER TABLE "' + self._table + '" DROP CONSTRAINT "' + res2[0]['conname'] + '"')
                                            cr.execute('ALTER TABLE "' + self._table + '" ADD FOREIGN KEY ("' + k + '") REFERENCES "' + ref + '" ON DELETE ' + f.ondelete)
                                            cr.commit()
                    elif len(res)>1:
                        logger.notifyChannel('orm', netsvc.LOG_ERROR, "Programming error, column %s->%s has multiple instances !"%(self._table,k))
                    if not res:
                        if not isinstance(f, fields.function) or f.store:

                            # add the missing field
                            cr.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (self._table, k, get_pg_type(f)[1]))
                            cr.execute("COMMENT ON COLUMN %s.%s IS '%s'" % (self._table, k, f.string.replace("'","''")))

                            # initialize it
                            if not create and k in self._defaults:
                                if callable(self._defaults[k]):
                                    default = self._defaults[k](self, cr, 1, context)
                                else:
                                    default = self._defaults[k]

                                ss = self._columns[k]._symbol_set
                                query = 'UPDATE "%s" SET "%s"=%s' % (self._table, k, ss[0])
                                cr.execute(query, (ss[1](default),))
                                cr.commit()
                                logger.notifyChannel('orm', netsvc.LOG_DEBUG, 'setting default value of new column %s of table %s'% (k, self._table))
                            elif not create:
                                logger.notifyChannel('orm', netsvc.LOG_DEBUG, 'creating new column %s of table %s'% (k, self._table))

                            if isinstance(f, fields.function):
                                order = 10
                                if f.store is not True:
                                    order = f.store[f.store.keys()[0]][2]
                                todo_update_store.append((order, f,k))

                            # and add constraints if needed
                            if isinstance(f, fields.many2one):
                                if not self.pool.get(f._obj):
                                    raise except_orm('Programming Error', ('There is no reference available for %s') % (f._obj,))
                                ref = self.pool.get(f._obj)._table
#                                ref = f._obj.replace('.', '_')
                                # ir_actions is inherited so foreign key doesn't work on it
                                if ref != 'ir_actions':
                                    cr.execute('ALTER TABLE "%s" ADD FOREIGN KEY ("%s") REFERENCES "%s" ON DELETE %s' % (self._table, k, ref, f.ondelete))
                            if f.select:
                                cr.execute('CREATE INDEX "%s_%s_index" ON "%s" ("%s")' % (self._table, k, self._table, k))
                            if f.required:
                                try:
                                    cr.commit()
                                    cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" SET NOT NULL' % (self._table, k))
                                except Exception:
                                    logger.notifyChannel('orm', netsvc.LOG_WARNING, 'WARNING: unable to set column %s of table %s not null !\nTry to re-run: openerp-server.py --update=module\nIf it doesn\'t work, update records and execute manually:\nALTER TABLE %s ALTER COLUMN %s SET NOT NULL' % (k, self._table, self._table, k))
                            cr.commit()
            for order,f,k in todo_update_store:
                todo_end.append((order, self._update_store, (f, k)))

        else:
            cr.execute("SELECT relname FROM pg_class WHERE relkind IN ('r','v') AND relname=%s", (self._table,))
            create = not bool(cr.fetchone())

        cr.commit()     # start a new transaction

        for (key, con, _) in self._sql_constraints:
            conname = '%s_%s' % (self._table, key)
            cr.execute("SELECT conname FROM pg_constraint where conname=%s", (conname,))
            if not cr.dictfetchall():
                query = 'ALTER TABLE "%s" ADD CONSTRAINT "%s" %s' % (self._table, conname, con,)
                try:
                    cr.execute(query)
                    cr.commit()
                except:
                    logger.notifyChannel('orm', netsvc.LOG_WARNING, 'unable to add \'%s\' constraint on table %s !\n If you want to have it, you should update the records and execute manually:\n%s' % (con, self._table, query))
                    cr.rollback()

        if create:
            if hasattr(self, "_sql"):
                for line in self._sql.split(';'):
                    line2 = line.replace('\n', '').strip()
                    if line2:
                        cr.execute(line2)
                        cr.commit()
        if store_compute:
            self._parent_store_compute(cr)
            cr.commit()
        return todo_end

    def __init__(self, cr):
        super(orm, self).__init__(cr)

        if not hasattr(self, '_log_access'):
            # if not access is not specify, it is the same value as _auto
            self._log_access = getattr(self, "_auto", True)

        self._columns = self._columns.copy()
        for store_field in self._columns:
            f = self._columns[store_field]
            if hasattr(f, 'digits_change'):
                f.digits_change(cr)
            if not isinstance(f, fields.function):
                continue
            if not f.store:
                continue
            if self._columns[store_field].store is True:
                sm = {self._name:(lambda self,cr, uid, ids, c={}: ids, None, 10, None)}
            else:
                sm = self._columns[store_field].store
            for object, aa in sm.items():
                if len(aa)==4:
                    (fnct,fields2,order,length)=aa
                elif len(aa)==3:
                    (fnct,fields2,order)=aa
                    length = None
                else:
                    raise except_orm('Error',
                        ('Invalid function definition %s in object %s !\nYou must use the definition: store={object:(fnct, fields, priority, time length)}.' % (store_field, self._name)))
                self.pool._store_function.setdefault(object, [])
                ok = True
                for x,y,z,e,f,l in self.pool._store_function[object]:
                    if (x==self._name) and (y==store_field) and (e==fields2):
                        if f==order:
                            ok = False
                if ok:
                    self.pool._store_function[object].append( (self._name, store_field, fnct, fields2, order, length))
                    self.pool._store_function[object].sort(lambda x,y: cmp(x[4],y[4]))

        for (key, _, msg) in self._sql_constraints:
            self.pool._sql_error[self._table+'_'+key] = msg

        # Load manual fields

        cr.execute("SELECT id FROM ir_model_fields WHERE name=%s AND model=%s", ('state', 'ir.model.fields'))
        if cr.fetchone():
            cr.execute('SELECT * FROM ir_model_fields WHERE model=%s AND state=%s', (self._name, 'manual'))
            for field in cr.dictfetchall():
                if field['name'] in self._columns:
                    continue
                attrs = {
                    'string': field['field_description'],
                    'required': bool(field['required']),
                    'readonly': bool(field['readonly']),
                    'domain': field['domain'] or None,
                    'size': field['size'],
                    'ondelete': field['on_delete'],
                    'translate': (field['translate']),
                    #'select': int(field['select_level'])
                }

                if field['ttype'] == 'selection':
                    self._columns[field['name']] = getattr(fields, field['ttype'])(eval(field['selection']), **attrs)
                elif field['ttype'] == 'reference':
                    self._columns[field['name']] = getattr(fields, field['ttype'])(selection=eval(field['selection']), **attrs)
                elif field['ttype'] == 'many2one':
                    self._columns[field['name']] = getattr(fields, field['ttype'])(field['relation'], **attrs)
                elif field['ttype'] == 'one2many':
                    self._columns[field['name']] = getattr(fields, field['ttype'])(field['relation'], field['relation_field'], **attrs)
                elif field['ttype'] == 'many2many':
                    _rel1 = field['relation'].replace('.', '_')
                    _rel2 = field['model'].replace('.', '_')
                    _rel_name = 'x_%s_%s_%s_rel' %(_rel1, _rel2, field['name'])
                    self._columns[field['name']] = getattr(fields, field['ttype'])(field['relation'], _rel_name, 'id1', 'id2', **attrs)
                else:
                    self._columns[field['name']] = getattr(fields, field['ttype'])(**attrs)
        self._inherits_check()
        self._inherits_reload()
        if not self._sequence:
            self._sequence = self._table+'_id_seq'
        for k in self._defaults:
            assert (k in self._columns) or (k in self._inherit_fields), 'Default function defined in %s but field %s does not exist !' % (self._name, k,)
        for f in self._columns:
            self._columns[f].restart()

    #
    # Update objects that uses this one to update their _inherits fields
    #

    def _inherits_reload_src(self):
        for obj in self.pool.obj_pool.values():
            if self._name in obj._inherits:
                obj._inherits_reload()

    def _inherits_reload(self):
        res = {}
        for table in self._inherits:
            res.update(self.pool.get(table)._inherit_fields)
            for col in self.pool.get(table)._columns.keys():
                res[col] = (table, self._inherits[table], self.pool.get(table)._columns[col])
            for col in self.pool.get(table)._inherit_fields.keys():
                res[col] = (table, self._inherits[table], self.pool.get(table)._inherit_fields[col][2])
        self._inherit_fields = res
        self._inherits_reload_src()

    def _inherits_check(self):
        for table, field_name in self._inherits.items():
            if field_name not in self._columns:
                logging.getLogger('init').info('Missing many2one field definition for _inherits reference "%s" in "%s", using default one.' % (field_name, self._name))
                self._columns[field_name] =  fields.many2one(table, string="Automatically created field to link to parent %s" % table,
                                                             required=True, ondelete="cascade")
            elif not self._columns[field_name].required or self._columns[field_name].ondelete.lower() != "cascade":
                logging.getLogger('init').warning('Field definition for _inherits reference "%s" in "%s" must be marked as "required" with ondelete="cascade", forcing it.' % (field_name, self._name))
                self._columns[field_name].required = True
                self._columns[field_name].ondelete = "cascade"

    #def __getattr__(self, name):
    #    """
    #    Proxies attribute accesses to the `inherits` parent so we can call methods defined on the inherited parent
    #    (though inherits doesn't use Python inheritance).
    #    Handles translating between local ids and remote ids.
    #    Known issue: doesn't work correctly when using python's own super(), don't involve inherit-based inheritance
    #                 when you have inherits.
    #    """
    #    for model, field in self._inherits.iteritems():
    #        proxy = self.pool.get(model)
    #        if hasattr(proxy, name):
    #            attribute = getattr(proxy, name)
    #            if not hasattr(attribute, '__call__'):
    #                return attribute
    #            break
    #    else:
    #        return super(orm, self).__getattr__(name)

    #    def _proxy(cr, uid, ids, *args, **kwargs):
    #        objects = self.browse(cr, uid, ids, kwargs.get('context', None))
    #        lst = [obj[field].id for obj in objects if obj[field]]
    #        return getattr(proxy, name)(cr, uid, lst, *args, **kwargs)

    #    return _proxy


    def fields_get(self, cr, user, fields=None, context=None):
        """
        Get the description of list of fields

        :param cr: database cursor
        :param user: current user id
        :param fields: list of fields
        :param context: context arguments, like lang, time zone
        :return: dictionary of field dictionaries, each one describing a field of the business object
        :raise AccessError: * if user has no create/write rights on the requested object

        """
        ira = self.pool.get('ir.model.access')
        write_access = ira.check(cr, user, self._name, 'write', raise_exception=False, context=context) or \
                       ira.check(cr, user, self._name, 'create', raise_exception=False, context=context)
        return super(orm, self).fields_get(cr, user, fields, context, write_access)

    def read(self, cr, user, ids, fields=None, context=None, load='_classic_read'):
        """
        Read records with given ids with the given fields

        :param cr: database cursor
        :param user: current user id
        :param ids: id or list of the ids of the records to read
        :param fields: optional list of field names to return (default: all fields would be returned)
        :type fields: list (example ['field_name_1', ...])
        :param context: (optional) context arguments, like lang, time zone
        :return: list of dictionaries((dictionary per record asked)) with requested field values
        :rtype: [{‘name_of_the_field’: value, ...}, ...]
        :raise AccessError: * if user has no read rights on the requested object
                            * if user tries to bypass access rules for read on the requested object

        """
        if not context:
            context = {}
        self.pool.get('ir.model.access').check(cr, user, self._name, 'read', context=context)
        if not fields:
            fields = self._columns.keys() + self._inherit_fields.keys()
        if isinstance(ids, (int, long)):
            select = [ids]
        else:
            select = ids
        select = map(lambda x: isinstance(x,dict) and x['id'] or x, select)
        result = self._read_flat(cr, user, select, fields, context, load)

        for r in result:
            for key, v in r.items():
                if v is None:
                    r[key] = False
                if key in self._columns:
                    column = self._columns[key]
                elif key in self._inherit_fields:
                    column = self._inherit_fields[key][2]
                else:
                    continue
                if v and column._type == 'reference':
                    model_name, ref_id = v.split(',', 1)
                    model = self.pool.get(model_name)
                    if not model:
                        reset = True
                    else:
                        cr.execute('SELECT count(1) FROM "%s" WHERE id=%%s' % (model._table,), (ref_id,))
                        reset = not cr.fetchone()[0]
                    if reset:
                        if column._classic_write:
                            query = 'UPDATE "%s" SET "%s"=NULL WHERE id=%%s' % (self._table, key)
                            cr.execute(query, (r['id'],))
                        r[key] = False

        if isinstance(ids, (int, long, dict)):
            return result and result[0] or False
        return result

    def _read_flat(self, cr, user, ids, fields_to_read, context=None, load='_classic_read'):
        if not context:
            context = {}
        if not ids:
            return []
        if fields_to_read == None:
            fields_to_read = self._columns.keys()

        # Construct a clause for the security rules.
        # 'tables' hold the list of tables necessary for the SELECT including the ir.rule clauses,
        # or will at least contain self._table.
        rule_clause, rule_params, tables = self.pool.get('ir.rule').domain_get(cr, user, self._name, 'read', context=context)

        # all inherited fields + all non inherited fields for which the attribute whose name is in load is True
        fields_pre = [f for f in fields_to_read if
                           f == self.CONCURRENCY_CHECK_FIELD
                        or (f in self._columns and getattr(self._columns[f], '_classic_write'))
                     ] + self._inherits.values()

        res = []
        if len(fields_pre):
            def convert_field(f):
                f_qual = "%s.%s" % (self._table, f) # need fully-qualified references in case len(tables) > 1
                if f in ('create_date', 'write_date'):
                    return "date_trunc('second', %s) as %s" % (f_qual, f)
                if f == self.CONCURRENCY_CHECK_FIELD:
                    if self._log_access:
                        return "COALESCE(%s.write_date, %s.create_date, now())::timestamp AS %s" % (self._table, self._table, f,)
                    return "now()::timestamp AS %s" % (f,)
                if isinstance(self._columns[f], fields.binary) and context.get('bin_size', False):
                    return 'length(%s) as "%s"' % (f_qual, f)
                return f_qual

            fields_pre2 = map(convert_field, fields_pre)
            order_by = self._parent_order or self._order
            select_fields = ','.join(fields_pre2 + [self._table + '.id'])
            query = 'SELECT %s FROM %s WHERE %s.id IN %%s' % (select_fields, ','.join(tables), self._table)
            if rule_clause:
                query += " AND " + (' OR '.join(rule_clause))
            query += " ORDER BY " + order_by
            for sub_ids in cr.split_for_in_conditions(ids):
                if rule_clause:
                    cr.execute(query, [tuple(sub_ids)] + rule_params)
                    if cr.rowcount != len(sub_ids):
                        raise except_orm(_('AccessError'),
                                _('You try to bypass an access rule while reading (Document type: %s).') % self._description)
                else:
                    cr.execute(query, (tuple(sub_ids),))
                res.extend(cr.dictfetchall())
        else:
            res = map(lambda x: {'id': x}, ids)

        for f in fields_pre:
            if f == self.CONCURRENCY_CHECK_FIELD:
                continue
            if self._columns[f].translate:
                ids = [x['id'] for x in res]
                #TODO: optimize out of this loop
                res_trans = self.pool.get('ir.translation')._get_ids(cr, user, self._name+','+f, 'model', context.get('lang', False) or 'en_US', ids)
                for r in res:
                    r[f] = res_trans.get(r['id'], False) or r[f]

        for table in self._inherits:
            col = self._inherits[table]
            cols = intersect(self._inherit_fields.keys(), set(fields_to_read) - set(self._columns.keys()))
            if not cols:
                continue
            res2 = self.pool.get(table).read(cr, user, [x[col] for x in res], cols, context, load)

            res3 = {}
            for r in res2:
                res3[r['id']] = r
                del r['id']

            for record in res:
                if not record[col]:# if the record is deleted from _inherits table?
                    continue
                record.update(res3[record[col]])
                if col not in fields_to_read:
                    del record[col]

        # all fields which need to be post-processed by a simple function (symbol_get)
        fields_post = filter(lambda x: x in self._columns and self._columns[x]._symbol_get, fields_to_read)
        if fields_post:
            for r in res:
                for f in fields_post:
                    r[f] = self._columns[f]._symbol_get(r[f])
        ids = [x['id'] for x in res]

        # all non inherited fields for which the attribute whose name is in load is False
        fields_post = filter(lambda x: x in self._columns and not getattr(self._columns[x], load), fields_to_read)

        # Compute POST fields
        todo = {}
        for f in fields_post:
            todo.setdefault(self._columns[f]._multi, [])
            todo[self._columns[f]._multi].append(f)
        for key,val in todo.items():
            if key:
                res2 = self._columns[val[0]].get(cr, self, ids, val, user, context=context, values=res)
                for pos in val:
                    for record in res:
                        if isinstance(res2[record['id']], str):res2[record['id']] = eval(res2[record['id']]) #TOCHECK : why got string instend of dict in python2.6
                        record[pos] = res2[record['id']][pos]
            else:
                for f in val:
                    res2 = self._columns[f].get(cr, self, ids, f, user, context=context, values=res)
                    for record in res:
                        if res2:
                            record[f] = res2[record['id']]
                        else:
                            record[f] = []
        readonly = None
        for vals in res:
            for field in vals.copy():
                fobj = None
                if field in self._columns:
                    fobj = self._columns[field]

                if not fobj:
                    continue
                groups = fobj.read
                if groups:
                    edit = False
                    for group in groups:
                        module = group.split(".")[0]
                        grp = group.split(".")[1]
                        cr.execute("select count(*) from res_groups_users_rel where gid IN (select res_id from ir_model_data where name=%s and module=%s and model=%s) and uid=%s"  \
                                   (grp, module, 'res.groups', user))
                        readonly = cr.fetchall()
                        if readonly[0][0] >= 1:
                            edit = True
                            break
                        elif readonly[0][0] == 0:
                            edit = False
                        else:
                            edit = False

                    if not edit:
                        if type(vals[field]) == type([]):
                            vals[field] = []
                        elif type(vals[field]) == type(0.0):
                            vals[field] = 0
                        elif type(vals[field]) == type(''):
                            vals[field] = '=No Permission='
                        else:
                            vals[field] = False
        return res

    def perm_read(self, cr, user, ids, context=None, details=True):
        """
        Read the permission for record of the given ids

        :param cr: database cursor
        :param user: current user id
        :param ids: id or list of ids
        :param context: context arguments, like lang, time zone
        :param details: if True, \*_uid fields are replaced with the name of the user
        :return: list of ownership dictionaries for each requested record
        :rtype: list of dictionaries with the following keys:

                    * id: object id
                    * create_uid: user who created the record
                    * create_date: date when the record was created
                    * write_uid: last user who changed the record
                    * write_date: date of the last change to the record

        """
        if not context:
            context = {}
        if not ids:
            return []
        fields = ''
        uniq = isinstance(ids, (int, long))
        if uniq:
            ids = [ids]
        fields = 'id'
        if self._log_access:
            fields += ', create_uid, create_date, write_uid, write_date'
        query = 'SELECT %s FROM "%s" WHERE id IN %%s' % (fields, self._table)
        cr.execute(query, (tuple(ids),))
        res = cr.dictfetchall()
        for r in res:
            for key in r:
                r[key] = r[key] or False
                if key in ('write_uid', 'create_uid', 'uid') and details:
                    if r[key]:
                        r[key] = self.pool.get('res.users').name_get(cr, user, [r[key]])[0]
        if uniq:
            return res[ids[0]]
        return res

    def _check_concurrency(self, cr, ids, context):
        if not context:
            return
        if context.get(self.CONCURRENCY_CHECK_FIELD) and self._log_access:
            def key(oid):
                return "%s,%s" % (self._name, oid)
            santa = "(id = %s AND %s < COALESCE(write_date, create_date, now())::timestamp)"
            for i in range(0, len(ids), cr.IN_MAX):
                sub_ids = tools.flatten(((oid, context[self.CONCURRENCY_CHECK_FIELD][key(oid)])
                                          for oid in ids[i:i+cr.IN_MAX]
                                          if key(oid) in context[self.CONCURRENCY_CHECK_FIELD]))
                if sub_ids:
                    cr.execute("SELECT count(1) FROM %s WHERE %s" % (self._table, " OR ".join([santa]*(len(sub_ids)/2))), sub_ids)
                    res = cr.fetchone()
                    if res and res[0]:
                        raise except_orm('ConcurrencyException', _('Records were modified in the meanwhile'))

    def check_access_rule(self, cr, uid, ids, operation, context=None):
        """Verifies that the operation given by ``operation`` is allowed for the user
           according to ir.rules.

           :param operation: one of ``write``, ``unlink``
           :raise except_orm: * if current ir.rules do not permit this operation.
           :return: None if the operation is allowed
        """
        where_clause, where_params, tables = self.pool.get('ir.rule').domain_get(cr, uid, self._name, operation, context=context)
        if where_clause:
            where_clause = ' and ' + ' and '.join(where_clause)
            for sub_ids in cr.split_for_in_conditions(ids):
                cr.execute('SELECT ' + self._table + '.id FROM ' + ','.join(tables) +
                           ' WHERE ' + self._table + '.id IN %s' + where_clause,
                           [sub_ids] + where_params)
                if cr.rowcount != len(sub_ids):
                    raise except_orm(_('AccessError'),
                                     _('Operation prohibited by access rules (Operation: %s, Document type: %s).')
                                     % (operation, self._name))

    def unlink(self, cr, uid, ids, context=None):
        """
        Delete records with given ids

        :param cr: database cursor
        :param uid: current user id
        :param ids: id or list of ids
        :param context: (optional) context arguments, like lang, time zone
        :return: True
        :raise AccessError: * if user has no unlink rights on the requested object
                            * if user tries to bypass access rules for unlink on the requested object
        :raise UserError: if the record is default property for other records

        """
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]

        result_store = self._store_get_values(cr, uid, ids, None, context)

        self._check_concurrency(cr, ids, context)

        self.pool.get('ir.model.access').check(cr, uid, self._name, 'unlink', context=context)

        properties = self.pool.get('ir.property')
        domain = [('res_id', '=', False),
                  ('value_reference', 'in', ['%s,%s' % (self._name, i) for i in ids]),
                 ]
        if properties.search(cr, uid, domain, context=context):
            raise except_orm(_('Error'), _('Unable to delete this document because it is used as a default property'))

        wf_service = netsvc.LocalService("workflow")
        for oid in ids:
            wf_service.trg_delete(uid, self._name, oid, cr)


        self.check_access_rule(cr, uid, ids, 'unlink', context=context)
        for sub_ids in cr.split_for_in_conditions(ids):
            cr.execute('delete from ' + self._table + ' ' \
                       'where id IN %s', (sub_ids,))
        for order, object, store_ids, fields in result_store:
            if object != self._name:
                obj =  self.pool.get(object)
                cr.execute('select id from '+obj._table+' where id IN %s',(tuple(store_ids),))
                rids = map(lambda x: x[0], cr.fetchall())
                if rids:
                    obj._store_set_values(cr, uid, rids, fields, context)
        return True

    #
    # TODO: Validate
    #
    def write(self, cr, user, ids, vals, context=None):
        """
        Update records with given ids with the given field values

        :param cr: database cursor
        :param user: current user id
        :type user: integer
        :param ids: object id or list of object ids to update according to **vals**
        :param vals: field values to update, e.g {'field_name': new_field_value, ...}
        :type vals: dictionary
        :param context: (optional) context arguments, e.g. {'lang': 'en_us', 'tz': 'UTC', ...}
        :type context: dictionary
        :return: True
        :raise AccessError: * if user has no write rights on the requested object
                            * if user tries to bypass access rules for write on the requested object
        :raise ValidateError: if user tries to enter invalid value for a field that is not in selection
        :raise UserError: if a loop would be created in a hierarchy of objects a result of the operation (such as setting an object as its own parent)

        **Note**: The type of field values to pass in ``vals`` for relationship fields is specific:

            + For a many2many field, a list of tuples is expected.
              Here is the list of tuple that are accepted, with the corresponding semantics ::

                 (0, 0,  { values })    link to a new record that needs to be created with the given values dictionary
                 (1, ID, { values })    update the linked record with id = ID (write *values* on it)
                 (2, ID)                remove and delete the linked record with id = ID (calls unlink on ID, that will delete the object completely, and the link to it as well)
                 (3, ID)                cut the link to the linked record with id = ID (delete the relationship between the two objects but does not delete the target object itself)
                 (4, ID)                link to existing record with id = ID (adds a relationship)
                 (5)                    unlink all (like using (3,ID) for all linked records)
                 (6, 0, [IDs])          replace the list of linked IDs (like using (5) then (4,ID) for each ID in the list of IDs)

                 Example:
                    [(6, 0, [8, 5, 6, 4])] sets the many2many to ids [8, 5, 6, 4]

            + For a one2many field, a lits of tuples is expected.
              Here is the list of tuple that are accepted, with the corresponding semantics ::

                 (0, 0,  { values })    link to a new record that needs to be created with the given values dictionary
                 (1, ID, { values })    update the linked record with id = ID (write *values* on it)
                 (2, ID)                remove and delete the linked record with id = ID (calls unlink on ID, that will delete the object completely, and the link to it as well)

                 Example:
                    [(0, 0, {'field_name':field_value_record1, ...}), (0, 0, {'field_name':field_value_record2, ...})]

            + For a many2one field, simply use the ID of target record, which must already exist, or ``False`` to remove the link.
            + For a reference field, use a string with the model name, a comma, and the target object id (example: ``'product.product, 5'``)

        """
        readonly = None
        for field in vals.copy():
            fobj = None
            if field in self._columns:
                fobj = self._columns[field]
            else:
                fobj = self._inherit_fields[field][2]
            if not fobj:
                continue
            groups = fobj.write

            if groups:
                edit = False
                for group in groups:
                    module = group.split(".")[0]
                    grp = group.split(".")[1]
                    cr.execute("select count(*) from res_groups_users_rel where gid IN (select res_id from ir_model_data where name=%s and module=%s and model=%s) and uid=%s" \
                               (grp, module, 'res.groups', user))
                    readonly = cr.fetchall()
                    if readonly[0][0] >= 1:
                        edit = True
                        break
                    elif readonly[0][0] == 0:
                        edit = False
                    else:
                        edit = False

                if not edit:
                    vals.pop(field)

        if not context:
            context = {}
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]

        self._check_concurrency(cr, ids, context)
        self.pool.get('ir.model.access').check(cr, user, self._name, 'write', context=context)

        result = self._store_get_values(cr, user, ids, vals.keys(), context) or []

        # No direct update of parent_left/right
        vals.pop('parent_left', None)
        vals.pop('parent_right', None)

        parents_changed = []
        if self._parent_store and (self._parent_name in vals):
            # The parent_left/right computation may take up to
            # 5 seconds. No need to recompute the values if the
            # parent is the same. Get the current value of the parent
            parent_val = vals[self._parent_name]
            if parent_val:
                query = "SELECT id FROM %s WHERE id IN %%s AND (%s != %%s OR %s IS NULL)" % \
                                (self._table, self._parent_name, self._parent_name)
                cr.execute(query, (tuple(ids), parent_val))
            else:
                query = "SELECT id FROM %s WHERE id IN %%s AND (%s IS NOT NULL)" % \
                                (self._table, self._parent_name)
                cr.execute(query, (tuple(ids),))
            parents_changed = map(operator.itemgetter(0), cr.fetchall())

        upd0 = []
        upd1 = []
        upd_todo = []
        updend = []
        direct = []
        totranslate = context.get('lang', False) and (context['lang'] != 'en_US')
        for field in vals:
            if field in self._columns:
                if self._columns[field]._classic_write and not (hasattr(self._columns[field], '_fnct_inv')):
                    if (not totranslate) or not self._columns[field].translate:
                        upd0.append('"'+field+'"='+self._columns[field]._symbol_set[0])
                        upd1.append(self._columns[field]._symbol_set[1](vals[field]))
                    direct.append(field)
                else:
                    upd_todo.append(field)
            else:
                updend.append(field)
            if field in self._columns \
                    and hasattr(self._columns[field], 'selection') \
                    and vals[field]:
                if self._columns[field]._type == 'reference':
                    val = vals[field].split(',')[0]
                else:
                    val = vals[field]
                if isinstance(self._columns[field].selection, (tuple, list)):
                    if val not in dict(self._columns[field].selection):
                        raise except_orm(_('ValidateError'),
                        _('The value "%s" for the field "%s" is not in the selection') \
                                % (vals[field], field))
                else:
                    if val not in dict(self._columns[field].selection(
                        self, cr, user, context=context)):
                        raise except_orm(_('ValidateError'),
                        _('The value "%s" for the field "%s" is not in the selection') \
                                % (vals[field], field))

        if self._log_access:
            upd0.append('write_uid=%s')
            upd0.append('write_date=now()')
            upd1.append(user)

        if len(upd0):
            self.check_access_rule(cr, user, ids, 'write', context=context)
            for sub_ids in cr.split_for_in_conditions(ids):
                cr.execute('update ' + self._table + ' set ' + ','.join(upd0) + ' ' \
                           'where id IN %s', upd1 + [sub_ids])

            if totranslate:
                # TODO: optimize
                for f in direct:
                    if self._columns[f].translate:
                        src_trans = self.pool.get(self._name).read(cr,user,ids,[f])[0][f]
                        if not src_trans:
                            src_trans = vals[f]
                            # Inserting value to DB
                            self.write(cr, user, ids, {f:vals[f]})
                        self.pool.get('ir.translation')._set_ids(cr, user, self._name+','+f, 'model', context['lang'], ids, vals[f], src_trans)


        # call the 'set' method of fields which are not classic_write
        upd_todo.sort(lambda x, y: self._columns[x].priority-self._columns[y].priority)

        # default element in context must be removed when call a one2many or many2many
        rel_context = context.copy()
        for c in context.items():
            if c[0].startswith('default_'):
                del rel_context[c[0]]

        for field in upd_todo:
            for id in ids:
                result += self._columns[field].set(cr, self, id, field, vals[field], user, context=rel_context) or []

        for table in self._inherits:
            col = self._inherits[table]
            nids = []
            for sub_ids in cr.split_for_in_conditions(ids):
                cr.execute('select distinct "'+col+'" from "'+self._table+'" ' \
                           'where id IN %s', (sub_ids,))
                nids.extend([x[0] for x in cr.fetchall()])

            v = {}
            for val in updend:
                if self._inherit_fields[val][0] == table:
                    v[val] = vals[val]
            self.pool.get(table).write(cr, user, nids, v, context)

        self._validate(cr, user, ids, context)

        # TODO: use _order to set dest at the right position and not first node of parent
        # We can't defer parent_store computation because the stored function
        # fields that are computer may refer (directly or indirectly) to
        # parent_left/right (via a child_of domain)
        if parents_changed:
            if self.pool._init:
                self.pool._init_parent[self._name]=True
            else:
                order = self._parent_order or self._order
                parent_val = vals[self._parent_name]
                if parent_val:
                    clause, params = '%s=%%s' % (self._parent_name,), (parent_val,)
                else:
                    clause, params = '%s IS NULL' % (self._parent_name,), ()
                cr.execute('SELECT parent_right, id FROM %s WHERE %s ORDER BY %s' % (self._table, clause, order), params)
                parents = cr.fetchall()

                for id in parents_changed:
                    cr.execute('SELECT parent_left, parent_right FROM %s WHERE id=%%s' % (self._table,), (id,))
                    pleft, pright = cr.fetchone()
                    distance = pright - pleft + 1

                    # Find Position of the element
                    position = None
                    for (parent_pright, parent_id) in parents:
                        if parent_id == id:
                            break
                        position = parent_pright+1

                    # It's the first node of the parent
                    if not position:
                        if not parent_val:
                            position = 1
                        else:
                            cr.execute('select parent_left from '+self._table+' where id=%s', (parent_val,))
                            position = cr.fetchone()[0]+1

                    if pleft < position <= pright:
                        raise except_orm(_('UserError'), _('Recursivity Detected.'))

                    if pleft < position:
                        cr.execute('update '+self._table+' set parent_left=parent_left+%s where parent_left>=%s', (distance, position))
                        cr.execute('update '+self._table+' set parent_right=parent_right+%s where parent_right>=%s', (distance, position))
                        cr.execute('update '+self._table+' set parent_left=parent_left+%s, parent_right=parent_right+%s where parent_left>=%s and parent_left<%s', (position-pleft,position-pleft, pleft, pright))
                    else:
                        cr.execute('update '+self._table+' set parent_left=parent_left+%s where parent_left>=%s', (distance, position))
                        cr.execute('update '+self._table+' set parent_right=parent_right+%s where parent_right>=%s', (distance, position))
                        cr.execute('update '+self._table+' set parent_left=parent_left-%s, parent_right=parent_right-%s where parent_left>=%s and parent_left<%s', (pleft-position+distance,pleft-position+distance, pleft+distance, pright+distance))

        result += self._store_get_values(cr, user, ids, vals.keys(), context)
        result.sort()

        done = {}
        for order, object, ids, fields in result:
            key = (object,tuple(fields))
            done.setdefault(key, {})
            # avoid to do several times the same computation
            todo = []
            for id in ids:
                if id not in done[key]:
                    done[key][id] = True
                    todo.append(id)
            self.pool.get(object)._store_set_values(cr, user, todo, fields, context)

        wf_service = netsvc.LocalService("workflow")
        for id in ids:
            wf_service.trg_write(user, self._name, id, cr)
        return True

    #
    # TODO: Should set perm to user.xxx
    #
    def create(self, cr, user, vals, context=None):
        """
        Create new record with specified value

        :param cr: database cursor
        :param user: current user id
        :type user: integer
        :param vals: field values for new record, e.g {'field_name': field_value, ...}
        :type vals: dictionary
        :param context: optional context arguments, e.g. {'lang': 'en_us', 'tz': 'UTC', ...}
        :type context: dictionary
        :return: id of new record created
        :raise AccessError: * if user has no create rights on the requested object
                            * if user tries to bypass access rules for create on the requested object
        :raise ValidateError: if user tries to enter invalid value for a field that is not in selection
        :raise UserError: if a loop would be created in a hierarchy of objects a result of the operation (such as setting an object as its own parent)

        **Note**: The type of field values to pass in ``vals`` for relationship fields is specific.
        Please see the description of the :py:meth:`~osv.osv.osv.write` method for details about the possible values and how
        to specify them.

        """
        if not context:
            context = {}
        self.pool.get('ir.model.access').check(cr, user, self._name, 'create', context=context)

        vals = self._add_missing_default_values(cr, user, vals, context)

        tocreate = {}
        for v in self._inherits:
            if self._inherits[v] not in vals:
                tocreate[v] = {}
            else:
                tocreate[v] = {'id' : vals[self._inherits[v]]}
        (upd0, upd1, upd2) = ('', '', [])
        upd_todo = []
        for v in vals.keys():
            if v in self._inherit_fields:
                (table, col, col_detail) = self._inherit_fields[v]
                tocreate[table][v] = vals[v]
                del vals[v]
            else:
                if (v not in self._inherit_fields) and (v not in self._columns):
                    del vals[v]

        # Try-except added to filter the creation of those records whose filds are readonly.
        # Example : any dashboard which has all the fields readonly.(due to Views(database views))
        try:
            cr.execute("SELECT nextval('"+self._sequence+"')")
        except:
            raise except_orm(_('UserError'),
                        _('You cannot perform this operation. New Record Creation is not allowed for this object as this object is for reporting purpose.'))

        id_new = cr.fetchone()[0]
        for table in tocreate:
            if self._inherits[table] in vals:
                del vals[self._inherits[table]]

            record_id = tocreate[table].pop('id', None)

            if record_id is None or not record_id:
                record_id = self.pool.get(table).create(cr, user, tocreate[table], context=context)
            else:
                self.pool.get(table).write(cr, user, [record_id], tocreate[table], context=context)

            upd0 += ','+self._inherits[table]
            upd1 += ',%s'
            upd2.append(record_id)

        #Start : Set bool fields to be False if they are not touched(to make search more powerful)
        bool_fields = [x for x in self._columns.keys() if self._columns[x]._type=='boolean']

        for bool_field in bool_fields:
            if bool_field not in vals:
                vals[bool_field] = False
        #End
        for field in vals.copy():
            fobj = None
            if field in self._columns:
                fobj = self._columns[field]
            else:
                fobj = self._inherit_fields[field][2]
            if not fobj:
                continue
            groups = fobj.write
            if groups:
                edit = False
                for group in groups:
                    module = group.split(".")[0]
                    grp = group.split(".")[1]
                    cr.execute("select count(*) from res_groups_users_rel where gid IN (select res_id from ir_model_data where name='%s' and module='%s' and model='%s') and uid=%s" % \
                               (grp, module, 'res.groups', user))
                    readonly = cr.fetchall()
                    if readonly[0][0] >= 1:
                        edit = True
                        break
                    elif readonly[0][0] == 0:
                        edit = False
                    else:
                        edit = False

                if not edit:
                    vals.pop(field)
        for field in vals:
            if self._columns[field]._classic_write:
                upd0 = upd0 + ',"' + field + '"'
                upd1 = upd1 + ',' + self._columns[field]._symbol_set[0]
                upd2.append(self._columns[field]._symbol_set[1](vals[field]))
            else:
                if not isinstance(self._columns[field], fields.related):
                    upd_todo.append(field)
            if field in self._columns \
                    and hasattr(self._columns[field], 'selection') \
                    and vals[field]:
                if self._columns[field]._type == 'reference':
                    val = vals[field].split(',')[0]
                else:
                    val = vals[field]
                if isinstance(self._columns[field].selection, (tuple, list)):
                    if val not in dict(self._columns[field].selection):
                        raise except_orm(_('ValidateError'),
                        _('The value "%s" for the field "%s" is not in the selection') \
                                % (vals[field], field))
                else:
                    if val not in dict(self._columns[field].selection(
                        self, cr, user, context=context)):
                        raise except_orm(_('ValidateError'),
                        _('The value "%s" for the field "%s" is not in the selection') \
                                % (vals[field], field))
        if self._log_access:
            upd0 += ',create_uid,create_date'
            upd1 += ',%s,now()'
            upd2.append(user)
        cr.execute('insert into "'+self._table+'" (id'+upd0+") values ("+str(id_new)+upd1+')', tuple(upd2))
        self.check_access_rule(cr, user, [id_new], 'create', context=context)
        upd_todo.sort(lambda x, y: self._columns[x].priority-self._columns[y].priority)

        if self._parent_store and not context.get('defer_parent_store_computation'):
            if self.pool._init:
                self.pool._init_parent[self._name]=True
            else:
                parent = vals.get(self._parent_name, False)
                if parent:
                    cr.execute('select parent_right from '+self._table+' where '+self._parent_name+'=%s order by '+(self._parent_order or self._order), (parent,))
                    pleft_old = None
                    result_p = cr.fetchall()
                    for (pleft,) in result_p:
                        if not pleft:
                            break
                        pleft_old = pleft
                    if not pleft_old:
                        cr.execute('select parent_left from '+self._table+' where id=%s', (parent,))
                        pleft_old = cr.fetchone()[0]
                    pleft = pleft_old
                else:
                    cr.execute('select max(parent_right) from '+self._table)
                    pleft = cr.fetchone()[0] or 0
                cr.execute('update '+self._table+' set parent_left=parent_left+2 where parent_left>%s', (pleft,))
                cr.execute('update '+self._table+' set parent_right=parent_right+2 where parent_right>%s', (pleft,))
                cr.execute('update '+self._table+' set parent_left=%s,parent_right=%s where id=%s', (pleft+1,pleft+2,id_new))

        # default element in context must be remove when call a one2many or many2many
        rel_context = context.copy()
        for c in context.items():
            if c[0].startswith('default_'):
                del rel_context[c[0]]

        result = []
        for field in upd_todo:
            result += self._columns[field].set(cr, self, id_new, field, vals[field], user, rel_context) or []
        self._validate(cr, user, [id_new], context)

        if not context.get('no_store_function', False):
            result += self._store_get_values(cr, user, [id_new], vals.keys(), context)
            result.sort()
            done = []
            for order, object, ids, fields2 in result:
                if not (object, ids, fields2) in done:
                    self.pool.get(object)._store_set_values(cr, user, ids, fields2, context)
                    done.append((object, ids, fields2))

        if self._log_create and not (context and context.get('no_store_function', False)):
            message = self._description + \
                " '" + \
                self.name_get(cr, user, [id_new], context=context)[0][1] + \
                "' "+ _("created.")
            self.log(cr, user, id_new, message, True, context=context)
        wf_service = netsvc.LocalService("workflow")
        wf_service.trg_create(user, self._name, id_new, cr)
        return id_new

    def _store_get_values(self, cr, uid, ids, fields, context):
        result = {}
        fncts = self.pool._store_function.get(self._name, [])
        for fnct in range(len(fncts)):
            if fncts[fnct][3]:
                ok = False
                if not fields:
                    ok = True
                for f in (fields or []):
                    if f in fncts[fnct][3]:
                        ok = True
                        break
                if not ok:
                    continue

            result.setdefault(fncts[fnct][0], {})

            # uid == 1 for accessing objects having rules defined on store fields
            ids2 = fncts[fnct][2](self,cr, 1, ids, context)
            for id in filter(None, ids2):
                result[fncts[fnct][0]].setdefault(id, [])
                result[fncts[fnct][0]][id].append(fnct)
        dict = {}
        for object in result:
            k2 = {}
            for id,fnct in result[object].items():
                k2.setdefault(tuple(fnct), [])
                k2[tuple(fnct)].append(id)
            for fnct,id in k2.items():
                dict.setdefault(fncts[fnct[0]][4],[])
                dict[fncts[fnct[0]][4]].append((fncts[fnct[0]][4],object,id,map(lambda x: fncts[x][1], fnct)))
        result2 = []
        tmp = dict.keys()
        tmp.sort()
        for k in tmp:
            result2+=dict[k]
        return result2

    def _store_set_values(self, cr, uid, ids, fields, context):
        if not ids:
            return True
        field_flag = False
        field_dict = {}
        if self._log_access:
            cr.execute('select id,write_date from '+self._table+' where id IN %s',(tuple(ids),))
            res = cr.fetchall()
            for r in res:
                if r[1]:
                    field_dict.setdefault(r[0], [])
                    res_date = time.strptime((r[1])[:19], '%Y-%m-%d %H:%M:%S')
                    write_date = datetime.datetime.fromtimestamp(time.mktime(res_date))
                    for i in self.pool._store_function.get(self._name, []):
                        if i[5]:
                            up_write_date = write_date + datetime.timedelta(hours=i[5])
                            if datetime.datetime.now() < up_write_date:
                                if i[1] in fields:
                                    field_dict[r[0]].append(i[1])
                                    if not field_flag:
                                        field_flag = True
        todo = {}
        keys = []
        for f in fields:
            if self._columns[f]._multi not in keys:
                keys.append(self._columns[f]._multi)
            todo.setdefault(self._columns[f]._multi, [])
            todo[self._columns[f]._multi].append(f)
        for key in keys:
            val = todo[key]
            if key:
                # uid == 1 for accessing objects having rules defined on store fields
                result = self._columns[val[0]].get(cr, self, ids, val, 1, context=context)
                for id,value in result.items():
                    if field_flag:
                        for f in value.keys():
                            if f in field_dict[id]:
                                value.pop(f)
                    upd0 = []
                    upd1 = []
                    for v in value:
                        if v not in val:
                            continue
                        if self._columns[v]._type in ('many2one', 'one2one'):
                            try:
                                value[v] = value[v][0]
                            except:
                                pass
                        upd0.append('"'+v+'"='+self._columns[v]._symbol_set[0])
                        upd1.append(self._columns[v]._symbol_set[1](value[v]))
                    upd1.append(id)
                    if upd0 and upd1:
                        cr.execute('update "' + self._table + '" set ' + \
                            string.join(upd0, ',') + ' where id = %s', upd1)

            else:
                for f in val:
                    # uid == 1 for accessing objects having rules defined on store fields
                    result = self._columns[f].get(cr, self, ids, f, 1, context=context)
                    for r in result.keys():
                        if field_flag:
                            if r in field_dict.keys():
                                if f in field_dict[r]:
                                    result.pop(r)
                    for id,value in result.items():
                        if self._columns[f]._type in ('many2one', 'one2one'):
                            try:
                                value = value[0]
                            except:
                                pass
                        cr.execute('update "' + self._table + '" set ' + \
                            '"'+f+'"='+self._columns[f]._symbol_set[0] + ' where id = %s', (self._columns[f]._symbol_set[1](value),id))
        return True

    #
    # TODO: Validate
    #
    def perm_write(self, cr, user, ids, fields, context=None):
        raise NotImplementedError(_('This method does not exist anymore'))

    # TODO: ameliorer avec NULL
    def _where_calc(self, cr, user, args, active_test=True, context=None):
        """Computes the WHERE clause needed to implement an OpenERP domain.
        :param args: the domain to compute
        :type args: list
        :param active_test: whether the default filtering of records with ``active``
                            field set to ``False`` should be applied. 
        :return: tuple with 3 elements: (where_clause, where_clause_params, tables) where
                 ``where_clause`` contains a list of where clause elements (to be joined with 'AND'),
                 ``where_clause_params`` is a list of parameters to be passed to the db layer
                 for the where_clause expansion, and ``tables`` is the list of double-quoted
                 table names that need to be included in the FROM clause. 
        :rtype: tuple 
        """
        if not context:
            context = {}
        args = args[:]
        # if the object has a field named 'active', filter out all inactive
        # records unless they were explicitely asked for
        if 'active' in self._columns and (active_test and context.get('active_test', True)):
            if args:
                active_in_args = False
                for a in args:
                    if a[0] == 'active':
                        active_in_args = True
                if not active_in_args:
                    args.insert(0, ('active', '=', 1))
            else:
                args = [('active', '=', 1)]

        if args:
            import expression
            e = expression.expression(args)
            e.parse(cr, user, self, context)
            tables = e.get_tables()
            qu1, qu2 = e.to_sql()
            qu1 = qu1 and [qu1] or []
        else:
            qu1, qu2, tables = [], [], ['"%s"' % self._table]

        return (qu1, qu2, tables)

    def _check_qorder(self, word):
        if not regex_order.match(word):
            raise except_orm(_('AccessError'), _('Bad query.'))
        return True

    def _apply_ir_rules(self, cr, uid, where_clause, where_clause_params, tables, mode='read', model_name=None, context=None):
        """Add what's missing in ``where_clause``, ``where_params``, ``tables`` to implement
           all appropriate ir.rules (on the current object but also from it's _inherits parents)

           :param where_clause: list with current elements of the WHERE clause (strings)
           :param where_clause_params: list with parameters for ``where_clause``
           :param tables: list with double-quoted names of the tables that are joined
                          in ``where_clause``
           :param model_name: optional name of the model whose ir.rules should be applied (default:``self._name``)
                              This could be useful for inheritance for example, but there is no provision to include
                              the appropriate JOIN for linking the current model to the one referenced in model_name. 
           :return: True if additional clauses where applied.
        """
        added_clause, added_params, added_tables  = self.pool.get('ir.rule').domain_get(cr, uid, model_name or self._name, mode, context=context)
        if added_clause:
            where_clause += added_clause
            where_clause_params += added_params
            for table in added_tables:
                if table not in tables:
                    tables.append(table)
            return True
        return False

    def _search(self, cr, user, args, offset=0, limit=None, order=None, context=None, count=False, access_rights_uid=None):
        """
        Private implementation of search() method, allowing specifying the uid to use for the access right check. 
        This is useful for example when filling in the selection list for a drop-down and avoiding access rights errors,
        by specifying ``access_rights_uid=1`` to bypass access rights check, but not ir.rules!
        This is ok at the security level because this method is private and not callable through XML-RPC.
        
        :param access_rights_uid: optional user ID to use when checking access rights
                                  (not for ir.rules, this is only for ir.model.access)
        """
        if context is None:
            context = {}
        self.pool.get('ir.model.access').check(cr, access_rights_uid or user, self._name, 'read', context=context)
        # compute the where, order by, limit and offset clauses
        (where_clause, where_clause_params, tables) = self._where_calc(cr, user, args, context=context)

        # apply direct ir.rules from current model
        self._apply_ir_rules(cr, user, where_clause, where_clause_params, tables, 'read', context=context)

        # then apply the ir.rules from the parents (through _inherits), adding the appropriate JOINs if needed
        for inherited_model in self._inherits:
            previous_tables = list(tables)
            if self._apply_ir_rules(cr, user, where_clause, where_clause_params, tables, 'read', model_name=inherited_model, context=context):
                # if some rules were applied, need to add the missing JOIN for them to make sense, passing the previous
                # list of table in case the inherited table was not in the list before (as that means the corresponding
                # JOIN(s) was(were) not present)
                self._inherits_join_add(inherited_model, previous_tables, where_clause)
                tables = list(set(tables).union(set(previous_tables)))

        where = where_clause

        order_by = self._order
        if order:
            self._check_qorder(order)
            o = order.split(' ')[0]
            if (o in self._columns):
                # we can only do efficient sort if the fields is stored in database
                if getattr(self._columns[o], '_classic_read'):
                    order_by = order
            elif (o in self._inherit_fields):
                parent_obj = self.pool.get(self._inherit_fields[o][0])
                if getattr(parent_obj._columns[o], '_classic_read'):
                    # Allowing inherits'ed field for server side sorting, if they can be sorted by the dbms
                    inherited_tables, inherit_join, order_by = self._inherits_join_calc(o, tables, where_clause)

        limit_str = limit and ' limit %d' % limit or ''
        offset_str = offset and ' offset %d' % offset or ''
        
        if where:
            where_str = " WHERE %s" % " AND ".join(where)
        else:
            where_str = ""

        if count:
            cr.execute('select count(%s.id) from ' % self._table +
                    ','.join(tables) + where_str + limit_str + offset_str, where_clause_params)
            res = cr.fetchall()
            return res[0][0]
        cr.execute('select %s.id from ' % self._table + ','.join(tables) + where_str +' order by '+order_by+limit_str+offset_str, where_clause_params)
        res = cr.fetchall()
        return [x[0] for x in res]

    # returns the different values ever entered for one field
    # this is used, for example, in the client when the user hits enter on
    # a char field
    def distinct_field_get(self, cr, uid, field, value, args=None, offset=0, limit=None):
        if not args:
            args = []
        if field in self._inherit_fields:
            return self.pool.get(self._inherit_fields[field][0]).distinct_field_get(cr, uid, field, value, args, offset, limit)
        else:
            return self._columns[field].search(cr, self, args, field, value, offset, limit, uid)

    def name_get(self, cr, user, ids, context=None):
        """

        :param cr: database cursor
        :param user: current user id
        :type user: integer
        :param ids: list of ids
        :param context: context arguments, like lang, time zone
        :type context: dictionary
        :return: tuples with the text representation of requested objects for to-many relationships

        """
        if not context:
            context = {}
        if not ids:
            return []
        if isinstance(ids, (int, long)):
            ids = [ids]
        return [(r['id'], tools.ustr(r[self._rec_name])) for r in self.read(cr, user, ids,
            [self._rec_name], context, load='_classic_write')]

    # private implementation of name_search, allows passing a dedicated user for the name_get part to
    # solve some access rights issues
    def _name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100, name_get_uid=None):
        if args is None:
            args = []
        if context is None:
            context = {}
        args = args[:]
        if name:
            args += [(self._rec_name, operator, name)]
        access_rights_uid = name_get_uid or user
        ids = self._search(cr, user, args, limit=limit, context=context, access_rights_uid=access_rights_uid)
        res = self.name_get(cr, access_rights_uid, ids, context)
        return res

    def name_search(self, cr, user, name='', args=None, operator='ilike', context=None, limit=100):
        """

        :param cr: database cursor
        :param user: current user id
        :param name: object name to search
        :param args: list of tuples specifying search criteria [('field_name', 'operator', 'value'), ...]
        :param operator: operator for search criterion
        :param context: context arguments, like lang, time zone
        :type context: dictionary
        :param limit: optional max number of records to return
        :return: list of object names matching the search criteria, used to provide completion for to-many relationships

        This method is equivalent of :py:meth:`~osv.osv.osv.search` on **name** + :py:meth:`~osv.osv.osv.name_get` on the result.
        See :py:meth:`~osv.osv.osv.search` for an explanation of the possible values for the search domain specified in **args**.

        """
        return self._name_search(cr, user, name, args, operator, context, limit)

    def copy_data(self, cr, uid, id, default=None, context=None):
        """
        Copy given record's data with all its fields values

        :param cr: database cursor
        :param user: current user id
        :param id: id of the record to copy
        :param default: field values to override in the original values of the copied record
        :type default: dictionary
        :param context: context arguments, like lang, time zone
        :type context: dictionary
        :return: dictionary containing all the field values
        """

        if context is None:
            context = {}
        if default is None:
            default = {}
        if 'state' not in default:
            if 'state' in self._defaults:
                if callable(self._defaults['state']):
                    default['state'] = self._defaults['state'](self, cr, uid, context)
                else:
                    default['state'] = self._defaults['state']

        context_wo_lang = context
        if 'lang' in context:
            del context_wo_lang['lang']
        data = self.read(cr, uid, [id], context=context_wo_lang)[0]

        fields = self.fields_get(cr, uid, context=context)
        for f in fields:
            ftype = fields[f]['type']

            if self._log_access and f in ('create_date', 'create_uid', 'write_date', 'write_uid'):
                del data[f]

            if f in default:
                data[f] = default[f]
            elif ftype == 'function':
                del data[f]
            elif ftype == 'many2one':
                try:
                    data[f] = data[f] and data[f][0]
                except:
                    pass
            elif ftype in ('one2many', 'one2one'):
                res = []
                rel = self.pool.get(fields[f]['relation'])
                if data[f]:
                    # duplicate following the order of the ids
                    # because we'll rely on it later for copying
                    # translations in copy_translation()!
                    data[f].sort()
                    for rel_id in data[f]:
                        # the lines are first duplicated using the wrong (old)
                        # parent but then are reassigned to the correct one thanks
                        # to the (0, 0, ...)
                        d = rel.copy_data(cr, uid, rel_id, context=context)
                        res.append((0, 0, d))
                data[f] = res
            elif ftype == 'many2many':
                data[f] = [(6, 0, data[f])]

        del data['id']

        # make sure we don't break the current parent_store structure and
        # force a clean recompute!
        for parent_column in ['parent_left', 'parent_right']:
            data.pop(parent_column, None)

        for v in self._inherits:
            del data[self._inherits[v]]
        return data

    def copy_translations(self, cr, uid, old_id, new_id, context=None):
        trans_obj = self.pool.get('ir.translation')
        fields = self.fields_get(cr, uid, context=context)

        translation_records = []
        for field_name, field_def in fields.items():
            # we must recursively copy the translations for o2o and o2m
            if field_def['type'] in ('one2one', 'one2many'):
                target_obj = self.pool.get(field_def['relation'])
                old_record, new_record  = self.read(cr, uid, [old_id, new_id], [field_name], context=context)
                # here we rely on the order of the ids to match the translations
                # as foreseen in copy_data()
                old_childs = sorted(old_record[field_name])
                new_childs = sorted(new_record[field_name])
                for (old_child, new_child) in zip(old_childs, new_childs):
                    # recursive copy of translations here
                    target_obj.copy_translations(cr, uid, old_child, new_child, context=context)
            # and for translatable fields we keep them for copy
            elif field_def.get('translate'):
                trans_name = ''
                if field_name in self._columns:
                    trans_name = self._name + "," + field_name
                elif field_name in self._inherit_fields:
                    trans_name = self._inherit_fields[field_name][0] + "," + field_name
                if trans_name:
                    trans_ids = trans_obj.search(cr, uid, [
                            ('name', '=', trans_name),
                            ('res_id','=', old_id)
                    ])
                    translation_records.extend(trans_obj.read(cr,uid,trans_ids,context=context))

        for record in translation_records:
            del record['id']
            record['res_id'] = new_id
            trans_obj.create(cr, uid, record, context=context)


    def copy(self, cr, uid, id, default=None, context=None):
        """
        Duplicate record with given id updating it with default values

        :param cr: database cursor
        :param uid: current user id
        :param id: id of the record to copy
        :param default: dictionary of field values to override in the original values of the copied record, e.g: ``{'field_name': overriden_value, ...}``
        :type default: dictionary
        :param context: context arguments, like lang, time zone
        :type context: dictionary
        :return: True

        """
        data = self.copy_data(cr, uid, id, default, context)
        new_id = self.create(cr, uid, data, context)
        self.copy_translations(cr, uid, id, new_id, context)
        return new_id

    def exists(self, cr, uid, ids, context=None):
        if type(ids) in (int,long):
            ids = [ids]
        query = 'SELECT count(1) FROM "%s"' % (self._table)
        cr.execute(query + "WHERE ID IN %s", (tuple(ids),))
        return cr.fetchone()[0] == len(ids)

    def check_recursion(self, cr, uid, ids, parent=None):
        """
        Verifies that there is no loop in a hierarchical structure of records,
        by following the parent relationship using the **parent** field until a loop
        is detected or until a top-level record is found.

        :param cr: database cursor
        :param uid: current user id
        :param ids: list of ids of records to check
        :param parent: optional parent field name (default: ``self._parent_name = parent_id``)
        :return: **True** if the operation can proceed safely, or **False** if an infinite loop is detected.
        """

        if not parent:
            parent = self._parent_name
        ids_parent = ids[:]
        query = 'SELECT distinct "%s" FROM "%s" WHERE id IN %%s' % (parent, self._table)
        while ids_parent:
            ids_parent2 = []
            for i in range(0, len(ids), cr.IN_MAX):
                sub_ids_parent = ids_parent[i:i+cr.IN_MAX]
                cr.execute(query, (tuple(sub_ids_parent),))
                ids_parent2.extend(filter(None, map(lambda x: x[0], cr.fetchall())))
            ids_parent = ids_parent2
            for i in ids_parent:
                if i in ids:
                    return False
        return True

    def get_xml_id(self, cr, uid, ids, *args, **kwargs):
        """Find out the XML ID of any database record, if there
        is one. This method works as a possible implementation
        for a function field, to be able to add it to any
        model object easily, referencing it as ``osv.osv.get_xml_id``.

        **Synopsis**: ``get_xml_id(cr, uid, ids) -> { 'id': 'module.xml_id' }``

        :return: the fully qualified XML ID of the given object,
                 defaulting to an empty string when there's none
                 (to be usable as a function field).
        """
        result = dict.fromkeys(ids, '')
        model_data_obj = self.pool.get('ir.model.data')
        data_ids = model_data_obj.search(cr,uid,
                [('model','=',self._name),('res_id','in',ids)])
        data_results = model_data_obj.read(cr,uid,data_ids,
                ['name','module','res_id'])
        for record in data_results:
            result[record['res_id']] = '%(module)s.%(name)s' % record
        return result

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

