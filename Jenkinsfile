#!groovy

def workerNode = "devel9"

pipeline {
	agent {label workerNode}
	environment {
		ARTIFACTORY_LOGIN = credentials("artifactory_login")
	}
	triggers {
		pollSCM("H/02 * * * *")
	}
	stages {
		stage("upload wheel package") {
			agent {
				docker {
					label workerNode
					image "docker.dbc.dk/build-env"
					alwaysPull true
				}
			}
			when {
				branch "master"
			}
			steps {
				sh """#!/usr/bin/env bash
					set -xe
					rm -rf dist
					python3 setup.py egg_info --tag-build=${env.BUILD_NUMBER} bdist_wheel
					twine upload -u $ARTIFACTORY_LOGIN_USR -p $ARTIFACTORY_LOGIN_PSW --repository-url https://artifactory.dbc.dk/artifactory/api/pypi/pypi-dbc dist/*
				"""
			}
		}
	}
}
