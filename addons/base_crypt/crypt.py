from random import seed, sample
from string import letters, digits
from osv import fields,osv
import pooler
import tools
from service import security

magic_md5 = '$1$'

def gen_salt( length=8, symbols=letters + digits ):
    seed()
    return ''.join( sample( symbols, length ) )

import md5

def encrypt_md5( raw_pw, salt, magic=magic_md5 ):
    hash = md5.new( raw_pw + magic + salt )
    stretch = md5.new( raw_pw + salt + raw_pw).digest()

    for i in range( 0, len( raw_pw ) ):
        hash.update( stretch[i % 16] )

    i = len( raw_pw )

    while i:
        if i & 1:
            hash.update('\x00')
        else:
            hash.update( raw_pw[0] )
        i >>= 1

    saltedmd5 = hash.digest()

    for i in range( 1000 ):
        hash = md5.new()

        if i & 1:
            hash.update( raw_pw )
        else:
            hash.update( saltedmd5 )

        if i % 3:
            hash.update( salt )
        if i % 7:
            hash.update( raw_pw )
        if i & 1:
            hash.update( saltedmd5 )
        else:
            hash.update( raw_pw )

        saltedmd5 = hash.digest()

    itoa64 = './0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

    rearranged = ''
    for a, b, c in ((0, 6, 12), (1, 7, 13), (2, 8, 14), (3, 9, 15), (4, 10, 5)):
        v = ord( saltedmd5[a] ) << 16 | ord( saltedmd5[b] ) << 8 | ord( saltedmd5[c] )

        for i in range(4):
            rearranged += itoa64[v & 0x3f]
            v >>= 6

    v = ord( saltedmd5[11] )

    for i in range( 2 ):
        rearranged += itoa64[v & 0x3f]
        v >>= 6

    return magic + salt + '$' + rearranged

_salt_cache = {}

def login(db, login, password):
    cr = pooler.get_db(db).cursor()
    cr.execute( 'select password from res_users where login=%s', (login.encode( 'utf-8' ),) )
    stored_pw = cr.fetchone()

    if stored_pw:
        stored_pw = stored_pw[0]
    else:
        # Return early if no one has a login name like that.
        return False

    # Calculate a new password ('updated_pw') from 'stored_pw' if the
    # latter isn't encrypted yet. Use that to update the database entry.
    # Also update the 'stored_pw' to reflect the change.

    if stored_pw[0:3] != magic_md5:
        updated_pw = encrypt_md5( stored_pw, gen_salt() )
        cr.execute( 'update res_users set password=%s where login=%s', (updated_pw.encode( 'utf-8' ), login.encode( 'utf-8' ),) )
        cr.commit()

        cr.execute( 'select password from res_users where login=%s', (login.encode( 'utf-8' ),) )
        stored_pw = cr.fetchone()[0]

    # Calculate an encrypted password from the user-provided
    # password ('encrypted_pw').

    salt = _salt_cache[password] = stored_pw[3:11]
    encrypted_pw = encrypt_md5( password, salt )

    # Retrieve a user id from the database, factoring in an encrypted
    # password.

    cr.execute('select id from res_users where login=%s and password=%s and active', (login.encode('utf-8'), encrypted_pw.encode('utf-8')))
    res = cr.fetchone()
    cr.close()

    if res:
        return res[0]
    else:
        return False

#def check_super(passwd):
#    salt = _salt_cache[passwd]
#    if encrypt_md5( passwd, salt ) == tools.config['admin_passwd']:
#         return True
#    else:
#         raise Exception('AccessDenied')

def check(db, uid, passwd):
    if security._uid_cache.has_key( uid ) and (security._uid_cache[uid]==passwd):
        return True
    cr = pooler.get_db(db).cursor()
    salt = _salt_cache[passwd]
    cr.execute(' select count(*) from res_users where id=%d and password=%s', (int(uid), encrypt_md5( passwd, salt )) )
    res = cr.fetchone()[0]
    cr.close()
    if not bool(res):
        raise Exception('AccessDenied')
    if res:
        security._uid_cache[uid] = passwd
    return bool(res)


def access(db, uid, passwd, sec_level, ids):
    cr = pooler.get_db(db).cursor()
    salt = _salt_cache[passwd]
    cr.execute('select id from res_users where id=%s and password=%s', (uid, encrypt_md5( passwd, salt )) )
    res = cr.fetchone()
    cr.close()
    if not res:
        raise Exception('Bad username or password')
    return res[0]

# check if module is installed or not
security.login=login
#security.check_super=check_super
security.access=access
security.check=check

class users(osv.osv):
    _name="res.users"
    _inherit="res.users"
    # agi - 022108
    # Add handlers for 'input_pw' field.

    def set_pw( self, cr, uid, id, name, value, args, context ):
        self.write( cr, uid, id, { 'password' : encrypt_md5( value, gen_salt() ) } )
        del value

    def get_pw( self, cr, uid, ids, name, args, context ):
        res = {}
        for id in ids:
            res[id] = ''
        return res

    # Continuing to original code.

    _columns = {
        'input_pw': fields.function( get_pw, fnct_inv=set_pw, type='char', method=True, size=20, string='Password', invisible=True),
            }
users()