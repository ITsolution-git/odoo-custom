import cgi
import logging
import re
import types

#from openerp.tools.safe_eval import safe_eval as eval

import xml   # FIXME use lxml
import xml.dom.minidom
import traceback
from openerp.osv import osv, orm

_logger = logging.getLogger(__name__)

BUILTINS = {
    'False': False,
    'None': None,
    'True': True,
    'abs': abs,
    'bool': bool,
    'dict': dict,
    'filter': filter,
    'len': len,
    'list': list,
    'map': map,
    'max': max,
    'min': min,
    'reduce': reduce,
    'repr': repr,
    'round': round,
    'set': set,
    'str': str,
    'tuple': tuple,
}

class QWebContext(dict):
    def __init__(self, data, undefined_handler=None):
        self.undefined_handler = undefined_handler
        dic = BUILTINS.copy()
        dic.update(data)
        dict.__init__(self, dic)
        self['defined'] = lambda key: key in self

    def __getitem__(self, key):
        if key in self:
            return self.get(key)
        elif not self.undefined_handler:
            raise NameError("QWeb: name %r is not defined while rendering template %r" % (key, self.get('__template__')))
        else:
            return self.get(key, self.undefined_handler(key, self))

class QWebXml(object):
    """QWeb Xml templating engine

    The templating engine use a very simple syntax, "magic" xml attributes, to
    produce any kind of texutal output (even non-xml).

    QWebXml:
        the template engine core implements the basic magic attributes:

        t-att t-raw t-esc t-if t-foreach t-set t-call t-trim


    - loader: function that return a template


    """
    def __init__(self, loader=None, undefined_handler=None):
        self.loader = loader
        self.undefined_handler = undefined_handler
        self.node = xml.dom.Node
        self._t = {}
        self._render_tag = {}
        self._format_regex = re.compile('#\{(.*?)\}')
        self._void_elements = set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'keygen',
                                  'link', 'menuitem', 'meta', 'param', 'source', 'track', 'wbr'])
        prefix = 'render_tag_'
        for i in [j for j in dir(self) if j.startswith(prefix)]:
            name = i[len(prefix):].replace('_', '-')
            self._render_tag[name] = getattr(self.__class__, i)

        self._render_att = {}
        prefix = 'render_att_'
        for i in [j for j in dir(self) if j.startswith(prefix)]:
            name = i[len(prefix):].replace('_', '-')
            self._render_att[name] = getattr(self.__class__, i)

    def register_tag(self, tag, func):
        self._render_tag[tag] = func

    def add_template(self, x):
        if hasattr(x, 'documentElement'):
            dom = x
        elif x.startswith("<?xml"):
            dom = xml.dom.minidom.parseString(x)
        else:
            dom = xml.dom.minidom.parse(x)
        for n in dom.documentElement.childNodes:
            if n.nodeType == 1 and n.getAttribute('t-name'):
                self._t[str(n.getAttribute("t-name"))] = n

    def get_template(self, name):
        if name in self._t:
            return self._t[name]
        elif self.loader:
            xml = self.loader(name)
            self.add_template(xml)
            if name in self._t:
                return self._t[name]
        raise KeyError('qweb: template "%s" not found' % name)

    def eval(self, expr, v):
        try:
            return eval(expr, None, v)
        except (osv.except_osv, orm.except_orm), err:
            raise orm.except_orm("QWeb Error", "Invalid expression %r while rendering template '%s'.\n\n%s" % (expr, v.get('__template__'), err[1]))
        except Exception:
            raise SyntaxError("QWeb: invalid expression %r while rendering template '%s'.\n\n%s" % (expr, v.get('__template__'), traceback.format_exc()))

    def eval_object(self, expr, v):
        return self.eval(expr, v)

    def eval_str(self, expr, v):
        if expr == "0":
            return v.get(0, '')
        val = self.eval(expr, v)
        if isinstance(val, unicode):
            return val.encode("utf8")
        return str(val)

    def eval_format(self, expr, v):
        use_native = True
        for m in self._format_regex.finditer(expr):
            use_native = False
            expr = expr.replace(m.group(), self.eval_str(m.groups()[0], v))
        if not use_native:
            return expr
        else:
            try:
                return str(expr % v)
            except:
                raise Exception("QWeb: format error '%s' " % expr)

    def eval_bool(self, expr, v):
        val = self.eval(expr, v)
        if val:
            return 1
        else:
            return 0

    def render(self, tname, v=None, out=None):
        if v is None:
            v = {}
        v['__template__'] = tname
        stack = v.get('__stack__', [])
        if stack:
            v['__caller__'] = stack[-1]
        stack.append(tname)
        v['__stack__'] = stack
        v = QWebContext(v, self.undefined_handler)
        return self.render_node(self.get_template(tname), v)

    def render_node(self, e, v):
        r = ""
        if e.nodeType == self.node.TEXT_NODE or e.nodeType == self.node.CDATA_SECTION_NODE:
            r = e.data.encode("utf8")
        elif e.nodeType == self.node.ELEMENT_NODE:
            g_att = ""
            t_render = None
            t_att = {}
            for (an, av) in e.attributes.items():
                an = str(an)
                if isinstance(av, types.UnicodeType):
                    av = av.encode("utf8")
                else:
                    av = av.nodeValue.encode("utf8")
                if an.startswith("t-"):
                    for i in self._render_att:
                        if an[2:].startswith(i):
                            g_att += self._render_att[i](self, e, an, av, v)
                            break
                    else:
                        if an[2:] in self._render_tag:
                            t_render = an[2:]
                        t_att[an[2:]] = av
                else:
                    g_att += ' %s="%s"' % (an, cgi.escape(av, 1))
            if t_render:
                if t_render in self._render_tag:
                    r = self._render_tag[t_render](self, e, t_att, g_att, v)
            else:
                r = self.render_element(e, t_att, g_att, v)
        return r

    def render_element(self, e, t_att, g_att, v, inner=None):
        # e: element
        # t_att: t-* attributes
        # g_att: generated attributes
        # v: values
        # inner: optional innerXml
        if inner:
            g_inner = inner
        else:
            g_inner = []
            for n in e.childNodes:
                g_inner.append(self.render_node(n, v))
        name = str(e.nodeName)
        inner = "".join(g_inner)
        trim = t_att.get("trim", 0)
        if trim == 0:
            pass
        elif trim == 'left':
            inner = inner.lstrip()
        elif trim == 'right':
            inner = inner.rstrip()
        elif trim == 'both':
            inner = inner.strip()
        if name == "t":
            return inner
        elif len(inner) or name not in self._void_elements:
            return "<%s%s>%s</%s>" % (name, g_att, inner, name)
        else:
            return "<%s%s/>" % (name, g_att)

    # Attributes
    def render_att_att(self, e, an, av, v):
        if an.startswith("t-attf-"):
            att, val = an[7:], self.eval_format(av, v)
        elif an.startswith("t-att-"):
            att, val = an[6:], self.eval_str(av, v)
        else:
            att, val = self.eval_object(av, v)
        return ' %s="%s"' % (att, cgi.escape(val, 1))

    # Tags
    def render_tag_raw(self, e, t_att, g_att, v):
        inner = self.eval_str(t_att["raw"], v)
        return self.render_element(e, t_att, g_att, v, inner)

    def render_tag_rawf(self, e, t_att, g_att, v):
        inner = self.eval_format(t_att["rawf"], v)
        return self.render_element(e, t_att, g_att, v, inner)

    def render_tag_esc(self, e, t_att, g_att, v):
        inner = cgi.escape(self.eval_str(t_att["esc"], v))
        return self.render_element(e, t_att, g_att, v, inner)

    def render_tag_escf(self, e, t_att, g_att, v):
        inner = cgi.escape(self.eval_format(t_att["escf"], v))
        return self.render_element(e, t_att, g_att, v, inner)

    def render_tag_foreach(self, e, t_att, g_att, v):
        expr = t_att["foreach"]
        enum = self.eval_object(expr, v)
        if enum is not None:
            var = t_att.get('as', expr).replace('.', '_')
            d = QWebContext(v.copy(), self.undefined_handler)
            size = -1
            if isinstance(enum, types.ListType):
                size = len(enum)
            elif isinstance(enum, types.TupleType):
                size = len(enum)
            elif hasattr(enum, 'count'):
                size = enum.count()
            d["%s_size" % var] = size
            d["%s_all" % var] = enum
            index = 0
            ru = []
            for i in enum:
                d["%s_value" % var] = i
                d["%s_index" % var] = index
                d["%s_first" % var] = index == 0
                d["%s_even" % var] = index % 2
                d["%s_odd" % var] = (index + 1) % 2
                d["%s_last" % var] = index + 1 == size
                if index % 2:
                    d["%s_parity" % var] = 'odd'
                else:
                    d["%s_parity" % var] = 'even'
                if isinstance(i, types.DictType):
                    d.update(i)
                else:
                    d[var] = i
                ru.append(self.render_element(e, t_att, g_att, d))
                index += 1
            return "".join(ru)
        else:
            return "qweb: t-foreach %s not found." % expr

    def render_tag_if(self, e, t_att, g_att, v):
        if self.eval_bool(t_att["if"], v):
            return self.render_element(e, t_att, g_att, v)
        else:
            return ""

    def render_tag_call(self, e, t_att, g_att, v):
        if "import" in t_att:
            d = v
        else:
            d = QWebContext(v.copy(), self.undefined_handler)
        d[0] = self.render_element(e, t_att, g_att, d)
        return self.render(t_att["call"], d)

    def render_tag_set(self, e, t_att, g_att, v):
        if "value" in t_att:
            v[t_att["set"]] = self.eval_object(t_att["value"], v)
        elif "valuef" in t_att:
            v[t_att["set"]] = self.eval_format(t_att["valuef"], v)
        else:
            v[t_att["set"]] = self.render_element(e, t_att, g_att, v)
        return ""

    def render_tag_field(self, e, t_att, g_att, v):
        """ eg: <span t-record="browse_record(res.partner, 1)" t-field="phone">+1 555 555 8069</span>"""

        record, field = t_att["field"].rsplit('.', 1)
        record = self.eval_object(record, v)

        inner = ""
        field_type = record._model._all_columns.get(field).column._type
        try:
            if field_type == 'many2one':
                field_data = record.read([field])[0].get(field)
                inner = field_data and field_data[1] or ""
            else:
                inner = getattr(record, field) or ""
            if isinstance(inner, types.UnicodeType):
                inner = inner.encode("utf8")
            if field_type != 'html':
                cgi.escape(str(inner))
            if e.tagName != 't':
                g_att += ''.join(
                    ' %s="%s"' % (name, cgi.escape(str(value), True))
                    for name, value in [
                        ('data-oe-model', record._model._name),
                        ('data-oe-id', str(record.id)),
                        ('data-oe-field', field),
                        ('data-oe-type', field_type),
                    ]
                )
        except AttributeError:
            _logger.warning("t-field no field %s for model %s", field, record._model._name)

        return self.render_element(e, t_att, g_att, v, str(inner))

    def render_tag_debug(self, e, t_att, g_att, v):
        debugger = t_att.get('debug', 'pdb')
        __import__(debugger).set_trace() # pdb, ipdb, pudb, ...
        return self.render_element(e, t_att, g_att, v)

# leave this, al.
