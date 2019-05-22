import hashlib
import sys
import time
import urllib.request as request

from PySide2.QtCore import QObject, QThread, QTimer, Slot, Signal
import requests

class WatcherPool(QObject):
    updated = Signal(str, str)
    startTrigger = Signal()
    stopTrigger = Signal(str)
    shutdownTrigger = Signal()

    def __init__(self, parent=None):
        super(WatcherPool, self).__init__(parent)
        self.watchers = {}
        self.graveyard = []
        self.thread = QThread()
        self.thread.setObjectName("Watcher")
        self.thread.start()

    def add(self, url):
        if self.watchers.get(url):
            self.remove(url)

        self.watchers[url] = Watcher(url, self.updated)
        self.watchers[url].moveToThread(self.thread)
        self.stopTrigger.connect(self.watchers[url].stop)
        self.shutdownTrigger.connect(self.watchers[url].shutdown)

        if self.thread.isRunning():
            print("Watch thread already running. Starting", url)
            # TODO: There should be a better way to write this
            try:
                self.startTrigger.disconnect()
            except Exception:
                pass

            self.startTrigger.connect(self.watchers[url].start)
            self.startTrigger.emit()
        else:
            print("Watch thread not running. Scheduling", url)
            self.thread.started.connect(self.watchers[url].start)

    def remove(self, url):
        if self.watchers.get(url):
            self.stopTrigger.emit(url)

            # Append to graveyard so that the timer can gracefully stop
            # instead of the reference being dropped
            self.graveyard.append(self.watchers.pop(url))

    @Slot()
    def shutdown(self):
        self.shutdownTrigger.emit()

        # TODO: Hack to get the pool's thread to run the shutdown requests
        #       prior to shutting down the thread itself. Stopping the thread
        #       immediately results in timers in the pool thread being stopped
        #       by the main thread. This seems problematic? I do not know
        #       enough of the systems to make a proper call
        time.sleep(0.25)

        self.thread.quit()
        self.thread.wait()

class Watcher(QObject):
    def __init__(self, url, updater = None, parent=None):
        super(Watcher, self).__init__(parent)

        self.check = None
        self.url = url
        self.updater = updater

        self.timer = None

    @Slot()
    def start(self):
        print("Start watcher", self.url)
        print("Current thread during start", QThread.currentThread().objectName())
        self.timer = QTimer()
        self.timer.setInterval(6000)
        self.timer.timeout.connect(self.run)
        self.timer.start()
        self.run()

    @Slot(str)
    def stop(self, url):
        print("Current thread during watcher stop", QThread.currentThread().objectName(), url)

        if self.timer:
            if url == self.url:
                print("Stop timer")
                self.timer.stop()

    @Slot()
    def shutdown(self):
        print("Current thread during watcher shutdown", QThread.currentThread().objectName())

        if self.timer:
            print("Stop timer")
            self.timer.stop()

    @Slot()
    def run(self):
        print("Current thread during run", QThread.currentThread().objectName())
        try:
            print("Try fetch", self.url)
            req = requests.get(self.url, timeout=5)

            with req:
                req.raise_for_status()
                check = hashlib.sha512(req.content).hexdigest()

                if not self.check == check:
                    self.check = check
                    print("Update available", self.url)
                    self.updater.emit(self.url, req.text)

        except Exception:
            print("Fetch error", self.url)
            print(sys.exc_info())
