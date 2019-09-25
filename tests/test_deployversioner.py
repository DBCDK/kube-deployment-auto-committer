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
    @unittest.mock.patch("urllib.request.urlopen")
    def test_set_image_tag(self, mock_urlopen):
        configuration_path = os.path.join(get_tests_path(), "deployment.yml")
        with open(configuration_path) as fp:
            mock_urlopen.return_value = io.BytesIO(fp.read().encode("utf8"))
            gitlab_request = deployversioner.deployversioner.GitlabRequest(
                "gitlab.url", "token", 103, "staging")
            result = deployversioner.deployversioner.set_image_tag(
                gitlab_request, "filename", "new_image_tag")
            docs = [d for d in yaml.load_all(result)]
            self.assertEqual(docs, deployment_object)

    @unittest.mock.patch("urllib.request.urlopen")
    def test_that_set_image_tag_sets_all_tags_in_a_yaml_doc(self, mock_urlopen):
        configuration_path = os.path.join(get_tests_path(), "deployment2.yml")
        with open(configuration_path) as fp:
            mock_urlopen.return_value = io.BytesIO(fp.read().encode("utf8"))
            gitlab_request = deployversioner.deployversioner.GitlabRequest(
                "gitlab.url", "token", 103, "staging")
            result = deployversioner.deployversioner.set_image_tag(
                gitlab_request, "filename", "TAG-1")
            self.assertEqual(result.count("TAG-1"), 4)

    @unittest.mock.patch("urllib.request.urlopen")
    def test_set_image_tag_identical_new_tag(self, mock_urlopen):
        configuration_path = os.path.join(get_tests_path(), "deployment.yml")
        with open(configuration_path) as fp:
            mock_urlopen.return_value = io.BytesIO(fp.read().encode("utf8"))
            gitlab_request = deployversioner.deployversioner.GitlabRequest(
                "gitlab.url", "token", 103, "staging")
            with self.assertRaises(deployversioner.deployversioner
                    .VersionUnchangedException):
                deployversioner.deployversioner.set_image_tag(
                    gitlab_request, "filename", "master-9")

    def test_parse_image(self):
        image = "docker-io.dbc.dk/author-name-suggester-service:master-9"
        imagename, image_tag = deployversioner.deployversioner.parse_image(image)
        self.assertEqual(imagename, "docker-io.dbc.dk/author-name-suggester-service")
        self.assertEqual(image_tag, "master-9")

    @unittest.mock.patch("urllib.request.urlopen")
    def test_commit_changes(self, request_urlopen):
        request_urlopen.return_value = io.BytesIO(json.dumps(
            {"file_path":"app/file.ext", "branch":"staging"}).encode("utf8"))
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        response = deployversioner.deployversioner.commit_changes(
            gitlab_request, "app/file.ext", "cont")
        self.assertEqual(json.loads(response),
            json.loads('{"file_path": "app/file.ext", "branch": "staging"}'))
        request = request_urlopen.call_args[0][0]
        self.assertEqual(request.method, "PUT")
        self.assertEqual(json.loads(request.data), {"branch": "staging",
            "content": "cont", "commit_message": "updating image tag in app/file.ext"})
        self.assertEqual(request.headers, {'Private-token': 'token',
            'Content-type': 'application/json'})

    @unittest.mock.patch("urllib.request.urlopen")
    def test_get_file_contents(self, mock_urlopen):
        mock_urlopen.return_value = io.BytesIO("file contents".encode("utf8"))
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        response = deployversioner.deployversioner.get_file_contents(
            gitlab_request, "filename")
        self.assertEqual(response, "file contents")
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.full_url,
            "https://gitlab.url/api/v4/projects/103/repository/files/"
            "filename/raw?ref=staging")
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.headers, {"Private-token": "token"})

    @unittest.mock.patch("urllib.request.urlopen")
    def test_get_project_number(self, mock_urlopen):
        mock_urlopen.return_value = io.BytesIO("file contents".encode("utf8"))
        configuration_path = os.path.join(get_tests_path(), "git_project.json")
        with open(configuration_path) as fp:
            mock_urlopen.return_value = io.BytesIO(fp.read().encode("utf8"))
            print (mock_urlopen.return_value)
            self.assertEqual( 143,
                              deployversioner.deployversioner
                              .get_project_number( 'https://gitlab.dbc.dk/api/v4/projects',
                                                  'metascrum/rrflow-deploy',
                                                  'token') )


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
