# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Business Applications
#    Copyright (c) 2012-TODAY OpenERP S.A. <http://openerp.com>
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

import logging
from urllib import quote as quote

from openerp.osv import osv, fields
from openerp.tools import ustr
from openerp.tools.translate import _

_logger = logging.getLogger(__name__)
try:
    from mako.template import Template as MakoTemplate
except ImportError:
    _logger.warning("payment_acquirer: mako templates not available, payment acquirer will not work!")


class acquirer(osv.Model):
    _name = 'portal.payment.acquirer'
    _description = 'Online Payment Acquirer'
    
    _columns = {
        'name': fields.char('Name', required=True),
        'form_template': fields.text('Payment form template (HTML)', translate=True), 
        'visible': fields.boolean('Visible', help="Whether this payment acquirer is currently displayed in portal forms"),
    }

    _default = {
        'visible': True,
    }

    def render(self, cr, uid, id, object, reference, currency, amount, context=None, **kwargs):
        """ Renders the form template of the given acquirer as a mako template  """
        if not isinstance(id, (int,long)):
            id = id[0]
        this = self.browse(cr, uid, id)
        if context is None:
            context = {}
        try:
            i18n_kind = _(object._description) # may fail to translate, but at least we try
            template = ustr(this.form_template)
            result = MakoTemplate(template).render_unicode(object=object,
                                                           reference=reference,
                                                           currency=currency,
                                                           amount=amount,
                                                           kind=i18n_kind,
                                                           quote=quote,
                                                           # context kw would clash with mako internals
                                                           ctx=context,
                                                           format_exceptions=True)
            result = result.strip()
            if result == u'False':
                result = u''
            return result
        except Exception:
            _logger.exception("failed to render mako template value for payment.acquirer %s: %r", this.name, template)
            return

    def _wrap_payment_block(self, cr, uid, html_block, context=None):
        payment_header = _('Pay safely online:')
        result =  """<div class="payment_acquirers">
                         <span class="payment_header">%s</span>
                         %%s
                     </div>""" % payment_header
        return result % html_block

    def render_payment_block(self, cr, uid, object, reference, currency, amount, context=None, **kwargs):
        """ Renders all visible payment acquirer forms for the given rendering context, and
            return them wrapped in an appropriate HTML block, ready for direct inclusion
            in an OpenERP v7 form view """
        acquirer_ids = self.search(cr, uid, [('visible', '=', True)])
        if not acquirer_ids:
            return
        html_forms = []
        for this in self.browse(cr, uid, acquirer_ids):
            html_forms.append(this.render(object, reference, currency, amount, context=context, **kwargs))
        html_block = '\n'.join(html_forms)
        return self._wrap_payment_block(cr, uid, html_block, context=context)  
