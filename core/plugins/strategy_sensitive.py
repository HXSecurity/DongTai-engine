#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author: owefsad@huoxian.cn
# datetime: 2021/10/22 下午2:29
# project: DongTai-engine
# desc: data rule, response field rule, sql field rule
import re

import jq
from dongtai.models.sensitive_info import IastSensitiveInfoRule
from dongtai.utils import const
from celery.apps.worker import logger

from core.plugins.strategy_headers import save_vul


def parse_json_response(res_body):
    try:
        import json
        return json.loads(res_body)
    except Exception as e:
        return None


def check_response_content(method_pool):
    rules = IastSensitiveInfoRule.objects.filter(status=const.HOOK_TYPE_ENABLE)
    needed_check_data = {}
    if rules.values("id").count() > 0:
        if method_pool.res_body:
            needed_check_data['HTTP Response Body'] = method_pool.res_body
        if method_pool.req_params:
            needed_check_data['HTTP Request Params'] = method_pool.req_params
        if method_pool.req_data:
            needed_check_data['HTTP Request Data'] = method_pool.req_data
    else:
        return

    json_response = parse_json_response(method_pool.res_body)
    for rule in rules:
        try:
            if rule.pattern_type.id == 1:
                pattern = re.compile(rule.pattern, re.M)
                for key, value in needed_check_data.items():
                    try:
                        result = pattern.search(value)
                        if result and result.groups():
                            save_vul(
                                vul_type=rule.strategy.vul_type,
                                method_pool=method_pool,
                                position=key,
                                data=result.group(0)
                            )
                    except Exception as e:
                        logger.error(
                            f'check_response_content error, rule: {rule.id}, rule name: {rule.strategy.vul_type}, reason: {e}')
            elif json_response and rule.pattern_type.id == 2:
                pattern = jq.compile(rule.pattern)
                result = pattern.input(json_response).all()
                if result:
                    save_vul(
                        vul_type=rule.strategy.vul_type,
                        method_pool=method_pool,
                        position='HTTP Response Body',
                        data=' '.join(result)
                    )
        except Exception as e:
            logger.error(
                f'check_response_content error, rule: {rule.id}, rule name: {rule.strategy.vul_type}, reason: {e}')

    search_id_card_leak(method_pool)


def search_id_card_leak(method_pool):
    pattern = re.compile(
        r'([1-9]\d{5}(18|19|([23]\d))\d{2}((0[1-9])|(10|11|12))(([0-2][1-9])|10|20|30|31)\d{3}[0-9Xx])|([1-9]\d{5}\d{2}((0[1-9])|(10|11|12))(([0-2][1-9])|10|20|30|31)\d{3})',
        re.M)
    needed_check_data = {}
    needed_check_data['HTTP Response Body'] = method_pool.res_body
    needed_check_data['HTTP Request Params'] = method_pool.req_params
    needed_check_data['HTTP Request Data'] = method_pool.req_data

    for key, value in needed_check_data.items():
        try:
            if value is None:
                continue
            result = pattern.search(value)
            if result is None:
                continue
            card = result.group(1)
            if check_id_card(card):
                # todo: add highlight to id_card
                save_vul(vul_type='ID Number Leak', method_pool=method_pool, position=key, data=card)
        except Exception as e:
            logger.error(
                f'check_response_content error, rule name: ID Number Leak, Method Pool ID: {method_pool.id}, reason: {e}')


def check_id_card(id_card):
    try:
        from id_validator import validator
        return validator.is_valid(id_card)
    except:
        return False
