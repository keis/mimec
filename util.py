from gi.repository import GObject


def defer(fun, *args, **kwargs):
    def _wrap():
        fun(*args, **kwargs)
        return False
    GObject.idle_add(_wrap)
