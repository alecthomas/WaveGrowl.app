# encoding: utf-8
#
# Copyright 2010 Alec Thomas <alec@swapoff.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app


class OAuthVerifications(db.Model):
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
        verification = OAuthVerifications(oauth_token=oauth_token,
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
        verification = OAuthVerifications \
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
