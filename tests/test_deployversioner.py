#!/usr/bin/env python3

# Copyright Dansk Bibliotekscenter a/s. Licensed under GPLv3
# See license text in LICENSE.txt or at https://opensource.dbc.dk/licenses/gpl-3.0/
import typing

import io
import json
import os
import unittest.mock
import pathlib
import sys

import yaml

import deployversioner.deployversioner

@unittest.mock.patch("urllib.request.urlopen")
class VerionerTests(unittest.TestCase):

    def test_set_image_tag(self, mock_urlopen):
        mock_urlopen.side_effect=get_url_open_response_return_value
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        result, _ = deployversioner.deployversioner.set_image_tag(
            gitlab_request, "gui.yaml", "new_image_tag")
        docs = [d for d in yaml.safe_load_all(result)]
        configuration_path = os.path.join(get_tests_path(), "gui.yaml")
        with open(configuration_path) as fp:
            depl_docs = [d for d in yaml.safe_load_all(io.BytesIO(fp.read().encode("utf8")))]
            self.assertEqual(docs, depl_docs)

    def test_that_set_image_tag_sets_all_tags_in_a_yaml_doc(self, mock_urlopen):
        mock_urlopen.side_effect = get_url_open_response_return_value
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        result,_ = deployversioner.deployversioner.set_image_tag(
            gitlab_request, "services/batch-exchange-sink.yml", "TAG-2")
        self.assertEqual(result.count("TAG-2"), 2)

    def test_that_change_image_tag_makes_a_commit_message_covering_all_bumped_tags(self, mock_urlopen):
        repo_tree_response = json.dumps([
            {
                "id": "5ab350dcf92bf662b2b309b4db83415afc2d6baa",
                "name": "files",
                "type": "tree",
                "path": "files",
                "mode": "040000"
            },
            {
                "id": "a240c0e70890a799d51a8aee556808d98e689a36",
                "name": "file1.yml",
                "type": "blob",
                "path": "files/file1.yml",
                "mode": "100644"
            },
            {
                "id": "589ed823e9a84c56feb95ac58e7cf384626b9cbf4",
                "name": "file2.yml",
                "type": "blob",
                "path": "files/file2.yml",
                "mode": "100644"
            }]
        )
        file_content_responses = ["""apiVersion: apps/v1
kind: Deployment
metadata:
  name: service1
spec:
  template:
    spec:
      containers:
      - image: docker-image:master-01
""", """apiVersion: apps/v1
kind: Deployment
metadata:
  name: service2
spec:
  template:
    spec:
      containers:
      - image: docker-image:master-02
        """]
        commit_response = json.dumps({
            "title": "Bump docker tag from master-01 to TAG-2",
            "message": "Bump docker tag from master-01 to TAG-2\nBump docker tag from master-02 to TAG-2",
            "status": None,
            "project_id": 103
        })
        mock_urlopen.side_effect = [
            io.BytesIO(repo_tree_response.encode("utf8")),
            io.BytesIO(file_content_responses[0].encode("utf8")),
            io.BytesIO(file_content_responses[1].encode("utf8")),
            io.BytesIO(commit_response.encode("utf8"))
        ]
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        proposed_commits, changed_image_tags = deployversioner.deployversioner.change_image_tag(
            gitlab_request, "files", "TAG-2")
        deployversioner.deployversioner.commit_changes(
            gitlab_request, proposed_commits, "TAG-2", changed_image_tags)
        request = mock_urlopen.call_args[0][0]
        commit_message=json.loads(request.data)["commit_message"]
        self.assertIn('Bump docker tag from master-01 to TAG-2', commit_message)
        self.assertIn('Bump docker tag from master-02 to TAG-2', commit_message)

    def test_multiple_yaml_files(self, mock_urlopen):
        repo_tree_response = json.dumps([
            {
                "id": "5ab350dcf92bf662b2b309b4db83415afc2d6baa",
                "name": "files",
                "type": "tree",
                "path": "files",
            },
            {
                "id": "a240c0e70890a799d51a8aee556808d98e689a36",
                "name": "file1.yml",
                "type": "blob",
                "path": "files/file1.yml",
            },
            {
                "id": "589ed823e9a84c56feb95ac58e7cf384626b9cbf4",
                "name": "file2.yml",
                "type": "blob",
                "path": "files/file2.yml",
            }]
        )
        file_content_responses = ["""apiVersion: apps/v1
kind: Deployment
metadata:
  name: service1
spec:
  template:
    spec:
      containers:
      - image: docker-image:master-01
""", """apiVersion: apps/v1
kind: Deployment
metadata:
  name: service2
spec:
  template:
    spec:
      containers:
      - image: docker-image:master-01
"""]
        mock_urlopen.side_effect = [
            io.BytesIO(repo_tree_response.encode("utf8")),
            io.BytesIO(file_content_responses[0].encode("utf8")),
            io.BytesIO(file_content_responses[1].encode("utf8"))
        ]
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        result = deployversioner.deployversioner.change_image_tag(
            gitlab_request, "files", "master-02")
        self.assertEqual(len(result), 2)
        self.assertEqual(mock_urlopen.call_count, 3)

    def test_set_image_tag_identical_new_tag(self, mock_urlopen):
        mock_urlopen.side_effect = get_url_open_response_return_value
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        with self.assertRaises(deployversioner.deployversioner
                .VersionUnchangedException):
            deployversioner.deployversioner.set_image_tag(
                gitlab_request, "services/dummy-sink.yml", "master-27")

    def test_parse_image(self, mock_urlopen):
        image = "docker-io.dbc.dk/author-name-suggester-service:master-9"
        imagename, image_tag = deployversioner.deployversioner.parse_image(image)
        self.assertEqual(imagename, "docker-io.dbc.dk/author-name-suggester-service")
        self.assertEqual(image_tag, "master-9")

    def test_commit_changes(self, mock_urlopen):
        repo_tree_response = json.dumps([
            {
                "id": "5ab350dcf92bf662b2b309b4db83415afc2d6baa",
                "name": "files",
                "type": "tree",
                "path": "files",
            },
            {
                "id": "a240c0e70890a799d51a8aee556808d98e689a36",
                "name": "file1.yml",
                "type": "blob",
                "path": "files/file1.yml",
            }]
        )
        file_content_response = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: service
spec:
  template:
    spec:
      containers:
      - image: docker-image:master-01
"""
        commit_response = json.dumps({
            "id": "82b15418fdd0048a8aba1d61e7f5d81db312bdda",
            "title": "Bump docker tag to TAG-2",
            "message": "Bump docker tag to TAG-2",
            "status": None,
            "project_id": 103
        })
        mock_urlopen.side_effect = [
            io.BytesIO(repo_tree_response.encode("utf8")),
            io.BytesIO(file_content_response.encode("utf8")),
            io.BytesIO(commit_response.encode("utf8"))]
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        proposed_commits, changed_tags = deployversioner.deployversioner.change_image_tag(
            gitlab_request, "files", "TAG-2")
        deployversioner.deployversioner.commit_changes(
            gitlab_request, proposed_commits, "TAG-2", changed_tags)
        request = mock_urlopen.call_args[0][0]
        data=json.loads(request.data)

        self.assertEqual(request.method, "POST")
        self.assertEqual([d["file_path"] for d in data["actions"]].sort(),
                         ["services/dummy-sink.yml", "services/batch-exchange-sink.yml", "services/diff-sink.yml"].sort())
        self.assertEqual(set([d['action'] for d in data["actions"]]), {"update"})
        self.assertEqual(data["branch"], "staging")
        self.assertEqual(data["commit_message"], "Bump docker tag from master-01 to TAG-2")
        self.assertEqual(request.headers, {'Private-token': 'token',
            'Content-type': 'application/json'})

    def test_get_file_contents(self, mock_urlopen):
        mock_urlopen.side_effect = get_url_open_response_return_value
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        deployversioner.deployversioner.get_file_contents(
            gitlab_request, "gui.yaml")
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.full_url,
            "https://gitlab.url/api/v4/projects/103/repository/files/gui.yaml/raw?ref=staging")
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.headers, {"Private-token": "token"})

    def test_file_does_not_exist(self, mock_urlopen):
        repo_tree_response = json.dumps([
            {
                "id": "5ab350dcf92bf662b2b309b4db83415afc2d6baa",
                "name": "files",
                "type": "tree",
                "path": "files",
                "mode": "040000"
            },
            {
                "id": "a240c0e70890a799d51a8aee556808d98e689a36",
                "name": "file1.yml",
                "type": "blob",
                "path": "files/file1.yml",
                "mode": "100644"
            }]
        )
        mock_urlopen.return_value = io.BytesIO(repo_tree_response.encode("utf8"))
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        with self.assertRaises(deployversioner.deployversioner
                                       .VersionerFileNotFound):
            deployversioner.deployversioner.change_image_tag(
                gitlab_request, "services/no_exist.yaml", "TAG-2")

    def test_get_project_number(self, mock_urlopen):
        mock_urlopen.side_effect = get_url_open_response_return_value
        self.assertEqual( 103, deployversioner.deployversioner
            .get_project_number( 'https://gitlab.url/api/v4/projects',
            'test_namespace/test_project', 'token') )


def get_tests_path():
    try:
        # get the parent directory of the directory this file is in
        p = pathlib.PurePath(sys.modules[__name__].__file__)
        return str(p.parents[0])
    except IndexError:
        return "tests"


def get_url_open_response_return_value(request):
    return io.BytesIO(url_open_response_return_values[request.full_url].encode('utf-8'))



########################################################
# Data here as url-request=>response key/value pairs   #
########################################################

url_open_response_return_values = {
    "https://gitlab.url/api/v4/projects/103/repository/tree/?ref=staging&recursive=True&per_page=5000": """[
          {
            "id": "5ab350dcf92bf662b2b309b4db83415afc2d6baa",
            "name": "services",
            "type": "tree",
            "path": "services",
            "mode": "040000"
          },
          {
            "id": "bcd9a9d1d8364a323486c8388cd59287b5cd8ef4",
            "name": "gui.yaml",
            "type": "blob",
            "path": "gui.yaml",
            "mode": "100644"
          },
          {
            "id": "3c8c72f32e71b0f63103adfae6519a38bcb518ec",
            "name": "batch-exchange-sink.yml",
            "type": "blob",
            "path": "services/batch-exchange-sink.yml",
            "mode": "100644"
          },
          {
            "id": "8debbafc24584d1da20010c1667bf20568f3add1",
            "name": "diff-sink.yml",
            "type": "blob",
            "path": "services/diff-sink.yml",
            "mode": "100644"
          },
          {
            "id": "a240c0e70890a799d51a8aee556808d98e689a36",
            "name": "dummy-sink.yml",
            "type": "blob",
            "path": "services/dummy-sink.yml",
            "mode": "100644"
          }
        ]""",


        "https://gitlab.url/api/v4/projects/103/repository/files/gui.yaml/raw?ref=staging": """apiVersion: apps/v1
kind: Deployment
metadata:
  labels: {app: dataio-gui-service, app.dbc.dk/team: metascrum, app.kubernetes.io/component: service,
    app.kubernetes.io/name: gui, app.kubernetes.io/part-of: dataio}
  name: dataio-gui-service
spec:
  progressDeadlineSeconds: 180
  replicas: 1
  selector:
    matchLabels: {app: gui-service}
  strategy:
    rollingUpdate: {maxSurge: 1, maxUnavailable: 0}
    type: RollingUpdate
  template:
    metadata:
      labels: {app: gui-service, app.dbc.dk/team: metascrum, app.kubernetes.io/component: service,
        app.kubernetes.io/name: gui, app.kubernetes.io/part-of: dataio, network-policy-ftp-outgoing: 'yes',
        network-policy-http-incoming: 'yes', network-policy-http-outgoing: 'yes',
        network-policy-svn-outgoing: 'yes'}
    spec:
      containers:
      - env:
        - {name: JAVA_MAX_HEAP_SIZE, value: 8G}
        - {name: TZ, value: "Europe/Copenhagen"}
        image: docker-io.dbc.dk/dbc-payara-gui:master-28
        livenessProbe:
          failureThreshold: 3
          httpGet: {path: /status, port: 8080}
          initialDelaySeconds: 45
          periodSeconds: 5
        name: gui-service
        ports:
        - {containerPort: 8080, protocol: TCP}
        readinessProbe:
          failureThreshold: 9
          httpGet: {path: /status, port: 8080}
          initialDelaySeconds: 15
          periodSeconds: 5
      dnsConfig:
        searches: [dbc.dk]
---
apiVersion: v1
kind: Service
metadata:
  labels: {app: gui-service, app.dbc.dk/team: metascrum, app.kubernetes.io/component: service,
    app.kubernetes.io/name: gui, app.kubernetes.io/part-of: dataio}
  name: dataio-gui-service
spec:
  ports:
  - {name: http, port: 80, protocol: TCP, targetPort: 8080}
  selector: {app: gui-service}
  type: ClusterIP""",


    "https://gitlab.url/api/v4/projects/103/repository/files/services%2Fbatch-exchange-sink.yml/raw?ref=staging": """apiVersion: apps/v1
kind: Deployment
spec:
    template:
        spec:
          containers:
          - image: docker-io.dbc.dk/dbc-payara-batch-exchange-sink:TAG-2
          
---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - image: docker-io.dbc.dk/dbc-payara-batch-exchange-sink:master-28
""",


    "https://gitlab.url/api/v4/projects/103/repository/files/services%2Fdiff-sink.yml/raw?ref=staging": """apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - image: docker-io.dbc.dk/dbc-payara-diff-sink:master-28
""",



    "https://gitlab.url/api/v4/projects/103/repository/files/services%2Fdummy-sink.yml/raw?ref=staging":"""apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - image: docker-io.dbc.dk/dbc-payara-dummy-sink:master-27
""",


    "https://gitlab.url/api/v4/projects/103/repository/commits?ref=staging": """{
  "id": "82b15418fdd0048a8aba1d61e7f5d81db312bdda",   
  "title": "Bump docker tag to TAG-2",
  "message": "Bump docker tag to TAG-2",
  "status": null,
  "project_id": 103
}""",

    "https://gitlab.url/api/v4/projects/test_namespace%2Ftest_project": """{"id": 103,
  "name_with_namespace": "test_namespace / test_poject",
  "approvals_before_merge": 0,
  "mirror": false
}"""
}
