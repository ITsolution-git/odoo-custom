#!/usr/bin/env python
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

# setup from TinERP
#   taken from straw http://www.nongnu.org/straw/index.html
#   taken from gnomolicious http://www.nongnu.org/gnomolicious/
#   adapted by Nicolas Évrard <nicoe@altern.org>
#

import imp
import sys
import os
import glob

from distutils.core import setup, Command
from distutils.command.install import install

has_py2exe = False
if os.name == 'nt':
    import py2exe
    has_py2exe = True

sys.path.append(os.path.join(os.path.abspath(os.path.dirname(__file__)), "bin"))

opj = os.path.join

execfile(opj('bin', 'release.py'))

if sys.argv[1] == 'bdist_rpm':
    version = version.split('-')[0]

# get python short version
py_short_version = '%s.%s' % sys.version_info[:2]

required_modules = [
    ('psycopg2', 'PostgreSQL module'),
    ('xml', 'XML Tools for python'),
    ('reportlab', 'reportlab module'),
    ('pychart', 'pychart module'),
    ('pydot', 'pydot module'),
    ('lxml', 'lxml module: pythonic libxml2 and libxslt bindings'),
]

def check_modules():
    ok = True
    for modname, desc in required_modules:
        try:
            exec('import %s' % modname)
        except ImportError:
            ok = False
            print 'Error: python module %s (%s) is required' % (modname, desc)

    if not ok:
        sys.exit(1)

def _find_addons():
    for (dp, dn, names) in os.walk(opj('bin', 'addons')):
        if '__terp__.py' in names:
            modname = os.path.basename(dp)
            yield (modname, dp)
    #look for extra modules
    try:
        empath = os.getenv('EXTRA_MODULES_PATH','../addons/')
        f = open(opj(empath,'server_modules.list'),'r')
        # print 'Getting modules from:' , opj(empath,'server_modules.list')
        mods = f.readlines()
        for mname in mods:
            mname = mname.strip()
            if not mname:
                continue
            if os.path.exists(opj(empath,mname,'__terp__.py')):
                yield ( mname, opj(empath,mname) )
            else:
                print "Module %s specified, but no valid path." % mname
    except:
        pass

__found_addons = None

# Cache the results of _find_addons() and return them
def find_addons(found_addons = None):
    if not found_addons:
        found_addons = _find_addons()
    return found_addons

def data_files():
    '''Build list of data files to be installed'''
    files = []
    if os.name == 'nt':
        os.chdir('bin')
        for (dp,dn,names) in os.walk('addons'):
            files.append((dp, map(lambda x: opj('bin', dp, x), names)))
        os.chdir('..')
        for (dp,dn,names) in os.walk('doc'):
            files.append((dp, map(lambda x: opj(dp, x), names)))
        files.append(('.', [opj('bin', 'import_xml.rng'),
                            opj('bin', 'server.pkey'),
                            opj('bin', 'server.cert')]))
    else:
        man_directory = opj('share', 'man')
        files.append((opj(man_directory, 'man1'), ['man/openerp-server.1']))
        files.append((opj(man_directory, 'man5'), ['man/openerp_serverrc.5']))

        doc_directory = opj('share', 'doc', 'openerp-server-%s' % version)
        files.append((doc_directory, [f for f in glob.glob('doc/*') if os.path.isfile(f)]))
        files.append((opj(doc_directory, 'migrate', '3.3.0-3.4.0'), [f for f in glob.glob('doc/migrate/3.3.0-3.4.0/*') if os.path.isfile(f)]))
        files.append((opj(doc_directory, 'migrate', '3.4.0-4.0.0'), [f for f in glob.glob('doc/migrate/3.4.0-4.0.0/*') if os.path.isfile(f)]))

        openerp_site_packages = opj('lib', 'python%s' % py_short_version, 'site-packages', 'openerp-server')

        files.append((openerp_site_packages, [opj('bin', 'import_xml.rng'),
                                              opj('bin', 'server.pkey'),
                                              opj('bin', 'server.cert')]))

        if sys.version_info[0:2] == (2,5):
            files.append((openerp_site_packages, [ opj('python25-compat','BaseHTTPServer.py'),
                                                   opj('python25-compat','SimpleXMLRPCServer.py'),
                                                   opj('python25-compat','SocketServer.py')]))

        for (addonname, add_path) in find_addons():
            addon_path = opj('lib', 'python%s' % py_short_version, 'site-packages', 'openerp-server','addons', addonname)
            pathfiles = []
            for root, dirs, innerfiles in os.walk(add_path):
                innerfiles = filter(lambda fil: os.path.splitext(fil)[1] not in ('.pyc', '.pyd', '.pyo'), innerfiles)
                if innerfiles:
                    res = os.path.normpath(opj(addon_path, root.replace(opj(add_path), '.')))
                    pathfiles.extend(((res, map(lambda fil: opj(root, fil), innerfiles)),))
            files.extend(pathfiles)

    # for tup in files:
    #    print "Files:", tup[0], tup[1]
    return files

if not os.getenv('NO_CHECK_MODULES',False) :
    check_modules()

f = file('openerp-server','w')
start_script = """#!/bin/sh\necho "OpenERP Setup - The content of this file is generated at the install stage\n" """
f.write(start_script)
f.close()

def find_package_dirs():
    res = {}
    for (mod, path) in find_addons():
        res ['openerp-server.addons.'+ mod ] = path
    res ['openerp-server'] = 'bin'
    return res

class openerp_server_install(install):
    def run(self):
        # create startup script
        start_script = "#!/bin/sh\ncd %s\nexec %s ./openerp-server.py $@\n" % (opj(self.install_libbase, "openerp-server"), sys.executable)
        # write script
        f = open('openerp-server', 'w')
        f.write(start_script)
        f.close()
        install.run(self)

options = {
    "py2exe": {
        "compressed": 1,
        "optimize": 2,
        "dist_dir": 'dist',
        "packages": ["lxml", "lxml.builder", "lxml._elementpath", "lxml.etree",
                     "lxml.objectify", "decimal", "xml", "xml.dom", "xml.xpath",
                     "encodings","mx.DateTime","wizard","pychart","PIL", "pyparsing",
                     "pydot","asyncore","asynchat", "reportlab", "vobject",
                     "HTMLParser", "select"],
        "excludes" : ["Tkconstants","Tkinter","tcl"],
    }
}

setup(name             = name,
      version          = version,
      description      = description,
      long_description = long_desc,
      url              = url,
      author           = author,
      author_email     = author_email,
      classifiers      = filter(None, classifiers.split("\n")),
      license          = license,
      data_files       = data_files(),
      cmdclass         = {
            'install' : openerp_server_install,
      },
      scripts          = ['openerp-server'],
      packages         = ['openerp-server',
                          'openerp-server.addons',
                          'openerp-server.ir',
                          'openerp-server.osv',
                          'openerp-server.service',
                          'openerp-server.tools',
                          'openerp-server.report',
                          'openerp-server.report.printscreen',
                          'openerp-server.report.pyPdf',
                          'openerp-server.report.render',
                          'openerp-server.report.render.rml2pdf',
                          'openerp-server.report.render.rml2html',
                          'openerp-server.report.render.rml2txt',
                          'openerp-server.report.render.html2html',
                          'openerp-server.wizard',
                          'openerp-server.report.render.odt2odt',
                          'openerp-server.workflow'] + \
                          list(map( lambda (a, p): 'openerp-server.addons.'+ a ,find_addons())),
      package_dir      = find_package_dirs(),
      console = [ { "script" : "bin\\openerp-server.py", "icon_resources" : [ (1,"pixmaps\\openerp-icon.ico") ] } ],
      options = options,
      )

if has_py2exe:
  # Sometime between pytz-2008a and pytz-2008i common_timezones started to
  # include only names of zones with a corresponding data file in zoneinfo.
  # pytz installs the zoneinfo directory tree in the same directory
  # as the pytz/__init__.py file. These data files are loaded using
  # pkg_resources.resource_stream. py2exe does not copy this to library.zip so
  # resource_stream can't find the files and common_timezones is empty when
  # read in the py2exe executable.
  # This manually copies zoneinfo into the zip. See also
  # http://code.google.com/p/googletransitdatafeed/issues/detail?id=121
  import pytz
  import zipfile
  # Make sure the layout of pytz hasn't changed
  assert (pytz.__file__.endswith('__init__.pyc') or
          pytz.__file__.endswith('__init__.py')), pytz.__file__
  zoneinfo_dir = os.path.join(os.path.dirname(pytz.__file__), 'zoneinfo')
  # '..\\Lib\\pytz\\__init__.py' -> '..\\Lib'
  disk_basedir = os.path.dirname(os.path.dirname(pytz.__file__))
  zipfile_path = os.path.join(options['py2exe']['dist_dir'], 'library.zip')
  z = zipfile.ZipFile(zipfile_path, 'a')
  for absdir, directories, filenames in os.walk(zoneinfo_dir):
    assert absdir.startswith(disk_basedir), (absdir, disk_basedir)
    zip_dir = absdir[len(disk_basedir):]
    for f in filenames:
      z.write(os.path.join(absdir, f), os.path.join(zip_dir, f))
  z.close()

