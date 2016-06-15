# -*- coding: utf-8 -*-

from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from openerp import api, fields, models, _
from openerp.exceptions import UserError, ValidationError
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT as DF


class AccountAssetCategory(models.Model):
    _name = 'account.asset.category'
    _description = 'Asset category'

    active = fields.Boolean(default=True)
    name = fields.Char(required=True, index=True, string="Asset Type")
    account_analytic_id = fields.Many2one('account.analytic.account', string='Analytic Account', domain=[('account_type', '=', 'normal')])
    account_asset_id = fields.Many2one('account.account', string='Expense Account', required=True, domain=[('internal_type','=','other'), ('deprecated', '=', False)])
    account_income_recognition_id = fields.Many2one('account.account', string='Recognition Income Account', domain=[('internal_type','=','other'), ('deprecated', '=', False)], oldname='account_expense_depreciation_id')
    account_depreciation_id = fields.Many2one('account.account', string='Depreciation Account', required=True, domain=[('internal_type','=','other'), ('deprecated', '=', False)])
    journal_id = fields.Many2one('account.journal', string='Journal', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env['res.company']._company_default_get('account.asset.category'))
    method = fields.Selection([('linear', 'Linear'), ('degressive', 'Degressive')], string='Computation Method', required=True, default='linear',
        help="Choose the method to use to compute the amount of depreciation lines.\n"
            "  * Linear: Calculated on basis of: Gross Value / Number of Depreciations\n"
            "  * Degressive: Calculated on basis of: Residual Value * Degressive Factor")
    method_number = fields.Integer(string='Number of Depreciations', default=5, help="The number of depreciations needed to depreciate your asset")
    method_period = fields.Integer(string='Period Length', default=1, help="State here the time between 2 depreciations, in months", required=True)
    method_progress_factor = fields.Float('Degressive Factor', default=0.3)
    method_time = fields.Selection([('number', 'Number of Depreciations'), ('end', 'Ending Date')], string='Time Method', required=True, default='number',
        help="Choose the method to use to compute the dates and number of depreciation lines.\n"
           "  * Number of Depreciations: Fix the number of depreciation lines and the time between 2 depreciations.\n"
           "  * Ending Date: Choose the time between 2 depreciations and the date the depreciations won't go beyond.")
    method_end = fields.Date('Ending date')
    prorata = fields.Boolean(string='Prorata Temporis', help='Indicates that the first depreciation entry for this asset have to be done from the purchase date instead of the first of January')
    open_asset = fields.Boolean(string='Post Journal Entries', help="Check this if you want to automatically confirm the assets of this category when created by invoices.")
    type = fields.Selection([('sale', 'Sale: Revenue Recognition'), ('purchase', 'Purchase: Asset')], required=True, index=True, default='purchase')

    @api.onchange('type')
    def onchange_type(self):
        if self.type == 'sale':
            self.prorata = True
            self.method_period = 1
        else:
            self.method_period = 12


class AccountAssetAsset(models.Model):
    _name = 'account.asset.asset'
    _description = 'Asset/Revenue Recognition'
    _inherit = ['mail.thread', 'ir.needaction_mixin']

    account_move_ids = fields.One2many('account.move', 'asset_id', string='Entries', readonly=True, states={'draft': [('readonly', False)]})
    entry_count = fields.Integer(compute='_entry_count', string='# Asset Entries')
    name = fields.Char(string='Asset Name', required=True, readonly=True, states={'draft': [('readonly', False)]})
    code = fields.Char(string='Reference', size=32, readonly=True, states={'draft': [('readonly', False)]})
    value = fields.Float(string='Gross Value', required=True, readonly=True, digits=0, states={'draft': [('readonly', False)]}, oldname='purchase_value')
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, readonly=True, states={'draft': [('readonly', False)]},
        default=lambda self: self.env.user.company_id.currency_id.id)
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True, states={'draft': [('readonly', False)]},
        default=lambda self: self.env['res.company']._company_default_get('account.asset.asset'))
    note = fields.Text()
    category_id = fields.Many2one('account.asset.category', string='Category', required=True, change_default=True, readonly=True, states={'draft': [('readonly', False)]})
    date = fields.Date(string='Date', required=True, readonly=True, states={'draft': [('readonly', False)]}, default=fields.Date.context_today, oldname="purchase_date")
    state = fields.Selection([('draft', 'Draft'), ('open', 'Running'), ('close', 'Close')], 'Status', required=True, copy=False, default='draft',
        help="When an asset is created, the status is 'Draft'.\n"
            "If the asset is confirmed, the status goes in 'Running' and the depreciation lines can be posted in the accounting.\n"
            "You can manually close an asset when the depreciation is over. If the last line of depreciation is posted, the asset automatically goes in that status.")
    active = fields.Boolean(default=True)
    partner_id = fields.Many2one('res.partner', string='Partner', readonly=True, states={'draft': [('readonly', False)]})
    method = fields.Selection([('linear', 'Linear'), ('degressive', 'Degressive')], string='Computation Method', required=True, readonly=True, states={'draft': [('readonly', False)]}, default='linear',
        help="Choose the method to use to compute the amount of depreciation lines.\n  * Linear: Calculated on basis of: Gross Value / Number of Depreciations\n"
            "  * Degressive: Calculated on basis of: Residual Value * Degressive Factor")
    method_number = fields.Integer(string='Number of Depreciations', readonly=True, states={'draft': [('readonly', False)]}, default=5, help="The number of depreciations needed to depreciate your asset")
    method_period = fields.Integer(string='Number of Months in a Period', required=True, readonly=True, default=12, states={'draft': [('readonly', False)]},
        help="The amount of time between two depreciations, in months")
    method_end = fields.Date(string='Ending Date', readonly=True, states={'draft': [('readonly', False)]})
    method_progress_factor = fields.Float(string='Degressive Factor', readonly=True, default=0.3, states={'draft': [('readonly', False)]})
    value_residual = fields.Float(compute='_amount_residual', method=True, digits=0, string='Residual Value')
    method_time = fields.Selection([('number', 'Number of Depreciations'), ('end', 'Ending Date')], string='Time Method', required=True, readonly=True, default='number', states={'draft': [('readonly', False)]},
        help="Choose the method to use to compute the dates and number of depreciation lines.\n"
             "  * Number of Depreciations: Fix the number of depreciation lines and the time between 2 depreciations.\n"
             "  * Ending Date: Choose the time between 2 depreciations and the date the depreciations won't go beyond.")
    prorata = fields.Boolean(string='Prorata Temporis', readonly=True, states={'draft': [('readonly', False)]},
        help='Indicates that the first depreciation entry for this asset have to be done from the purchase date instead of the first January / Start date of fiscal year')
    depreciation_line_ids = fields.One2many('account.asset.depreciation.line', 'asset_id', string='Depreciation Lines', readonly=True, states={'draft': [('readonly', False)], 'open': [('readonly', False)]})
    salvage_value = fields.Float(string='Salvage Value', digits=0, readonly=True, states={'draft': [('readonly', False)]},
        help="It is the amount you plan to have that you cannot depreciate.")
    invoice_id = fields.Many2one('account.invoice', string='Invoice', states={'draft': [('readonly', False)]}, copy=False)
    type = fields.Selection(related="category_id.type", string='Type', required=True)

    @api.multi
    def unlink(self):
        for asset in self:
            if asset.state in ['open', 'close']:
                raise UserError(_('You cannot delete a document is in %s state.') % (asset.state,))
            if asset.account_move_ids:
                raise UserError(_('You cannot delete a document that contains posted entries.'))
        return super(AccountAssetAsset, self).unlink()

    @api.multi
    def _get_last_depreciation_date(self):
        """
        @param id: ids of a account.asset.asset objects
        @return: Returns a dictionary of the effective dates of the last depreciation entry made for given asset ids. If there isn't any, return the purchase date of this asset
        """
        self.env.cr.execute("""
            SELECT a.id as id, COALESCE(MAX(m.date),a.date) AS date
            FROM account_asset_asset a
            LEFT JOIN account_move m ON (m.asset_id = a.id)
            WHERE a.id IN %s
            GROUP BY a.id, a.date """, (tuple(self.ids),))
        result = dict(self.env.cr.fetchall())
        return result

    @api.model
    def _cron_generate_entries(self):
        assets = self.env['account.asset.asset'].search([('state', '=', 'open')])
        assets._compute_entries(datetime.today())

    def _compute_board_amount(self, sequence, residual_amount, amount_to_depr, undone_dotation_number, posted_depreciation_line_ids, total_days, depreciation_date):
        amount = 0
        if sequence == undone_dotation_number:
            amount = residual_amount
        else:
            if self.method == 'linear':
                amount = amount_to_depr / (undone_dotation_number - len(posted_depreciation_line_ids))
                if self.prorata and self.category_id.type == 'purchase':
                    amount = amount_to_depr / self.method_number
                    if sequence == 1:
                        days = (self.company_id.compute_fiscalyear_dates(depreciation_date)['date_to'] - depreciation_date).days + 1
                        amount = (amount_to_depr / self.method_number) / total_days * days
            elif self.method == 'degressive':
                amount = residual_amount * self.method_progress_factor
                if self.prorata:
                    if sequence == 1:
                        days = (self.company_id.compute_fiscalyear_dates(depreciation_date)['date_to'] - depreciation_date).days + 1
                        amount = (residual_amount * self.method_progress_factor) / total_days * days
        return amount

    def _compute_board_undone_dotation_nb(self, depreciation_date, total_days):
        undone_dotation_number = self.method_number
        if self.method_time == 'end':
            end_date = datetime.strptime(self.method_end, DF).date()
            undone_dotation_number = 0
            while depreciation_date <= end_date:
                depreciation_date = date(depreciation_date.year, depreciation_date.month, depreciation_date.day) + relativedelta(months=+self.method_period)
                undone_dotation_number += 1
        if self.prorata and self.category_id.type == 'purchase':
            undone_dotation_number += 1
        return undone_dotation_number

    @api.multi
    def compute_depreciation_board(self):
        self.ensure_one()

        posted_depreciation_line_ids = self.depreciation_line_ids.filtered(lambda x: x.move_check).sorted(key=lambda l: l.depreciation_date)
        unposted_depreciation_line_ids = self.depreciation_line_ids.filtered(lambda x: not x.move_check)

        # Remove old unposted depreciation lines. We cannot use unlink() with One2many field
        commands = [(2, line_id.id, False) for line_id in unposted_depreciation_line_ids]

        if self.value_residual != 0.0:
            amount_to_depr = residual_amount = self.value_residual
            if self.prorata:
                depreciation_date = datetime.strptime(self._get_last_depreciation_date()[self.id], DF).date()
            else:
                # depreciation_date = 1st of January of purchase year
                asset_date = datetime.strptime(self.date[:4] + '-01-01', DF).date()
                # if we already have some previous validated entries, starting date isn't 1st January but last entry + method period
                if posted_depreciation_line_ids and posted_depreciation_line_ids[-1].depreciation_date:
                    last_depreciation_date = datetime.strptime(posted_depreciation_line_ids[-1].depreciation_date, DF).date()
                    depreciation_date = last_depreciation_date + relativedelta(months=+self.method_period)
                else:
                    depreciation_date = asset_date
            day = depreciation_date.day
            month = depreciation_date.month
            year = depreciation_date.year
            total_days = (year % 4) and 365 or 366

            undone_dotation_number = self._compute_board_undone_dotation_nb(depreciation_date, total_days)

            for x in range(len(posted_depreciation_line_ids), undone_dotation_number):
                sequence = x + 1
                amount = self._compute_board_amount(sequence, residual_amount, amount_to_depr, undone_dotation_number, posted_depreciation_line_ids, total_days, depreciation_date)
                amount = self.currency_id.round(amount)
                residual_amount -= amount
                vals = {
                    'amount': amount,
                    'asset_id': self.id,
                    'sequence': sequence,
                    'name': (self.code or '') + '/' + str(sequence),
                    'remaining_value': residual_amount,
                    'depreciated_value': self.value - (self.salvage_value + residual_amount),
                    'depreciation_date': depreciation_date.strftime(DF),
                }
                commands.append((0, False, vals))
                # Considering Depr. Period as months
                depreciation_date = date(year, month, day) + relativedelta(months=+self.method_period)
                day = depreciation_date.day
                month = depreciation_date.month
                year = depreciation_date.year

        self.write({'depreciation_line_ids': commands})

        return True

    @api.multi
    def validate(self):
        self.write({'state': 'open'})
        fields = [
            'method',
            'method_number',
            'method_period',
            'method_end',
            'method_progress_factor',
            'method_time',
            'salvage_value',
            'invoice_id',
        ]
        ref_tracked_fields = self.env['account.asset.asset'].fields_get(fields)
        for asset in self:
            tracked_fields = ref_tracked_fields.copy()
            if asset.method == 'linear':
                del(tracked_fields['method_progress_factor'])
            if asset.method_time != 'end':
                del(tracked_fields['method_end'])
            else:
                del(tracked_fields['method_number'])
            dummy, tracking_value_ids = asset._message_track(tracked_fields, dict.fromkeys(fields))
            asset.message_post(subject=_('Asset created'), tracking_value_ids=tracking_value_ids)

    @api.multi
    def set_to_close(self):
        move_ids = []
        for asset in self:
            unposted_depreciation_line_ids = asset.depreciation_line_ids.filtered(lambda x: not x.move_check)
            if unposted_depreciation_line_ids:
                old_values = {
                    'method_end': asset.method_end,
                    'method_number': asset.method_number,
                }

                # Remove all unposted depr. lines
                commands = [(2, line_id.id, False) for line_id in unposted_depreciation_line_ids]

                # Create a new depr. line with the residual amount and post it
                sequence = len(asset.depreciation_line_ids) - len(unposted_depreciation_line_ids) + 1
                today = datetime.today().strftime(DF)
                vals = {
                    'amount': asset.value_residual,
                    'asset_id': asset.id,
                    'sequence': sequence,
                    'name': (asset.code or '') + '/' + str(sequence),
                    'remaining_value': 0,
                    'depreciated_value': asset.value - asset.salvage_value,  # the asset is completely depreciated
                    'depreciation_date': today,
                }
                commands.append((0, False, vals))
                asset.write({'depreciation_line_ids': commands, 'method_end': today, 'method_number': sequence})
                tracked_fields = self.env['account.asset.asset'].fields_get(['method_number', 'method_end'])
                changes, tracking_value_ids = asset._message_track(tracked_fields, old_values)
                if changes:
                    asset.message_post(subject=_('Asset sold or disposed. Accounting entry awaiting for validation.'), tracking_value_ids=tracking_value_ids)
                move_ids += asset.depreciation_line_ids[-1].create_move(post_move=False)
        if move_ids:
            name = _('Disposal Move')
            view_mode = 'form'
            if len(move_ids) > 1:
                name = _('Disposal Moves')
                view_mode = 'tree,form'
            return {
                'name': name,
                'view_type': 'form',
                'view_mode': view_mode,
                'res_model': 'account.move',
                'type': 'ir.actions.act_window',
                'target': 'current',
                'res_id': move_ids[0],
            }

    @api.multi
    def set_to_draft(self):
        self.write({'state': 'draft'})

    @api.one
    @api.depends('value', 'salvage_value', 'depreciation_line_ids.move_check', 'depreciation_line_ids.amount')
    def _amount_residual(self):
        total_amount = 0.0
        for line in self.depreciation_line_ids:
            if line.move_check:
                total_amount += line.amount
        self.value_residual = self.value - total_amount - self.salvage_value

    @api.onchange('company_id')
    def onchange_company_id(self):
        self.currency_id = self.company_id.currency_id.id

    @api.multi
    @api.depends('account_move_ids')
    def _entry_count(self):
        for asset in self:
            asset.entry_count = self.env['account.move'].search_count([('asset_id', '=', asset.id)])

    @api.one
    @api.constrains('prorata', 'method_time')
    def _check_prorata(self):
        if self.prorata and self.method_time != 'number':
            raise ValidationError(_('Prorata temporis can be applied only for time method "number of depreciations".'))

    @api.onchange('category_id')
    def onchange_category_id(self):
        vals = self.onchange_category_id_values(self.category_id.id)
        # We cannot use 'write' on an object that doesn't exist yet
        if vals:
            for k, v in vals['value'].iteritems():
                setattr(self, k, v)

    def onchange_category_id_values(self, category_id):
        if category_id:
            category = self.env['account.asset.category'].browse(category_id)
            return {
                'value': {
                    'method': category.method,
                    'method_number': category.method_number,
                    'method_time': category.method_time,
                    'method_period': category.method_period,
                    'method_progress_factor': category.method_progress_factor,
                    'method_end': category.method_end,
                    'prorata': category.prorata,
                }
            }

    @api.onchange('method_time')
    def onchange_method_time(self):
        if self.method_time != 'number':
            self.prorata = False

    @api.multi
    def copy_data(self, default=None):
        if default is None:
            default = {}
        default['name'] = self.name + _(' (copy)')
        return super(AccountAssetAsset, self).copy_data(default)[0]

    @api.multi
    def _compute_entries(self, date):
        depreciation_ids = self.env['account.asset.depreciation.line'].search([
            ('asset_id', 'in', self.ids), ('depreciation_date', '<=', date),
            ('move_check', '=', False)])
        return depreciation_ids.create_move()

    @api.model
    def create(self, vals):
        asset = super(AccountAssetAsset, self.with_context(mail_create_nolog=True)).create(vals)
        asset.compute_depreciation_board()
        return asset

    @api.multi
    def write(self, vals):
        res = super(AccountAssetAsset, self).write(vals)
        if 'depreciation_line_ids' not in vals and 'state' not in vals:
            self.compute_depreciation_board()
        return res

    @api.multi
    def open_entries(self):
        return {
            'name': _('Journal Entries'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': dict(self.env.context or {}, search_default_asset_id=self.id, default_asset_id=self.id),
        }


class AccountAssetDepreciationLine(models.Model):
    _name = 'account.asset.depreciation.line'
    _description = 'Asset depreciation line'

    name = fields.Char(string='Depreciation Name', required=True, index=True)
    sequence = fields.Integer(required=True)
    asset_id = fields.Many2one('account.asset.asset', string='Asset', required=True, ondelete='cascade')
    parent_state = fields.Selection(related='asset_id.state', string='State of Asset')
    amount = fields.Float(string='Current Depreciation', digits=0, required=True)
    remaining_value = fields.Float(string='Next Period Depreciation', digits=0, required=True)
    depreciated_value = fields.Float(string='Cumulative Depreciation', required=True)
    depreciation_date = fields.Date('Depreciation Date', index=True)
    move_id = fields.Many2one('account.move', string='Depreciation Entry')
    move_check = fields.Boolean(compute='_get_move_check', string='Posted', track_visibility='always', store=True)

    @api.one
    @api.depends('move_id')
    def _get_move_check(self):
        self.move_check = bool(self.move_id)

    @api.multi
    def create_move(self, post_move=True):
        created_moves = self.env['account.move']
        for line in self:
            depreciation_date = self.env.context.get('depreciation_date') or line.depreciation_date or fields.Date.context_today(self)
            company_currency = line.asset_id.company_id.currency_id
            current_currency = line.asset_id.currency_id
            amount = current_currency.compute(line.amount, company_currency)
            sign = (line.asset_id.category_id.journal_id.type == 'purchase' or line.asset_id.category_id.journal_id.type == 'sale' and 1) or -1
            asset_name = line.asset_id.name + ' (%s/%s)' % (line.sequence, line.asset_id.method_number)
            reference = line.asset_id.code
            journal_id = line.asset_id.category_id.journal_id.id
            partner_id = line.asset_id.partner_id.id
            categ_type = line.asset_id.category_id.type
            debit_account = line.asset_id.category_id.account_asset_id.id
            credit_account = line.asset_id.category_id.account_depreciation_id.id
            move_line_1 = {
                'name': asset_name,
                'account_id': credit_account,
                'debit': 0.0,
                'credit': amount,
                'journal_id': journal_id,
                'partner_id': partner_id,
                'currency_id': company_currency != current_currency and current_currency.id or False,
                'amount_currency': company_currency != current_currency and - sign * line.amount or 0.0,
                'analytic_account_id': line.asset_id.category_id.account_analytic_id.id if categ_type == 'sale' else False,
                'date': depreciation_date,
            }
            move_line_2 = {
                'name': asset_name,
                'account_id': debit_account,
                'credit': 0.0,
                'debit': amount,
                'journal_id': journal_id,
                'partner_id': partner_id,
                'currency_id': company_currency != current_currency and current_currency.id or False,
                'amount_currency': company_currency != current_currency and sign * line.amount or 0.0,
                'analytic_account_id': line.asset_id.category_id.account_analytic_id.id if categ_type == 'purchase' else False,
                'date': depreciation_date,
            }
            move_vals = {
                'ref': reference,
                'date': depreciation_date or False,
                'journal_id': line.asset_id.category_id.journal_id.id,
                'line_ids': [(0, 0, move_line_1), (0, 0, move_line_2)],
                'asset_id': line.asset_id.id,
                }
            move = self.env['account.move'].create(move_vals)
            line.write({'move_id': move.id, 'move_check': True})
            created_moves |= move

        if post_move and created_moves:
            created_moves.filtered(lambda r: r.asset_id and r.asset_id.category_id and r.asset_id.category_id.open_asset).post()
        return [x.id for x in created_moves]

    @api.multi
    def post_lines_and_close_asset(self):
        # we re-evaluate the assets to determine whether we can close them
        for line in self:
            line.log_message_when_posted()
            asset = line.asset_id
            if asset.currency_id.is_zero(asset.value_residual):
                asset.message_post(body=_("Document closed."))
                asset.write({'state': 'close'})

    @api.multi
    def log_message_when_posted(self):
        def _format_message(message_description, tracked_values):
            message = ''
            if message_description:
                message = '<span>%s</span>' % message_description
            for name, values in tracked_values.iteritems():
                message += '<div> &nbsp; &nbsp; &bull; <b>%s</b>: ' % name
                message += '%s</div>' % values
            return message

        for line in self:
            if line.move_id and line.move_id.state == 'draft':
                partner_name = line.asset_id.partner_id.name
                currency_name = line.asset_id.currency_id.name
                msg_values = {_('Currency'): currency_name, _('Amount'): line.amount}
                if partner_name:
                    msg_values[_('Partner')] = partner_name
                msg = _format_message(_('Depreciation line posted.'), msg_values)
                line.asset_id.message_post(body=msg)

    @api.multi
    def unlink(self):
        for record in self:
            if record.move_check:
                if record.asset_id.category_id.type == 'purchase':
                    msg = _("You cannot delete posted depreciation lines.")
                else:
                    msg = _("You cannot delete posted installment lines.")
                raise UserError(msg)
        return super(AccountAssetDepreciationLine, self).unlink()


class AccountMove(models.Model):
    _inherit = 'account.move'

    asset_id = fields.Many2one('account.asset.asset', string='Asset', ondelete="restrict")

    @api.multi
    def post(self):
        for move in self:
            if move.asset_id:
                move.asset_id.depreciation_line_ids.post_lines_and_close_asset()
        return super(AccountMove, self).post()
