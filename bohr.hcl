var "registry" {
  default = "436196666173.dkr.ecr.us-east-1.amazonaws.com"
}

docker_release "release" {
  registry    = "${var.registry}"
  build    = {
    image           = "slack-autoarchive"
    tag             = "${builtins.gitRevisionShort}"
    dockerfile_path = "./Dockerfile"
  }
}
