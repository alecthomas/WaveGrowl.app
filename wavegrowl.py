# encoding: utf-8
#
# Copyright (C) 2010 Alec Thomas <alec@swapoff.org>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
# Author: Alec Thomas <alec@swapoff.org>

"""Growl notifications for Wave."""


import json
import os
import time
import urllib2

from AppKit import NSWorkspace, NSStatusBar, NSMenuItem, NSMenu, NSImage, \
        NSVariableStatusItemLength, NSRunLoop, NSDefaultRunLoopMode, \
        NSApplication, NSThread, NSAutoreleasePool, NSUserDefaults, NSLog
from Foundation import NSURL, NSObject, NSTimer, NSDate
from PyObjCTools import AppHelper
from PyObjCTools import Debugging
from waveapi import waveservice
import Growl
import keyring

import credentials


class Notifier(object):
    GROWL_ICON = 'wavegrowl.png'

    def __init__(self):
        self.image = Growl.Image.imageFromPath(self.GROWL_ICON)
        self.notifier = Growl.GrowlNotifier('WaveGrowl', ['status'])
        self.notifier.register()

    def notify(self, title, message):
        self.notifier.notify('status', title, message, icon=self.image)


class WaveGrowl(NSObject):
    DEFAULT_FREQUENCY = 5
    MINUTES = [1, 2, 5, 15, 30]
    MENUBAR_ICON = 'wavegrowlmenubar.png'
    DISABLED_MENUBAR_ICON = 'wavegrowlmenubardisabled.png'

    frequency_menus = {}
    disabled_menus = []
    frequency_menu_item = None
    status_menu_item = None
    images = {}
    statusbar = None
    state = 'enabled'
    timer = None
    notified_state = {}
    state_dir = os.path.expanduser('~/Library/Application Support/WaveGrowl')

    def _authenticate(self):
        pool = NSAutoreleasePool.alloc().init()
        try:
            self.service = get_authenticated_service(self.notifier)
        except Exception, e:
            self.notifier.notify('Authentication Failed',
                                 'Failed to authenticate: %s' % e)
            NSApplication.sharedApplication().terminate_(self)
            return
        # Get the timer going
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            '_start_checking', None, False)
        del pool

    @property
    def frequency(self):
        return self.defaults.objectForKey_('frequency') \
                or self.DEFAULT_FREQUENCY

    def _start_checking(self, _):
        self.enable(True)
        self.set_status()
        self.set_check_frequency(self.frequency)

    def applicationDidFinishLaunching_(self, notification):
        self.defaults = NSUserDefaults.standardUserDefaults()
        self.notifier = Notifier()

        self.load_state()
        # Build status bar icon
        self.create_status_item()

    def create_status_item(self):
        statusbar = NSStatusBar.systemStatusBar()
        self.status_item = statusbar.statusItemWithLength_(
            NSVariableStatusItemLength)
        self.images['enabled'] = NSImage.alloc().initByReferencingFile_(
            self.MENUBAR_ICON)
        self.images['disabled'] = NSImage.alloc().initByReferencingFile_(
            self.DISABLED_MENUBAR_ICON)
        self.status_item.setHighlightMode_(1)
        self.status_item.setToolTip_('Wave Growl Notifier')

        self.menu = NSMenu.alloc().init()
        self.status_menu_item = NSMenuItem.alloc() \
                .initWithTitle_action_keyEquivalent_('Authenticating...',
                                                     None, '')
        self.menu.addItem_(self.status_menu_item)
        self.menu.addItem_(NSMenuItem.separatorItem())
        self.frequency_menu_item = NSMenuItem.alloc() \
                .initWithTitle_action_keyEquivalent_('Frequency', None, '')
        self.menu.addItem_(self.frequency_menu_item)
        menu_item = NSMenuItem.alloc() \
                .initWithTitle_action_keyEquivalent_('Quit', 'terminate:', '')
        self.menu.addItem_(menu_item)
        self.status_item.setMenu_(self.menu)

        frequency_menu = NSMenu.alloc().init()
        for minute in self.MINUTES:
            if minute == 1:
                message = '1 Minute'
            else:
                message = '%d Minutes' % minute
            menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                message, 'frequency:', '')
            menu_item.setTag_(minute)
            self.frequency_menus[minute] = menu_item
            frequency_menu.addItem_(menu_item)
            if minute == self.frequency:
                menu_item.setState_(1)
                self.frequency_menu_default = menu_item
        self.menu.setSubmenu_forItem_(frequency_menu, self.frequency_menu_item)
        self.enable(False)

        # Authenticate in the background
        self._authentication_thread = NSThread.alloc() \
                .initWithTarget_selector_object_(
                    self, self._authenticate, None)
        self._authentication_thread.start()

    def set_check_frequency(self, frequency, start_time=None):
        self.defaults.setObject_forKey_(frequency, 'frequency')
        self.defaults.synchronize()
        if self.timer:
            self.timer.invalidate()
        if not start_time:
            start_time = NSDate.date()
        self.timer = NSTimer.alloc() \
                .initWithFireDate_interval_target_selector_userInfo_repeats_(
                    start_time, self.frequency * 60, self, 'tick:', None, True)
        NSRunLoop.currentRunLoop() \
                .addTimer_forMode_(self.timer, NSDefaultRunLoopMode)
        self.frequency_menu_default.setState_(0)
        self.frequency_menu_default = self.frequency_menus[frequency]
        self.frequency_menu_default.setState_(1)

    def frequency_(self, notification):
        frequency = notification.tag()
        if frequency == 1:
            message = 'Checking every minute.'
        else:
            message = 'Checking every %d minutes.' % frequency
        self.notifier.notify('Wave Growl Notifier', message)
        start_time = NSDate.dateWithTimeIntervalSinceNow_(frequency * 60)
        self.set_check_frequency(frequency, start_time)

    def tick_(self, notification):
        self.set_status('Checking...')
        try:
            self.check_status()
            self.enable(True)
            self.set_status()
        except Exception, e:
            NSLog('Check failed: %s.' % e)
            self.enable(False, and_frequency_menu=False)
            self.set_status('Fetch failed.')

    def check_status(self):
        result = self.service.search(
            'in:inbox is:unread', num_results=100)
        total_count = 0
        notified_count = 0
        for digest in result.digests:
            total_count += 1
            last_notification = self.notified_state.get(digest.wave_id, 0)
            if notified_count < 10 \
                    and last_notification < digest.last_modified:
                # TODO(alec) GrowlNotifier doesn't seem to support click
                # events, but it would be nice to be able to go to the wave
                # when you click the notification.
                self.notifier.notify('%s (%d unread blip)'
                                     % (digest.title, digest.unread_count),
                                     digest.snippet)
                notified_count += 1
                self.notified_state[digest.wave_id] = digest.last_modified
        self.save_state()
        self.set_status()
        if total_count:
            self.status_item.setAttributedTitle_('%i' % total_count)
        else:
            self.status_item.setAttributedTitle_('')

    def load_state(self):
        self.notified_state = {}
        try:
            path = os.path.join(self.state_dir, 'State.json')
            with open(path) as fd:
                state = json.load(fd)
                self.notified_state = state['notified_state']
        except Exception, e:
            NSLog('Failed to load state: %s' % e)

    def save_state(self):
        path = self.state_dir
        if not os.path.exists(path):
            os.makedirs(path)
        state = {'notified_state': self.notified_state}
        with open(os.path.join(path, 'State.json'), 'wb') as fd:
            json.dump(state, fd, indent=True)

    def enable(self, enabled, and_frequency_menu=True):
        if and_frequency_menu:
            self.frequency_menu_item.setEnabled_(enabled)
        image = self.images['enabled' if enabled else 'disabled']
        self.status_item.setImage_(image)

    def set_status(self, status=None):
        self.status_menu_item.setTitle_(status or 'Wave Growl Notifier')


def fetch_oauth_verifier_token(request_token):
    """Polls the wavegrowl OAuth helper server repeatedly until a verifier
    token is available. """
    # Poll for two minutes
    attempts = 120 / 5
    oauth_verifier = None
    while not oauth_verifier and attempts:
        attempts -= 1
        try:
            request = urllib2.urlopen(
                'http://wavegrowl.appspot.com/verifier/%s' % request_token.key)
            return request.read().strip()
        except urllib2.HTTPError, e:
            if e.code == 404:
                time.sleep(5)
                continue
            raise
    raise Exception('Time out waiting for authentication verification token.')


def get_authenticated_service(notifier):
    """Return an authenticated WaveService object."""
    # TODO(alec) Move all of these strings out into constants.
    service = waveservice.WaveService(
            consumer_key=credentials.CONSUMER_KEY,
            consumer_secret=credentials.CONSUMER_SECRET,
    )
    access_token = keyring.get_password('GrowlWave', 'access_token')
    if access_token:
        service.set_access_token(access_token)
        return service

    notifier.notify('Wave Growl Notifier',
                    'Authenticating your Google account.')
    request_token = service.fetch_request_token(
            callback='http://wavegrowl.appspot.com/authsub')
    auth_url = service.generate_authorization_url()

    workspace = NSWorkspace.sharedWorkspace()
    workspace.openURL_(NSURL.URLWithString_(auth_url))

    oauth_verifier = fetch_oauth_verifier_token(request_token)

    service = waveservice.WaveService(
            consumer_key=credentials.CONSUMER_KEY,
            consumer_secret=credentials.CONSUMER_SECRET,
    )
    access_token = service.upgrade_to_access_token(request_token,
                                                   oauth_verifier)
    keyring.set_password('GrowlWave', 'access_token', access_token.to_string())
    notifier.notify('Wave Growl Notifier', 'Successfully authenticated!')
    return service


def main():
    Debugging.installVerboseExceptionHandler()
    app = NSApplication.sharedApplication()
    delegate = WaveGrowl.alloc().init()
    app.setDelegate_(delegate)
    AppHelper.runEventLoop()


if __name__ == '__main__':
    main()
