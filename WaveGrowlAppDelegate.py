#
#  WaveGrowlAppDelegate.py
#  WaveGrowl
#
#  Created by Alec Thomas on 22/07/10.
#  Copyright __MyCompanyName__ 2010. All rights reserved.
#


from AppKit import NSWorkspace, NSStatusBar, NSMenuItem, NSMenu, NSImage, \
        NSVariableStatusItemLength, NSRunLoop, NSDefaultRunLoopMode
from Foundation import NSURL, NSObject, NSTimer, NSDate
from waveapi import waveservice
# FIXME(aat) How do I make this work in Corp?
#waveservice.WaveService.RPC_URL = \
#  'http://www-opensocial-test.googleusercontent.com/api/rpc'
import Growl
import keyring

import credentials


MENUBAR_ICON = 'wavegrowlmenubar.png'
GROWL_ICON = 'wavegrowl.png'


class Notifier(object):
    def __init__(self):
        self.image = Growl.Image.imageFromPath(GROWL_ICON)
        self.notifier = Growl.GrowlNotifier('WaveGrowl', ['status'])
        self.notifier.register()

    def notify(self, title, message):
        self.notifier.notify('status', title, message, icon=self.image)


class WaveGrowlAppDelegate(NSObject):
    MINUTES = [1, 2, 5, 15, 30]

    frequency = 60
    frequency_menus = {}
    images = {}
    statusbar = None
    state = 'idle'
    timer = None

    def applicationDidFinishLaunching_(self, notification):
        self.notifier = Notifier()
        self.service = get_authenticated_service(self.notifier)
        statusbar = NSStatusBar.systemStatusBar()
        self.statusitem = statusbar.statusItemWithLength_(
            NSVariableStatusItemLength)
        self.images['active'] = NSImage.alloc().initByReferencingFile_(
            MENUBAR_ICON)
        self.statusitem.setImage_(self.images['active'])
        self.statusitem.setHighlightMode_(1)
        self.statusitem.setToolTip_('Sync Trigger')

        self.menu = NSMenu.alloc().init()
        menuitem = NSMenuItem.alloc() \
                .initWithTitle_action_keyEquivalent_('Wave Growl', None, '')
        self.menu.addItem_(menuitem)
        frequencymenuitem = NSMenuItem.alloc() \
                .initWithTitle_action_keyEquivalent_('Frequency', None, '')
        self.menu.addItem_(frequencymenuitem)
        menuitem = NSMenuItem.alloc() \
                .initWithTitle_action_keyEquivalent_('Quit', 'terminate:', '')
        self.menu.addItem_(menuitem)
        self.statusitem.setMenu_(self.menu)

        frequencymenu = NSMenu.alloc().init()
        for minute in self.MINUTES:
            seconds = minute * 60
            menuitem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                '%d Minute%s' % (minute, 's' if minute > 1 else ''),
                'frequency:', '')
            menuitem.setTag_(seconds)
            self.frequency_menus[seconds] = menuitem
            frequencymenu.addItem_(menuitem)
            if seconds == self.frequency:
                menuitem.setState_(1)
                self.frequency_menu_default = menuitem
        self.menu.setSubmenu_forItem_(frequencymenu, frequencymenuitem)

        # Get the timer going
        self.set_check_frequency(self.frequency)

    def set_check_frequency(self, frequency):
        self.frequency = frequency
        if self.timer:
            self.timer.invalidate()
        start_time = NSDate.date()
        self.timer = NSTimer.alloc() \
                .initWithFireDate_interval_target_selector_userInfo_repeats_(
                    start_time, self.frequency, self, 'tick:', None, True)
        NSRunLoop.currentRunLoop() \
                .addTimer_forMode_(self.timer, NSDefaultRunLoopMode)
        self.notifier.notify('Wave Growl', 'Checking every %d minutes.'
                             % (self.frequency / 60))
        self.frequency_menu_default.setState_(0)
        self.frequency_menu_default = self.frequency_menus[frequency]
        self.frequency_menu_default.setState_(1)

    def frequency_(self, notification):
        self.set_check_frequency(notification.tag())

    def tick_(self, notification):
        notify_on_changed_waves(self.notifier, self.service,
                                'in:inbox is:changed is:unread past:2days')


def get_authenticated_service(notifier):
    """Return an authenticated WaveService object."""
    service = waveservice.WaveService(
            consumer_key=credentials.CONSUMER_KEY,
            consumer_secret=credentials.CONSUMER_SECRET,
    )
    access_token = keyring.get_password('GrowlWave', 'access_token')
    if access_token:
        service.set_access_token(access_token)
        return service

    notifier.notify('Wave Growl',
                    'Authenticating your Google account.')
    request_token = service.fetch_request_token(
            callback='http://oauthhelper.appspot.com/WaveGrowl')
    auth_url = service.generate_authorization_url()

    workspace = NSWorkspace.sharedWorkspace()
    workspace.openURL_(NSURL.URLWithString_(auth_url))
    # TODO Poll oauthhelper for token rather than prompting user.
    oauth_verifier = raw_input('oauth_verifier: ')
    service = waveservice.WaveService(
            consumer_key=credentials.CONSUMER_KEY,
            consumer_secret=credentials.CONSUMER_SECRET,
    )
    access_token = service.upgrade_to_access_token(request_token,
                                                   oauth_verifier)
    keyring.set_password('GrowlWave', 'access_token', access_token.to_string())
    return service


def notify_on_changed_waves(
        notifier, service, query='in:inbox is:unread is:changed past:2days'):
    for digest in service.search(query).digests:
        # TODO(alec) GrowlNotifier doesn't seem to support click events, but it
        # would be nice to be able to go to the wave when you click the
        # notification.
        notifier.notify('%s (%d unread blip)'
                        % (digest.title, digest.unread_count),
                        digest.snippet)
