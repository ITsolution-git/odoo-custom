# xml2json-direct
# Simple and straightforward XML-to-JSON converter in Python
# New BSD Licensed
#
# URL: http://code.google.com/p/xml2json-direct/
import simplejson
from xml.etree import ElementTree


class Xml2Json(object):
    @staticmethod
    def convert_to_json(s):
        return simplejson.dumps(
            Xml2Json.convert_to_structure(s), sort_keys=True, indent=4)

    @staticmethod
    def convert_to_structure(s):
        root = ElementTree.fromstring(s)
        return Xml2Json.convert_element(root)

    @staticmethod
    def convert_element(el, preserve_whitespaces=False):
        res = {}
        if el.tag[0] == "{":
            ns, name = el.tag.rsplit("}", 1)
            res["tag"] = name
            res["namespace"] = ns[1:]
        else:
            res["tag"] = el.tag
        res["attrs"] = {}
        for k, v in el.items():
            res["attrs"][k] = v
        kids = []
        if el.text and (preserve_whitespaces or el.text.strip() != ''):
            kids.append(el.text)
        for kid in el:
            kids.append(Xml2Json.convert_element(kid, preserve_whitespaces))
            if kid.tail and (preserve_whitespaces or kid.tail.strip() != ''):
                kids.append(kid.tail)
        res["children"] = kids
        return res
