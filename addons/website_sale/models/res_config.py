# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields

class WebsiteConfigSettings(models.TransientModel):
    _inherit = 'website.config.settings'

    def _default_order_mail_template(self):
        if self.env['ir.module.module'].search([('name', '=', 'website_quote')]).state in ('installed', 'to upgrade'):
            return self.env.ref('website_quote.confirmation_mail').id
        else:
            return self.env.ref('sale.email_template_edi_sale').id

    salesperson_id = fields.Many2one('res.users', related='website_id.salesperson_id', string='Salesperson')
    salesteam_id = fields.Many2one('crm.team', related='website_id.salesteam_id', string='Sales Channel', domain=[('team_type', '!=', 'pos')])
    module_delivery = fields.Boolean("Manage shipping internally")
    module_website_sale_delivery = fields.Boolean("Shipping Costs")
    # field used to have a nice radio in form view, resuming the 2 fields above
    sale_delivery_settings = fields.Selection([
        ('none', 'No shipping management on website'),
        ('internal', "Delivery methods are only used internally: the customer doesn't pay for shipping costs"),
        ('website', "Delivery methods are selectable on the website: the customer pays for shipping costs"),
        ], string="Shipping Management")
    module_delivery_dhl = fields.Boolean("DHL integration")
    module_delivery_fedex = fields.Boolean("Fedex integration")
    module_delivery_ups = fields.Boolean("UPS integration")
    module_delivery_usps = fields.Boolean("USPS integration")
    module_delivery_bpost = fields.Boolean("bpost integration")

    module_sale_ebay = fields.Boolean("eBay connector")
    module_sale_coupon = fields.Boolean("Discount Programs")

    group_website_multiimage = fields.Boolean(string='Multi-Images', implied_group='website_sale.group_website_multi_image', group='base.group_portal,base.group_user,base.group_public')
    group_discount_per_so_line = fields.Boolean(string="Discounted Prices", implied_group='sale.group_discount_per_so_line')
    group_delivery_invoice_address = fields.Boolean(string="Shipping Address", implied_group='sale.group_delivery_invoice_address')

    module_website_sale_options = fields.Boolean("Optional Products", help='Installs *e-Commerce Optional Products*')
    module_website_sale_digital = fields.Boolean("Digital Content")
    module_website_sale_wishlist = fields.Boolean("Wishlists ", help='Installs *e-Commerce Wishlist*')
    module_website_sale_comparison = fields.Boolean("Product Comparator", help='Installs *e-Commerce Comparator*')

    module_account_invoicing = fields.Boolean("Invoicing")
    module_sale_stock = fields.Boolean("Delivery Orders")

    # sale_pricelist_settings splitted in several entries for usability purpose
    multi_sales_price = fields.Boolean(
        string="Multiple sales price per product",
        oldname='sale_pricelist_setting_split_1')
    multi_sales_price_method = fields.Selection([
        (0, 'Multiple prices per product (e.g. customer segments, currencies)'),
        (1, 'Prices computed from formulas (discounts, margins, roundings)')],
        string="Sales Price", default=0,
        oldname='sale_pricelist_setting_split_2')
    sale_pricelist_setting = fields.Selection([
        ('fixed', 'A single sales price per product'),
        ('percentage', 'Multiple prices per product (e.g. customer segments, currencies)'),
        ('formula', 'Price computed from formulas (discounts, margins, roundings)')
        ], string="Pricelists")
    group_sale_pricelist = fields.Boolean("Use pricelists to adapt your price per customers",
        implied_group='product.group_sale_pricelist')

    group_product_variant = fields.Boolean("Attributes and Variants", implied_group='product.group_product_variant')
    group_pricelist_item = fields.Boolean("Show pricelists to customers",
        implied_group='product.group_pricelist_item')
    group_product_pricelist = fields.Boolean("Show pricelists On Products",
        implied_group='product.group_product_pricelist')

    order_mail_template = fields.Many2one('mail.template', string='Order Confirmation Email',
        default=_default_order_mail_template, domain="[('model', '=', 'sale.order')]",
        help="Email sent to customer at the end of the checkout process")
    group_show_price_subtotal = fields.Boolean(
        "Show subtotal",
        implied_group='sale.group_show_price_subtotal',
        group='base.group_portal,base.group_user,base.group_public')
    group_show_price_total = fields.Boolean(
        "Show total",
        implied_group='sale.group_show_price_total',
        group='base.group_portal,base.group_user,base.group_public')

    default_invoice_policy = fields.Selection([
        ('order', 'Invoice what is ordered'),
        ('delivery', 'Invoice what is delivered')
        ], 'Invoicing Policy', default='order')
    automatic_invoice = fields.Boolean("Automatic Invoice")

    group_multi_currency = fields.Boolean(string='Multi-Currencies', implied_group='base.group_multi_currency')

    sale_show_tax = fields.Selection([
        ('total', 'Tax-Included Prices'),
        ('subtotal', 'Tax-Excluded Prices')],
        "Product Prices", default='total')

    @api.multi
    def set_automatic_invoice(self):
        value = self.module_account_invoicing and self.default_invoice_policy == 'order' and self.automatic_invoice
        self.env['ir.config_parameter'].sudo().set_param('website_sale.automatic_invoice', value)

    @api.model
    def get_default_automatic_invoice(self, fields):
        value = self.env['ir.config_parameter'].sudo().get_param('website_sale.automatic_invoice', default=False)
        return {'automatic_invoice': value}

    @api.onchange('multi_sales_price', 'multi_sales_price_method')
    def _onchange_sale_price(self):
        if self.multi_sales_price:
            if self.multi_sales_price_method:
                self.sale_pricelist_setting = 'formula'
            else:
                self.sale_pricelist_setting = 'percentage'
        else:
            self.sale_pricelist_setting = 'fixed'

    @api.onchange('sale_pricelist_setting')
    def _onchange_sale_pricelist_setting(self):
        if self.sale_pricelist_setting == 'percentage':
            self.update({
                'group_product_pricelist': True,
                'group_sale_pricelist': True,
                'group_pricelist_item': False,
            })
        elif self.sale_pricelist_setting == 'formula':
            self.update({
                'group_product_pricelist': False,
                'group_sale_pricelist': True,
                'group_pricelist_item': True,
            })
        else:
            self.update({
                'group_product_pricelist': False,
                'group_sale_pricelist': False,
                'group_pricelist_item': False,
            })

    @api.model
    def get_default_sale_delivery_settings(self, fields):
        sale_delivery_settings = 'none'
        if self.env['ir.module.module'].search([('name', '=', 'delivery')], limit=1).state in ('installed', 'to install', 'to upgrade'):
            sale_delivery_settings = 'internal'
            if self.env['ir.module.module'].search([('name', '=', 'website_sale_delivery')], limit=1).state in ('installed', 'to install', 'to upgrade'):
                sale_delivery_settings = 'website'
        return {'sale_delivery_settings': sale_delivery_settings}

    @api.model
    def get_default_sale_pricelist_setting(self, fields):
        sale_pricelist_setting = self.env['ir.config_parameter'].sudo().get_param('sale.sale_pricelist_setting')
        return dict(
            multi_sales_price=sale_pricelist_setting in ['percentage', 'formula'],
            multi_sales_price_method=sale_pricelist_setting in ['formula'] and 1 or False,
            sale_pricelist_setting=sale_pricelist_setting,
        )

    def set_multi_sales_price(self):
        self.env['ir.config_parameter'].sudo().set_param('sale.sale_pricelist_setting', self.sale_pricelist_setting)

    @api.onchange('sale_delivery_settings')
    def _onchange_sale_delivery_settings(self):
        if self.sale_delivery_settings == 'none':
            self.update({
                'module_delivery': False,
                'module_website_sale_delivery': False,
            })
        elif self.sale_delivery_settings == 'internal':
            self.update({
                'module_delivery': True,
                'module_website_sale_delivery': False,
            })
        else:
            self.update({
                'module_delivery': True,
                'module_website_sale_delivery': True,
            })

    @api.onchange('group_discount_per_so_line')
    def _onchange_group_discount_per_so_line(self):
        if self.group_discount_per_so_line:
            self.update({
                'sale_pricelist_setting_split_1': True,
            })

    @api.onchange('sale_show_tax')
    def _onchange_sale_tax(self):
        if self.sale_show_tax == "subtotal":
            self.update({
                'group_show_price_total': False,
                'group_show_price_subtotal': True,
            })
        else:
            self.update({
                'group_show_price_total': True,
                'group_show_price_subtotal': False,
            })

    def get_default_sale_show_tax(self, fields):
        return dict(sale_show_tax=self.env['ir.config_parameter'].sudo().get_param('website.sale_show_tax'))

    def set_sale_show_tax(self):
        return self.env['ir.config_parameter'].sudo().set_param('website.sale_show_tax', self.sale_show_tax)
