# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class LinkTracker(models.Model):
    _inherit = "link.tracker"

    mass_mailing_id = fields.Many2one('mail.mass_mailing', string='Mass Mailing')
    mass_mailing_campaign_id = fields.Many2one('mail.mass_mailing.campaign', string='Mass Mailing Campaign')


class LinkTrackerClick(models.Model):
    _inherit = "link.tracker.click"

    mail_stat_id = fields.Many2one('mail.mail.statistics', string='Mail Statistics')
    mass_mailing_id = fields.Many2one('mail.mass_mailing', string='Mass Mailing')
    mass_mailing_campaign_id = fields.Many2one('mail.mass_mailing.campaign', string='Mass Mailing Campaign')

    def _get_click_values_from_route(self, route_values):
        click_values = super(LinkTrackerClick, self)._get_click_values_from_route(route_values)
        if route_values['stat_id']:
            mail_stat = self.env['mail.mail.statistics'].browse(route_values['stat_id'])
            click_values['mail_stat_id'] = mail_stat.id
            if mail_stat.mass_mailing_campaign_id:
                click_values['mass_mailing_campaign_id'] = mail_stat.mass_mailing_campaign_id.id
            if mail_stat.mass_mailing_id:
                click_values['mass_mailing_id'] = mail_stat.mass_mailing_id.id
        return click_values
