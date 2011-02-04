#!/usr/bin/env python
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

    @author: RaNaN
    @author: mkaay
"""

from threading import Lock
from threading import Thread
from threading import Event
from os import remove
from os.path import exists
from shutil import move

from Queue import Queue

from traceback import print_exc

try:
    from pysqlite2 import dbapi2 as sqlite3
except:
    import sqlite3

DB_VERSION = 4

class style():
    db = None
    
    @classmethod
    def setDB(cls, db):
        cls.db = db
    
    @classmethod
    def inner(cls, f):
        @staticmethod
        def x(*args, **kwargs):
            if cls.db:
                return f(cls.db, *args, **kwargs)
        return x
    
    @classmethod
    def queue(cls, f):
        @staticmethod
        def x(*args, **kwargs):
            if cls.db:
                return cls.db.queue(f, *args, **kwargs)
        return x
    
    @classmethod
    def async(cls, f):
        @staticmethod
        def x(*args, **kwargs):
            if cls.db:
                return cls.db.async(f, *args, **kwargs)
        return x

class DatabaseJob():
    def __init__(self, f, *args, **kwargs):
        self.done = Event()
        
        self.f = f
        self.args = args
        self.kwargs = kwargs
        
        self.result = None
        self.exception = False
    
    def processJob(self):
        try:
            self.result = self.f(*self.args, **self.kwargs)
        except Exception, e:
            print "Database Error @", self.f.__name__, self.args[1:], self.kwargs, e
            print_exc()
            self.exception = e
        self.done.set()
    
    def wait(self):
        self.done.wait()

class DatabaseBackend(Thread):
    subs = []
    def __init__(self, core):
        Thread.__init__(self)
        self.setDaemon(True)
        self.core = core
        
        self.transactionLock = Lock()
        self.jobs = Queue()
        
        self.setuplock = Event()
        
        style.setDB(self)
    
    def setup(self):
        self.start()
        self.setuplock.wait()
    
    def run(self):
        """main loop, which executes commands"""
        convert = self._checkVersion() #returns None or current version
        
        self.conn = sqlite3.connect("files.db")
        self.c = self.conn.cursor() #compatibility
        
        if convert is not None:
            self._convertDB(convert)
        
        self._createTables()
        self.conn.commit()
        
        self.setuplock.set()
        
        while True:
            j = self.jobs.get()
            self.transactionLock.acquire()
            if j == "quit":
                break
            j.processJob()
            if j.exception:
                self.conn.rollback()
            else:
                self.conn.commit()
            self.transactionLock.release()

    def shutdown(self):
        self.syncSave()
        self.jobs.put(("quit"))

    def _checkVersion(self):
        """ check db version and delete it if needed"""
        if not exists("files.version"):
            f = open("files.version", "wb")
            f.write(str(DB_VERSION))
            f.close()
            return
        
        f = open("files.version", "rb")
        v = int(f.read().strip())
        f.close()
        if v < DB_VERSION:
            if v < 2:
                self.manager.core.log.warning(_("Filedatabase was deleted due to incompatible version."))
                remove("files.version")
                move("files.db", "files.backup.db")
            f = open("files.version", "wb")
            f.write(str(DB_VERSION))
            f.close()
            return v
    
    def _convertDB(self, v):
        try:
            getattr(self, "_convertV%i" % v)()
        except:
            self.core.log.error(_("Filedatabase could NOT be converted."))
    
    #--convert scripts start
    
    def _convertV2(self):
        self.c.execute('CREATE TABLE IF NOT EXISTS "storage" ("id" INTEGER PRIMARY KEY AUTOINCREMENT, "identifier" TEXT NOT NULL, "key" TEXT NOT NULL, "value" TEXT DEFAULT "")')
        self.manager.core.log.info(_("Database was converted from v2 to v3."))
        self._convertV3()
    
    def _convertV3(self):
        self.c.execute('CREATE TABLE IF NOT EXISTS "users" ("id" INTEGER PRIMARY KEY AUTOINCREMENT, "name" TEXT NOT NULL, "email" TEXT DEFAULT "" NOT NULL, "password" TEXT NOT NULL, "role" INTEGER DEFAULT 0 NOT NULL, "permission" INTEGER DEFAULT 0 NOT NULL, "template" TEXT DEFAULT "default" NOT NULL)')
        self.manager.core.log.info(_("Database was converted from v3 to v2."))
    
    #--convert scripts end
    
    def _createTables(self):
        """create tables for database"""

        self.c.execute('CREATE TABLE IF NOT EXISTS "packages" ("id" INTEGER PRIMARY KEY AUTOINCREMENT, "name" TEXT NOT NULL, "folder" TEXT, "password" TEXT DEFAULT "", "site" TEXT DEFAULT "", "queue" INTEGER DEFAULT 0 NOT NULL, "packageorder" INTEGER DEFAULT 0 NOT NULL, "priority" INTEGER DEFAULT 0 NOT NULL)')
        self.c.execute('CREATE TABLE IF NOT EXISTS "links" ("id" INTEGER PRIMARY KEY AUTOINCREMENT, "url" TEXT NOT NULL, "name" TEXT, "size" INTEGER DEFAULT 0 NOT NULL, "status" INTEGER DEFAULT 3 NOT NULL, "plugin" TEXT DEFAULT "BasePlugin" NOT NULL, "error" TEXT DEFAULT "", "linkorder" INTEGER DEFAULT 0 NOT NULL, "package" INTEGER DEFAULT 0 NOT NULL, FOREIGN KEY(package) REFERENCES packages(id))')
        self.c.execute('CREATE INDEX IF NOT EXISTS "pIdIndex" ON links(package)')
        self.c.execute('CREATE TABLE IF NOT EXISTS "storage" ("id" INTEGER PRIMARY KEY AUTOINCREMENT, "identifier" TEXT NOT NULL, "key" TEXT NOT NULL, "value" TEXT DEFAULT "")')
        self.c.execute('CREATE TABLE IF NOT EXISTS "users" ("id" INTEGER PRIMARY KEY AUTOINCREMENT, "name" TEXT NOT NULL, "email" TEXT DEFAULT "" NOT NULL, "password" TEXT NOT NULL, "role" INTEGER DEFAULT 0 NOT NULL, "permission" INTEGER DEFAULT 0 NOT NULL, "template" TEXT DEFAULT "default" NOT NULL)')
        self.c.execute('VACUUM')
    
    def createCursor(self):
        return self.conn.cursor()
    
    @style.async
    def commit(self):
        self.conn.commit()
    
    @style.async
    def rollback(self):
        self.conn.rollback()
    
    def async(self, f, *args, **kwargs):
        args = (self, ) + args
        job = DatabaseJob(f, *args, **kwargs)
        self.jobs.put(job)
    
    def queue(self, f, *args, **kwargs):
        args = (self, ) + args
        job = DatabaseJob(f, *args, **kwargs)
        self.jobs.put(job)
        job.wait()
        return job.result
    
    @classmethod
    def registerSub(cls, klass):
        cls.subs.append(klass)
    
    @classmethod
    def unregisterSub(cls, klass):
        cls.subs.remove(klass)
    
    def __getattr__(self, attr):
        for sub in DatabaseBackend.subs:
            if hasattr(sub, attr):
                return getattr(sub, attr)

if __name__ == "__main__":
    db = DatabaseBackend()
    db.setup()
    
    class Test():
        @style.queue
        def insert(db):
            c = db.createCursor()
            for i in range(1000):
                c.execute("INSERT INTO storage (identifier, key, value) VALUES (?, ?, ?)", ("foo", i, "bar"))
        @style.async
        def insert2(db):
            c = db.createCursor()
            for i in range(1000*1000):
                c.execute("INSERT INTO storage (identifier, key, value) VALUES (?, ?, ?)", ("foo", i, "bar"))
        
        @style.queue
        def select(db):
            c = db.createCursor()
            for i in range(10):
                res = c.execute("SELECT value FROM storage WHERE identifier=? AND key=?", ("foo", i))
                print res.fetchone()
        
        @style.queue
        def error(db):
            c = db.createCursor()
            print "a"
            c.execute("SELECT myerror FROM storage WHERE identifier=? AND key=?", ("foo", i))
            print "e"
    
    db.registerSub(Test)
    from time import time
    start = time()
    for i in range(100):
        db.insert()
    end = time()
    print end-start
    
    start = time()
    db.insert2()
    end = time()
    print end-start
    
    db.error()
