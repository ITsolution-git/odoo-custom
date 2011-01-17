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


{
    'name': 'Event',
    'version': '0.1',
    'category': 'Generic Modules/Association',
    'description': """Organization and management of Event.

    This module allow you
        * to manage your events and their registrations
        * to use emails to automatically confirm and send acknowledgements for any registration to an event
        * ...
    A dashboard for associations that includes:
    * Registration by Events (graph)
    Note that:
    - You can define new types of events in
                Events / Configuration / Types of Events
    - You can access predefined reports about number of registration per event or per event category in:
                Events / Reporting
""",
    'author': 'OpenERP SA',
    'depends': ['crm', 'base_contact', 'account', 'marketing'],
    'init_xml': [],
    'update_xml': [
        'security/event_security.xml',
        'security/ir.model.access.csv',
        'wizard/event_confirm_registration_view.xml',
        'wizard/event_confirm_view.xml',
        'event_view.xml',
        'report/report_event_registration_view.xml',
        'wizard/event_make_invoice_view.xml',
        'wizard/partner_event_registration_view.xml',
        'board_association_view.xml',
        'res_partner_view.xml',
    ],
    'demo_xml': ['event_demo.xml'],
    'test': ['test/test_event.yml'],
    'installable': True,
    'active': False,
    'certificate': '0083059161581',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
