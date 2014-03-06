# Tornado Sessions

## Introduction

Tornado sessions is a basic system for handling session data stored in Redis.
A secure cookie on the client stores the session id, which maps to a hash of 
pickled data in redis.

Handlers inheriting from `SessionHandler` or methods wrapped by
`@session`are session aware, with a self.session object that can be 
accessed as a dict, which is saved on handler finish.

## Requirements

 - Tornado
 - Redis
 
## Usage

To use sessions, you must have a cookie secret set (for secure cookies).

There are two was to give handlers session access.

First using the `@session` wrapper on handler methods:

    class MainHandler(tornado.web.RequestHandler):
    
        @session
        def get(self):
            self.session # this is loaded now


Alternatively, handlers inheriting from `SessionHandler`:

    class MainHandler(SessionHandler):
    
        def get(self):
            self.session # this is loaded now

The `self.session` object can be treated as a dict that is automatically saved
to Redis when the handler method finishes. For example:


    class MainHandler(SessionHandler):
    
        def get(self):
            self.session['foo'] = 'bar'
            self.session['an_int'] = 7
            self.session['arbitrary_object'] = datetime.datetime.now()
    
    class LaterHandler(SessionHandler):
    
        def get(self):
            foo = self.session['foo'] # bar
            last_access = self.session['arbitrary_object'] # datetime object
            self.session['not_set'] # raises KeyError
            # in general, either use get or try/except
            self.session.get('not_set') # None
            # pop also works
            self.session.pop('an_int')

