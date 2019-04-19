try:
    import httplib
except ImportError:
    import http.client as httplib  # type: ignore
import cgi

class PrettyErrorHandler(object):
    """
    mix-in to improve cyclone.web.RequestHandler
    """
    def get_error_html(self, status_code, **kwargs):
        try:
            tb = kwargs['exception'].getTraceback()
        except AttributeError:
            tb = ""
        return "<html><title>%(code)d: %(message)s</title>" \
               "<body>%(code)d: %(message)s<pre>%(tb)s</pre></body></html>" % {
            "code": status_code,
            "message": httplib.responses[status_code],
            "tb" : cgi.escape(tb),
        }
