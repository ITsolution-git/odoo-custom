# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import psycopg2

_schema = logging.getLogger('odoo.schema')

def table_exists(cr, tablename):
    """ Return whether the given table exists. """
    query = "SELECT 1 FROM pg_class WHERE relkind IN ('r','v') AND relname=%s"
    cr.execute(query, (tablename,))
    return cr.rowcount

def table_kind(cr, tablename):
    """ Return the kind of a table: 'r' for ordinary tables, 'v' for views. """
    cr.execute("SELECT relkind FROM pg_class WHERE relname=%s", (tablename,))
    return cr.fetchone()[0] if cr.rowcount else None

def create_model_table(cr, tablename, comment=None):
    """ Create the table for a model. """
    cr.execute('CREATE TABLE "{}" (id SERIAL NOT NULL, PRIMARY KEY(id))'.format(tablename))
    if comment:
        cr.execute('COMMENT ON TABLE "{}" IS %s'.format(tablename), (comment,))
    _schema.debug("Table %r: created", tablename)

def table_columns(cr, tablename):
    """ Return a dict mapping column names to their configuration. The latter is
        a dict with the following keys: `relname` (table name), `attname`
        (column name), `attlen`, `atttypmod`, `attnotnull` (whether it has a NOT
        NULL constraint), `atthasdef` (whether it has a default value),
        `typname` (data type name), `size` (varchar size).
    """
    # attlen is the number of bytes necessary to represent the type when the
    # type has a fixed size. If the type has a varying size attlen is -1 and
    # atttypmod is the size limit + 4, or -1 if there is no limit.
    query = """ SELECT c.relname, a.attname, a.attlen, a.atttypmod,
                       a.attnotnull, a.atthasdef, t.typname,
                       CASE WHEN a.attlen=-1 THEN (
                           CASE WHEN a.atttypmod=-1 THEN 0 ELSE a.atttypmod-4 END
                       ) ELSE a.attlen END as size
                FROM pg_class c, pg_attribute a, pg_type t
                WHERE c.relname=%s AND c.oid=a.attrelid AND a.atttypid=t.oid """
    cr.execute(query, (tablename,))
    return {row['attname']: row for row in cr.dictfetchall()}

def column_exists(cr, tablename, columnname):
    """ Return whether the given column exists. """
    query = """ SELECT 1 FROM pg_class c, pg_attribute a
                WHERE c.relname=%s AND a.attname=%s AND c.oid=a.attrelid """
    cr.execute(query, (tablename, columnname))
    return cr.rowcount

def create_column(cr, tablename, columnname, columntype, comment=None):
    """ Create a column with the given type. """
    cr.execute('ALTER TABLE "{}" ADD COLUMN "{}" {}'.format(tablename, columnname, columntype))
    if comment:
        cr.execute('COMMENT ON COLUMN "{}"."{}" IS %s'.format(tablename, columnname), (comment,))
    _schema.debug("Table %r: added column %r of type %s", tablename, columnname, columntype)

def rename_column(cr, tablename, columnname1, columnname2):
    """ Rename the given column. """
    cr.execute('ALTER TABLE "{}" RENAME COLUMN "{}" TO "{}"'.format(tablename, columnname1, columnname2))
    _schema.debug("Table %r: renamed column %r to %r", tablename, columnname1, columnname2)

def convert_column(cr, tablename, columnname, columntype):
    """ Convert the column to the given type. """
    try:
        with cr.savepoint():
            cr.execute('ALTER TABLE "{}" ALTER COLUMN "{}" TYPE {}'.format(tablename, columnname, columntype),
                       log_exceptions=False)
    except psycopg2.NotSupportedError:
        # can't do inplace change -> use a casted temp column
        query = 'ALTER TABLE "{0}" RENAME COLUMN "{1}" TO __temp_type_cast; ' \
                'ALTER TABLE "{0}" ADD COLUMN "{1}" {2}; ' \
                'UPDATE "{0}" SET "{1}"= __temp_type_cast::{2}' \
                'ALTER TABLE "{0}" DROP COLUMN  __temp_type_cast CASCADE'
        cr.execute(query.format(tablename, columntype, columntype))
    _schema.debug("Table %r: column %r changed to type %s", tablename, columntype, columntype)

def set_not_null(cr, tablename, columnname):
    """ Add a NOT NULL constraint on the given column. """
    query = 'ALTER TABLE "{}" ALTER COLUMN "{}" SET NOT NULL'.format(tablename, columnname)
    try:
        with cr.savepoint():
            cr.execute(query)
            _schema.debug("Table %r: column %r: added constraint NOT NULL", tablename, columnname)
    except Exception:
        msg = "Table %r: unable to set NOT NULL on column %r!\n" \
              "If you want to have it, you should update the records and execute manually:\n%s"
        _schema.warning(msg, tablename, columnname, query, exc_info=True)

def drop_not_null(cr, tablename, columnname):
    """ Drop the NOT NULL constraint on the given column. """
    cr.execute('ALTER TABLE "{}" ALTER COLUMN "{}" DROP NOT NULL'.format(tablename, columnname))
    _schema.debug("Table %r: column %r: dropped constraint NOT NULL", tablename, columnname)

def constraint_definition(cr, constraintname):
    """ Return the given constraint's definition. """
    cr.execute("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname=%s", (constraintname,))
    return cr.fetchone()[0] if cr.rowcount else None

def add_constraint(cr, tablename, constraintname, definition):
    """ Add a constraint on the given table. """
    query = 'ALTER TABLE "{}" ADD CONSTRAINT "{}" {}'.format(tablename, constraintname, definition)
    try:
        with cr.savepoint():
            cr.execute(query)
            _schema.debug("Table %r: added constraint %r as %s", tablename, constraintname, definition)
    except Exception:
        msg = "Table %r: unable to add constraint %r!\n" \
              "If you want to have it, you should update the records and execute manually:\n%s"
        _schema.warning(msg, tablename, constraintname, query, exc_info=True)

def drop_constraint(cr, tablename, constraintname):
    """ drop the given constraint. """
    try:
        with cr.savepoint():
            cr.execute('ALTER TABLE "{}" DROP CONSTRAINT "{}"'.format(tablename, constraintname))
            _schema.debug("Table %r: dropped constraint %r", tablename, constraintname)
    except Exception:
        _schema.warning("Table %r: unable to drop constraint %r!", tablename, constraintname)

def index_exists(cr, indexname):
    """ Return whether the given index exists. """
    cr.execute("SELECT 1 FROM pg_indexes WHERE indexname=%s", (indexname,))
    return cr.rowcount

def create_index(cr, indexname, tablename, expressions):
    """ Create the given index unless it exists. """
    if index_exists(cr, indexname):
        return
    args = ', '.join(expressions)
    cr.execute('CREATE INDEX "{}" ON "{}" ({})'.format(indexname, tablename, args))
    _schema.debug("Table %r: created index %r (%s)", tablename, indexname, args)

def create_unique_index(cr, indexname, tablename, expressions):
    """ Create the given index unless it exists. """
    if index_exists(cr, indexname):
        return
    args = ', '.join(expressions)
    cr.execute('CREATE UNIQUE INDEX "{}" ON "{}" ({})'.format(indexname, tablename, args))
    _schema.debug("Table %r: created index %r (%s)", tablename, indexname, args)

def drop_index(cr, indexname, tablename):
    """ Drop the given index if it exists. """
    cr.execute('DROP INDEX IF EXISTS "{}"'.format(indexname))
    _schema.debug("Table %r: dropped index %r", tablename, indexname)

def drop_view_if_exists(cr, viewname):
    cr.execute("DROP view IF EXISTS %s CASCADE" % (viewname,))
    cr.commit()

def escape_psql(to_escape):
    return to_escape.replace('\\', r'\\').replace('%', '\%').replace('_', '\_')

def pg_varchar(size=0):
    """ Returns the VARCHAR declaration for the provided size:

    * If no size (or an empty or negative size is provided) return an
      'infinite' VARCHAR
    * Otherwise return a VARCHAR(n)

    :type int size: varchar size, optional
    :rtype: str
    """
    if size:
        if not isinstance(size, int):
            raise ValueError("VARCHAR parameter should be an int, got %s" % type(size))
        if size > 0:
            return 'VARCHAR(%d)' % size
    return 'VARCHAR'

def reverse_order(order):
    """ Reverse an ORDER BY clause """
    items = []
    for item in order.split(','):
        item = item.lower().split()
        direction = 'asc' if item[1:] == ['desc'] else 'desc'
        items.append('%s %s' % (item[0], direction))
    return ', '.join(items)
