#!/usr/bin/env python
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from prometheus_client import Counter, Histogram, generate_latest
import base64
import json
import logging
import os
import os.path
import ssl

CLUSTER_LOCATION_LABEL = "k8s.osp.tech/global-cluster-location"
IGNORE_WITH_LABEL = "k8s.osp.tech/no-cluster-location"
CERT_PATH = os.getenv("CERT_PATH", "/certs/tls.crt")
KEY_PATH = os.getenv("KEY_PATH", "/certs/tls.key")
CLUSTER_LOCATION = os.getenv("CLUSTER_LOCATION", "UNKNOWN")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

numeric_level = getattr(logging, LOG_LEVEL.upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError('Invalid LOG_LEVEL: %s' % LOG_LEVEL)
logging.basicConfig(level=numeric_level)

REQUESTS = Counter('webhook_request_total',
                   'webhooks requests.', ['path', 'method'])
LATENCY = Histogram('webhook_request_latency_seconds',
                    'Time for a request webhook.', ['path', 'method'])


def request_metrics(func):
    def wrapper(self):
        with LATENCY.labels(self.path, self.command).time():
            REQUESTS.labels(self.path, self.command).inc()
            return func(self)
    return wrapper


def safe_json_patch_key(key):
    ''' see https://tools.ietf.org/html/rfc6901#section-3 '''
    return key.replace('/', '~1')


class Webhook(BaseHTTPRequestHandler):
    # build the JSONPatch once rather than every request as it won't change
    patch_content = [{'op': 'add',
                      'path': '/metadata/labels',
                      'value': {safe_json_patch_key(CLUSTER_LOCATION_LABEL): CLUSTER_LOCATION}}]
    patch = base64.b64encode(json.dumps(
        patch_content).encode('utf-8')).decode()

    def _build_response(self, uid, labels):
        response = {
            "response": {
                "uid": uid,
                "allowed": True,
                "patch": "",
                "patchType": "JSONPatch",
            }
        }
        if IGNORE_WITH_LABEL not in labels:
            response['response']['patch'] = self.patch
        return response

    def _send_json(self, data):
        body = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        logging.info(str(body))
        self.wfile.write(body)

    def _hook(self):
        try:
            raw = self.rfile.read(int(self.headers.get('content-length')))
            logging.debug(str(raw))
            recieved = json.loads(raw)
        except json.decoder.JSONDecodeError as j:
            error_debug = "JSONDecodeError: {0}".format(j.msg)
            self.send_error(HTTPStatus.BAD_REQUEST, error_debug)
            return
        except Exception as e:
            error_debug = "Error: {0}".format(e)
            self.send_error(HTTPStatus.BAD_REQUEST, error_debug)
            return

        if recieved.get('kind') != "AdmissionReview":
            self.send_error(HTTPStatus.BAD_REQUEST, "Not an AdmissionReview")
            return
        uid = recieved.get('request')['uid']
        labels = recieved.get('request', {}).get(
            'object', {}).get('metadata', {}).get('labels', {})
        self._send_json(self._build_response(uid, labels))

    @request_metrics
    def do_POST(self):
        self._hook()

    @request_metrics
    def do_PUT(self):
        self._hook()

    @request_metrics
    def do_GET(self):
        """ use for healthz check """
        self.send_response(200)
        self.end_headers()
        if self.path == '/metrics':
            self.wfile.write(generate_latest())
            return
        self.wfile.write(b'OK')


def run():
    logging.info('CLUSTER_LOCATION set to '+CLUSTER_LOCATION)
    httpd = ThreadingHTTPServer(('', 8080), Webhook)
    if os.path.isfile(CERT_PATH) and os.path.isfile(KEY_PATH):
        logging.info('using tls cert at '+CERT_PATH)
        logging.info('using tls key at '+KEY_PATH)
        httpd.socket = ssl.wrap_socket(
            httpd.socket, certfile=CERT_PATH, keyfile=KEY_PATH, server_side=True)
    logging.info('starting on 8080...')
    httpd.serve_forever()


if __name__ == '__main__':
    run()
