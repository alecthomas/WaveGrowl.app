Wave Growl Notifications
========================
I worked on the Wave team. I wrote this a week before Wave was cancelled. Good
times.

This is mostly now only useful as an example of Cocoa Python code, and using
two-legged OAuth from a desktop application.

Two-legged OAuth was a giant PITA. To make it work, a server component waits
for a verifier token from the Google authentication process, which it stores in
the datastore. WaveGrowl polls the server repeatedly until a timeout, or
the auth token is verified.
