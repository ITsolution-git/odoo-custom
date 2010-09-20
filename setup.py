#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
from os.path import join, isfile, basename
import glob

from setuptools import setup, find_packages
from setuptools.command.install import install
from distutils.sysconfig import get_python_lib

has_py2exe = False
if os.name == 'nt':
    import py2exe
    has_py2exe = True

sys.path.append(join(os.path.abspath(os.path.dirname(__file__)), "bin"))

execfile(join('bin', 'release.py'))

if 'bdist_rpm' in sys.argv:
    version = version.split('-')[0]

# get python short version
py_short_version = '%s.%s' % sys.version_info[:2]

def find_addons():
    for root, _, names in os.walk(join('bin', 'addons'), followlinks=True):
        if '__openerp__.py' in names or '__terp__.py' in names:
            yield basename(root), root

def data_files():
    '''Build list of data files to be installed'''
    files = []
    if os.name == 'nt':
        for root, _, names in os.walk(join('bin','addons')):
            files.append((root, [join(root, name) for name in names]))
        for root, _, names in os.walk('doc'):
            files.append((root, [join(root, name) for name in names]))
        for root, _, names in os.walk('pixmaps'):
            files.append((root, [join(root, name) for name in names]))
        files.append(('.', [join('bin', 'import_xml.rng'),
                            join('bin', 'server.pkey'),
                            join('bin', 'server.cert')]))
    else:
        man_directory = join('share', 'man')
        files.append((join(man_directory, 'man1'), ['man/openerp-server.1']))
        files.append((join(man_directory, 'man5'), ['man/openerp_serverrc.5']))

        doc_directory = join('share', 'doc', 'openerp-server-%s' % version)
        files.append((doc_directory, filter(isfile, glob.glob('doc/*'))))
        files.append((join(doc_directory, 'migrate', '3.3.0-3.4.0'),
                      filter(isfile, glob.glob('doc/migrate/3.3.0-3.4.0/*'))))
        files.append((join(doc_directory, 'migrate', '3.4.0-4.0.0'),
                      filter(isfile, glob.glob('doc/migrate/3.4.0-4.0.0/*'))))

        openerp_site_packages = join(get_python_lib(prefix=''), 'openerp-server')

        files.append((openerp_site_packages, [join('bin', 'import_xml.rng'),
                                              join('bin', 'server.pkey'),
                                              join('bin', 'server.cert')]))

        if sys.version_info[0:2] == (2,5):
            files.append((openerp_site_packages, [ join('python25-compat','BaseHTTPServer.py'),
                                                   join('python25-compat','SimpleXMLRPCServer.py'),
                                                   join('python25-compat','SocketServer.py')]))

        for addonname, add_path in find_addons():
            addon_path = join(get_python_lib(prefix=''), 'openerp-server','addons', addonname)
            for root, dirs, innerfiles in os.walk(add_path):
                innerfiles = filter(lambda fil: os.path.splitext(fil)[1] not in ('.pyc', '.pyd', '.pyo'), innerfiles)
                if innerfiles:
                    res = os.path.normpath(join(addon_path, root.replace(join(add_path), '.')))
                    files.extend(((res, map(lambda fil: join(root, fil),
                                            innerfiles)),))

    return files

f = file('openerp-server','w')
f.write("""#!/bin/sh
echo "Error: the content of this file should have been replaced during "
echo "installation\n"
exit 1
""")
f.close()

def find_package_dirs():
    package_dirs = {'openerp-server': 'bin'}
    for mod, path in find_addons():
        package_dirs['openerp-server.addons.' + mod] = path
    return package_dirs

class openerp_server_install(install):
    def run(self):
        # create startup script
        start_script = "#!/bin/sh\ncd %s\nexec %s ./openerp-server.py $@\n"\
            % (join(self.install_libbase, "openerp-server"), sys.executable)
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
        "packages": [
                 "lxml", "lxml.builder", "lxml._elementpath", "lxml.etree",
                 "lxml.objectify", "decimal", "xml", "xml", "xml.dom", "xml.xpath",
                 "encodings", "dateutil", "wizard", "pychart", "PIL", "pyparsing",
                 "pydot", "asyncore","asynchat", "reportlab", "vobject",
                 "HTMLParser", "select", "mako", "poplib",
                 "imaplib", "smtplib", "email", "yaml", "DAV",
                 ],
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
      packages = [
          '.'.join(['openerp-server'] + package.split('.')[1:]) for package in find_packages()
      ],
      package_dir      = find_package_dirs(),
      console = [
          {
              "script": join("bin", "openerp-server.py"),
              "icon_resources": [(1, join("pixmaps","openerp-icon.ico"))]
          }
      ],
      options = options,
      install_requires = ['lxml',
                          'mako',
                          'python-dateutil',
                          'psycopg2',
                          'pychart',
                          'pydot',
                          'pytz',
                          'reportlab',
                          'caldav',
                          'pyyaml',
                          'sqlalchemy',
                          'django',
                          'pywebdav'
                          'cx_Oracle',
                          'mysqldb',
                          'feedparser',
                          'bsddb3',
                          'egenix-mx-base'],
      extras_require={
          'SSL' : ['pyopenssl'],
      }
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
  zoneinfo_dir = join(os.path.dirname(pytz.__file__), 'zoneinfo')
  # '..\\Lib\\pytz\\__init__.py' -> '..\\Lib'
  disk_basedir = os.path.dirname(os.path.dirname(pytz.__file__))
  zipfile_path = join(options['py2exe']['dist_dir'], 'library.zip')
  z = zipfile.ZipFile(zipfile_path, 'a')
  for absdir, directories, filenames in os.walk(zoneinfo_dir):
    assert absdir.startswith(disk_basedir), (absdir, disk_basedir)
    zip_dir = absdir[len(disk_basedir):]
    for f in filenames:
      z.write(join(absdir, f), join(zip_dir, f))
  z.close()

