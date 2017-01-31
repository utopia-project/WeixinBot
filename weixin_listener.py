#!/usr/bin/env python
# encoding: utf-8

import multiprocessing
import cookielib
import re
import os
import random
import platform
import logging
import sys
import time
import argparse
import urllib2
import urllib
import json
import httplib
from collections import defaultdict
from urlparse import urlparse
from lxml import html

# for media upload
import mimetypes
from requests_toolbelt.multipart.encoder import MultipartEncoder
from os.path import expanduser

from weixin_util import WeixinUtil


def catchKeyboardInterrupt(fn):
    def wrapper(*args):
        try:
            return fn(*args)
        except KeyboardInterrupt:
            print '\n[*] 强制退出程序'
            logging.debug('[*] 强制退出程序')
    return wrapper


class WeixinListener:

    def __init__(self, argsFile, cookieFile):
        self.DEBUG = True
        self.syncHost = ''
        self.lastCheckTs = 0

        fileContent = ''
        with open(argsFile, 'rb') as fp:
            fileContent = fp.read()
        args = json.loads(fileContent)

        self.sid = args['sid']
        self.uin = args['uin']
        self.skey = args['skey']
        self.pass_ticket = args['pass_ticket']
        self.deviceId = args['deviceId']
        self.synckey = args['synckey']
        self.SyncKey = args['SyncKey']
        self.base_uri = args['base_uri']

        self.BaseRequest = {
            'Uin': int(self.uin),
            'Sid': self.sid,
            'Skey': self.skey,
            'DeviceID': self.deviceId,
        }

        self.User = args['User']
        self.MemberList = args['MemberList']
        self.ContactList = args['ContactList']  # 好友
        self.GroupList = args['GroupList']  # 群
        self.GroupMemeberList = args['GroupMemeberList']  # 群友
        self.PublicUsersList = args['PublicUsersList']  # 公众号／服务号
        self.SpecialUsersList = args['SpecialUsersList']  # 特殊账号

        self.autoReplyMode = False
        self.autoOpen = False

        self.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.109 Safari/537.36'

        self.cookie = cookielib.MozillaCookieJar()
        self.cookie.load(cookieFile, ignore_discard=True, ignore_expires=True)
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookie))
        opener.addheaders = [('User-agent', self.user_agent)]
        urllib2.install_opener(opener)

    def testsynccheck(self):
        SyncHost = [
            'webpush.weixin.qq.com',
            # 'webpush2.weixin.qq.com',
            'webpush.wechat.com',
            'webpush1.wechat.com',
            'webpush2.wechat.com',
            'webpush.wx.qq.com',
            'webpush2.wx.qq.com'
            # 'webpush.wechatapp.com'
        ]
        for host in SyncHost:
            self.syncHost = host
            [retcode, selector] = self.synccheck()
            if retcode == '0':
                return True
        return False

    def listenMsgMode(self):
        print '[*] 进入消息监听模式 ... 成功'
        logging.debug('[*] 进入消息监听模式 ... 成功')
        WeixinUtil.run('[*] 进行同步线路测试 ... ', self.testsynccheck)
        playWeChat = 0
        redEnvelope = 0
        while True:
            self.lastCheckTs = time.time()
            [retcode, selector] = self.synccheck()
            if self.DEBUG:
                print 'retcode: %s, selector: %s' % (retcode, selector)
            logging.debug('retcode: %s, selector: %s' % (retcode, selector))
            if retcode == '1100':
                print '[*] 你在手机上登出了微信，债见'
                logging.debug('[*] 你在手机上登出了微信，债见')
                break
            if retcode == '1101':
                print '[*] 你在其他地方登录了 WEB 版微信，债见'
                logging.debug('[*] 你在其他地方登录了 WEB 版微信，债见')
                break
            elif retcode == '0':
                if selector == '2':
                    r = self.webwxsync()
                    if r is not None:
                        self.handleMsg(r)
                elif selector == '6':
                    # TODO
                    redEnvelope += 1
                    print '[*] 收到疑似红包消息 %d 次' % redEnvelope
                    logging.debug('[*] 收到疑似红包消息 %d 次' % redEnvelope)
                elif selector == '7':
                    playWeChat += 1
                    print '[*] 你在手机上玩微信被我发现了 %d 次' % playWeChat
                    logging.debug('[*] 你在手机上玩微信被我发现了 %d 次' % playWeChat)
                    r = self.webwxsync()
                elif selector == '0':
                    time.sleep(1)
            if (time.time() - self.lastCheckTs) <= 20:
                time.sleep(time.time() - self.lastCheckTs)

    def synccheck(self):
        params = {
            'r': int(time.time()),
            'sid': self.sid,
            'uin': self.uin,
            'skey': self.skey,
            'deviceid': self.deviceId,
            'synckey': self.synckey,
            '_': int(time.time()),
        }
        url = 'https://' + self.syncHost + \
            '/cgi-bin/mmwebwx-bin/synccheck?' + urllib.urlencode(params)
        print url
        data = WeixinUtil.get(url)
        if data == '':
            return [-1, -1]
        pm = re.search(
            r'window.synccheck={retcode:"(\d+)",selector:"(\d+)"}', data)
        retcode = pm.group(1)
        selector = pm.group(2)
        return [retcode, selector]

    def webwxsync(self):
        url = self.base_uri + \
            '/webwxsync?sid=%s&skey=%s&pass_ticket=%s' % (
                self.sid, self.skey, self.pass_ticket)
        params = {
            'BaseRequest': self.BaseRequest,
            'SyncKey': self.SyncKey,
            'rr': ~int(time.time())
        }
        dic = WeixinUtil.post(url, params)
        if dic == '':
            return None
        if self.DEBUG:
            print json.dumps(dic, indent=4)
            (json.dumps(dic, indent=4))

        if dic['BaseResponse']['Ret'] == 0:
            self.SyncKey = dic['SyncKey']
            self.synckey = '|'.join(
                [str(keyVal['Key']) + '_' + str(keyVal['Val']) for keyVal in self.SyncKey['List']])
        return dic

    def _xiaodoubi(self, word):
        url = 'http://www.xiaodoubi.com/bot/chat.php'
        try:
            r = requests.post(url, data={'chat': word})
            return r.content
        except:
            return "让我一个人静静 T_T..."

    def webwxsendmsg(self, word, to='filehelper'):
        url = self.base_uri + \
            '/webwxsendmsg?pass_ticket=%s' % (self.pass_ticket)
        clientMsgId = str(int(time.time() * 1000)) + \
            str(random.random())[:5].replace('.', '')
        params = {
            'BaseRequest': self.BaseRequest,
            'Msg': {
                "Type": 1,
                "Content": self._transcoding(word),
                "FromUserName": self.User['UserName'],
                "ToUserName": to,
                "LocalID": clientMsgId,
                "ClientMsgId": clientMsgId
            }
        }
        headers = {'content-type': 'application/json; charset=UTF-8'}
        data = json.dumps(params, ensure_ascii=False).encode('utf8')
        r = requests.post(url, data=data, headers=headers)
        dic = r.json()
        return dic['BaseResponse']['Ret'] == 0

    def webwxgetmsgimg(self, msgid):
        url = self.base_uri + \
            '/webwxgetmsgimg?MsgID=%s&skey=%s' % (msgid, self.skey)
        data = WeixinUtil.get(url)
        if data == '':
            return ''
        fn = 'img_' + msgid + '.jpg'
        # TODO
        # return self._saveFile(fn, data, 'webwxgetmsgimg')

    # Not work now for weixin haven't support this API
    def webwxgetvideo(self, msgid):
        url = self.base_uri + \
            '/webwxgetvideo?msgid=%s&skey=%s' % (msgid, self.skey)
        data = WeixinUtil.get(url, api='webwxgetvideo')
        if data == '':
            return ''
        fn = 'video_' + msgid + '.mp4'
        return self._saveFile(fn, data, 'webwxgetvideo')

    def webwxgetvoice(self, msgid):
        url = self.base_uri + \
            '/webwxgetvoice?msgid=%s&skey=%s' % (msgid, self.skey)
        data = WeixinUtil.get(url)
        if data == '':
            return ''
        fn = 'voice_' + msgid + '.mp3'
        return self._saveFile(fn, data, 'webwxgetvoice')

    def _safe_open(self, path):
        if self.autoOpen:
            if platform.system() == "Linux":
                os.system("xdg-open %s &" % path)
            else:
                os.system('open %s &' % path)

    def handleMsg(self, r):
        for msg in r['AddMsgList']:
            print '[*] 你有新的消息，请注意查收'
            logging.debug('[*] 你有新的消息，请注意查收')

            if self.DEBUG:
                fn = 'msg' + str(int(random.random() * 1000)) + '.json'
                with open(fn, 'w') as f:
                    f.write(json.dumps(msg))
                print '[*] 该消息已储存到文件: ' + fn
                logging.debug('[*] 该消息已储存到文件: %s' % (fn))

            msgType = msg['MsgType']
            name = self.getUserRemarkName(msg['FromUserName'])
            content = msg['Content'].replace('&lt;', '<').replace('&gt;', '>')
            msgid = msg['MsgId']

            if msgType == 1:
                raw_msg = {'raw_msg': msg}
                self._showMsg(raw_msg)
                if self.autoReplyMode:
                    ans = self._xiaodoubi(content) + '\n[微信机器人自动回复]'
                    if self.webwxsendmsg(ans, msg['FromUserName']):
                        print '自动回复: ' + ans
                        logging.info('自动回复: ' + ans)
                    else:
                        print '自动回复失败'
                        logging.info('自动回复失败')
            elif msgType == 3:
                image = self.webwxgetmsgimg(msgid)
                raw_msg = {'raw_msg': msg,
                           'message': '%s 发送了一张图片: %s' % (name, image)}
                self._showMsg(raw_msg)
                self._safe_open(image)
            elif msgType == 34:
                voice = self.webwxgetvoice(msgid)
                raw_msg = {'raw_msg': msg,
                           'message': '%s 发了一段语音: %s' % (name, voice)}
                self._showMsg(raw_msg)
                self._safe_open(voice)
            elif msgType == 42:
                info = msg['RecommendInfo']
                print '%s 发送了一张名片:' % name
                print '========================='
                print '= 昵称: %s' % info['NickName']
                print '= 微信号: %s' % info['Alias']
                print '= 地区: %s %s' % (info['Province'], info['City'])
                print '= 性别: %s' % ['未知', '男', '女'][info['Sex']]
                print '========================='
                raw_msg = {'raw_msg': msg, 'message': '%s 发送了一张名片: %s' % (
                    name.strip(), json.dumps(info))}
                self._showMsg(raw_msg)
            elif msgType == 47:
                url = self._searchContent('cdnurl', content)
                raw_msg = {'raw_msg': msg,
                           'message': '%s 发了一个动画表情，点击下面链接查看: %s' % (name, url)}
                self._showMsg(raw_msg)
                self._safe_open(url)
            elif msgType == 49:
                appMsgType = defaultdict(lambda: "")
                appMsgType.update({5: '链接', 3: '音乐', 7: '微博'})
                print '%s 分享了一个%s:' % (name, appMsgType[msg['AppMsgType']])
                print '========================='
                print '= 标题: %s' % msg['FileName']
                print '= 描述: %s' % self._searchContent('des', content, 'xml')
                print '= 链接: %s' % msg['Url']
                print '= 来自: %s' % self._searchContent('appname', content, 'xml')
                print '========================='
                card = {
                    'title': msg['FileName'],
                    'description': self._searchContent('des', content, 'xml'),
                    'url': msg['Url'],
                    'appname': self._searchContent('appname', content, 'xml')
                }
                raw_msg = {'raw_msg': msg, 'message': '%s 分享了一个%s: %s' % (
                    name, appMsgType[msg['AppMsgType']], json.dumps(card))}
                self._showMsg(raw_msg)
            elif msgType == 51:
                raw_msg = {'raw_msg': msg, 'message': '[*] 成功获取联系人信息'}
                self._showMsg(raw_msg)
            elif msgType == 62:
                video = self.webwxgetvideo(msgid)
                raw_msg = {'raw_msg': msg,
                           'message': '%s 发了一段小视频: %s' % (name, video)}
                self._showMsg(raw_msg)
                self._safe_open(video)
            elif msgType == 10002:
                raw_msg = {'raw_msg': msg, 'message': '%s 撤回了一条消息' % name}
                self._showMsg(raw_msg)
            else:
                logging.debug('[*] 该消息类型为: %d，可能是表情，图片, 链接或红包: %s' %
                              (msg['MsgType'], json.dumps(msg)))
                raw_msg = {
                    'raw_msg': msg, 'message': '[*] 该消息类型为: %d，可能是表情，图片, 链接或红包' % msg['MsgType']}
                self._showMsg(raw_msg)

    def getNameById(self, id):
        url = self.base_uri + \
            '/webwxbatchgetcontact?type=ex&r=%s&pass_ticket=%s' % (
                int(time.time()), self.pass_ticket)
        params = {
            'BaseRequest': self.BaseRequest,
            "Count": 1,
            "List": [{"UserName": id, "EncryChatRoomId": ""}]
        }
        dic = WeixinUtil.post(url, params)
        if dic == '':
            return None

        # blabla ...
        return dic['ContactList']

    def getGroupName(self, id):
        name = '未知群'
        for member in self.GroupList:
            if member['UserName'] == id:
                name = member['NickName']
        if name == '未知群':
            # 现有群里面查不到
            GroupList = self.getNameById(id)
            for group in GroupList:
                self.GroupList.append(group)
                if group['UserName'] == id:
                    name = group['NickName']
                    MemberList = group['MemberList']
                    for member in MemberList:
                        self.GroupMemeberList.append(member)
        return name

    def getUserRemarkName(self, id):
        name = '未知群' if id[:2] == '@@' else '陌生人'
        if id == self.User['UserName']:
            return self.User['NickName']  # 自己

        if id[:2] == '@@':
            # 群
            name = self.getGroupName(id)
        else:
            # 特殊账号
            for member in self.SpecialUsersList:
                if member['UserName'] == id:
                    name = member['RemarkName'] if member[
                        'RemarkName'] else member['NickName']

            # 公众号或服务号
            for member in self.PublicUsersList:
                if member['UserName'] == id:
                    name = member['RemarkName'] if member[
                        'RemarkName'] else member['NickName']

            # 直接联系人
            for member in self.ContactList:
                if member['UserName'] == id:
                    name = member['RemarkName'] if member[
                        'RemarkName'] else member['NickName']
            # 群友
            for member in self.GroupMemeberList:
                if member['UserName'] == id:
                    name = member['DisplayName'] if member[
                        'DisplayName'] else member['NickName']

        if name == '未知群' or name == '陌生人':
            logging.debug(id)
        return name

    def _showMsg(self, message):

        srcName = None
        dstName = None
        groupName = None
        content = None

        msg = message
        logging.debug(msg)

        if msg['raw_msg']:
            srcName = self.getUserRemarkName(msg['raw_msg']['FromUserName'])
            dstName = self.getUserRemarkName(msg['raw_msg']['ToUserName'])
            content = msg['raw_msg']['Content'].replace(
                '&lt;', '<').replace('&gt;', '>')
            message_id = msg['raw_msg']['MsgId']

            if content.find('http://weixin.qq.com/cgi-bin/redirectforward?args=') != -1:
                # 地理位置消息
                data = WeixinUtil.get(content)
                if data == '':
                    return
                data.decode('gbk').encode('utf-8')
                pos = self._searchContent('title', data, 'xml')
                temp = WeixinUtil.get(content)
                if temp == '':
                    return
                tree = html.fromstring(temp)
                url = tree.xpath('//html/body/div/img')[0].attrib['src']

                for item in urlparse(url).query.split('&'):
                    if item.split('=')[0] == 'center':
                        loc = item.split('=')[-1:]

                content = '%s 发送了一个 位置消息 - 我在 [%s](%s) @ %s]' % (
                    srcName, pos, url, loc)

            if msg['raw_msg']['ToUserName'] == 'filehelper':
                # 文件传输助手
                dstName = '文件传输助手'

            if msg['raw_msg']['FromUserName'][:2] == '@@':
                # 接收到来自群的消息
                if ":<br/>" in content:
                    [people, content] = content.split(':<br/>', 1)
                    groupName = srcName
                    srcName = self.getUserRemarkName(people)
                    dstName = 'GROUP'
                else:
                    groupName = srcName
                    srcName = 'SYSTEM'
            elif msg['raw_msg']['ToUserName'][:2] == '@@':
                # 自己发给群的消息
                groupName = dstName
                dstName = 'GROUP'

            # 收到了红包
            if content == '收到红包，请在手机上查看':
                msg['message'] = content

            # 指定了消息内容
            if 'message' in msg.keys():
                content = msg['message']

        if groupName is not None:
            # print '%s |%s| %s -> %s: %s' % (message_id, groupName.strip(), srcName.strip(), dstName.strip(), content.replace('<br/>', '\n'))
            logging.info('%s |%s| %s -> %s: %s' % (message_id, groupName.strip().decode('utf8'),
                                                   srcName.strip().decode('utf8'), dstName.strip().decode('utf8'), content.replace('<br/>', '\n').decode('utf8')))
        else:
            # print '%s %s -> %s: %s' % (message_id, srcName.strip(), dstName.strip(), content.replace('<br/>', '\n'))
            logging.info('%s %s -> %s: %s' % (message_id, srcName.strip().decode('utf8'),
                                              dstName.strip().decode('utf8'), content.replace('<br/>', '\n').decode('utf8')))
        self.postProcessMsg(message_id, srcName, dstName, content)

    def _searchContent(self, key, content, fmat='attr'):
        if fmat == 'attr':
            pm = re.search(key + '\s?=\s?"([^"<]+)"', content)
            if pm:
                return pm.group(1)
        elif fmat == 'xml':
            pm = re.search('<{0}>([^<]+)</{0}>'.format(key), content)
            if not pm:
                pm = re.search(
                    '<{0}><\!\[CDATA\[(.*?)\]\]></{0}>'.format(key), content)
            if pm:
                return pm.group(1)
        return '未知'

    def postProcessMsg(self, message_id, srcName, dstName, content):
        from os.path import expanduser
        home = expanduser("~")
        interestedSender = [u'微信支付', u'广发信用卡', u'招商银行信用卡', u'手机充值']
        msgHome = '%s/weixinmsg/%s' % (home, srcName)
        if srcName.decode('utf8') in interestedSender:
            if not os.path.isdir(msgHome):
                os.makedirs(msgHome)
            with open('%s/%s.json' % (msgHome, message_id), 'w+') as fp:
                fp.write(content)

    @catchKeyboardInterrupt
    def start(self):
        if sys.platform.startswith('win'):
            import thread
            thread.start_new_thread(self.listenMsgMode())
        else:
            listenProcess = multiprocessing.Process(target=self.listenMsgMode)
            listenProcess.start()
        while True:
            text = raw_input('')
            if text == 'quit':
                listenProcess.terminate()
                print('[*] 退出微信')
                logging.debug('[*] 退出微信')
                exit()
            elif text[:2] == '->':
                [name, word] = text[2:].split(':')
                if name == 'all':
                    self.sendMsgToAll(word)
                else:
                    self.sendMsg(name, word)
            elif text[:3] == 'm->':
                [name, file] = text[3:].split(':')
                self.sendMsg(name, file, True)
            elif text[:3] == 'f->':
                print '发送文件'
                logging.debug('发送文件')
            elif text[:3] == 'i->':
                print '发送图片'
                [name, file_name] = text[3:].split(':')
                self.sendImg(name, file_name)
                logging.debug('发送图片')
            elif text[:3] == 'e->':
                print '发送表情'
                [name, file_name] = text[3:].split(':')
                self.sendEmotion(name, file_name)
                logging.debug('发送表情')


class UnicodeStreamFilter:

    def __init__(self, target):
        self.target = target
        self.encoding = 'utf-8'
        self.errors = 'replace'
        self.encode_to = self.target.encoding

    def write(self, s):
        if type(s) == str:
            s = s.decode('utf-8')
        s = s.encode(self.encode_to, self.errors).decode(self.encode_to)
        self.target.write(s)

    def flush(self):
        self.target.flush()

# if sys.stdout.encoding != 'cp936' or sys.stdout.encoding == 'sacii':
if sys.stdout.encoding != 'utf-8' or sys.stdout.encoding == 'utf8':
    sys.stdout = UnicodeStreamFilter(sys.stdout)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='weixin listener')
    parser.add_argument('-args', '--args', dest='args', help="args file path")
    parser.add_argument('-cookie', '--cookie', dest='cookie', help="cookie file path")

    p = parser.parse_args(sys.argv[1:])

    l = WeixinListener(p.args, p.cookie)
    l.start()
