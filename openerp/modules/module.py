# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2010-2011 OpenERP s.a. (<http://openerp.com>).
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

import os, sys, imp
from os.path import join as opj
import itertools
import zipimport

import openerp

import openerp.osv as osv
import openerp.tools as tools
import openerp.tools.osutil as osutil
from openerp.tools.safe_eval import safe_eval as eval
from openerp.tools.translate import _

import openerp.netsvc as netsvc

import zipfile
import openerp.release as release

import re
import base64
from zipfile import PyZipFile, ZIP_DEFLATED
from cStringIO import StringIO

import logging

import openerp.modules.db
import openerp.modules.graph

_logger = logging.getLogger(__name__)

_ad = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'addons') # default addons path (base)
ad_paths = []

# Modules already loaded
loaded = []

logger = netsvc.Logger()

class AddonsImportHook(object):
    """
    Import hook to load OpenERP addons from multiple paths.

    OpenERP implements its own import-hook to load its addons. OpenERP
    addons are Python modules. Originally, they were each living in their
    own top-level namespace, e.g. the sale module, or the hr module. For
    backward compatibility, `import <module>` is still supported. Now they
    are living in `openerp.addons`. The good way to import such modules is
    thus `import openerp.addons.module`.

    For backward compatibility, loading an addons puts it in `sys.modules`
    under both the legacy (short) name, and the new (longer) name. This
    ensures that
        import hr
        import openerp.addons.hr
    loads the hr addons only once.

    When an OpenERP addons name clashes with some other installed Python
    module (for instance this is the case of the `resource` addons),
    obtaining the OpenERP addons is only possible with the long name. The
    short name will give the expected Python module.

    Instead of relying on some addons path, an alternative approach would be
    to use pkg_resources entry points from already installed Python libraries
    (and install our addons as such). Even when implemented, we would still
    have to support the addons path approach for backward compatibility.
    """

    def find_module(self, module_name, package_path):
        module_parts = module_name.split('.')
        if len(module_parts) == 3 and module_name.startswith('openerp.addons.'):
            return self # We act as a loader too.

        # TODO list of loadable modules can be cached instead of always
        # calling get_module_path().
        if len(module_parts) == 1 and \
            get_module_path(module_parts[0],
                display_warning=False):
            try:
                # Check if the bare module name clashes with another module.
                f, path, descr = imp.find_module(module_parts[0])
                logger = logging.getLogger('init')
                logger.warning("""
Ambiguous import: the OpenERP module `%s` is shadowed by another
module (available at %s).
To import it, use `import openerp.addons.<module>.`.""" % (module_name, path))
                return
            except ImportError, e:
                # Using `import <module_name>` instead of
                # `import openerp.addons.<module_name>` is ugly but not harmful
                # and kept for backward compatibility.
                return self # We act as a loader too.

    def load_module(self, module_name):

        module_parts = module_name.split('.')
        if len(module_parts) == 3 and module_name.startswith('openerp.addons.'):
            module_part = module_parts[2]
            if module_name in sys.modules:
                return sys.modules[module_name]

        if len(module_parts) == 1:
            module_part = module_parts[0]
            if module_part in sys.modules:
                return sys.modules[module_part]

        try:
            # Check if the bare module name shadows another module.
            f, path, descr = imp.find_module(module_part)
            is_shadowing = True
        except ImportError, e:
            # Using `import <module_name>` instead of
            # `import openerp.addons.<module_name>` is ugly but not harmful
            # and kept for backward compatibility.
            is_shadowing = False

        # Note: we don't support circular import.
        f, path, descr = imp.find_module(module_part, ad_paths)
        mod = imp.load_module(module_name, f, path, descr)
        if not is_shadowing:
            sys.modules[module_part] = mod
            for k in sys.modules.keys():
                if k.startswith('openerp.addons.' + module_part):
                    sys.modules[k[len('openerp.addons.'):]] = sys.modules[k]
        sys.modules['openerp.addons.' + module_part] = mod
        return mod

def initialize_sys_path():
    """
    Setup an import-hook to be able to import OpenERP addons from the different
    addons paths.

    This ensures something like ``import crm`` (or even
    ``import openerp.addons.crm``) works even if the addons are not in the
    PYTHONPATH.
    """
    global ad_paths
    if ad_paths:
        return

    ad_paths = map(lambda m: os.path.abspath(tools.ustr(m.strip())), tools.config['addons_path'].split(','))
    ad_paths.append(_ad) # for get_module_path
    sys.meta_path.append(AddonsImportHook())

def get_module_path(module, downloaded=False, display_warning=True):
    """Return the path of the given module.

    Search the addons paths and return the first path where the given
    module is found. If downloaded is True, return the default addons
    path if nothing else is found.

    """
    initialize_sys_path()
    for adp in ad_paths:
        if os.path.exists(opj(adp, module)) or os.path.exists(opj(adp, '%s.zip' % module)):
            return opj(adp, module)

    if downloaded:
        return opj(_ad, module)
    if display_warning:
        logger.notifyChannel('init', netsvc.LOG_WARNING, 'module %s: module not found' % (module,))
    return False


def get_module_filetree(module, dir='.'):
    path = get_module_path(module)
    if not path:
        return False

    dir = os.path.normpath(dir)
    if dir == '.':
        dir = ''
    if dir.startswith('..') or (dir and dir[0] == '/'):
        raise Exception('Cannot access file outside the module')

    if not os.path.isdir(path):
        # zipmodule
        zip = zipfile.ZipFile(path + ".zip")
        files = ['/'.join(f.split('/')[1:]) for f in zip.namelist()]
    else:
        files = osutil.listdir(path, True)

    tree = {}
    for f in files:
        if not f.startswith(dir):
            continue

        if dir:
            f = f[len(dir)+int(not dir.endswith('/')):]
        lst = f.split(os.sep)
        current = tree
        while len(lst) != 1:
            current = current.setdefault(lst.pop(0), {})
        current[lst.pop(0)] = None

    return tree

def zip_directory(directory, b64enc=True, src=True):
    """Compress a directory

    @param directory: The directory to compress
    @param base64enc: if True the function will encode the zip file with base64
    @param src: Integrate the source files

    @return: a string containing the zip file
    """

    RE_exclude = re.compile('(?:^\..+\.swp$)|(?:\.py[oc]$)|(?:\.bak$)|(?:\.~.~$)', re.I)

    def _zippy(archive, path, src=True):
        path = os.path.abspath(path)
        base = os.path.basename(path)
        for f in osutil.listdir(path, True):
            bf = os.path.basename(f)
            if not RE_exclude.search(bf) and (src or bf in ('__openerp__.py', '__terp__.py') or not bf.endswith('.py')):
                archive.write(os.path.join(path, f), os.path.join(base, f))

    archname = StringIO()
    archive = PyZipFile(archname, "w", ZIP_DEFLATED)

    # for Python 2.5, ZipFile.write() still expects 8-bit strings (2.6 converts to utf-8)
    directory = tools.ustr(directory).encode('utf-8')

    archive.writepy(directory)
    _zippy(archive, directory, src=src)
    archive.close()
    archive_data = archname.getvalue()
    archname.close()

    if b64enc:
        return base64.encodestring(archive_data)

    return archive_data

def get_module_as_zip(modulename, b64enc=True, src=True):
    """Generate a module as zip file with the source or not and can do a base64 encoding

    @param modulename: The module name
    @param b64enc: if True the function will encode the zip file with base64
    @param src: Integrate the source files

    @return: a stream to store in a file-like object
    """

    ap = get_module_path(str(modulename))
    if not ap:
        raise Exception('Unable to find path for module %s' % modulename)

    ap = ap.encode('utf8')
    if os.path.isfile(ap + '.zip'):
        val = file(ap + '.zip', 'rb').read()
        if b64enc:
            val = base64.encodestring(val)
    else:
        val = zip_directory(ap, b64enc, src)

    return val


def get_module_resource(module, *args):
    """Return the full path of a resource of the given module.

    @param module: the module
    @param args: the resource path components

    @return: absolute path to the resource

    TODO name it get_resource_path
    TODO make it available inside on osv object (self.get_resource_path)
    """
    a = get_module_path(module)
    if not a: return False
    resource_path = opj(a, *args)
    if zipfile.is_zipfile( a +'.zip') :
        zip = zipfile.ZipFile( a + ".zip")
        files = ['/'.join(f.split('/')[1:]) for f in zip.namelist()]
        resource_path = '/'.join(args)
        if resource_path in files:
            return opj(a, resource_path)
    elif os.path.exists(resource_path):
        return resource_path
    return False

def get_module_icon(module):
    iconpath = ['static', 'src', 'img', 'icon.png']
    if get_module_resource(module, *iconpath):
        return ('/' + module + '/') + '/'.join(iconpath)
    return '/base/'  + '/'.join(iconpath)

def load_information_from_description_file(module):
    """
    :param module: The name of the module (sale, purchase, ...)
    """

    terp_file = get_module_resource(module, '__openerp__.py')
    if not terp_file:
        terp_file = get_module_resource(module, '__terp__.py')
    mod_path = get_module_path(module)
    if terp_file:
        info = {}
        if os.path.isfile(terp_file) or zipfile.is_zipfile(mod_path+'.zip'):
            # default values for descriptor
            info = {
                'application': False,
                'author': '',
                'auto_install': False,
                'category': 'Uncategorized',
                'certificate': None,
                'complexity': 'normal',
                'depends': [],
                'description': '',
                'icon': get_module_icon(module),
                'installable': True,
                'auto_install': False,
                'license': 'AGPL-3',
                'name': False,
                'post_load': None,
                'version': '0.0.0',
                'web': False,
                'website': '',
                'sequence': 100,
            }
            info.update(itertools.izip(
                'depends data demo test init_xml update_xml demo_xml'.split(),
                iter(list, None)))

            f = tools.file_open(terp_file)
            try:
                info.update(eval(f.read()))
            finally:
                f.close()

            if 'active' in info:
                # 'active' has been renamed 'auto_install'
                info['auto_install'] = info['active']

            return info

    #TODO: refactor the logger in this file to follow the logging guidelines
    #      for 6.0
    logging.getLogger('modules').debug('module %s: no descriptor file'
        ' found: __openerp__.py or __terp__.py (deprecated)', module)
    return {}


def init_module_models(cr, module_name, obj_list):
    """ Initialize a list of models.

    Call _auto_init and init on each model to create or update the
    database tables supporting the models.

    TODO better explanation of _auto_init and init.

    """
    logger.notifyChannel('init', netsvc.LOG_INFO,
        'module %s: creating or updating database tables' % module_name)
    todo = []
    for obj in obj_list:
        result = obj._auto_init(cr, {'module': module_name})
        if result:
            todo += result
        if hasattr(obj, 'init'):
            obj.init(cr)
        cr.commit()
    for obj in obj_list:
        obj._auto_end(cr, {'module': module_name})
        cr.commit()
    todo.sort()
    for t in todo:
        t[1](cr, *t[2])
    cr.commit()

def register_module_classes(m):
    """ Register module named m, if not already registered.

    This loads the module and register all of its models, thanks to either
    the MetaModel metaclass, or the explicit instantiation of the model.

    """

    def log(e):
        mt = isinstance(e, zipimport.ZipImportError) and 'zip ' or ''
        msg = "Couldn't load %smodule %s" % (mt, m)
        logger.notifyChannel('init', netsvc.LOG_CRITICAL, msg)
        logger.notifyChannel('init', netsvc.LOG_CRITICAL, e)

    global loaded
    if m in loaded:
        return
    logger.notifyChannel('init', netsvc.LOG_INFO, 'module %s: registering objects' % m)
    mod_path = get_module_path(m)

    initialize_sys_path()
    try:
        zip_mod_path = mod_path + '.zip'
        if not os.path.isfile(zip_mod_path):
            __import__('openerp.addons.' + m)
        else:
            zimp = zipimport.zipimporter(zip_mod_path)
            zimp.load_module(m)
    except Exception, e:
        log(e)
        raise
    else:
        loaded.append(m)


def get_modules():
    """Returns the list of module names
    """
    def listdir(dir):
        def clean(name):
            name = os.path.basename(name)
            if name[-4:] == '.zip':
                name = name[:-4]
            return name

        def is_really_module(name):
            name = opj(dir, name)
            return os.path.isdir(name) or zipfile.is_zipfile(name)
        return map(clean, filter(is_really_module, os.listdir(dir)))

    plist = []
    initialize_sys_path()
    for ad in ad_paths:
        plist.extend(listdir(ad))
    return list(set(plist))


def get_modules_with_version():
    modules = get_modules()
    res = {}
    for module in modules:
        try:
            info = load_information_from_description_file(module)
            res[module] = "%s.%s" % (release.major_version, info['version'])
        except Exception, e:
            continue
    return res


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
