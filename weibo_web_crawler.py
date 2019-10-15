# -*- coding: UTF-8 -*-

from collections import OrderedDict
from datetime import datetime, timedelta
import json
from lxml import etree
import math
import requests
from requests.adapters import HTTPAdapter
import os
import random
import re
import sys
from time import sleep
from tqdm import tqdm
import traceback


"""
    Usage:
        python weibo_web_crawler.py path
    
    Args:
        path: Input path (a file including one user_id, start_date, 
              and end_date per line).
    
    Notice:
        Input file format:
            user_id [start_date] [end_date]
            (If end_date is specific and no specific start_date, use '-'. 
            If start_date is specific and no specific end_date, 
            no other input is needed.)
            (Default: Posts of all time.)

            e.g.
                1234567890 2019-01-01 2019-06-01
                0987654321 2018-01-01 2019-01-01
                1111111111 - 2019-02-01
                2222222222 2019-03-01
"""

URL = 'https://m.weibo.cn/api/container/getIndex?'
URL_LONG = 'https://m.weibo.cn/detail/%s'

START_DATE = '1900-01-01'
END_DATE = datetime.now().strftime("%Y-%m-%d")

LOG_PATH = os.path.join('.', 'output_{}.log'.format(
    datetime.now().strftime("%Y%m%d")))
RESULT_PATH = os.path.join('.', 'results')

PATTERN_DATE = r'\d\d\d\d-\d\d-\d\d'

"""
SELECT_FORWARDED_POST:
    True: Select forwarded and original posts. 
    False: Select only original posts.
"""
SELECT_FORWARDED_POST = False

selected_post_list = list()
post_id_list = list()


def get_pics(post_info):
    if post_info.get('pics'):
        pic_info = post_info['pics']
        pic_list = [pic['large']['url'] for pic in pic_info]
        pics = ', '.join(pic_list)
    else:
        pics = ''

    return pics

def get_video_url(post_info):
    video_url = ''
    if post_info.get('page_info'):
        if post_info['page_info'].get('media_info'):
            media_info = post_info['page_info']['media_info']
            video_url = media_info.get('mp4_720p_mp4')
            if not video_url:
                video_url = media_info.get('mp4_hd_url')
                if not video_url:
                    video_url = media_info.get('mp4_sd_url')
                    if not video_url:
                        video_url = ''

    return video_url

def get_location(selector):
    location_icon = 'timeline_card_small_location_default.png'
    span_list = selector.xpath('//span')

    location = ''
    for i, span in enumerate(span_list):
        if span.xpath('img/@src'):
            if location_icon in span.xpath('img/@src')[0]:
                location = span_list[i + 1].xpath('string(.)')
                break

    return location

def get_topics(selector):
    span_list = selector.xpath("//span[@class='surl-text']")

    topics = ''
    topic_list = []
    for span in span_list:
        text = span.xpath('string(.)')
        if len(text) > 2 and text[0] == '#' and text[-1] == '#':
            topic_list.append(text[1: -1])

    if topic_list:
        topics = ', '.join(topic_list)

    return topics

def get_at_users(selector):
    a_list = selector.xpath('//a')

    at_users = ''
    at_list = []
    for a in a_list:
        if '@' + a.xpath('@href')[0][3: ] == a.xpath('string(.)'):
            at_list.append(a.xpath('string(.)')[1: ])

    if at_list:
        at_users = ', '.join(at_list)

    return at_users

def string_to_int(string):
    if isinstance(string, int):
        return string
    elif string.endswith(u'万+'):
        string = int(string[: -2] + '0000')
    elif string.endswith(u'万'):
        string = int(string[: -1] + '0000')

    return int(string)

def standardize_info(info):
    for key, value in info.items():
        if 'int' not in str(type(value)) and 'long' not in str(
            type(value)) and 'bool' not in str(type(value)):
            info[key] = value.replace(u"\u200b", "").encode(sys.stdout.encoding, 
                "ignore").decode(sys.stdout.encoding)
    
    return info

def standardize_date(created_at):
    if u"刚刚" in created_at:
        created_at = datetime.now().strftime("%Y-%m-%d")
    elif u"分钟" in created_at:
        minute = created_at[: created_at.find(u"分钟")]
        minute = timedelta(minutes=int(minute))
        created_at = (datetime.now() - minute).strftime("%Y-%m-%d")
    elif u"小时" in created_at:
        hour = created_at[: created_at.find(u"小时")]
        hour = timedelta(hours=int(hour))
        created_at = (datetime.now() - hour).strftime("%Y-%m-%d")
    elif u"昨天" in created_at:
        day = timedelta(days=1)
        created_at = (datetime.now() - day).strftime("%Y-%m-%d")
    elif created_at.count('-') == 1:
        year = datetime.now().strftime("%Y")
        created_at = year + "-" + created_at

    return created_at

def parse_post(post_info):
    post = OrderedDict()

    if post_info['user']:
        post['user_id'] = post_info['user']['id']
        post['screen_name'] = post_info['user']['screen_name']
    else:
        post['user_id'] = ''
        post['screen_name'] = ''

    post['id'] = int(post_info['id'])
    post['bid'] = post_info['bid']
    text_body = post_info['text']
    selector = etree.HTML(text_body)
    post['text'] = etree.HTML(text_body).xpath('string(.)')
    post['pics'] = get_pics(post_info)
    post['video_url'] = get_video_url(post_info)
    post['location'] = get_location(selector)
    post['created_at'] = post_info['created_at']
    post['source'] = post_info['source']
    post['attitudes_count'] = string_to_int(post_info['attitudes_count'])
    post['comments_count'] = string_to_int(post_info['comments_count'])
    post['reposts_count'] = string_to_int(post_info['reposts_count'])
    post['topics'] = get_topics(selector)
    post['at_users'] = get_at_users(selector)

    return standardize_info(post)

def get_long_post(post_id):
    url = URL_LONG % post_id

    html = requests.get(url).text
    html = html[html.find('"status":'): ]
    html = html[:html.rfind('"hotScheme"')]
    html = html[:html.rfind(',')]
    html = '{' + html + '}'

    json_request = json.loads(html, strict=False)
    post_info = json_request.get('status')

    if post_info:
        return parse_post(post_info)

def is_pinned_post(info):
    post_info = info['mblog']
    title = post_info.get('title')

    if title and title.get('text') == u'置顶':
        return True
    else:
        return False

def print_one_post(post):
    print('id: {}'.format(post['id']))
    print('text: {}'.format(post['text']))
    print('pics: {}'.format(post['pics']))
    print('location: {}'.format(post['location']))
    print('created_at: {}'.format(post['created_at']))
    print('source: {}'.format(post['source']))
    print('attitudes_count: {}'.format(post['attitudes_count']))
    print('comments_count: {}'.format(post['comments_count']))
    print('reposts_count: {}'.format(post['reposts_count']))
    print('topics: {}'.format(post['topics']))
    print('at_users: {}'.format(post['at_users']))

def print_posts(post):
    if post.get('retweet'):
        print_one_post(post['retweet'])
        print()

    print_one_post(post)
    print()

def print_user_info(user_info):
    print('\nUser info: ')
    print('id: {}'.format(user_info['id']))
    print('screen_name: {}'.format(user_info['screen_name']))
    print('gender: {}'.format(user_info['gender']))
    print('statuses_count: {}'.format(user_info['statuses_count']))
    print('followers_count: {}'.format(user_info['followers_count']))
    print('follow_count: {}'.format(user_info['follow_count']))
    print('verified_reason: {}'.format(user_info['verified_reason']))
    print('description: {}'.format(user_info['description']))
    print()

def get_one_post(info):
    post_info = info['mblog']
    post_id = post_info['id']
    retweeted_status = post_info.get('retweeted_status')
    is_long = post_info['isLongText']

    try:
        # Forwarded post.
        if retweeted_status:
            retweet_id = retweeted_status['id']
            is_long_retweet = retweeted_status['isLongText']

            if is_long:
                post = get_long_post(post_id)
                if not post:
                    post = parse_post(post_info)
            else:
                post = parse_post(post_info)

            if is_long_retweet:
                retweet = get_long_post(retweet_id)
                if not retweet:
                    retweet = parse_post(retweeted_status)
            else:
                retweet = parse_post(retweeted_status)

            retweet['created_at'] = standardize_date(
                retweeted_status['created_at'])
            post['retweet'] = retweet
        # Original post.
        else: 
            if is_long:
                post = get_long_post(post_id)
                if not post:
                    post = parse_post(post_info)
            else:
                post = parse_post(post_info)

        post['created_at'] = standardize_date(post_info['created_at'])

        return post
    except Exception as e:
        msg = '\n{} - Warning: No permission to see this post (id: {}).\n'.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(retweet_id))
        print(msg)
        with open(LOG_PATH, 'a', encoding='utf8') as output_log:
            output_log.write(msg)

def get_one_page(user_id, page):
    params = {'containerid': '107603' + str(user_id), 'page': page}
    request = requests.get(URL, params).json()

    if request['ok']:
        post_list = request['data']['cards']
        for post in post_list:
            if post['card_type'] == 9:
                post_info = get_one_post(post)
                if post_info:
                    if post_info['id'] in post_id_list:
                        continue

                    created_at = datetime.strptime(
                        post_info['created_at'], "%Y-%m-%d")
                    start_date = datetime.strptime(
                        START_DATE, "%Y-%m-%d")
                    end_date = datetime.strptime(
                        END_DATE, "%Y-%m-%d")

                    # The web crawler explores posts from new to old.
                    if created_at < start_date:
                        if is_pinned_post(post):
                            continue
                        else:
                            return True
                    
                    if created_at > end_date:
                        continue

                    if SELECT_FORWARDED_POST or 'retweet' not in post_info.keys():
                        selected_post_list.append(post_info)
                        post_id_list.append(post_info['id'])
                        # print_posts(post_info)
    else:
        msg = '\n{} - Warning: Failed to get this page (page: {}).\n'.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), page)
        print(msg)
        with open(LOG_PATH, 'a', encoding='utf8') as output_log:
            output_log.write(msg)

def get_user_info(user_id):
    params = {'containerid': '100505' + str(user_id)}
    request = requests.get(URL, params).json()

    if request['ok']:
        info = request['data']['userInfo']

        user_info = dict()
        user_info['id'] = user_id
        user_info['screen_name'] = info.get('screen_name', '')
        user_info['gender'] = info.get('gender', '')
        user_info['statuses_count'] = info.get('statuses_count', 0)
        user_info['followers_count'] = info.get('followers_count', 0)
        user_info['follow_count'] = info.get('follow_count', 0)
        user_info['description'] = info.get('description', '')
        user_info['profile_url'] = info.get('profile_url', '')
        user_info['profile_image_url'] = info.get('profile_image_url', '')
        user_info['avatar_hd'] = info.get('avatar_hd', '')
        user_info['urank'] = info.get('urank', 0)
        user_info['mbrank'] = info.get('mbrank', 0)
        user_info['verified'] = info.get('verified', False)
        user_info['verified_type'] = info.get('verified_type', 0)
        user_info['verified_reason'] = info.get('verified_reason', '')

        return standardize_info(user_info)
    else:
        msg = '\n{} - Error: Failed to get the info.\n'.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        with open(LOG_PATH, 'w', encoding='utf8') as output_log:
            output_log.write(msg)
        raise Exception(msg)

def download_one_file(url, save_path):
    try:
        if not os.path.isfile(save_path):
            session = requests.Session()
            session.mount(url, HTTPAdapter(max_retries=5))
            downloaded = session.get(url, timeout=(5, 10))
            with open(save_path, 'wb') as file:
                file.write(downloaded.content)
    except Exception as e:
        msg = '\n{} - Warning: Failed to download this file (url: {}).\n'.format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), url)
        print(msg)
        with open(LOG_PATH, 'a', encoding='utf8') as output_log:
            output_log.write(msg)
        traceback.print_exc(file=open(LOG_PATH, 'a', encoding='utf8'))

def download_images_and_videos(save_path):
    print('Start downloading images and videos ...\n')
    for post in tqdm(selected_post_list, desc='Progress'):
        file_prefix = post['created_at'][: 11].replace('-', '') + '_' + str(post['id'])
        if post['pics']:
            if ', ' in post['pics']:
                post['pics'] = post['pics'].split(', ')
                for i, url in enumerate(post['pics']):
                    file_suffix = url[url.rfind('.'): ]
                    file_name = file_prefix + '_' + str(i + 1) + file_suffix
                    file_path = os.path.join(save_path, 'images', file_name) 
                    download_one_file(url, file_path)
        if post['video_url']:
            file_name = file_prefix + '.mp4'
            file_path = os.path.join(save_path, 'videos', file_name) 
            download_one_file(post['video_url'], file_path)
    print('Finish downloading images and videos ...\n')

def web_crawler(user_id_list):
    for x in user_id_list:
        if len(x) != 1:
            if re.match(PATTERN_DATE, x[1]):
                START_DATE = x[1]
            if len(x) == 3 and re.match(PATTERN_DATE, x[2]):
                END_DATE = x[2]
        user_id = x[0]

        user_info = get_user_info(user_id)
        # print_user_info(user_info)
        page_count = int(math.ceil(user_info['statuses_count'] / 10.0))

        selected_post_list = list()
        post_id_list = list()

        tmp_page = 0
        random_pages = random.randint(1, 5)

        print('Start exploring ...\n')
        for page in tqdm(range(1, page_count + 1), desc='Progress'):
            print('\nPage: %d.\n' % page)
            # Check if it's over.
            if get_one_page(user_id, page):
                break

            # Prevent rejection.
            if page - tmp_page == random_pages and page < page_count:
                sleep(random.randint(6, 10))
                tmp_page = page
                random_pages = random.randint(1, 5)
        print('Finish exploring ...\n')

        save_path = os.path.join(RESULT_PATH, user_info['screen_name'])

        if not os.path.exists(RESULT_PATH): 
            os.makedirs(RESULT_PATH)
        if not os.path.exists(save_path): 
            os.makedirs(save_path)
        if not os.path.exists(os.path.join(save_path, 'images')): 
            os.makedirs(os.path.join(save_path, 'images'))
        if not os.path.exists(os.path.join(save_path, 'videos')): 
            os.makedirs(os.path.join(save_path, 'videos'))

        download_images_and_videos(save_path)
        
if __name__ == '__main__':
    assert len(sys.argv) == 2, 'Error: The number of arguments is incorrect.'

    user_id_list = list()
    with open(sys.argv[1], 'r', encoding='utf8') as input_file:
        for line in input_file:
            tmp = line.split()
            if len(tmp) != 0 and tmp[0].isdigit():
                user_id_list.append(tmp)  

    web_crawler(user_id_list)
    