#!/bin/env python
""" Unit tests for the rest.connector cisco-shared package. """
import os
import unittest
from requests.models import Response
from unittest.mock import patch, MagicMock
from requests.exceptions import RequestException

from pyats.topology import loader

from rest.connector import Rest
HERE = os.path.dirname(__file__)


class test_rest_connector(unittest.TestCase):
    def setUp(self):
        self.testbed = loader.load(os.path.join(HERE, 'testbed.yaml'))
        self.device = self.testbed.devices['webex']
        self.testbed_connection_names = ["rest", "rest-ipv6", "rest-fqdn"]

    def test_init(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                self.assertEqual(connection.device, self.device)

                with self.assertRaises(NotImplementedError):
                    self.assertRaises(connection.execute())
                with self.assertRaises(NotImplementedError):
                    self.assertRaises(connection.configure())

    def test_connection(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                self.assertEqual(connection.connected, False)

                with patch('requests.Session') as req:
                    resp = Response()
                    resp.status_code = 200
                    req().get.return_value = resp
                    connection.connect()
                    self.assertEqual(connection.connected, True)
                    connection.connect()
                    self.assertEqual(connection.connected, True)

                # Now disconnect
                with patch('requests.Session') as req:
                    connection.disconnect()
                self.assertEqual(connection.connected, False)

    def test_post_not_connected(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                with self.assertRaises(Exception):
                    connection.post(dn='temp', payload={'payload': 'something'})

    def test_connection_wrong_code(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                self.assertEqual(connection.connected, False)

                with patch('requests.Session') as req:
                    resp = Response()
                    resp.status_code = 404
                    req().post.return_value = resp

                    with self.assertRaises(RequestException):
                        connection.connect()

                self.assertEqual(connection.connected, False)

                # Now disconnect
                with patch('requests.Session') as req:
                    connection.disconnect()
                self.assertEqual(connection.connected, False)

    def test_post_not_connected(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                with self.assertRaises(Exception):
                    connection.post(dn='temp', payload={'payload': 'something'})

    def test_post_connected(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                self.assertEqual(connection.connected, False)

                with patch('requests.Session') as req:
                    resp = Response()
                    resp.status_code = 200
                    req().get.return_value = resp
                    req().post.return_value = resp
                    connection.connect()
                    resp.json = MagicMock(return_value={'imdata': []})
                    connection.post(dn='temp', payload={'payload': 'something'})
                    connection.disconnect()
                self.assertEqual(connection.connected, False)

    def test_post_connected_wrong_status(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                self.assertEqual(connection.connected, False)

                with patch('requests.Session') as req:
                    resp = Response()
                    resp.status_code = 200
                    resp2 = Response()
                    resp2.status_code = 400
                    req().request.return_value = resp2
                    req().get.return_value = resp
                    req().post.return_value = resp2

                    connection.connect()
                    resp.json = MagicMock(return_value={'imdata': []})
                    resp2.json = MagicMock(return_value={'imdata': []})

                    with self.assertRaises(RequestException):
                        connection.post(dn='temp', payload={'payload': 'something'})

                    self.assertEqual(connection.connected, True)
                    connection.disconnect()

                self.assertEqual(connection.connected, False)

    def test_post_connected_change_expected(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                self.assertEqual(connection.connected, False)

                with patch('requests.Session') as req:
                    resp = Response()
                    resp.status_code = 200
                    resp2 = Response()
                    resp2.status_code = 300
                    req().get.side_effect = [resp, resp, resp]
                    req().post.return_value = resp2

                    connection.connect()
                    resp.json = MagicMock(return_value={'imdata': []})
                    resp2.json = MagicMock(return_value={'imdata': []})

                    connection.post(dn='temp', payload={'payload': 'something'})
                    self.assertEqual(connection.connected, True)
                    connection.disconnect()
                self.assertEqual(connection.connected, False)

    def test_post_connected_wrong_status_change_expected(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                self.assertEqual(connection.connected, False)

                with patch('requests.Session') as req:
                    resp = Response()
                    resp.status_code = 200
                    resp2 = Response()
                    resp2.status_code = 400
                    req().request.return_value = resp2
                    req().post.return_value = resp
                    req().get.return_value = resp

                    connection.connect()
                    resp.json = MagicMock(return_value={'imdata': []})
                    resp2.json = MagicMock(return_value={'imdata': []})

                    with self.assertRaises(RequestException):
                        connection.post(dn='temp', payload={'payload': 'something'})

                    self.assertEqual(connection.connected, True)
                    connection.disconnect()

                self.assertEqual(connection.connected, False)

    def test_get_not_connected(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                with self.assertRaises(Exception):
                    connection.get(dn='temp')

    def test_get_connected(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                self.assertEqual(connection.connected, False)

                with patch('requests.Session') as req:
                    resp = Response()
                    resp.status_code = 200
                    req().post.return_value = resp
                    req().get.return_value = resp
                    connection.connect()
                    resp.json = MagicMock(return_value={'imdata': []})
                    connection.get(dn='temp')
                    connection.disconnect()
                self.assertEqual(connection.connected, False)

    def test_get_connected_wrong_status(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                self.assertEqual(connection.connected, False)

                with patch('requests.Session') as req:
                    resp = Response()
                    resp.status_code = 200
                    resp2 = Response()
                    resp2.status_code = 400
                    req().request.return_value = resp2
                    req().get.return_value = resp
                    req().post.return_value = resp

                    connection.connect()
                    resp.json = MagicMock(return_value={'imdata': []})
                    resp2.json = MagicMock(return_value={'imdata': []})

                    with self.assertRaises(RequestException):
                        connection.get(dn='temp')

                    self.assertEqual(connection.connected, True)
                    connection.disconnect()

                self.assertEqual(connection.connected, False)

    def test_get_connected_change_expected(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                self.assertEqual(connection.connected, False)

                with patch('requests.Session') as req:
                    resp = Response()
                    resp.status_code = 200
                    resp2 = Response()
                    resp2.status_code = 300
                    req().get.side_effect = [resp, resp]

                    connection.connect()
                    resp.json = MagicMock(return_value={'imdata': []})
                    resp2.json = MagicMock(return_value={'imdata': []})

                    connection.get(dn='temp')
                    self.assertEqual(connection.connected, True)
                    connection.disconnect()
                self.assertEqual(connection.connected, False)

    def test_get_connected_wrong_status_change_expected(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                self.assertEqual(connection.connected, False)

                with patch('requests.Session') as req:
                    resp = Response()
                    resp.status_code = 200
                    resp2 = Response()
                    resp2.status_code = 500
                    req().request.return_value = resp2
                    req().get.return_value = resp
                    req().post.return_value = resp

                    connection.connect()
                    resp.json = MagicMock(return_value={'imdata': []})
                    resp2.json = MagicMock(return_value={'imdata': []})

                    with self.assertRaises(RequestException):
                        connection.get(dn='temp')

                    self.assertEqual(connection.connected, True)
                    connection.disconnect()

                self.assertEqual(connection.connected, False)

    def test_delete_not_connected(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                with self.assertRaises(Exception):
                    connection.delete(dn='temp')

    def test_delete_connected(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                self.assertEqual(connection.connected, False)

                with patch('requests.Session') as req:
                    resp = Response()
                    resp.status_code = 200
                    req().get.return_value = resp
                    req().delete.return_value = resp
                    connection.connect()
                    resp.json = MagicMock(return_value={'imdata': []})
                    connection.delete(dn='temp')
                    connection.disconnect()
                self.assertEqual(connection.connected, False)

    def test_delete_connected_wrong_status(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                self.assertEqual(connection.connected, False)

                with patch('requests.Session') as req:
                    resp = Response()
                    resp.status_code = 200
                    resp2 = Response()
                    resp2.status_code = 400
                    req().request.return_value = resp2
                    req().get.return_value = resp
                    req().post.return_value = resp

                    connection.connect()
                    resp.json = MagicMock(return_value={'imdata': []})
                    resp2.json = MagicMock(return_value={'imdata': []})

                    with self.assertRaises(RequestException):
                        connection.delete(dn='temp')

                    self.assertEqual(connection.connected, True)
                    connection.disconnect()

                self.assertEqual(connection.connected, False)

    def test_delete_connected_change_expected(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                self.assertEqual(connection.connected, False)

                with patch('requests.Session') as req:
                    resp = Response()
                    resp.status_code = 200
                    resp2 = Response()
                    resp2.status_code = 300
                    req().delete.return_value = resp2
                    req().get.return_value = resp
                    req().post.side_effect = [resp, resp2]

                    connection.connect()
                    resp.json = MagicMock(return_value={'imdata': []})
                    resp2.json = MagicMock(return_value={'imdata': []})
                    connection.delete(dn='temp')
                    self.assertEqual(connection.connected, True)
                    connection.disconnect()

                self.assertEqual(connection.connected, False)

    def test_delete_connected_wrong_status_change_expected(self):
        for connection_name in self.testbed_connection_names:
            with self.subTest(connection_name=connection_name):
                connection = Rest(device=self.device, alias='rest', via=connection_name)

                self.assertEqual(connection.connected, False)

                with patch('requests.Session') as req:
                    resp = Response()
                    resp.status_code = 200
                    resp2 = Response()
                    resp2.status_code = 400
                    req().get.return_value = resp
                    req().post.return_value = resp
                    req().request.return_value = resp2

                    connection.connect()

                    with self.assertRaises(RequestException):
                        connection.delete(dn='/temp')

                    self.assertEqual(connection.connected, True)
                    connection.disconnect()

                self.assertEqual(connection.connected, False)
