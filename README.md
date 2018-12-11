# cluster-location admission webhook

Pods need to be labelled with cluster location to support Istio cluster-local services

For all Pod objects it should add the label `k8s.osp.tech/global-cluster-location: <location>`

The location could be taken from a `global-environment` ConfigMap or set statically.

This should exclude Pods labelled with `k8s.osp.tech/no-cluster-location` to help with bootstrap issues

## configuration

Name | description | default
 --- | --- | ---
CERT_PATH | can be set to the path of a tls certificate | /certs/tls.crt
CLUSTER_LOCATION | should be set to the physical location of the cluster | UNKNOWN
KEY_PATH | can be set to the path of a tls key | /certs/tls.key
LOG_LEVEL | can be set to a valid log level eg: `DEBUG` | INFO

## test

see the patch with:
```
$ pip install -r requirements.txt
$ python3 ./hook.py &
$ curl -XPOST -d @contrib/request.txt localhost:8080/mutate -H 'Content-Type: application/json' -s | jq '.response.patch' -r | base64 -d | jq '.'
```

Copyright © 2018 Ocado
