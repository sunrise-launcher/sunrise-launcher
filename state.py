import os
import pickle
import sys
import xml.etree.ElementTree as ET

from PySide2.QtCore import QObject, Slot, Signal

from helpers import uList
from manifest import fromXML, fromXMLString, Manifest
from settings import Settings, PathSettings, ContainerSettings, RecentServers, SunriseSettings
from theme import Loader, Theme

LOCAL_MANIFEST_URL = "local://manifests.xml"

# Storage of metadata about the users current install
class Store(QObject):
    updated = Signal()

    def __init__(self, parent = None):
        super(Store, self).__init__(parent)

        self.manifestNames = {}
        self.applications = {}
        self.runtimes = {}
        self.servers = {}
        self.cache = {}
        self.settings = Settings()
        self.running = []
        self.themes = {}

        try:
            dirs = list(os.walk(os.path.abspath("themes")))
            for themeId in dirs[0][1]:
                print("Adding theme from", themeId)
                theme = Theme.fromPath(os.path.join("themes", themeId))

                if theme.props and "name" in theme.props:
                    self.themes[theme.props["name"]] = theme

        except Exception:
            print(sys.exc_info())
            pass

        try:
            dirs = list(os.walk(os.path.join(SunriseSettings.settingsPath, "themes")))
            for themeId in dirs[0][1]:
                print("Adding user theme from", themeId)
                theme = Theme.fromPath(os.path.join(SunriseSettings.settingsPath, "themes", themeId))

                if theme.props and "name" in theme.props:
                    self.themes[theme.props["name"]] = theme

        except Exception:
            print(sys.exc_info())
            pass

        self.settings.committed.connect(self.saveSettings)
        self.updated.connect(self.saveManifests)

    def load(self):

        try:
            settingsFile = os.path.join(SunriseSettings.settingsPath, "settings.pickle")
            print(settingsFile)

            if os.path.isfile(settingsFile):
                f = open(settingsFile, "rb")
                self.settings.load(pickle.load(f))
            else:
                self.settings.set("autoPatch", True)
                self.settings.set("containerSettings", {})
                self.settings.set("paths", PathSettings("bin", "run"))
                self.settings.set("recentServers", RecentServers())
                self.settings.set("hiddenServers", uList())
                self.settings.set("theme", list(self.themes.keys())[0])
                self.settings.set("manifestList", uList())

            self.settings.commit()
        except Exception:
            print(sys.exc_info())
            pass

        try:
            storedManifests = open(os.path.join(SunriseSettings.settingsPath, "manifests.xml"), "r").read()
            self.loadManifest(LOCAL_MANIFEST_URL, storedManifests)
        except Exception:
            print(sys.exc_info())
            pass

        print("Loaded state")
        print(self.settings.get("theme"))

        self.updated.emit()

    def getTools(self):
        return list(filter(lambda a: a.type == "mod", self.applications.values()))

    def getClients(self):
        return list(filter(lambda a: a.type == "client", self.applications.values()))

    def installTheme(self, filePath):
        theme = Loader.load(filePath)

        if theme:
            self.themes[theme.props["name"]] = theme
            self.settings.set("theme", theme.props["name"])
            self.settings.commit()
            self.updated.emit()

    @Slot(str, str)
    def loadManifest(self, url, data):
        manifest = fromXMLString(data, url)

        print("Updating manifest from", url, "in store")

        self.applications.update(manifest.applications)
        self.runtimes.update(manifest.runtimes)
        self.servers.update(manifest.servers)

        containerSettings = self.settings.get("containerSettings")

        for app in self.applications.values():
            if not app.id in containerSettings:
                containerSettings[app.id] = ContainerSettings(app.id)

        for runtime in self.runtimes.values():
            if not runtime.id in containerSettings:
                containerSettings[runtime.id] = ContainerSettings(runtime.id)

        self.settings.set("containerSettings", containerSettings)

        if not manifest.source == LOCAL_MANIFEST_URL:
            self.manifestNames[url] = manifest.name
            manifests = self.settings.get("manifestList")
            manifests.push(url)

            print("Manifest source", manifest.source, manifest.source == LOCAL_MANIFEST_URL)

            self.settings.set("manifestList", manifests)

        self.settings.commit()
        print("Committed settings for", url)

        self.updated.emit()

    @Slot(str)
    def addRunning(self, id):
        print("Adding", id, "to running list")
        self.running.append(id)

    @Slot(str)
    def removeRunning(self, id):
        print("Removing", id, "to running list")
        self.running.remove(id)

    def resolveDownload(self, id):
        # TODO: Do we need to handle collisions between app and runtime ids
        requested = self.applications.get(id, self.runtimes.get(id))

        if requested:
            print("Resolved", requested.id)
            if hasattr(requested, "runtime") and requested.runtime:
                return self.resolveDownload(requested.runtime) + [requested]
            else:
                return [requested]
        else:
            print("Failed to resolve", id)
            return []

    def saveSettings(self):
        if not os.path.isdir(SunriseSettings.settingsPath):
            os.makedirs(SunriseSettings.settingsPath)

        f = open(os.path.join(SunriseSettings.settingsPath, "settings.pickle"), "wb+")
        settingsOutput = pickle.dump(self.settings.getData(), f)

        f.close()

    def saveManifests(self):
        if not os.path.isdir(SunriseSettings.settingsPath):
            os.makedirs(SunriseSettings.settingsPath)

        manifest = Manifest("store", self.servers, self.applications, self.runtimes, LOCAL_MANIFEST_URL)
        manifestOutput = ET.tostring(manifest.toXML(), encoding="utf8", method="xml")

        f = open(os.path.join(SunriseSettings.settingsPath, "manifests.xml"), "wb+")
        f.write(manifestOutput)
        f.close()
