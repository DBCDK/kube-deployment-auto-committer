#!/usr/bin/env python3

import argparse
import collections
import json
import sys
import typing
import urllib.parse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import yaml

GitlabRequest = collections.namedtuple("GitlabRequest", ["url", "api_token",
    "project_id", "branch"])

class VersionerError(Exception):
    pass

# this is a convenience exception to be able to avoid making commits if the
# image tag is unchanged. it doesn't really signify an error
class VersionUnchangedException(Exception):
    pass

class VersionerFileNotFound(VersionerError):
    pass

def get_file_contents(gitlab_request: GitlabRequest, filename: str) -> str:
    url = gitlab_request.url
    if url[:4] != "http":
        url = "https://{}".format(url)
    headers = {"private-token": gitlab_request.api_token}
    url = "{}/api/v4/projects/{}/repository/files/{}/raw?ref={}".format(url,
        gitlab_request.project_id, urllib.parse.quote(filename, safe=""), gitlab_request.branch)
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError as e:
        raise VersionerError("unable to get contents of {}: {}".format(
            filename, e))

def get_project_number(gitlab_get_projects_url: str, project_name:str, token:str) -> int:
    url = "{}/{}".format( gitlab_get_projects_url, urllib.parse.quote(project_name, safe='') )
    try:
        response = requests.get(url, headers={"private-token": token})
        response.raise_for_status()
        js = response.json()
        if "id" in js:
            return js["id"]
        raise VersionerError(f"No id found in response for url {url}: {js}")
    except requests.exceptions.HTTPError as e:
        raise VersionerError("unable to get contents of {}: {}".format( url, e))

def set_image_tag(gitlab_request: GitlabRequest, filename: str,
        new_image_tag: str) -> typing.Tuple[typing.Any, set]:
    file_contents = get_file_contents(gitlab_request, filename)
    docs = [d for d in yaml.safe_load_all(file_contents) if d is not None]
    changed=False
    changed_image_tags = set()
    for doc in docs:
        # added guard for None type as the script would otherwise fail on services with --- seperators
        if "kind" in doc and doc["kind"] in ["Deployment", "StatefulSet", "CronJob", "Job"]:
            try:
                if doc["kind"] == 'CronJob':
                    containers = doc["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"]
                else:
                    containers = doc["spec"]["template"]["spec"]["containers"]
                if len(containers) > 1:
                    raise VersionerError(
                        "too many container templates in the deployment")
                image = containers[0]["image"]
                imagename, image_tag = parse_image(image)
                if image_tag != new_image_tag:
                    changed_image_tags.add(image_tag)
                    containers[0]["image"] = "{}:{}".format(imagename,
                        new_image_tag)
                    changed=True
            except IndexError as e:
                raise VersionerError(e)
    if not changed:
        raise VersionUnchangedException(
            "new image tag matches old, nothing to do")
    return yaml.dump_all(docs), changed_image_tags

def parse_image(image: str) -> typing.List[str]:
    parts = image.split(":")
    if len(parts) != 2:
        raise VersionerError("invalid image format: {}".format(image))
    return parts


def get_content(gitlab_request: GitlabRequest, file: typing.Dict, image_tag: str, dir: str) -> typing.Dict:
    if dir not in file['path'] or not file['type'] == 'blob' or (
            not file['path'].endswith('.yml') and not file['path'].endswith('.yaml')):
        return {"commit_blob": {}, "changed_image_tags": set()}

    commit_blob = {}
    try:
        commit_blob['content'], changed_tags = set_image_tag(gitlab_request, file['path'], image_tag)
        commit_blob['action'] = 'update'
        commit_blob['file_path'] = file['path']
    except VersionUnchangedException as e:
        return {"commit_blob": {}, "changed_image_tags": set()}
    return {"commit_blob": commit_blob, "changed_image_tags": changed_tags}

def fetch_page_and_append(api_token, url, page_number, old_value = []):
    r"""fetch a page from url and return a new value of old_value + fetched data.

    Expects page to be a JSON array and appends the fetched page to the old_value fetch

    :param api_token to the gitlab api
    :param url without any paging arguments
    :param page_number
    :param old_value previous array that this page is added to.
    """
    response = requests.get(f"{url}&per_page=100&page={page_number}", headers={"private-token": api_token})
    response.raise_for_status()
    current_page = response.json()
    new_value = old_value + current_page
    if len(current_page) == 100:
        return new_value, True
    else:
        return new_value, False

def change_image_tag(gitlab_request: GitlabRequest, file_object: str, image_tag: str) -> typing.Tuple[typing.Any, set]:
    url = gitlab_request.url
    if url[:4] != "http":
        url = "https://{}".format(url)
    path = "/".join(file_object.split("/")[:-1])
    url = f"{url}/api/v4/projects/{gitlab_request.project_id}/repository/tree/?ref={gitlab_request.branch}&recursive=True&path={path}"
    page_number = 1
    try:
        (file_tree, more_to_fetch) = fetch_page_and_append(gitlab_request.api_token, url, page_number, [])
        while more_to_fetch:
            page_number += 1
            (file_tree, more_to_fetch) = fetch_page_and_append(gitlab_request.api_token, url, page_number, file_tree)


        if not file_object=="" and file_object not in [n["path"] for n in file_tree]:
            raise VersionerFileNotFound("File or dir {} not found".format(file_object))
        changes = [changes for changes in
                            [get_content(gitlab_request, n, image_tag, file_object) for n in file_tree]
                            if not changes["commit_blob"]=={}]
        proposed_commits = []
        changed_image_tags: set = set()
        for change in changes:
            proposed_commits.append(change["commit_blob"])
            changed_image_tags.update(change["changed_image_tags"])
        return proposed_commits, changed_image_tags
    except requests.exceptions.HTTPError as e:
        raise VersionerError("unable to get contents of dir: {}: {}".format(
            file_object, e))


def format_commit_message(tag: str, changed_image_tags: typing.Set[str]):
    lines = ["Bump docker tag from {} to {}".format(existing_image_tag, tag) for existing_image_tag in
            changed_image_tags]
    return "Bump docker tag to {}\n\n{}".format(tag, "\n".join(lines))

def commit_changes(gitlab_request: GitlabRequest, proposed_commits: dict, tag:str, changed_image_tags: typing.Set[str]):
    if len(proposed_commits)==0:
        raise VersionUnchangedException("no changes found.")
    commit_blob={"branch": gitlab_request.branch, "commit_message": format_commit_message(tag, changed_image_tags), "actions":[]}
    for proposed_commit in proposed_commits:
        commit_blob["actions"].append({"action": "update", "file_path": proposed_commit["file_path"], "content": proposed_commit["content"]})
    url = gitlab_request.url
    if url[:4] != "http":
        url = "https://{}".format(url)
    headers = {"private-token": gitlab_request.api_token, "Content-Type": "application/json"}
    url = "{}/api/v4/projects/{}/repository/commits?ref={}".format(url,
        gitlab_request.project_id,
        gitlab_request.branch)
    try:
        session = requests.Session()
        # Normally status 400 means that you shouldn't retry the request but in this case it seems to work
        adapter = HTTPAdapter(max_retries=Retry(total=3,
            status_forcelist=[400], allowed_methods=["POST"],
            backoff_factor=2))
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        response = session.post(url, headers=headers, data=json.dumps(commit_blob))
        response.raise_for_status()
        js = response.json()
        if js["status"] is not None:
            raise VersionerError(f"Unable to do commit with data {commit_blob}. Status from {url} is {js}")
    except (requests.exceptions.HTTPError, requests.exceptions.RetryError) as e:
        raise VersionerError("unable to do commit to repository at: {}  with docker-tag:{}\n {}".format(
            url, tag, e))

def setup_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("deployment_configuration",
        metavar="deployment-configuration",
        help="filename or dir of deployment configuration to change. If a dir is specified, all .yaml and .yml files "
             "in that dir recursively will be included.")
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

        proposed_commits, changed_image_tags = change_image_tag(gitlab_request, args.deployment_configuration, args.image_tag)

        if args.dry_run:
            for proposed_commit in proposed_commits:
                print("\n\nFile: {}".format(proposed_commit['file_path']))
                print("=" * (len(proposed_commit['file_path']) + 6))
                print(proposed_commit['content'])
        else:
            commit_changes(gitlab_request, proposed_commits, args.image_tag, changed_image_tags)

    except VersionUnchangedException as e:
        print(e)
    except VersionerError as e:
        print("caught unexpected error: {}".format(e), file=sys.stderr)
        sys.exit(1)
