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
		ARTIFACTORY_LOGIN = credentials("artifactory_login")
	}
	triggers {
		pollSCM("H/02 * * * *")
	}
	stages {
		stage("test") {
			steps {
				test()
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
