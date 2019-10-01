#!/usr/bin/env python3

# Copyright Dansk Bibliotekscenter a/s. Licensed under GPLv3
# See license text in LICENSE.txt or at https://opensource.dbc.dk/licenses/gpl-3.0/

import io
import json
import os
import unittest.mock
import pathlib
import sys

import yaml

import deployversioner.deployversioner

@unittest.mock.patch("urllib.request.urlopen")
class VerionerTest(unittest.TestCase):

    def test_set_image_tag(self, mock_urlopen):
        mock_urlopen.side_effect=get_url_open_response_return_value
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        result = deployversioner.deployversioner.set_image_tag(
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
        result = deployversioner.deployversioner.set_image_tag(
            gitlab_request, "services/batch-exchange-sink.yml", "TAG-2")
        self.assertEqual(result.count("TAG-2"), 2)

    def test_multiple_yaml_files(self, mock_urlopen):
        mock_urlopen.side_effect=get_url_open_response_return_value
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        result = deployversioner.deployversioner.change_image_tag(
            gitlab_request, "services", "TAG-2")
        tag_occurences=0
        for content in result:
            docs = [d for d in yaml.safe_load_all(content['content'])]
            for doc in docs:
                if doc['kind']=="Deployment":
                    self.assertTrue(doc['spec']['template']['spec']['containers'][0]['image'].endswith(":TAG-2"), msg="Found TAG-2 tag")
                    tag_occurences=+1
        self.assertTrue(tag_occurences, 4)

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
        mock_urlopen.side_effect = get_url_open_response_return_value
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        proposed_commits = deployversioner.deployversioner.change_image_tag(
            gitlab_request, "services", "TAG-2")
        deployversioner.deployversioner.commit_changes(
            gitlab_request, proposed_commits, "TAG-2")
        request = mock_urlopen.call_args[0][0]
        data=json.loads(request.data)

        self.assertEqual(request.method, "POST")
        self.assertEqual([d["file_path"] for d in data["actions"]].sort(),
                         ["services/dummy-sink.yml", "services/batch-exchange-sink.yml", "services/diff-sink.yml"].sort())
        self.assertEqual(set([d['action'] for d in data["actions"]]), {"update"})
        self.assertEqual(data["branch"], "staging")
        self.assertEqual(data["commit_message"], "Bump docker tag to TAG-2")
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
        mock_urlopen.side_effect = get_url_open_response_return_value
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
    "https://gitlab.url/api/v4/projects/103/repository/tree/?ref=staging&recursive=True": """[
          {
            "id": "5ab350dcf92bf662b2b309b4db83415afc2d6baa",
            "name": "services",
            "type": "tree",
            "path": "services",
            "mode": "040000"
          },
          {
            "id": "5cc225ac3057da5c4b958e600b9a60a754c8e9da",
            "name": "README.md",
            "type": "blob",
            "path": "README.md",
            "mode": "100644"
          },
          {
            "id": "bcd9a9d1d8364a323486c8388cd59287b5cd8ef4",
            "name": "gui.yaml",
            "type": "blob",
            "path": "gui.yaml",
            "mode": "100644"
          },
          {
            "id": "7ed8ec6c836f68434570302bbd92bfa7b71faf46",
            "name": "p.valid",
            "type": "blob",
            "path": "p.valid",
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
metadata:
  labels: {app: dataio-batch-exchange-sink-loadtest-service, app.dbc.dk/team: metascrum,
    app.kubernetes.io/component: service, app.kubernetes.io/instance: loadtest, app.kubernetes.io/name: batch-exchange-sink,
    app.kubernetes.io/part-of: dataio}
  name: dataio-batch-exchange-sink-loadtest-service
spec:
  progressDeadlineSeconds: 180
  replicas: 1
  selector:
    matchLabels: {app: dataio-batch-exchange-sink-loadtest-service}
  strategy:
    rollingUpdate: {maxSurge: 1, maxUnavailable: 0}
    type: RollingUpdate
  template:
    metadata:
      labels: {app: dataio-batch-exchange-sink-loadtest-service, app.dbc.dk/team: metascrum,
        app.kubernetes.io/component: service, app.kubernetes.io/instance: loadtest,
        app.kubernetes.io/name: batch-exchange-sink, app.kubernetes.io/part-of: dataio,
        network-policy-http-incoming: 'yes', network-policy-http-outgoing: 'yes',
        network-policy-mq-outgoing: 'yes', network-policy-payara-incoming: 'yes',
        network-policy-postgres-outgoing: 'yes'}
    spec:
      containers:
      - env:
        - {name: JAVA_MAX_HEAP_SIZE, value: 2G}
        image: docker-io.dbc.dk/dbc-payara-batch-exchange-sink:TAG-2
        livenessProbe:
          failureThreshold: 3
          httpGet: {path: /dataio/sink/batch-exchange/status, port: 8080}
          initialDelaySeconds: 45
          periodSeconds: 5
        name: dataio-batch-exchange-sink-loadtest-service
        ports:
        - {containerPort: 4848, protocol: TCP}
        - {containerPort: 8080, protocol: TCP}
        readinessProbe:
          failureThreshold: 9
          httpGet: {path: /dataio/sink/batch-exchange/status, port: 8080}
          initialDelaySeconds: 15
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  labels: {app: dataio-batch-exchange-sink-loadtest-service, app.dbc.dk/team: metascrum,
    app.kubernetes.io/component: service, app.kubernetes.io/instance: loadtest, app.kubernetes.io/name: batch-exchange-sink,
    app.kubernetes.io/part-of: dataio}
  name: dataio-batch-exchange-sink-loadtest-service
spec:
  ports:
  - {name: http, port: 80, protocol: TCP, targetPort: 8080}
  - {name: admin, port: 4848, protocol: TCP, targetPort: 4848}
  selector: {app: dataio-batch-exchange-sink-loadtest-service}
  type: ClusterIP
---
apiVersion: apps/v1
kind: Deployment
metadata:
  labels: {app: dataio-batch-exchange-sink-boblebad-service, app.dbc.dk/team: metascrum,
    app.kubernetes.io/component: service, app.kubernetes.io/instance: boblebad, app.kubernetes.io/name: batch-exchange-sink,
    app.kubernetes.io/part-of: dataio}
  name: dataio-batch-exchange-sink-boblebad-service
spec:
  progressDeadlineSeconds: 180
  replicas: 1
  selector:
    matchLabels: {app: dataio-batch-exchange-sink-boblebad-service}
  strategy:
    rollingUpdate: {maxSurge: 1, maxUnavailable: 0}
    type: RollingUpdate
  template:
    metadata:
      labels: {app: dataio-batch-exchange-sink-boblebad-service, app.dbc.dk/team: metascrum,
        app.kubernetes.io/component: service, app.kubernetes.io/instance: boblebad,
        app.kubernetes.io/name: batch-exchange-sink, app.kubernetes.io/part-of: dataio,
        network-policy-http-incoming: 'yes', network-policy-http-outgoing: 'yes',
        network-policy-mq-outgoing: 'yes', network-policy-payara-incoming: 'yes',
        network-policy-postgres-outgoing: 'yes'}
    spec:
      containers:
      - env:
        - {name: JAVA_MAX_HEAP_SIZE, value: 2G}
        image: docker-io.dbc.dk/dbc-payara-batch-exchange-sink:master-28
        livenessProbe:
          failureThreshold: 3
          httpGet: {path: /dataio/sink/batch-exchange/status, port: 8080}
          initialDelaySeconds: 45
          periodSeconds: 5
        name: dataio-batch-exchange-sink-boblebad-service
        ports:
        - {containerPort: 4848, protocol: TCP}
        - {containerPort: 8080, protocol: TCP}
        readinessProbe:
          failureThreshold: 9
          httpGet: {path: /dataio/sink/batch-exchange/status, port: 8080}
          initialDelaySeconds: 15
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  annotations: {healthcheck.path: /dataio/sink/batch-exchange/status, healthcheck.severity: warning}
  labels: {app: dataio-batch-exchange-sink-boblebad-service, app.dbc.dk/team: metascrum,
    app.kubernetes.io/component: service, app.kubernetes.io/instance: boblebad, app.kubernetes.io/name: batch-exchange-sink,
    app.kubernetes.io/part-of: dataio, healthcheck.type: http}
  name: dataio-batch-exchange-sink-boblebad-service
spec:
  ports:
  - {name: http, port: 80, protocol: TCP, targetPort: 8080}
  - {name: admin, port: 4848, protocol: TCP, targetPort: 4848}
  selector: {app: dataio-batch-exchange-sink-boblebad-service}
  type: ClusterIP

""",




    "https://gitlab.url/api/v4/projects/103/repository/files/services%2Fdiff-sink.yml/raw?ref=staging": """apiVersion: apps/v1
kind: Deployment
metadata:
  labels: {app: dataio-diff-sink-service, app.dbc.dk/team: metascrum, app.kubernetes.io/component: service,
    app.kubernetes.io/name: diff-sink, app.kubernetes.io/part-of: dataio}
  name: dataio-diff-sink-service
spec:
  progressDeadlineSeconds: 180
  replicas: 1
  selector:
    matchLabels: {app: dataio-diff-sink-service}
  strategy:
    rollingUpdate: {maxSurge: 1, maxUnavailable: 0}
    type: RollingUpdate
  template:
    metadata:
      labels: {app: dataio-diff-sink-service, app.dbc.dk/team: metascrum, app.kubernetes.io/component: service,
        app.kubernetes.io/name: diff-sink, app.kubernetes.io/part-of: dataio, network-policy-http-incoming: 'yes',
        network-policy-http-outgoing: 'yes', network-policy-mq-outgoing: 'yes', network-policy-payara-incoming: 'yes'}
    spec:
      containers:
      - env:
        - {name: JAVA_MAX_HEAP_SIZE, value: 2G}
        image: docker-io.dbc.dk/dbc-payara-diff-sink:master-28
        livenessProbe:
          failureThreshold: 3
          httpGet: {path: /dataio/sink/diff/status, port: 8080}
          initialDelaySeconds: 45
          periodSeconds: 5
        name: dataio-diff-sink-service
        ports:
        - {containerPort: 4848, protocol: TCP}
        - {containerPort: 8080, protocol: TCP}
        readinessProbe:
          failureThreshold: 9
          httpGet: {path: /dataio/sink/diff/status, port: 8080}
          initialDelaySeconds: 15
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  labels: {app: dataio-diff-sink-service, app.dbc.dk/team: metascrum, app.kubernetes.io/component: service,
    app.kubernetes.io/name: diff-sink, app.kubernetes.io/part-of: dataio}
  name: dataio-diff-sink-service
spec:
  ports:
  - {name: http, port: 80, protocol: TCP, targetPort: 8080}
  - {name: admin, port: 4848, protocol: TCP, targetPort: 4848}
  selector: {app: dataio-diff-sink-service}
  type: ClusterIP
""",



    "https://gitlab.url/api/v4/projects/103/repository/files/services%2Fdummy-sink.yml/raw?ref=staging":"""apiVersion: apps/v1
kind: Deployment
metadata:
  labels: {app: dataio-dummy-sink-service, app.dbc.dk/team: metascrum, app.kubernetes.io/component: service,
    app.kubernetes.io/name: dummy-sink, app.kubernetes.io/part-of: dataio}
  name: dataio-dummy-sink-service
spec:
  progressDeadlineSeconds: 180
  replicas: 1
  selector:
    matchLabels: {app: dataio-dummy-sink-service}
  strategy:
    rollingUpdate: {maxSurge: 1, maxUnavailable: 0}
    type: RollingUpdate
  template:
    metadata:
      labels: {app: dataio-dummy-sink-service, app.dbc.dk/team: metascrum, app.kubernetes.io/component: service,
        app.kubernetes.io/name: dummy-sink, app.kubernetes.io/part-of: dataio, network-policy-http-incoming: 'yes',
        network-policy-http-outgoing: 'yes', network-policy-mq-outgoing: 'yes', network-policy-payara-incoming: 'yes'}
    spec:
      containers:
      - env:
        - {name: JAVA_MAX_HEAP_SIZE, value: 4G}
        image: docker-io.dbc.dk/dbc-payara-dummy-sink:master-27
        livenessProbe:
          failureThreshold: 3
          httpGet: {path: /dataio/sink/dummy/status, port: 8080}
          initialDelaySeconds: 45
          periodSeconds: 5
        name: dataio-dummy-sink-service
        ports:
        - {containerPort: 4848, protocol: TCP}
        - {containerPort: 8080, protocol: TCP}
        readinessProbe:
          failureThreshold: 9
          httpGet: {path: /dataio/sink/dummy/status, port: 8080}
          initialDelaySeconds: 15
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  labels: {app: dataio-dummy-sink-service, app.dbc.dk/team: metascrum, app.kubernetes.io/component: service,
    app.kubernetes.io/name: dummy-sink, app.kubernetes.io/part-of: dataio}
  name: dataio-dummy-sink-service
spec:
  ports:
  - {name: http, port: 80, protocol: TCP, targetPort: 8080}
  - {name: admin, port: 4848, protocol: TCP, targetPort: 4848}
  selector: {app: dataio-dummy-sink-service}
  type: ClusterIP
""",


    "https://gitlab.url/api/v4/projects/103/repository/commits?ref=staging": """{
  "id": "82b15418fdd0048a8aba1d61e7f5d81db312bdda",
  "short_id": "82b15418",
  "created_at": "2019-10-01T10:47:36.000+02:00",
  "parent_ids": [
    "e043759502dd3dd08b48ff53a4226e20ba8efeaa"
  ],
  "title": "Bump docker tag to TAG-2",
  "message": "Bump docker tag to TAG-2",
  "author_name": "Author",
  "author_email": "author@dbc.dk",
  "authored_date": "2019-10-01T10:47:36.000+02:00",
  "committer_name": "Committer",
  "committer_email": "commiter@dbc.dk",
  "committed_date": "2019-10-01T10:47:36.000+02:00",
  "stats": {
    "additions": 4,
    "deletions": 4,
    "total": 8
  },
  "status": null,
  "last_pipeline": null,
  "project_id": 103
}""",



    "https://gitlab.url/api/v4/projects/test_namespace%2Ftest_project": """{"id": 103,
  "description": "",
  "name": "rb_test_project",
  "name_with_namespace": "test_namespace / test_poject",
  "path": "rb_test_project",
  "path_with_namespace": "test_namespace/test_poject",
  "created_at": "2019-09-03T07:19:00.525Z",
  "default_branch": "master",
  "tag_list": [],
  "ssh_url_to_repo": "gitlab@gitlab.url:test_namespace/test_poject.git",
  "http_url_to_repo": "https://gitlab.url/test_namespace/test_poject.git",
  "web_url": "https://gitlab.url/test_namespace/test_poject",
  "readme_url": "https://gitlab.url/test_namespace/test_poject/blob/master/README.md",
  "avatar_url": null,
  "star_count": 0,
  "forks_count": 0,
  "last_activity_at": "2019-10-01T08:46:52.004Z",
  "namespace": {
    "id": 9,
    "name": "test_namespace",
    "path": "test_namespace",
    "kind": "group",
    "full_path": "test_namespace",
    "parent_id": null,
    "avatar_url": null,
    "web_url": "https://gitlab.url/groups/test_namespace"
  },
  "_links": {
    "self": "https://gitlab.url/api/v4/projects/103",
    "issues": "https://gitlab.url/api/v4/projects/103/issues",
    "merge_requests": "https://gitlab.url/api/v4/projects/103/merge_requests",
    "repo_branches": "https://gitlab.url/api/v4/projects/103/repository/branches",
    "labels": "https://gitlab.url/api/v4/projects/103/labels",
    "events": "https://gitlab.url/api/v4/projects/103/events",
    "members": "https://gitlab.url/api/v4/projects/103/members"
  },
  "empty_repo": false,
  "archived": false,
  "visibility": "internal",
  "resolve_outdated_diff_discussions": false,
  "container_registry_enabled": true,
  "issues_enabled": true,
  "merge_requests_enabled": true,
  "wiki_enabled": true,
  "jobs_enabled": true,
  "snippets_enabled": true,
  "issues_access_level": "enabled",
  "repository_access_level": "enabled",
  "merge_requests_access_level": "enabled",
  "wiki_access_level": "enabled",
  "builds_access_level": "enabled",
  "snippets_access_level": "enabled",
  "shared_runners_enabled": true,
  "lfs_enabled": true,
  "creator_id": 8,
  "import_status": "none",
  "import_error": null,
  "open_issues_count": 0,
  "runners_token": "token",
  "ci_default_git_depth": null,
  "public_jobs": true,
  "build_git_strategy": "fetch",
  "build_timeout": 3600,
  "auto_cancel_pending_pipelines": "enabled",
  "build_coverage_regex": null,
  "ci_config_path": null,
  "shared_with_groups": [],
  "only_allow_merge_if_pipeline_succeeds": false,
  "request_access_enabled": false,
  "only_allow_merge_if_all_discussions_are_resolved": false,
  "printing_merge_request_link_enabled": true,
  "merge_method": "merge",
  "auto_devops_enabled": false,
  "auto_devops_deploy_strategy": "continuous",
  "permissions": {
    "project_access": null,
    "group_access": {
      "access_level": 50,
      "notification_level": 3
    }
  },
  "approvals_before_merge": 0,
  "mirror": false
}"""
}
