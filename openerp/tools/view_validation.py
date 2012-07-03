""" View validation code (using assertions, not the RNG schema). """

def valid_page_in_book(arch):
    """A `page` node must be below a `book` node."""
    return not arch.xpath('//page[not(ancestor::notebook)]')

def valid_field_in_graph(arch):
    """A `field` node must be below a `graph` node."""
    return not arch.xpath('//graph[not(field)]')

def valid_field_in_tree(arch):
    """A `field` and `button` node must be below a `tree` node."""
    return not arch.xpath('//tree[not((field) and (button))]')


def valid_att_in_field(arch):
    """A `name` attribute must be in a `field` node."""
    return not arch.xpath('//field[not (@name)]')

def valid_att_in_label(arch):
    """A `for` and `string` attribute must be in a `lable` node."""
    return not arch.xpath('//label[not ((@for) or (@string))]')
    
def valid_att_in_tree(arch):
    """A `string` attribute must be in a `tree` node."""
    return not arch.xpath('//tree[not (@string)]')

def valid_att_in_form(arch):
    """A `string` attribute must be in a `form` node."""
    return not arch.xpath('//form[not (@string)]')

def valid_att_in_graph(arch):
    """A `string` attribute must be in a `graph` node."""
    return not arch.xpath('//graph[not (@string)]')

def valid_type_in_colspan(arch):
    """A `colspan` attribute must be an `integer` type."""
    return arch.xpath('boolean (number (//*/@colspan))')
    
def valid_type_in_col(arch):
    """A `col` attribute must be an `integer` type."""
    return arch.xpath('boolean (number (//*/@col))')
    
def valid_colspan_view(arch):
        for pred in [valid_type_in_colspan]:
            if not pred(arch):
                return False
        return True
        
def valid_col_view(arch):
        for pred in [valid_type_in_col]:
            if not pred(arch):
                return False
        return True

def valid_field_view(arch):
        for pred in [valid_att_in_field]:
            if not pred(arch):
                return False
        return True
    
def valid_label_view(arch):
        for pred in [valid_att_in_label]:
            if not pred(arch):
                return False
        return True

def valid_tree_view(arch):
    if arch.tag == 'tree':
        for pred in [valid_att_in_tree]:
            if not pred(arch):
                return False
    return True

def valid_form_view(arch):
    if arch.tag == 'form':
        for pred in [valid_att_in_form]:
            if not pred(arch):
                return False
    return True

def valid_graph_view(arch):
    if arch.tag == 'graph':
        for pred in [valid_att_in_graph]:
            if not pred(arch):
                return False
    return True

    
def valid_view(arch):
    if arch.tag == 'form':
        for pred in [valid_page_in_book]:
            if not pred(arch):
                return False
    elif arch.tag == 'graph':
        for pred in [valid_field_in_graph]:
            if not pred(arch):
                return False
    elif arch.tag == 'tree':
        for pred in [valid_field_in_tree]:
            if not pred(arch):
                return False
    return True

