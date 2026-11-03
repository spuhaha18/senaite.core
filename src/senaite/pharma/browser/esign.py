# -*- coding: utf-8 -*-
"""Views for electronic signatures
"""

from bika.lims import api
from plone.protect import CheckAuthenticator
from Products.CMFCore.utils import _checkPermission
from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from senaite.core.i18n import translate as _translate
from senaite.pharma import _
from senaite.pharma import esign
from senaite.pharma.config import SIGNATURE_MEANINGS
from senaite.pharma.config import STUDY_SIGNED_ACTIONS
from senaite.pharma.interfaces import IStabilityStudy
from senaite.pharma.permissions import ApproveStabilityStudy
from senaite.pharma.permissions import SignElectronically
from senaite.pharma.stability import SCOPE_PROTOCOL


def translate(msg):
    """Translate to unicode (status messages and templates need unicode)
    """
    return _translate(msg, to_utf8=False)


def get_action_title(action):
    titles = {
        "activate": _(u"Approve and start the study"),
        "complete": _(u"Complete the study"),
        "cancel": _(u"Cancel the study"),
        "approve_report": _(u"Approve the stability report"),
        "": _(u"Sign the record"),
    }
    return titles.get(action, action)


def get_signature_infos(obj):
    """Returns the signatures of the object prepared for display
    """
    infos = []
    for signature in esign.get_signatures(obj):
        info = dict(signature)
        info["meaning_title"] = translate(
            esign.get_meaning_title(signature.get("meaning")))
        info["action_title"] = translate(
            get_action_title(signature.get("action") or ""))
        info["valid"] = esign.is_signature_valid(obj, signature)
        infos.append(info)
    return infos


class ESignView(BrowserView):
    """Electronic signature form

    Asks the signer for the password (re-authentication), the meaning of the
    signature and an optional comment. On success, the signature is stored
    and the signed action (e.g. a workflow transition) is executed.
    """
    template = ViewPageTemplateFile("templates/esign.pt")

    def __init__(self, context, request):
        super(ESignView, self).__init__(context, request)
        self.errors = []

    def __call__(self):
        form = self.request.form
        self.action = form.get("action", "")
        if self.action not in self.get_allowed_actions():
            return self.redirect(_(u"This action is not allowed"), "error")

        if form.get("form.button.cancel"):
            return self.redirect()

        if form.get("form.button.sign"):
            CheckAuthenticator(self.request)
            result = self.handle_sign(form)
            if result is not None:
                return result

        return self.template()

    # -- Form data -----------------------------------------------------------

    @property
    def is_study(self):
        return IStabilityStudy.providedBy(self.context)

    def get_allowed_actions(self):
        """Returns the actions the current user can sign on this record
        """
        if not _checkPermission(SignElectronically, self.context):
            return []
        if not self.is_study:
            return [""]
        if not _checkPermission(ApproveStabilityStudy, self.context):
            return []
        state = api.get_review_status(self.context)
        actions = {
            "draft": ["activate", "cancel"],
            "active": ["complete", "cancel", "approve_report"],
            "completed": ["approve_report"],
        }
        return actions.get(state, [])

    def get_action_title(self):
        return get_action_title(self.action)

    def get_fixed_meaning(self):
        """Returns the meaning of the signature when it is given by the action
        """
        return STUDY_SIGNED_ACTIONS.get(self.action)

    def get_meanings(self):
        fixed = self.get_fixed_meaning()
        selected = self.request.form.get("meaning") or fixed or "reviewed"
        return [{
            "value": value,
            "title": title,
            "selected": value == selected,
        } for value, title in SIGNATURE_MEANINGS
            if not fixed or value == fixed]

    def show_conclusion(self):
        return self.action == "complete"

    def get_conclusion(self):
        if "conclusion" in self.request.form:
            return self.request.form.get("conclusion")
        if self.is_study:
            return self.context.getConclusion()
        return u""

    def get_signer(self):
        user = api.get_current_user()
        return {
            "userid": user.getId(),
            "fullname": api.safe_unicode(
                user.getProperty("fullname") or user.getId()),
        }

    def get_record_title(self):
        return api.safe_unicode(api.get_title(self.context))

    def get_locked_until(self):
        user = api.get_current_user()
        locked = esign.get_locked_until(user.getId())
        return esign.to_iso(locked) if locked else None

    # -- Form handling -------------------------------------------------------

    def handle_sign(self, form):
        password = form.get("password", "")
        comment = form.get("comment", "").strip()
        meaning = self.get_fixed_meaning() or form.get("meaning")

        if not form.get("certify"):
            self.errors.append(_(
                u"Please confirm that the electronic signature is the "
                u"legally binding equivalent of your handwritten signature"))
        if self.action == "cancel" and not comment:
            self.errors.append(_(u"A reason is required for cancellation"))
        if self.action == "complete":
            from senaite.pharma.stability import get_unfinished_samples
            unfinished = get_unfinished_samples(self.context)
            if unfinished:
                self.errors.append(_(
                    u"The study can not be completed before the results of "
                    u"all pulled samples are verified: ${ids}",
                    mapping={"ids": u", ".join(map(api.get_id, unfinished))}))
        if self.action == "complete" and not form.get("conclusion", ""):
            self.errors.append(_(u"A conclusion is required to complete "
                                 u"the study"))
        if self.errors:
            return None

        # Values of the record that are part of the signed content need to be
        # set before signing, so that they are covered by the fingerprint
        old_conclusion = None
        if self.action == "complete":
            old_conclusion = self.context.getConclusion()
            self.context.setConclusion(form.get("conclusion"))

        # The approval of the study covers the protocol only
        scope = SCOPE_PROTOCOL if self.action == "activate" else None

        try:
            signature = esign.sign(self.context, password, meaning,
                                   action=self.action, comment=comment,
                                   scope=scope)
        except esign.SignatureError as exc:
            if old_conclusion is not None:
                self.context.setConclusion(old_conclusion)
            if exc.outcome == esign.OUTCOME_LOCKED:
                self.errors.append(_(
                    u"You are temporarily locked out of signing because of "
                    u"repeated failed attempts. Please contact your lab "
                    u"manager."))
            elif exc.outcome == esign.OUTCOME_WRONG_PASSWORD:
                self.errors.append(_(u"The password is not correct. The "
                                     u"failed attempt has been logged."))
            else:
                self.errors.append(api.safe_unicode(exc.message))
            return None

        self.perform_action(signature)
        message = _(u"Signed electronically by ${name}",
                    mapping={"name": signature["fullname"]})
        return self.redirect(message)

    def perform_action(self, signature):
        """Executes the signed action
        """
        if not self.is_study:
            return
        # Imported here to avoid circular imports
        from senaite.pharma.browser.report import approve_report
        from senaite.pharma.stability import build_schedule
        study = self.context
        if self.action == "approve_report":
            approve_report(study, self.request, signature)
            return
        if self.action == "activate":
            study.setSchedule(build_schedule(study))
        self.request.set("senaite_pharma_esign", self.action)
        try:
            api.do_transition_for(study, self.action)
        finally:
            self.request.set("senaite_pharma_esign", None)
        if self.action in ("complete", "cancel"):
            # close the time points that were not pulled
            from senaite.pharma.stability import cancel_pulls
            open_ids = [e["id"] for e in study.getSchedule()
                        if e["status"] == "scheduled"]
            remarks = translate(_(u"Study completed")) \
                if self.action == "complete" \
                else translate(_(u"Study cancelled"))
            cancel_pulls(study, open_ids, remarks)
        study.reindexObject()

    def redirect(self, message=None, level="info"):
        if message:
            self.context.plone_utils.addPortalMessage(
                translate(message), level)
        url = self.request.form.get("came_from") or api.get_url(self.context)
        self.request.response.redirect(url)
        return u""


class SignaturesView(BrowserView):
    """Signature manifestations of a record
    """
    template = ViewPageTemplateFile("templates/signatures.pt")

    def __call__(self):
        return self.template()

    def get_signatures(self):
        return get_signature_infos(self.context)

    def can_sign(self):
        if IStabilityStudy.providedBy(self.context):
            return False
        return _checkPermission(SignElectronically, self.context)


class SignatureLogView(BrowserView):
    """Site wide log of all signature attempts
    """
    template = ViewPageTemplateFile("templates/signature_log.pt")

    def __call__(self):
        form = self.request.form
        if form.get("unlock"):
            CheckAuthenticator(self.request)
            esign.unlock_user(form.get("unlock"))
            self.context.plone_utils.addPortalMessage(
                translate(_(u"User ${user} has been unlocked",
                            mapping={"user": form.get("unlock")})))
        return self.template()

    def get_log(self):
        log = esign.get_signature_log()
        for entry in log:
            entry["meaning_title"] = translate(
                esign.get_meaning_title(entry.get("meaning")))
            entry["locked_until"] = None
        return log[:500]

    def get_locked_users(self):
        users = set([e["userid"] for e in esign.get_signature_log()])
        locked = []
        for userid in sorted(users):
            until = esign.get_locked_until(userid)
            if until:
                locked.append({"userid": userid,
                               "until": esign.to_iso(until)})
        return locked
