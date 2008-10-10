# -*- coding: iso8859-1 -*-
##############################################################################
#
# Copyright (c) 2004 TINY SPRL. (http://tiny.be) All Rights Reserved.
#                    Fabien Pinckaers <fp@tiny.Be>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

#-------------------------------------------------------------
#ENGLISH
#-------------------------------------------------------------

ones = {
    0: '', 1:'One', 2:'Two', 3:'Three', 4:'Four', 5:'Five', 6:'Six', 7:'Seven', 8:'Eight', 9:'Nine',
    10:'Ten', 11:'Eleven', 12:'Twelve', 13:'Thirteen', 14:'Forteen', 15:'Fifteen', 16:'Sixteen', 17:"Seventeen",18:"Eighteen",19:"Nineteen",
}

tens = {
    1: 'Ten', 2: 'Twenty ', 3:'Thirty', 4:'Forty', 5:'Fifty', 6: 'Sixty', 7 : 'Seventy', 8:'Eighty' ,9: 'Ninety'}

hundred = {
     0:'',1: 'One Hundred', 2: 'Two Hundred', 3: 'Three Hundred', 4 :'Four Hundred', 5: 'Five Hundred', 6: 'Six Hundred', 7 :'Seven Hundred', 8:' Eight Hundred ', 9:'Nine Hundred '
}

thousands ={
     0:'',1: 'One Thousand'
}

lacs = {
     0:'',1: 'Lac'
}

def _100_to_text(number):
    if number in ones:
        return ones[number]
    else:
        if number%10>0:
            return tens[number / 10]+'-'+ones[number % 10]
        else:
            return tens[number / 10]

def _1000_to_text(number):
    d = _100_to_text(number % 100)
    d2 = number/100
    if d2>0 and d:
        return hundred[d2]+' '+d
    elif d2>1 and not(d):
        return hundred[d2]+'s'
    else:
        return hundred[d2] or d

def _10000_to_text(number):
    if number==0:
        return 'zero'
    part1 = _1000_to_text(number % 1000)
    part2 = thousands.get(number / 1000,  _1000_to_text(number / 1000)+' Thousands')
    if part2 and part1:
        part1 = ' '+part1
    return part2+part1

def _1000000_to_text(number):
    if number==0:
        return 'zero'
    part1 = _10000_to_text(number % 100000)
    part2 = lacs.get(number / 100000,  _10000_to_text(number / 100000)+' Lacs')
    if part2 and part1:
        part1 = ' '+part1
    return part2+part1


def amount_to_text(number, currency):
    lacs_number = int(number)
    units_name = currency
    if lacs_number > 1:
        units_name += 's'
    
    lacs = _1000000_to_text(lacs_number)
    lacs = lacs_number and '%s %s' % (lacs, units_name) or ''
    
    units_number = int(number * 10000) % 10000
    units = _10000_to_text(units_number)
    units = units_number and '%s %s' % (units, units_name) or ''
    
    cents_number = int(number * 100) % 100
    cents_name = (cents_number > 1) and 'cents' or 'cent'
    cents = _100_to_text(cents_number)
    cents = cents_number and '%s %s' % (cents, cents_name) or ''
    return lacs


#-------------------------------------------------------------
# Generic functions
#-------------------------------------------------------------

_translate_funcs = {'en' : amount_to_text}
    
#TODO: we should use the country AND language (ex: septante VS soixante dix)
#TODO: we should use en by default, but the translation func is yet to be implemented
def amount_to_text(nbr, lang='en', currency='euro'):
    """
    Converts an integer to its textual representation, using the language set in the context if any.
    Example:
        1654: thousands six cent cinquante-quatre.
    """
    if nbr > 10000000:
#TODO: use logger    
        print "WARNING: number too large '%d', can't translate it!" % (nbr,)
        return str(nbr)
    
    if not _translate_funcs.has_key(lang):
#TODO: use logger    
        print "WARNING: no translation function found for lang: '%s'" % (lang,)
#TODO: (default should be en) same as above
        lang = 'en'
    return _translate_funcs[lang](nbr, currency)

if __name__=='__main__':
    from sys import argv
    
    lang = 'nl'
    if len(argv) < 2:
        for i in range(1,200):
            print i, ">>", int_to_text(i, lang)
        for i in range(200,999999,139):
            print i, ">>", int_to_text(i, lang)
    else:
        print int_to_text(int(argv[1]), lang)

