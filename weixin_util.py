#!/usr/bin/env python
# encoding: utf-8

import logging
import sys
import time
import urllib2
import urllib
import json
import httplib


def _decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = _decode_dict(item)
        rv.append(item)
    return rv


def _decode_dict(data):
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = _decode_list(value)
        elif isinstance(value, dict):
            value = _decode_dict(value)
        rv[key] = value
    return rv


class WeixinUtil:

    def __init__(self):
        pass

    @staticmethod
    def run(str, func, *args):
        WeixinUtil.echo(str)
        if func(*args):
            print '成功'
            logging.debug('%s... 成功' % (str))
        else:
            print('失败\n[*] 退出程序')
            logging.debug('%s... 失败' % (str))
            logging.debug('[*] 退出程序')
            sys.exit(0)

    @staticmethod
    def echo(str):
        sys.stdout.write(str)
        sys.stdout.flush()

    @staticmethod
    def get(url, api=None):
        request = urllib2.Request(url=url)
        request.add_header('Referer', 'https://wx.qq.com/')
        if api == 'webwxgetvoice':
            request.add_header('Range', 'bytes=0-')
        if api == 'webwxgetvideo':
            request.add_header('Range', 'bytes=0-')
        try:
            response = urllib2.urlopen(request)
            data = response.read()
            logging.debug(url)
            return data
        except urllib2.HTTPError, e:
            logging.error('HTTPError = ' + str(e.code))
        except urllib2.URLError, e:
            logging.error('URLError = ' + str(e.reason))
        except httplib.HTTPException, e:
            logging.error('HTTPException')
        except Exception:
            import traceback
            logging.error('generic exception: ' + traceback.format_exc())
        return ''

    @staticmethod
    def post(url, params, jsonfmt=True):
        if jsonfmt:
            request = urllib2.Request(url=url, data=json.dumps(params))
            request.add_header(
                'ContentType', 'application/json; charset=UTF-8')
        else:
            request = urllib2.Request(url=url, data=urllib.urlencode(params))


        try:
            response = urllib2.urlopen(request)
            data = response.read()
            if jsonfmt:
                return json.loads(data, object_hook=_decode_dict)
            return data
        except urllib2.HTTPError, e:
            logging.error('HTTPError = ' + str(e.code))
        except urllib2.URLError, e:
            logging.error('URLError = ' + str(e.reason))
        except httplib.HTTPException, e:
            logging.error('HTTPException')
        except Exception:
            import traceback
            logging.error('generic exception: ' + traceback.format_exc())

        return ''