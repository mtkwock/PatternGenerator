load("@rules_proto//proto:defs.bzl", "proto_library")
# load("@protobuf//:protobuf.bzl", "proto_library")
load("@protobuf//:protobuf.bzl", "py_proto_library")


proto_library(
	name = "spawner_proto",
	srcs = ["spawner.proto"],
)

py_proto_library(
	name = "spawner_py_pb2",
	srcs = ["spawner.proto"],
    visibility = ["//visibility:public"],
)

