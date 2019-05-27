#!/usr/bin/env python3

# Copyright Dansk Bibliotekscenter a/s. Licensed under GPLv3
# See license text in LICENSE.txt or at https://opensource.dbc.dk/licenses/gpl-3.0/

import argparse
import collections
import json
import sys
import typing
import urllib.error
import urllib.parse
import urllib.request

import yaml

GitlabRequest = collections.namedtuple("GitlabRequest", ["url", "api_token",
    "project_id", "branch"])

class VersionerError(Exception):
    pass

# this is a convenience exception to be able to avoid making commits if the
# image tag is unchanged. it doesn't really signify an error
class VersionUnchangedException(Exception):
    pass

def get_file_contents(gitlab_request: GitlabRequest, filename: str) -> str:
    url = gitlab_request.url
    if url[:4] != "http":
        url = "https://{}".format(url)
    headers = {"private-token": gitlab_request.api_token}
    url = "{}/api/v4/projects/{}/repository/files/{}/raw?ref={}".format(url,
        gitlab_request.project_id, urllib.parse.quote(filename, safe=""), gitlab_request.branch)
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        page = urllib.request.urlopen(request)
        return page.read().decode("utf8")
    except urllib.error.URLError as e:
        raise VersionerError("unable to get contents of {}: {}".format(
            filename, e))

def get_project_number(gitlab_get_projects_url: str, project_name:str, token:str) -> int:
    url = "{}/{}".format( gitlab_get_projects_url, urllib.parse.quote(project_name, safe='') )
    request = urllib.request.Request( url ,
                                      method="GET",
                                      headers={"private-token": token} )
    try:
        page = urllib.request.urlopen(request)
        return  json.loads( page.read().decode("utf8") )["id"]

    except urllib.error.URLError as e:
        raise VersionerError("unable to get contents of {}: {}".format( url, e))


def set_image_tag(gitlab_request: GitlabRequest, filename: str,
        new_image_tag: str) -> str:
    file_contents = get_file_contents(gitlab_request, filename)
    docs = [d for d in yaml.safe_load_all(file_contents)]
    for doc in docs:
        if "kind" in doc and doc["kind"] == "Deployment":
            try:
                containers = doc["spec"]["template"]["spec"]["containers"]
                if len(containers) > 1:
                    raise VersionerError(
                        "too many container templates in the deployment")
                image = containers[0]["image"]
                imagename, image_tag = parse_image(image)
                if image_tag != new_image_tag:
                    containers[0]["image"] = "{}:{}".format(imagename,
                        new_image_tag)
                else:
                    raise VersionUnchangedException(
                        "new image tag matches old, nothing to do")
            except IndexError as e:
                raise VersionerError(e)
    return yaml.dump_all(docs)

def parse_image(image: str) -> typing.List[str]:
    parts = image.split(":")
    if len(parts) != 2:
        raise VersionerError("invalid image format: {}".format(image))
    return parts

def commit_changes(gitlab_request: GitlabRequest, filename: str,
        content: str) -> str:
    url = gitlab_request.url
    if url[:4] != "http":
        url = "https://{}".format(url)
    headers = {"private-token": gitlab_request.api_token,
        "content-type": "application/json"}
    commit_message = "updating image tag in {}".format(filename)
    data = {"branch": gitlab_request.branch, "content": content,
        "commit_message": commit_message}
    url = "{}/api/v4/projects/{}/repository/files/{}".format(url,
        gitlab_request.project_id, urllib.parse.quote(filename, safe=""))
    request = urllib.request.Request(url, headers=headers,
        data=json.dumps(data).encode("utf8"), method="PUT")
    try:
        page = urllib.request.urlopen(request)
        return page.read().decode("utf8")
    except urllib.error.URLError as e:
        raise VersionerError("unable to commit change: {}".format(e))

def setup_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("deployment_configuration",
        metavar="deployment-configuration",
        help="filename of deployment configuration to change")
    parser.add_argument("gitlab_api_token", metavar="gitlab-api-token",
        help="private token for accessing the gitlab api")
    parser.add_argument("project_name", metavar="project-name",
        help="Name of project (including group hierarchy), e.g., metascrum/rrflow-deploy")
    parser.add_argument("-b", "--branch", default="staging")
    parser.add_argument("image_tag", metavar="image-tag",
        help="new tag to commit into the deployment configuration")
    parser.add_argument("--gitlab-url", default="https://gitlab.dbc.dk")
    parser.add_argument("-n", "--dry-run", action="store_true",
        help="don't commit changes, print them to stdout")
    args = parser.parse_args()
    return args

def main():
    args = setup_args()
    try:

        project_id = get_project_number("{}/api/v4/projects".format(args.gitlab_url), args.project_name, args.gitlab_api_token)

        gitlab_request = GitlabRequest(args.gitlab_url,
            args.gitlab_api_token, project_id, args.branch)
        content = set_image_tag(gitlab_request,
            args.deployment_configuration, args.image_tag)
        if args.dry_run:
            print(content)
        else:
            commit_changes(gitlab_request, args.deployment_configuration,
                content)
    except VersionUnchangedException as e:
        print(e)
    except VersionerError as e:
        print("caught enexpected error: {}".format(e), file=sys.stderr)
        sys.exit(1)
