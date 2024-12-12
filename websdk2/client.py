#!/usr/bin/env python
# -*- coding: utf-8 -*-
""""
Contact : 191715030@qq.com
Author : shenshuo
Date   : 2018年2月5日13:37:54
Desc   : 处理API请求
"""

import json
import requests
from urllib.parse import urlencode
from typing import Union, Optional
import logging
from .consts import const
from .configs import configs
from tornado.httpclient import AsyncHTTPClient

logger = logging.getLogger(__name__)


class AcsClient:
    def __init__(self, request=None, auth_key=None, headers=None, endpoint='http://gw.opendevops.cn',
                 request_timeout=10):
        if request:
            self.headers = request.headers
        elif headers:
            self.headers = headers
        elif auth_key:
            self.headers = {"Cookie": 'auth_key={}'.format(auth_key)}
        else:
            self.headers = {"Cookie": 'auth_key={}'.format(configs.get(const.API_AUTH_KEY))}

        if 'If-None-Match' in self.headers: del self.headers['If-None-Match']
        self.endpoint = endpoint
        if configs.get(const.WEBSITE_API_GW_URL) and endpoint == 'http://gw.opendevops.cn':
            self.endpoint = configs.get(const.WEBSITE_API_GW_URL)
        self.headers['Sdk-Method'] = 'zQtY4sw7sqYspVLrqV'
        self.request_timeout = request_timeout

    # 设置返回为json
    def do_action(self, **kwargs):
        kwargs = self.with_params_data_url(**kwargs)
        response = requests.request(kwargs.get('method'), kwargs.get('url'), headers=self.headers,
                                    data=kwargs.get('body'), timeout=self.request_timeout)

        return response.text

    # 返回完整信息
    def do_action_v2(self, **kwargs):
        kwargs = self.with_params_data_url(**kwargs)
        response = requests.request(kwargs.get('method'), kwargs.get('url'), headers=self.headers,
                                    data=kwargs.get('body'), timeout=self.request_timeout)
        return response

    def do_action_v3(self, **kwargs):
        kwargs = self.with_params_data_url(**kwargs)

        request_params = {
            'method': kwargs.get('method'),
            'url': kwargs.get('url'),
            'headers': self.headers,
            'timeout': self.request_timeout
        }

        if kwargs.get('json'):
            request_params['json'] = kwargs['json']
        else:
            request_params['data'] = kwargs.get('body')

        response = requests.request(**request_params)
        return response

    async def do_action_with_async(self, **kwargs):

        body = await self._implementation_of_do_action(**kwargs)
        return body

    async def _implementation_of_do_action(self, **kwargs):
        http_client = AsyncHTTPClient()
        request = self.with_params_data_url(**kwargs)
        # json=kwargs.get('json')
        response = await http_client.fetch(request.get('url'), method=request.get('method'), raise_error=False,
                                           body=request.get('body'), headers=self.headers,
                                           request_timeout=self.request_timeout)

        return response.body

    # import aiohttp
    # async def do_action_with_async_v2(self, **kwargs):
    #     body = await self._implementation_of_do_aiohttp(**kwargs)
    #     return body
    #
    # async def _implementation_of_do_aiohttp(self, **kwargs):
    #     async with aiohttp.ClientSession() as session:
    #         request = self.with_params_data_url(**kwargs)
    #         async with session.request(method=request['method'], url=request['url'],
    #                                    headers=self.headers, data=request.get('body'),
    #                                    timeout=self.request_timeout) as response:
    #             return await response.read()

    # def with_params_data_url(self, **kwargs):
    #     # 重新组装URL
    #     url = "{}{}".format(self.endpoint, kwargs['url'])
    #     kwargs['url'] = url
    #
    #     if not kwargs['method']: kwargs['method'] = 'GET'
    #
    #     # logging.debug(f"with_params_data_url {kwargs}")
    #     body = kwargs.get('body', {})
    #     req_json = kwargs.get('json')
    #
    #     if kwargs['method'] in ['POST', 'post', 'PATCH', 'patch', 'PUT', 'put']:
    #         if not (body or req_json):
    #             raise TypeError('method {},  body can not be empty'.format(kwargs['method']))
    #         else:
    #             if not isinstance(body, dict):
    #                 json.loads(body)
    #
    #     if body and isinstance(body, dict): kwargs['body'] = json.dumps(body)
    #
    #     params = kwargs.get('params')
    #     if params: kwargs['url'] = "{}?{}".format(url, urlencode(params))
    #
    #     if not self.headers: self.headers = kwargs.get('headers', {})
    #
    #     if kwargs['method'] not in ['GET', 'get']: self.headers['Content-Type'] = 'application/json'
    #
    #     return kwargs

    def with_params_data_url(self, **kwargs) -> dict:
        endpoint = self.endpoint.strip("'").strip('"')
        kwargs['url'] = f"{endpoint}{kwargs.get('url', '')}"
        kwargs['method'] = kwargs.get('method', 'GET').upper()

        body: Union[dict, str] = kwargs.get('body', {})
        req_json: Optional[dict] = kwargs.get('json')

        if kwargs['method'] in {'POST', 'PATCH', 'PUT'}:
            if not (body or req_json):
                raise TypeError(f"Method {kwargs['method']} requires a non-empty body or JSON payload.")
            if body and not isinstance(body, dict):
                try:
                    body = json.loads(body)
                except json.JSONDecodeError as e:
                    raise TypeError(f"Invalid JSON body: {e}")

        if body and isinstance(body, dict):
            kwargs['body'] = json.dumps(body)

        params: Optional[dict] = kwargs.get('params')
        if params:
            kwargs['url'] = f"{kwargs['url']}?{urlencode(params)}"

        kwargs['headers'] = kwargs.get('headers', self.headers or {})

        if kwargs['method'] != 'GET':
            kwargs['headers'].setdefault('Content-Type', 'application/json')

        return kwargs

    @staticmethod
    def help():
        help_info = """
        headers = {"Cookie": 'auth_key={}'.format(auth_key)}
        ### 三种实例化方式
        1. client = AcsClient(endpoint=endpoint, headers=headers)
        2. client = AcsClient(endpoint=endpoint, request=self.request)
        3. client = AcsClient(endpoint=endpoint, auth_key=auth_key)
        
        调用： 传入api 的参数，可以参考下面示例
        
        同步
        response = client.do_action(**api_set.get_users) 
        print(json.loads(response))
        
        异步
        # import asyncio
        # loop = asyncio.get_event_loop()
        # ### 使用gather或者wait可以同时注册多个任务，实现并发
        # # task1 = asyncio.ensure_future(coroutine1)
        # # task2 = asyncio.ensure_future(coroutine2)
        # # tasks = asyncio.gather(*[task1, task2])
        # # loop.run_until_complete(tasks)
        # ### 单个使用
        # response = loop.run_until_complete(client.do_action_with_async(**api_set.get_users))
        # response = json.loads(response)
        # print(response)
        # loop.close()
        
        tornado 项目内必须使用异步，不过可以直接使用
        from websdk2.client import AcsClient
        from websdk2.api_set import api_set
        async def get(self):
            endpoint = ''
            client = AcsClient(endpoint=endpoint, headers=self.request.headers)
            response = await client.do_action_with_async(**api_set.get_users)
            return self.write(response)
        
         """
        return help_info


if __name__ == '__main__':
    pass
