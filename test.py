try:
    import unittest2 as unittest
except ImportError:
    import unittest
try:
    from io import BytesIO as IO
except ImportError:
    from StringIO import StringIO as IO
import base64
import json
import jsonpatch
from hook import Webhook  # My BaseHTTPRequestHandler child


class TestableHandler(Webhook):
    def setup(self):
        super().setup()
        self.wfile = IO()

    def finish(self):
        # Do not close self.wfile, so we can read its value
        self.wfile.flush()
        self.final_value = self.wfile.getvalue()
        super().finish()

    def date_time_string(self, timestamp=None):
        """ Mocked date time string """
        return 'DATETIME'

    def version_string(self):
        """ mock the server id """
        return 'BaseHTTP/x.x Python/x.x.x'


class MockSocket(object):
    def getsockname(self):
        return ('sockname',)


class MockGETRequest(object):
    _sock = MockSocket()

    def __init__(self, path):
        self._path = path

    def makefile(self, *args, **kwargs):
        return IO(b"GET %s HTTP/1.0" % self._path)


class MockPUTRequest(object):
    _sock = MockSocket()

    def __init__(self, path, data):
        self._path = path
        self._data = data

    def makefile(self, *args, **kwargs):
        return IO(b"PUT %s HTTP/1.0\nContent-Length: %d\n\n%s" % (self._path, len(self._data), self._data))


class HTTPRequestHandlerTestCase(unittest.TestCase):
    maxDiff = None

    def _test(self, request):
        handler = TestableHandler(request, (0, 0), None)
        return handler.final_value

    def test_get(self):
        self.assertIn(
            b'HTTP/1.0 200 OK',
            self._test(MockGETRequest(b'/'))
        )

    def test_get_metrics(self):
        self.assertIn(
            b'python_info',
            self._test(MockGETRequest(b'/metrics'))
        )

    def test_good_put(self):
        req = open("contrib/request.txt", "rb")
        self.assertIn(
            b'"uid": "64bcda5e-f304-11e8-8699-fa163e69c69a"',
            self._test(MockPUTRequest(b'/mutate', req.read()))
        )
        req.close()

    def _apply_patch(self, req, resp):
        resp_patch = base64.b64decode(json.loads(resp[resp.find(b'{'):])['response']['patch'])
        req_object = json.loads(req)['request']['object']
        object = jsonpatch.apply_patch(req_object, resp_patch)
        self.assertEqual(object['metadata']['labels']['k8s.osp.tech/global-cluster-location'], 'UNKNOWN')
        return object

    def test_good_put_patch(self):
        req = open("contrib/request.txt", "rb").read()
        resp = self._test(MockPUTRequest(b'/mutate', req))
        object = self._apply_patch(req, resp)
        self.assertEqual(object['metadata']['labels']['app'], 'scheduler-healthcheck-test-pod')

    def test_good_put_patch_no_labels(self):
        req = open("contrib/request.txt", "rb").read()
        req_object = json.loads(req)
        del req_object['request']['object']['metadata']['labels']
        req = json.dumps(req_object).encode('utf-8')
        resp = self._test(MockPUTRequest(b'/mutate', req))
        self._apply_patch(req, resp)


    def test_bad_put(self):
        self.assertIn(
            b'400 Not an AdmissionReview',
            self._test(MockPUTRequest(b'/mutate', b'{"foo": "bar"}'))
        )


def main():
    unittest.main()


if __name__ == "__main__":
    main()
