# -*- coding: utf-8 -*-
"""Stability study logic: pull schedule, sample pulls and results matrix
"""

import calendar
from collections import OrderedDict
from datetime import date
from datetime import timedelta

from bika.lims import api
from bika.lims.api.analysis import get_formatted_interval
from bika.lims.api.analysis import is_out_of_range
from bika.lims.utils.analysisrequest import create_analysisrequest
from DateTime import DateTime
from senaite.pharma import logger
from senaite.pharma.config import FINAL_ANALYSIS_STATES
from senaite.pharma.config import IGNORED_ANALYSIS_STATES
from senaite.pharma.config import PULL_CANCELLED
from senaite.pharma.config import PULL_PULLED
from senaite.pharma.config import PULL_SCHEDULED
from senaite.pharma.esign import hash_data
from senaite.pharma.esign import now
from senaite.pharma.esign import to_iso

# Key of the shared initial time point (T0)
INITIAL_KEY = "T0"


def to_date(value):
    """Converts a date/datetime/DateTime to a datetime.date
    """
    if value is None:
        return None
    if isinstance(value, DateTime):
        return value.asdatetime().date()
    if hasattr(value, "date") and callable(value.date):
        return value.date()
    if isinstance(value, date):
        return value
    return api.to_date(value).asdatetime().date()


def add_months(start, months):
    """Adds the (possibly fractional) number of months to the given date.
    Fractions are converted to days (1 month = 30 days)

    >>> add_months(date(2026, 1, 31), 1)
    datetime.date(2026, 2, 28)
    """
    whole = int(months)
    rest = months - whole
    month_index = start.month - 1 + whole
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    result = date(year, month, day)
    if rest:
        result += timedelta(days=int(round(rest * 30)))
    return result


def format_month(month):
    """Returns the label of a time point, e.g. "6M" or "T0"
    """
    if not month:
        return INITIAL_KEY
    return u"{}M".format(month)


def build_schedule(study):
    """Builds the pull schedule of the study from its protocol

    The initial time point (0 months) is shared by all conditions and
    therefore only scheduled once.
    """
    start = to_date(study.getStartDate())
    window = study.getPullWindow()
    entries = []
    has_initial = False

    for index, condition in enumerate(study.getConditions()):
        for month in condition["months"]:
            if not month:
                has_initial = True
                continue
            entries.append({
                "id": u"C{}-{}".format(index + 1, format_month(month)),
                "condition_index": index + 1,
                "condition": condition.get("condition"),
                "study_type": condition.get("study_type"),
                "month": month,
            })

    if has_initial:
        entries.insert(0, {
            "id": INITIAL_KEY,
            "condition_index": 0,
            "condition": u"",
            "study_type": u"",
            "month": 0,
        })

    for entry in entries:
        due = add_months(start, entry["month"])
        entry.update({
            "label": format_month(entry["month"]),
            "due_date": due.isoformat(),
            "window_start": (due - timedelta(days=window)).isoformat(),
            "window_end": (due + timedelta(days=window)).isoformat(),
            "status": PULL_SCHEDULED,
            "sample_uid": None,
            "sample_id": None,
            "pulled_date": None,
            "pulled_by": None,
            "remarks": u"",
        })

    # sort by due date, then by condition
    entries.sort(key=lambda e: (e["due_date"], e["condition_index"]))
    return entries


def get_pull_status(entry, today=None):
    """Returns the effective status of a schedule entry, including the
    calculated states "due" and "overdue" for scheduled entries
    """
    status = entry.get("status")
    if status != PULL_SCHEDULED:
        return status
    today = today or date.today()
    window_start = date(*map(int, entry["window_start"].split("-")))
    window_end = date(*map(int, entry["window_end"].split("-")))
    if today > window_end:
        return "overdue"
    if today >= window_start:
        return "due"
    return status


def ensure_batch(study):
    """Returns the batch that groups the samples of the study. The batch is
    created when not yet present.
    """
    batch = study.getBatch()
    if batch is not None:
        return batch
    portal = api.get_portal()
    client = study.getClient()
    title = u"{} {}".format(study.getProtocolID(),
                            api.safe_unicode(study.Title())).strip()
    batch = api.create(
        portal.batches, "Batch",
        title=title,
        Client=client,
        ClientBatchID=study.getProtocolID(),
        description=u"Stability study: {}".format(api.get_url(study)),
    )
    study.setBatchUID(api.get_uid(batch))
    return batch


def pull(study, entry_ids, request, remarks=u""):
    """Pulls the given time points: creates one sample per time point with
    the analyses of the study.

    :returns: list of created samples
    """
    client = study.getClient()
    contact = study.getContact()
    sampletype = study.getSampleType()
    if any([obj is None for obj in (client, contact, sampletype)]):
        raise ValueError("Client contact and sample type are required")

    batch = ensure_batch(study)
    service_uids = study.getRawServices()
    specification = study.getSpecification()
    schedule = dict([(e["id"], e) for e in study.getSchedule()])
    user = api.get_current_user()

    samples = []
    for entry_id in entry_ids:
        entry = schedule.get(entry_id)
        if entry is None or entry["status"] != PULL_SCHEDULED:
            continue
        condition = entry.get("condition") or u"Initial"
        values = {
            "Contact": api.get_uid(contact),
            "SampleType": api.get_uid(sampletype),
            "DateSampled": DateTime(),
            "Batch": api.get_uid(batch),
            "ClientSampleID": u"{}/{}".format(
                study.getProtocolID(), entry_id),
            "ClientReference": study.getLotNumbers(),
            "EnvironmentalConditions": condition,
        }
        if remarks:
            values["Remarks"] = remarks
        if specification is not None:
            values["Specification"] = api.get_uid(specification)
        sample = create_analysisrequest(client, request, values,
                                        analyses=service_uids)
        study.updateScheduleEntry(
            entry_id,
            status=PULL_PULLED,
            sample_uid=api.get_uid(sample),
            sample_id=api.get_id(sample),
            pulled_date=to_iso(now()),
            pulled_by=user.getId(),
            remarks=api.safe_unicode(remarks),
        )
        logger.info("Stability pull {} of {}: created sample {}".format(
            entry_id, api.get_path(study), api.get_id(sample)))
        samples.append(sample)
    return samples


def cancel_pulls(study, entry_ids, remarks=u""):
    """Cancels scheduled (not yet pulled) time points
    """
    cancelled = []
    for entry in study.getSchedule():
        if entry["id"] not in entry_ids:
            continue
        if entry["status"] != PULL_SCHEDULED:
            continue
        study.updateScheduleEntry(entry["id"], status=PULL_CANCELLED,
                                  remarks=api.safe_unicode(remarks))
        cancelled.append(entry["id"])
    return cancelled


# Sample states that are considered final for the completion of a study
FINAL_SAMPLE_STATES = ("verified", "published", "invalid", "cancelled",
                       "rejected")


def get_unfinished_samples(study):
    """Returns the pulled samples of the study whose results are not final
    """
    unfinished = []
    for entry in study.getSchedule():
        uid = entry.get("sample_uid")
        sample = api.get_object_by_uid(uid, default=None) if uid else None
        if sample is None:
            continue
        if api.get_review_status(sample) not in FINAL_SAMPLE_STATES:
            unfinished.append(sample)
    return unfinished


# -----------------------------------------------------------------------------
# Results
# -----------------------------------------------------------------------------

def get_valid_analyses(sample):
    """Returns the valid analyses of the sample by keyword. Retests replace
    the retested analyses.
    """
    analyses = OrderedDict()
    for analysis in sample.getAnalyses(full_objects=True):
        if api.get_review_status(analysis) in IGNORED_ANALYSIS_STATES:
            continue
        analyses[analysis.getKeyword()] = analysis
    return analyses


def get_analysis_info(analysis):
    """Returns the result information of the analysis
    """
    state = api.get_review_status(analysis)
    result = analysis.getFormattedResult(html=False)
    if result in (None, ""):
        result = u""
    out_of_range = False
    if result:
        out_of_range = is_out_of_range(analysis)[0]
    return {
        "result": api.safe_unicode(result),
        "unit": api.safe_unicode(analysis.getUnit() or u""),
        "spec": api.safe_unicode(
            get_formatted_interval(analysis.getResultsRange(), u"")),
        "state": state,
        "final": state in FINAL_ANALYSIS_STATES,
        "out_of_range": out_of_range,
        "method": api.safe_unicode(
            analysis.getMethod().Title() if analysis.getMethod() else u""),
    }


def get_results_matrix(study):
    """Returns the results of the study arranged by condition

    The structure returned is::

        {
            "services": [{"keyword", "title", "unit"}],
            "conditions": [{
                "condition", "study_type", "index",
                "timepoints": [{"entry": <schedule entry>,
                                "results": {keyword: info}}]
            }]
        }

    The initial time point is shown as first column of every condition.
    """
    services = []
    for service in study.getServices():
        services.append({
            "keyword": service.getKeyword(),
            "title": api.safe_unicode(service.Title()),
            "unit": api.safe_unicode(service.getUnit() or u""),
        })

    # results per schedule entry
    results = {}
    schedule = study.getSchedule()
    for entry in schedule:
        uid = entry.get("sample_uid")
        sample = api.get_object_by_uid(uid, default=None) if uid else None
        entry_results = {}
        if sample is not None:
            for keyword, analysis in get_valid_analyses(sample).items():
                entry_results[keyword] = get_analysis_info(analysis)
            entry["sample_url"] = api.get_url(sample)
            entry["sample_state"] = api.get_review_status(sample)
        results[entry["id"]] = entry_results

    initial = [e for e in schedule if e["id"] == INITIAL_KEY]
    conditions = []
    for index, condition in enumerate(study.getConditions()):
        index += 1
        entries = [e for e in schedule if e["condition_index"] == index]
        if 0 in condition["months"]:
            entries = initial + entries
        entries.sort(key=lambda e: e["month"])
        timepoints = [{
            "entry": entry,
            "results": results.get(entry["id"], {}),
        } for entry in entries]
        conditions.append({
            "index": index,
            "condition": condition.get("condition"),
            "study_type": condition.get("study_type"),
            "storage": condition.get("storage"),
            "timepoints": timepoints,
        })

    return {
        "services": services,
        "conditions": conditions,
    }


# -----------------------------------------------------------------------------
# Record fingerprint
# -----------------------------------------------------------------------------

# Fingerprint scope that covers only the stability protocol
SCOPE_PROTOCOL = "protocol"


class StudyFingerprint(object):
    """Fingerprint of a stability study

    The scope "protocol" covers the protocol data only (approval of the
    study). Otherwise the fingerprint covers protocol, schedule, conclusion
    and the results of all pulled samples.
    """

    def __init__(self, context):
        self.context = context

    def __call__(self, scope=None):
        study = self.context
        data = {
            "uid": api.get_uid(study),
            "title": api.safe_unicode(study.Title()),
            "protocol_id": study.getProtocolID(),
            "product": study.getProductName(),
            "lots": study.getLotNumbers(),
            "start_date": str(to_date(study.getStartDate())),
            "pull_window": study.getPullWindow(),
            "conditions": [
                {"condition": c.get("condition"),
                 "study_type": c.get("study_type"),
                 "timepoints": c.get("months")}
                for c in study.getConditions()],
            "services": sorted(study.getRawServices()),
            "specification": api.get_uid(study.getSpecification())
            if study.getSpecification() else None,
        }
        if scope == SCOPE_PROTOCOL:
            return hash_data(data)
        data.update({
            "conclusion": study.getConclusion(),
            # only the pulled time points are covered, so that closing the
            # open time points on completion does not alter the record
            "schedule": [
                {"id": e["id"], "sample": e.get("sample_uid")}
                for e in study.getSchedule() if e.get("sample_uid")],
        })
        matrix = get_results_matrix(study) if study.getSchedule() else {}
        data["results"] = [
            [(tp["entry"]["id"], sorted(
                [(k, v["result"], v["state"])
                 for k, v in tp["results"].items()]))
             for tp in c["timepoints"]]
            for c in matrix.get("conditions", [])]
        return hash_data(data)


class SampleFingerprint(object):
    """Fingerprint of a sample: the results and states of its analyses
    """

    def __init__(self, context):
        self.context = context

    def __call__(self, scope=None):
        sample = self.context
        analyses = []
        for analysis in sample.getAnalyses(full_objects=True):
            analyses.append((
                api.get_uid(analysis),
                analysis.getKeyword(),
                api.safe_unicode(analysis.getResult()),
                api.get_review_status(analysis),
            ))
        data = {
            "uid": api.get_uid(sample),
            "id": api.get_id(sample),
            "state": api.get_review_status(sample),
            "analyses": sorted(analyses),
        }
        return hash_data(data)
