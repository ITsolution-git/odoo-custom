##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.     
#
##############################################################################
{
    "name" : "Stock Account",
    "version" : "1.1",
    "author" : "Tiny",
    "website" : "http://tinyerp.com",
    "description" : """This module will support the Anglo-Saxons accounting methodology by 
    changing the accounting logic with stock transactions. The difference between the Anglo-Saxon accounting countries 
    and the Rhine or also called Continental accounting countries is the moment of taking the Cost of Goods Sold versus Cost of Sales. 
    Anglo-Saxons accounting does take the cost when sales invoice is created, Continental accounting will take the cost at he moment the goods are shipped.
    This module will add this functionality by using a interim account, to store the value of shipped goods and will contra book this interim account 
    when the invoice is created to transfer this amount to the debtor or creditor account.""",
    "depends" : ["product", "account", "sale", "purchase"],
    "category" : "Generic Modules/Inventory Control",
    "init_xml" : [],
    "demo_xml" : [],
    "update_xml" : ["product_view.xml",],
    "active": False,
    "installable": True
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: