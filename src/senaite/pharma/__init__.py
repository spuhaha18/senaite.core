# -*- coding: utf-8 -*-
"""SENAITE PHARMA

Pharmaceutical laboratory extensions for SENAITE:

- Stability studies (ICH Q1A(R2) style protocols, pull schedules, results
  trending and stability reports)
- Electronic signatures (21 CFR Part 11 / EU GMP Annex 11 style: re-entry
  of credentials, signature meaning, record linking and signature log)
- PDF report output for stability studies
"""

import logging

from zope.i18nmessageid import MessageFactory

PRODUCT_NAME = "senaite.pharma"
PROFILE_ID = "profile-senaite.pharma:default"

logger = logging.getLogger(PRODUCT_NAME)

# Message factory for this package
_ = MessageFactory(PRODUCT_NAME)


def initialize(context):
    """Initializer called when used as a Zope 2 product."""
    logger.info("*** Initializing SENAITE PHARMA ***")
