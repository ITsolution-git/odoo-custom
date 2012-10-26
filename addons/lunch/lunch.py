
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

import pytz
import time
from osv import osv, fields
from datetime import datetime, timedelta
from lxml import etree


class lunch_order(osv.Model):
    """ lunch order """
    _name = 'lunch.order'
    _description = 'Lunch Order'

    def _price_get(self, cr, uid, ids, name, arg, context=None):
        """ get and sum the order lines' price"""
        result={}
        for order in self.browse(cr, uid, ids, context=context):
            value = 0.0
            for product in order.products: #TODO: use meaningful variable names `for order_line in ...´
                if product.state != 'cancelled':
                    value += product.product.price
                    result[order.id]=value
        return result


    def add_preference(self, cr, uid, ids, pref_id, context=None):
        """ create a new order line based on the preference selected (pref_id)"""
        pref_ref = self.pool.get("lunch.preference")
        orderline_ref = self.pool.get('lunch.order.line')
        prod_ref = self.pool.get('lunch.product')
        order = self.browse(cr,uid,ids,context=context)[0]
        pref = pref_ref.browse(cr,uid,pref_id,context=context)
        if pref.user_id.id == uid:
            new_order_line = {
                'date': order["date"],
                'user_id': uid,
                'product': pref["product"].id,
                'note': pref["note"],
                'order_id': order.id,
                'price': pref["price"],
                'supplier': prod_ref.browse(cr,uid,pref["product"].id,context=context)['supplier'].id
            }
            new_id = orderline_ref.create(cr,uid,new_order_line)
            order.products.append(new_id)
            #TODO: total is a computed field, so the write is useless, no?
            # ---> If I remove it, the total for order are not good (I try many times)
            # use store = {...}
            total = self._price_get(cr,uid,ids," "," ",context=context)
            self.write(cr,uid,ids,{},context) 
        return True

    def _alerts_get(self, cr, uid, ids, name, arg, context=None):
        """ get the alerts to display on the order form """
        orders = self.browse(cr,uid,ids,context=context)
        result={}
        alert_msg= self._default_alerts_get(cr,uid,arg,context=context)
        for order in orders:
            if order.state=='new':
                result[order.id]=alert_msg
        return result

    def check_day(self, alert):
        """ This method is used by can_display_alert to
            to check if the alert day corresponds
            to the current day 
        """
        today = datetime.now().isoweekday()
        if today == 1:
            if alert.monday == True:
                return True
        if today == 2:
            if alert.tuesday == True:
                return True
        if today == 3:
            if alert.wednesday == True:
                return True
        if today == 4:
            if alert.thursday == True:
                return True
        if today == 5:
            if alert.friday == True:
                return True
        if today == 6:
            if alert.saturday == True:
                return True
        if today == 7:
            if alert.sunday == True:
                return True
        return False

    def can_display_alert(self, alert):
        """ This method check if the alert can be displayed today """
        if alert.day=='specific':
            #the alert is only activated a specific day
            if alert.specific==fields.datetime.now().split(' ')[0]:
                return True
        elif alert.day=='week':
            #the alert is activated during some days of the week
            return self.check_day(alert)
        elif alert.day=='days':
            #the alert is activated everyday
            return True
        return False


    def _default_alerts_get(self,cr,uid,arg,context=None):
        """ get the alerts to display on the order form """
        alert_ref = self.pool.get('lunch.alert')
        alert_ids = alert_ref.search(cr,uid,[('active','=',True)],context=context) #TODO: active=True is automatically added by orm, so this param can be removed
        alert_msg=""
        for alert in alert_ref.browse(cr,uid,alert_ids,context=context):
            if self.can_display_alert(alert):
                if alert.active_from==alert.active_to:
                    #the alert is executing all the day
                    alert_msg+="! "
                    alert_msg+=alert.message
                    alert_msg+='\n'
                elif alert.active_from<alert.active_to:
                    #the alert is executing from ... to ...
                    now = datetime.utcnow()
                    user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
                    tz = pytz.timezone(user.tz) if user.tz else pytz.utc
                    tzoffset=tz.utcoffset(now)
                    mynow = now+tzoffset
                    hour_to = int(alert.active_to)
                    min_to = int((alert.active_to-hour_to)*60)
                    to_alert = datetime.strptime(str(hour_to)+":"+str(min_to),"%H:%M")
                    hour_from = int(alert.active_from)
                    min_from = int((alert.active_from-hour_from)*60)
                    from_alert = datetime.strptime(str(hour_from)+":"+str(min_from),"%H:%M")
                    if mynow.time()>=from_alert.time() and mynow.time()<=to_alert.time():
                        alert_msg+="! "
                        alert_msg+=alert.message
                        alert_msg+='\n'
        return alert_msg

    def onchange_price(self,cr,uid,ids,products,context=None):
        """ Onchange methode that refresh the total price of order"""
        res = {'value':{'total':0.0}}
        if products:
            tot = 0.0
            for prod in products:
                orderline = {}
                #TODO: that's weird. should truy to find another way to compute total on order lines when record is not saved...
                #   or at least put some comments
                if isinstance(prod[1],bool): 
                    orderline = prod[2]
                    tot += orderline['price']
                else:
                    orderline = self.pool.get('lunch.order.line').browse(cr,uid,prod[1],context=context)
                    tot += orderline.price
            res = {'value':{'total':tot}}
        return res

    def create(self, cr, uid, values, context=None):
        pref_ref = self.pool.get('lunch.preference')
        pref_ids = pref_ref.search(cr,uid,[],context=context)
        prod_ref = self.pool.get('lunch.product')
        new_id = super(lunch_order, self).create(cr, uid, values, context=context)
        #When we create a new order we also create new preference
        if len(values['products'])>0 and values['user_id']==uid:
            for prods in values['products']:
                already_exists = False #alreadyexist is used to check if a preferece already exists.
                for pref in pref_ref.browse(cr,uid,pref_ids,context=context):
                    if pref['product'].id == prods[2]['product']:
                        if pref['note'] == prods[2]['note']:
                            if pref['price'] == prods[2]['price']:
                                already_exists = True
                if already_exists == False:
                    new_pref = pref_ref.create(cr,uid,{'date':values['date'], 'color':0, 'order_id':new_id, 'user_id':values['user_id'], 'product': prods[2]['product'], 'product_name':prod_ref.browse(cr,uid,prods[2]['product'])['name'], 'note':prods[2]['note'], 'price':prods[2]['price']},context=context)
        return new_id
            
    def _default_preference_get(self,cr,uid,args,context=None):
        """ return a maximum of 15 last user preferences ordered by date"""
        return self.pool.get('lunch.preference').search(cr,uid,[('user_id','=',uid)],order='date desc',limit=15,context=context)

    def __getattr__(self, attr):
        """ this method catch unexisting method call and if starts with
            add_preference_'n' we execute the add_preference method with 
            'n' as parameter """
        if attr.startswith('add_preference_'):
            pref_id = int(attr[15:])
            def specific_function(cr, uid, ids, context=None):
                return self.add_preference(cr, uid, ids, pref_id, context=context)
            return specific_function
        return super(lunch_order,self).__getattr__(self,attr)

    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        #TODO: not reviewed
        res = super(lunch_order,self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            pref_ref = self.pool.get("lunch.preference")
            order_ref = self.pool.get("lunch.order")
            currency_obj = self.pool.get('res.currency')
            prod_ref = self.pool.get("lunch.product")

            pref_ids = pref_ref.search(cr,uid,[('user_id','=',uid)],context=context)
            order_ids = order_ref.search(cr,uid,[('user_id','=',uid)],context=context)
            if len(order_ids)>0:
                preferences = pref_ref.browse(cr,uid,pref_ids,context=context)
                this_order = order_ref.browse(cr,uid,order_ids[0],context=context)
                currency = currency_obj.browse(cr, uid, this_order['currency_id'], context=context)
                categories = {} #store the different categories of products in preference
                
                for pref in preferences:
                    categories[pref['product']['category_id']['name']]=[]
                for pref in preferences:
                    categories[pref['product']['category_id']['name']].append(pref)
                length = len(categories)
                text_xml = """<div class="oe_lunch_view">"""
                for key,value in categories.items():
                    text_xml+="""
                        <div class="oe_lunch_30pc">
                        <div class="oe_lunch_title">%s</div>
                    """ % (key,)
                    for val in value:
                        function_name = "add_preference_"+str(val.id)
                        text_xml+= '''
                            <div class="oe_lunch_vignette">
                                   <h3> %s </h3><span class="oe_tag">%.2f %s</span>
                                <br/>
                                <div class="oe_group_text_button oe_inline">
                                    <div class="oe_lunch_note">
                                        %s
                                    </div>
                                    <div class="oe_lunch_button">
                                        <button name="%s" class="oe_link oe_i" type="object" string="+"></button>
                                        <button name="%s" class="oe_link" type="object" string="Add"></button>
                                    </div>
                                </div>
                            </div>
                        ''' % (val['product_name'], val['price'] or 0.0, currency['name'], val['note'] or '', function_name, function_name)
                    text_xml+= ('''</div>''')
                text_xml+= ('''</div>''')
                # ADD into ARCH xml
                doc = etree.XML(res['arch'])
                node = doc.xpath("//div[@name='preferences']")
                to_add = etree.fromstring(text_xml)
                node[0].append(to_add)
                res['arch'] = etree.tostring(doc)
        return res

    _columns = {
        'user_id' : fields.many2one('res.users','User Name',required=True,readonly=True, states={'new':[('readonly', False)]}),
        'date': fields.date('Date', required=True,readonly=True, states={'new':[('readonly', False)]}),
        'products' : fields.one2many('lunch.order.line','order_id','Products',ondelete="cascade",readonly=True,states={'new':[('readonly', False)]}), #TODO: a good naming convention is to finish your field names with `_ids´ for *2many fields. BTW, the field name should reflect more it's nature: `order_line_ids´ for example
        'total' : fields.function(_price_get, string="Total",store=True),
        'state': fields.selection([('new', 'New'),('confirmed','Confirmed'), ('cancelled','Cancelled'), ('partially','Partially Confirmed')],'Status', readonly=True, select=True), #TODO: parcially? #TODO: the labels are confusing. confirmed=='received' or 'delivered'...
        'alerts': fields.function(_alerts_get, string="Alerts", type='text'),
        'preferences': fields.many2many("lunch.preference",'lunch_preference_rel','preferences','order_id','Preferences'),
        'company_id': fields.many2one('res.company', 'Company', required=True),
        'currency_id': fields.related('company_id','currency_id',string="Currency", readonly=True),
    }

    _defaults = {
        'user_id': lambda self, cr, uid, context: uid,
        'date': fields.date.context_today,
        'state': 'new',
        'alerts': _default_alerts_get,
        'preferences': _default_preference_get,
        'company_id': lambda self,cr,uid,context: self.pool.get('res.company')._company_default_get(cr, uid, 'lunch.order', context=context),
    }


class lunch_order_line(osv.Model):
    """ lunch order line : one lunch order can have many order lines"""
    _name = 'lunch.order.line'
    _description = 'lunch order line'

    def _price_get(self,cr,uid,ids,name,arg,context=None):
        """ get the price of the product store in the order line """
        result={}
        for order_line in self.browse(cr,uid,ids,context=context):
            result[order_line.id]=order_line.product.price
        return result

    def onchange_price(self,cr,uid,ids,product,context=None):
        """ Onchange methode to refresh the price """
        if product:
            price = self.pool.get('lunch.product').read(cr, uid, product, ['price'],context=context)['price']
            return {'value': {'price': price}}
        return {'value': {'price': 0.0}} 


    def confirm(self,cr,uid,ids,context=None):
        """ confirm one or more order line, update order status and create new cashmove """
        cashmove_ref = self.pool.get('lunch.cashmove')
        orders_ref = self.pool.get('lunch.order')
        for order_line in self.browse(cr,uid,ids,context=context):
            if order_line.state!='confirmed':
                new_id = cashmove_ref.create(cr,uid,{'user_id': order_line.user_id.id, 'amount':0 - order_line.price,'description':order_line.product.name, 'order_id':order_line.id, 'state':'order', 'date':order_line.date})
                self.write(cr,uid,[order_line.id],{'cashmove':[('0',new_id)], 'state':'confirmed'},context)
        for order_line in self.browse(cr,uid,ids,context=context):
            isconfirmed = True
            for product in order_line.order_id.products:
                if product.state == 'new':
                    isconfirmed = False
                if product.state == 'cancelled':
                    isconfirmed = False
                    orders_ref.write(cr,uid,[order_line.order_id.id],{'state':'partially'},context=context)
            if isconfirmed == True:
                orders_ref.write(cr,uid,[order_line.order_id.id],{'state':'confirmed'},context=context)
        return {}

    def cancel(self,cr,uid,ids,context=None):
        """ confirm one or more order.line, update order status and create new cashmove """
        cashmove_ref = self.pool.get('lunch.cashmove')
        orders_ref = self.pool.get('lunch.order')
        for order_line in self.browse(cr,uid,ids,context=context):
            self.write(cr,uid,[order_line.id],{'state':'cancelled'},context)
            for cash in order_line.cashmove:
                cashmove_ref.unlink(cr,uid,cash.id,context)
        for order_line in self.browse(cr,uid,ids,context=context):
            hasconfirmed = False
            hasnew = False
            for product in order_line.order_id.products:
                if product.state=='confirmed':
                    hasconfirmed= True
                if product.state=='new':
                    hasnew= True
            if hasnew == False:
                if hasconfirmed == False:
                    orders_ref.write(cr,uid,[order_line.order_id.id],{'state':'cancelled'},context)
                    return {}
            orders_ref.write(cr,uid,[order_line.order_id.id],{'state':'partially'},context)
        return {}

    _columns = {
        'date' : fields.related('order_id','date',type='date', string="Date", readonly=True,store=True),
        'supplier' : fields.related('product','supplier',type='many2one',relation='res.partner',string="Supplier",readonly=True,store=True),
        'user_id' : fields.related('order_id', 'user_id', type='many2one', relation='res.users', string='User', readonly=True, store=True),
        'product' : fields.many2one('lunch.product','Product',required=True), 
        'note' : fields.text('Note',size=256,required=False),
        'order_id' : fields.many2one('lunch.order','Order',ondelete='cascade'),
        'price' : fields.related('product', 'price', type="float", readonly=True,store=True),
        'state': fields.selection([('new', 'New'),('confirmed','Confirmed'), ('cancelled','Cancelled')], \
            'Status', readonly=True, select=True), #new confirmed and cancelled are the convention
        'cashmove': fields.one2many('lunch.cashmove','order_id','Cash Move',ondelete='cascade'),
        
    }
    _defaults = {
        'state': 'new',        
    }

class lunch_preference(osv.Model):
    """ lunch preference (based on user previous order lines) """
    _name = 'lunch.preference'
    _description= "user preferences"

    _columns = {
        'date' : fields.date('Date', required=True,readonly=True),
        'color': fields.integer('Color'),
        'user_id' : fields.many2one('res.users','User Name',required=True,readonly=True),
        'product' : fields.many2one('lunch.product','Product',required=True),
        'product_name' : fields.char('Product name',size=64),
        'note' : fields.text('Note',size=256,required=False),
        'price' : fields.float('Price',digits=(16,2)),
    }

    _defaults = {      
        'color': 1,
    }

class lunch_product(osv.Model):
    """ lunch product """
    _name = 'lunch.product'
    _description = 'lunch product'
    _columns = {
        'name' : fields.char('Product',required=True, size=64),
        'category_id': fields.many2one('lunch.product.category', 'Category'),
        'description': fields.text('Description', size=256, required=False),
        'price': fields.float('Price', digits=(16,2)),
        'active': fields.boolean('Active'), #If this product isn't offered anymore, the active boolean is set to false. This will allow to keep trace of previous orders and cashmoves.
        'supplier' : fields.many2one('res.partner','Supplier',required=True, domain=[('supplier_lunch','=',True)]), 
    }

class lunch_product_category(osv.Model):
    """ lunch product category """
    _name = 'lunch.product.category'
    _description = 'lunch product category'
    _columns = {
        'name' : fields.char('Category', required=True, size=64), #such as PIZZA, SANDWICH, PASTA, CHINESE, BURGER, ...
    }

class lunch_cashmove(osv.Model):
    """ lunch cashmove => order or payment """
    _name = 'lunch.cashmove'
    _description = 'lunch cashmove'
    _columns = {
        'user_id' : fields.many2one('res.users','User Name',required=True),
        'date' : fields.date('Date', required=True),
        'amount' : fields.float('Amount', required=True), #depending on the kind of cashmove, the amount will be positive or negative
        'description' : fields.text('Description',size=256), #the description can be an order or a payment
        'order_id' : fields.many2one('lunch.order.line','Order',required=False,ondelete='cascade'),
        'state' : fields.selection([('order','Order'),('payment','Payment')],'Is an order or a Payment'),
    }
    _defaults = {
        'user_id': lambda self, cr, uid, context: uid,
        'date': fields.date.context_today,
        'state': lambda self, cr, uid, context: 'payment',
    }

class lunch_alert(osv.Model):
    """ lunch alert """
    _name = 'lunch.alert'
    _description = 'lunch alert'
    _columns = {
        'message' : fields.text('Message',size=256, required=True),
        'active' : fields.boolean('Active'),
        'day' : fields.selection([('specific','Specific day'), ('week','Every Week'), ('days','Every Day')], 'Recurrency'),
        'specific' : fields.date('Day'),
        'monday' : fields.boolean('Monday'),
        'tuesday' : fields.boolean('Tuesday'),
        'wednesday' : fields.boolean('Wednesday'),
        'thursday' : fields.boolean('Thursday'),
        'friday' : fields.boolean('Friday'),
        'saturday' : fields.boolean('Saturday'),
        'sunday' :  fields.boolean('Sunday'),
        'active_from': fields.float('Between',required=True),
        'active_to': fields.float('And',required=True),
    }

class lunch_cancel(osv.Model):
    """ lunch cancel """
    _name = 'lunch.cancel'
    _description = 'cancel lunch order'

    def cancel(self,cr,uid,ids,context=None):
        #confirm one or more order.line, update order status and create new cashmove
        cashmove_ref = self.pool.get('lunch.cashmove')
        order_lines_ref = self.pool.get('lunch.order.line')
        orders_ref = self.pool.get('lunch.order')
        order_ids = context.get('active_ids', [])

        for order in order_lines_ref.browse(cr,uid,order_ids,context=context):
            order_lines_ref.write(cr,uid,[order.id],{'state':'cancelled'},context)
            for cash in order.cashmove:
                cashmove_ref.unlink(cr,uid,cash.id,context)
        for order in order_lines_ref.browse(cr,uid,order_ids,context=context):
            hasconfirmed = False
            hasnew = False
            for product in order.order_id.products:
                if product.state=='confirmed':
                    hasconfirmed= True
                if product.state=='new':
                    hasnew= True
            if hasnew == False:
                if hasconfirmed == False:
                    orders_ref.write(cr,uid,[order.order_id.id],{'state':'cancelled'},context)
                    return {}
            orders_ref.write(cr,uid,[order.order_id.id],{'state':'partially'},context)
        return {}

class lunch_validation(osv.Model):
    """ lunch validation """
    _name = 'lunch.validation'
    _description = 'lunch validation for order'

    def confirm(self,cr,uid,ids,context=None):
        #confirm one or more order.line, update order status and create new cashmove
        cashmove_ref = self.pool.get('lunch.cashmove')
        order_lines_ref = self.pool.get('lunch.order.line')
        orders_ref = self.pool.get('lunch.order')
        order_ids = context.get('active_ids', [])

        for order in order_lines_ref.browse(cr,uid,order_ids,context=context):
            if order.state!='confirmed':
                new_id = cashmove_ref.create(cr,uid,{'user_id': order.user_id.id, 'amount':0 - order.price,'description':order.product.name, 'order_id':order.id, 'state':'order', 'date':order.date})
                order_lines_ref.write(cr,uid,[order.id],{'cashmove':[('0',new_id)], 'state':'confirmed'},context)
        for order in order_lines_ref.browse(cr,uid,order_ids,context=context):
            isconfirmed = True
            for product in order.order_id.products:
                if product.state == 'new':
                    isconfirmed = False
                if product.state == 'cancelled':
                    isconfirmed = False
                    orders_ref.write(cr,uid,[order.order_id.id],{'state':'partially'},context)
            if isconfirmed == True:
                orders_ref.write(cr,uid,[order.order_id.id],{'state':'confirmed'},context)
        return {}
