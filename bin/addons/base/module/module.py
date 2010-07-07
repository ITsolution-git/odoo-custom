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

import tarfile
import re
import urllib
import os
import imp
import logging
import tools
from osv import fields, osv, orm
import zipfile
import release
import zipimport

import wizard
import addons
import pooler
import netsvc

from tools.parse_version import parse_version
from tools.translate import _

class module_category(osv.osv):
    _name = "ir.module.category"
    _description = "Module Category"

    def _module_nbr(self,cr,uid, ids, prop, unknow_none,context):
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
            childs = [c for c, in cr.fetchall()]
            result[id] = reduce(lambda x,y:x+y, [result.get(c, 0) for c in childs], result.get(id, 0))
        return result

    _columns = {
        'name': fields.char("Name", size=128, required=True),
        'parent_id': fields.many2one('ir.module.category', 'Parent Category', select=True),
        'child_ids': fields.one2many('ir.module.category', 'parent_id', 'Child Categories'),
        'module_nr': fields.function(_module_nbr, method=True, string='Number of Modules', type='integer')
    }
    _order = 'name'
module_category()

class module(osv.osv):
    _name = "ir.module.module"
    _description = "Module"

    def get_module_info(self, name):
        info = {}
        try:
            info = addons.load_information_from_description_file(name)
            if 'version' in info:
                info['version'] = release.major_version + '.' + info['version']
        except:
            pass
        return info

    def _get_latest_version(self, cr, uid, ids, field_name=None, arg=None, context={}):
        res = dict.fromkeys(ids, '')
        for m in self.browse(cr, uid, ids):
            res[m.id] = self.get_module_info(m.name).get('version', '')
        return res

    def _get_views(self, cr, uid, ids, field_name=None, arg=None, context={}):
        res = {}
        model_data_obj = self.pool.get('ir.model.data')
        view_obj = self.pool.get('ir.ui.view')
        report_obj = self.pool.get('ir.actions.report.xml')
        menu_obj = self.pool.get('ir.ui.menu')
        mlist = self.browse(cr, uid, ids, context=context)
        mnames = {}
        for m in mlist:
            mnames[m.name] = m.id
            res[m.id] = {
                'menus_by_module':'',
                'reports_by_module':'',
                'views_by_module': ''
            }
        view_id = model_data_obj.search(cr,uid,[('module','in', mnames.keys()),
            ('model','in',('ir.ui.view','ir.actions.report.xml','ir.ui.menu'))])
        for data_id in model_data_obj.browse(cr,uid,view_id,context):
            # We use try except, because views or menus may not exist
            try:
                key = data_id['model']
                if key=='ir.ui.view':
                    try:
                        v = view_obj.browse(cr,uid,data_id.res_id)
                        aa = v.inherit_id and '* INHERIT ' or ''
                        res[mnames[data_id.module]]['views_by_module'] += aa + v.name + ' ('+v.type+')\n'
                    except:
                        pass
                elif key=='ir.actions.report.xml':
                    res[mnames[data_id.module]]['reports_by_module'] += report_obj.browse(cr,uid,data_id.res_id).name + '\n'
                elif key=='ir.ui.menu':
                    try:
                        m = menu_obj.browse(cr,uid,data_id.res_id)
                        res[mnames[data_id.module]]['menus_by_module'] += m.complete_name + '\n'
                    except:
                        pass
            except KeyError, e:
                pass
        return res

    _columns = {
        'name': fields.char("Name", size=128, readonly=True, required=True),
        'category_id': fields.many2one('ir.module.category', 'Category', readonly=True),
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
        'dependencies_id': fields.one2many('ir.module.module.dependency',
            'module_id', 'Dependencies', readonly=True),
        'state': fields.selection([
            ('uninstallable','Not Installable'),
            ('uninstalled','Not Installed'),
            ('installed','Installed'),
            ('to upgrade','To be upgraded'),
            ('to remove','To be removed'),
            ('to install','To be installed')
        ], string='State', readonly=True),
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
    }

    _defaults = {
        'state': lambda *a: 'uninstalled',
        'demo': lambda *a: False,
        'license': lambda *a: 'AGPL-3',
    }
    _order = 'name'

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'The name of the module must be unique !'),
        ('certificate_uniq', 'unique (certificate)', 'The certificate ID of the module must be unique !')
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
        ids_meta = self.pool.get('ir.model.data').search(cr, uid, [('name', '=', 'module_meta_information'), ('module', 'in', mod_names)])

        if ids_meta:
            self.pool.get('ir.model.data').unlink(cr, uid, ids_meta, context)

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


    def state_update(self, cr, uid, ids, newstate, states_to_update, context={}, level=100):
        if level<1:
            raise orm.except_orm(_('Error'), _('Recursion error in modules dependencies !'))
        demo = False
        for module in self.browse(cr, uid, ids):
            mdemo = False
            for dep in module.dependencies_id:
                if dep.state == 'unknown':
                    raise orm.except_orm(_('Error'), _("You try to install the module '%s' that depends on the module:'%s'.\nBut this module is not available in your system.") % (module.name, dep.name,))
                ids2 = self.search(cr, uid, [('name','=',dep.name)])
                if dep.state != newstate:
                    mdemo = self.state_update(cr, uid, ids2, newstate, states_to_update, context, level-1,) or mdemo
                else:
                    od = self.browse(cr, uid, ids2)[0]
                    mdemo = od.demo or mdemo
            terp = self.get_module_info(module.name)
            try:
                self._check_external_dependencies(terp)
            except Exception, e:
                raise orm.except_orm(_('Error'), _('Unable %s the module "%s" because an external dependencie is not met: %s' % (newstate, module.name, e.args[0])))
            if not module.dependencies_id:
                mdemo = module.demo
            if module.state in states_to_update:
                self.write(cr, uid, [module.id], {'state': newstate, 'demo':mdemo})
            demo = demo or mdemo
        return demo

    def button_install(self, cr, uid, ids, context={}):
        return self.state_update(cr, uid, ids, 'to install', ['uninstalled'], context)

    def button_install_cancel(self, cr, uid, ids, context={}):
        self.write(cr, uid, ids, {'state': 'uninstalled', 'demo':False})
        return True

    def button_uninstall(self, cr, uid, ids, context={}):
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
        return True

    def button_uninstall_cancel(self, cr, uid, ids, context={}):
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
        return True

    def button_upgrade_cancel(self, cr, uid, ids, context={}):
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
            'license': terp.get('license', 'GPL-2'),
            'certificate': terp.get('certificate') or None,
        }

    # update the list of available packages
    def update_list(self, cr, uid, context={}):
        res = [0, 0] # [update, add]

        # iterate through installed modules and mark them as being so
        for mod_name in addons.get_modules():
            ids = self.search(cr, uid, [('name','=',mod_name)])
            terp = self.get_module_info(mod_name)
            values = self.get_values_from_terp(terp)

            if ids:
                id = ids[0]
                mod = self.browse(cr, uid, id)
                if terp.get('installable', True) and mod.state == 'uninstallable':
                    self.write(cr, uid, id, {'state': 'uninstalled'})
                if parse_version(terp.get('version', '')) > parse_version(mod.latest_version or ''):
                    self.write(cr, uid, id, {'url': ''})
                    res[0] += 1
                self.write(cr, uid, id, values)
                cr.execute('DELETE FROM ir_module_module_dependency WHERE module_id = %s', (id,))
            else:
                mod_path = addons.get_module_path(mod_name)
                if not mod_path:
                    continue
                if not terp or not terp.get('installable', True):
                    continue

                ids = self.search(cr, uid, [('name','=',mod_name)])
                id = self.create(cr, uid, dict(name=mod_name, state='uninstalled', **values))
                res[1] += 1
            self._update_dependencies(cr, uid, id, terp.get('depends', []))
            self._update_category(cr, uid, id, terp.get('category', 'Uncategorized'))

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
            zipfile = urllib.urlopen(mod.url).read()
            fname = addons.get_module_path(str(mod.name)+'.zip', downloaded=True)
            try:
                fp = file(fname, 'wb')
                fp.write(zipfile)
                fp.close()
            except Exception, e:
                raise orm.except_orm(_('Error'), _('Can not create the module file:\n %s') % (fname,))
            terp = self.get_module_info(mod.name)
            self.write(cr, uid, mod.id, self.get_values_from_terp(terp))
            cr.execute('DELETE FROM ir_module_module_dependency ' \
                    'WHERE module_id = %s', (mod.id,))
            self._update_dependencies(cr, uid, mod.id, terp.get('depends',
                []))
            self._update_category(cr, uid, mod.id, terp.get('category',
                'Uncategorized'))
            # Import module
            zimp = zipimport.zipimporter(fname)
            zimp.load_module(mod.name)
        return res

    def _update_dependencies(self, cr, uid, id, depends=[]):
        for d in depends:
            cr.execute('INSERT INTO ir_module_module_dependency (module_id, name) values (%s, %s)', (id, d))

    def _update_category(self, cr, uid, id, category='Uncategorized'):
        categs = category.split('/')
        p_id = None
        while categs:
            if p_id is not None:
                cr.execute('select id from ir_module_category where name=%s and parent_id=%s', (categs[0], p_id))
            else:
                cr.execute('select id from ir_module_category where name=%s and parent_id is NULL', (categs[0],))
            c_id = cr.fetchone()
            if not c_id:
                cr.execute('select nextval(\'ir_module_category_id_seq\')')
                c_id = cr.fetchone()[0]
                cr.execute('insert into ir_module_category (id, name, parent_id) values (%s, %s, %s)', (c_id, categs[0], p_id))
            else:
                c_id = c_id[0]
            p_id = c_id
            categs = categs[1:]
        self.write(cr, uid, [id], {'category_id': p_id})

    def update_translations(self, cr, uid, ids, filter_lang=None):
        logger = netsvc.Logger()
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
                if len(lang) > 5:
                    raise osv.except_osv(_('Error'), _('You Can Not Load Translation For language Due To Invalid Language/Country Code'))
                iso_lang = tools.get_iso_codes(lang)
                f = os.path.join(modpath, 'i18n', iso_lang + '.po')
                if not os.path.exists(f) and iso_lang.find('_') != -1:
                    f = os.path.join(modpath, 'i18n', iso_lang.split('_')[0] + '.po')
                    iso_lang = iso_lang.split('_')[0]
                if os.path.exists(f):
                    logger.notifyChannel("i18n", netsvc.LOG_INFO, 'module %s: loading translation file for language %s' % (mod.name, iso_lang))
                    tools.trans_load(cr.dbname, f, lang, verbose=False)

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

module()

class module_dependency(osv.osv):
    _name = "ir.module.module.dependency"
    _description = "Module dependency"

    def _state(self, cr, uid, ids, name, args, context={}):
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
        'name': fields.char('Name',  size=128),
        'module_id': fields.many2one('ir.module.module', 'Module', select=True, ondelete='cascade'),
        'state': fields.function(_state, method=True, type='selection', selection=[
            ('uninstallable','Uninstallable'),
            ('uninstalled','Not Installed'),
            ('installed','Installed'),
            ('to upgrade','To be upgraded'),
            ('to remove','To be removed'),
            ('to install','To be installed'),
            ('unknown', 'Unknown'),
            ], string='State', readonly=True),
    }
module_dependency()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

