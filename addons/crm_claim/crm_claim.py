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

from osv import fields, osv
from crm import crm
import time
from crm import wizard
import binascii
import tools
from tools.translate import _

wizard.mail_compose_message.SUPPORTED_MODELS.append('crm.claim')
CRM_CLAIM_PENDING_STATES = (
    crm.AVAILABLE_STATES[2][0], # Cancelled
    crm.AVAILABLE_STATES[3][0], # Done
    crm.AVAILABLE_STATES[4][0], # Pending
)


class crm_claim(crm.crm_case, osv.osv):
    """
    Crm claim
    """
    
    def _get_state(self, cr, uid, ids, name, arg, context=None):
        res = {}
        for claim in self.browse(cr, uid, ids, context=context):
            if claim.stage_id:
                res[claim.id] = claim.stage_id.state
        return res

    def _get_stage(self, cr, uid, ids, context=None):
        claim_obj = self.pool.get('crm.claim')
        result = {}
        for stage in self.browse(cr, uid, ids, context=context):
            if stage.state:
                claim_ids = claim_obj.search(cr, uid, [('state', '=', stage.state)], context=context)
        for claim in claim_obj.browse(cr, uid, claim_ids, context=context):
            result[claim.id] = True
        return result.keys()

    def _save_state(self, cr, uid, claim_id, field_name, field_value, arg, context=None):
        stage_ids = self.pool.get('crm.case.stage').search(cr, uid, [('state', '=', field_value)], context=context)
        if stage_ids:
            return self.write(cr, uid, claim_id, {'stage_id': stage_ids[0]}, context=context)
        else:
            return cr.execute("""UPDATE crm_claim SET state=%s WHERE id=%s""", (field_value, claim_id, ))

    _name = "crm.claim"
    _description = "Claim"
    _order = "priority,date desc"
    _inherit = ['mail.thread']
    _columns = {
        'id': fields.integer('ID', readonly=True),
        'name': fields.char('Claim Subject', size=128, required=True),
        'active': fields.boolean('Active'),
        'action_next': fields.char('Next Action', size=200),
        'date_action_next': fields.datetime('Next Action Date'),
        'description': fields.text('Description'),
        'resolution': fields.text('Resolution'),
        'create_date': fields.datetime('Creation Date' , readonly=True),
        'write_date': fields.datetime('Update Date' , readonly=True),
        'date_deadline': fields.date('Deadline'),
        'date_closed': fields.datetime('Closed', readonly=True),
        'date': fields.datetime('Claim Date', select=True),
        'ref' : fields.reference('Reference', selection=crm._links_get, size=128),
        'categ_id': fields.many2one('crm.case.categ', 'Category', \
                            domain="[('section_id','=',section_id),\
                            ('object_id.model', '=', 'crm.claim')]"),
        'priority': fields.selection(crm.AVAILABLE_PRIORITIES, 'Priority'),
        'type_action': fields.selection([('correction','Corrective Action'),('prevention','Preventive Action')], 'Action Type'),
        'user_id': fields.many2one('res.users', 'Responsible'),
        'user_fault': fields.char('Trouble Responsible', size=64),
        'section_id': fields.many2one('crm.case.section', 'Sales Team', \
                        select=True, help="Sales team to which Case belongs to."\
                                "Define Responsible user and Email account for"\
                                " mail gateway."),
        'company_id': fields.many2one('res.company', 'Company'),
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'email_cc': fields.text('Watchers Emails', size=252, help="These email addresses will be added to the CC field of all inbound and outbound emails for this record before being sent. Separate multiple email addresses with a comma"),
        'email_from': fields.char('Email', size=128, help="These people will receive email."),
        'partner_phone': fields.char('Phone', size=32),
        'stage_id': fields.many2one ('crm.case.stage', 'Stage', domain="[('section_ids','=',section_id)]"), 
        'cause': fields.text('Root Cause'),
        'state': fields.function(_get_state, fnct_inv=_save_state, type='selection', selection=crm.AVAILABLE_STATES, string="State", readonly=True,
            store = {
                'crm.claim': (lambda self, cr, uid, ids, c={}: ids, ['stage_id'], 10),
                'crm.case.stage': (_get_stage, ['state'], 10)
            },
                                  help='The state is set to \'Draft\', when a case is created.\
                                  \nIf the case is in progress the state is set to \'Open\'.\
                                  \nWhen the case is over, the state is set to \'Done\'.\
                                  \nIf the case needs to be reviewed then the state is set to \'Pending\'.'),
        'message_ids': fields.one2many('mail.message', 'res_id', 'Messages', domain=[('model','=',_name)]),
    }

    _defaults = {
        'user_id': crm.crm_case._get_default_user,
        'partner_id': crm.crm_case._get_default_partner,
        'email_from':crm.crm_case. _get_default_email,
        'state': lambda *a: 'draft',
        'section_id':crm.crm_case. _get_section,
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'company_id': lambda s, cr, uid, c: s.pool.get('res.company')._company_default_get(cr, uid, 'crm.case', context=c),
        'priority': lambda *a: crm.AVAILABLE_PRIORITIES[2][0],
        'active': lambda *a: 1
    }

    def case_get_note_msg_prefix(self, cr, uid, id, context=None):
        return 'Claim'

    def onchange_partner_id(self, cr, uid, ids, part, email=False):
        """This function returns value of partner address based on partner
           :param part: Partner's id
           :param email: ignored
        """
        if not part:
            return {'value': {'email_from': False,
                              'partner_phone': False
                            }
                   }
        address = self.pool.get('res.partner').browse(cr, uid, part)
        return {'value': {'email_from': address.email, 'partner_phone': address.phone}}

    def case_open(self, cr, uid, ids, *args):
        """Opens Claim"""
        for l in self.browse(cr, uid, ids):
            # When coming from draft override date and stage otherwise just set state
            if l.state == 'draft':
                message = _("The claim '%s' has been opened.") % l.name
                self.log(cr, uid, l.id, message)
                stage_id = self.stage_find(cr, uid, l.section_id.id or False, [('sequence','>',0)])
                if stage_id:
                    self.stage_set(cr, uid, [l.id], stage_id)
        res = super(crm_claim, self).case_open(cr, uid, ids, *args)
        return res
    
    def message_new(self, cr, uid, msg, custom_values=None, context=None):
        """Automatically called when new email message arrives"""
        res_id = super(crm_claim,self).message_new(cr, uid, msg, custom_values=custom_values, context=context)
        subject = msg.get('subject')
        body = msg.get('body_text')
        msg_from = msg.get('from')
        priority = msg.get('priority')
        vals = {
            'name': subject,
            'email_from': msg_from,
            'email_cc': msg.get('cc'),
            'description': body,
            'user_id': False,
        }
        if priority:
            vals['priority'] = priority
        vals.update(self.message_partner_by_email(cr, uid, msg.get('from', False)))
        self.write(cr, uid, [res_id], vals, context=context)
        return res_id

    def message_update(self, cr, uid, ids, msg, vals={}, default_act='pending', context=None):
        if isinstance(ids, (str, int, long)):
            ids = [ids]

        res_id = super(crm_claim,self).message_update(cr, uid, ids, msg, context=context)

        if msg.get('priority') in dict(crm.AVAILABLE_PRIORITIES):
            vals['priority'] = msg.get('priority')

        maps = {
            'cost':'planned_cost',
            'revenue': 'planned_revenue',
            'probability':'probability'
        }
        vls = {}
        for line in msg['body_text'].split('\n'):
            line = line.strip()
            res = tools.misc.command_re.match(line)
            if res and maps.get(res.group(1).lower()):
                key = maps.get(res.group(1).lower())
                vls[key] = res.group(2).lower()
        vals.update(vls)

        # Unfortunately the API is based on lists
        # but we want to update the state based on the
        # previous state, so we have to loop:
        for case in self.browse(cr, uid, ids, context=context):
            values = dict(vals)
            if case.state in CRM_CLAIM_PENDING_STATES:
                values.update(state=crm.AVAILABLE_STATES[1][0]) #re-open
            res = self.write(cr, uid, [case.id], values, context=context)
        return res

class res_partner(osv.osv):
    _inherit = 'res.partner'
    _columns = {
        'claims_ids': fields.one2many('crm.claim', 'partner_id', 'Claims'),
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
