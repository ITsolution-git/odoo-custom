# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2010 OpenERP s.a. (<http://openerp.com>).
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
import base64
import cStringIO
import imp
import logging
import os
import re
import StringIO
import urllib
import zipfile
import zipimport

import openerp.modules as addons
import pooler
import release
import tools

from tools.parse_version import parse_version
from tools.translate import _

from osv import fields, osv, orm

ACTION_DICT = {
    'view_type': 'form',
    'view_mode': 'form',
    'res_model': 'base.module.upgrade',
    'target': 'new',
    'type': 'ir.actions.act_window',
    'nodestroy':True,
}

class module_category(osv.osv):
    _name = "ir.module.category"
    _description = "Application"

    def _module_nbr(self,cr,uid, ids, prop, unknow_none, context):
        cr.execute('SELECT category_id, COUNT(*) \
                      FROM ir_module_module \
                     WHERE category_id IN %(ids)s \
                        OR category_id IN (SELECT id \
                                             FROM ir_module_category \
                                            WHERE parent_id IN %(ids)s) \
                     GROUP BY category_id', {'ids': tuple(ids)}
                    )
        result = dict(cr.fetchall())
        for id in ids:
            cr.execute('select id from ir_module_category where parent_id=%s', (id,))
            result[id] = sum([result.get(c, 0) for (c,) in cr.fetchall()],
                             result.get(id, 0))
        return result

    _columns = {
        'name': fields.char("Name", size=128, required=True, translate=True, select=True),
        'parent_id': fields.many2one('ir.module.category', 'Parent Application', select=True),
        'child_ids': fields.one2many('ir.module.category', 'parent_id', 'Child Applications'),
        'module_nr': fields.function(_module_nbr, method=True, string='Number of Modules', type='integer'),
        'module_ids' : fields.one2many('ir.module.module', 'category_id', 'Modules'),
        'description' : fields.text("Description", translate=True),
        'sequence' : fields.integer('Sequence'),
        'visible' : fields.boolean('Visible'),
    }
    _order = 'name'

    _defaults = {
        'visible' : 1,
    }

class module(osv.osv):
    _name = "ir.module.module"
    _description = "Module"
    __logger = logging.getLogger('base.' + _name)

    @classmethod
    def get_module_info(cls, name):
        info = {}
        try:
            info = addons.load_information_from_description_file(name)
            info['version'] = release.major_version + '.' + info['version']
        except Exception:
            cls.__logger.debug('Error when trying to fetch informations for '
                                'module %s', name, exc_info=True)
        return info

    def _get_latest_version(self, cr, uid, ids, field_name=None, arg=None, context=None):
        res = dict.fromkeys(ids, '')
        for m in self.browse(cr, uid, ids):
            res[m.id] = self.get_module_info(m.name).get('version', '')
        return res

    def _get_views(self, cr, uid, ids, field_name=None, arg=None, context=None):
        res = {}
        model_data_obj = self.pool.get('ir.model.data')
        view_obj = self.pool.get('ir.ui.view')
        report_obj = self.pool.get('ir.actions.report.xml')
        menu_obj = self.pool.get('ir.ui.menu')

        dmodels = []
        if field_name is None or 'views_by_module' in field_name:
            dmodels.append('ir.ui.view')
        if field_name is None or 'reports_by_module' in field_name:
            dmodels.append('ir.actions.report.xml')
        if field_name is None or 'menus_by_module' in field_name:
            dmodels.append('ir.ui.menu')
        assert dmodels, "no models for %s" % field_name
        
        for module_rec in self.browse(cr, uid, ids, context=context):
            res[module_rec.id] = {
                'menus_by_module': [],
                'reports_by_module': [],
                'views_by_module': []
            }

            # Skip uninstalled modules below, no data to find anyway.
            if module_rec.state not in ('installed', 'to upgrade', 'to remove'):
                continue

            # then, search and group ir.model.data records
            imd_models = dict( [(m,[]) for m in dmodels])
            imd_ids = model_data_obj.search(cr,uid,[('module','=', module_rec.name),
                ('model','in',tuple(dmodels))])

            for imd_res in model_data_obj.read(cr, uid, imd_ids, ['model', 'res_id'], context=context):
                imd_models[imd_res['model']].append(imd_res['res_id'])

            # For each one of the models, get the names of these ids.
            # We use try except, because views or menus may not exist.
            try:
                res_mod_dic = res[module_rec.id]
                for v in view_obj.browse(cr, uid, imd_models.get('ir.ui.view', []), context=context):
                    aa = v.inherit_id and '* INHERIT ' or ''
                    res_mod_dic['views_by_module'].append(aa + v.name + '('+v.type+')')

                for rx in report_obj.browse(cr, uid, imd_models.get('ir.actions.report.xml', []), context=context):
                    res_mod_dic['reports_by_module'].append(rx.name)

                for um in menu_obj.browse(cr, uid, imd_models.get('ir.ui.menu', []), context=context):
                    res_mod_dic['menus_by_module'].append(um.complete_name)
            except KeyError, e:
                self.__logger.warning(
                            'Data not found for items of %s', module_rec.name)
            except AttributeError, e:
                self.__logger.warning(
                            'Data not found for items of %s %s', module_rec.name, str(e))
            except Exception, e:
                self.__logger.warning('Unknown error while fetching data of %s',
                            module_rec.name, exc_info=True)
        for key, value in res.iteritems():
            for k, v in res[key].iteritems():
                res[key][k] = "\n".join(sorted(v))
        return res

    _columns = {
        'name': fields.char("Name", size=128, readonly=True, required=True, select=True),
        'category_id': fields.many2one('ir.module.category', 'Category', readonly=True, select=True),
        'shortdesc': fields.char('Short Description', size=256, readonly=True, translate=True),
        'description': fields.text("Description", readonly=True, translate=True),
        'author': fields.char("Author", size=128, readonly=True),
        'maintainer': fields.char('Maintainer', size=128, readonly=True),
        'contributors': fields.text('Contributors', readonly=True),
        'website': fields.char("Website", size=256, readonly=True),

        # attention: Incorrect field names !!
        #   installed_version refer the latest version (the one on disk)
        #   latest_version refer the installed version (the one in database)
        #   published_version refer the version available on the repository
        'installed_version': fields.function(_get_latest_version, method=True,
            string='Latest version', type='char'),
        'latest_version': fields.char('Installed version', size=64, readonly=True),
        'published_version': fields.char('Published Version', size=64, readonly=True),

        'url': fields.char('URL', size=128, readonly=True),
        'sequence': fields.integer('Sequence'),
        'dependencies_id': fields.one2many('ir.module.module.dependency',
            'module_id', 'Dependencies', readonly=True),
        'state': fields.selection([
            ('uninstallable','Not Installable'),
            ('uninstalled','Not Installed'),
            ('installed','Installed'),
            ('to upgrade','To be upgraded'),
            ('to remove','To be removed'),
            ('to install','To be installed')
        ], string='State', readonly=True, select=True),
        'demo': fields.boolean('Demo data'),
        'license': fields.selection([
                ('GPL-2', 'GPL Version 2'),
                ('GPL-2 or any later version', 'GPL-2 or later version'),
                ('GPL-3', 'GPL Version 3'),
                ('GPL-3 or any later version', 'GPL-3 or later version'),
                ('AGPL-3', 'Affero GPL-3'),
                ('Other OSI approved licence', 'Other OSI Approved Licence'),
                ('Other proprietary', 'Other Proprietary')
            ], string='License', readonly=True),
        'menus_by_module': fields.function(_get_views, method=True, string='Menus', type='text', multi="meta", store=True),
        'reports_by_module': fields.function(_get_views, method=True, string='Reports', type='text', multi="meta", store=True),
        'views_by_module': fields.function(_get_views, method=True, string='Views', type='text', multi="meta", store=True),
        'certificate' : fields.char('Quality Certificate', size=64, readonly=True),
        'application': fields.boolean('Application', readonly=True),
        'icon': fields.char('Icon URL', size=128),
        'complexity': fields.selection([('easy','Easy'), ('normal','Normal'), ('expert','Expert')],
            string='Complexity', readonly=True,
            help='Level of difficulty of module. Easy: intuitive and easy to use for everyone. Normal: easy to use for business experts. Expert: requires technical skills.'),
    }

    _defaults = {
        'state': 'uninstalled',
        'sequence': 100,
        'demo': False,
        'license': 'AGPL-3',
        'complexity': 'normal',
    }
    _order = 'sequence,name'

    def _name_uniq_msg(self, cr, uid, ids, context=None):
        return _('The name of the module must be unique !')
    def _certificate_uniq_msg(self, cr, uid, ids, context=None):
        return _('The certificate ID of the module must be unique !')

    _sql_constraints = [
        ('name_uniq', 'UNIQUE (name)',_name_uniq_msg ),
        ('certificate_uniq', 'UNIQUE (certificate)',_certificate_uniq_msg )
    ]

    def unlink(self, cr, uid, ids, context=None):
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        mod_names = []
        for mod in self.read(cr, uid, ids, ['state','name'], context):
            if mod['state'] in ('installed', 'to upgrade', 'to remove', 'to install'):
                raise orm.except_orm(_('Error'),
                        _('You try to remove a module that is installed or will be installed'))
            mod_names.append(mod['name'])
        #Removing the entry from ir_model_data
        #ids_meta = self.pool.get('ir.model.data').search(cr, uid, [('name', '=', 'module_meta_information'), ('module', 'in', mod_names)])

        #if ids_meta:
        #    self.pool.get('ir.model.data').unlink(cr, uid, ids_meta, context)

        return super(module, self).unlink(cr, uid, ids, context=context)

    @staticmethod
    def _check_external_dependencies(terp):
        depends = terp.get('external_dependencies')
        if not depends:
            return
        for pydep in depends.get('python', []):
            parts = pydep.split('.')
            parts.reverse()
            path = None
            while parts:
                part = parts.pop()
                try:
                    f, path, descr = imp.find_module(part, path and [path] or None)
                except ImportError:
                    raise ImportError('No module named %s' % (pydep,))

        for binary in depends.get('bin', []):
            if tools.find_in_path(binary) is None:
                raise Exception('Unable to find %r in path' % (binary,))

    @classmethod
    def check_external_dependencies(cls, module_name, newstate='to install'):
        terp = cls.get_module_info(module_name)
        try:
            cls._check_external_dependencies(terp)
        except Exception, e:
            if newstate == 'to install':
                msg = _('Unable to install module "%s" because an external dependency is not met: %s')
            elif newstate == 'to upgrade':
                msg = _('Unable to upgrade module "%s" because an external dependency is not met: %s')
            else:
                msg = _('Unable to process module "%s" because an external dependency is not met: %s')
            raise orm.except_orm(_('Error'), msg % (module_name, e.args[0]))

    def state_update(self, cr, uid, ids, newstate, states_to_update, context=None, level=100):
        if level<1:
            raise orm.except_orm(_('Error'), _('Recursion error in modules dependencies !'))
        demo = False
        for module in self.browse(cr, uid, ids, context=context):
            mdemo = False
            for dep in module.dependencies_id:
                if dep.state == 'unknown':
                    raise orm.except_orm(_('Error'), _("You try to install module '%s' that depends on module '%s'.\nBut the latter module is not available in your system.") % (module.name, dep.name,))
                ids2 = self.search(cr, uid, [('name','=',dep.name)])
                if dep.state != newstate:
                    mdemo = self.state_update(cr, uid, ids2, newstate, states_to_update, context, level-1,) or mdemo
                else:
                    od = self.browse(cr, uid, ids2)[0]
                    mdemo = od.demo or mdemo

            self.check_external_dependencies(module.name, newstate)
            if not module.dependencies_id:
                mdemo = module.demo
            if module.state in states_to_update:
                self.write(cr, uid, [module.id], {'state': newstate, 'demo':mdemo})
            demo = demo or mdemo
        return demo

    def button_install(self, cr, uid, ids, context=None):
        self.state_update(cr, uid, ids, 'to install', ['uninstalled'], context)
        return dict(ACTION_DICT, name=_('Install'))

    def button_immediate_install(self, cr, uid, ids, context=None):
        """ Installs the selected module(s) immediately and fully,
        returns the next res.config action to execute

        :param ids: identifiers of the modules to install
        :returns: next res.config item to execute
        :rtype: dict[str, object]
        """
        self.state_update(cr, uid, ids, 'to install', ['uninstalled'], context)
        cr.commit()
        db, pool = pooler.restart_pool(cr.dbname, update_module=True)

        config = pool.get('res.config').next(cr, uid, [], context=context) or {}
        if config.get('type') not in ('ir.actions.reload', 'ir.actions.act_window_close'):
            return config

        menu_ids = self.root_menus(cr,uid,ids,context)
        if menu_ids:
            action = {
                'type': 'ir.ui.menu',
                'menu_id': menu_ids[0],
                'reload' : True,
            }
            return action
        return False

    def button_install_cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'uninstalled', 'demo':False})
        return True

    def button_uninstall(self, cr, uid, ids, context=None):
        for module in self.browse(cr, uid, ids):
            cr.execute('''select m.state,m.name
                from
                    ir_module_module_dependency d
                join
                    ir_module_module m on (d.module_id=m.id)
                where
                    d.name=%s and
                    m.state not in ('uninstalled','uninstallable','to remove')''', (module.name,))
            res = cr.fetchall()
            if res:
                raise orm.except_orm(_('Error'), _('Some installed modules depend on the module you plan to Uninstall :\n %s') % '\n'.join(map(lambda x: '\t%s: %s' % (x[0], x[1]), res)))
        self.write(cr, uid, ids, {'state': 'to remove'})
        return dict(ACTION_DICT, name=_('Uninstall'))

    def button_uninstall_cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'installed'})
        return True

    def button_upgrade(self, cr, uid, ids, context=None):
        depobj = self.pool.get('ir.module.module.dependency')
        todo = self.browse(cr, uid, ids, context=context)
        self.update_list(cr, uid)

        i = 0
        while i<len(todo):
            mod = todo[i]
            i += 1
            if mod.state not in ('installed','to upgrade'):
                raise orm.except_orm(_('Error'),
                        _("Can not upgrade module '%s'. It is not installed.") % (mod.name,))
            self.check_external_dependencies(mod.name, 'to upgrade')
            iids = depobj.search(cr, uid, [('name', '=', mod.name)], context=context)
            for dep in depobj.browse(cr, uid, iids, context=context):
                if dep.module_id.state=='installed' and dep.module_id not in todo:
                    todo.append(dep.module_id)

        ids = map(lambda x: x.id, todo)
        self.write(cr, uid, ids, {'state':'to upgrade'}, context=context)

        to_install = []
        for mod in todo:
            for dep in mod.dependencies_id:
                if dep.state == 'unknown':
                    raise orm.except_orm(_('Error'), _('You try to upgrade a module that depends on the module: %s.\nBut this module is not available in your system.') % (dep.name,))
                if dep.state == 'uninstalled':
                    ids2 = self.search(cr, uid, [('name','=',dep.name)])
                    to_install.extend(ids2)

        self.button_install(cr, uid, to_install, context=context)
        return dict(ACTION_DICT, name=_('Upgrade'))

    def button_upgrade_cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'installed'})
        return True

    def button_update_translations(self, cr, uid, ids, context=None):
        self.update_translations(cr, uid, ids)
        return True

    @staticmethod
    def get_values_from_terp(terp):
        return {
            'description': terp.get('description', ''),
            'shortdesc': terp.get('name', ''),
            'author': terp.get('author', 'Unknown'),
            'maintainer': terp.get('maintainer', False),
            'contributors': ', '.join(terp.get('contributors', [])) or False,
            'website': terp.get('website', ''),
            'license': terp.get('license', 'AGPL-3'),
            'certificate': terp.get('certificate') or False,
            'complexity': terp.get('complexity', ''),
        }

    # update the list of available packages
    def update_list(self, cr, uid, context=None):
        res = [0, 0] # [update, add]

        known_mods = self.browse(cr, uid, self.search(cr, uid, []))
        known_mods_names = dict([(m.name, m) for m in known_mods])

        # iterate through detected modules and update/create them in db
        for mod_name in addons.get_modules():
            mod = known_mods_names.get(mod_name)
            terp = self.get_module_info(mod_name)
            values = self.get_values_from_terp(terp)

            if mod:
                updated_values = {}
                for key in values:
                    old = getattr(mod, key)
                    updated = isinstance(values[key], basestring) and tools.ustr(values[key]) or values[key] 
                    if not old == updated:
                        updated_values[key] = values[key]
                if terp.get('installable', True) and mod.state == 'uninstallable':
                    updated_values['state'] = 'uninstalled'
                if parse_version(terp.get('version', '')) > parse_version(mod.latest_version or ''):
                    res[0] += 1
                if updated_values:
                    self.write(cr, uid, mod.id, updated_values)
            else:
                mod_path = addons.get_module_path(mod_name)
                if not mod_path:
                    continue
                if not terp or not terp.get('installable', True):
                    continue
                id = self.create(cr, uid, dict(name=mod_name, state='uninstalled', **values))
                mod = self.browse(cr, uid, id)
                res[1] += 1

            self._update_dependencies(cr, uid, mod, terp.get('depends', []))
            self._update_category(cr, uid, mod, terp.get('category', 'Uncategorized'))

        return res

    def download(self, cr, uid, ids, download=True, context=None):
        res = []
        for mod in self.browse(cr, uid, ids, context=context):
            if not mod.url:
                continue
            match = re.search('-([a-zA-Z0-9\._-]+)(\.zip)', mod.url, re.I)
            version = '0'
            if match:
                version = match.group(1)
            if parse_version(mod.installed_version or '0') >= parse_version(version):
                continue
            res.append(mod.url)
            if not download:
                continue
            zip_content = urllib.urlopen(mod.url).read()
            fname = addons.get_module_path(str(mod.name)+'.zip', downloaded=True)
            try:
                with open(fname, 'wb') as fp:
                    fp.write(zip_content)
            except Exception:
                self.__logger.exception('Error when trying to create module '
                                        'file %s', fname)
                raise orm.except_orm(_('Error'), _('Can not create the module file:\n %s') % (fname,))
            terp = self.get_module_info(mod.name)
            self.write(cr, uid, mod.id, self.get_values_from_terp(terp))
            cr.execute('DELETE FROM ir_module_module_dependency ' \
                    'WHERE module_id = %s', (mod.id,))
            self._update_dependencies(cr, uid, mod, terp.get('depends',
                []))
            self._update_category(cr, uid, mod, terp.get('category',
                'Uncategorized'))
            # Import module
            zimp = zipimport.zipimporter(fname)
            zimp.load_module(mod.name)
        return res

    def _update_dependencies(self, cr, uid, mod_browse, depends=None):
        if depends is None:
            depends = []
        existing = set(x.name for x in mod_browse.dependencies_id)
        needed = set(depends)
        for dep in (needed - existing):
            cr.execute('INSERT INTO ir_module_module_dependency (module_id, name) values (%s, %s)', (mod_browse.id, dep))
        for dep in (existing - needed):
            cr.execute('DELETE FROM ir_module_module_dependency WHERE module_id = %s and name = %s', (mod_browse.id, dep))

    def _update_category(self, cr, uid, mod_browse, category='Uncategorized'):
        current_category = mod_browse.category_id
        current_category_path = []
        while current_category:
            current_category_path.insert(0, current_category.name)
            current_category = current_category.parent_id

        categs = category.split('/')
        if categs != current_category_path:
            p_id = None
            while categs:
                if p_id is not None:
                    cr.execute('SELECT id FROM ir_module_category WHERE name=%s AND parent_id=%s', (categs[0], p_id))
                else:
                    cr.execute('SELECT id FROM ir_module_category WHERE name=%s AND parent_id is NULL', (categs[0],))
                c_id = cr.fetchone()
                if not c_id:
                    cr.execute('INSERT INTO ir_module_category (name, parent_id) VALUES (%s, %s) RETURNING id', (categs[0], p_id))
                    c_id = cr.fetchone()[0]
                else:
                    c_id = c_id[0]
                p_id = c_id
                categs = categs[1:]
            self.write(cr, uid, [mod_browse.id], {'category_id': p_id})

    def update_translations(self, cr, uid, ids, filter_lang=None, context=None):
        if context is None:
            context = {}
        logger = logging.getLogger('i18n')
        if not filter_lang:
            pool = pooler.get_pool(cr.dbname)
            lang_obj = pool.get('res.lang')
            lang_ids = lang_obj.search(cr, uid, [('translatable', '=', True)])
            filter_lang = [lang.code for lang in lang_obj.browse(cr, uid, lang_ids)]
        elif not isinstance(filter_lang, (list, tuple)):
            filter_lang = [filter_lang]

        for mod in self.browse(cr, uid, ids):
            if mod.state != 'installed':
                continue
            modpath = addons.get_module_path(mod.name)
            if not modpath:
                # unable to find the module. we skip
                continue
            for lang in filter_lang:
                iso_lang = tools.get_iso_codes(lang)
                f = addons.get_module_resource(mod.name, 'i18n', iso_lang + '.po')
                context2 = context and context.copy() or {}
                if f and '_' in iso_lang:
                    iso_lang2 = iso_lang.split('_')[0]
                    f2 = addons.get_module_resource(mod.name, 'i18n', iso_lang2 + '.po')
                    if f2:
                        logger.info('module %s: loading base translation file %s for language %s', mod.name, iso_lang2, lang)
                        tools.trans_load(cr, f2, lang, verbose=False, context=context)
                        context2['overwrite'] = True
                # Implementation notice: we must first search for the full name of
                # the language derivative, like "en_UK", and then the generic,
                # like "en".
                if (not f) and '_' in iso_lang:
                    iso_lang = iso_lang.split('_')[0]
                    f = addons.get_module_resource(mod.name, 'i18n', iso_lang + '.po')
                if f:
                    logger.info('module %s: loading translation file (%s) for language %s', mod.name, iso_lang, lang)
                    tools.trans_load(cr, f, lang, verbose=False, context=context2)
                elif iso_lang != 'en':
                    logger.warning('module %s: no translation for language %s', mod.name, iso_lang)
        tools.trans_update_res_ids(cr)

    def check(self, cr, uid, ids, context=None):
        logger = logging.getLogger('init')
        for mod in self.browse(cr, uid, ids, context=context):
            if not mod.description:
                logger.warn('module %s: description is empty !', mod.name)

            if not mod.certificate or not mod.certificate.isdigit():
                logger.info('module %s: no quality certificate', mod.name)
            else:
                val = long(mod.certificate[2:]) % 97 == 29
                if not val:
                    logger.critical('module %s: invalid quality certificate: %s', mod.name, mod.certificate)
                    raise osv.except_osv(_('Error'), _('Module %s: Invalid Quality Certificate') % (mod.name,))

    def root_menus(self, cr, uid, ids, context=None):
        """ Return root menu ids the menus created by the modules whose ids are
        provided.

        :param list[int] ids: modules to get menus from
        """
        values = self.read(cr, uid, ids, ['name'], context=context)
        module_names = [i['name'] for i in values]

        ids = self.pool.get('ir.model.data').search(cr, uid, [ ('model', '=', 'ir.ui.menu'), ('module', 'in', module_names) ], context=context)
        values = self.pool.get('ir.model.data').read(cr, uid, ids, ['res_id'], context=context)
        all_menu_ids = [i['res_id'] for i in values]

        root_menu_ids = []
        for menu in self.pool.get('ir.ui.menu').browse(cr, uid, all_menu_ids, context=context):
            while menu.parent_id:
                menu = menu.parent_id
            if not menu.id in root_menu_ids:
                root_menu_ids.append(menu.id)
        return root_menu_ids

class module_dependency(osv.osv):
    _name = "ir.module.module.dependency"
    _description = "Module dependency"

    def _state(self, cr, uid, ids, name, args, context=None):
        result = {}
        mod_obj = self.pool.get('ir.module.module')
        for md in self.browse(cr, uid, ids):
            ids = mod_obj.search(cr, uid, [('name', '=', md.name)])
            if ids:
                result[md.id] = mod_obj.read(cr, uid, [ids[0]], ['state'])[0]['state']
            else:
                result[md.id] = 'unknown'
        return result

    _columns = {
        'name': fields.char('Name',  size=128, select=True),
        'module_id': fields.many2one('ir.module.module', 'Module', select=True, ondelete='cascade'),
        'state': fields.function(_state, method=True, type='selection', selection=[
            ('uninstallable','Uninstallable'),
            ('uninstalled','Not Installed'),
            ('installed','Installed'),
            ('to upgrade','To be upgraded'),
            ('to remove','To be removed'),
            ('to install','To be installed'),
            ('unknown', 'Unknown'),
            ], string='State', readonly=True, select=True),
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
