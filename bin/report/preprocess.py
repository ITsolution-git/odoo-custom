
from lxml import etree
import re
rml_parents = ['tr','story','section']
sxw_parents = ['{http://openoffice.org/2000/table}table-row','{http://openoffice.org/2000/office}body','{http://openoffice.org/2000/text}section']

class report(object):
    def preprocess_rml(self, root_node,type='pdf'):
        _regex1 = re.compile("\[\[(.*?)(repeatIn\(.*?\s*,\s*[\'\"].*?[\'\"]\s*(?:,\s*(.*?)\s*)?\s*\))(.*?)\]\]")
        _regex11= re.compile("\[\[(.*?)(repeatIn\(.*?\s*\(.*?\s*[\'\"].*?[\'\"]\s*\),[\'\"].*?[\'\"](?:,\s*(.*?)\s*)?\s*\))(.*?)\]\]")
        _regex2 = re.compile("\[\[(.*?)(removeParentNode\(\s*(?:['\"](.*?)['\"])\s*\))(.*?)\]\]")
        _regex3 = re.compile("\[\[\s*(.*?setTag\(\s*['\"](.*?)['\"]\s*,\s*['\"].*?['\"]\s*(?:,.*?)?\).*?)\s*\]\]")
        for node in root_node:
            if node.text:
                def _sub3(txt):
                    n = node
                    while n.tag != txt.group(2):
                        n = n.getparent()
                    n.set('rml_tag', txt.group(1))
                    return "[[ '' ]]"
                def _sub2(txt):
                    if txt.group(3):
                        n = node
                        try:
                            while n.tag != txt.group(3):
                                n = n.getparent()
                        except:
                            n = node
                    else:
                        n = node.getparent()
                    n.set('rml_except', txt.group(0)[2:-2])
                    return txt.group(0)
                def _sub1(txt):
                    if len(txt.group(4)) > 1:
                        return []
                    match = rml_parents
                    if type in ['odt','sxw']:
                        match = sxw_parents
                    if txt.group(3):
                        match = [txt.group(3)]
                    n = node
                    while n.tag not in match:
                        n = n.getparent()
                    n.set('rml_loop', txt.group(2))
                    return '[['+txt.group(1)+"''"+txt.group(4)+']]'
                t = _regex1.sub(_sub1, node.text)
                if t == []:
                    t = _regex11.sub(_sub1, node.text)
                t = _regex3.sub(_sub3, t)
                node.text = _regex2.sub(_sub2, t)
            self.preprocess_rml(node,type)
        return root_node

if __name__=='__main__':
    node = etree.XML('''<story>
    <para>This is a test[[ setTag('para','xpre') ]]</para>
    <blockTable>
    <tr>
        <td><para>Row 1 [[ setTag('tr','tr',{'style':'TrLevel'+str(a['level']), 'paraStyle':('Level'+str(a['level']))}) ]] </para></td>
        <td>Row 2 [[ True and removeParentNode('td') ]] </td>
    </tr><tr>
        <td>Row 1 [[repeatIn(o.order_line,'o')]] </td>
        <td>Row 2</td>
    </tr>
    </blockTable>
    <p>This isa test</p>
</story>''')
    a = report()
    result = a.preprocess_rml(node)
    print etree.tostring(result)

