#!groovy
@Library('ai') _

def workerNode = "devel12"

pipeline {
	agent {
		docker {
			label workerNode
			image "docker-dbc.artifacts.dbccloud.dk/build-env"
			alwaysPull true
		}
	}
	environment {
		PACKAGE = "kube-deployment-auto-committer"
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
				upload()
			}
		}
	}
}
