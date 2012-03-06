dbus-lastfm-scrobbler: DBus service (API) to scrobble tracks to last.fm
--------------------

Primary goal of this service is to make track scrobbling asynchronous, so tracks
can be scrobbled from single-threaded apps like [emacs'
EMMS](http://www.gnu.org/s/emms/) without blocking the app itself.

Secondary goal is to abstract complexity of the API (regardless of it's version
and/or changes) via well-maintained and otherwise awesome [pyast
module](http://code.google.com/p/pylast/).

As mentioned, I just got sick of EMMS blocking emacs when scrobbling over
sluggish internet connection, and deciding between whether I should look into
EMMS elisp code and try to update it to do it in a fully-async way (worst-case
via invoking some "curl" in a subprocess) and making a separate component to do
the job w/o any hassle with API, naturally I chose the latter.

To be fair, EMMS look like it should be non-blocking already, since
`url-retrieve` calls are advertised as asynchronous, but for some reason they
are just not, and that's probably fixable or can be replaced (e.g. with
something like [kiwanami/emacs-deferred](https://github.com/kiwanami/emacs-deferred)).


Installation / Usage
--------------------

These will be needed at runtime:

* [Python 2.7 (not 3.X)](http://python.org/)
* [pylast](http://code.google.com/p/pylast/)
* [dbus-python](http://dbus.freedesktop.org/doc/dbus-python/) and
  [pygobject](http://live.gnome.org/PyGObject)
* (optional) GTK+ 3.X and
  [gobject-introspection](https://live.gnome.org/GObjectIntrospection/)-enabled
  [pygobject](http://live.gnome.org/PyGObject) for desktop notifications on any
  failures/errors

Start the script by hand or install it as a dbus service file (so it will be
started anytime when message for it will arive) like this:

    cp dbus-lastfm-scrobbler.py /usr/libexec/dbus-lastfm-scrobbler
    cp net.fraggod.DBusLastFM.service /usr/share/dbus-1/services/

Then it can be used from any dbus-enabled thing, for example with dbus-send util:

    dbus-send --session --print-reply --type=method_call\
      --dest=net.fraggod.DBusLastFM /net/fraggod/DBusLastFM\
      net.fraggod.DBusLastFM.ReportNowPlaying
      string:'Some Artist' string:'Whatever Album' string:'Track Title' uint32:173

or from emacs:

    (let
      ((artist "Some Artist")
        (album "Whatever Album")
        (title "Track Title")
        (duration 173))
      (dbus-call-method :session
        "net.fraggod.DBusLastFM"
        "/net/fraggod/DBusLastFM"
        "net.fraggod.DBusLastFM"
        "Scrobble"
        :string artist
        :string album
        :string title
        :uint32 duration
        :double (- (float-time) duration))) ;; when track *started* playing

(extended emacs example can be found in [my emacs-setup
repo](https://github.com/mk-fg/emacs-setup/blob/master/core/fg_emms.el))

Methods and signatures can be looked up in the code, too lazy to add
introspection atm.

Some available command-line flags can be seen in ./dbus-lastfm-scrobbler.py -h.
