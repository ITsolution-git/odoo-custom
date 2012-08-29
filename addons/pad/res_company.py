# -*- coding: utf-8 -*-
from osv import fields, osv

DEFAULT_PAD_TEMPLATE = 'http://pad.openerp.com/p/%(db)s-%(model)s-%(salt)s'
DEFAULT_PAD_TEMPLATE = ''

class company_pad(osv.osv):
    _inherit = 'res.company'
    _columns = {
        'pad_url_template': fields.char('Pad URL Template', size=128, required=True, help="Template used to generate pad URL."),
    }
    _defaults = {
        'pad_url_template': DEFAULT_PAD_TEMPLATE,
    }


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
