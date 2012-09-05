# -*- coding: utf-8 -*-
import logging
import simplejson
import os
import openerp

try:
    import openerp.addons.web.common.http as openerpweb
    from openerp.addons.web.controllers.main import manifest_list, module_boot, html_template
except ImportError:
    import web.common.http as openerpweb

class PointOfSaleController(openerpweb.Controller):
    _cp_path = '/pos'

    @openerpweb.httprequest
    def app(self, req, s_action=None, **kw):
        js = "\n        ".join('<script type="text/javascript" src="%s"></script>' % i for i in manifest_list(req, None, 'js'))
        css = "\n        ".join('<link rel="stylesheet" href="%s">' % i for i in manifest_list(req, None, 'css'))

        cookie = req.httprequest.cookies.get("instance0|session_id")
        session_id = cookie.replace("%22","")
        template = html_template.replace('<html','<html manifest="/pos/manifest?session_id=%s"'%session_id)
        r = template % {
            'js': js,
            'css': css,
            'modules': simplejson.dumps(module_boot(req)),
            'init': 'var wc = new s.web.WebClient();wc.appendTo($(document.body));'
        }
        return r

    @openerpweb.httprequest
    def manifest(self, req, **kwargs):
        """ This generates a HTML5 cache manifest files that preloads the categories and products thumbnails 
            and other ressources necessary for the point of sale to work offline """

        ml = ["CACHE MANIFEST"]

        # loading all the images in the static/src/img/* directories
        def load_css_img(srcdir,dstdir):
            for f in os.listdir(srcdir):
                path = os.path.join(srcdir,f)
                dstpath = os.path.join(dstdir,f)
                if os.path.isdir(path) :
                    load_css_img(path,dstpath)
                elif f.endswith(('.png','.PNG','.jpg','.JPG','.jpeg','.JPEG','.gif','.GIF')):
                    ml.append(dstpath)

        imgdir = openerp.modules.get_module_resource('point_of_sale','static/src/img');
        load_css_img(imgdir,'/point_of_sale/static/src/img')
        
        products = req.session.model('product.product')
        for p in products.search_read([('pos_categ_id','!=',False)], ['name']):
            product_id = p['id']
            url = "/web/binary/image?session_id=%s&model=product.product&field=image&id=%s" % (req.session_id, product_id)
            ml.append(url)
        
        categories = req.session.model('pos.category')
        for c in categories.search_read([],['name']):
            category_id = c['id']
            url = "/web/binary/image?session_id=%s&model=pos.category&field=image&id=%s" % (req.session_id, category_id)
            ml.append(url)

        ml += ["NETWORK:","*"]
        m = "\n".join(ml)

        return m

    @openerpweb.jsonrequest
    def dispatch(self, request, iface, **kwargs):
        method = 'iface_%s' % iface
        return getattr(self, method)(request, **kwargs)

    @openerpweb.jsonrequest
    def scan_item_success(self, request, ean):
        """
        A product has been scanned with success
        """
        print 'scan_item_success: ' + str(ean)
        return 

    @openerpweb.jsonrequest
    def scan_item_error_unrecognized(self, request, ean):
        """
        A product has been scanned without success
        """
        print 'scan_item_error_unrecognized: ' + str(ean)
        return 

    @openerpweb.jsonrequest
    def help_needed(self, request):
        """
        The user wants an help (ex: light is on)
        """
        print "help_needed"
        return 

    @openerpweb.jsonrequest
    def help_canceled(self, request):
        """
        The user stops the help request
        """
        print "help_canceled"
        return 

    @openerpweb.jsonrequest
    def weighting_start(self, request):
        print "weighting_start"
        return 

    @openerpweb.jsonrequest
    def weighting_read_kg(self, request):
        print "weighting_read_kg"
        return 0.0

    @openerpweb.jsonrequest
    def weighting_end(self, request):
        print "weighting_end"
        return 

    @openerpweb.jsonrequest
    def payment_request(self, request, price, method, info):
        """
        The PoS will activate the method payment 
        """
        print "payment_request: price:"+str(price)+" method:"+str(method)+" info:"+str(info)
        return 

    @openerpweb.jsonrequest
    def is_payment_accepted(self, request):
        print "is_payment_accepted"
        return 'waiting_for_payment' 

    @openerpweb.jsonrequest
    def payment_canceled(self, request):
        print "payment_canceled"
        return 

    @openerpweb.jsonrequest
    def transaction_start(self, request):
        print 'transaction_start'
        return 

    @openerpweb.jsonrequest
    def transaction_end(self, request):
        print 'transaction_end'
        return 

    @openerpweb.jsonrequest
    def cashier_mode_activated(self, request):
        print 'cashier_mode_activated'
        return 

    @openerpweb.jsonrequest
    def cashier_mode_deactivated(self, request):
        print 'cashier_mode_deactivated'
        return 

    @openerpweb.jsonrequest
    def open_cashbox(self, request):
        print 'open_cashbox'
        return

    @openerpweb.jsonrequest
    def print_receipt(self, request, receipt):
        print 'print_receipt' + str(receipt)
        return


