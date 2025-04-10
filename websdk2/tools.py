#!/usr/bin/env python
# -*-coding:utf-8-*-
"""
Author : ss
date   : 2018年4月12日
role   : 工具类
"""

import sys
import re
import time
import redis
import logging
from shortuuid import uuid
import subprocess
from concurrent.futures import ThreadPoolExecutor
from abc import ABC, abstractmethod
from .consts import const


def singleton(class_):
    instances = {}

    def getinstance(*args, **kwargs):
        if class_ not in instances:
            instances[class_] = class_(*args, **kwargs)
        return instances[class_]

    return getinstance


def bytes_to_unicode(input_bytes):
    if sys.version_info.major >= 3:
        return str(input_bytes, encoding='utf-8')
    else:
        return (input_bytes).decode('utf-8')


def convert(data):
    if isinstance(data, bytes):  return data.decode('utf8')
    if isinstance(data, dict):   return dict(map(convert, data.items()))
    if isinstance(data, tuple):  return map(convert, data)
    return data


def check_password(data):
    return True if re.search("^(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).*$", data) and len(data) >= 8 else False


def is_mail(text, login_mail=None):
    if login_mail:
        if re.match(r'[0-9a-zA-Z_]{0,19}@%s' % login_mail, text):
            return True
        else:
            return False
    p = re.compile(r"[^@]+@[^@]+\.[^@]+")
    # if re.match(r'^[0-9a-zA-Z_]{0,19}@[0-9a-zA-Z]{1,13}\.[com,cn,net]{1,3}$', text):
    if p.match(text):
        return True
    else:
        return False


def is_tel(tel):
    ### 检查是否是手机号
    ret = re.match(r"^1[35678]\d{9}$", tel)
    if ret:
        return True
    else:
        return False


def check_contain_chinese(check_str):
    ### 检查是否包含汉字
    """
    :param check_str:
    :return:
    """
    for ch in check_str:
        if u'\u4e00' <= ch <= u'\u9fff':
            return True
    return False


class Executor(ThreadPoolExecutor):
    """ 线程执行类 """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not getattr(cls, '_instance', None):
            cls._instance = ThreadPoolExecutor(max_workers=10)
        return cls._instance


def exec_shell(cmd):
    '''执行shell命令函数'''
    sub = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, stderr = sub.communicate()
    ret = sub.returncode
    if ret == 0:
        return ret, stdout.decode('utf-8').split('\n')
    else:
        return ret, stdout.decode('utf-8').replace('\n', '')


class RunningProcess:
    def __init__(self, process):
        self.process = process
        self.start_time = time.time()

    def is_running(self):
        return bool(self.process.poll() is None)

    def read_line(self):
        return self.process.stdout.readline()

    @property
    def unread_lines(self):
        lines = self.process.stdout.readlines()
        self.process.stdout.close()
        return lines

    @property
    def run_state(self):
        return bool(self.process.poll() == 0)

    def is_timeout(self, exec_time=600):
        duration = time.time() - self.start_time
        if duration > exec_time:
            self.process.terminate()
            self.process.wait()
            self.process.communicate()
            # print("execute timeout, execute time {}, it's killed.".format(duration))
            return True
        return False


class RedisLock(object):
    def __init__(self, key, **conf):
        if not conf:
            from .configs import configs
            __redis_info = configs.get(const.REDIS_CONFIG_ITEM, None).get(const.DEFAULT_RD_KEY, None)
            conf = dict(host=__redis_info.get(const.RD_HOST_KEY), port=__redis_info.get(const.RD_PORT_KEY, 6379),
                        db=__redis_info.get(const.RD_DB_KEY, 0), password=__redis_info.get(const.RD_PASSWORD_KEY, None))

        self.rdcon = redis.Redis(host=conf.get('host'), port=conf.get('port'), password=conf.get('password'),
                                 db=conf.get('db', 0))
        self._lock = 0
        self.lock_key = "{}_dynamic_test".format(key)

    @staticmethod
    def get_lock(cls, key_timeout=59, func_timeout=59):
        ### key过期时间为一分钟，30秒内key任务没有完成则返回失败
        start_time = time.time()
        while cls._lock != 1:
            timestamp = time.time() + key_timeout + 1
            cls._lock = cls.rdcon.setnx(cls.lock_key, timestamp)
            lock_key = cls.rdcon.get(cls.lock_key)

            if time.time() - start_time > func_timeout:
                return False
            if cls._lock == 1 or (
                    time.time() > float(lock_key) and time.time() > float(cls.rdcon.getset(cls.lock_key, timestamp))):
                return True
            else:
                time.sleep(1)

    @staticmethod
    def release(cls):
        ### 释放lock
        lock_key = cls.rdcon.get(cls.lock_key)
        if lock_key and time.time() < float(lock_key): cls.rdcon.delete(cls.lock_key)


def deco(cls, release=False):
    """ 示例
    @deco(RedisLock("redis_lock_key", **dict(host='127.0.0.1', port=6379, password="", db=1)))
    def do_func():
        print("the func called.")
        time.sleep(50)
        print("the func end")


    do_func()
    """

    def _deco(func):
        def __deco(*args, **kwargs):
            if not cls.get_lock(cls): return False
            try:
                return func(*args, **kwargs)
            finally:
                ### 执行完就释放key，默认不释放
                if release: cls.release(cls)

        return __deco

    return _deco


def now_timestamp() -> int:
    return int(round(time.time() * 1000))


class LockClientV2(ABC):
    @abstractmethod
    def get_lock(self, key_timeout=59, func_timeout=5):
        pass

    @abstractmethod
    def release(self):
        pass


class RedisLockV2(LockClientV2):
    def __init__(self, key, **conf):
        # 注意: configs.import_dict(**settings) 是必须的
        if not conf:
            from .configs import configs
            redis_config = configs.get(const.REDIS_CONFIG_ITEM, {})
            default_config = redis_config.get(const.DEFAULT_RD_KEY, {})

            conf = {
                'host': default_config.get(const.RD_HOST_KEY, 'localhost'),
                'port': default_config.get(const.RD_PORT_KEY, 6379),
                'db': default_config.get(const.RD_DB_KEY, 0),
                'password': default_config.get(const.RD_PASSWORD_KEY)
            }
        self.redis_client: redis.Redis = redis.Redis(**conf)
        self._lock = 0
        self.lock_key = f"{key}_dynamic"
        self.uuid = str(uuid())

    def get_lock(self, key_timeout=59, func_timeout=5):
        # key过期时间为一分钟，30秒内key任务没有完成则返回失败
        start_time = time.time()
        redis_client: redis.Redis = self.redis_client
        _uuid = self.uuid
        _lock_key = self.lock_key

        while time.time() - start_time < func_timeout:
            ok = redis_client.set(_lock_key, _uuid, nx=True, ex=key_timeout)
            got_uuid = convert(redis_client.get(_lock_key))
            if got_uuid == _uuid and ok:
                return True
            time.sleep(1)
        return False

    def release(self):
        # 释放lock
        redis_client: redis.Redis = self.redis_client
        _uuid = self.uuid
        _lock_key = self.lock_key
        got_uuid = convert(redis_client.get(_lock_key))

        if got_uuid == _uuid:
            redis_client.delete(_lock_key)


def deco_v2(cls: LockClientV2, release=False, key_timeout=59, func_timeout=5):
    """ 示例
    @deco_v2(RedisLockV2("codo:xxxx:v2:xxxx"), release=True, key_timeout=30)
    def do_func():
        print("the func called.")
        time.sleep(50)
        print("the func end")


    do_func()


    :param
    cls: RedisLockV2实例
    release: 是否释放key，默认不释放
    key_timeout: key过期时间
    func_timeout: 函数争抢锁超时时间
    """

    def _deco(func):
        def __deco(*args, **kwargs):
            try:
                ok = cls.get_lock(key_timeout=key_timeout, func_timeout=func_timeout)
                if not ok:
                    return False
            except Exception as e:
                logging.error(f"[deco_v2] get lock func={func.__name__} error={str(e)}")
                return False
            try:
                return func(*args, **kwargs)
            finally:
                # 执行完就释放key，默认不释放
                if release:
                    cls.release()

        return __deco

    return _deco
