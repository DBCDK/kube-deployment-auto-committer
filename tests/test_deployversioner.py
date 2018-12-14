#!/usr/bin/env python3

# Copyright Dansk Bibliotekscenter a/s. Licensed under GPLv3
# See license text in LICENSE.txt or at https://opensource.dbc.dk/licenses/gpl-3.0/

import io
import json
import os
import unittest
import unittest.mock
import pathlib
import sys

import yaml

import deployversioner.deployversioner

class VerionerTest(unittest.TestCase):
    def test_set_image_tag(self):
        configuration_path = os.path.join(get_tests_path(), "deployment.yml")
        result = deployversioner.deployversioner.set_image_tag(configuration_path, "new_image_tag")

        docs = [d for d in yaml.load_all(result)]
        self.assertEqual(docs, deployment_object)

    def test_parse_image(self):
        image = "docker-io.dbc.dk/author-name-suggester-service:master-9"
        imagename, image_tag = deployversioner.deployversioner.parse_image(image)
        self.assertEqual(imagename, "docker-io.dbc.dk/author-name-suggester-service")
        self.assertEqual(image_tag, "master-9")

    @unittest.mock.patch("urllib.request.urlopen")
    def test_commit_changes(self, request_urlopen):
        request_urlopen.return_value = io.BytesIO(json.dumps(
            {"file_path":"app/file.ext", "branch":"staging"}).encode("utf8"))
        response = deployversioner.deployversioner.commit_changes(
            "gitlab.url", "token", 103, "app/file.ext", "staging", "cont")
        self.assertEqual(json.loads(response),
            json.loads('{"file_path": "app/file.ext", "branch": "staging"}'))
        request = request_urlopen.call_args[0][0]
        self.assertEqual(request.method, "PUT")
        self.assertEqual(json.loads(request.data), {"branch": "staging",
            "content": "cont", "commit_message": "updating image tag in app/file.ext"})
        self.assertEqual(request.headers, {'Private-token': 'token',
            'Content-type': 'application/json'})

def get_tests_path():
    try:
        # get the parent directory of the directory this file is in
        p = pathlib.PurePath(sys.modules[__name__].__file__)
        return str(p.parents[0])
    except IndexError:
        return "tests"

deployment_object = [
    {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "author-name-suggester"
        },
        "spec": {
            "selector": {
                "matchLabels": {
                    "app": "author-name-suggester"
                }
            },
            "template": {
                "metadata": {
                    "labels": {
                        "app": "author-name-suggester",
                        "network-ports": "standard-ports"
                    }
                },
                "spec": {
                    "containers": [
                        {
                            "image": "docker-io.dbc.dk/author-name-suggester-service:new_image_tag",
                            "livenessProbe": {
                                "httpGet": {
                                    "path": "/api/status",
                                    "port": 80
                                },
                                "initialDelaySeconds": 180,
                                "periodSeconds": 3
                            },
                            "name": "author-name-suggester",
                            "ports": [
                                {
                                    "containerPort": 80,
                                    "protocol": "TCP"
                                }
                            ]
                        }
                    ]
                }
            }
        }
    },
    {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "labels": {
                "app": "author-name-suggester"
            },
            "name": "author-name-suggester"
        },
        "spec": {
            "ports": [
                {
                    "port": 80,
                    "protocol": "TCP"
                }
            ],
            "selector": {
                "app": "author-name-suggester"
            },
            "type": "ClusterIP"
        }
    },
    {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": "ner-egress"
        },
        "spec": {
            "egress": [
                {
                    "ports": [
                        {
                            "port": 8585,
                            "protocol": "TCP"
                        }
                    ]
                }
            ],
            "podSelector": {
                "matchLabels": {
                    "app": "author-name-suggester"
                }
            },
            "policyTypes": [
                "Egress"
            ]
        }
    }
]
