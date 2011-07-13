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

class account_invoice(osv.osv, ir_edi.edi):
    _inherit = 'account.invoice'

    def edi_export(self, cr, uid, records, edi_struct=None, context=None):
        """Exports a supplier or customer invoice"""
        edi_struct = {
                'name': True,
                'origin': True,
                'company_id': True, # -> to be changed into partner
                'type': True, # -> reversed at import
                'internal_number': True, # -> reference at import
                'comment': True,
                'reference': True,
                'amount_untaxed': True,
                'amount_tax': True,
                'amount_total': True,
                'date_invoice': True,
                'date_due': True,
                'partner_id': True,
                'address_invoice_id': True, #only one address needed
                'payment_term': True,
                'currency_id': True,
                'invoice_line': {
                        'name': True,
                        'origin': True,
                        'uos_id': True,
                        'product_id': True,
                        'price_unit': True,
                        'price_subtotal': True,
                        'quantity': True,
                        'discount': True,
                        'note': True,
                },
                'tax_line': {
                        'name': True,
                        'base': True,
                        'amount': True,
                        'manual': True,
                        'sequence': True,
                        'base_amount': True,
                        'tax_amount': True,
                },
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
        for invoice in records:
            # Get EDI doc based on struct. The result will also contain all metadata fields and attachments.
            edi_doc = super(account_invoice,self).edi_export(cr, uid, [invoice], edi_struct, context)
            if not edi_doc:
                continue
            edi_doc = edi_doc[0]

            # Add company info and address
            res = partner_pool.address_get(cr, uid, [invoice.company_id.partner_id.id], ['contact', 'invoice'])
            contact_addr_id = res['contact']
            invoice_addr_id = res['invoice']

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
    
        """ During import, invoices will import the company that is provided in the invoice as
            a new partner (e.g. supplier company for a customer invoice will be come a supplier
            record for the new invoice.
            Summary of tasks that need to be done:
                - import company as a new partner, if type==in then supplier=1, else customer=1
                - partner_id field is modified to point to the new partner
                - company_address data used to add address to new partner
                - change type: out_invoice'<->'in_invoice','out_refund'<->'in_refund'
                - reference: should contain the value of the 'internal_number'
                - reference_type: 'none'
                - internal number: reset to False, auto-generated
                - journal_id: should be selected based on type: simply put the 'type' 
                    in the context when calling create(), will be selected correctly
                - payment_term: if set, create a default one based on name...
                - for invoice lines, the account_id value should be taken from the
                    product's default, i.e. from the default category, as it will not
                    be provided.
                - for tax lines, we disconnect from the invoice.line, so all tax lines
                    will be of type 'manual', and default accounts should be picked based
                    on the tax config of the DB where it is imported.    
        """

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
        edi_partner_id = edi_document['partner_id']
        company_name = edi_document['company_id'][1]
        invoice_type = edi_document['type']
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
        if invoice_type in ('out_invoice', 'in_refund'):
            partner_value.update({'customer': True, 'supplier': False})
        if invoice_type in ('in_invoice', 'out_refund'):
            partner_value.update({'customer': False, 'supplier': True})

        partner_id = partner_pool.create(cr, uid, partner_value, context=context)
        address_value.update({'partner_id': partner_id})
        address_id = partner_address_pool.create(cr, uid, address_value, context=context)

        partner = partner_pool.browse(cr, uid, partner_id, context=context)
        edi_document['partner_id'] = self.edi_m2o(cr, uid, partner, context=context)

        # change type: out_invoice'<->'in_invoice','out_refund'<->'in_refund'
        invoice_type = invoice_type.startswith('in_') and invoice_type.replace('in_','out_') or invoice_type.replace('out_','in_')
        edi_document['type'] = invoice_type

        # Set Account
        if invoice_type in ('out_invoice', 'out_refund'):
            invoice_account = partner.property_account_receivable
        else:
            invoice_account = partner.property_account_payable
        edi_document['account_id'] = invoice_account and self.edi_m2o(cr, uid, invoice_account, context=context) or False

        # reference: should contain the value of the 'internal_number'
        edi_document['reference'] = edi_document.get('internal_number', False)
        # reference_type: 'none'
        edi_document['reference_type'] = 'none'

        # internal number: reset to False, auto-generated
        edi_document['internal_number'] = False

        # company should set by default so delete company data from edi Document
        del edi_document['company_address']
        del edi_document['company_id'] 

        # journal_id: should be selected based on type: simply put the 'type' in the context when calling create(), will be selected correctly
        journal_context = context.copy()
        journal_context.update({'type':invoice_type})
        journal_id = self._get_journal(cr, uid, context=journal_context)
        journal = False
        if journal_id:
            journal = account_journal_pool.browse(cr, uid, journal_id, context=context)
        edi_document['journal_id'] = journal and  self.edi_m2o(cr, uid, journal, context=context) or False

        # for invoice lines, the account_id value should be taken from the product's default, i.e. from the default category, as it will not be provided.
        for edi_invoice_line in edi_document.get('invoice_line', []):
            product_id = edi_invoice_line.get('product_id', False)
            account = False
            if product_id:
                product_name = product_id and product_id[1]
                product_id = self.edi_import_relation(cr, uid, 'product.product', product_name, context=context)
                product = product_pool.browse(cr, uid, product_id, context=context)

                if invoice_type in ('out_invoice','out_refund'):
                    account = product.product_tmpl_id.property_account_income
                    if not account:
                        account = product.categ_id.property_account_income_categ
                else:
                    account = product.product_tmpl_id.property_account_expense
                    if not account:
                        account = product.categ_id.property_account_expense_categ
            # TODO: add effect of fiscal position 
            # account = fpos_obj.map_account(cr, uid, fiscal_position_id, account.id)
            edi_invoice_line['account_id'] = account and self.edi_m2o(cr, uid, account, context=context) or False

        # for tax lines, we disconnect from the invoice.line, so all tax lines will be of type 'manual', and default accounts should be picked based
        # on the tax config of the DB where it is imported.
        for edi_tax_line in edi_document.get('tax_line', []):
            account_ids = account_pool.search(cr, uid, [('type','<>','view'),('type','<>','income'), ('type', '<>', 'closed')])
            if account_ids:
                tax_account = account_pool.browse(cr, uid, account_ids[0])
                edi_tax_line['account_id'] = self.edi_m2o(cr, uid, tax_account, context=context) #TODO should select account of output VAT for Customer Invoice and Input VAT for Supplier Invoice
            edi_tax_line['manual'] = True

        # TODO :=> payment_term: if set, create a default one based on name... 
       
        return super(account_invoice,self).edi_import(cr, uid, edi_document, context=context)
      
account_invoice()

class account_invoice_line(osv.osv, ir_edi.edi):
    _inherit='account.invoice.line'

account_invoice_line()
class account_invoice_tax(osv.osv, ir_edi.edi):
    _inherit = "account.invoice.tax"

account_invoice_tax()
