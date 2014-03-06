# -*- coding: UTF-8 -*-
# Copyright 2014 Cole Maclean
"""Tornado sessions, stored in Redis.
"""
import datetime
import uuid
import json
from functools import wraps
try:
    from collections import MutableMapping #py2
except ImportError:
    from collections.abc import MutableMapping #py3
try:
    import cPickle as pickle #py2
except ImportError:
    import pickle #py3

import redis
from tornado.web import RequestHandler
from tornado.options import options, define

define("redis_host", default="localhost", help="Redis host")
define("redis_port", default=6379, help="Redis port number")
define("redis_session_db", default=0, help="Redis sessions _database")
define("session_length", default=14, help="Session length in days")

class Session(MutableMapping):
    """Simple session, stored in redis.
    sess_id = uuid.uuid4().hex
    s = Session(sess_id)
    s['foo'] = 'bar'
    s.save()
        
    s = Session.load(sess_id)
    s['foo']
    > 'bar'
    """
    store = redis.StrictRedis(host=options.redis_host,
        port=options.redis_port, db=options.redis_session_db)
    length = options.session_length * 86400 # in seconds
 
    def __init__(self, id, *args, **kwargs):
        self._id = id
        self._data = dict(*args, **kwargs)
        self._loaded = False
        self._dirty = False
        self._pipe = self.store.pipeline()
 
    @classmethod
    def load(cls, id, preload=False):
        """Load the given session id from redis. If there's nothing for the
        id given, returns an empty session.
        If preload is True, load and unpickle all data.
        
        returns Session object.
        """
        session = Session(id)
        if preload:
            session._load_data()
            
        return session
    
    def _load_data(self):
        # hgetall returns bytes
        for key, val in self.store.hgetall(self.id).items():
            self._data[key.decode('utf-8')] = pickle.loads(val)
        self._loaded = True
                
    @property
    def id(self):
        """Prefix the session id for storage."""
        return 'session:{0}'.format(self._id) if self._id else None

    def clear(self):
        """Delete the session and all data."""
        self._data.clear()
        self._pipe = self.store.pipeline()
        self.store.delete(self.id)
 
    def touch(self, remote_ip=None):
        """Update the session expiry and set the last access time
        and IP (if provided).
        """
        if remote_ip is not None:
            self['last_ip_address'] = remote_ip
        self['last_access_time'] = '{0}'.format(datetime.datetime.now())
        self._pipe.expire(self.id, self.length)
 
    def save(self, force=False):
        """Execute piped session commands."""
        if self._dirty or force:
            self._pipe.execute()
        self._dirty = False
 
    def __getitem__(self, key):
        if not (self._loaded or key in self._data) and self.store.hexists(self.id, key):
            self._data[key] = pickle.loads(self.store.hget(self.id, key))
        return self._data[key]
 
    def __setitem__(self, key, value):
        self._dirty = True
        self._pipe.hset(self.id, key, pickle.dumps(value))
        self._data[key] = value
 
    def __delitem__(self, key):
        # We save immediately here to prevent
        # autoloading of the key on next access
        if self._loaded or key in self._data:
            self._pipe.hdel(self.id, key)
            self.save(force=True)
            del self._data[key]
        elif self.store.hexists(self.id, key):
            self._pipe.hdel(self.id, key)
            self.save(force=True)
        
    def __iter__(self):
        if not self._loaded:
            self._load_data()
        return iter(self._data)
        
    def __len__(self):
        if not self._loaded:
            self._load_data()
        return len(self._data)
        
    def __repr__(self):
        if not self._loaded:
            self._load_data()
        return "<{0}, {1}>".format(self.id, repr(self._data))
    
    def to_json(self):
        if not self._loaded:
            self._load_data()
        return json.dumps(self, default=lambda o: o._data,
            sort_keys=True, indent=4)
            
    def copy(self):
        if not self._loaded:
            self._load_data()
        return Session(self._id, **self._data.copy())

def setup_session(handler):
    """Setup a new session (or retrieve the existing one)"""
    session_id = handler.get_secure_cookie('session')

    if session_id is not None:
        handler.session = Session.load(session_id.decode('utf-8'))
    else:
        new_id = uuid.uuid4().hex
        handler.session = Session(new_id)
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