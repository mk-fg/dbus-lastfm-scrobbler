#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
parser = argparse.ArgumentParser(
	description='DBus interface to last.fm scrobbling.')

parser.add_argument('-t', '--activity-timeout',
	type=float, default=30, metavar='minutes',
	help='No-activity (dbus calls) timeout before closing the daemon instance'
		' (less or equal to zero - infinite, default: %(default)s minutes).')
parser.add_argument('--default-network', default='lastfm',
	help='Name of the network to use, unless overidden'
		' by dbus calls ("lastfm" or "librefm", default: %(default)s).')

parser.add_argument('-n', '--dry-run', action='store_true', help='Do not actually send data.')
parser.add_argument('--sync', action='store_true',
	help='Do synchronous submissions and return'
		' errors/tracebacks on dbus. Can be useful for debugging.')
parser.add_argument('--debug', action='store_true', help='Verbose operation mode.')
optz = parser.parse_args()

import itertools as it, operator as op, functools as ft
from dbus.mainloop.glib import DBusGMainLoop
import dbus, dbus.service, dbus.exceptions
import os, sys, logging

try: from gi.repository import GObject # gtk+ 3.X
except ImportError: import gobject as GObject # gtk+ 2.X

logging.basicConfig(level=logging.WARNING if not optz.debug else logging.DEBUG)
log = logging.getLogger('dbus-lastfm')


_notify_init = False
def try_notification(title, body, critical=False, timeout=None):
	global _notify_init
	try:
		try: # gtk+ 3.X
			from gi.repository import Notify
			_pynotify = False
		except ImportError: # gtk+ 2.X
			import pynotify as Notify
			_pynotify = True
		if not _notify_init:
			Notify.init('dbus-last.fm')
			_notify_init = True
		if not _pynotify:
			note = Notify.Notification()
			note.set_properties(summary=title, body=body)
		else:
			note = Notify.Notification(title, body)
		if critical: note.set_urgency( Notify.Urgency.CRITICAL
			if not _pynotify else Notify.URGENCY_CRITICAL )
		if timeout is not None: note.set_timeout(timeout)
		note.show()
	except Exception as err:
		(log.exception if optz.debug else log.info)(
			'Failed to dispatch desktop-notification: {}'.format(err) )


class DBusLastFM(dbus.service.Object):

	dbus_id = 'net.fraggod.DBusLastFM'
	dbus_path = '/net/fraggod/DBusLastFM'

	def __init__(self, bus=None):
		if bus is None: bus = dbus.SessionBus()
		super(DBusLastFM, self).__init__( bus,
			self.dbus_path, dbus.service.BusName(self.dbus_id, bus) )

	def listen(self):
		log.debug('Starting gobject loop')
		GObject.MainLoop().run()


	class scrobbler(object):
		'This is NOT an abstraction, just a convenient proxy.'

		auth, scrobbler = dict(), None # are set from the outside
		network = optz.default_network

		def __init__(self):
			self.activity_event()

		def __getattr__(self, k):
			if k.startswith('_dbus_'): raise AttributeError(k)
			if not self.auth: raise dbus.exceptions.DBusException('NO-AUTH')
			return ft.partial(self.async_call if not optz.sync else self.call, k)

		def async_call(self, func, *argz, **kwz):
			GObject.timeout_add(0, ft.partial(self.call, func, *argz, **kwz))

		def call(self, func, *argz, **kwz):
			log.debug( 'Scrobbler call -'
				' {}, args: {}, kwz: {}'.format(func, argz, kwz) )
			self.activity_event()
			if optz.dry_run: return
			try:
				if not self.scrobbler:
					import pylast
					network = getattr(pylast, 'get_{}_network'.format(self.network))
					self.scrobbler = network(**self.auth)\
						.get_scrobbler(client_id='emm', client_version='1.0')
				return getattr(self.scrobbler, func)(*argz, **kwz)
			except Exception as err:
				msg = 'Failed to {} track'.format(func)
				if optz.debug:
					log.exception(msg)
					log.debug( 'Call data:\n  method:'
						' {}\n  args: {}\n  keywords: {}'.format(func, argz, kwz) )
				try_notification(msg, 'Error: {}'.format(err), critical=True)

		activity_timer = None
		def activity_event(self, timeout=None):
			if timeout is not None:
				log.debug('Exiting due to inactivity timeout ({}m)'.format(timeout))
				sys.exit()
			if self.activity_timer is not None: GObject.source_remove(self.activity_timer)
			if optz.activity_timeout > 0:
				self.activity_timer = GObject.timeout_add(
					int(optz.activity_timeout * 60 * 1000), self.activity_event, optz.activity_timeout )

	scrobbler = scrobbler()


	_dbus_method = ft.partial(dbus.service.method, dbus_id)
	_dbus_signal = ft.partial(dbus.service.signal, dbus_id)

	@_dbus_method('s', '')
	def SetNetwork(self, network):
		log.debug('Got update for network (to {})'.format(network))
		self.scrobbler.network, self.scrobbler.scrobbler = network, None

	@_dbus_method('sss', '')
	def Auth(self, api_key, api_secret, session_key):
		log.debug('Got update for API keys')
		self.scrobbler.auth = dict( api_key=api_key,
			api_secret=api_secret, session_key=session_key )

	@_dbus_method('sssud', '')
	def Scrobble(self, artist, album, title, duration, ts):
		self.scrobbler.scrobble(
			artist=artist, album=album, title=title,
			duration=duration, time_started=int(ts),
			source=pylast.SCROBBLE_SOURCE_USER,
			mode=pylast.SCROBBLE_MODE_PLAYED )

	@_dbus_method('sssu', '')
	def ReportNowPlaying(self, artist, album, title, duration):
		self.scrobbler.report_now_playing(
			artist=artist, album=album, title=title, duration=duration or '' )


DBusGMainLoop(set_as_default=True)
DBusLastFM().listen()
