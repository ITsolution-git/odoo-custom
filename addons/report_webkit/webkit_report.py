# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2010 Camptocamp SA (http://www.camptocamp.com) 
# All Right Reserved
#
# Author : Nicolas Bessi (Camptocamp)
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

import commands
import os
import report
import tempfile
import time
from mako.template import Template

import netsvc
import pooler
from report_helper import WebKitHelper
from report.report_sxw import *
from tools.config import config
from tools.translate import _
from osv.osv import except_osv

class WebKitParser(report_sxw):
    """Custom class that use webkit to render HTML reports
       Code partially taken from report openoffice. Thanks guys :)
    """
    
    def __init__(self, name, table, rml=False, parser=False, 
        header=True, store=False):
        self.parser_instance = False
        self.localcontext={}
        report_sxw.__init__(self, name, table, rml, parser, 
            header, store)

    def get_lib(self, cursor, uid, company) :
        """Return the lib wkhtml path"""
        #TODO Detect lib in system first
        path = self.pool.get('res.company').read(cursor, uid, company, ['lib_path',])
        path = path['lib_path']
        if not path:
            raise except_osv(
                             _('Wkhtmltopdf library path is not set in company'),
                             _('Please install executable on your system'+
                             ' (sudo apt-get install wkhtmltopdf) or download it from here:'+
                             ' http://code.google.com/p/wkhtmltopdf/downloads/list and set the'+
                             ' path to the executable on the Company form.')
                            ) 
        if os.path.isabs(path) :
            if (os.path.exists(path) and os.access(path, os.X_OK)\
                and os.path.basename(path).startswith('wkhtmltopdf')):
                return path
            else:
                raise except_osv(
                                _('Wrong Wkhtmltopdf path set in company'+
                                'Given path is not executable or path is wrong'),
                                'for path %s'%(path)
                                )
        else :
            raise except_osv(
                            _('path to Wkhtmltopdf is not absolute'),
                            'for path %s'%(path)
                            )
    def generate_pdf(self, comm_path, report_xml, header, footer, html_list):
        """Call webkit in order to generate pdf"""
        tmp_dir = tempfile.gettempdir()
        out = report_xml.name+str(time.time())+'.pdf'
        out = os.path.join(tmp_dir, out.replace(' ',''))
        files = []
        file_to_del = []
        if comm_path:
            command = [comm_path]
        else:
            command = ['wkhtmltopdf']
                
        command.append('-q')
        if header :
            head_file = file( os.path.join(
                                  tmp_dir,
                                  str(time.time()) + '.head.html'
                                 ), 
                                'w'
                            )
            head_file.write(header)
            head_file.close()
            file_to_del.append(head_file.name)
            command.append("--header-html '%s'"%(head_file.name))
        if footer :
            foot_file = file(  os.path.join(
                                  tmp_dir,
                                  str(time.time()) + '.foot.html'
                                 ), 
                                'w'
                            )
            foot_file.write(footer)
            foot_file.close()
            file_to_del.append(foot_file.name)
            command.append("--footer-html '%s'"%(foot_file.name))
            
        if report_xml.webkit_header.margin_top :
            command.append('--margin-top %s'%(report_xml.webkit_header.margin_top))
        if report_xml.webkit_header.margin_bottom :
            command.append('--margin-bottom %s'%(report_xml.webkit_header.margin_bottom))
        if report_xml.webkit_header.margin_left :
            command.append('--margin-left %s'%(report_xml.webkit_header.margin_left))
        if report_xml.webkit_header.margin_right :
            command.append('--margin-right %s'%(report_xml.webkit_header.margin_right))
        if report_xml.webkit_header.orientation :
            command.append("--orientation '%s'"%(report_xml.webkit_header.orientation))
        if report_xml.webkit_header.format :
            command.append(" --page-size '%s'"%(report_xml.webkit_header.format))
        for html in html_list :
            html_file = file(os.path.join(tmp_dir, str(time.time()) + '.body.html'), 'w')
            html_file.write(html)
            html_file.close()
            file_to_del.append(html_file.name)
            command.append(html_file.name)
        command.append(out)
        generate_command = ' '.join(command)
        try:
            status = commands.getstatusoutput(generate_command)
            if status[0] :
                raise except_osv(
                                _('Webkit raise an error' ), 
                                status[1]
                            )
        except Exception:
            for f_to_del in file_to_del :
                os.unlink(f_to_del)

        pdf = file(out).read()
        for f_to_del in file_to_del :
            os.unlink(f_to_del)

        os.unlink(out)
        return pdf
    
    
    def setLang(self, lang):
        if not lang:
            lang = 'en_US'
        self.localcontext['lang'] = lang

    def translate_call(self, src):
        """Translate String."""
        ir_translation = self.pool.get('ir.translation')
        res = ir_translation._get_source(self.parser_instance.cr, self.parser_instance.uid, self.name, 'report', self.localcontext.get('lang', 'en_US'), src)
        return res 
 
    def formatLang(self, value, digits=None, date=False, date_time=False, grouping=True, monetary=False):
        """format using the know cursor, language from localcontext"""
        if digits is None:
            digits = self.parser_instance.get_digits(value)
        if isinstance(value, (str, unicode)) and not value:
            return ''
        pool_lang = self.pool.get('res.lang')
        lang = self.localcontext['lang']
        
        lang_ids = pool_lang.search(self.parser_instance.cr, self.parser_instance.uid, [('code','=',lang)])[0]
        lang_obj = pool_lang.browse(self.parser_instance.cr, self.parser_instance.uid, lang_ids)

        if date or date_time:
            if not str(value):
                return ''

            date_format = lang_obj.date_format
            parse_format = '%Y-%m-%d'
            if date_time:
                value=value.split('.')[0]
                date_format = date_format + " " + lang_obj.time_format
                parse_format = '%Y-%m-%d %H:%M:%S'
            if not isinstance(value, time.struct_time):
                return time.strftime(date_format, time.strptime(value, parse_format))

            else:
                date = datetime(*value.timetuple()[:6])
            return date.strftime(date_format)

        return lang_obj.format('%.' + str(digits) + 'f', value, grouping=grouping, monetary=monetary)

    # override needed to keep the attachments' storing procedure
    def create_single_pdf(self, cursor, uid, ids, data, report_xml, context=None):
        """generate the PDF"""
        
        if not context:
            context={}
            
        if report_xml.report_type != 'webkit':
            return super(WebKitParser,self).create_single_pdf(cursor, uid, ids, data, report_xml, context=context)

        self.parser_instance = self.parser(
                                            cursor, 
                                            uid, 
                                            self.name2, 
                                            context=context
                                        )

        self.pool = pooler.get_pool(cursor.dbname)
        objs = self.getObjects(cursor, uid, ids, context)
        self.parser_instance.set_context(objs, data, ids, report_xml.report_type)

        template =  False

        if report_xml.report_file :
            path = os.path.join(config['addons_path'], report_xml.report_file)
            if os.path.exists(path) :
                template = file(path).read()
        if not template and report_xml.report_webkit_data :
            template =  report_xml.report_webkit_data
        if not template :
            raise except_osv(_('Webkit Report template not found !'), _(''))
        header = report_xml.webkit_header.html
        footer = report_xml.webkit_header.footer_html
        if not header and report_xml.header:
          raise except_osv(
                _('No header defined for this Webkit report!'),
                _('Please set a header in company settings')
            )
        if not report_xml.header :
            #I know it could be cleaner ...
            header = u"""
<html>
    <head>
        <style type="text/css"> 
            ${css}
        </style>
        <script>
        function subst() {
           var vars={};
           var x=document.location.search.substring(1).split('&');
           for(var i in x) {var z=x[i].split('=',2);vars[z[0]] = unescape(z[1]);}
           var x=['frompage','topage','page','webpage','section','subsection','subsubsection'];
           for(var i in x) {
             var y = document.getElementsByClassName(x[i]);
             for(var j=0; j<y.length; ++j) y[j].textContent = vars[x[i]];
           }
         }
        </script>
    </head>
<body style="border:0; margin: 0;" onload="subst()">
</body>
</html>"""
        css = report_xml.webkit_header.css
        if not css :
            css = ''
        user = self.pool.get('res.users').browse(cursor, uid, uid)
        company= user.company_id
        
        #default_filters=['unicode', 'entity'] can be used to set global filter
        body_mako_tpl = Template(template ,input_encoding='utf-8')
        helper = WebKitHelper(cursor, uid, report_xml.id, context)
        html = body_mako_tpl.render(     helper=helper, 
                                         css=css,
                                         _=self.translate_call,
                                         **self.parser_instance.localcontext
                                         )
        head_mako_tpl = Template(header, input_encoding='utf-8')
        head = head_mako_tpl.render(
                                    company=company, 
                                    time=time, 
                                    helper=helper, 
                                    css=css,
                                    formatLang=self.formatLang,
                                    setLang=self.setLang,
                                    _=self.translate_call,
                                    _debug=False
                                )
        foot = False
        if footer :
            foot_mako_tpl = Template(footer ,input_encoding='utf-8')
            foot = foot_mako_tpl.render(
                                        company=company, 
                                        time=time, 
                                        helper=helper, 
                                        css=css, 
                                        formatLang=self.formatLang,
                                        setLang=self.setLang,
                                        _=self.translate_call,
                                        )
        if report_xml.webkit_debug :
            deb = head_mako_tpl.render(
                                        company=company, 
                                        time=time, 
                                        helper=helper, 
                                        css=css, 
                                        _debug=html,
                                        formatLang=self.formatLang,
                                        setLang=self.setLang,
                                        _=self.translate_call,
                                        )
            return (deb, 'html')
        bin = self.get_lib(cursor, uid, company.id)
        pdf = self.generate_pdf(bin, report_xml, head, foot, [html])
        return (pdf, 'pdf')


    def create(self, cursor, uid, ids, data, context=None):
        """We override the create function in order to handle generator
           Code taken from report openoffice. Thanks guys :) """
        pool = pooler.get_pool(cursor.dbname)
        ir_obj = pool.get('ir.actions.report.xml')
        report_xml_ids = ir_obj.search(cursor, uid,
                [('report_name', '=', self.name[7:])], context=context)
        if report_xml_ids:
            
            report_xml = ir_obj.browse(
                                        cursor, 
                                        uid, 
                                        report_xml_ids[0], 
                                        context=context
                                    )
            report_xml.report_rml = None
            report_xml.report_rml_content = None
            report_xml.report_sxw_content_data = None
            report_rml.report_sxw_content = None
            report_rml.report_sxw = None
        else:
            return super(WebKitParser, self).create(cursor, uid, ids, data, context)
        if report_xml.report_type != 'webkit' :
            return super(WebKitParser, self).create(cursor, uid, ids, data, context)
        result = self.create_source_pdf(cursor, uid, ids, data, report_xml, context)
        if not result:
            return (False,False)
        return result
