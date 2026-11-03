# -*- coding: utf-8 -*-

import copy

from AccessControl import ClassSecurityInfo
from bika.lims import api
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping
from plone.autoform import directives
from plone.supermodel import model
from Products.CMFCore import permissions
from senaite.core.catalog import CONTACT_CATALOG
from senaite.core.catalog import SETUP_CATALOG
from senaite.core.content.base import Container
from senaite.core.schema import UIDReferenceField
from senaite.core.schema.datetimefield import DatetimeField
from senaite.core.schema.fields import DataGridField
from senaite.core.schema.fields import DataGridRow
from senaite.core.z3cform.widgets.datagrid import DataGridWidgetFactory
from senaite.core.z3cform.widgets.datetimewidget import DatetimeWidgetFactory
from senaite.core.z3cform.widgets.uidreference import \
    UIDReferenceWidgetFactory
from senaite.pharma import _
from senaite.pharma.config import ICH_CONDITIONS
from senaite.pharma.config import STUDY_TYPES
from senaite.pharma.interfaces import ISignable
from senaite.pharma.interfaces import IStabilityStudy
from zope import schema
from zope.interface import Interface
from zope.interface import implementer
from zope.interface import Invalid
from zope.interface import invariant
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary

STUDY_TYPES_VOCABULARY = SimpleVocabulary([
    SimpleTerm(value=key, token=key, title=title)
    for key, title in STUDY_TYPES])


def default_conditions():
    """ICH Q1A(R2) default storage conditions
    """
    return copy.deepcopy(ICH_CONDITIONS)


def parse_timepoints(value):
    """Parses a comma separated list of months into a sorted list of numbers

    >>> parse_timepoints(u"0, 3, 6, 1.5")
    [0, 1.5, 3, 6]
    """
    months = set()
    for token in (value or u"").replace(";", ",").split(","):
        token = token.strip().upper().rstrip("M").strip()
        if not token:
            continue
        number = float(token)
        if number < 0:
            raise ValueError("Negative time point")
        months.add(int(number) if number.is_integer() else number)
    return sorted(months)


def validate_timepoints(value):
    try:
        parse_timepoints(value)
    except ValueError:
        raise Invalid(_(
            u"Time points must be a comma separated list of months, "
            u"e.g. '0, 3, 6, 9, 12'"))
    return True


class IConditionRecord(Interface):
    """Storage condition of a stability study (data grid row)
    """

    condition = schema.TextLine(
        title=_(u"Storage condition"),
        required=True)

    study_type = schema.Choice(
        title=_(u"Study type"),
        vocabulary=STUDY_TYPES_VOCABULARY,
        default=u"long_term",
        required=True)

    timepoints = schema.TextLine(
        title=_(u"Time points (months)"),
        constraint=validate_timepoints,
        required=True)

    storage = schema.TextLine(
        title=_(u"Storage location / chamber"),
        required=False)


class IStabilityStudySchema(model.Schema):
    """Schema of a stability study (stability protocol)
    """

    model.fieldset(
        "product",
        label=_(u"Product"),
        fields=[
            "product_name",
            "sampletype",
            "lot_numbers",
            "manufacturing_date",
            "container_closure",
        ])

    model.fieldset(
        "protocol",
        label=_(u"Storage conditions & tests"),
        fields=[
            "conditions",
            "services",
            "specification",
        ])

    title = schema.TextLine(
        title=_(u"Study title"),
        required=True)

    protocol_id = schema.TextLine(
        title=_(u"Protocol number"),
        description=_(u"Number of the approved stability protocol"),
        required=True)

    description = schema.Text(
        title=_(u"Description / objective"),
        required=False)

    directives.widget(
        "contact",
        UIDReferenceWidgetFactory,
        catalog=CONTACT_CATALOG,
        query={
            "portal_type": "Contact",
            "is_active": True,
            "sort_on": "sortable_title",
        },
        display_template="<a href='${url}'>${getFullname}</a>",
        columns=[{
            "name": "getFullname",
            "width": "50",
            "align": "left",
            "label": _(u"Name"),
        }, {
            "name": "getEmailAddress",
            "width": "50",
            "align": "left",
            "label": _(u"Email"),
        }])
    contact = UIDReferenceField(
        title=_(u"Requesting client contact"),
        description=_(u"The stability samples are registered for the client "
                      u"of this contact"),
        allowed_types=("Contact", ),
        multi_valued=False,
        required=True)

    directives.widget(
        "start_date",
        DatetimeWidgetFactory,
        show_time=False)
    start_date = DatetimeField(
        title=_(u"Study start date (T0)"),
        description=_(u"Due dates of the time points are calculated from "
                      u"this date"),
        required=True)

    pull_window = schema.Int(
        title=_(u"Pull window (± days)"),
        description=_(u"Allowed deviation from the due date of a time point"),
        default=7,
        min=0,
        required=True)

    # Product

    product_name = schema.TextLine(
        title=_(u"Product name"),
        required=True)

    directives.widget(
        "sampletype",
        UIDReferenceWidgetFactory,
        catalog=SETUP_CATALOG,
        query={
            "portal_type": "SampleType",
            "is_active": True,
            "sort_on": "sortable_title",
        },
        display_template="<a href='${url}'>${Title}</a>",
    )
    sampletype = UIDReferenceField(
        title=_(u"Sample type"),
        description=_(u"Sample type of the stability samples (e.g. dosage "
                      u"form)"),
        allowed_types=("SampleType", ),
        multi_valued=False,
        required=True)

    lot_numbers = schema.TextLine(
        title=_(u"Lot / batch number(s)"),
        required=True)

    directives.widget(
        "manufacturing_date",
        DatetimeWidgetFactory,
        show_time=False)
    manufacturing_date = DatetimeField(
        title=_(u"Manufacturing date"),
        required=False)

    container_closure = schema.TextLine(
        title=_(u"Container closure system"),
        description=_(u"Primary packaging, e.g. 'HDPE bottle 30 count'"),
        required=False)

    # Protocol

    directives.widget(
        "conditions",
        DataGridWidgetFactory,
        allow_insert=True,
        allow_delete=True,
        allow_reorder=True,
        auto_append=False)
    conditions = DataGridField(
        title=_(u"Storage conditions"),
        description=_(u"One line per storage condition. Time points are "
                      u"given in months, e.g. '0, 3, 6, 9, 12'. The initial "
                      u"time point (0) is pulled only once for all "
                      u"conditions."),
        value_type=DataGridRow(
            title=u"Condition",
            schema=IConditionRecord),
        defaultFactory=default_conditions,
        required=True)

    directives.widget(
        "services",
        UIDReferenceWidgetFactory,
        catalog=SETUP_CATALOG,
        query={
            "portal_type": "AnalysisService",
            "is_active": True,
            "sort_on": "sortable_title",
        },
        display_template="<a href='${url}'>${Title}</a>",
        columns=[{
            "name": "Title",
            "width": "60",
            "align": "left",
            "label": _(u"Test"),
        }, {
            "name": "getKeyword",
            "width": "40",
            "align": "left",
            "label": _(u"Keyword"),
        }])
    services = UIDReferenceField(
        title=_(u"Tests"),
        description=_(u"Analyses that are performed at every time point"),
        allowed_types=("AnalysisService", ),
        multi_valued=True,
        required=True)

    directives.widget(
        "specification",
        UIDReferenceWidgetFactory,
        catalog=SETUP_CATALOG,
        query={
            "portal_type": "AnalysisSpec",
            "is_active": True,
            "sort_on": "sortable_title",
        },
        display_template="<a href='${url}'>${Title}</a>",
    )
    specification = UIDReferenceField(
        title=_(u"Specification"),
        description=_(u"Acceptance criteria applied to the stability "
                      u"samples"),
        allowed_types=("AnalysisSpec", ),
        multi_valued=False,
        required=False)

    @invariant
    def validate_conditions(data):
        conditions = getattr(data, "conditions", None) or []
        names = [api.safe_unicode(c.get("condition") or u"").strip()
                 for c in conditions]
        if not any(names):
            raise Invalid(_(u"At least one storage condition is required"))
        if len(set(names)) != len(names):
            raise Invalid(_(u"Storage conditions must be unique"))


@implementer(IStabilityStudy, IStabilityStudySchema, ISignable)
class StabilityStudy(Container):
    """Stability study

    The study holds the stability protocol (product, storage conditions,
    time points and tests). Once approved, the pull schedule is generated and
    the samples of the due time points are created on demand. The samples
    are grouped in a batch of the study.
    """
    security = ClassSecurityInfo()

    # -- Simple accessors ----------------------------------------------------

    def _get(self, fieldname, raw=False):
        accessor = self.accessor(fieldname, raw=raw)
        return accessor(self) if accessor else None

    @security.protected(permissions.View)
    def getProtocolID(self):
        return self._get("protocol_id") or u""

    @security.protected(permissions.View)
    def getProductName(self):
        return self._get("product_name") or u""

    @security.protected(permissions.View)
    def getLotNumbers(self):
        return self._get("lot_numbers") or u""

    @security.protected(permissions.View)
    def getContainerClosure(self):
        return self._get("container_closure") or u""

    @security.protected(permissions.View)
    def getStartDate(self):
        return self._get("start_date")

    @security.protected(permissions.View)
    def getManufacturingDate(self):
        return self._get("manufacturing_date")

    @security.protected(permissions.View)
    def getPullWindow(self):
        return self._get("pull_window") or 0

    @security.protected(permissions.View)
    def getConditions(self):
        """Returns the storage conditions as list of dicts with the parsed
        time points under the key `months`
        """
        conditions = []
        for record in self._get("conditions") or []:
            record = dict(record)
            record["months"] = parse_timepoints(record.get("timepoints"))
            conditions.append(record)
        return conditions

    @security.protected(permissions.View)
    def getContact(self):
        return self._get("contact")

    @security.protected(permissions.View)
    def getClient(self):
        contact = self.getContact()
        if contact is None:
            return None
        return api.get_parent(contact)

    @security.protected(permissions.View)
    def getSampleType(self):
        return self._get("sampletype")

    @security.protected(permissions.View)
    def getServices(self):
        return self._get("services") or []

    @security.protected(permissions.View)
    def getRawServices(self):
        return self._get("services", raw=True) or []

    @security.protected(permissions.View)
    def getSpecification(self):
        return self._get("specification")

    # -- Study data that is not part of the edit form ------------------------

    @security.protected(permissions.View)
    def getSchedule(self):
        """Returns the pull schedule as list of dicts
        """
        return [dict(entry) for entry in getattr(self, "_schedule", [])]

    @security.private
    def setSchedule(self, entries):
        self._schedule = PersistentList(
            [PersistentMapping(entry) for entry in entries])

    @security.private
    def updateScheduleEntry(self, entry_id, **values):
        for entry in getattr(self, "_schedule", []):
            if entry.get("id") == entry_id:
                entry.update(values)
                self._p_changed = True
                return dict(entry)
        raise KeyError(entry_id)

    @security.protected(permissions.View)
    def getBatchUID(self):
        return getattr(self, "_batch_uid", None)

    @security.private
    def setBatchUID(self, uid):
        self._batch_uid = uid

    @security.protected(permissions.View)
    def getBatch(self):
        uid = self.getBatchUID()
        return api.get_object_by_uid(uid, default=None) if uid else None

    @security.protected(permissions.View)
    def getConclusion(self):
        return getattr(self, "_conclusion", u"")

    @security.private
    def setConclusion(self, value):
        self._conclusion = api.safe_unicode(value or u"")

    @security.protected(permissions.View)
    def getApprovedReports(self):
        """Returns the list of approved (signed and frozen) reports
        """
        return list(getattr(self, "_reports", []))

    @security.private
    def addApprovedReport(self, report):
        if getattr(self, "_reports", None) is None:
            self._reports = PersistentList()
        self._reports.append(report)
