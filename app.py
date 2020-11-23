#!/usr/bin/env python3

from flask import (
    Flask,
    jsonify,
    request,
)

from hmip import HmIP

application = Flask(__name__)
homematic_ip: HmIP


@application.route('/fetch', methods=['GET'])
def fetch():
    homematic_ip.fetch_metrics()
    return ''


@application.route('/', methods=['GET'])
def index():
    return ''


@application.route('/search', methods=['POST'])
def search():
    application.logger.debug(request.headers, request.get_json())
    metrics = homematic_ip.get_metric_names()
    return jsonify(list(metrics))


@application.route('/query', methods=['POST'])
def query():
    req = request.get_json()
    application.logger.debug(req)
    return jsonify(homematic_ip.get_metrics(start=req['range']['from'], end=req['range']['to'], resolution=req['interval'],
                                            metrics=list(t['target'] for t in req['targets'])))


@application.route('/annotations')
def annotations():
    pass


@application.before_first_request
def startup():
    global homematic_ip
    homematic_ip = HmIP()


if __name__ == '__main__':
    application.run()
