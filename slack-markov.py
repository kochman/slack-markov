import json
import os
import sys

import flask
import markovify
import redis
import requests

try:
    SLACK_TOKEN = os.environ['SLACK_TOKEN']
except KeyError:
    print('SLACK_TOKEN must be defined.')
    sys.exit(1)

app = flask.Flask(__name__)

def redis_get(url, params={}):
    h = url + '|' + str(params)

    r = redis.StrictRedis(host='redis', port=6379, db=0)
    res = r.get(h)
    if res is None:
        j = requests.get(url, params).text
        r.set(h, j, ex=86400)
        res = j
    return json.loads(res)


def filter_messages(messages, user):
    res = []
    for message in messages:
        if message['type'] == 'message' and 'subtype' not in message and message['user'] == user:
            res.append(message['text'])
    return res


def get_user_id(username):
    users = redis_get('https://slack.com/api/users.list', params={'token': SLACK_TOKEN})['members']
    for user in users:
        if user['name'] == username:
            return user['id']


def generate_sentence(username):
    channels = redis_get('https://slack.com/api/channels.list', params={'token': SLACK_TOKEN})['channels']
    user_messages = []

    for channel in channels:
        messages = redis_get('https://slack.com/api/channels.history', params={'token': SLACK_TOKEN,
                                                                                  'channel': channel['id'],
                                                                                  'count': 1000})['messages']

        user_messages.extend(filter_messages(messages, get_user_id(username)))

    user_messages_model = markovify.NewlineText('\n'.join(user_messages))

    sentence = None
    count = 0
    while sentence is None or sentence[0] == '@':
        sentence = user_messages_model.make_sentence()
        count += 1
        if count > 100:
            return 'ERROR'
    return sentence


@app.route('/', methods=['POST'])
def return_sentence():
    username = flask.request.form['text']

    resp = {
        "response_type": "in_channel",
        "text": username + ' says:',
        "attachments": [
            {
                "text": generate_sentence(username)
            }
        ]
    }

    return flask.jsonify(resp)


if __name__ == '__main__':
    app.run('0.0.0.0', port=8080)
