import tornado.ioloop
import tornado.web
import tornado.template

from sessions import session, SessionHandler

template = tornado.template.Template("""
<html>
<head>
    <title>Sessions example</title>
</head>
<body>
<form action="/" method="post">
<textarea rows="15" cols="60" name="entry">Text entered here will be saved in the session</textarea>
<br>
<input type="submit" value="submit">
</form>
<hr>
{% if entries %}
<strong>Here's what you've entered so far:</strong>
<ul>{% for entry in entries %}
  <li>{{ entry }}</li>
{% end %}</ul>
<form action="/clear" method="post">
<input type="submit" value="clear">
</form>
{% end %}
</body>
</html>
""")

class MainHandler(tornado.web.RequestHandler):
    """By wrapping handler methods with @session, we load the
    session before the method executes and save it after.
    """
    @session
    def get(self):
        self.write(template.generate(entries=self.session.get('entries', [])))
    
    @session
    def post(self):
        try:
            entries = self.session['entries']
        except KeyError:
            entries = []
        
        entry = self.get_argument("entry")
        entries.append(entry)
        
        self.session['entries'] = entries
        self.write(template.generate(entries=entries))

class ClearHandler(SessionHandler):
    """Handlers inheriting from SessionHandler automatically get session
    access through self.session.
    """
    def post(self):
        self.session.clear()
        self.redirect('/')

application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/clear", ClearHandler),
], cookie_secret='fdjkslfjdskfajdlskafjdksjafhdsjakhfs')

if __name__ == "__main__":
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()