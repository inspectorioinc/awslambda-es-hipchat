#!/usr/bin/env python
# -*- coding: utf-8 -*-
# File: hipchat.py
# Author: Khuong Nguyen <khuong@inspectorio.com>
# Date: 14.05.2018
# Last Modified Date: 14.05.2018
# Last Modified By: Khuong Nguyen <khuong@inspectorio.com>

import json
import os
import requests
import datetime
from urllib2 import Request, urlopen
from aws_requests_auth.aws_auth import AWSRequestsAuth
from elasticsearch import Elasticsearch, RequestsHttpConnection

es_host = os.getenv('ELASTICSEARCH_URL')
es_index = os.getenv('ELASTICSEARCH_INDEX')
access_key = os.getenv('AWS_ACCESS_KEY_ID')
secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
session_token = os.getenv('AWS_SESSION_TOKEN')
region = os.getenv('AWS_REGION')
hipchat_v2_token = os.getenv('HIPCHAT_V2_TOKEN')
hipchat_room_id = os.getenv('HIPCHAT_ROOMID')

def connectES(esEndPoint):
    print ('Connecting to the ES Endpoint {0}'.format(esEndPoint))
    try:
        auth = AWSRequestsAuth(aws_access_key=access_key,
                               aws_secret_access_key=secret_access_key,
                               aws_token=session_token,
                               aws_host=esEndPoint,
                               aws_region=region,
                               aws_service='es')

        # use the requests connection_class and pass in our custom auth class
        es_client = Elasticsearch(hosts=[{'host': esEndPoint, 'port': 443}],
                                   use_ssl=True,
                                   verify_certs=True,
                                   connection_class=RequestsHttpConnection,
                                   http_auth=auth)
        return es_client
    except Exception as E:
        print("Unable to connect to {0}".format(esEndPoint))
        print(E)
        exit(3)

   

def hipchat_notify(token, room, message, color='yellow', notify=False,
                   format='text', host='api.hipchat.com'):
    """Send notification to a HipChat room via API version 2
    Parameters
    ----------
    token : str
        HipChat API version 2 compatible token (room or user token)
    room: str
        Name or API ID of the room to notify
    message: str
        Message to send to room
    color: str, optional
        Background color for message, defaults to yellow
        Valid values: yellow, green, red, purple, gray, random
    notify: bool, optional
        Whether message should trigger a user notification, defaults to False
    format: str, optional
        Format of message, defaults to text
        Valid values: text, html
    host: str, optional
        Host to connect to, defaults to api.hipchat.com
    """
    if len(message) > 10000:
        raise ValueError('Message too long')
    if format not in ['text', 'html']:
        raise ValueError("Invalid message format '{0}'".format(format))
    if color not in ['yellow', 'green', 'red', 'purple', 'gray', 'random']:
        raise ValueError("Invalid color {0}".format(color))
    if not isinstance(notify, bool):
        raise TypeError("Notify must be boolean")

    url = "https://{0}/v2/room/{1}/notification".format(host, room)
    headers = {'Content-type': 'application/json'}
    headers['Authorization'] = "Bearer " + token
    payload = {
        'message': message,
        'notify': notify,
        'message_format': format,
        'color': color
    }
    r = requests.post(url, data=json.dumps(payload), headers=headers)
    r.raise_for_status()


def lambda_handler(event, context):

    date_prefix = datetime.datetime.today().strftime('-%Y-%m-%d')
    index_name = es_index + date_prefix    
    
    es_client = connectES(es_host)

    for record in event['Records']:
        sns = record['Sns']

        if sns.get('Subject') is not None:
            message = sns['Subject']
        else:
            message = sns['Message']

        #write to elastic search       
        es_client.index(index=index_name, doc_type='events',
                            body=message)
        print ('Suceeded to write into {0}'.format(es_host))
        #notify hipchat                            
        try:
            hipchat_notify(token=hipchat_v2_token, room=int(hipchat_room_id),message=message, notify=True,format='html')
        except Exception as e:
            msg = "[ERROR] HipChat notify failed: '{0}'".format(e)
            print(msg)
            return "Failed"
        
        return "Success"