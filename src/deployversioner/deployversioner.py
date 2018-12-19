#!/usr/bin/env python3

# Copyright Dansk Bibliotekscenter a/s. Licensed under GPLv3
# See license text in LICENSE.txt or at https://opensource.dbc.dk/licenses/gpl-3.0/

import argparse
import json
import sys
import typing
import urllib.error
import urllib.parse
import urllib.request

import yaml

class VersionerError(Exception):
    pass

# this is a convenience exception to be able to avoid making commits if the
# image tag is unchanged. it doesn't really signify an error
class VersionUnchangedException(Exception):
    pass

def set_image_tag(configuration_path: str, new_image_tag: str) -> str:
    with open(configuration_path) as fp:
        docs = [d for d in yaml.load_all(fp)]
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

def commit_changes(gitlab_url: str, gitlab_api_token: str, project_id: int, filename: str,
        branch: str, content: str) -> str:
    if gitlab_url[:4] != "http":
        gitlab_url = "https://{}".format(gitlab_url)
    headers = {"private-token": gitlab_api_token,
        "content-type": "application/json"}
    commit_message = "updating image tag in {}".format(filename)
    data = {"branch": branch, "content": content, "commit_message": commit_message}
    url = "{}/api/v4/projects/{}/repository/files/{}".format(gitlab_url,
        project_id, urllib.parse.quote(filename, safe=""))
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
        metavar="deployment-configuration")
    parser.add_argument("gitlab_api_token", metavar="gitlab-api-token",
        help="private token for accessing the gitlab api")
    parser.add_argument("project_id", metavar="project-id",
        help="id of gitlab project. can be found in the output of "
        "gitlab.url/api/v4/projects [https://docs.gitlab.com/ee/api/"
        "projects.html#list-all-projects]")
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
        content = set_image_tag(args.deployment_configuration, args.image_tag)
        if args.dry_run:
            print(content)
        else:
            commit_changes(args.gitlab_url, args.gitlab_api_token, args.project_id,
                args.deployment_configuration, args.branch, content)
    except VersionUnchangedException as e:
        print(e)
    except VersionerError as e:
        print("caught enexpected error: {}".format(e), file=sys.stderr)
        sys.exit(1)
