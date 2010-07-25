# encoding: utf-8
#
# Copyright (C) 2010 Alec Thomas <alec@swapoff.org>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
# Author: Alec Thomas <alec@swapoff.org>

"""."""

import logging

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app


class OAuthVerififications(db.Model):
    oauth_token = db.StringProperty(required=True)
    oauth_verifier = db.StringProperty(required=True)


class MainPage(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/html'
        self.response.out.write("""
        <html>
            <head>
                <title>Wave Growl Notifier</title>
            </head>
            <body>
                Wave Growl Notifier
            </body>
        </html>
        """)


class OAuthEndpoint(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        oauth_verifier = self.request.get('oauth_verifier', '')
        oauth_token = self.request.get('oauth_token', '')
        logging.info('token=%s, verifier=%s', oauth_token, oauth_verifier)
        if not oauth_verifier or not oauth_token:
            self.error(400)
            return
        verification = OAuthVerififications(oauth_token=oauth_token,
                                            oauth_verifier=oauth_verifier)
        verification.put()
        self.response.headers['Content-Type'] = 'text/html'
        self.response.out.write("""
        <html>
            <head>
                <title>Account Authenticated</title>
            </head>
            <body>
                <p>
                    Your account has been authenticated. You may safely close
                    this page.
                </p>
            </body>
        </html>
        """)


class OAuthVerifier(webapp.RequestHandler):
    def get(self, token):
        verification = OAuthVerififications \
                .all() \
                .filter('oauth_token =', token) \
                .get()
        if not verification:
            self.error(404)
            return
        verification.delete()
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write(verification.oauth_verifier)


application = webapp.WSGIApplication([
    ('/authsub', OAuthEndpoint),
    ('/verifier/(.*)', OAuthVerifier),
    ('/', MainPage),
])


def main():
    run_wsgi_app(application)


if __name__ == "__main__":
    main()
