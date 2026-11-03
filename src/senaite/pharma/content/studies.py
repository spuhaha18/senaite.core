# -*- coding: utf-8 -*-

from bika.lims.interfaces import IDoNotSupportSnapshots
from plone.supermodel import model
from senaite.core.content.base import Container
from senaite.core.interfaces import IHideActionsMenu
from senaite.pharma.interfaces import IStabilityStudies
from zope.interface import implementer


class IStabilityStudiesSchema(model.Schema):
    """Schema of the stability studies folder
    """


@implementer(IStabilityStudies, IStabilityStudiesSchema,
             IDoNotSupportSnapshots, IHideActionsMenu)
class StabilityStudies(Container):
    """Root folder of the stability studies
    """
