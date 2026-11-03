# -*- coding: utf-8 -*-

from bika.lims import api
from senaite.core.setuphandlers import add_dexterity_items
from senaite.pharma import logger


def setup_handler(context):
    """Generic setup handler of senaite.pharma
    """
    if context.readDataFile("senaite.pharma.txt") is None:
        return
    logger.info("SENAITE PHARMA setup handler [BEGIN]")
    portal = context.getSite()
    add_stability_folder(portal)
    logger.info("SENAITE PHARMA setup handler [DONE]")


def add_stability_folder(portal):
    """Adds the root folder of the stability studies after the batches
    """
    add_dexterity_items(portal, [
        ("stability", "Stability Studies", "StabilityStudies"),
    ])
    if "batches" in portal.objectIds():
        position = portal.getObjectPosition("batches")
        portal.moveObjectToPosition("stability", position + 1)
        portal.plone_utils.reindexOnReorder(portal)
    portal.stability.reindexObject()
    add_sidebar_folder("stability", after="batches")


def add_sidebar_folder(folder_id, after=None):
    """Shows the folder in the sidebar navigation. An empty selection in the
    setup means that all folders are shown, so nothing to do in that case.
    """
    setup = api.get_senaite_setup()
    folders = list(setup.getSidebarFolders() or [])
    if not folders or folder_id in folders:
        return
    position = len(folders)
    if after in folders:
        position = folders.index(after) + 1
    folders.insert(position, folder_id)
    setup.setSidebarFolders(folders)
