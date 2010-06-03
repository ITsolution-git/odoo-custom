# -*- encoding: utf-8 -*-
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
from report import report_sxw
import xml.dom.minidom
import os, time
import osv
import re
import tools
import pooler
import re
import sys


class rml_parse(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(rml_parse, self).__init__(cr, uid, name, context=None)
        self.localcontext.update({
            'comma_me': self.comma_me,
            'format_date': self._get_and_change_date_format_for_swiss,
            'strip_name' : self._strip_name,
            'explode_name' : self._explode_name,
        })

    def comma_me(self,amount):
        #print "#" + str(amount) + "#"
        if not amount:
            amount = 0.0
        if  type(amount) is float :
            amount = str('%.2f'%amount)
        else :
            amount = str(amount)
        if (amount == '0'):
             return ' '
        orig = amount
        new = re.sub("^(-?\d+)(\d{3})", "\g<1>'\g<2>", amount)
        if orig == new:
            return new
        else:
            return self.comma_me(new)
        
    def _ellipsis(self, string, maxlen=100, ellipsis = '...'):
        ellipsis = ellipsis or ''
        try:
            return string[:maxlen - len(ellipsis) ] + (ellipsis, '')[len(string) < maxlen]
        except Exception, e:
            return False
        
    def _strip_name(self, name, maxlen=50):
        return self._ellipsis(name, maxlen, '...')

    def _get_and_change_date_format_for_swiss (self,date_to_format):
        date_formatted=''
        if date_to_format:
            date_formatted = strptime (date_to_format,'%Y-%m-%d').strftime('%d.%m.%Y')
        return date_formatted

    def _explode_name(self,chaine,length):
        # We will test if the size is less then account
        full_string = ''
        if (len(str(chaine)) <= length):
            return chaine
        #
        else:
            chaine = unicode(chaine,'utf8').encode('iso-8859-1')
            rup = 0
            for carac in chaine:
                rup = rup + 1
                if rup == length:
                    full_string = full_string + '\n'
                    full_string = full_string + carac
                    rup = 0
                else:
                    full_string = full_string + carac

        return full_string

    def makeAscii(self,str):
        try:
            Stringer = str.encode("utf-8")
        except UnicodeDecodeError:
            try:
                Stringer = str.encode("utf-16")
            except UnicodeDecodeError:
                print "UTF_16 Error"
                Stringer = str
            else:
                return Stringer
        else:
            return Stringer
        return Stringer
    
    def explode_this(self,chaine,length):
        #chaine = self.repair_string(chaine)
        chaine = rstrip(chaine)
        ast = list(chaine)
        i = length
        while i <= len(ast):
            ast.insert(i,'\n')
            i = i + length
        chaine = str("".join(ast))
        return chaine
    
    def repair_string(self,chaine):
        ast = list(chaine)
        UnicodeAst = []
        _previouslyfound = False
        i = 0
        #print str(ast)
        while i < len(ast):
            elem = ast[i]
            try:
                Stringer = elem.encode("utf-8")
            except UnicodeDecodeError:
                to_reencode = elem + ast[i+1]
                print str(to_reencode)
                Good_char = to_reencode.decode('utf-8')
                UnicodeAst.append(Good_char)
                i += i +2
            else:
                UnicodeAst.append(elem)
                i += i + 1
        return "".join(UnicodeAst)

    def ReencodeAscii(self,str):
        print sys.stdin.encoding
        try:
            Stringer = str.decode("ascii")
        except UnicodeEncodeError:
            print "REENCODING ERROR"
            return str.encode("ascii")
        except UnicodeDecodeError:
            print "DECODING ERROR"
            return str.encode("ascii")
        else:
            print Stringer
            return Stringer

    def _add_header(self, node, header=1):
        if header==2:
            rml_head =  self.rml_header2
        else:
            rml_head =  self.rml_header
        rml_head =  rml_head.replace('<pageGraphics>','''<pageGraphics> <image x="10" y="26cm" height="770.0" width="1120.0" >[[company.logo]] </image> ''')
        return True



