# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution	
#    Copyright (C) 2004-2008 Tiny SPRL (<http://tiny.be>). All Rights Reserved
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

from osv import fields, osv
import tools

TRANSLATION_TYPE = [
    ('field', 'Field'),
    ('model', 'Object'),
    ('rml', 'RML'),
    ('selection', 'Selection'),
    ('view', 'View'),
    ('wizard_button', 'Wizard Button'),
    ('wizard_field', 'Wizard Field'),
    ('wizard_view', 'Wizard View'),
    ('xsl', 'XSL'),
    ('help', 'Help'),
    ('code', 'Code'),
    ('constraint', 'Constraint'),
]

class ir_translation(osv.osv):
    _name = "ir.translation"
    _log_access = False

    def _get_language(self, cr, uid, context):
        lang_obj = self.pool.get('res.lang')
        lang_ids = lang_obj.search(cr, uid, [('translatable', '=', True)],
                context=context)
        langs = lang_obj.browse(cr, uid, lang_ids, context=context)
        res = [(lang.code, lang.name) for lang in langs]
        for lang_dict in tools.scan_languages():
            if lang_dict not in res:
                res.append(lang_dict)
        return res

    _columns = {
        'name': fields.char('Field Name', size=128, required=True),
        'res_id': fields.integer('Resource ID', select=True),
        'lang': fields.selection(_get_language, string='Language', size=5),
        'type': fields.selection(TRANSLATION_TYPE, string='Type', size=16, select=True),
        'src': fields.text('Source'),
        'value': fields.text('Translation Value'),
    }

    def _auto_init(self, cr, context={}):
        super(ir_translation, self)._auto_init(cr, context)
        cr.execute('SELECT indexname FROM pg_indexes WHERE indexname = %s', ('ir_translation_ltns',))
        if not cr.fetchone():
            cr.execute('CREATE INDEX ir_translation_ltns ON ir_translation (lang, type, name, src)')
            cr.commit()

        cr.execute('SELECT indexname FROM pg_indexes WHERE indexname = %s', ('ir_translation_ltn',))
        if not cr.fetchone():
            cr.execute('CREATE INDEX ir_translation_ltn ON ir_translation (lang, type, name)')
            cr.commit()

        cr.execute('SELECT indexname FROM pg_indexes WHERE indexname = %s', ('ir_translation_lts',))
        if not cr.fetchone():
            cr.execute('CREATE INDEX ir_translation_lts ON ir_translation (lang, type, src)')
            cr.commit()

    @tools.cache(skiparg=3)
    def _get_ids(self, cr, uid, name, tt, lang, ids):
        translations = {}
        if ids:
            cr.execute('select res_id,value ' \
                    'from ir_translation ' \
                    'where lang=%s ' \
                        'and type=%s ' \
                        'and name=%s ' \
                        'and res_id in ('+','.join(map(str, ids))+')',
                    (lang,tt,name))
            for res_id, value in cr.fetchall():
                translations[res_id] = value
        for res_id in ids:
            if res_id not in translations:
                translations[res_id] = False
        return translations

    def _set_ids(self, cr, uid, name, tt, lang, ids, value):
        cr.execute('delete from ir_translation ' \
                'where lang=%s ' \
                    'and type=%s ' \
                    'and name=%s ' \
                    'and res_id in ('+','.join(map(str,ids))+')',
                (lang,tt,name))
        for id in ids:
            self.create(cr, uid, {
                'lang':lang,
                'type':tt,
                'name':name,
                'res_id':id,
                'value':value,
                })
        return len(ids)

    @tools.cache(skiparg=3)
    def _get_source(self, cr, uid, name, tt, lang, source=None):
        if source:
            #if isinstance(source, unicode):
            #   source = source.encode('utf8')
            cr.execute('select value ' \
                    'from ir_translation ' \
                    'where lang=%s ' \
                        'and type=%s ' \
                        'and name=%s ' \
                        'and src=%s',
                    (lang, tt, str(name), source))
        else:
            cr.execute('select value ' \
                    'from ir_translation ' \
                    'where lang=%s ' \
                        'and type=%s ' \
                        'and name=%s',
                    (lang, tt, str(name)))
        res = cr.fetchone()
        trad = res and res[0] or ''
        return trad

ir_translation()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

