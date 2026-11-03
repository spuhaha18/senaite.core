# -*- coding: utf-8 -*-

from bika.lims import api
from plone.protect import CheckAuthenticator
from Products.CMFCore.utils import _checkPermission
from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from senaite.core.i18n import translate as _translate
from senaite.pharma import _
from senaite.pharma import stability
from senaite.pharma.browser.esign import ESignView
from senaite.pharma.browser.esign import get_action_title
from senaite.pharma.browser.esign import get_signature_infos
from senaite.pharma.config import PULL_STATUSES
from senaite.pharma.config import STUDY_TYPES
from senaite.pharma.permissions import PullStabilitySamples

STATUS_TITLES = dict(PULL_STATUSES)
STATUS_TITLES.update({
    "due": _(u"Due"),
    "overdue": _(u"Overdue"),
})

STATUS_CSS = {
    "scheduled": "badge-light",
    "due": "badge-warning",
    "overdue": "badge-danger",
    "pulled": "badge-success",
    "cancelled": "badge-secondary",
}

ACTION_CSS = {
    "activate": "btn-primary",
    "complete": "btn-success",
    "approve_report": "btn-info",
    "cancel": "btn-outline-danger",
}


def translate(msg):
    """Translate to unicode (status messages and templates need unicode)
    """
    return _translate(msg, to_utf8=False)


def format_date(value):
    if not value:
        return u""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return api.safe_unicode(value)[:10]


class StabilityStudyView(BrowserView):
    """Main view of a stability study
    """
    template = ViewPageTemplateFile("templates/study.pt")

    def __call__(self):
        form = self.request.form
        if form.get("form.button.pull") or form.get("form.button.skip"):
            CheckAuthenticator(self.request)
            self.handle_pulls(form)
            self.request.response.redirect(api.get_url(self.context))
            return u""
        return self.template()

    def add_message(self, message, level="info"):
        self.context.plone_utils.addPortalMessage(translate(message), level)

    # -- Actions -------------------------------------------------------------

    def can_pull(self):
        if api.get_review_status(self.context) != "active":
            return False
        return _checkPermission(PullStabilitySamples, self.context)

    def handle_pulls(self, form):
        if not self.can_pull():
            self.add_message(_(u"You are not allowed to pull samples"),
                             "error")
            return
        entry_ids = form.get("entries") or []
        if isinstance(entry_ids, basestring):  # noqa: F821 (py2)
            entry_ids = [entry_ids]
        remarks = api.safe_unicode(form.get("remarks", u"")).strip()
        if not entry_ids:
            self.add_message(_(u"No time points selected"), "warning")
            return
        if form.get("form.button.skip"):
            if not remarks:
                self.add_message(_(u"A reason is required to cancel time "
                                   u"points"), "error")
                return
            cancelled = stability.cancel_pulls(self.context, entry_ids,
                                               remarks)
            self.add_message(_(u"${count} time point(s) cancelled",
                               mapping={"count": len(cancelled)}))
            return
        samples = stability.pull(self.context, entry_ids, self.request,
                                 remarks)
        ids = u", ".join([api.get_id(sample) for sample in samples])
        self.add_message(_(u"Samples created: ${ids}",
                           mapping={"ids": ids}))

    def get_signed_actions(self):
        """Returns the signed actions available for the current user
        """
        view = ESignView(self.context, self.request)
        base_url = api.get_url(self.context)
        return [{
            "id": action,
            "title": get_action_title(action),
            "url": "{}/esign?action={}".format(base_url, action),
            "css": ACTION_CSS.get(action, "btn-secondary"),
        } for action in view.get_allowed_actions()]

    # -- Data ----------------------------------------------------------------

    def get_state_title(self):
        wf = api.get_tool("portal_workflow")
        state = api.get_review_status(self.context)
        title = wf.getTitleForStateOnType(state, "StabilityStudy")
        return translate(_(api.safe_unicode(title)))

    def get_protocol(self):
        study = self.context

        def title(obj):
            if obj is None:
                return u""
            return api.safe_unicode(api.get_title(obj) or api.get_id(obj))

        def url(obj):
            return api.get_url(obj) if obj is not None else None

        contact = study.getContact()
        client = study.getClient()
        sampletype = study.getSampleType()
        spec = study.getSpecification()
        batch = study.getBatch()
        return [
            (_(u"Protocol number"), study.getProtocolID(), None),
            (_(u"Product name"), study.getProductName(), None),
            (_(u"Sample type"), title(sampletype), url(sampletype)),
            (_(u"Lot / batch number(s)"), study.getLotNumbers(), None),
            (_(u"Manufacturing date"),
             format_date(study.getManufacturingDate()), None),
            (_(u"Container closure system"), study.getContainerClosure(),
             None),
            (_(u"Client"), title(client), url(client)),
            (_(u"Requesting client contact"),
             contact.getFullname() if contact is not None else u"", None),
            (_(u"Study start date (T0)"), format_date(study.getStartDate()),
             None),
            (_(u"Pull window (\u00b1 days)"), study.getPullWindow(), None),
            (_(u"Specification"), title(spec), url(spec)),
            (_(u"Batch"), api.get_id(batch) if batch is not None else u"",
             url(batch)),
        ]

    def get_conditions(self):
        types = dict(STUDY_TYPES)
        conditions = []
        for condition in self.context.getConditions():
            condition["study_type_title"] = types.get(
                condition.get("study_type"), condition.get("study_type"))
            condition["months_label"] = u", ".join(
                [stability.format_month(m) for m in condition["months"]])
            conditions.append(condition)
        return conditions

    def get_services(self):
        return [{
            "title": api.safe_unicode(service.Title()),
            "keyword": service.getKeyword(),
            "unit": service.getUnit(),
        } for service in self.context.getServices()]

    def get_schedule(self):
        schedule = []
        for entry in self.context.getSchedule():
            status = stability.get_pull_status(entry)
            entry["status_effective"] = status
            entry["status_title"] = STATUS_TITLES.get(status, status)
            entry["status_css"] = STATUS_CSS.get(status, "badge-light")
            entry["condition_title"] = entry.get("condition") or translate(
                _(u"Initial (all conditions)"))
            entry["selectable"] = entry["status"] == "scheduled"
            sample_uid = entry.get("sample_uid")
            sample = api.get_object_by_uid(sample_uid, default=None) \
                if sample_uid else None
            entry["sample_url"] = api.get_url(sample) \
                if sample is not None else None
            entry["sample_state"] = api.get_review_status(sample) \
                if sample is not None else u""
            schedule.append(entry)
        return schedule

    def get_results_matrix(self):
        return stability.get_results_matrix(self.context)

    def get_signatures(self):
        return get_signature_infos(self.context)

    def get_reports(self):
        base_url = api.get_url(self.context)
        reports = []
        for report in reversed(self.context.getApprovedReports()):
            report = dict(report)
            report["url"] = "{}/stability_report_download?id={}".format(
                base_url, report["id"])
            reports.append(report)
        return reports
