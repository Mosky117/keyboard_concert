"""Stub of solaar.configuration — a per-device settings persister.

logitech_receiver uses the persister purely as a dict (`.get`, `in`, `[]=`), so a
plain dict subclass suffices. keyboard_concert keeps its own config separately and doesn't
rely on Solaar's on-disk device settings, so this never touches the filesystem.
"""


class _Persister(dict):
    def save(self, *args, **kwargs):
        pass


def persister(device):
    return _Persister()


def save(*args, **kwargs):
    pass
