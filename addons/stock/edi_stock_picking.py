# -*- coding: utf-8 -*-
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

from osv import fields, osv, orm
from base.ir import ir_edi
from tools.translate import _

class stock_picking(osv.osv, ir_edi.edi):
    _inherit = 'stock.picking'

    def edi_export(self, cr, uid, records, edi_struct=None, context=None):
        """Exports a supplier or customer invoice"""
        edi_struct = {
                
                'origin': True,
                'type': True,
                'stock_journal_id': True,
                'move_type': True,
                'date': True,
                'date_done': True,
                'move_lines': {
                        'name': True,
                        'date': True,
                        'date_expected': True,
                        'product_id': True,
                        'product_qty': True,
                        'product_uom': True,
                        'location_id': True,
                        'location_dest_id': True,
                        'company_id': True,
                },
                'invoice_state': True,
                'address_id': True,
                'company_id': True,
        }
        partner_pool = self.pool.get('res.partner')
        partner_address_pool = self.pool.get('res.partner.address')
        company_address_dict = {
            'street': True,
            'street2': True,
            'zip': True,
            'city': True,
            'state_id': True,
            'country_id': True,
            'email': True,
            'phone': True,
                   
        }
        edi_doc_list = []
        for picking in records:
            # Get EDI doc based on struct. The result will also contain all metadata fields and attachments.
            edi_doc = super(stock_picking,self).edi_export(cr, uid, [picking], edi_struct, context)
            if not edi_doc:
                continue
            edi_doc = edi_doc[0]

            # Add company info and address
            res = partner_pool.address_get(cr, uid, [picking.company_id.partner_id.id], ['contact', 'picking'])
            contact_addr_id = res['contact']
            invoice_addr_id = res['picking']

            address = partner_address_pool.browse(cr, uid, invoice_addr_id, context=context)
            edi_company_address_dict = {}
            for key, value in company_address_dict.items():
                if not value:
                   continue
                address_rec = getattr(address, key)
                if not address_rec:
                    continue
                if key.endswith('_id'):
                    address_rec = self.edi_m2o(cr, uid, address_rec, context=context)
                edi_company_address_dict[key] = address_rec
                    
            edi_doc.update({
                    'company_address': edi_company_address_dict,
                    #'company_logo': inv_comp.logo,#TODO
                    #'paid': inv_comp.paid, #TODO
            })
            edi_doc_list.append(edi_doc)
        return edi_doc_list

    def edi_import(self, cr, uid, edi_document, context=None):
    
        partner_pool = self.pool.get('res.partner')
        partner_address_pool = self.pool.get('res.partner.address')
        model_data_pool = self.pool.get('ir.model.data')
        product_pool = self.pool.get('product.product')
        product_categ_pool = self.pool.get('product.category')
        company_pool = self.pool.get('res.company')
        country_pool = self.pool.get('res.country')
        state_pool = self.pool.get('res.country.state')
        account_journal_pool = self.pool.get('account.journal')
        invoice_line_pool = self.pool.get('account.invoice.line')
        account_pool = self.pool.get('account.account')
        tax_id = []
        account_id = []
        partner_id = None
        company_id = None
        if context is None:
            context = {}
        
        # import company as a new partner, if type==in then supplier=1, else customer=1
        # partner_id field is modified to point to the new partner
        # company_address data used to add address to new partner
        edi_company_address = edi_document['company_address']
        
        company_name = edi_document['company_id'][1]
        shipping_type = edi_document['type']
        state_id = edi_company_address.get('state_id', False)
        state_name = state_id and state_id[1]
        country_id = edi_company_address.get('country_id', False)
        country_name = country_id and country_id[1]

        country_id = country_name and self.edi_import_relation(cr, uid, 'res.country', country_name, context=context) or False
        state_id = state_name and self.edi_import_relation(cr, uid, 'res.country.state', state_name, 
                                values={'country_id': country_id, 'code': state_name}, context=context) or False
        address_value = {
            'street': edi_company_address.get('street', False),
            'street2': edi_company_address.get('street2', False),
            'zip': edi_company_address.get('zip', False),
            'city': edi_company_address.get('city', False),
            'state_id': state_id,
            'country_id': country_id,
            'email': edi_company_address.get('email', False),
            'phone': edi_company_address.get('phone', False),
               
        }
        

        partner_value = {'name': company_name}
        partner_id = partner_pool.search(cr, uid, [('name','=',company_name)])
        if len(partner_id):
            partner_id = partner_pool.browse(cr, uid, partner_id[0], context=context)
            address_id = partner_id.address[0].id
        else:
            partner_id = partner_pool.create(cr, uid, partner_value, context=context)
            address_value.update({'partner_id': partner_id})
            address_id = partner_address_pool.create(cr, uid, address_value, context=context)
        partner_address = partner_address_pool.browse(cr, uid, address_id, context=context)
        edi_document.update({'address_id': self.edi_m2o(cr, uid, partner_address, context=context)})
        
        
        

        # change type: out'<->'in for shipping
        shipping_type = shipping_type.startswith('in') and shipping_type.replace('in','out') or shipping_type.replace('out','in')
        edi_document['type'] = shipping_type
        company_id = edi_document['company_id']
        #print ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>",edi_document['move_lines']
        edi_document.update({'company_id': edi_document['move_lines'][0]['company_id']})
        edi_document['move_lines'][0].update({'company_id':company_id})
       
        del edi_document['company_address']
        
       
       
        return super(stock_picking,self).edi_import(cr, uid, edi_document, context=context)
      
stock_picking()

class stock_move(osv.osv, ir_edi.edi):
    _inherit='stock.move'

stock_move()

