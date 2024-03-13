#!groovy

def workerNode = "devel9"

pipeline {
	agent {
		docker {
			label workerNode
			image "docker-dbc.artifacts.dbccloud.dk/build-env"
			alwaysPull true
		}
	}
	environment {
		ARTIFACTORY_LOGIN = credentials("artifactory_login")
	}
	triggers {
		pollSCM("H/02 * * * *")
	}
	stages {
		stage("test") {
			steps {
				sh """#!/usr/bin/env bash
					set -xe
					rm -rf ENV
					python3 -m venv ENV
					source ENV/bin/activate
					pip install -U pip
					pip install .
					python3 -m unittest discover -s tests
				"""
			}
		}
		stage("upload wheel package") {
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
