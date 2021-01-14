#!/usr/bin/env python3

import typing

import io
import json
import os
import unittest.mock
import pathlib
import sys

import requests
import yaml

import deployversioner.deployversioner

class TestDeployVersioner(unittest.TestCase):
    def setUp(self):
        self.tests_path = get_tests_path()

    @unittest.mock.patch("requests.get", autospec=True)
    def test_set_image_tag(self, mock_requests_get):
        mock_requests_get.return_value = self.get_mock_response_from_file(
            "data/files-gui-yaml-response.txt")
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        result, _ = deployversioner.deployversioner.set_image_tag(
            gitlab_request, "gui.yaml", "new_image_tag")
        docs = [d for d in yaml.safe_load_all(result)]
        configuration_path = os.path.join(get_tests_path(), "gui.yaml")
        with open(configuration_path) as fp:
            depl_docs = [d for d in yaml.safe_load_all(io.BytesIO(fp.read().encode("utf8")))]
            self.assertEqual(docs, depl_docs)
        self.assertEqual(mock_requests_get.call_count, 1)

    @unittest.mock.patch("requests.get", autospec=True)
    def test_that_set_image_tag_sets_all_tags_in_a_yaml_doc(self, mock_requests_get):
        mock_requests_get.return_value = self.get_mock_response_from_file(
            "data/files-batch-exchange-sink-yaml-response.txt")
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        result,_ = deployversioner.deployversioner.set_image_tag(
            gitlab_request, "services/batch-exchange-sink.yml", "TAG-2")
        self.assertEqual(result.count("TAG-2"), 2)
        self.assertEqual(mock_requests_get.call_count, 1)

    @unittest.mock.patch("requests.get", autospec=True)
    @unittest.mock.patch("requests.Session", autospec=True)
    def test_that_change_image_tag_makes_a_commit_message_covering_all_bumped_tags(
            self, mock_requests_session, mock_requests_get):
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
        mock_requests_get.side_effect = [
            self.get_mock_response(repo_tree_response.encode("utf8")),
            self.get_mock_response(file_content_responses[0].encode("utf8")),
            self.get_mock_response(file_content_responses[1].encode("utf8")),
        ]
        mock_requests_session.return_value.post.return_value = self.get_mock_response(
            commit_response.encode("utf8"))
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        proposed_commits, changed_image_tags = deployversioner.deployversioner.change_image_tag(
            gitlab_request, "files", "TAG-2")
        deployversioner.deployversioner.commit_changes(
            gitlab_request, proposed_commits, "TAG-2", changed_image_tags)
        request = mock_requests_session.return_value.post.call_args[1]
        commit_message = json.loads(request["data"])["commit_message"]
        self.assertEqual("Bump docker tag from master-01 to TAG-2" in commit_message, True)
        self.assertEqual("Bump docker tag from master-02 to TAG-2" in commit_message, True)

    @unittest.mock.patch("requests.get", autospec=True)
    def test_multiple_yaml_files(self, mock_requests_get):
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
        mock_requests_get.side_effect = [
            self.get_mock_response(repo_tree_response.encode("utf8")),
            self.get_mock_response(file_content_responses[0].encode("utf8")),
            self.get_mock_response(file_content_responses[1].encode("utf8"))
        ]
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        result = deployversioner.deployversioner.change_image_tag(
            gitlab_request, "files", "master-02")
        self.assertEqual(len(result), 2)
        self.assertEqual(mock_requests_get.call_count, 3)

    @unittest.mock.patch("requests.get", autospec=True)
    def test_set_image_tag_identical_new_tag(self, mock_requests_get):
        mock_requests_get.return_value = self.get_mock_response_from_file(
            "data/files-services-dummy-sink-yaml-response.txt")
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        with self.assertRaises(deployversioner.deployversioner
                .VersionUnchangedException):
            deployversioner.deployversioner.set_image_tag(
                gitlab_request, "services/dummy-sink.yml", "master-27")

    def test_parse_image(self):
        image = "docker-io.dbc.dk/author-name-suggester-service:master-9"
        imagename, image_tag = deployversioner.deployversioner.parse_image(image)
        self.assertEqual(imagename, "docker-io.dbc.dk/author-name-suggester-service")
        self.assertEqual(image_tag, "master-9")

    @unittest.mock.patch("requests.get", autospec=True)
    @unittest.mock.patch("requests.Session", autospec=True)
    def test_commit_changes(self, mock_requests_session, mock_requests_get):
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
        mock_requests_get.side_effect = [
            self.get_mock_response(repo_tree_response.encode("utf8")),
            self.get_mock_response(file_content_response.encode("utf8")),
        ]
        mock_requests_session.return_value.post.return_value = self.get_mock_response(
            commit_response.encode("utf8"))
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        proposed_commits, changed_tags = deployversioner.deployversioner.change_image_tag(
            gitlab_request, "files", "TAG-2")
        deployversioner.deployversioner.commit_changes(
            gitlab_request, proposed_commits, "TAG-2", changed_tags)
        request = mock_requests_session.return_value.post.call_args[1]
        data = json.loads(request["data"])

        self.assertEqual([d["file_path"] for d in data["actions"]].sort(),
                         ["services/dummy-sink.yml", "services/batch-exchange-sink.yml", "services/diff-sink.yml"].sort())
        self.assertEqual(set([d['action'] for d in data["actions"]]), {"update"})
        self.assertEqual(data["branch"], "staging")
        self.assertEqual(data["commit_message"], "Bump docker tag to TAG-2\n\nBump docker tag from master-01 to TAG-2")
        self.assertEqual(request["headers"], {"private-token": "token",
            "Content-Type": "application/json"})

    @unittest.mock.patch("requests.get", autospec=True)
    @unittest.mock.patch("requests.Session", autospec=True)
    def test_commit_changes_error_400(self, mock_requests_session,
            mock_requests_get):
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
        mock_requests_get.side_effect = [
            self.get_mock_response(repo_tree_response.encode("utf8")),
            self.get_mock_response(file_content_response.encode("utf8")),
        ]
        # I would ideally like to test the retry logic here but I can't figure out how to mock it.
        commit_response = requests.Response()
        commit_response.status_code = 400
        # wraps makes sure that methods of the original object is called
        mock_commit_response = unittest.mock.Mock(requests.Response,
            wraps=commit_response)
        mock_requests_session.return_value.post.return_value = mock_commit_response
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        proposed_commits, changed_tags = deployversioner.deployversioner.change_image_tag(
            gitlab_request, "files", "TAG-2")
        with self.assertRaises(deployversioner.deployversioner
                .VersionerError):
            deployversioner.deployversioner.commit_changes(
                gitlab_request, proposed_commits, "TAG-2", changed_tags)

    @unittest.mock.patch("requests.get", autospec=True)
    def test_get_file_contents(self, mock_requests_get):
        mock_requests_get.return_value = self.get_mock_response_from_file(
            "data/files-gui-yaml-response.txt")
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        deployversioner.deployversioner.get_file_contents(
            gitlab_request, "gui.yaml")
        self.assertEqual(mock_requests_get.call_count, 1)
        request = mock_requests_get.call_args[0][0]
        self.assertEqual(mock_requests_get.call_args[0][0],
            "https://gitlab.url/api/v4/projects/103/repository/files/gui.yaml/raw?ref=staging")
        self.assertEqual(mock_requests_get.call_args[1]["headers"], {"private-token": "token"})

    # TODO: this test doesn't seem to make sense
    @unittest.mock.patch("requests.get", autospec=True)
    @unittest.mock.patch("requests.post", autospec=True)
    def test_file_does_not_exist(self, mock_requests_post, mock_requests_get):
        gitlab_request = deployversioner.deployversioner.GitlabRequest(
            "gitlab.url", "token", 103, "staging")
        with self.assertRaises(deployversioner.deployversioner
                                       .VersionerFileNotFound):
            deployversioner.deployversioner.change_image_tag(
                gitlab_request, "services/no_exist.yaml", "TAG-2")

    @unittest.mock.patch("requests.get", autospec=True)
    def test_get_project_number(self, mock_requests_get):
        mock_requests_get.return_value = self.get_mock_response_from_file(
            "data/projects-test-namespace-test-project-response.txt")
        self.assertEqual( 103, deployversioner.deployversioner
            .get_project_number( 'https://gitlab.url/api/v4/projects',
            'test_namespace/test_project', 'token') )
        self.assertEqual(mock_requests_get.call_count, 1)

    def get_mock_response(self, content):
        mock_response = unittest.mock.Mock(requests.Response)
        mock_response.content = content
        mock_response.text = mock_response.content.decode("utf8")
        mock_response.json = lambda: json.loads(mock_response.text)
        return mock_response

    def get_mock_response_from_file(self, response_filename):
        with open(os.path.join(self.tests_path, response_filename), "rb") as fp:
            return self.get_mock_response(fp.read())

def get_tests_path():
    try:
        # get the parent directory of the directory this file is in
        p = pathlib.PurePath(sys.modules[__name__].__file__)
        return str(p.parents[0])
    except IndexError:
        return "tests"
