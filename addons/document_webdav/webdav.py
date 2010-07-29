# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#    Copyright (c) 1999 Christian Scholz (ruebe@aachen.heimat.de)
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

import xml.dom.minidom
domimpl = xml.dom.minidom.getDOMImplementation()
import urlparse
import urllib
from DAV import utils
from DAV.propfind import PROPFIND
import tools


super_mk_prop_response = PROPFIND.mk_prop_response
def mk_prop_response(self, uri, good_props, bad_props, doc):        
    """ make a new <prop> result element 

    We differ between the good props and the bad ones for
    each generating an extra <propstat>-Node (for each error
    one, that means).
    
    """      
    re=doc.createElement("D:response")
    # append namespaces to response
    nsnum=0
    namespaces = self.namespaces
    if 'DAV:' in namespaces:
        namespaces.remove('DAV:')
    for nsname in namespaces:
        re.setAttribute("xmlns:ns"+str(nsnum),nsname)
        nsnum=nsnum+1
    
    # write href information
    uparts=urlparse.urlparse(uri)
    fileloc=uparts[2]
    if isinstance(fileloc, unicode):
        fileloc = fileloc.encode('utf-8')
    href=doc.createElement("D:href")
    davpath = self._dataclass.parent.get_davpath()
    hurl = '%s://%s%s%s' % (uparts[0], uparts[1], davpath, urllib.quote(fileloc))
    huri=doc.createTextNode(hurl)
    href.appendChild(huri)
    re.appendChild(href)

    # write good properties
    ps=doc.createElement("D:propstat")
    if good_props:
        re.appendChild(ps)

    gp=doc.createElement("D:prop")
    for ns in good_props.keys():
        if ns == 'DAV:':
            ns_prefix = 'D:'
        else:
            ns_prefix="ns"+str(namespaces.index(ns))+":"
        for p,v in good_props[ns].items():
            if not v:
                continue
            pe=doc.createElement(ns_prefix+str(p))
            if hasattr(v, '__class__') and v.__class__.__name__ == 'Element':
                pe.appendChild(v)
            else:
                if ns == 'DAV:' and p=="resourcetype":
                    if v == 1:
                        ve=doc.createElement("D:collection")
                        pe.appendChild(ve)
                elif isinstance(v,tuple) and v[1] == ns:
                    ve=doc.createElement(ns_prefix+v[0])
                    pe.appendChild(ve)
                else:
                    ve=doc.createTextNode(tools.ustr(v))
                    pe.appendChild(ve)

            gp.appendChild(pe)
    
    ps.appendChild(gp)
    s=doc.createElement("D:status")
    t=doc.createTextNode("HTTP/1.1 200 OK")
    s.appendChild(t)
    ps.appendChild(s)
    re.appendChild(ps)

    # now write the errors!
    if len(bad_props.items()):

        # write a propstat for each error code
        for ecode in bad_props.keys():
            ps=doc.createElement("D:propstat")
            re.appendChild(ps)
            bp=doc.createElement("D:prop")
            ps.appendChild(bp)

            for ns in bad_props[ecode].keys():
                if ns == 'DAV:':
                    ns_prefix='D:'
                else:
                    ns_prefix="ns"+str(self.namespaces.index(ns))+":"
            
            for p in bad_props[ecode][ns]:
                pe=doc.createElement(ns_prefix+str(p))
                bp.appendChild(pe)
            
            s=doc.createElement("D:status")
            t=doc.createTextNode(utils.gen_estring(ecode))
            s.appendChild(t)
            ps.appendChild(s)
            re.appendChild(ps)

    # return the new response element
    return re
    

def mk_propname_response(self,uri,propnames,doc):
    """ make a new <prop> result element for a PROPNAME request 

    This will simply format the propnames list.
    propnames should have the format {NS1 : [prop1, prop2, ...], NS2: ...}

    """
    re=doc.createElement("D:response")

    # write href information
    uparts=urlparse.urlparse(uri)
    fileloc=uparts[2]
    if isinstance(fileloc, unicode):
        fileloc = fileloc.encode('utf-8')
    href=doc.createElement("D:href")
    davpath = self._dataclass.parent.get_davpath()
    hurl = '%s://%s%s%s' % (uparts[0], uparts[1], davpath, urllib.quote(fileloc))
    huri=doc.createTextNode(hurl)
    href.appendChild(huri)
    re.appendChild(href)

    ps=doc.createElement("D:propstat")
    nsnum=0

    for ns,plist in propnames.items():
        # write prop element
        pr=doc.createElement("D:prop")
        if ns == 'DAV':
            nsp = 'D'
        else:
            nsp="ns"+str(nsnum)
            ps.setAttribute("xmlns:"+nsp,ns)
            nsnum=nsnum+1

        # write propertynames
        for p in plist:
            pe=doc.createElement(nsp+":"+p)
            pr.appendChild(pe)

        ps.appendChild(pr)

    re.appendChild(ps)

    return re

PROPFIND.mk_prop_response = mk_prop_response
PROPFIND.mk_propname_response = mk_propname_response

