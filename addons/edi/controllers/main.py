import json
import textwrap

import simplejson
import werkzeug.wrappers

import web.common.http as openerpweb
import web.controllers.main

class EDI(openerpweb.Controller):
    # http://hostname:8069/edi/view?db=XXXX&token=XXXXXXXXXXX
    # http://hostname:8069/edi/import_url?url=URIEncodedURL
    _cp_path = "/edi"

    def template(self, req, mods='web,edi'):
        self.wc = openerpweb.controllers_path['/web/webclient']
        d = {}
        d["js"] = "\n".join('<script type="text/javascript" src="%s"></script>'%i for i in self.wc.manifest_list(req, mods, 'js'))
        d["css"] = "\n".join('<link rel="stylesheet" href="%s">'%i for i in self.wc.manifest_list(req, mods, 'css'))
        d["modules"] = simplejson.dumps(mods.split(','))
        return d

    @openerpweb.httprequest
    def view(self, req, db, token):
        d = self.template(req)
        d["init"] = 'new s.edi.EdiView(null,"%s","%s").appendTo($("body"));'%(db,token)
        r = web.controllers.main.html_template % d
        return r

    @openerpweb.httprequest
    def import_url(self, req, url):
        d = self.template(req)
        d["init"] = 'new s.edi.EdiImportUrl(null,"%s").appendTo($("body"));'%(url)
        r = web.controllers.main.html_template % d
        return r

    @openerpweb.httprequest
    def download(self, req, db, token):
        result = req.session.proxy('edi').get_edi_document(db, token)
        response = werkzeug.wrappers.Response( result, headers=[('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', len(result))]) 
        return response

    @openerpweb.httprequest
    def download_attachment(self, req, db, token):
        result = req.session.proxy('edi').get_edi_document(db, token)
        doc = json.loads(result)[0]
        attachment = doc['__attachments'] and doc['__attachments'][0]
        if attachment:
            result = attachment["content"].decode('base64')
            import email.Utils as utils

            # Encode as per RFC 2231
            filename_utf8 = attachment['file_name']
            filename_encoded = "%s=%s" % ('filename*',
                                          utils.encode_rfc2231(filename_utf8, 'utf-8'))
            response = werkzeug.wrappers.Response( result, headers=[('Content-Type', 'application/pdf'),
                                                                    ('Content-Disposition', 'inline; ' + filename_encoded),
                                                                    ('Content-Length', len(result))])
            return response

    @openerpweb.jsonrequest
    def get_edi_document(self, req, db, token):
        result = req.session.proxy('edi').get_edi_document(db, token)
        return json.loads(result)

    @openerpweb.jsonrequest
    def import_edi_url(self, req, url):
        result = req.session.proxy('edi').import_edi_url(req.session._db, req.session._uid, req.session._password, url)
        return result

#
