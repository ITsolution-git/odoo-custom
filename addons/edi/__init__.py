# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Business Applications
#    Copyright (c) 2011 OpenERP S.A. <http://openerp.com>
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

from . import models
from . import edi_service
from models.edi import EDIMixin, edi
_logger = logging.getLogger(__name__)

# web
try:
    import openerp.addons.web.controllers
except ImportError:
    _logger.warn(
        """Could not load openerp-web section of EDI, EDI will not behave correctly

To fix, launch openerp-web in embedded mode""")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
