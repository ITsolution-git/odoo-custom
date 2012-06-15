{
 'name': 'Reset Password',
 'description': 'Allow users to reset their password from the login page',
 'author': 'OpenERP SA',
 'version': '1.0',
 'category': 'Tools',
 'website': 'http://www.openerp.com',
 'installable': True,
 'depends': ['anonymous', 'email_template'],
 'data': [
    'email_templates.xml',
    'res_users.xml',
 ],
 'js': [
    'static/src/js/reset_password.js',
 ],
 'css': [
     'static/src/css/reset_password.css',
 ],
 'qweb': [
     'static/src/xml/reset_password.xml',
 ],
}
