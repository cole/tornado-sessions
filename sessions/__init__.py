# -*- coding: UTF-8 -*-
# Copyright 2014 Cole Maclean
"""Tornado sessions, stored in Redis.
"""
import datetime
import uuid
from functools import wraps
try:
    # python2
    import cPickle as pickle
except ImportError:
    # python3
    import pickle

import redis
from tornado.web import RequestHandler
from tornado.options import options, define

define("redis_host", default="localhost", help="Redis host")
define("redis_port", default=6379, help="Redis port number")
define("redis_session_db", default=0, help="Redis sessions database")
define("session_length", default=14, help="Session length in days")

class Session(object):
    """Simple session, stored in redis.
    sess_id = uuid.uuid4().hex
    s = Session(id=sess_id)
    s['foo'] = 'bar'
    s.save()
        
    s = Session.load(sess_id)
    s['foo']
    > 'bar'
    """
    store = redis.StrictRedis(host=options.redis_host,
        port=options.redis_port, db=options.redis_session_db)
    length = options.session_length * 86400 # in seconds
 
    def __init__(self, id=None):
        self._id = id
        self._data = {}
        self.pipe = self.store.pipeline()
 
    @classmethod
    def load(cls, id):
        """Load the given session id from redis. If there's nothing for the
        id given, returns an empty session.
        
        returns Session object.
        """
        session = Session(id=id)
        # hgetall returns bytes
        for key, val in cls.store.hgetall(session.id).items():
            session._data[key.decode('utf-8')] = pickle.loads(val)
            
        return session
             
    @property
    def id(self):
        """Prefix the session id for storage."""
        return 'session:{}'.format(self._id) if self._id else None

    def clear(self):
        """Delete the session and all data."""
        self._data = {}
        self.pipe = self.store.pipeline()
        self.store.delete(self.id)
 
    def touch(self, remote_ip=None):
        """Update the session expiry and set the last access time
        and IP (if provided).
        """
        if remote_ip is not None:
            self['last_ip_address'] = remote_ip
        self['last_access_time'] = '{}'.format(datetime.datetime.now())
        self.pipe.expire(self.id, self.length)
                  
    def pop(self, key, default=None):
        """Pop a value off of the session.
        
        Returns session data or fallback."""
        if key in self:
            val = self[key]
            self.pipe.hdel(self.id, key)
            return val
        else:
            return default
 
    def save(self):
        """Execute piped session commands."""
        self.pipe.execute()
        
    def get(self, key, default):
        return self._data.get(key, default)
 
    def __getitem__(self, key):
        return self._data.__getitem__(key)
 
    def __setitem__(self, key, value):
        self.pipe.hset(self.id, key, pickle.dumps(value))
        self._data[key] = value
 
    def __delitem__(self, key):
        self.pipe.delete(self.id, key)
        del self._data[key]
 
    def __len__(self):
        return len(self._data)
 
    def __contains__(self, key):
        return (key in self._data)
 
    def __iter__(self):
        return iter(self._data)
 
    def __repr__(self):
        return "<{}, {}>".format(self.id, self._data.__repr__())

def setup_session(handler):
    """Setup a new session (or retrieve the existing one)"""
    session_id = handler.get_secure_cookie('session')

    if session_id is not None:
        handler.session = Session.load(session_id.decode('utf-8'))
    else:
        new_id = uuid.uuid4().hex
        handler.session = Session(id=new_id)
        handler.set_secure_cookie('session', new_id)

    handler.session.touch(remote_ip=handler.request.remote_ip)

def save_session(handler):
    """Store the session to redis."""
    if hasattr(handler, 'session') and handler.session is not None:
        handler.session.save()

class SessionHandler(RequestHandler):
    """Handlers inheriting from this class get session access (self.session).
    """
    def prepare(self):
        setup_session(self)
            
    def on_finish(self, *args, **kwargs):
        save_session(self)
        
    def clear_session(self):
        self.session.clear()
        self.clear_cookie('session')
            
def session(method):
    """Decorator for handler methods. Loads the session prior to method
    execution and saves it after.
    """
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        setup_session(self)
        result = method(self, *args, **kwargs)
        save_session(self)
        return result
    return wrapper