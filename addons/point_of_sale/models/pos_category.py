# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, tools, _


class PosCategory(models.Model):
    _name = "pos.category"
    _description = "Public Category"
    _order = "sequence, name"

    @api.constrains('parent_id')
    def _check_category_recursion(self):
        if not self._check_recursion():
            raise ValueError(_('Error ! You cannot create recursive categories.'))

    name = fields.Char(required=True, translate=True)
    parent_id = fields.Many2one('pos.category', string='Parent Category', index=True)
    child_id = fields.One2many('pos.category', 'parent_id', string='Children Categories')
    sequence = fields.Integer(help="Gives the sequence order when displaying a list of product categories.")
    # NOTE: there is no 'default image', because by default we don't show
    # thumbnails for categories. However if we have a thumbnail for at least one
    # category, then we display a default image on the other, so that the
    # buttons have consistent styling.
    image = fields.Binary(attachment=True,
        help="This field holds the image used as image for the cateogry, limited to 1024x1024px.")
    image_medium = fields.Binary(string="Medium-sized image",
        compute='_compute_images', inverse='_inverse_image_medium', store=True, attachment=True,
        help="Medium-sized image of the category. It is automatically "
             "resized as a 128x128px image, with aspect ratio preserved. "
             "Use this field in form views or some kanban views.")
    image_small = fields.Binary(string="Small-sized image",
        compute='_compute_images', inverse='_inverse_image_small', store=True, attachment=True,
        help="Small-sized image of the category. It is automatically "
             "resized as a 64x64px image, with aspect ratio preserved. "
             "Use this field anywhere a small image is required.")

    @api.depends('image')
    def _compute_images(self):
        for rec in self:
            rec.image_medium = tools.image_resize_image_medium(rec.image)
            rec.image_small = tools.image_resize_image_small(rec.image)

    def _inverse_image_medium(self):
        for rec in self:
            rec.image = tools.image_resize_image_big(rec.image_medium)

    def _inverse_image_small(self):
        for rec in self:
            rec.image = tools.image_resize_image_big(rec.image_small)

    @api.multi
    def name_get(self):
        def get_names(cat):
            res = []
            while cat:
                res.append(cat.name)
                cat = cat.parent_id
            return res
        return [(cat.id, " / ".join(reversed(get_names(cat)))) for cat in self]
