# -*- coding: UTF-8 -*-
# tests/unit/session_tests.py
# Rideshare
#
# Copyright 2013 Cole Maclean
"""Unit tests for session handling."""
import os
import sys
import datetime
import unittest
try:
    # python3
    from urllib.parse import urlencode
except ImportError:
    # python2
    from urllib import urlencode
    
import redis
import tornado.testing
import tornado.web
from tornado.escape import json_encode, json_decode
from tornado.options import options, define

from . import Session, SessionHandler, session

define("redis_test_db", default=15, help="Redis test database")
Session.store = redis.StrictRedis(host=options.redis_host,
    port=options.redis_port, db=options.redis_test_db)

class SessionTests(unittest.TestCase):    
    """Session handling tests.
    """
    def setUp(self):
        self.session_id = '12345678'
        self.session = Session(id=self.session_id)
    
    def tearDown(self):
        Session.store.flushdb()
    
    def test_session_id(self):
        self.assertTrue(self.session.id)
        
    def test_session_save(self):
        self.session['foo'] = 'bar'
        self.session.save()
        
        loaded = Session.load(self.session_id)
        self.assertEqual(loaded['foo'], 'bar')
        
    def test_session_not_save_on_del(self):
        self.session['foo'] = 'bar'
        del self.session
        
        loaded = Session.load(self.session_id)
        self.assertFalse('foo' in loaded)
        
    def test_save_basic_types(self):
        self.session['foo'] = 123
        self.session['bar'] = { 'hello': 'world' }
        self.session['baz'] = ['foo', 'bar']
        self.session.save()

        loaded = Session.load(self.session_id)
        self.assertEqual(loaded['foo'], 123)
        self.assertEqual(loaded['bar'], { 'hello': 'world' })
        self.assertEqual(loaded['baz'], ['foo', 'bar'])
        
    def test_save_custom_types(self):
        self.session['module'] = tornado.web.RequestHandler
        self.session['func'] = json_encode
        self.session.save()

        loaded = Session.load(self.session_id)
        self.assertEqual(loaded['module'], tornado.web.RequestHandler)
        self.assertEqual(loaded['func'], json_encode)
        
class SessionTestHandler(SessionHandler):

    def get(self):
        self.write(json_encode(self.session._data))

    def post(self):
        args = self.request.arguments
        for arg, val in args.items():
            self.session[arg] = val[0].decode('utf-8')
        self.finish()
    
    def delete(self):
        self.clear_session()
        self.finish()

class SessionWrapperHandler(tornado.web.RequestHandler):
    
    @session
    def get(self):
        self.write(json_encode(self.session._data))
    
    @session
    def post(self):
        args = self.request.arguments
        for arg, val in args.items():
            self.session[arg] = val[0].decode('utf-8')
        self.finish()
        
    @session
    def delete(self):
        self.session.clear()
        self.clear_cookie('session')
        self.finish()
        
class SessionHandlerTests(tornado.testing.AsyncHTTPTestCase):
    def get_app(self):
        settings = {
            'cookie_secret': "sdafdsklfdsfdsafkdsafjdskfjsdflksd",
            'log_function': lambda s: s, # hide web server logs
        }
        return tornado.web.Application([
            (r"/session_handler", SessionTestHandler),
            (r"/session_wrapper", SessionWrapperHandler),
        ], **settings)

    @tornado.testing.gen_test
    def test_session_handler(self):
        data = {
            'foo': 'bar',
            'testing': 123
        }
        post = yield self.http_client.fetch(self.get_url('/session_handler'),
            method="POST", body=urlencode(data))
        cookie = post.headers['Set-Cookie']
        raw_resp = yield self.http_client.fetch(self.get_url('/session_handler'),
            headers={ 'Cookie': cookie })
        json = json_decode(raw_resp.body)
        self.assertEqual(data['foo'], json['foo'])
        self.assertEqual(data['testing'], int(json['testing']))
    
        cleanup = yield self.http_client.fetch(self.get_url('/session_handler'),
            method="DELETE", headers={ 'Cookie': cookie })

class SessionWrapperTests(SessionHandlerTests):
    
    @tornado.testing.gen_test
    def test_session_wrapper(self):
        data = {
            'foo': 'bar',
            'testing': 123
        }
        post = yield self.http_client.fetch(self.get_url('/session_wrapper'),
            method="POST", body=urlencode(data))
        cookie = post.headers['Set-Cookie']
        raw_resp = yield self.http_client.fetch(self.get_url('/session_wrapper'),
            headers={ 'Cookie': cookie })
        json = json_decode(raw_resp.body)
        self.assertEqual(data['foo'], json['foo'])
        self.assertEqual(data['testing'], int(json['testing']))
    
        cleanup = yield self.http_client.fetch(self.get_url('/session_wrapper'),
            method="DELETE", headers={ 'Cookie': cookie })
            
def suite():
    suite = unittest.TestLoader().loadTestsFromTestCase(SessionTests)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(SessionHandlerTests))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(SessionWrapperTests))
    return suite
    
if __name__ == '__main__':        
    all = lambda: suite()
    tornado.testing.main()

