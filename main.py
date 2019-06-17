import hashlib
import math
import os, os.path
import posixpath
import random
import requests
import struct
import sys
import time
import urllib.request as request
import urllib.parse
import webbrowser
import xml.etree.ElementTree as ET
from PySide2.QtCore import QByteArray, QFile, QObject, QUrl, QThread, Signal, Slot, Qt, QCoreApplication, QEvent
from PySide2.QtGui import QImage, QPixmap
from PySide2.QtUiTools import QUiLoader
from PySide2.QtWebEngineWidgets import QWebEngineView
from PySide2.QtWidgets import QWidget, QApplication, QProgressBar, QMainWindow, QVBoxLayout, QPushButton, QListWidget, QListWidgetItem

from detailsui import DetailsUI
from downloadui import DownloadUI
from gamelistui import GameListUI
from headerui import HeaderUI
from helpers import createWidget, logger
from importui import ImportUI
from serverlistui import ServerListUI
from settingsui import SettingsUI

from launcher import Launcher
from manifestpool import ManifestPool
from patcher import Patcher
from state import Store
from watcher import WatcherPool

from manifest import fromXML

log = logger("main")

@Slot(int)
def selectPage(index):
    for page in pages:
        page.hide()

    pages[index].show()

class SunriseApp(QApplication):
    def event(self, event):
        if event.type() == QEvent.FileOpen:
            log.info("Requested to open %s", event.url())

            try:
                importUI.display(event.url().toString())
            except Exception as e:
                log.error(e)

        return QApplication.event(self, event)

if __name__ == "__main__":
    log.info("Launching with %s", sys.argv)

    QThread.currentThread().setObjectName("Main")

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    application = SunriseApp(sys.argv)

    # Construct the main ui window
    window = createWidget("ui/sunrise-v3.ui")

    # Boot the initial data store
    store = Store()

    # Initialize the global UI elements
    headerUI = HeaderUI(store, window.gridLayout)

    # Initialize the main pages
    serverListUI = ServerListUI(store, window.gridLayout)
    gameListUI = GameListUI(store, window.gridLayout)
    settingsUI = SettingsUI(store, window.gridLayout)

    pages = [serverListUI, gameListUI, settingsUI]

    # Show the first page by default
    selectPage(0)

    # Initialize background data fetching pools
    pool = ManifestPool(store)

    # Initialize the application launcher
    launcher = Launcher(store)

    # Wire the inidivudal components together

    # Connect the main header buttons to their pages
    headerUI.itemSelected.connect(selectPage)

    # Update the state store when a manifest update is received
    pool.updated.connect(store.loadManifest)

    # Connect the store to the launcher so a list of running applications
    # can be maintained
    launcher.started.connect(store.addRunning)
    launcher.exited.connect(store.removeRunning)

    # Connect the list views to the launcher
    serverListUI.launch.connect(launcher.launch)
    gameListUI.launch.connect(launcher.launch)

    # Bind shutdown handlers for closing out background threads
    application.aboutToQuit.connect(serverListUI.shutdown)
    application.aboutToQuit.connect(gameListUI.shutdown)

    application.aboutToQuit.connect(pool.shutdown)

    # Save application data on quit
    application.aboutToQuit.connect(pool.store.saveCache)
    application.aboutToQuit.connect(pool.store.saveSettings)
    application.aboutToQuit.connect(pool.store.saveManifests)

    # Connect to theme selection
    # TODO: This requires a key existance check. User may have deleted the theme between runs
    store.settings.connectKey("theme", lambda _: store.settings.get("theme") and store.themes[store.settings.get("theme")].activate(application))

    # Load any settings store for the user
    store.load()

    # if store.settings.get("autoPatch"):
        # autoPatchPool = WatcherPool()
        # application.aboutToQuit.connect(autoPatchPool.shutdown)
        # patcher = Patcher("", autoPatchPool)

    # pool.add("manifests/manifest1.xml")
    # pool.add("manifests/manifest2.xml")
    # pool.add("manifests/manifest3.xml")

    window.setWindowTitle(store.s("ABOUT_TITLE"))

    # Show the application
    window.show()

    try:
        importUI = ImportUI(store, window)
        importUI.resize(window.width(), window.height());

        if len(sys.argv) == 2:
            importUI.display(sys.argv[1])
    except Exception as e:
        log.error(e)

    sys.exit(application.exec_())
