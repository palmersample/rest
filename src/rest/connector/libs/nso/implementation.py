import re
import json
import logging
from ipaddress import ip_address, IPv4Address, IPv6Address
import requests
from dict2xml import dict2xml
from requests.exceptions import RequestException

from pyats.connections import BaseConnection
from rest.connector.implementation import Implementation as RestImplementation
from rest.connector.utils import get_username_password


# create a logger for this module
log = logging.getLogger(__name__)


class Implementation(RestImplementation):
    '''Rest Implementation for NSO

    Implementation of Rest connection to Network Service Orchestrator (NSO)

    YAML Example
    ------------

        devices:
            ncs:
                os: nso
                connections:
                    rest:
                        class: rest.connector.Rest
                        ip: 127.0.0.1
                        port: "8080"
                        protocol: http
                        credentials:
                            rest:
                                username: admin
                                password: admin
                custom:
                    abstraction:
                        order: [os]

    Code Example
    ------------

        >>> from pyats.topology import loader
        >>> testbed = loader.load('ncs.yaml')
        >>> device = testbed.devices['ncs']
        >>> device.connect(alias='rest', via='rest')
        >>> device.rest.connected
        True
    '''

    @BaseConnection.locked
    def connect(self,
                timeout=30,
                port='8080',
                protocol='http',
                default_content_type='json',
                verbose=False):
        '''connect to the device via REST

        Arguments
        ---------

            timeout (int): Timeout value
            port (str): Port number. Default to 8080
            protocol (str): http or https. Default to http
            default_content_type: Default for content type, json or xml

        Raises
        ------

        Exception
        ---------

            If the connection did not go well

        Note
        ----

        There is no return from this method. If something goes wrong, an
        exception will be raised.

        '''

        if self.connected:
            return

        log.debug("Content type: %s" % default_content_type)
        log.debug("Timeout: %s" % timeout)
        self.content_type = default_content_type

        # support sshtunnel
        if 'sshtunnel' in self.connection_info:
            try:
                from unicon.sshutils import sshtunnel
            except ImportError:
                raise ImportError(
                    '`unicon` is not installed for `sshtunnel`. Please install by `pip install unicon`.'
                )
            try:
                tunnel_port = sshtunnel.auto_tunnel_add(self.device, self.via)
                if tunnel_port:
                    ip = self.device.connections[self.via].sshtunnel.tunnel_ip
                    port = tunnel_port
            except AttributeError as e:
                raise AttributeError(
                    "Cannot add ssh tunnel. Connection %s may not have ip/host or port.\n%s"
                    % (self.via, e))
        else:
            try:
                host = self.connection_info['host']
            except KeyError:
                host = self.connection_info['ip']
                if not isinstance(host, (IPv4Address, IPv6Address)):
                    host = ip_address(host)

                # Properly format IPv6 URL if a v6 address is provided
                if isinstance(host, IPv6Address):
                    host = f"[{host.exploded}]"
                else:
                    host = host.exploded

            port = self.connection_info.get('port', port)

        if 'protocol' in self.connection_info:
            protocol = self.connection_info['protocol']

        self.base_url = '{protocol}://{host}:{port}'.format(protocol=protocol,
                                                            host=host,
                                                            port=port)

        self.login_url = '{f}/api'.format(f=self.base_url)

        log.info("Connecting to '{d}' with alias "
                 "'{a}'".format(d=self.device.name, a=self.alias))

        username, password = get_username_password(self)

        self.session = requests.Session()
        self.session.auth = (username, password)

        # Connect to the device via requests
        response = self.session.get(self.login_url, timeout=timeout)
        output = response.text
        log.debug("Response: {c} {r}, headers: {h}".format(c=response.status_code,
            r=response.reason, h=response.headers))
        if verbose:
            log.info("Response text:\n%s" % output)

        # Make sure it returned requests.codes.ok
        if response.status_code != requests.codes.ok:
            # Something bad happened
            raise RequestException("Connection to '{host}:{port}' has returned the "
                                   "following code '{c}', instead of the "
                                   "expected status code '{ok}'"\
                                        .format(host=host, port=port, c=response.status_code,
                                                ok=requests.codes.ok))
        self._is_connected = True
        log.info("Connected successfully to '{d}'".format(d=self.device.name))

        return response


    @BaseConnection.locked
    def disconnect(self):
        '''disconnect the device for this particular alias'''

        log.info("Disconnecting from '{d}' with "
                 "alias '{a}'".format(d=self.device.name, a=self.alias))
        try:
            self.session.close()
        finally:
            self._is_connected = False
        log.info("Disconnected successfully from "
                 "'{d}'".format(d=self.device.name))


    @BaseConnection.locked
    def get(self, api_url, content_type=None, headers=None,
             expected_status_codes=(
             requests.codes.no_content,
             requests.codes.ok
             ),
            timeout=30,
            verbose=False):
        '''GET REST Command to retrieve information from the device

        Arguments
        ---------
        api_url: API url string
        content_type: expected content type to be returned (xml or json)
        headers: dictionary of HTTP headers (optional)
        expected_status_codes: list of expected result codes (integers)
        timeout: timeout in seconds (default: 30)
        '''
        if not self.connected:
            raise Exception("'{d}' is not connected for "
                            "alias '{a}'".format(d=self.device.name,
                                                 a=self.alias))
        if content_type is None:
            content_type = self.content_type

        full_url = '{b}{a}'.format(b=self.base_url, a=api_url)

        header = 'application/vnd.yang.data+{fmt}' \
                 ', application/vnd.yang.collection+{fmt}' \
                 ', application/vnd.yang.datastore+{fmt}'

        if content_type.lower() == 'json':
            accept_header = header.format(fmt='json')
        elif content_type.lower() == 'xml':
            accept_header = header.format(fmt='xml')
        else:
            accept_header = content_type

        self.session.headers.update({'Accept': accept_header})
        if headers is not None:
            self.session.headers.update(headers)

        log.debug("Sending GET command to '{d}': "\
                 "{u}".format(d=self.device.name, u=full_url))
        log.debug("Request headers:{headers}".format(
                    headers= self.session.headers))

        response = self.session.get(full_url, timeout=timeout)
        output = response.text
        log.debug("Response: {c} {r}, headers: {h}".format(c=response.status_code,
            r=response.reason, h=response.headers))
        if verbose:
            log.info("Output received:\n{output}".format(output=output))

        # Make sure it returned requests.codes.ok
        if response.status_code not in expected_status_codes:
            # Something bad happened
            raise RequestException("'{c}' result code has been returned "
                                   "instead of the expected status code(s) "
                                   "'{e}' for '{d}'\n{t}"\
                                   .format(d=self.device.name,
                                           c=response.status_code,
                                           e=expected_status_codes,
                                           t=response.text))
        return response


    @BaseConnection.locked
    def post(self, api_url, payload='', content_type=None, headers=None, 
             expected_status_codes=(
             requests.codes.created,
             requests.codes.no_content,
             requests.codes.ok
             ),
             timeout=30,
             verbose=False):
        '''POST REST Command to configure information from the device

        Arguments
        ---------
        api_url: API url string
        payload: payload to sent, can be string or dict
        content_type: expected content type to be returned (xml or json)
        headers: dictionary of HTTP headers (optional)
        expected_status_codes: list of expected result codes (integers)
        timeout: timeout in seconds (default: 30)
        '''

        if not self.connected:
            raise Exception("'{d}' is not connected for "
                            "alias '{a}'".format(d=self.device.name,
                                                 a=self.alias))

        full_url = '{b}{a}'.format(b=self.base_url, a=api_url)

        request_payload = payload
        if isinstance(payload, dict):
            assert content_type != None, 'content_type parameter required when passing dict'
            if content_type == 'json':
                request_payload = json.dumps(payload)
            elif content_type == 'xml':
                request_payload = dict2xml(payload)

        if content_type is None:
            if re.match("<", payload.lstrip()) is not None:
                content_type = 'xml'
            else:
                content_type = 'json'

        # NSO Northbound APIs / Resources / Operations and Actions
        #
        # YANG-defined operations, defined with the YANG statements "rpc" or "tailf:action",
        # and the built-in operations, are represented with the media type "application/vnd.yang.operation".
        # Resources of this type accept only the method "POST".
        # In XML, such resources are encoded as subelements to the XML element "y:operations".
        # In JSON, they are encoded under "_operations".
        #

        if '/_operations' in api_url:
            # Rest operations like /api/running/devices/_operations/connect
            content_type_header = 'application/vnd.yang.operation+{fmt}'
        elif '/api/' in api_url:
            # for URIs accessing datastores (i.e. /api/running))
            content_type_header = 'application/vnd.yang.datastore+{fmt}'
        else:
            content_type_header = 'application/vnd.yang.data+{fmt}'

        accept_header = 'application/vnd.yang.data+{fmt}' \
         ', application/vnd.yang.collection+{fmt}' \
         ', application/vnd.yang.datastore+{fmt}'

        if content_type.lower() == 'json':
            content_type_header = content_type_header.format(fmt='json')
            accept_header = accept_header.format(fmt='json')
        elif content_type.lower() == 'xml':
            content_type_header = content_type_header.format(fmt='xml')
            accept_header = accept_header.format(fmt='xml')
        else:
            content_type_header = content_type
            accept_header = content_type

        self.session.headers.update({'Content-type': content_type_header})
        self.session.headers.update({'Accept': accept_header})
        if headers is not None:
            self.session.headers.update(headers)

        log.debug("Sending POST command to '{d}': {u}"\
            .format(d=self.device.name, u=full_url))
        log.debug("Request headers: {h}\nPayload: {p}"\
            .format(h=self.session.headers, p=request_payload))
        if verbose:
            log.info('Request payload:\n{payload}'.format(payload=request_payload))

        # Send to the device
        response = self.session.post(full_url, request_payload, timeout=timeout)
        output = response.text
        log.debug("Response: {c} {r}, headers: {h}".format(c=response.status_code,
            r=response.reason, h=response.headers))
        if verbose:
            log.info("Output received:\n{output}".format(output=output))

        # Make sure it returned requests.codes.ok
        if response.status_code not in expected_status_codes:
            # Something bad happened
            raise RequestException("'{c}' result code has been returned "
                                   "instead of the expected status code(s) "
                                   "'{e}' for '{d}'\n{t}"\
                                   .format(d=self.device.name,
                                           c=response.status_code,
                                           e=expected_status_codes,
                                           t=response.text))
        return response


    @BaseConnection.locked
    def patch(self, api_url, payload, content_type=None, headers=None, 
             expected_status_codes=(
             requests.codes.created,
             requests.codes.no_content,
             requests.codes.ok
             ),
             timeout=30,
             verbose=False):
        '''PATCH REST Command to configure information from the device

        Arguments
        ---------
        api_url: API url string
        payload: payload to sent, can be string or dict
        content_type: expected content type to be returned (xml or json)
        headers: dictionary of HTTP headers (optional)
        expected_status_codes: list of expected result codes (integers)
        timeout: timeout in seconds (default: 30)
        '''

        if not self.connected:
            raise Exception("'{d}' is not connected for "
                            "alias '{a}'".format(d=self.device.name,
                                                 a=self.alias))

        request_payload = payload
        if isinstance(payload, dict):
            assert content_type != None, 'content_type parameter required when passing dict'
            if content_type == 'json':
                request_payload = json.dumps(payload)
            elif content_type == 'xml':
                request_payload = dict2xml(payload)

        full_url = '{b}{a}'.format(b=self.base_url, a=api_url)

        if content_type is None:
            if re.match("<", payload.lstrip()) is not None:
                content_type = 'xml'
            else:
                content_type = 'json'

        content_type_header = 'application/vnd.yang.data+{fmt}'
        accept_header = 'application/vnd.yang.data+{fmt}' \
         ', application/vnd.yang.collection+{fmt}' \
         ', application/vnd.yang.datastore+{fmt}'

        if content_type.lower() == 'json':
            content_type_header = content_type_header.format(fmt='json')
            accept_header = accept_header.format(fmt='json')
        elif content_type.lower() == 'xml':
            content_type_header = content_type_header.format(fmt='xml')
            accept_header = accept_header.format(fmt='xml')
        else:
            content_type_header = content_type
            accept_header = content_type

        self.session.headers.update({'Content-type': content_type_header})
        self.session.headers.update({'Accept': accept_header})
        if headers is not None:
            self.session.headers.update(headers)

        log.debug("Sending PATCH command to '{d}': {u}".format(
                                                    d=self.device.name, u=full_url))
        log.debug("Request headers: {h}\nPayload:{p}".format(h=self.session.headers,
                                                    p=request_payload))
        if verbose:
            log.info('Request payload:\n{payload}'.format(payload=request_payload))

        # Send to the device
        response = self.session.patch(full_url, request_payload, timeout=timeout)
        output = response.text
        log.debug("Response: {c} {r}, headers: {h}".format(c=response.status_code,
            r=response.reason, h=response.headers))
        if verbose:
            log.info("Output received:\n{output}".format(output=output))

        # Make sure it returned requests.codes.ok
        if response.status_code not in expected_status_codes:
            # Something bad happened
            raise RequestException("'{c}' result code has been returned "
                                   "instead of the expected status code(s) "
                                   "'{e}' for '{d}'\n{t}"\
                                   .format(d=self.device.name,
                                           c=response.status_code,
                                           e=expected_status_codes,
                                           t=response.text))
        return response


    @BaseConnection.locked
    def put(self, api_url, payload, content_type=None, headers=None, 
             expected_status_codes=(
             requests.codes.created,
             requests.codes.no_content,
             requests.codes.ok
             ),
             timeout=30,
             verbose=False):
        '''PUT REST Command to configure information from the device

        Arguments
        ---------
        api_url: API url string
        payload: payload to sent, can be string or dict
        content_type: expected content type to be returned (xml or json)
        headers: dictionary of HTTP headers (optional)
        expected_status_codes: list of expected result codes (integers)
        timeout: timeout in seconds (default: 30)
        '''

        if not self.connected:
            raise Exception("'{d}' is not connected for "
                            "alias '{a}'".format(d=self.device.name,
                                                 a=self.alias))

        full_url = '{b}{a}'.format(b=self.base_url, a=api_url)

        request_payload = payload
        if isinstance(payload, dict):
            assert content_type != None, 'content_type parameter required when passing dict'
            if content_type == 'json':
                request_payload = json.dumps(payload)
            elif content_type == 'xml':
                request_payload = dict2xml(payload)

        if content_type is None:
            if re.match("<", payload.lstrip()) is not None:
                content_type = 'xml'
            else:
                content_type = 'json'

        content_type_header = 'application/vnd.yang.data+{fmt}'
        accept_header = 'application/vnd.yang.data+{fmt}' \
         ', application/vnd.yang.collection+{fmt}' \
         ', application/vnd.yang.datastore+{fmt}'

        if content_type.lower() == 'json':
            content_type_header = content_type_header.format(fmt='json')
            accept_header = accept_header.format(fmt='json')
        elif content_type.lower() == 'xml':
            content_type_header = content_type_header.format(fmt='xml')
            accept_header = accept_header.format(fmt='xml')
        else:
            content_type_header = content_type
            accept_header = content_type

        self.session.headers.update({'Content-type': content_type_header})
        self.session.headers.update({'Accept': accept_header})
        if headers is not None:
            self.session.headers.update(headers)

        log.debug("Sending PUT command to '{d}': {u}".format(
                                                    d=self.device.name, u=full_url))
        log.debug("Request headers: {h}\nPayload:{p}".format(h=self.session.headers,
                                                    p=request_payload))
        if verbose:
            log.info('Request payload:\n{payload}'.format(payload=request_payload))

        # Send to the device
        response = self.session.put(full_url, request_payload, timeout=timeout)
        output = response.text
        log.debug("Response: {c} {r}, headers: {h}".format(c=response.status_code,
            r=response.reason, h=response.headers))
        if verbose:
            log.info("Output received:\n{output}".format(output=output))

        # Make sure it returned requests.codes.ok
        if response.status_code not in expected_status_codes:
            # Something bad happened
            raise RequestException("'{c}' result code has been returned "
                                   "instead of the expected status code(s) "
                                   "'{e}' for '{d}'\n{t}"\
                                   .format(d=self.device.name,
                                           c=response.status_code,
                                           e=expected_status_codes,
                                           t=response.text))
        return response


    @BaseConnection.locked
    def delete(self, api_url, content_type=None, headers=None, 
             expected_status_codes=(
             requests.codes.created,
             requests.codes.no_content,
             requests.codes.ok
             ),
             timeout=30,
             verbose=False):
        '''DELETE REST Command to configure information from the device

        Arguments
        ---------
        api_url: API url string
        content_type: expected content type to be returned (xml or json)
        headers: dictionary of HTTP headers (optional)
        expected_status_codes: list of expected result codes (integers)
        timeout: timeout in seconds (default: 30)
        '''

        if not self.connected:
            raise Exception("'{d}' is not connected for "
                            "alias '{a}'".format(d=self.device.name,
                                                 a=self.alias))

        if content_type is None:
            content_type = self.content_type

        full_url = '{b}{a}'.format(b=self.base_url, a=api_url)

        if content_type.lower() == 'json':
            accept_header = 'application/vnd.yang.data+json'
        elif content_type.lower() == 'xml':
            accept_header = 'application/vnd.yang.data+xml'
        else:
            accept_header = content_type

        self.session.headers.update({'Accept': accept_header})
        if headers is not None:
            self.session.headers.update(headers)

        log.debug("Sending DELETE command to '{d}': "\
                 "{u}".format(d=self.device.name, u=full_url))
        log.debug("Request headers:{headers}".format(
                    headers= self.session.headers))

        response = self.session.delete(full_url, timeout=timeout)
        output = response.text
        log.debug("Response: {c} {r}, headers: {h}".format(c=response.status_code,
            r=response.reason, h=response.headers))
        if verbose:
            log.info("Output received:\n{output}".format(output=output))

        # Make sure it returned requests.codes.ok
        if response.status_code not in expected_status_codes:
            # Something bad happened
            raise RequestException("'{c}' result code has been returned "
                                   "instead of the expected status code(s) "
                                   "'{e}' for '{d}'\n{t}"\
                                   .format(d=self.device.name,
                                           c=response.status_code,
                                           e=expected_status_codes,
                                           t=response.text))
        return response
