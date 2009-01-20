# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import os
from os.path import join
import fnmatch
import csv, xml.dom, re
import osv, tools, pooler
import ir
import netsvc
from tools.misc import UpdateableStr
import inspect
import mx.DateTime as mxdt
import tempfile
import tarfile
import codecs
import locale


class UNIX_LINE_TERMINATOR(csv.excel):
    lineterminator = '\n'

csv.register_dialect("UNIX", UNIX_LINE_TERMINATOR)

#
# Warning: better use self.pool.get('ir.translation')._get_source if you can
#
def translate(cr, name, source_type, lang, source=None):
    if source and name:
        cr.execute('select value from ir_translation where lang=%s and type=%s and name=%s and src=%s', (lang, source_type, str(name), source))
    elif name:
        cr.execute('select value from ir_translation where lang=%s and type=%s and name=%s', (lang, source_type, str(name)))
    elif source:
        cr.execute('select value from ir_translation where lang=%s and type=%s and src=%s', (lang, source_type, source))
    res_trans = cr.fetchone()
    res = res_trans and res_trans[0] or False
    return res

class GettextAlias(object):
    def __call__(self, source):
        frame = inspect.stack()[1][0]
        cr = frame.f_locals.get('cr')
        lang = frame.f_locals.get('context', {}).get('lang', False)
        if not (lang and cr):
            return source

        cr.execute('select value from ir_translation where lang=%s and type=%s and src=%s', (lang, 'code', source))
        res_trans = cr.fetchone()
        return res_trans and res_trans[0] or source
_ = GettextAlias()


# class to handle po files
class TinyPoFile(object):
    def __init__(self, buffer):
        self.buffer = buffer

    def __iter__(self):
        self.buffer.seek(0)
        self.lines = self._get_lines()

        self.first = True
        self.tnrs= []
        return self

    def _get_lines(self):
        lines = self.buffer.readlines()
        # remove the BOM (Byte Order Mark):
        if len(lines):
            lines[0] = unicode(lines[0], 'utf8').lstrip(unicode( codecs.BOM_UTF8, "utf8"))

        lines.append('') # ensure that the file ends with at least an empty line
        return lines

    def next(self):
        def unquote(str):
            return str[1:-1].replace("\\n", "\n")   \
                            .replace('\\"', '"')

        type = name = res_id = source = trad = None

        if self.tnrs:
            type, name, res_id, source, trad = self.tnrs.pop(0)
        else:
            tmp_tnrs = []
            line = None
            while (not line):
                if 0 == len(self.lines):
                    raise StopIteration()
                line = self.lines.pop(0).strip()
                if line.startswith('#:'): 
                    tmp_tnrs.append( line[2:].strip().split(':') )
                if line.startswith('#'):
                    line = None

            if not line.startswith('msgid'):
                raise Exception("malformed file: bad line: %s" % line)
            source = unquote(line[6:])
            line = self.lines.pop(0).strip()
            if not source and self.first:
                # if the source is "" and it's the first msgid, it's the special
                # msgstr with the informations about the traduction and the
                # traductor; we skip it
                self.tnrs = []
                while line:
                    line = self.lines.pop(0).strip()
                return self.next()

            while not line.startswith('msgstr'):
                if not line:
                    raise Exception('malformed file')
                source += unquote(line)
                line = self.lines.pop(0).strip()

            trad = unquote(line[7:])
            line = self.lines.pop(0).strip()
            while line:
                trad += unquote(line)
                line = self.lines.pop(0).strip()

            if tmp_tnrs:
                type, name, res_id = tmp_tnrs.pop(0)
                for t, n, r in tmp_tnrs:
                    self.tnrs.append((t, n, r, source, trad))

        self.first = False
        return type, name, res_id, source, trad

    def write_infos(self, modules):
        import release
        self.buffer.write("# Translation of %(project)s.\n" \
                          "# This file containt the translation of the following modules:\n" \
                          "%(modules)s" \
                          "#\n" \
                          "msgid \"\"\n" \
                          "msgstr \"\"\n" \
                          '''"Project-Id-Version: %(project)s %(version)s\\n"\n''' \
                          '''"Report-Msgid-Bugs-To: %(bugmail)s\\n"\n''' \
                          '''"POT-Creation-Date: %(now)s\\n"\n'''        \
                          '''"PO-Revision-Date: %(now)s\\n"\n'''         \
                          '''"Last-Translator: <>\\n"\n''' \
                          '''"Language-Team: \\n"\n'''   \
                          '''"MIME-Version: 1.0\\n"\n''' \
                          '''"Content-Type: text/plain; charset=UTF-8\\n"\n'''   \
                          '''"Content-Transfer-Encoding: \\n"\n'''       \
                          '''"Plural-Forms: \\n"\n'''    \
                          "\n"

                          % { 'project': release.description,
                              'version': release.version,
                              'modules': reduce(lambda s, m: s + "#\t* %s\n" % m, modules, ""),
                              'bugmail': release.support_email,
                              'now': mxdt.ISO.strUTC(mxdt.ISO.DateTime.utc()),
                            }
                          )

    def write(self, modules, tnrs, source, trad):
        def quote(s):
            return '"%s"' % s.replace('"','\\"') \
                             .replace('\n', '\\n"\n"')

        plurial = len(modules) > 1 and 's' or ''
        self.buffer.write("#. module%s: %s\n" % (plurial, ', '.join(modules)))


        code = False
        for typy, name, res_id in tnrs:
            self.buffer.write("#: %s:%s:%s\n" % (typy, name, res_id))
            if typy == 'code':
                code = True

        if code:
            # only strings in python code are python formated
            self.buffer.write("#, python-format\n")

        if not isinstance(trad, unicode):
            trad = unicode(trad, 'utf8')
        if not isinstance(source, unicode):
            source = unicode(source, 'utf8')

        msg = "msgid %s\n"      \
              "msgstr %s\n\n"   \
                  % (quote(source), quote(trad))
        self.buffer.write(msg.encode('utf8'))


# Methods to export the translation file

def trans_export(lang, modules, buffer, format, dbname=None):

    def _process(format, modules, rows, buffer, lang, newlang):
        if format == 'csv':
            writer=csv.writer(buffer, 'UNIX')
            for row in rows:
                writer.writerow(row)
        elif format == 'po':
            rows.pop(0)
            writer = tools.TinyPoFile(buffer)
            writer.write_infos(modules)

            # we now group the translations by source. That means one translation per source.
            grouped_rows = {}
            for module, type, name, res_id, src, trad in rows:
                row = grouped_rows.setdefault(src, {})
                row.setdefault('modules', set()).add(module)
                if ('translation' not in row) or (not row['translation']):
                    row['translation'] = trad
                row.setdefault('tnrs', []).append((type, name, res_id))

            for src, row in grouped_rows.items():
                writer.write(row['modules'], row['tnrs'], src, row['translation'])

        elif format == 'tgz':
            rows.pop(0)
            rows_by_module = {}
            for row in rows:
                module = row[0]
                rows_by_module.setdefault(module, []).append(row)

            tmpdir = tempfile.mkdtemp()
            for mod, modrows in rows_by_module.items():
                tmpmoddir = join(tmpdir, mod, 'i18n')
                os.makedirs(tmpmoddir)
                pofilename = (newlang and mod or lang) + ".po" + (newlang and 't' or '')
                buf = open(join(tmpmoddir, pofilename), 'w')
                _process('po', [mod], modrows, buf, lang, newlang)

            tar = tarfile.open(fileobj=buffer, mode='w|gz')
            tar.add(tmpdir, '')
            tar.close()

        else:
            raise Exception(_('Bad file format'))

    newlang = not bool(lang)
    if newlang:
        lang = 'en_US'
    trans = trans_generate(lang, modules, dbname)
    modules = set([t[0] for t in trans[1:]])
    _process(format, modules, trans, buffer, lang, newlang)
    del trans


def trans_parse_xsl(de):
    res = []
    for n in [i for i in de.childNodes if (i.nodeType == i.ELEMENT_NODE)]:
        if n.hasAttribute("t"):
            for m in [j for j in n.childNodes if (j.nodeType == j.TEXT_NODE)]:
                l = m.data.strip().replace('\n',' ')
                if len(l):
                    res.append(l.encode("utf8"))
        res.extend(trans_parse_xsl(n))
    return res

def trans_parse_rml(de):
    res = []
    for n in [i for i in de.childNodes if (i.nodeType == i.ELEMENT_NODE)]:
        for m in [j for j in n.childNodes if (j.nodeType == j.TEXT_NODE)]:
            string_list = [s.replace('\n', ' ').strip() for s in re.split('\[\[.+?\]\]', m.data)]
            for s in string_list:
                if s:
                    res.append(s.encode("utf8"))
        res.extend(trans_parse_rml(n))
    return res

def trans_parse_view(de):
    res = []
    if de.hasAttribute("string"):
        s = de.getAttribute('string')
        if s:
            res.append(s.encode("utf8"))
    if de.hasAttribute("sum"):
        s = de.getAttribute('sum')
        if s:
            res.append(s.encode("utf8"))
    for n in [i for i in de.childNodes if (i.nodeType == i.ELEMENT_NODE)]:
        res.extend(trans_parse_view(n))
    return res

# tests whether an object is in a list of modules
def in_modules(object_name, modules):
    if 'all' in modules:
        return True

    module_dict = {
        'ir': 'base',
        'res': 'base',
        'workflow': 'base',
    }
    module = object_name.split('.')[0]
    module = module_dict.get(module, module)
    return module in modules

def trans_generate(lang, modules, dbname=None):
    logger = netsvc.Logger()
    if not dbname:
        dbname=tools.config['db_name']
        if not modules:
            modules = ['all']

    pool = pooler.get_pool(dbname)
    trans_obj = pool.get('ir.translation')
    model_data_obj = pool.get('ir.model.data')
    cr = pooler.get_db(dbname).cursor()
    uid = 1
    l = pool.obj_pool.items()
    l.sort()

    query = 'SELECT name, model, res_id, module'    \
            '  FROM ir_model_data'
    if not 'all' in modules:
        query += ' WHERE module IN (%s)' % ','.join(['%s']*len(modules))
    query += ' ORDER BY module, model, name'

    query_param = not 'all' in modules and modules or None
    cr.execute(query, query_param)

    _to_translate = []
    def push_translation(module, type, name, id, source):
        tuple = (module, source, name, id, type)
        if source and tuple not in _to_translate:
            _to_translate.append(tuple)
    
    def encode(s):
        if isinstance(s, unicode):
            return s.encode('utf8')
        return s

    for (xml_name,model,res_id,module) in cr.fetchall():
        module = encode(module)
        model = encode(model)
        xml_name = "%s.%s" % (module, encode(xml_name))

        if not pool.get(model):
            logger.notifyChannel("db", netsvc.LOG_ERROR, "unable to find object %r" % (model,))
            continue
        obj = pool.get(model).browse(cr, uid, res_id)
        if model=='ir.ui.view':
            d = xml.dom.minidom.parseString(encode(obj.arch))
            for t in trans_parse_view(d.documentElement):
                push_translation(module, 'view', encode(obj.model), 0, t)
        elif model=='ir.actions.wizard':
            service_name = 'wizard.'+encode(obj.wiz_name)
            obj2 = netsvc.SERVICES[service_name]
            for state_name, state_def in obj2.states.iteritems():
                if 'result' in state_def:
                    result = state_def['result']
                    if result['type'] != 'form':
                        continue
                    name = "%s,%s" % (encode(obj.wiz_name), state_name)
                    
                    def_params = {
                        'string': ('wizard_field', lambda s: [encode(s)]),
                        'selection': ('selection', lambda s: [encode(e[1]) for e in (callable(s) and s(None, cr, uid, {}) or s)]),
                        'help': ('help', lambda s: [encode(s)]),
                    }

                    # export fields
                    for field_name, field_def in result['fields'].iteritems():
                        res_name = name + ',' + field_name
                       
                        for fn in def_params:
                            if fn in field_def:
                                transtype, modifier = def_params[fn]
                                for val in modifier(field_def[fn]):
                                    push_translation(module, transtype, res_name, 0, val)

                    # export arch
                    arch = result['arch']
                    if arch and not isinstance(arch, UpdateableStr):
                        d = xml.dom.minidom.parseString(arch)
                        for t in trans_parse_view(d.documentElement):
                            push_translation(module, 'wizard_view', name, 0, t)

                    # export button labels
                    for but_args in result['state']:
                        button_name = but_args[0]
                        button_label = but_args[1]
                        res_name = name + ',' + button_name
                        push_translation(module, 'wizard_button', res_name, 0, button_label)

        elif model=='ir.model.fields':
            field_name = encode(obj.name)
            objmodel = pool.get(obj.model)
            if not objmodel or not field_name in objmodel._columns:
                continue
            field_def = objmodel._columns[field_name]

            name = "%s,%s" % (encode(obj.model), field_name)
            push_translation(module, 'field', name, 0, encode(field_def.string))

            if field_def.help:
                push_translation(module, 'help', name, 0, encode(field_def.help))

            if field_def.translate:
                ids = objmodel.search(cr, uid, [])
                obj_values = objmodel.read(cr, uid, ids, [field_name])
                for obj_value in obj_values:
                    res_id = obj_value['id']
                    if obj.name in ('ir.model', 'ir.ui.menu'):
                        res_id = 0
                    model_data_ids = model_data_obj.search(cr, uid, [
                        ('model', '=', model),
                        ('res_id', '=', res_id),
                        ])
                    if not model_data_ids:
                        push_translation(module, 'model', name, 0, encode(obj_value[field_name]))

            if hasattr(field_def, 'selection') and isinstance(field_def.selection, (list, tuple)):
                for key, val in field_def.selection:
                    push_translation(module, 'selection', name, 0, encode(val))

        elif model=='ir.actions.report.xml':
            name = encode(obj.report_name)
            fname = ""
            if obj.report_rml:
                fname = obj.report_rml
                parse_func = trans_parse_rml
                report_type = "rml"
            elif obj.report_xsl:
                fname = obj.report_xsl
                parse_func = trans_parse_xsl
                report_type = "xsl"
            try:
                xmlstr = tools.file_open(fname).read()
                d = xml.dom.minidom.parseString(xmlstr)
                for t in parse_func(d.documentElement):
                    push_translation(module, report_type, name, 0, t)
            except IOError, xml.dom.expatbuilder.expat.ExpatError:
                if fname:
                    logger.notifyChannel("init", netsvc.LOG_ERROR, "couldn't export translation for report %s %s %s" % (name, report_type, fname))

        for constraint in pool.get(model)._constraints:
            msg = constraint[1]
            push_translation(module, 'constraint', model, 0, encode(msg))

        for field_name,field_def in pool.get(model)._columns.items():
            if field_def.translate:
                name = model + "," + field_name
                trad = getattr(obj, field_name) or ''
                push_translation(module, 'model', name, xml_name, encode(trad))

    # parse source code for _() calls
    def get_module_from_path(path):
        relative_addons_path = tools.config['addons_path'][len(tools.config['root_path'])+1:]
        if path.startswith(relative_addons_path) and (os.path.dirname(path) != relative_addons_path):
            path = path[len(relative_addons_path)+1:]
            return path.split(os.path.sep)[0]
        return 'base'   # files that are not in a module are considered as being in 'base' module

    modobj = pool.get('ir.module.module')
    installed_modids = modobj.search(cr, uid, [('state', '=', 'installed')])
    installed_modules = map(lambda m: m['name'], modobj.read(cr, uid, installed_modids, ['name']))

    for root, dirs, files in tools.osutil.walksymlinks(tools.config['root_path']):
        for fname in fnmatch.filter(files, '*.py'):
            fabsolutepath = join(root, fname)
            frelativepath = fabsolutepath[len(tools.config['root_path'])+1:]
            module = get_module_from_path(frelativepath)
            is_mod_installed = module in installed_modules
            if (('all' in modules) or (module in modules)) and is_mod_installed:
                code_string = tools.file_open(fabsolutepath, subdir='').read()
                iter = re.finditer(
                    '[^a-zA-Z0-9_]_\([\s]*["\'](.+?)["\'][\s]*\)',
                    code_string, re.M)
                for i in iter:
                    push_translation(module, 'code', frelativepath, 0, encode(i.group(1)))


    out = [["module","type","name","res_id","src","value"]] # header
    _to_translate.sort()
    # translate strings marked as to be translated
    for module, source, name, id, type in _to_translate:
        trans = trans_obj._get_source(cr, uid, name, type, lang, source)
        out.append([module, type, name, id, source, encode(trans) or ''])
    
    cr.close()
    return out

def trans_load(db_name, filename, lang, strict=False, verbose=True):
    logger = netsvc.Logger()
    try:
        fileobj = open(filename,'r')
        fileformat = os.path.splitext(filename)[-1][1:].lower()
        r = trans_load_data(db_name, fileobj, fileformat, lang, strict=strict, verbose=verbose)
        fileobj.close()
        return r
    except IOError:
        if verbose:
            logger.notifyChannel("init", netsvc.LOG_ERROR, "couldn't read translation file %s" % (filename,)) 
        return None

def trans_load_data(db_name, fileobj, fileformat, lang, strict=False, lang_name=None, verbose=True):
    logger = netsvc.Logger()
    if verbose:
        logger.notifyChannel("init", netsvc.LOG_INFO,
                'loading translation file for language %s' % (lang))
    pool = pooler.get_pool(db_name)
    lang_obj = pool.get('res.lang')
    trans_obj = pool.get('ir.translation')
    model_data_obj = pool.get('ir.model.data')
    try:
        uid = 1
        cr = pooler.get_db(db_name).cursor()
        ids = lang_obj.search(cr, uid, [('code','=',lang)])
        lc, encoding = locale.getdefaultlocale()
        if not encoding:
            encoding = 'UTF-8'
        if encoding == 'utf':
            encoding = 'UTF-8'
        if encoding == 'cp1252':
            encoding= '1252'

        try:
            if os.name == 'nt':
                locale.setlocale(locale.LC_ALL, str(_LOCALE2WIN32.get(lang, lang) + '.' + encoding))
            else:
                locale.setlocale(locale.LC_ALL, str(lang + '.' + encoding))
        except Exception:
            netsvc.Logger().notifyChannel(' ', netsvc.LOG_WARNING,
                    'unable to set locale "%s"' % (lang)) 
            locale.setlocale(locale.LC_ALL, str('en_US' + '.' + encoding))

        if not ids:
            if not lang_name:
                lang_name=lang
                languages=tools.get_languages()
                lang_name = languages.get(lang, lang)
            ids = lang_obj.create(cr, uid, {
                'code': lang,
                'name': lang_name,
                'translatable': 1,
                'date_format' : locale.nl_langinfo(locale.D_FMT).replace('%y', '%Y'),
                'time_format' : locale.nl_langinfo(locale.T_FMT),
                'grouping' : [],
                'decimal_point' : locale.nl_langinfo(locale.RADIXCHAR),
                'thousands_sep' : locale.nl_langinfo(locale.THOUSEP)
                })
        else:
            lang_obj.write(cr, uid, ids, {'translatable':1,
                                          'date_format' : locale.nl_langinfo(locale.D_FMT).replace('%y', '%Y'),
                                          'time_format' : locale.nl_langinfo(locale.T_FMT),
                                          'grouping' : [],
                                          'decimal_point' : locale.nl_langinfo(locale.RADIXCHAR),
                                          'thousands_sep' : locale.nl_langinfo(locale.THOUSEP)
                                            })
        
        locale.resetlocale(locale.LC_ALL)
        lang_ids = lang_obj.search(cr, uid, [])
        langs = lang_obj.read(cr, uid, lang_ids)
        ls = map(lambda x: (x['code'],x['name']), langs)

        fileobj.seek(0)

        if fileformat == 'csv':
            reader = csv.reader(fileobj, quotechar='"', delimiter=',')
            # read the first line of the file (it contains columns titles)
            for row in reader:
                f = row
                break
        elif fileformat == 'po':
            reader = TinyPoFile(fileobj)
            f = ['type', 'name', 'res_id', 'src', 'value']
        else:
            raise Exception(_('Bad file format'))

        # read the rest of the file
        line = 1
        for row in reader:
            line += 1
            # skip empty rows and rows where the translation field (=last fiefd) is empty
            if (not row) or (not row[-1]):
                continue

            # dictionary which holds values for this line of the csv file
            # {'lang': ..., 'type': ..., 'name': ..., 'res_id': ...,
            #  'src': ..., 'value': ...}
            dic = {'lang': lang}
            for i in range(len(f)):
                if f[i] in ('module',):
                    continue
                dic[f[i]] = row[i]

            try:
                dic['res_id'] = int(dic['res_id'])
            except:
                model_data_ids = model_data_obj.search(cr, uid, [
                    ('model', '=', dic['name'].split(',')[0]),
                    ('module', '=', dic['res_id'].split('.', 1)[0]),
                    ('name', '=', dic['res_id'].split('.', 1)[1]),
                    ])
                if model_data_ids:
                    dic['res_id'] = model_data_obj.browse(cr, uid,
                            model_data_ids[0]).res_id
                else:
                    dic['res_id'] = False

            if dic['type'] == 'model' and not strict:
                (model, field) = dic['name'].split(',')

                # get the ids of the resources of this model which share
                # the same source
                obj = pool.get(model)
                if obj:
                    ids = obj.search(cr, uid, [(field, '=', dic['src'])])

                    # if the resource id (res_id) is in that list, use it,
                    # otherwise use the whole list
                    ids = (dic['res_id'] in ids) and [dic['res_id']] or ids
                    for id in ids:
                        dic['res_id'] = id
                        ids = trans_obj.search(cr, uid, [
                            ('lang', '=', lang),
                            ('type', '=', dic['type']),
                            ('name', '=', dic['name']),
                            ('src', '=', dic['src']),
                            ('res_id', '=', dic['res_id'])
                        ])
                        if ids:
                            trans_obj.write(cr, uid, ids, {'value': dic['value']})
                        else:
                            trans_obj.create(cr, uid, dic)
            else:
                ids = trans_obj.search(cr, uid, [
                    ('lang', '=', lang),
                    ('type', '=', dic['type']),
                    ('name', '=', dic['name']),
                    ('src', '=', dic['src'])
                ])
                if ids:
                    trans_obj.write(cr, uid, ids, {'value': dic['value']})
                else:
                    trans_obj.create(cr, uid, dic)
            cr.commit()
        cr.close()
        if verbose:
            logger.notifyChannel("init", netsvc.LOG_INFO,
                    "translation file loaded succesfully")
    except IOError:
        filename = '[lang: %s][format: %s]' % (lang or 'new', fileformat)
        logger.notifyChannel("init", netsvc.LOG_ERROR, "couldn't read translation file %s" % (filename,))


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

