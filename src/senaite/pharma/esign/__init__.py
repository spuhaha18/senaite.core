# -*- coding: utf-8 -*-
"""Electronic signatures

Implements electronic signatures in the spirit of 21 CFR Part 11 and
EU GMP Annex 11:

- Each signing requires the re-entry of the password of the logged-in user
  (11.200 (a)(1)); the signature can not be executed by anyone else.
- The signature manifestation contains the printed name of the signer, the
  date and time of signing and the meaning of the signature (11.50).
- The signature is linked to the record by a SHA-256 fingerprint of the
  record content taken at signing time (11.70). Later changes of the record
  are detected and shown.
- Signatures are stored append-only on the record. Every attempt, successful
  or not, is written to a site wide signature log, and users are locked out
  of signing after repeated failures (11.300 (d)).
"""

import hashlib
import json
import uuid
from datetime import datetime
from datetime import timedelta

from BTrees.OOBTree import OOBTree
from bika.lims import api
from plone import api as ploneapi
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping
from Products.PluggableAuthService.interfaces.plugins import \
    IAuthenticationPlugin
from senaite.pharma import logger
from senaite.pharma.config import ESIGN_LOCKOUT_MINUTES
from senaite.pharma.config import ESIGN_MAX_FAILED_ATTEMPTS
from senaite.pharma.config import SIGNATURE_MEANINGS
from senaite.pharma.interfaces import IRecordFingerprint
from zope.annotation.interfaces import IAnnotations
from zope.component import queryAdapter

SIGNATURES_KEY = "senaite.pharma.esignatures"
SIGNATURE_LOG_KEY = "senaite.pharma.esignature_log"
LOCKOUT_KEY = "senaite.pharma.esignature_lockout"

# Outcomes for the signature log
OUTCOME_SIGNED = "signed"
OUTCOME_WRONG_PASSWORD = "wrong_password"
OUTCOME_LOCKED = "locked"


class SignatureError(Exception):
    """Raised when an electronic signature can not be executed
    """

    def __init__(self, message, outcome=None):
        super(SignatureError, self).__init__(message)
        self.message = message
        self.outcome = outcome


def now():
    """Returns the current local date time as naive datetime
    """
    return datetime.now()


def to_iso(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def from_iso(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def get_meaning_title(meaning):
    """Returns the (translatable) title of the signature meaning
    """
    return dict(SIGNATURE_MEANINGS).get(meaning, meaning)


# -----------------------------------------------------------------------------
# Record fingerprint
# -----------------------------------------------------------------------------

def to_json(data):
    """Stable JSON serialization used for fingerprints
    """
    return json.dumps(data, sort_keys=True, default=api.safe_unicode,
                      separators=(",", ":"))


def hash_data(data):
    """Returns the SHA-256 hex digest of the given data structure
    """
    payload = to_json(data)
    if isinstance(payload, unicode):  # noqa: F821 (py2)
        payload = payload.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def get_fingerprint(obj, scope=None):
    """Returns the fingerprint of the record content

    :param scope: optional name of the part of the record that is covered,
        e.g. "protocol" for the approval of a stability protocol
    """
    adapter = queryAdapter(obj, IRecordFingerprint)
    if adapter is not None:
        return adapter(scope=scope)
    # Fallback: hash the UID and the modification date
    return hash_data({
        "uid": api.get_uid(obj),
        "modified": str(api.get_modification_date(obj)),
    })


# -----------------------------------------------------------------------------
# Signature storage
# -----------------------------------------------------------------------------

def get_signatures(obj):
    """Returns the list of signatures (dicts) of the given object, oldest first
    """
    annotations = IAnnotations(obj)
    signatures = annotations.get(SIGNATURES_KEY) or []
    return [dict(signature) for signature in signatures]


def get_last_signature(obj, action=None):
    """Returns the latest signature, optionally for the given action
    """
    signatures = get_signatures(obj)
    if action:
        signatures = filter(lambda s: s.get("action") == action, signatures)
    return signatures[-1] if signatures else None


def is_signature_valid(obj, signature):
    """Checks if the record is unchanged since the signature was given
    """
    scope = signature.get("scope")
    return signature.get("record_hash") == get_fingerprint(obj, scope=scope)


def _append_signature(obj, signature):
    annotations = IAnnotations(obj)
    if annotations.get(SIGNATURES_KEY) is None:
        annotations[SIGNATURES_KEY] = PersistentList()
    annotations[SIGNATURES_KEY].append(PersistentMapping(signature))


# -----------------------------------------------------------------------------
# Signature log and lockout
# -----------------------------------------------------------------------------

def get_signature_log():
    """Returns the site wide signature log (newest first)
    """
    annotations = IAnnotations(api.get_portal())
    log = annotations.get(SIGNATURE_LOG_KEY) or []
    return list(reversed([dict(entry) for entry in log]))


def log_attempt(obj, userid, outcome, action="", meaning="", comment=""):
    """Writes an entry to the site wide signature log
    """
    annotations = IAnnotations(api.get_portal())
    if annotations.get(SIGNATURE_LOG_KEY) is None:
        annotations[SIGNATURE_LOG_KEY] = PersistentList()
    entry = {
        "date": to_iso(now()),
        "userid": userid,
        "outcome": outcome,
        "action": action,
        "meaning": meaning,
        "comment": comment,
        "uid": api.get_uid(obj),
        "path": api.get_path(obj),
        "title": api.safe_unicode(api.get_title(obj)),
        "portal_type": api.get_portal_type(obj),
    }
    annotations[SIGNATURE_LOG_KEY].append(PersistentMapping(entry))
    level = logger.info if outcome == OUTCOME_SIGNED else logger.warning
    level("E-signature {outcome}: user={userid} action={action} "
          "path={path}".format(**entry))


def _get_lockout_storage():
    annotations = IAnnotations(api.get_portal())
    if annotations.get(LOCKOUT_KEY) is None:
        annotations[LOCKOUT_KEY] = OOBTree()
    return annotations[LOCKOUT_KEY]


def get_locked_until(userid):
    """Returns the datetime until the user is locked out of signing or None
    """
    record = _get_lockout_storage().get(userid)
    if not record or not record.get("locked_until"):
        return None
    locked_until = from_iso(record["locked_until"])
    if locked_until < now():
        return None
    return locked_until


def _register_failure(userid):
    storage = _get_lockout_storage()
    record = PersistentMapping(storage.get(userid) or {})
    failures = record.get("failures", 0) + 1
    record["failures"] = failures
    if failures >= ESIGN_MAX_FAILED_ATTEMPTS:
        until = now() + timedelta(minutes=ESIGN_LOCKOUT_MINUTES)
        record["locked_until"] = to_iso(until)
        record["failures"] = 0
    storage[userid] = record
    return failures


def _reset_failures(userid):
    storage = _get_lockout_storage()
    if userid in storage:
        del storage[userid]


def unlock_user(userid):
    """Removes a signing lockout of the given user
    """
    _reset_failures(userid)


# -----------------------------------------------------------------------------
# Authentication
# -----------------------------------------------------------------------------

def verify_credentials(user, password):
    """Verifies the password of the given user against all PAS
    authentication plugins. Returns True if the credentials are valid and
    belong to the given user.
    """
    if not password:
        return False
    acl_users = api.get_tool("acl_users")
    login = user.getUserName()
    credentials = {"login": login, "password": password}
    plugins = acl_users.plugins.listPlugins(IAuthenticationPlugin)
    for plugin_id, plugin in plugins:
        try:
            result = plugin.authenticateCredentials(credentials)
        except Exception:  # noqa: plugins may raise anything
            logger.exception("Authentication plugin {} failed"
                             .format(plugin_id))
            continue
        if result and result[0] == user.getId():
            return True
    return False


# -----------------------------------------------------------------------------
# Signing
# -----------------------------------------------------------------------------

def sign(obj, password, meaning, action="", comment=u"", user=None,
         scope=None):
    """Signs the object electronically on behalf of the current user

    :param obj: the record to sign
    :param password: the password re-entered by the signer
    :param meaning: the meaning of the signature (see SIGNATURE_MEANINGS)
    :param action: the action (e.g. workflow transition) that is signed
    :param comment: optional reason/comment of the signer
    :param scope: part of the record covered by the signature fingerprint
    :returns: the signature (dict)
    :raises: SignatureError
    """
    if meaning not in dict(SIGNATURE_MEANINGS):
        raise SignatureError("Invalid signature meaning '{}'".format(meaning))

    user = user or ploneapi.user.get_current()
    if user is None or ploneapi.user.is_anonymous():
        raise SignatureError("Anonymous users can not sign")
    userid = user.getId()

    locked_until = get_locked_until(userid)
    if locked_until:
        log_attempt(obj, userid, OUTCOME_LOCKED, action, meaning, comment)
        raise SignatureError(
            "Signing is locked until {}".format(to_iso(locked_until)),
            outcome=OUTCOME_LOCKED)

    if not verify_credentials(user, password):
        _register_failure(userid)
        log_attempt(obj, userid, OUTCOME_WRONG_PASSWORD, action, meaning,
                    comment)
        raise SignatureError("Invalid password",
                             outcome=OUTCOME_WRONG_PASSWORD)

    _reset_failures(userid)

    fullname = user.getProperty("fullname") or userid
    signature = {
        "id": uuid.uuid4().hex,
        "userid": userid,
        "fullname": api.safe_unicode(fullname),
        "meaning": meaning,
        "action": action,
        "comment": api.safe_unicode(comment or u""),
        "date": to_iso(now()),
        "record_hash": get_fingerprint(obj, scope=scope),
        "scope": scope,
        "record_id": api.get_id(obj),
    }
    _append_signature(obj, signature)
    log_attempt(obj, userid, OUTCOME_SIGNED, action, meaning, comment)
    return signature
