# -*- coding: utf-8 -*-

from senaite.pharma import _

# ICH Q1A(R2) storage conditions with their typical testing frequency
# (months). Used to pre-fill new stability studies.
ICH_CONDITIONS = [
    {
        "condition": u"25°C ± 2°C / 60% RH ± 5% RH",
        "study_type": u"long_term",
        "timepoints": u"0, 3, 6, 9, 12, 18, 24, 36",
        "storage": u"",
    }, {
        "condition": u"30°C ± 2°C / 65% RH ± 5% RH",
        "study_type": u"intermediate",
        "timepoints": u"0, 6, 9, 12",
        "storage": u"",
    }, {
        "condition": u"40°C ± 2°C / 75% RH ± 5% RH",
        "study_type": u"accelerated",
        "timepoints": u"0, 3, 6",
        "storage": u"",
    },
]

# Study types of a storage condition
STUDY_TYPES = (
    ("long_term", _(u"Long-term")),
    ("intermediate", _(u"Intermediate")),
    ("accelerated", _(u"Accelerated")),
    ("stress", _(u"Stress / Forced degradation")),
    ("photostability", _(u"Photostability")),
    ("in_use", _(u"In-use")),
    ("other", _(u"Other")),
)

# Status of a time point (pull) in the schedule
PULL_SCHEDULED = "scheduled"
PULL_PULLED = "pulled"
PULL_CANCELLED = "cancelled"

PULL_STATUSES = (
    (PULL_SCHEDULED, _(u"Scheduled")),
    (PULL_PULLED, _(u"Pulled")),
    (PULL_CANCELLED, _(u"Cancelled")),
)

# Signature meanings (21 CFR 11.50 (a)(3))
SIGNATURE_MEANINGS = (
    ("authored", _(u"Authored")),
    ("reviewed", _(u"Reviewed")),
    ("approved", _(u"Approved")),
    ("verified", _(u"Verified")),
    ("responsibility", _(u"Responsibility")),
)

# Workflow transitions of the stability study that require an electronic
# signature, with the meaning that is recorded with the signature
STUDY_SIGNED_ACTIONS = {
    "activate": "approved",
    "complete": "approved",
    "cancel": "responsibility",
    "approve_report": "approved",
}

# Electronic signature lockout policy (21 CFR 11.300 (d)): after this number
# of consecutive failed signature attempts, the user is not allowed to sign
# for the given amount of minutes
ESIGN_MAX_FAILED_ATTEMPTS = 3
ESIGN_LOCKOUT_MINUTES = 30

# Review states of analyses that are considered final for reports
FINAL_ANALYSIS_STATES = ("verified", "published")

# Review states of analyses that are ignored in the results matrix
IGNORED_ANALYSIS_STATES = ("retracted", "rejected", "cancelled")
