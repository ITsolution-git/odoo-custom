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

from osv import fields, osv
from tools.translate import _
import decimal_precision as dp

class sale_advance_payment_inv(osv.osv_memory):
    _name = "sale.advance.payment.inv"
    _description = "Sales Advance Payment Invoice"

    _columns = {
        'advance_payment_method':fields.selection(
            [('all', 'Invoice the whole sale order'), ('percentage','Percentage'), ('fixed','Fixed price (deposit)'),
                ('lines', 'Some order lines')],
            'What do you want to invoice?', required=True,
            help="""Use All to create the final invoice.
                Use Percentage to invoice a percentage of the total amount.
                Use Fixed Price to invoice a specific amound in advance.
                Use Some Order Lines to invoice a selection of the sale order lines."""),
        'qtty': fields.float('Quantity', digits=(16, 2), required=True),
        'product_id': fields.many2one('product.product', 'Advance Product',
            help="""Select a product of type service which is called 'Advance Product'.
                You may have to create it and set it as a default value on this field."""),
        'amount': fields.float('Advance Amount', digits_compute= dp.get_precision('Account'),
            help="The amount to be invoiced in advance."),
    }


    def fields_view_get(self, cr, uid, view_id=None, view_type=False, context=None, toolbar=False, submenu=False):
        if context is None:context = {}
        user_obj = self.pool.get('res.users')
        res = super(sale_advance_payment_inv, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        active_ids = context.get('active_ids', False)
        invoice_obj = self.pool.get('account.invoice')
        model = context.get('active_model', '')
        model_obj = self.pool.get(model)
        if context.get('active_model', '') in ['sale.order'] and context.get('active_ids', []):
             order_data = model_obj.read(cr, uid, context.get('active_ids'), ['invoice_ids'])[0]
             for inv in invoice_obj.browse(cr, uid, order_data.get('invoice_ids')):
                 for line in inv.invoice_line:
                     # if percentage(Advance payment) is given then remove sale order lines option..
                     if str(line.name).startswith("Advance of"):
                         for field in res['fields']:
                             if field == 'advance_payment_method':
                                 res['fields'][field]['selection'] = [('all', 'Invoice all the Sale Order'), ('percentage', 'Percentage'), ('fixed', 'Fixed Price'),]
        return res

    def _get_advance_product(self, cr, uid, context=None):
        try:
            product = self.pool.get('ir.model.data').get_object(cr, uid, 'sale', 'advance_product_0')
        except ValueError:
            # a ValueError is returned if the xml id given is not found in the table ir_model_data
            return False
        return product.id

    _defaults = {
        'advance_payment_method': 'all',
        'qtty': 1.0,
        'product_id': _get_advance_product,
    }

    def onchange_method(self, cr, uid, ids, advance_payment_method, product_id, context=None):
        if advance_payment_method == 'percentage':
            return {'value': {'amount':0, 'product_id':False }}
        if product_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            return {'value': {'amount': product.list_price}}
        return {'value': {'amount': 0}}

    def create_invoices(self, cr, uid, ids, context=None):
        """ create invoices for the active sale orders """
        if context is None:
            context = {}
        sale_obj = self.pool.get('sale.order')
        inv_obj = self.pool.get('account.invoice')
        inv_line_obj = self.pool.get('account.invoice.line')
        ir_property_obj = self.pool.get('ir.property')
        act_window = self.pool.get('ir.actions.act_window')
        fiscal_obj = self.pool.get('account.fiscal.position')
        wizard = self.browse(cr, uid, ids[0], context)
        sale_ids = context.get('active_ids', [])

        if wizard.advance_payment_method == 'all':
            # create the final invoices of the active sale orders
            res = sale_obj.manual_invoice(cr, uid, sale_ids, context)
            if context.get('open_invoices', False):
                return res
            return {'type': 'ir.actions.act_window_close'}

        if wizard.advance_payment_method == 'lines':
            # open the list view of sale order lines to invoice
            res = act_window.for_xml_id(cr, uid, 'sale', 'action_order_line_tree2', context)
            res['context'] = {
                'search_default_uninvoiced': 1,
                'search_default_order_id': sale_ids and sale_ids[0] or False,
            }
            return res
        assert wizard.advance_payment_method in ('fixed', 'percentage')

        inv_ids = []

        for sale in sale_obj.browse(cr, uid, sale_ids, context=context):
            if sale.order_policy == 'postpaid':
                raise osv.except_osv(
                    _('Error!'),
                    _("You cannot make an advance on a sales order \
                         that is defined as 'Automatic Invoice after delivery'."))

            val = inv_line_obj.product_id_change(cr, uid, [], wizard.product_id.id,
                    uom=False, partner_id=sale.partner_id.id, fposition_id=sale.fiscal_position.id)
            res = val['value']

            # determine and check income account
            if not wizard.product_id.id :
                prop = ir_property_obj.get(cr, uid,
                            'property_account_income_categ', 'product.category', context=context)
                prop_id = prop and prop.id or False
                account_id = fiscal_obj.map_account(cr, uid, sale.fiscal_position.id or False, prop_id)
                if not account_id:
                    raise osv.except_osv(_('Configuration Error!'),
                            _('There is no income account defined as global property.'))
                res['account_id'] = account_id
            if not res.get('account_id'):
                raise osv.except_osv(_('Configuration Error!'),
                        _('There is no income account defined for this product: "%s" (id:%d).') % \
                            (wizard.product_id.name, wizard.product_id.id,))

            # determine invoice amount
            if wizard.amount <= 0.00:
                raise osv.except_osv(_('Incorrect Data'),
                    _('The value of Advance Amount must be positive.'))
            if wizard.advance_payment_method == 'percentage':
                inv_amount = sale.amount_total * wizard.amount / 100
                if not res.get('name'):
                    res['name'] = _("Advance of %s %%") % (wizard.amount)
            else:
                inv_amount = wizard.amount
                if not res.get('name'):
                    #TODO: should find a way to call formatLang() from rml_parse
                    symbol = sale.pricelist_id.currency_id.symbol
                    if sale.pricelist_id.currency_id.position == 'after':
                        res['name'] = _("Advance of %s %s") % (inv_amount, symbol)
                    else:
                        res['name'] = _("Advance of %s %s") % (symbol, inv_amount)

            # determine taxes
            if res.get('invoice_line_tax_id'):
                res['invoice_line_tax_id'] = [(6, 0, res.get('invoice_line_tax_id'))]
            else:
                res['invoice_line_tax_id'] = False

            # create the invoice
            inv_line_values = {
                'name': res.get('name'),
                'account_id': res['account_id'],
                'price_unit': inv_amount,
                'quantity': wizard.qtty or 1.0,
                'discount': False,
                'uos_id': res.get('uos_id', False),
                'product_id': wizard.product_id.id,
                'invoice_line_tax_id': res.get('invoice_line_tax_id'),
                'account_analytic_id': sale.project_id.id or False,
            }
            inv_values = {
                'name': sale.client_order_ref or sale.name,
                'origin': sale.name,
                'type': 'out_invoice',
                'reference': False,
                'account_id': sale.partner_id.property_account_receivable.id,
                'partner_id': sale.partner_id.id,
                'invoice_line': [(0, 0, inv_line_values)],
                'currency_id': sale.pricelist_id.currency_id.id,
                'comment': '',
                'payment_term': sale.payment_term.id,
                'fiscal_position': sale.fiscal_position.id or sale.partner_id.property_account_position.id
            }
            inv_id = inv_obj.create(cr, uid, inv_values, context=context)
            inv_obj.button_reset_taxes(cr, uid, [inv_id], context=context)
            inv_ids.append(inv_id)

            # add the invoice to the sale order's invoices
            sale.write({'invoice_ids': [(4, inv_id)]})

        if context.get('open_invoices', False):
            return self.open_invoices( cr, uid, ids, inv_ids, context=context)
        return {'type': 'ir.actions.act_window_close'}

    def open_invoices(self, cr, uid, ids, invoice_ids, context=None):
        """ open a view on one of the given invoice_ids """
        ir_model_data = self.pool.get('ir.model.data')
        form_res = ir_model_data.get_object_reference(cr, uid, 'account', 'invoice_form')
        form_id = form_res and form_res[1] or False
        tree_res = ir_model_data.get_object_reference(cr, uid, 'account', 'invoice_tree')
        tree_id = tree_res and tree_res[1] or False

        return {
            'name': _('Advance Invoice'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'account.invoice',
            'res_id': invoice_ids[0],
            'view_id': False,
            'views': [(form_id, 'form'), (tree_id, 'tree')],
            'context': "{'type': 'out_invoice'}",
            'type': 'ir.actions.act_window',
        }

sale_advance_payment_inv()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
