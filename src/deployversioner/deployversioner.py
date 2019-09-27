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
    changed=False
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
                    changed=True

            except IndexError as e:
                raise VersionerError(e)
    if not changed:
        raise VersionUnchangedException(
            "new image tag matches old, nothing to do")
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


def get_content(gitlab_request: GitlabRequest, file: typing.Dict, image_tag: str, dir: str) -> typing.Dict:
    if dir not in file['path'] or not file['type'] == 'blob' or (
            not file['path'].endswith('.yml') and not file['path'].endswith('.yaml')):
        return None

    commit_blob = {}
    try:
        commit_blob['content'] = set_image_tag(gitlab_request, file['path'], image_tag)
        commit_blob['action'] = 'update'
        commit_blob['file_path'] = file['path']
    except VersionUnchangedException as e:
        return None
    return commit_blob


def change_image_tag_in_all_yaml_files_in_dir(gitlab_request: GitlabRequest, dir: str, image_tag: str):
    url = gitlab_request.url
    if url[:4] != "http":
        url = "https://{}".format(url)
    headers = {"private-token": gitlab_request.api_token}
    url = "{}/api/v4/projects/{}/repository/tree/?ref={}&recursive=True".format(url,
                                                                                gitlab_request.project_id,
                                                                                gitlab_request.branch)
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        page = urllib.request.urlopen(request)
        p = page.read().decode("utf8")
        proposed_commits = [proposed_commit for proposed_commit in
                            [get_content(gitlab_request, n, image_tag, dir) for n in json.loads(p)]
                            if proposed_commit is not None]
        return proposed_commits
    except urllib.error.URLError as e:
        raise VersionerError("unable to get contents of dir: {}: {}".format(
            dir, e))

def commit_changes_in_multiple_files(gitlab_rquest: GitlabRequest, proposed_commits: dict):
    # Todo: Make json blob here and do post to gitlab
    return None

def setup_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("deployment_configuration",
        metavar="deployment-configuration",
        help="filename of deployment configuration to change. Or all .yaml and .yml files in <deployment-configuration> dir. "
             "Add --dir to command to specify that this is a directory.")
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
    parser.add_argument("--dir", action="store_true", default=False, help="Specify --dir to indicate that "
                                                                          "<deployment_configuration> is a directory.")
    args = parser.parse_args()
    return args


def main():
    args = setup_args()
    try:
        project_id = get_project_number("{}/api/v4/projects".format(args.gitlab_url), args.project_name, args.gitlab_api_token)

        gitlab_request = GitlabRequest(args.gitlab_url,
            args.gitlab_api_token, project_id, args.branch)

        if args.dir:
            proposed_commits = change_image_tag_in_all_yaml_files_in_dir(gitlab_request, args.deployment_configuration,
                                                                         args.image_tag)
            if args.dry_run:
                for proposed_commit in proposed_commits:
                    print("\n\nFile: {}".format(proposed_commit['file_path']))
                    print("=" * (len(proposed_commit['file_path']) + 6))
                    print(proposed_commit['content'])
            else:
                commit_changes_in_multiple_files(gitlab_request, proposed_commits)
        else:
            content = set_image_tag(gitlab_request,
                                    args.deployment_configuration, args.image_tag)
            if args.dry_run:
                print(content)
            else:
                commit_changes(gitlab_request, args.deployment_configuration, content)
    except VersionUnchangedException as e:
        print(e)
    except VersionerError as e:
        print("caught enexpected error: {}".format(e), file=sys.stderr)
        sys.exit(1)
