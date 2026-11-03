# -*- coding: utf-8 -*-

import collections

from bika.lims import api
from bika.lims.utils import get_link
from senaite.core.browser.listing.base import ListingView
from senaite.core.i18n import translate
from senaite.pharma import _
from senaite.pharma.permissions import AddStabilityStudy


class StabilityStudiesView(ListingView):
    """Listing of the stability studies
    """

    def __init__(self, context, request):
        super(StabilityStudiesView, self).__init__(context, request)

        self.catalog = "portal_catalog"
        self.contentFilter = {
            "portal_type": "StabilityStudy",
            "path": {
                "query": api.get_path(context),
                "depth": 1,
            },
            "sort_on": "created",
            "sort_order": "descending",
        }

        self.context_actions = {
            _(u"Add"): {
                "url": "++add++StabilityStudy",
                "icon": "++resource++bika.lims.images/add.png",
                "permission": AddStabilityStudy,
            }
        }

        self.title = translate(_(u"Stability Studies"))
        self.description = translate(_(
            u"Stability studies according to approved stability protocols"))
        self.icon = api.get_icon("Batch", html_tag=False)
        self.show_select_column = False

        self.columns = collections.OrderedDict((
            ("getId", {"title": _(u"ID")}),
            ("ProtocolID", {"title": _(u"Protocol number")}),
            ("Title", {"title": _(u"Study title"), "index": "sortable_title"}),
            ("Product", {"title": _(u"Product name")}),
            ("Lots", {"title": _(u"Lot / batch number(s)")}),
            ("StartDate", {"title": _(u"Study start date (T0)")}),
            ("Progress", {"title": _(u"Pulled")}),
            ("NextDue", {"title": _(u"Next due date")}),
            ("state_title", {"title": _(u"State")}),
        ))

        self.review_states = [{
            "id": "default",
            "title": _(u"Active"),
            "contentFilter": {"review_state": ["draft", "active"]},
            "columns": self.columns.keys(),
        }, {
            "id": "completed",
            "title": _(u"Completed"),
            "contentFilter": {"review_state": ["completed"]},
            "columns": self.columns.keys(),
        }, {
            "id": "cancelled",
            "title": _(u"Cancelled"),
            "contentFilter": {"review_state": ["cancelled"]},
            "columns": self.columns.keys(),
        }, {
            "id": "all",
            "title": _(u"All"),
            "contentFilter": {},
            "columns": self.columns.keys(),
        }]

    def folderitem(self, obj, item, index):
        study = api.get_object(obj)
        url = api.get_url(study)
        item["replace"]["getId"] = get_link(url, api.get_id(study))
        item["replace"]["Title"] = get_link(url, api.safe_unicode(
            study.Title()))
        item["ProtocolID"] = study.getProtocolID()
        item["Product"] = study.getProductName()
        item["Lots"] = study.getLotNumbers()
        start = study.getStartDate()
        item["StartDate"] = start.strftime("%Y-%m-%d") if start else ""

        schedule = study.getSchedule()
        pulled = [e for e in schedule if e["status"] == "pulled"]
        active = [e for e in schedule if e["status"] != "cancelled"]
        item["Progress"] = u"{}/{}".format(len(pulled), len(active)) \
            if schedule else u""
        scheduled = [e["due_date"] for e in schedule
                     if e["status"] == "scheduled"]
        item["NextDue"] = min(scheduled) if scheduled else u""
        wf = api.get_tool("portal_workflow")
        state = wf.getTitleForStateOnType(
            api.get_review_status(study), "StabilityStudy")
        item["state_title"] = translate(_(api.safe_unicode(state)))
        return item
