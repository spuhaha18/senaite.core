# -*- coding: utf-8 -*-

from senaite.core.interfaces import ISenaiteCore
from zope.interface import Interface


class ISenaitePharmaLayer(ISenaiteCore):
    """Browser layer of senaite.pharma
    """


class IStabilityStudies(Interface):
    """Marker interface for the stability studies root folder
    """


class IStabilityStudy(Interface):
    """Marker interface for a stability study
    """


class ISignable(Interface):
    """Marker interface for objects that can be signed electronically
    """


class IRecordFingerprint(Interface):
    """Adapter that computes a fingerprint (hash) of the record content

    The fingerprint is stored with each electronic signature, so that the
    signature is linked to the exact content of the record that was signed
    (21 CFR 11.70). If the record changes later, the stored hash no longer
    matches and the signature is flagged accordingly.
    """

    def __call__(scope=None):
        """Return a hex digest of the current record content

        :param scope: optional name of the part of the record to cover
        """
