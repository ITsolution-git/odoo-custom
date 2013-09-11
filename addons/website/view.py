# -*- coding: utf-8 -*-

from lxml import etree, html
from openerp.osv import osv, fields


class view(osv.osv):
    _inherit = "ir.ui.view"
    _columns = {
        'inherit_option_id': fields.many2one('ir.ui.view','Optional Inheritancy'),
        'inherited_option_ids': fields.one2many('ir.ui.view','inherit_option_id','Optional Inheritancies'),
        'page': fields.boolean("Whether this view is a web page template (complete)"),
    }
    _defaults = {
        'page': False,
    }

    # Returns all views (called and inherited) related to a view
    # Used by translation mechanism, SEO and optional templates
    def _views_get(self, cr, uid, view, options=True, context=None, root=True, stack_result=None):
        if  not context:
            context = {}
        if  not stack_result:
            stack_result = []

        def view_obj(view):
            if type(view) in (str, unicode):
                mod_obj = self.pool.get("ir.model.data")
                m, n = view.split('.')
                _, view = mod_obj.get_object_reference(cr, uid, m, n)
            if type(view) == int:
                view_obj = self.pool.get("ir.ui.view")
                view = view_obj.browse(cr, uid, view, context=context)
            return view
        view = view_obj(view)

        while root and view.inherit_id:
            view = view.inherit_id

        result = [view]
        todo = view.inherit_children_ids
        if options:
            todo += filter(lambda x: not x.inherit_id, view.inherited_option_ids)
        for child_view in todo:
            result += self._views_get(cr, uid, child_view, options=options, context=context, root=False, stack_result=result)
        node = etree.fromstring(view.arch)
        for child in node.xpath("//t[@t-call]"):
            call_view = view_obj(child.get('t-call'))
            if call_view not in stack_result:
                result += self._views_get(cr, uid, call_view, options=options, context=context, stack_result=result)
        return result



    def extract_embedded_fields(self, cr, uid, arch, context=None):
        return arch.xpath('//*[@data-oe-model != "ir.ui.view"]')

    def save_embedded_field(self, cr, uid, el, context=None):
        embedded_id = int(el.get('data-oe-id'))
        # FIXME: type conversions
        self.pool[el.get('data-oe-model')].write(cr, uid, embedded_id, {
            # FIXME: ckeditor parser does not follow HTML5 parsing, breaks block-level links
            el.get('data-oe-field'): el.text_content()
        }, context=context)

    def to_field_ref(self, cr, uid, el, context=None):
        out = html.html_parser.makeelement(el.tag, attrib={
            't-field': el.get('data-oe-expression'),
        })
        out.tail = el.tail
        return out

    def replace_arch_section(self, cr, uid, view_id, section_xpath, replacement, context=None):
        arch = replacement
        if section_xpath:
            previous_arch = etree.fromstring(self.browse(cr, uid, view_id, context=context).arch.encode('utf-8'))
            # ensure there's only one match
            [previous_section] = previous_arch.xpath(section_xpath)
            previous_section.getparent().replace(previous_section, replacement)
            arch = previous_arch
        return arch

    def save(self, cr, uid, res_id, value, xpath=None, context=None):
        """ Update a view section. The view section may embed fields to write

        :param str model:
        :param int res_id:
        :param str xpath: valid xpath to the tag to replace
        """
        res_id = int(res_id)

        arch_section = html.fromstring(value)

        for el in self.extract_embedded_fields(cr, uid, arch_section, context=context):
            self.save_embedded_field(cr, uid, el, context=context)

            # transform embedded field back to t-field
            el.getparent().replace(el, self.to_field_ref(cr, uid, el, context=context))

        arch = self.replace_arch_section(cr, uid, res_id, xpath, arch_section, context=context)
        self.write(cr, uid, res_id, {
            'arch': etree.tostring(arch, encoding='utf-8').decode('utf-8')
        }, context=context)
