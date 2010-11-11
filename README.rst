Wave Growl Notifications
========================
I worked on the Wave team. I wrote this a week before Wave was cancelled. Good
timing!

This is mostly now only useful as an example of Cocoa Python code, and using
three-legged OAuth from a desktop application.

Three-legged OAuth was a giant PITA. To make it work, a server component waits
for a verifier token from the Google authentication process, which is stored in
the AppEngine datastore. WaveGrowl polls the server component repeatedly until
a timeout, or the auth token is verified.

Technology Used
---------------
* Python.
* Three-legged OAuth.
* Py2App.
* Cocoa.
