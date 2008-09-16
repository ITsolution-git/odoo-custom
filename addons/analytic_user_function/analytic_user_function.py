# -*- encoding: utf-8 -*-
from osv import fields,osv
from osv import orm

class analytic_user_funct_grid(osv.osv):

    _name="analytic_user_funct_grid"
    _description= "Relation table between users and products on a analytic account"
    _columns={
        'user_id': fields.many2one("res.users","User",required=True,),
        'product_id': fields.many2one("product.product","Product",required=True,),
        'account_id': fields.many2one("account.analytic.account", "Analytic Account",required=True,),
        }

analytic_user_funct_grid()


class account_analytic_account(osv.osv):

    _inherit = "account.analytic.account"
    _columns = {
        'user_product_ids' : fields.one2many('analytic_user_funct_grid', 'account_id', 'Users/Products Rel.'),
    }

account_analytic_account()


class hr_analytic_timesheet(osv.osv):

    _inherit = "hr.analytic.timesheet"


    # Look in account, if no value for the user => look in parent until there is no more parent to look
    # Take the first found... if nothing found => return False
    def _get_related_user_account_recursiv(self,cr,uid,user_id,account_id):
        
        temp=self.pool.get('analytic_user_funct_grid').search(cr, uid, [('user_id', '=', user_id),('account_id', '=', account_id) ])
        account=self.pool.get('account.analytic.account').browse(cr,uid,account_id)
        if temp:
            return temp
        else:
            if account.parent_id:
                return self._get_related_user_account_recursiv(cr,uid,user_id,account.parent_id.id)
            else:
                return False
                
                
    def on_change_account_id(self, cr, uid, ids,user_id, account_id, unit_amount=0):
        #{'value': {'to_invoice': False, 'amount': (-162.0,), 'product_id': 7, 'general_account_id': (5,)}}
        res = {}
        if not (account_id):
            #avoid a useless call to super
            return res 

        if not (user_id):
            return super(hr_analytic_timesheet, self).on_change_account_id(cr, uid, ids,account_id)

        #get the browse record related to user_id and account_id
        temp = self._get_related_user_account_recursiv(cr,uid,user_id,account_id)
        # temp = self.pool.get('analytic_user_funct_grid').search(cr, uid, [('user_id', '=', user_id),('account_id', '=', account_id) ])
        if not temp:
            #if there isn't any record for this user_id and account_id
            return super(hr_analytic_timesheet, self).on_change_account_id(cr, uid, ids,account_id)
        else:
            #get the old values from super and add the value from the new relation analytic_user_funct_grid
            r = self.pool.get('analytic_user_funct_grid').browse(cr, uid, temp)[0]
            res.setdefault('value',{})
            res['value']= super(hr_analytic_timesheet, self).on_change_account_id(cr, uid, ids,account_id)['value']
            res['value']['product_id'] = r.product_id.id
            res['value']['product_uom_id'] = r.product_id.product_tmpl_id.uom_id.id

            #the change of product has to impact the amount, uom and general_account_id
            a = r.product_id.product_tmpl_id.property_account_expense.id
            if not a:
                a = r.product_id.categ_id.property_account_expense_categ.id
            if not a:
                raise osv.except_osv('Error !',
                        'There is no expense account define ' \
                                'for this product: "%s" (id:%d)' % \
                                (r.product_id.name, r.product_id.id,))
            amount = unit_amount * r.product_id.uom_id._compute_price(cr, uid,
                    r.product_id.uom_id.id, r.product_id.standard_price, False)
            res ['value']['amount']= - round(amount, 2)
            res ['value']['general_account_id']= a
        return res

    def on_change_user_id(self, cr, uid, ids,user_id, account_id, unit_amount=0):
        res = {}
        if not (user_id):
            #avoid a useless call to super
            return res 

        #get the old values from super
        res = super(hr_analytic_timesheet, self).on_change_user_id(cr, uid, ids,user_id)

        if account_id:
            #get the browse record related to user_id and account_id
            # temp = self.pool.get('analytic_user_funct_grid').search(cr, uid, [('user_id', '=', user_id),('account_id', '=', account_id) ])
            temp = self._get_related_user_account_recursiv(cr,uid,user_id,account_id)
            if temp:
                #add the value from the new relation analytic_user_funct_grid
                r = self.pool.get('analytic_user_funct_grid').browse(cr, uid, temp)[0]
                res['value']['product_id'] = r.product_id.id    

                #the change of product has to impact the amount, uom and general_account_id
                a = r.product_id.product_tmpl_id.property_account_expense.id
                if not a:
                    a = r.product_id.categ_id.property_account_expense_categ.id
                if not a:
                    raise osv.except_osv('Error !',
                            'There is no expense account define ' \
                                    'for this product: "%s" (id:%d)' % \
                                    (r.product_id.name, r.product_id.id,))
                amount = unit_amount * r.product_id.uom_id._compute_price(cr, uid,
                        r.product_id.uom_id.id, r.product_id.standard_price, False)
                res ['value']['amount']= - round(amount, 2)
                res ['value']['general_account_id']= a
        return res

hr_analytic_timesheet()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

