# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.addons.website.models.website import slug


class ResPartnerGrade(models.Model):
    _name = 'res.partner.grade'
    _inherit = ['website.published.mixin']

    website_published = fields.Boolean(default=True)
    sequence = fields.Integer('Sequence')
    active = fields.Boolean('Active', default=lambda *args: 1)
    name = fields.Char('Level Name')
    partner_weight = fields.Integer('Level Weight', default=1,
        help="Gives the probability to assign a lead to this partner. (0 means no assignation.)")

    @api.multi
    def _website_url(self, field_name, arg):
        res = super(ResPartnerGrade, self)._website_url(field_name, arg)
        for grade in self:
            res[grade.id] = "/partners/grade/%s" % (slug(grade))
        return res

class ResPartnerActivation(models.Model):
    _name = 'res.partner.activation'
    _order = 'sequence'

    sequence = fields.Integer('Sequence')
    name = fields.Char('Name', required=True)

class ResPartner(models.Model):
    _inherit = "res.partner"

    partner_weight = fields.Integer('Level Weight', default=lambda *args: 0,
        help="Gives the probability to assign a lead to this partner. (0 means no assignation.)")
    grade_id = fields.Many2one('res.partner.grade', 'Level')
    activation = fields.Many2one('res.partner.activation', 'Activation', select=1)
    date_partnership = fields.Date('Partnership Date')
    date_review = fields.Date('Latest Partner Review')
    date_review_next = fields.Date('Next Partner Review')
    # customer implementation
    assigned_partner_id = fields.Many2one(
        'res.partner', 'Implemented by',
    )
    implemented_partner_ids = fields.One2many(
        'res.partner', 'assigned_partner_id',
        string='Implementation References',
    )

    @api.onchange('grade_id')
    def _onchange_grade_id(self):
        grade = self.grade_id
        self.partner_weight = grade.partner_weight if grade else 0
