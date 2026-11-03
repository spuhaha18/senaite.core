# -*- coding: utf-8 -*-

from bika.lims import api
from plone.app.layout.viewlets import ViewletBase
from Products.CMFCore.utils import _checkPermission
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from senaite.pharma.browser.esign import get_signature_infos
from senaite.pharma.permissions import SignElectronically


class SampleSignaturesViewlet(ViewletBase):
    """Shows the electronic signatures of a sample and a button to sign
    """
    index = ViewPageTemplateFile("templates/sample_signatures_viewlet.pt")

    def update(self):
        super(SampleSignaturesViewlet, self).update()
        self.signatures = get_signature_infos(self.context)

    def can_sign(self):
        return _checkPermission(SignElectronically, self.context)

    def sign_url(self):
        return "{}/esign?action=".format(api.get_url(self.context))

    def available(self):
        return bool(self.signatures) or self.can_sign()
