from osv import osv, fields
from html2text import html2text
import re
import smtplib
import base64
from email import Encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import decode_header, Header
from email.utils import formatdate
import re
import netsvc
import string
import email
import time, datetime
import email_template_engines
from tools.translate import _
import tools

class email_template_account(osv.osv):
    """
    Object to store email account settings
    """
    _name = "email_template.account"
    _known_content_types = ['multipart/mixed',
                            'multipart/alternative',
                            'multipart/related',
                            'text/plain',
                            'text/html'
                            ]
    _columns = {
        'name': fields.char('Description',
                        size=64, required=True,
                        readonly=True, select=True,
                        states={'draft':[('readonly', False)]}),
        'user':fields.many2one('res.users',
                        'Related User', required=True,
                        readonly=True, states={'draft':[('readonly', False)]}),
        'email_id': fields.char('Email ID',
                        size=120, required=True,
                        readonly=True, states={'draft':[('readonly', False)]} ,
                        help=" eg:yourname@yourdomain.com "),
        'smtpserver': fields.char('Server',
                        size=120, required=True,
                        readonly=True, states={'draft':[('readonly', False)]},
                        help="Enter name of outgoing server,eg:smtp.gmail.com "),
        'smtpport': fields.integer('SMTP Port ',
                        size=64, required=True,
                        readonly=True, states={'draft':[('readonly', False)]},
                        help="Enter port number,eg:SMTP-587 "),
        'smtpuname': fields.char('User Name',
                        size=120, required=False,
                        readonly=True, states={'draft':[('readonly', False)]}),
        'smtppass': fields.char('Password',
                        size=120, invisible=True,
                        required=False, readonly=True,
                        states={'draft':[('readonly', False)]}),
        'smtptls':fields.boolean('TLS',
                        states={'draft':[('readonly', False)]}, readonly=True),
                                
        'smtpssl':fields.boolean('SSL/TLS (only in python 2.6)',
                        states={'draft':[('readonly', False)]}, readonly=True),
        'send_pref':fields.selection([
                                      ('html', 'HTML otherwise Text'),
                                      ('text', 'Text otherwise HTML'),
                                      ('both', 'Both HTML & Text')
                                      ], 'Mail Format', required=True),
        'company':fields.selection([
                        ('yes', 'Yes'),
                        ('no', 'No')
                        ], 'Company Mail A/c',
                        readonly=True,
                        help="Select if this mail account does not belong" \
                        "to specific user but the organisation as a whole." \
                        "eg:info@somedomain.com",
                        required=True, states={
                                           'draft':[('readonly', False)]
                                           }),

        'state':fields.selection([
                                  ('draft', 'Initiated'),
                                  ('suspended', 'Suspended'),
                                  ('approved', 'Approved')
                                  ],
                        'Status', required=True, readonly=True),
    }

    _defaults = {
         'name':lambda self, cursor, user, context:self.pool.get(
                                                'res.users'
                                                ).read(
                                                        cursor,
                                                        user,
                                                        user,
                                                        ['name'],
                                                        context
                                                        )['name'],
         'state':lambda * a:'draft',
         'user':lambda self, cursor, user, context:user,
         'send_pref':lambda * a: 'html',
         'smtptls':lambda * a:True,
     }
    
    _sql_constraints = [
        (
         'email_uniq',
         'unique (email_id)',
         'Another setting already exists with this email ID !')
    ]
    
    def _constraint_unique(self, cursor, user, ids):
        """
        This makes sure that you dont give personal 
        users two accounts with same ID (Validated in sql constaints)
        However this constraint exempts company accounts. 
        Any no of co accounts for a user is allowed
        """
        if self.read(cursor, user, ids, ['company'])[0]['company'] == 'no':
            accounts = self.search(cursor, user, [
                                                 ('user', '=', user),
                                                 ('company', '=', 'no')
                                                 ])
            if len(accounts) > 1 :
                return False
            else :
                return True
        else:
            return True
        
    _constraints = [
        (_constraint_unique,
         'Error: You are not allowed to have more than 1 account.',
         [])
    ]
    
    def on_change_emailid(self, cursor, user, ids, name=None, email_id=None, context=None):
        """
        Called when the email ID field changes.
        
        UI enhancement
        Writes the same email value to the smtpusername
        and incoming username
        """
        #TODO: Check and remove the write. Is it needed?
        self.write(cursor, user, ids, {'state':'draft'}, context=context)
        return {
                'value': {
                          'state': 'draft',
                          'smtpuname':email_id,
                          'isuser':email_id
                          }
                }
    
    def get_outgoing_server(self, cursor, user, ids, context=None):
        """
        Returns the Out Going Connection (SMTP) object
        
        @attention: DO NOT USE except_osv IN THIS METHOD
        @param cursor: Database Cursor
        @param user: ID of current user
        @param ids: ID/list of ids of current object for 
                    which connection is required
                    First ID will be chosen from lists
        @param context: Context
        
        @return: SMTP server object or Exception
        """
        #Type cast ids to integer
        if type(ids) == list:
            ids = ids[0]
        this_object = self.browse(cursor, user, ids, context)
        if this_object:
            if this_object.smtpserver and this_object.smtpport: 
                try:
                    if this_object.smtpssl:
                        serv = smtplib.SMTP_SSL(this_object.smtpserver, this_object.smtpport)
                    else:
                        serv = smtplib.SMTP(this_object.smtpserver, this_object.smtpport)
                    if this_object.smtptls:
                        serv.ehlo()
                        serv.starttls()
                        serv.ehlo()
                except Exception, error:
                    raise error
                try:
                    if serv.has_extn('AUTH') or this_object.smtpuname or this_object.smtppass:
                        serv.login(this_object.smtpuname, this_object.smtppass)
                except Exception, error:
                    raise error
                return serv
            raise Exception(_("SMTP SERVER or PORT not specified"))
        raise Exception(_("Core connection for the given ID does not exist"))
    
    def check_outgoing_connection(self, cursor, user, ids, context=None):
        """
        checks SMTP credentials and confirms if outgoing connection works
        (Attached to button)
        @param cursor: Database Cursor
        @param user: ID of current user
        @param ids: list of ids of current object for 
                    which connection is required
        @param context: Context
        """
        try:
            self.get_outgoing_server(cursor, user, ids, context)
            raise osv.except_osv(_("SMTP Test Connection Was Successful"), '')
        except osv.except_osv, success_message:
            raise success_message
        except Exception, error:
            raise osv.except_osv(
                                 _("Out going connection test failed"),
                                 _("Reason: %s") % error
                                 )
    
    def do_approval(self, cr, uid, ids, context={}):
        #TODO: Check if user has rights
        self.write(cr, uid, ids, {'state':'approved'}, context=context)
#        wf_service = netsvc.LocalService("workflow")

    def smtp_connection(self, cursor, user, id, context=None):
        """
        This method should now wrap smtp_connection
        """
        #This function returns a SMTP server object
        logger = netsvc.Logger()
        core_obj = self.browse(cursor, user, id, context)
        if core_obj.smtpserver and core_obj.smtpport and core_obj.state == 'approved':
            try:
                serv = self.get_outgoing_server(cursor, user, id, context)
            except Exception, error:
                logger.notifyChannel(_("Email Template"), netsvc.LOG_ERROR, _("Mail from Account %s failed on login. Probable Reason:Could not login to server\nError: %s") % (id, error))
                return False
            #Everything is complete, now return the connection
            return serv
        else:
            logger.notifyChannel(_("Email Template"), netsvc.LOG_ERROR, _("Mail from Account %s failed. Probable Reason:Account not approved") % id)
            return False
                      
#**************************** MAIL SENDING FEATURES ***********************#
    def split_to_ids(self, ids_as_str):
        """
        Identifies email IDs separated by separators
        and returns a list
        TODO: Doc this
        "a@b.com,c@bcom; d@b.com;e@b.com->['a@b.com',...]"
        """
        email_sep_by_commas = ids_as_str \
                                    .replace('; ', ',') \
                                    .replace(';', ',') \
                                    .replace(', ', ',')
        return email_sep_by_commas.split(',')
    
    def get_ids_from_dict(self, addresses={}):
        """
        TODO: Doc this
        """
        result = {'all':[]}
        keys = ['To', 'CC', 'BCC']
        for each in keys:
            ids_as_list = self.split_to_ids(addresses.get(each, u''))
            while u'' in ids_as_list:
                ids_as_list.remove(u'')
            result[each] = ids_as_list
            result['all'].extend(ids_as_list)
        return result
    
    def send_mail(self, cr, uid, ids, addresses, subject='', body=None, payload=None, context=None):
        #TODO: Replace all this with a single email object
        if body is None:
            body = {}
        if payload is None:
            payload = {}
        if context is None:
            context = {}
        logger = netsvc.Logger()
        for id in ids:  
            core_obj = self.browse(cr, uid, id, context)
            serv = self.smtp_connection(cr, uid, id)
            if serv:
                try:
                    msg = MIMEMultipart()
                    if subject:
                        msg['Subject'] = subject
                    sender_name = Header(core_obj.name, 'utf-8').encode()
                    msg['From'] = sender_name + " <" + core_obj.email_id + ">"
                    msg['Organization'] = tools.ustr(core_obj.user.company_id.name)
                    msg['Date'] = formatdate()
                    addresses_l = self.get_ids_from_dict(addresses) 
                    if addresses_l['To']:
                        msg['To'] = u','.join(addresses_l['To'])
                    if addresses_l['CC']:
                        msg['CC'] = u','.join(addresses_l['CC'])
#                    if addresses_l['BCC']:
#                        msg['BCC'] = u','.join(addresses_l['BCC'])
                    if body.get('text', False):
                        temp_body_text = body.get('text', '')
                        l = len(temp_body_text.replace(' ', '').replace('\r', '').replace('\n', ''))
                        if l == 0:
                            body['text'] = u'No Mail Message'
                    # Attach parts into message container.
                    # According to RFC 2046, the last part of a multipart message, in this case
                    # the HTML message, is best and preferred.
                    if core_obj.send_pref == 'text' or core_obj.send_pref == 'both':
                        body_text = body.get('text', u'No Mail Message')
                        body_text = tools.ustr(body_text)
                        msg.attach(MIMEText(body_text.encode("utf-8"), _charset='UTF-8'))
                    if core_obj.send_pref == 'html' or core_obj.send_pref == 'both':
                        html_body = body.get('html', u'')
                        if len(html_body) == 0 or html_body == u'':
                            html_body = body.get('text', u'<p>No Mail Message</p>').replace('\n', '<br/>').replace('\r', '<br/>')
                        html_body = tools.ustr(html_body)
                        msg.attach(MIMEText(html_body.encode("utf-8"), _subtype='html', _charset='UTF-8'))
                    #Now add attachments if any
                    for file in payload.keys():
                        part = MIMEBase('application', "octet-stream")
                        part.set_payload(base64.decodestring(payload[file]))
                        part.add_header('Content-Disposition', 'attachment; filename="%s"' % file)
                        Encoders.encode_base64(part)
                        msg.attach(part)
                except Exception, error:
                    logger.notifyChannel(_("Email Template"), netsvc.LOG_ERROR, _("Mail from Account %s failed. Probable Reason:MIME Error\nDescription: %s") % (id, error))
                    return {'error_msg': "Server Send Error\nDescription: %s"%error}
                try:
                    #print msg['From'],toadds
                    serv.sendmail(msg['From'], addresses_l['all'], msg.as_string())
                except Exception, error:
                    logger.notifyChannel(_("Email Template"), netsvc.LOG_ERROR, _("Mail from Account %s failed. Probable Reason:Server Send Error\nDescription: %s") % (id, error))
                    return {'error_msg': "Server Send Error\nDescription: %s"%error}
                #The mail sending is complete
                serv.close()
                logger.notifyChannel(_("Email Template"), netsvc.LOG_INFO, _("Mail from Account %s successfully Sent.") % (id))
                return True
            else:
                logger.notifyChannel(_("Email Template"), netsvc.LOG_ERROR, _("Mail from Account %s failed. Probable Reason:Account not approved") % id)
                return {'error_msg':"Mail from Account %s failed. Probable Reason:Account not approved"% id}
                                
    def extracttime(self, time_as_string):
        """
        TODO: DOC THis
        """
        logger = netsvc.Logger()
        #The standard email dates are of format similar to:
        #Thu, 8 Oct 2009 09:35:42 +0200
        #print time_as_string
        date_as_date = False
        convertor = {'+':1, '-':-1}
        try:
            time_as_string = time_as_string.replace(',', '')
            date_list = time_as_string.split(' ')
            date_temp_str = ' '.join(date_list[1:5])
            if len(date_list) >= 6:
                sign = convertor.get(date_list[5][0], False)
            else:
                sign = False
            try:
                dt = datetime.datetime.strptime(
                                            date_temp_str,
                                            "%d %b %Y %H:%M:%S")
            except:
                try:
                    dt = datetime.datetime.strptime(
                                            date_temp_str,
                                            "%d %b %Y %H:%M")
                except:
                    return False
            if sign:
                try:
                    offset = datetime.timedelta(
                                hours=sign * int(
                                             date_list[5][1:3]
                                                ),
                                             minutes=sign * int(
                                                            date_list[5][3:5]
                                                                )
                                                )
                except Exception, e2:
                    """Looks like UT or GMT, just forget decoding"""
                    return False
            else:
                offset = datetime.timedelta(hours=0)
            dt = dt + offset
            date_as_date = dt.strftime('%Y-%m-%d %H:%M:%S')
            #print date_as_date
        except Exception, e:
            logger.notifyChannel(
                    _("Email Template"),
                    netsvc.LOG_WARNING,
                    _(
                      "Datetime Extraction failed.Date:%s \
                      \tError:%s") % (
                                    time_as_string,
                                    e)
                      )
        return date_as_date
        
    def send_receive(self, cr, uid, ids, context=None):
        for id in ids:
            ctx = context.copy()
            ctx['filters'] = [('account_id', '=', id)]
            self.pool.get('email_template.mailbox').send_all_mail(cr, uid, [], context=ctx)
        return True
 
    def decode_header_text(self, text):
        """ Decode internationalized headers RFC2822.
            To, CC, BCC, Subject fields can contain 
            text slices with different encodes, like:
                =?iso-8859-1?Q?Enric_Mart=ED?= <enricmarti@company.com>, 
                =?Windows-1252?Q?David_G=F3mez?= <david@company.com>
            Sometimes they include extra " character at the beginning/
            end of the contact name, like:
                "=?iso-8859-1?Q?Enric_Mart=ED?=" <enricmarti@company.com>
            and decode_header() does not work well, so we use regular 
            expressions (?=   ? ?   ?=) to split the text slices
        """
        if not text:
            return text        
        p = re.compile("(=\?.*?\?.\?.*?\?=)")
        text2 = ''
        try:
            for t2 in p.split(text):
                text2 += ''.join(
                            [s.decode(
                                      t or 'ascii'
                                    ) for (s, t) in decode_header(t2)]
                                ).encode('utf-8')
        except:
            return text
        return text2

email_template_account()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
