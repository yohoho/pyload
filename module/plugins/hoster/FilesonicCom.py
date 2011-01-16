#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

from module.plugins.Hoster import Hoster
from module.plugins.ReCaptcha import ReCaptcha
    

class FilesonicCom(Hoster):
    __name__ = "FilesonicCom"
    __type__ = "hoster"
    __pattern__ = r"http://[\w\.]*?(sharingmatrix|filesonic)\.(com|net)/.*?file/([0-9]+(/.+)?|[a-z0-9]+/[0-9]+(/.+)?)"
    __version__ = "0.1"
    __description__ = """FilesonicCom und Sharingmatrix Download Hoster"""
    __author_name__ = ("jeix")
    __author_mail__ = ("jeix@hasnomail.de")

    def setup(self):
        self.multiDL = True if self.account else False

    def process(self, pyfile):
        self.pyfile = pyfile
        
        self.url = self.convertURL(self.pyfile.url)
        
        self.html = self.load(self.url)
        name = re.search(r'Filename:\s*</span>\s*<strong>(.*?)<', self.html)
        if name:
            self.pyfile.name = name.group(1)
        else:
            self.offline()

        self.download(self.getFileUrl())

    def getFileUrl(self):

        link = self.url + "/" + re.search(r'href="(.*?start=1.*?)"', self.html).group(1)
        self.html = self.load(link)

        self.handleErrors()

        realLinkRegexp = "<p><a href=\"(http://[^<]*?\\.filesonic\\.com[^<]*?)\"><span>Start download now!</span></a></p>"
        url = re.search(realLinkRegexp, self.html)
        
        if not url:
            if "This file is available for premium users only." in self.html:
                self.fail("Need premium account.")
            
            countDownDelay = re.search("countDownDelay = (\\d+)", self.html)
            if countDownDelay:
                wait_time = int(countDownDelay.group(1))
                 
                if wait_time > 300:
                    self.wantReconnect = True
                
                self.setWait(wait_time)
                self.log.info("%s: Waiting %d seconds." % self.__name__, wait_time)
                self.wait()
                
                tm = re.search("name='tm' value='(.*?)' />", self.html).group(1)
                tm_hash = re.search("name='tm_hash' value='(.*?)' />", self.html).group(1)
                
                self.html = self.load(self.url + "?start=1", post={"tm":tm,"tm_hash":tm_hash})

                self.handleErrors()
            
            
            if "Please Enter Password" in self.html:
                self.fail("implement need pw")
            
            chall = re.search(r'Recaptcha.create("(.*?)",', self.html)
            if chall:
                re_captcha = ReCaptcha(self)
                challenge, result = re_captcha.challenge(chall.group(1))
            
                postData = {"recaptcha_challenge_field": challenge,
                            "recaptcha_response_field" : result}
                            
                self.html = self.load(link, post=postData)

        url = re.search(realLinkRegexp, self.html).group(1)
        return url
        
    def convertURL(self, url):
        id = re.search("/file/([0-9]+(/.+)?)", url)
        if not id:
            id = re.search("/file/[a-z0-9]+/([0-9]+(/.+)?)", url)
        return ("http://www.filesonic.com/file/" + id.group(1))

    def handleErrors(self):
        if "The file that you're trying to download is larger than" in self.html:
            self.fail("need premium account for file")

        if "Free users may only download 1 file at a time" in self.html:
            self.fail("only 1 file at a time for free users")

        if "Free user can not download files" in self.html:
            self.fail("need premium account for file")
            
        if "Download session in progress" in self.html:
            self.fail("already downloading")
                
        if "This file is password protected" in self.html:
            self.fail("This file is password protected, please one.")
            
        if "An Error Occurred" in self.html:
            self.fail("A server error occured.")
