# -*- coding: utf-8 -*-
"""Stability report: HTML preview, PDF output and approved (frozen) reports
"""

import hashlib
import uuid

from bika.lims import api
from persistent.mapping import PersistentMapping
from plone.namedfile.file import NamedBlobFile
from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from senaite.pharma import logger
from senaite.pharma.browser.esign import get_signature_infos
from senaite.pharma.browser.study import StabilityStudyView
from senaite.pharma.browser.study import format_date
from senaite.pharma.esign import now
from senaite.pharma.esign import to_iso


def html_to_pdf(html, base_url=None):
    """Converts the HTML to PDF with WeasyPrint
    """
    # WeasyPrint is a dependency of senaite.impress
    from weasyprint import HTML
    if isinstance(html, unicode):  # noqa: F821 (py2)
        html = html.encode("utf-8")
    return HTML(string=html, base_url=base_url, encoding="utf-8").write_pdf()


def get_laboratory_name():
    """Returns the name of the laboratory
    """
    try:
        setup = api.get_senaite_setup()
        lab = setup.get("laboratory") if setup else None
    except Exception:  # noqa
        lab = None
    if lab is None:
        lab = getattr(api.get_bika_setup(), "laboratory", None)
    return api.safe_unicode(lab.Title()) if lab is not None else u""


class StabilityReportView(StabilityStudyView):
    """Printable stability report (HTML)
    """
    template = ViewPageTemplateFile("templates/report.pt")

    # set to True when rendering for PDF output
    for_pdf = False

    # set to True when rendering the approved (signed) report
    approved = False

    def __call__(self):
        return self.template()

    def is_final(self):
        return api.get_review_status(self.context) == "completed"

    def get_laboratory_name(self):
        return get_laboratory_name()

    def get_print_date(self):
        return to_iso(now())

    def get_report_signatures(self):
        """Signatures shown in the report (study approval and completion and
        report approvals)
        """
        return get_signature_infos(self.context)

    def get_pull_date(self, entry):
        return format_date(entry.get("pulled_date"))

    def render_pdf(self):
        self.for_pdf = True
        html = self.template()
        return html_to_pdf(html, base_url=api.get_url(self.context))

    def get_pdf_filename(self):
        study = self.context
        name = u"{}-{}".format(study.getProtocolID() or api.get_id(study),
                               "final" if self.is_final() else "interim")
        return name.replace(u"/", u"-").replace(u" ", u"_") + u".pdf"


class StabilityReportPDFView(StabilityReportView):
    """Stability report as PDF (draft, not signed)
    """

    def __call__(self):
        pdf = self.render_pdf()
        filename = self.get_pdf_filename()
        response = self.request.response
        response.setHeader("Content-Type", "application/pdf")
        response.setHeader(
            "Content-Disposition",
            "inline; filename=\"{}\"".format(filename.encode("utf-8")))
        return pdf


class StabilityReportDownloadView(BrowserView):
    """Download of an approved (frozen) report
    """

    def __call__(self):
        report_id = self.request.form.get("id")
        for report in self.context.getApprovedReports():
            if report["id"] != report_id:
                continue
            blob = report["file"]
            response = self.request.response
            response.setHeader("Content-Type", "application/pdf")
            response.setHeader(
                "Content-Disposition",
                "inline; filename=\"{}\"".format(
                    blob.filename.encode("utf-8")))
            return blob.data
        self.request.response.setStatus(404)
        return u"Report not found"


def approve_report(study, request, signature):
    """Generates the PDF of the stability report, including the given
    approval signature, and stores it frozen in the study
    """
    view = StabilityReportView(study, request)
    view.approved = True
    pdf = view.render_pdf()
    filename = view.get_pdf_filename()
    report = PersistentMapping({
        "id": uuid.uuid4().hex,
        "date": signature["date"],
        "kind": "final" if view.is_final() else "interim",
        "signature_id": signature["id"],
        "signed_by": signature["fullname"],
        "filename": filename,
        "sha256": hashlib.sha256(pdf).hexdigest(),
        "record_hash": signature["record_hash"],
        "file": NamedBlobFile(data=pdf, contentType="application/pdf",
                              filename=filename),
    })
    study.addApprovedReport(report)
    logger.info("Approved stability report {} of {} (sha256 {})".format(
        filename, api.get_path(study), report["sha256"]))
    return report
