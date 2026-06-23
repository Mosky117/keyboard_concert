"""Stub of solaar.i18n — pass-through translation helpers (no localization)."""

import gettext as _gettext


def _(text):
    return text


def ngettext(singular, plural, n):
    return singular if n == 1 else plural


def C_(context, text):
    return text


# Some code paths may reference a gettext translation object; provide a null one.
translation = _gettext.NullTranslations()
