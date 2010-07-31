# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

import time
import ir
from osv import osv,fields
import base64
import netsvc
from tools.translate import _

class tinythunderbird_partner(osv.osv):

    def _links_get(self, cr, uid, context={}):
        obj = self.pool.get('res.request.link')
        ids = obj.search(cr, uid, [])
        res = obj.read(cr, uid, ids, ['object', 'name'], context)

        return [(r['object'], r['name']) for r in res]

    _name = "tinythunderbird.partner"
    _description="Thunderbid mails"
    _rec_name="sender"
    _columns = {
                'sender':fields.char("Sender",size=128,required=True,select=True),
                'receiver':fields.text("Receiver"),
                "copy_to":fields.text("Copy To"),
                "date":fields.date("Date",select=True),
                "title":fields.char("Subject",size=128,select=True),
                "description":fields.text("Description"),
                "reference":fields.reference("Reference", selection=_links_get, size=128),
                "res_user_id":fields.many2one("res.users","User"),
                "attachments":fields.text("Attached Files",readonly=True),
                }
    _defaults = {
                 'res_user_id':lambda obj,cr,uid,context: uid,
                 'date': lambda *a: time.strftime('%Y-%m-%d')
                 }

    def thunderbird_mailcreate(self,cr,user,vals):
        dictcreate = dict(vals)
        import email
        header_name = email.Header.decode_header(dictcreate['name'])
        dictcreate['name'] = header_name and header_name[0] and header_name[0][0]
        add_obj=self.pool.get('res.partner.address')
        case_pool=self.pool.get(dictcreate.get('object','crm.case'))
        partner_ids=add_obj.search(cr,user,[('email','=',dictcreate['email_from'])])
        partner=add_obj.read(cr,user,partner_ids,['partner_id','name'])
        if partner and partner[0] and partner[0]['partner_id']:
            dictcreate.update({'partner_id':partner[0]['partner_id'][0],'partner_name':partner[0]['name']})
        create_id = case_pool.create(cr, user, dictcreate)
        cases=case_pool.browse(cr,user,[create_id])
        case_pool._history(cr, user, cases, _('Archive'), history=True, email=False)
        return create_id

    def thunderbird_createcontact(self,cr,user,vals):
        dictcreate = dict(vals)
        create_id = self.pool.get('res.partner.address').create(cr, user, dictcreate)
        return create_id

    def thunderbird_tempsearch_address(self, cr, user, vals):
        address_obj = self.pool.get('res.partner.address')
        partner = address_obj.search(cr, user,[('email','=',vals)])
        res = {}
        if partner:
            partner=partner[0]
            test = address_obj.read(cr,user, partner)
            res = {
                'partner_name': test['partner_id'] and test['partner_id'][1] or '',
                'contactname': test['name'] or '',
                'street': test['street'] or '',
                'street2': test['street2'] or '',
                'zip': test['zip'] or '',
                'city': test['city'] or '',
                'country': test['country_id'] and test['country_id'][0] or '',
                'state': test['state_id'] and test['state_id'][0] or '',
                'email': test['email'] or '',
                'phone': test['phone'] or '',
                'mobile': test['mobile'] or '',
                'fax': test['fax'] or '',
                'res_id': str(partner),
            }
        return res.items()

    def thunderbird_newcreatecontact(self,cr,user,vals):
        dictcreate = dict(vals)
        res_id = dictcreate.get('res_id',False)
        result={}
        if res_id:
            dictcreate.pop('res_id')
            add_obj = self.pool.get('res.partner.address')
            add_data = add_obj.read(cr, user, int(res_id), [])
            result={           'partner_id': add_data['partner_id'] and add_data['partner_id'][0] or False,
                               'country_id': dictcreate['country_id'] and int(dictcreate['country_id'][0]) or False,
                               'state_id': dictcreate['state_id'] and int(dictcreate['state_id'][0]) or False,
                               'name': dictcreate['name'],
                               'street': dictcreate['street'],
                               'street2': dictcreate['street2'],
                               'zip': dictcreate['zip'],
                               'city': dictcreate['city'],
#                               'country_id': dictcreate['country_id'][0],
#                               'state_id': dictcreate['state_id'],
                               'phone': dictcreate['phone'],
                               'fax': dictcreate['fax'],
                               'mobile': dictcreate['mobile'],
                               'email': dictcreate['email'],
                               }
        add_obj.write(cr, user,res_id,result )
        return True

    def thunderbird_createpartner(self,cr,user,vals):
        dictcreate = dict(vals)
        address_obj = self.pool.get('res.partner')
        search_id = address_obj.search(cr, user,[('name','=',dictcreate['name'])])
        if search_id:
            return 0
        create_id = address_obj.create(cr, user, dictcreate)
        return create_id

    def thunderbird_searchobject(self,cr,user,vals):
        dictcreate = dict(vals)
        search_id = self.pool.get('ir.model').search(cr, user,[('model','=',dictcreate['model'])])
        return (search_id and search_id[0]) or 0

    def thunderbird_searchcontact(self,cr,user,vals):
        address_obj = self.pool.get('res.partner.address')
        search_id1 = address_obj.search(cr,user,[('name','ilike',vals)])
        search_id2 = address_obj.search(cr,user,[('email','=',vals)])
        if search_id1:
            return address_obj.name_get(cr, user, search_id1)
        elif search_id2:
            return address_obj.name_get(cr, user, search_id2)
        return []

    def thunderbird_tempsearch(self,cr,user,vals):
        if vals[0]:
            value = vals[0][0]
        if vals[1]:
            obj = vals[1];
        name_get=[]
        er_val=[]
        for object in obj:
            dyn_object = self.pool.get(object)
            if object == 'res.partner.address':
                search_id1 = dyn_object.search(cr,user,[('name','ilike',value)])
                search_id2 = dyn_object.search(cr,user,[('email','=',value)])
                if search_id1:
                    name_get.append(object)
                    name_get.append(dyn_object.name_get(cr, user, search_id1))
                elif search_id2:
                    name_get.append(object)
                    name_get.append(dyn_object.name_get(cr, user, search_id2))
            else:
                try:
                    search_id1 = dyn_object.search(cr,user,[('name','ilike',value)])
                    if search_id1:
                        name_get.append(object)
                        name_get.append(dyn_object.name_get(cr, user, search_id1))
                except:
                    er_val.append(object)
                    continue
        if len(er_val) > 0:
            name_get.append('error')
            name_get.append(er_val)
        return name_get

    def thunderbird_attachment(self,cr,user,vals):
        dictcreate = dict(vals)
        datas = [dictcreate['datas']]
        name = [dictcreate['name']]
        f_name = [dictcreate['datas_fname']]
        if(dictcreate['datas'].__contains__(',')):
            name = dictcreate['name'].split(',')
            datas = dictcreate['datas'].split(',')
            f_name = dictcreate['datas_fname'].split(',')
        for i in range(0,datas.__len__()):
            dictcreate['name'] = name[i]
            dictcreate['datas'] = datas[i]
            dictcreate['datas_fname'] = f_name[i]
            create_id = self.pool.get('ir.attachment').create(cr,user,dictcreate)
        return 0

    def thunderbird_login(self,cr,user,vals):
        dictcreate = dict(vals)
        service = netsvc.LocalService('common')
        res = service.login(dictcreate['db'],dictcreate['login'],dictcreate['passwd'])
        return res or 0

    def read(self, cr, user, ids, fields=None, context={}, load='_classic_read'):
         ret_read = super(tinythunderbird_partner, self).read(cr, user, ids,fields,context,load)
         attach_obj = self.pool.get('ir.attachment')
         for read_data in ret_read:
             attachments = attach_obj.search(cr,user,[('res_model','=',self._name),('res_id','=',read_data['id'])])
             attechments_data = sattach_obj.read(cr,user,attachments,['name'])
             file_names = [a['name'] for a in attechments_data]
             text_atteched = '\n'.join(file_names)
             read_data['attachments'] = text_atteched
         return ret_read

    def unlink(self, cr, uid, ids, context={}):
        attach_obj = self.pool.get('ir.attachment')
        attachments = attach_obj.search(cr,uid,[('res_model','=',self._name),('res_id','in',ids)])
        attach_obj.unlink(cr,uid,attachments)
        return super(tinythunderbird_partner, self).unlink(cr, uid, ids,context)

    def thunderbird_objectsearch(self,cr,user,vals):
        obj_list= [('crm.lead','Lead'),('project.issue','Project Issue'), ('hr.applicant','HR Recruitment')]
        object=[]
        model_obj = self.pool.get('ir.model')
        for obj in obj_list:
            if model_obj.search(cr, user, [('model', '=', obj[0])]):
                object.append(obj)
        return object

    def thunderbird_objectcountry(self,cr,user,vals):
        country_list = []
        cr.execute("SELECT id, name from res_country")
        country_list = cr.fetchall()
        return country_list

    def thunderbird_objectstate(self,cr,user,vals):
        cr.execute("SELECT id, name from res_country_state")
        state_country_list = cr.fetchall()
        return state_country_list

    def thunderbird_list_search_object(self,cr,user,vals):
        model_obj = self.pool.get('ir.model')
        object=''
        for obj in vals[0][1].split(','):
            if model_obj.search(cr, user, [('model', '=', obj)]):
                object += obj + ","
            else:
                object += "null,"
        return object

tinythunderbird_partner()
