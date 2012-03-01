#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function

import argparse
parser = argparse.ArgumentParser(
	description='DBus interface to last.fm scrobbling.')
parser.add_argument('-n', '--dry-run', action='store_true', help='Do not actually send data.')
parser.add_argument('--sync', action='store_true',
	help='Do synchronous submissions and return'
		' errors/tracebacks on dbus. Can be useful for debugging.')
parser.add_argument('--debug', action='store_true', help='Verbose operation mode.')
optz = parser.parse_args()

import itertools as it, operator as op, functools as ft
from dbus.mainloop.glib import DBusGMainLoop
import dbus, dbus.service
from gi.repository import GObject
import os, sys, logging

import pylast

logging.basicConfig(level=logging.WARNING if not optz.debug else logging.DEBUG)
log = logging.getLogger('dbus-lastfm')


_notify_init = False
def try_notification(title, body, critical=False, timeout=None):
	global _notify_init
	try:
		from gi.repository import Notify
		if not _notify_init:
			Notify.init('dbus-last.fm')
			_notify_init = True
		note = Notify.Notification()
		note.set_properties(summary=title, body=body)
		if critical: note.set_urgency(Notify.Urgency.CRITICAL)
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
		auth, scrobbler = dict(), None

		def __getattr__(self, k):
			return ft.partial(self.async_call if not optz.sync else self.call, k)

		def async_call(self, func, *argz, **kwz):
			GObject.timeout_add(0, ft.partial(self.call, func, *argz, **kwz))

		def call(self, func, *argz, **kwz):
			try:
				if not self.scrobbler:
					self.scrobbler = pylast.get_lastfm_network(**self.auth)\
						.get_scrobbler(client_id='emm', client_version='1.0')
				return getattr(self.scrobbler, func)(*argz, **kwz)
			except Exception as err:
				msg = 'Failed to {} track'.format(func)
				if optz.debug:
					log.exception(msg)
					log.debug( 'Call data:\n  method:'
						' {}\n  args: {}\n  keywords: {}'.format(func, argz, kwz) )
				try_notification(msg, 'Error: {}'.format(err), critical=True)

	scrobbler = scrobbler()


	_dbus_method = ft.partial(dbus.service.method, dbus_id)
	_dbus_signal = ft.partial(dbus.service.signal, dbus_id)

	@_dbus_method('sss', '')
	def Auth(self, api_key, api_secret, session_key):
		self.scrobbler.auth = dict( api_key=api_key,
			api_secret=api_secret, session_key=session_key )

	@_dbus_method('sssuu', '')
	def Scrobble(self, artist, album, title, ts, duration):
		self.scrobbler.scrobble(
			artist=artist, album=album, title=title,
			duration=duration, time_started=ts,
			source=pylast.SCROBBLE_SOURCE_USER,
			mode=pylast.SCROBBLE_MODE_PLAYED )

	@_dbus_method('sssu', '')
	def ReportNowPlaying(self, artist, album, title, duration):
		self.scrobbler.report_now_playing(
			artist=artist, album=album, title=title, duration=duration or '' )


DBusGMainLoop(set_as_default=True)
DBusLastFM().listen()
