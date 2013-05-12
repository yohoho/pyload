  # -*- coding: utf-8 -*-

"""
    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 3 of the License,
    or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
    See the GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, see <http://www.gnu.org/licenses/>.

    @author: Walter Purcaro
"""

from module.plugins.Hook import Hook
from time import time


class RestartFailed(Hook):
    __name__ = "RestartFailed"
    __version__ = "1.2"
    __description__ = "Automatically restart failed/aborted downloads"
    __config__ = [
        ("activated", "bool", "Activated", "True"),
        ("dlFail", "bool", "Restart when download fail", "True"),
        ("dlFail_n", "int", "Only when failed downloads are at least", "5"),
        ("dlFail_i", "int", "Only when elapsed time since last restart is (min)", "10"),
        ("dlPrcs", "bool", "Restart after all downloads are processed", "True"),
        ("recnt", "bool", "Restart after reconnecting", "True"),
        ("rsLoad", "bool", "Restart on plugin activation", "False")
    ]
    __author_name__ = ("Walter Purcaro")
    __author_mail__ = ("vuolter@gmail.com")

    def resetCounters(self):
        # self.logDebug("self.resetCounters")
        self.info["dlfailed"] = 0
        if self.info["timerflag"]:
            self.setTimer(False, None)

    def restart(self):
        now = time()
        self.resetCounters()
        self.core.api.restartFailed()
        self.logDebug("self.restart: self.core.api.restartFailed")
        self.info["lastrstime"] = now

    def setTimer(self, timerflag, interval):
        # self.logDebug("self.setTimer")
        self.info["timerflag"] = timerflag
        if interval and interval != self.interval:
            self.interval = interval
        if timerflag:
            self.addEvent("periodical", self.restart)
        else:
            self.removeEvent("periodical", self.restart)

    def checkFailed_i(self):
        #self.logDebug("self.checkFailed_i")
        now = time()
        lastrstime = self.info["lastrstime"]
        interval = self.getConfig("dlFail_i") * 60
        timerflag = self.info["timerflag"]
        if now >= lastrstime + interval:
            self.restart()
        elif not timerflag:
            self.setTimer(True, interval)

    def checkFailed_n(self):
        # self.logDebug("self.checkFailed_n")
        curr = self.info["dlfailed"]
        max = self.getConfig("dlFail_n")
        if curr >= max:
            self.checkFailed_i()

    def checkFailed(self, pyfile):
        # self.logDebug("self.checkFailed")
        self.info["dlfailed"] += 1
        self.checkFailed_n()

    def addEvent(self, event, handler):
        if event in self.manager.events:
            if handler not in self.manager.events[event]:
                self.manager.events[event].append(handler)
                # self.logDebug("self.addEvent: " + event + " event: added handler")
            else:
                # self.logDebug("self.addEvent: " + event + " event: NOT added handler")
                return False
        else:
            self.manager.events[event] = [handler]
            # self.logDebug("self.addEvent: " + event + " event: added event and handler")
        return True

    def removeEvent(self, event, handler):
        if event in self.manager.events and handler in self.manager.events[event]:
            self.manager.events[event].remove(handler)
            # self.logDebug("self.removeEvent: " + event + " event: removed handler")
            return True
        else:
            # self.logDebug("self.removeEvent: " + event + " event: NOT removed handler")
            return False

    def onAfterReconnecting(self, ip):
        # self.logDebug("self.onAfterReconnecting")
        self.restart()

    def configEvents(self, plugin, name, value):
        # self.logDebug("self.configEvents")
        if self.getConfig("dlFail"):
            self.addEvent("downloadFailed", self.checkFailed)
        else:
            self.removeEvent("downloadFailed", self.checkFailed)
            self.resetCounters()
        if self.getConfig("dlPrcs"):
            self.addEvent("allDownloadsProcessed", self.restart)
        else:
            self.removeEvent("allDownloadsProcessed", self.restart)
        if self.getConfig("recnt"):
            self.addEvent("afterReconnecting", self.onAfterReconnecting)
        else:
            self.removeEvent("afterReconnecting", self.onAfterReconnecting)

    def unload(self):
        # self.logDebug("self.unload")
        self.removeEvent("pluginConfigChanged", self.configEvents)
        self.removeEvent("periodical", self.restart)
        self.removeEvent("downloadFailed", self.checkFailed)
        self.removeEvent("allDownloadsProcessed", self.restart)
        self.removeEvent("afterReconnecting", self.onAfterReconnecting)

    def coreReady(self):
        # self.logDebug("self.coreReady")
        self.info = {"dlfailed": 0, "lastrstime": 0, "timerflag": False}
        if self.getConfig("rsLoad"):
            self.restart()
        self.addEvent("pluginConfigChanged", self.configEvents)
        self.configEvents(None, None, None)
