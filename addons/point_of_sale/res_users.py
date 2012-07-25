#!/usr/bin/env python
from osv import osv, fields
import math

def is_pair(x):
    return not x%2
# This code is a duplicate of product#check_ean function
def check_ean(eancode):
    if not eancode:
        return True
    if len(eancode) <> 13:
        return False
    try:
        int(eancode)
    except:
        return False
    oddsum=0
    evensum=0
    total=0
    eanvalue=eancode
    reversevalue = eanvalue[::-1]
    finalean=reversevalue[1:]

    for i in range(len(finalean)):
        if is_pair(i):
            oddsum += int(finalean[i])
        else:
            evensum += int(finalean[i])
    total=(oddsum * 3) + evensum

    check = int(10 - math.ceil(total % 10.0)) %10

    if check != int(eancode[-1]):
        return False
    return True

class res_users(osv.osv):
    _inherit = 'res.users'
    _columns = {
        'ean13' : fields.char('EAN13', size=13, help="BarCode"),
        'pos_config' : fields.many2one('pos.config', 'Default Point of Sale', domain=[('state', '=', 'active')]),
    }

    def _check_ean(self, cr, uid, ids, context=None):
        return all(
            check_ean(user.ean13) == True
            for user in self.browse(cr, uid, ids, context=context)
        )

    def edit_ean(self, cr, uid, ids, context):
        return {
            'name': "Edit Ean",
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'pos.ean_wizard',
            'target' : 'new',
            'view_id': False,
            'context':context,
        }

    _constraints = [
        (_check_ean, "Error: Invalid ean code", ['ean13'],),
    ]

