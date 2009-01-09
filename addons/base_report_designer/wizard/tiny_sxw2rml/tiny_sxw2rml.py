#!/usr/bin/python
# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c):
#
#     2005 pyopenoffice.py Martin Simon (http://www.bezirksreiter.de)
#     2005 Fabien Pinckaers, TINY SPRL. (http://tiny.be)
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contact a Free Software
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

"""
Tiny SXW2RML - The Open ERP's report engine

Tiny SXW2RMLis part of the Tiny report project.
Tiny Report is a module that allows you to render high quality PDF document
from an OpenOffice template (.sxw) and any relationnal database.

The whole source code is distributed under the terms of the
GNU Public Licence.

(c) 2005 pyopenoffice.py Martin Simon (http://www.bezirksreiter.de)
(c) 2005-TODAY, Fabien Pinckaers - Tiny sprl
"""
__version__ = '0.9'


import re
import string
import os
import zipfile
import xml.dom.minidom
from reportlab.lib.units import toLength
import base64

class DomApiGeneral:
    """General DOM API utilities."""
    def __init__(self,content_string="",file=""):
        self.content_string = content_string
        self.re_digits = re.compile(r"(.*?\d)(pt|cm|mm|inch|in)")

    def _unitTuple(self,string):
        """Split values and units to a tuple."""
        temp = self.re_digits.findall(string)
        if not temp:
            return (string,"")
        else:
            return (temp[0])

    def stringPercentToFloat(self,string):
        temp = string.replace("""%""","")
        return float(temp)/100

    def findChildrenByName(self,parent,name,attr_dict={}):
        """Helper functions. Does not work recursively.
        Optional: also test for certain attribute/value pairs."""
        children = []
        for c in parent.childNodes:
            if c.nodeType == c.ELEMENT_NODE and c.nodeName == name:
                children.append(c)
        if attr_dict == {}:
            return children
        else:
            return self._selectForAttributes(nodelist=children,attr_dict=attr_dict)

    def _selectForAttributes(self,nodelist,attr_dict):
        "Helper function."""
        selected_nodes = []
        for n in nodelist:
            check = 1
            for a in attr_dict.keys():
                if n.getAttribute(a) != attr_dict[a]:
                    # at least one incorrect attribute value?
                    check = 0
            if check:
                selected_nodes.append(n)
        return selected_nodes

    def _stringToTuple(self,s):
        """Helper function."""
        try:
            temp = string.split(s,",")
            return int(temp[0]),int(temp[1])
        except:
            return None

    def _tupleToString(self,t):
        try:
            return self.openOfficeStringUtf8("%s,%s" % (t[0],t[1]))
        except:
            return None

    def _lengthToFloat(self,value):
        v = value
        if not self.re_digits.search(v):
            return v
        try:
            if v[-4:] == "inch":
                # OO files use "inch" instead of "in" in Reportlab units
                v = v[:-2]
        except:
            pass
        try:
            c = round(toLength(v))
            return c
        except:
            return v

    def openOfficeStringUtf8(self,string):
        if type(string) == unicode:
            return string.encode("utf-8")
        tempstring = unicode(string,"cp1252").encode("utf-8")
        return tempstring

class DomApi(DomApiGeneral):
    """This class provides a DOM-API for XML-Files from an SXW-Archive."""
    def __init__(self,xml_content,xml_styles):
        DomApiGeneral.__init__(self)
        self.content_dom = xml.dom.minidom.parseString(xml_content)
        self.styles_dom = xml.dom.minidom.parseString(xml_styles)
        body = self.content_dom.getElementsByTagName("office:body")
        self.body = body and body[0]

        # TODO:
        self.style_dict = {}
        self.style_properties_dict = {}

        # ******** always use the following order:
        self.buildStyleDict()
        self.buildStylePropertiesDict()
        if self.styles_dom.getElementsByTagName("style:page-master").__len__()<>0:
            self.page_master = self.styles_dom.getElementsByTagName("style:page-master")[0]
        if  self.styles_dom.getElementsByTagName("style:page-layout").__len__()<>0 :
			self.page_master = self.styles_dom.getElementsByTagName("style:page-layout")[0]        
        self.document = self.content_dom.getElementsByTagName("office:document-content")[0]

    def buildStylePropertiesDict(self):
        for s in self.style_dict.keys():
            self.style_properties_dict[s] = self.getStylePropertiesDict(s)

    def updateWithPercents(self,dict,updatedict):
        """Sometimes you find values like "115%" in the style hierarchy."""
        if not updatedict:
            # no style hierarchies for this style? =>
            return
        new_updatedict = copy.copy(updatedict)
        for u in new_updatedict.keys():
            try:
                if new_updatedict[u].find("""%""") != -1 and dict.has_key(u):
                    number = float(self.re_digits.search(dict[u]).group(1))
                    unit = self.re_digits.search(dict[u]).group(2)
                    new_number = self.stringPercentToFloat(new_updatedict[u]) * number
                    if unit == "pt":
                        new_number = int(new_number)
                        # no floats allowed for "pt"
                        # OOo just takes the int, does not round (try it out!)
                    new_updatedict[u] = "%s%s" % (new_number,unit)
                else:
                    dict[u] = new_updatedict[u]
            except:
                dict[u] = new_updatedict[u]
        dict.update(new_updatedict)

    def normalizeStyleProperties(self):
        """Transfer all style:style-properties attributes from the
        self.style_properties_hierarchical dict to the automatic-styles
        from content.xml. Use this function to preprocess content.xml for
        XSLT transformations etc.Do not try to implement this function
        with XSlT - believe me, it's a terrible task..."""
        styles_styles = self.styles_dom.getElementsByTagName("style:style")
        automatic_styles = self.content_dom.getElementsByTagName("office:automatic-styles")[0]
        for s in styles_styles:
            automatic_styles.appendChild(s.cloneNode(deep=1))
        content_styles = self.content_dom.getElementsByTagName("style:style")
        # these are the content_styles with styles_styles added!!!
        for s in content_styles:
            c = self.findChildrenByName(s,"style:properties")
            if c == []:
                # some derived automatic styles do not have "style:properties":
                temp = self.content_dom.createElement("style:properties")
                s.appendChild(temp)
                c = self.findChildrenByName(s,"style:properties")
            c = c[0]
            dict = self.style_properties_dict[(s.getAttribute("style:name")).encode("latin-1")] or {}
            for attribute in dict.keys():
                c.setAttribute(self.openOfficeStringUtf8(attribute),self.openOfficeStringUtf8(dict[attribute]))

    def transferStylesXml(self):
        """Transfer certain sub-trees from styles.xml to the normalized content.xml
        (see above). It is not necessary to do this - for example - with paragraph styles.
        the "normalized" style properties contain all information needed for
        further processing."""
        # TODO: What about table styles etc.?
        outline_styles = self.styles_dom.getElementsByTagName("text:outline-style")
        t = self.content_dom.createElement("transferredfromstylesxml")
        self.document.insertBefore(t,self.body)
        t_new = self.body.previousSibling
        try:
            page_master = self.page_master
            t_new.appendChild(page_master.cloneNode(deep=1))
            t_new.appendChild(outline_styles[0].cloneNode(deep=1))
        except:
            pass

    def normalizeLength(self):
        """Normalize all lengthes to floats (i.e: 1 inch = 72).
        Always use this after "normalizeContent" and "transferStyles"!"""
        # TODO: The complex attributes of table cell styles are not transferred yet.
        #all_styles = self.content_dom.getElementsByTagName("style:properties")
        #all_styles += self.content_dom.getElementsByTagName("draw:image")
        all_styles = self.content_dom.getElementsByTagName("*")
        for s in all_styles:
            for x in s._attrs.keys():
                v = s.getAttribute(x)
                s.setAttribute(x,"%s" % self._lengthToFloat(v))
                # convert float to string first!

    def normalizeTableColumns(self):
        """Handle this strange table:number-columns-repeated attribute."""
        columns = self.content_dom.getElementsByTagName("table:table-column")
        for c in columns:
            if c.hasAttribute("table:number-columns-repeated"):
                number = int(c.getAttribute("table:number-columns-repeated"))
                c.removeAttribute("table:number-columns-repeated")
                for i in range(number-1):
                    (c.parentNode).insertBefore(c.cloneNode(deep=1),c)

    def buildStyleDict(self):
        """Store all style:style-nodes from content.xml and styles.xml in self.style_dict.
        Caution: in this dict the nodes from two dom apis are merged!"""
        for st in (self.styles_dom,self.content_dom):
            for s in st.getElementsByTagName("style:style"):
                name = s.getAttribute("style:name").encode("latin-1")
                self.style_dict[name] = s
        return True

    def toxml(self):
        return self.content_dom.toxml(encoding="utf-8")

    def getStylePropertiesDict(self,style_name):
        res = {}

        if self.style_dict[style_name].hasAttribute("style:parent-style-name"):
            parent = self.style_dict[style_name].getAttribute("style:parent-style-name").encode("latin-1")
            res = self.getStylePropertiesDict(parent)

        childs = self.style_dict[style_name].childNodes
        for c in childs:
            if c.nodeType == c.ELEMENT_NODE and c.nodeName.find("properties")>0 :
                for attr in c._attrs.keys():
                    res[attr] = c.getAttribute(attr).encode("latin-1")
        return res

class PyOpenOffice(object):
    """This is the main class which provides all functionality."""
    def __init__(self, path='.', save_pict=False):
        self.path = path
        self.save_pict = save_pict
        self.images = {}

    def oo_read(self,fname):
        z = zipfile.ZipFile(fname,"r")
        content = z.read('content.xml')
        style = z.read('styles.xml')
        all = z.namelist()
        for a in all:
            if a[:9]=='Pictures/' and len(a)>10:
                pic_content = z.read(a)
                self.images[a[9:]] = pic_content
                if self.save_pict:
                    f=open(os.path.join(self.path, os.path.basename(a)),"wb")
                    f.write(pic_content)
                    f.close()
        z.close()
        return content,style

    def oo_replace(self,content):
        regex = [
            (r"<para[^>]*/>", ""),
            #(r"<text:ordered-list.*?>(.*?)</text:ordered-list>", "$1"),
            #(r"<text:unordered-list.*?>(.*?)</text:unordered-list>", "$1"),
            (r"<para(.*)>(.*?)<text:line-break[^>]*/>", "<para$1>$2</para><para$1>"),
        ]
        for key,val in regex:
            content = re.sub(key, val, content)
        return content

    def unpackNormalize(self,sourcefile):
        c,s = self.oo_read(sourcefile)
        c = self.oo_replace(c)
        dom = DomApi(c,s)
        dom.normalizeStyleProperties()
        dom.transferStylesXml()
        dom.normalizeLength()
        dom.normalizeTableColumns()
        new_c = dom.toxml()
        return new_c

def sxw2rml(sxw_file, xsl, output='.', save_pict=False):
    import libxslt
    import libxml2
    tool = PyOpenOffice(output, save_pict = save_pict)
    res = tool.unpackNormalize(sxw_file)
    styledoc = libxml2.parseDoc(xsl)
    style = libxslt.parseStylesheetDoc(styledoc)
    doc = libxml2.parseMemory(res,len(res))
    result = style.applyStylesheet(doc, None)

    root = result.xpathEval("/document/stylesheet")
    if root:
        root=root[0]
        images = libxml2.newNode("images")
        for img in tool.images:
            node = libxml2.newNode('image')
            node.setProp('name', img)
            node.setContent( base64.encodestring(tool.images[img]))
            images.addChild(node)
        root.addNextSibling(images)
    try:
        xml = style.saveResultToString(result)
        return xml
    except:
        return result

if __name__ == "__main__":
    import optparse
    parser = optparse.OptionParser(
        version="Tiny Report v%s" % __version__,
        usage = 'tiny_sxw2rml.py [options] file.sxw')
    parser.add_option("-v", "--verbose", default=False, dest="verbose", help="enable basic debugging")
    parser.add_option("-o", "--output", dest="output", default='.', help="directory of image output")
    (opt, args) = parser.parse_args()
    if len(args) != 1:
        parser.error("incorrect number of arguments")

    import sys
    import StringIO

    fname = sys.argv[1]
    f = StringIO.StringIO(file(fname).read())
    xsl_file = 'normalized_oo2rml.xsl'
    z = zipfile.ZipFile(fname,"r")
    mimetype = z.read('mimetype')
    if mimetype.split('/')[-1] == 'vnd.oasis.opendocument.text' :
		xsl_file = 'normalized_odt2rml.xsl'
    xsl = file(os.path.join(os.getcwd(), os.path.dirname(sys.argv[0]), xsl_file)).read()
    result = sxw2rml(f, xsl, output=opt.output, save_pict=False)

    print result
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

