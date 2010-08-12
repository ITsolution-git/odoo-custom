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

    def _prop_child(xnode, ns, prop, value):
        """Append a property xml node to xnode, with <prop>value</prop>
           
           And a little smarter than that, it will consider namespace and
           also allow nested properties etc.
           
           :param ns the namespace of the <prop/> node
           :param prop the name of the property
           :param value the value. Can be:
                    string: text node
                    tuple ('elem', 'ns') for empty sub-node <ns:elem />
                    tuple ('elem', 'ns', sub-elems) for sub-node with elements
                    list, of above tuples
        """
        if ns == 'DAV:':
            ns_prefix = 'D:'
        else:
            ns_prefix="ns"+str(namespaces.index(ns))+":"

        pe=doc.createElement(ns_prefix+str(prop))
        if hasattr(value, '__class__') and value.__class__.__name__ == 'Element':
            pe.appendChild(value)
        else:
            if ns == 'DAV:' and prop=="resourcetype" and isinstance(value, int):
                # hack, to go..
                if value == 1:
                    ve=doc.createElement("D:collection")
                    pe.appendChild(ve)
            else:
                _prop_elem_child(pe, ns, value, ns_prefix)

            xnode.appendChild(pe)

    def _prop_elem_child(pnode, pns, v, pns_prefix):
        
        if isinstance(v, list):
            for vit in v:
                _prop_elem_child(pnode, pns, vit, pns_prefix)
        elif isinstance(v,tuple):
            need_ns = False
            if v[1] == pns:
                ns_prefix = pns_prefix
            elif v[1] == 'DAV:':
                ns_prefix = 'D:'
            elif v[1] in namespaces:
                ns_prefix="ns"+str(namespaces.index(v[1]))+":"
            else:
                # namespaces.append(v[1])
                # nsnum += 1
                ns_prefix="ns"+str(nsnum)+":"
                need_ns = True

            ve=doc.createElement(ns_prefix+v[0])
            if need_ns:
                ve.setAttribute("xmlns:ns"+str(nsnum), v[1])
            if len(v) > 2 and isinstance(v[2], list):
                # support nested elements like:
                # ( 'elem', 'ns:', [('sub-elem1', 'ns1'), ...]
                _prop_elem_child(ve, v[1], v[2], ns_prefix)
            pnode.appendChild(ve)
        else:
            ve=doc.createTextNode(tools.ustr(v))
            pnode.appendChild(ve)

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
            _prop_child(gp, ns, p, v)

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

