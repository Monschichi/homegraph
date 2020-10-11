#!/usr/bin/env python3

from flask import (
    Flask,
    jsonify,
    request,
)

from hmip import HmIP

app = Flask(__name__)
homematic_ip: HmIP


@app.route('/fetch', methods=['GET'])
def fetch():
    homematic_ip.fetch_metrics()
    return ''


@app.route('/', methods=['GET'])
def index():
    return ''


@app.route('/search', methods=['POST'])
def search():
    app.logger.debug(request.headers, request.get_json())
    metrics = homematic_ip.get_metric_names()
    return jsonify(list(metrics))


@app.route('/query', methods=['POST'])
def query():
    req = request.get_json()
    app.logger.debug(req)
    return jsonify(homematic_ip.get_metrics(start=req['range']['from'], end=req['range']['to'], resolution=req['interval'],
                                            metrics=list(t['target'] for t in req['targets'])))


@app.route('/annotations')
def annotations():
    pass


@app.before_first_request
def startup():
    global homematic_ip
    homematic_ip = HmIP()


if __name__ == '__main__':
    app.run()
