# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (C) Stephane Wirtel
# Copyright (C) 2011 Nicolas Vanhoren
# Copyright (C) 2011 OpenERP s.a. (<http://openerp.com>).
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the <organization> nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
##############################################################################

"""
OpenERP Client Library
"""

import xmlrpclib
import logging 
import socket

try:
    import cPickle as pickle
    pickle.__name__
except:
    import pickle

try:
    import cStringIO as StringIO
    StringIO.__name__
except:
    import StringIO

_logger = logging.getLogger(__name__)

def _getChildLogger(logger, subname):
    return logging.getLogger(logger.name + "." + subname)

class Connector(object):
    """
    The base abstract class representing a connection to an OpenERP Server.
    """

    __logger = _getChildLogger(_logger, 'connector')

    def __init__(self, hostname, port):
        """
        Initilize by specifying an hostname and a port.
        :param hostname: Host name of the server.
        :param port: Port for the connection to the server.
        """
        self.hostname = hostname
        self.port = port

class XmlRPCConnector(Connector):
    """
    A type of connector that uses the XMLRPC protocol.
    """
    PROTOCOL = 'xmlrpc'
    
    __logger = _getChildLogger(_logger, 'connector.xmlrpc')

    def __init__(self, hostname, port=8069):
        """
        Initialize by specifying the hostname and the port.
        :param hostname: The hostname of the computer holding the instance of OpenERP.
        :param port: The port used by the OpenERP instance for XMLRPC (default to 8069).
        """
        Connector.__init__(self, hostname, port)
        self.url = 'http://%s:%d/xmlrpc' % (self.hostname, self.port)

    def send(self, service_name, method, *args):
        url = '%s/%s' % (self.url, service_name)
        service = xmlrpclib.ServerProxy(url)
        return getattr(service, method)(*args)

class NetRPC_Exception(Exception):
    """
    Exception for NetRPC errors.
    """
    def __init__(self, faultCode, faultString):
        self.faultCode = faultCode
        self.faultString = faultString
        self.args = (faultCode, faultString)

class NetRPC:
    """
    Low level class for NetRPC protocol.
    """
    def __init__(self, sock=None):
        if sock is None:
            self.sock = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock
        self.sock.settimeout(120)
    def connect(self, host, port=False):
        if not port:
            buf = host.split('//')[1]
            host, port = buf.split(':')
        self.sock.connect((host, int(port)))

    def disconnect(self):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()

    def mysend(self, msg, exception=False, traceback=None):
        msg = pickle.dumps([msg,traceback])
        size = len(msg)
        self.sock.send('%8d' % size)
        self.sock.send(exception and "1" or "0")
        totalsent = 0
        while totalsent < size:
            sent = self.sock.send(msg[totalsent:])
            if sent == 0:
                raise RuntimeError, "socket connection broken"
            totalsent = totalsent + sent

    def myreceive(self):
        buf=''
        while len(buf) < 8:
            chunk = self.sock.recv(8 - len(buf))
            if chunk == '':
                raise RuntimeError, "socket connection broken"
            buf += chunk
        size = int(buf)
        buf = self.sock.recv(1)
        if buf != "0":
            exception = buf
        else:
            exception = False
        msg = ''
        while len(msg) < size:
            chunk = self.sock.recv(size-len(msg))
            if chunk == '':
                raise RuntimeError, "socket connection broken"
            msg = msg + chunk
        msgio = StringIO.StringIO(msg)
        unpickler = pickle.Unpickler(msgio)
        unpickler.find_global = None
        res = unpickler.load()

        if isinstance(res[0],Exception):
            if exception:
                raise NetRPC_Exception(str(res[0]), str(res[1]))
            raise res[0]
        else:
            return res[0]

class NetRPCConnector(Connector):
    """
    A type of connector that uses the NetRPC protocol.
    """

    PROTOCOL = 'netrpc'
    
    __logger = _getChildLogger(_logger, 'connector.netrpc')

    def __init__(self, hostname, port=8070):
        """
        Initialize by specifying the hostname and the port.
        :param hostname: The hostname of the computer holding the instance of OpenERP.
        :param port: The port used by the OpenERP instance for NetRPC (default to 8070).
        """
        Connector.__init__(self, hostname, port)

    def send(self, service_name, method, *args):
        socket = NetRPC()
        socket.connect(self.hostname, self.port)
        socket.mysend((service_name, method, )+args)
        result = socket.myreceive()
        socket.disconnect()
        return result

class Service:
    """
    A class to execute RPC calls on a specific service of the remote server.
    """
    def __init__(self, connector, service_name):
        """
        :param connector: A valid Connector instance.
        :param service_name: The name of the service on the remote server.
        """
        self.connector = connector
        self.service_name = service_name
        self.__logger = _getChildLogger(_getChildLogger(_logger, 'service'),service_name)
        
    def __getattr__(self, method):
        """
        :param method: The name of the method to execute on the service.
        """
        self.__logger.debug('method: %r', method)
        def proxy(*args):
            """
            :param args: A list of values for the method
            """
            self.__logger.debug('args: %r', args)
            result = self.connector.send(self.service_name, method, *args)
            self.__logger.debug('result: %r' % result)
            return result
        return proxy

class Connection(object):
    """
    A class to represent a connection with authentification to an OpenERP Server.
    It also provides utility methods to interact with the server more easily.
    """
    __logger = _getChildLogger(_logger, 'connection')

    def __init__(self, connector,
                 database=None,
                 login=None,
                 password=None,
                 user_id=None):
        """
        Initialize with login information. The login information is facultative to allow specifying
        it after the initialization of this object.

        :param connector: A valid Connector instance to send messages to the remote server.
        :param database: The name of the database to work on.
        :param login: The login of the user.
        :param password: The password of the user.
        :param user_id: The user id is a number identifying the user. This is only useful if you
        already know it, in most cases you don't need to specify it.
        """
        self.connector = connector

        self.set_login_info(database, login, password, user_id)

    def set_login_info(self, database, login, password, user_id=None):
        """
        Set login information after the initialisation of this object.

        :param connector: A valid Connector instance to send messages to the remote server.
        :param database: The name of the database to work on.
        :param login: The login of the user.
        :param password: The password of the user.
        :param user_id: The user id is a number identifying the user. This is only useful if you
        already know it, in most cases you don't need to specify it.
        """
        self.database, self.login, self.password = database, login, password

        self.user_id = user_id
        
    def check_login(self, force=True):
        """
        Checks that the login information is valid. Throws an AuthentificationError if the
        authentification fails.

        :param force: Force to re-check even if this Connection was already validated previously.
        Default to True.
        """
        if self.user_id and not force:
            return
        
        self.user_id = self.get_service("common").login(self.database, self.login, self.password)
        if not self.user_id:
            raise AuthentificationError("Authentification failure")
        self.__logger.debug("Authentified with user id %s" % self.user_id)
    
    """
    Returns a Model instance to allow easy remote manipulation of an OpenERP model.
    
    :param model_name: The name of the model.
    """
    def get_model(self, model_name):
        return Model(self, model_name)

    """
    Returns a Service instance to allow easy manipulation of one of the services offered by the remote server.
    Please note this Connection instance does not need to have valid authenfication information since authentification
    is only necessary for the "object" service that handles models.

    :param service_name: The name of the service.
    """
    def get_service(self, service_name):
        return Service(self.connector, service_name)

class AuthentificationError(Exception):
    """
    An error thrown when an authentification to an OpenERP server failed.
    """
    pass

class Model(object):
    """
    Useful class to dialog with one of the models provided by an OpenERP server.
    An instance of this class depends on a Connection instance with valid authenfication information.
    """

    def __init__(self, connection, model_name):
        """
        :param connection: A valid Connection instance with correct authentification information.
        :param model_name: The name of the model.
        """
        self.connection = connection
        self.model_name = model_name
        self.__logger = _getChildLogger(_getChildLogger(_logger, 'object'), model_name)

    def __getattr__(self, method):
        """
        Provides proxy methods that will forward calls to the model on the remote OpenERP server.

        :param method: The method for the linked model (search, read, write, unlink, create, ...)
        """
        def proxy(*args):
            """
            :param args: A list of values for the method
            """
            self.connection.check_login(False)
            self.__logger.debug(args)
            result = self.connection.get_service('object').execute(
                                                    self.connection.database,
                                                    self.connection.user_id,
                                                    self.connection.password,
                                                    self.model_name,
                                                    method,
                                                    *args)
            if method == "read":
                if isinstance(result, list) and len(result) > 0 and "id" in result[0]:
                    index = {}
                    for i in xrange(len(result)):
                        index[result[i]["id"]] = result[i]
                    result = [index[x] for x in args[0]]
            self.__logger.debug('result: %r' % result)
            return result
        return proxy

    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, context=None):
        """
        A shortcut method to combine a search() and a read().

        :param domain: The domain for the search.
        :param fields: The fields to extract (can be None or [] to extract all fields).
        :param offset: The offset for the rows to read.
        :param limit: The maximum number of rows to read.
        :param order: The order to class the rows.
        :param context: The context.
        :return: A list of dictionaries containing all the specified fields.
        """
        record_ids = self.search(domain or [], offset, limit or False, order or False, context or {})
        records = self.read(record_ids, fields or [], context or {})
        return records

def get_connector(hostname, protocol="xmlrpc", port="auto"):
    """
    A shortcut method to easily create a connector to a remote server using XMLRPC or NetRPC.

    :param hostname: The hostname to the remote server.
    :param protocol: The name of the protocol, must be "xmlrpc" or "netrpc".
    :param port: The number of the port. Defaults to auto.
    """
    if port == 'auto':
        port = 8069 if protocol=="xmlrpc" else 8070
    if protocol == "xmlrpc":
        return XmlRPCConnector(hostname, port)
    elif protocol == "netrpc":
        return NetRPCConnector(hostname, port)
    else:
        raise ValueError("You must choose xmlrpc or netrpc")

def get_connection(hostname, protocol="xmlrpc", port='auto', database=None,
                 login=None, password=None, user_id=None):
    """
    A shortcut method to easily create a connection to a remote OpenERP server.

    :param hostname: The hostname to the remote server.
    :param protocol: The name of the protocol, must be "xmlrpc" or "netrpc".
    :param port: The number of the port. Defaults to auto.
    :param connector: A valid Connector instance to send messages to the remote server.
    :param database: The name of the database to work on.
    :param login: The login of the user.
    :param password: The password of the user.
    :param user_id: The user id is a number identifying the user. This is only useful if you
    already know it, in most cases you don't need to specify it.
    """
    return Connection(get_connector(hostname, protocol, port), database, login, password, user_id)
        
