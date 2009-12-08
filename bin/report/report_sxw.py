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

from lxml import etree
import StringIO
import cStringIO
import base64
import copy
import locale
import mx.DateTime
import os
import re
import time
from interface import report_rml
import preprocess
import ir
import netsvc
import osv
import pooler
import tools
import warnings
import zipfile
import common

DT_FORMAT = '%Y-%m-%d'
DHM_FORMAT = '%Y-%m-%d %H:%M:%S'
HM_FORMAT = '%H:%M:%S'

rml_parents = {
    'tr':1,
    'li':1,
    'story': 0,
    'section': 0
}

rml_tag="para"

sxw_parents = {
    'table-row': 1,
    'list-item': 1,
    'body': 0,
    'section': 0,
}

html_parents = {
    'tr' : 1,
    'body' : 0,
    'div' : 0
    }
sxw_tag = "p"

rml2sxw = {
    'para': 'p',
}

class _format(object):
    def set_value(self, cr, uid, name, object, field, lang_obj):
        self.object = object
        self._field = field
        self.name = name
        self.lang_obj = lang_obj

class _float_format(float, _format):
    def __init__(self,value):
        super(_float_format, self).__init__()
        self.val = value

    def __str__(self):
        digits = 2
        if hasattr(self,'_field') and hasattr(self._field, 'digits') and self._field.digits:
            digits = self._field.digits[1]
        if hasattr(self, 'lang_obj'):
            return self.lang_obj.format('%.' + str(digits) + 'f', self.name, True)
        return self.val

class _int_format(int, _format):
    def __init__(self,value):
        super(_int_format, self).__init__()
        self.val = value and str(value) or str(0)

    def __str__(self):
        if hasattr(self,'lang_obj'):
            return self.lang_obj.format('%.d', self.name, True)
        return self.val

class _date_format(str, _format):
    def __init__(self,value):
        super(_date_format, self).__init__()
        self.val = value and str(value) or ''

    def __str__(self):
        if self.val:
            if hasattr(self,'name') and (self.name):
                date = mx.DateTime.strptime(self.name,DT_FORMAT)
                return date.strftime(self.lang_obj.date_format)
        return self.val

class _dttime_format(str, _format):
    def __init__(self,value):
        super(_dttime_format, self).__init__()
        self.val = value and str(value) or ''

    def __str__(self):
        if self.val:
            if hasattr(self,'name') and self.name:
                datetime = mx.DateTime.strptime(self.name,DHM_FORMAT)
                return datetime.strftime(self.lang_obj.date_format+ " " + self.lang_obj.time_format)
        return self.val


_fields_process = {
    'float': _float_format,
    'date': _date_format,
    'integer': _int_format,
    'datetime' : _dttime_format
}

#
# Context: {'node': node.dom}
#
class browse_record_list(list):
    def __init__(self, lst, context):
        super(browse_record_list, self).__init__(lst)
        self.context = context

    def __getattr__(self, name):
        res = browse_record_list([getattr(x,name) for x in self], self.context)
        return res

    def __str__(self):
        return "browse_record_list("+str(len(self))+")"

class rml_parse(object):
    def __init__(self, cr, uid, name, parents=rml_parents, tag=rml_tag, context=None):
        if not context:
            context={}
        self.cr = cr
        self.uid = uid
        self.pool = pooler.get_pool(cr.dbname)
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        self.localcontext = {
            'user': user,
            'company': user.company_id,
            'repeatIn': self.repeatIn,
            'setLang': self.setLang,
            'setTag': self.setTag,
            'removeParentNode': self.removeParentNode,
            'format': self.format,
            'formatLang': self.formatLang,
            'logo' : user.company_id.logo,
            'lang' : user.company_id.partner_id.lang,
            'translate' : self._translate,
            'setHtmlImage' : self.set_html_image
        }
        self.localcontext.update(context)
        self.rml_header = user.company_id.rml_header
        self.rml_header2 = user.company_id.rml_header2
        self.logo = user.company_id.logo
        self.name = name
        self._node = None
        self.parents = parents
        self.tag = tag
        self._lang_cache = {}
        self.lang_dict = {}
        self.default_lang = {}
        self.lang_dict_called = False
        self._transl_regex = re.compile('(\[\[.+?\]\])')

    def setTag(self, oldtag, newtag, attrs=None):
        return newtag, attrs

    def format(self, text, oldtag=None):
        return text.strip()

    def removeParentNode(self, tag=None):
        raise Exception('Skip')

    def set_html_image(self,id,model=None,field=None,context=None):
        if not id :
            return ''
        if not model:
            model = 'ir.attachment'
        try :
            id = int(id)
            res = self.pool.get(model).read(self.cr,self.uid,id)
            if field :
                return res[field]
            elif model =='ir.attachment' :
                return res['datas']
            else :
                return ''
        except Exception,e:
            return ''

    def setLang(self, lang):
        if not lang or self.default_lang.has_key(lang):
            if not lang:
                key = 'en_US'
        self.localcontext['lang'] = lang
        self.lang_dict_called = False
        for obj in self.objects:
            obj._context['lang'] = lang
            for table in obj._cache:
                for id in obj._cache[table]:
                    self._lang_cache.setdefault(obj._context['lang'], {}).setdefault(table,
                            {}).update(obj._cache[table][id])
                    if lang in self._lang_cache \
                            and table in self._lang_cache[lang] \
                            and id in self._lang_cache[lang][table]:
                        obj._cache[table][id] = self._lang_cache[lang][table][id]
                    else:
                        obj._cache[table][id] = {'id': id}

    def _get_lang_dict(self):
        pool_lang = self.pool.get('res.lang')
        lang = self.localcontext.get('lang', 'en_US') or 'en_US'
        lang_ids = pool_lang.search(self.cr,self.uid,[('code','=',lang)])[0]
        lang_obj = pool_lang.browse(self.cr,self.uid,lang_ids)
        self.lang_dict.update({'lang_obj':lang_obj,'date_format':lang_obj.date_format,'time_format':lang_obj.time_format})
        self.default_lang[lang] = self.lang_dict.copy()
        return True

    def formatLang(self, value, digits=2, date=False,date_time=False, grouping=True, monetary=False):
        if isinstance(value, (str, unicode)) and not value:
            return ''
        if not self.lang_dict_called:
            self._get_lang_dict()
            self.lang_dict_called = True

        if date or date_time:
            if not str(value):
                return ''
            date_format = self.lang_dict['date_format']
            parse_format = DT_FORMAT
            if date_time:
                date_format = date_format + " " + self.lang_dict['time_format']
                parse_format = DHM_FORMAT

            # filtering time.strftime('%Y-%m-%d')
            if type(value) == type(''):
                parse_format = DHM_FORMAT
                if (not date_time):
                    return str(value)

            if not isinstance(value, time.struct_time):
                try:
                    date = mx.DateTime.strptime(str(value),parse_format)
                except:# sometimes it takes converted values into value, so we dont need conversion.
                    return str(value)
            else:
                date = mx.DateTime.DateTime(*(value.timetuple()[:6]))
            return date.strftime(date_format)
        return self.lang_dict['lang_obj'].format('%.' + str(digits) + 'f', value, grouping=grouping, monetary=monetary)

    def repeatIn(self, lst, name,nodes_parent=False):
        ret_lst = []
        for id in lst:
            ret_lst.append({name:id})
        return ret_lst

    def _translate(self,text):
        lang = self.localcontext['lang']
        if lang and text and not text.isspace():
            transl_obj = self.pool.get('ir.translation')
            piece_list = self._transl_regex.split(text)
            for pn in range(len(piece_list)):
                if not self._transl_regex.match(piece_list[pn]):
                    source_string = piece_list[pn].replace('\n', ' ').strip()
                    if len(source_string):
                        translated_string = transl_obj._get_source(self.cr, self.uid, self.name, 'rml', lang, source_string)
                        if translated_string:
                            piece_list[pn] = piece_list[pn].replace(source_string, translated_string)
            text = ''.join(piece_list)
        return text

    def _add_header(self, rml_dom, header=1):
        if header==2:
            rml_head =  self.rml_header2
        else:
            rml_head =  self.rml_header
        if self.logo and (rml_head.find('company.logo')<0 or rml_head.find('<image')<0) and rml_head.find('<!--image')<0:
            rml_head =  rml_head.replace('<pageGraphics>','''<pageGraphics> <image x="10" y="26cm" height="70" width="90" >[[company.logo]] </image> ''')
        if not self.logo and rml_head.find('company.logo')>=0:
            rml_head = rml_head.replace('<image','<!--image')
            rml_head = rml_head.replace('</image>','</image-->')
        head_dom = etree.XML(rml_head)
        for tag in head_dom:
            found = rml_dom.find('.//'+tag.tag)
            if found is not None and len(found):
                if tag.get('position'):
                    found.append(tag)
                else :
                    found.getparent().replace(found,tag)
        return True

    def set_context(self, objects, data, ids, report_type = None):
        self.localcontext['data'] = data
        self.localcontext['objects'] = objects
        self.datas = data
        self.ids = ids
        self.objects = objects
        if report_type:
            if report_type=='odt' :
                self.localcontext.update({'name_space' :common.odt_namespace})
            else:
                self.localcontext.update({'name_space' :common.sxw_namespace})

class report_sxw(report_rml, preprocess.report):
    def __init__(self, name, table, rml=False, parser=rml_parse, header=True, store=False):
        report_rml.__init__(self, name, table, rml, '')
        self.name = name
        self.parser = parser
        self.header = header
        self.store = store

    def getObjects(self, cr, uid, ids, context):
        table_obj = pooler.get_pool(cr.dbname).get(self.table)
        return table_obj.browse(cr, uid, ids, list_class=browse_record_list, context=context, fields_process=_fields_process)

    def create(self, cr, uid, ids, data, context=None):
        pool = pooler.get_pool(cr.dbname)
        ir_obj = pool.get('ir.actions.report.xml')
        report_xml_ids = ir_obj.search(cr, uid,
                [('report_name', '=', self.name[7:])], context=context)
        if report_xml_ids:
            report_xml = ir_obj.browse(cr, uid, report_xml_ids[0], context=context)
        else:
            title = ''
            rml = tools.file_open(self.tmpl, subdir=None).read()
            report_type= data.get('report_type', 'pdf')
            class a(object):
                def __init__(self, *args, **argv):
                    for key,arg in argv.items():
                        setattr(self, key, arg)
            report_xml = a(title=title, report_type=report_type, report_rml_content=rml, name=title, attachment=False, header=self.header)
        report_type = report_xml.report_type
        if report_type in ['sxw','odt']:
            fnct = self.create_source_odt
        elif report_type in ['pdf','raw','html']:
            fnct = self.create_source_pdf
        elif report_type=='html2html':
            fnct = self.create_source_html2html
        else:
            raise 'Unknown Report Type'
        return fnct(cr, uid, ids, data, report_xml, context)

    def create_source_odt(self, cr, uid, ids, data, report_xml, context=None):
        return self.create_single_odt(cr, uid, ids, data, report_xml, context or {})

    def create_source_html2html(self, cr, uid, ids, data, report_xml, context=None):
        return self.create_single_html2html(cr, uid, ids, data, report_xml, context or {})

    def create_source_pdf(self, cr, uid, ids, data, report_xml, context=None):
        if not context:
            context={}
        pool = pooler.get_pool(cr.dbname)
        attach = report_xml.attachment
        if attach:
            objs = self.getObjects(cr, uid, ids, context)
            results = []
            for obj in objs:
                aname = eval(attach, {'object':obj, 'time':time})
                result = False
                if report_xml.attachment_use and aname and context.get('attachment_use', True):
                    aids = pool.get('ir.attachment').search(cr, uid, [('datas_fname','=',aname+'.pdf'),('res_model','=',self.table),('res_id','=',obj.id)])
                    if aids:
                        brow_rec = pool.get('ir.attachment').browse(cr, uid, aids[0])
                        if not brow_rec.datas:
                            continue
                        d = base64.decodestring(brow_rec.datas)
                        results.append((d,'pdf'))
                        continue
                result = self.create_single_pdf(cr, uid, [obj.id], data, report_xml, context)
                try:
                    if aname:
                        name = aname+'.'+result[1]
                        pool.get('ir.attachment').create(cr, uid, {
                            'name': aname,
                            'datas': base64.encodestring(result[0]),
                            'datas_fname': name,
                            'res_model': self.table,
                            'res_id': obj.id,
                            }, context=context
                        )
                        cr.commit()
                except Exception,e:
                     import traceback, sys
                     tb_s = reduce(lambda x, y: x+y, traceback.format_exception(sys.exc_type, sys.exc_value, sys.exc_traceback))
                     netsvc.Logger().notifyChannel('report', netsvc.LOG_ERROR,str(e))
                results.append(result)
            if results:
                if results[0][1]=='pdf':
                    from pyPdf import PdfFileWriter, PdfFileReader
                    output = PdfFileWriter()
                    for r in results:
                        reader = PdfFileReader(cStringIO.StringIO(r[0]))
                        for page in range(reader.getNumPages()):
                            output.addPage(reader.getPage(page))
                    s = cStringIO.StringIO()
                    output.write(s)
                    return s.getvalue(), results[0][1]
        return self.create_single_pdf(cr, uid, ids, data, report_xml, context)

    def create_single_pdf(self, cr, uid, ids, data, report_xml, context=None):
        if not context:
            context={}
        logo = None
        context = context.copy()
        title = report_xml.name
        rml = report_xml.report_rml_content
        rml_parser = self.parser(cr, uid, self.name2, context=context)
        objs = self.getObjects(cr, uid, ids, context)
        rml_parser.set_context(objs, data, ids, report_xml.report_type)
        processed_rml = self.preprocess_rml(etree.XML(rml),report_xml.report_type)
        if report_xml.header:
            rml_parser._add_header(processed_rml)
        if rml_parser.logo:
            logo = base64.decodestring(rml_parser.logo)
        create_doc = self.generators[report_xml.report_type]
        pdf = create_doc(etree.tostring(processed_rml),rml_parser.localcontext,logo,title.encode('utf8'))
        return (pdf, report_xml.report_type)

    def create_single_odt(self, cr, uid, ids, data, report_xml, context=None):
        if not context:
            context={}
        context = context.copy()
        report_type = report_xml.report_type
        context['parents'] = sxw_parents
        sxw_io = StringIO.StringIO(report_xml.report_sxw_content)
        sxw_z = zipfile.ZipFile(sxw_io, mode='r')
        rml = sxw_z.read('content.xml')
        meta = sxw_z.read('meta.xml')
        sxw_z.close()

        rml_parser = self.parser(cr, uid, self.name2, context=context)
        rml_parser.parents = sxw_parents
        rml_parser.tag = sxw_tag
        objs = self.getObjects(cr, uid, ids, context)
        rml_parser.set_context(objs, data, ids,report_xml.report_type)

        rml_dom_meta = node = etree.XML(meta)
        elements = node.findall(rml_parser.localcontext['name_space']["meta"]+"user-defined")
        for pe in elements:
            if pe.get(rml_parser.localcontext['name_space']["meta"]+"name"):
                if pe.get(rml_parser.localcontext['name_space']["meta"]+"name") == "Info 3":
                    pe[0].text=data['id']
                if pe.get(rml_parser.localcontext['name_space']["meta"]+"name") == "Info 4":
                    pe[0].text=data['model']
        meta = etree.tostring(rml_dom_meta, encoding='utf-8',
                              xml_declaration=True)

        rml_dom =  etree.XML(rml)
        body = rml_dom[-1]
        elements = []
        key1 = rml_parser.localcontext['name_space']["text"]+"p"
        key2 = rml_parser.localcontext['name_space']["text"]+"drop-down"
        for n in rml_dom.iterdescendants():
            if n.tag == key1:
                elements.append(n)
        if report_type == 'odt':
            for pe in elements:
                e = pe.findall(key2)
                for de in e:
                    pp=de.getparent()
                    if de.text or de.tail:
                        pe.text = de.text or de.tail
                    for cnd in de:
                        if cnd.text or cnd.tail:
                            if pe.text:
                                pe.text +=  cnd.text or cnd.tail
                            else:
                                pe.text =  cnd.text or cnd.tail
                            pp.remove(de)
        else:
            for pe in elements:
                e = pe.findall(key2)
                for de in e:
                    pp = de.getparent()
                    if de.text or de.tail:
                        pe.text = de.text or de.tail
                    for cnd in de:
                        text = cnd.get("{http://openoffice.org/2000/text}value",False)
                        if text:
                            if pe.text and text.startswith('[['):
                                pe.text +=  text
                            elif text.startswith('[['):
                                pe.text =  text
                            if de.getparent():
                                pp.remove(de)

        rml_dom = self.preprocess_rml(rml_dom,report_type)
        create_doc = self.generators[report_type]
        odt = etree.tostring(create_doc(rml_dom, rml_parser.localcontext),
                             encoding='utf-8', xml_declaration=True)
        sxw_z = zipfile.ZipFile(sxw_io, mode='a')
        sxw_z.writestr('content.xml', odt)
        sxw_z.writestr('meta.xml', meta)

        if report_xml.header:
            #Add corporate header/footer
            rml = tools.file_open(os.path.join('base', 'report', 'corporate_%s_header.xml' % report_type)).read()
            rml_parser = self.parser(cr, uid, self.name2, context=context)
            rml_parser.parents = sxw_parents
            rml_parser.tag = sxw_tag
            objs = self.getObjects(cr, uid, ids, context)
            rml_parser.set_context(objs, data, ids, report_xml.report_type)
            rml_dom = self.preprocess_rml(etree.XML(rml),report_type)
            create_doc = self.generators[report_type]
            odt = create_doc(rml_dom,rml_parser.localcontext)
            if report_xml.header:
                rml_parser._add_header(odt)
            odt = etree.tostring(odt, encoding='utf-8',
                                 xml_declaration=True)
            sxw_z.writestr('styles.xml', odt)
        sxw_z.close()
        final_op = sxw_io.getvalue()
        sxw_io.close()
        return (final_op, report_type)

    def create_single_html2html(self, cr, uid, ids, data, report_xml, context=None):
        if not context:
            context = {}
        context = context.copy()
        report_type = 'html'
        context['parents'] = html_parents

        html = report_xml.report_rml_content
        html_parser = self.parser(cr, uid, self.name2, context=context)
        html_parser.parents = html_parents
        html_parser.tag = sxw_tag
        objs = self.getObjects(cr, uid, ids, context)
        html_parser.set_context(objs, data, ids, report_type)

        html_dom =  etree.HTML(html)
        html_dom = self.preprocess_rml(html_dom,'html2html')

        create_doc = self.generators['html2html']
        html = etree.tostring(create_doc(html_dom, html_parser.localcontext))

        return (html.replace('&amp;','&').replace('&lt;', '<').replace('&gt;', '>').replace('</br>',''), report_type)


