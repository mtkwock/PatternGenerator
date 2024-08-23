load("@rules_python//python:defs.bzl", "py_binary")
load("@rules_python//python:defs.bzl", "py_library")
load("@rules_python//python:defs.bzl", "py_test")

py_library(
	name = "state_function",
	srcs = ["state_function.py"],
	deps = [
		"//proto:spawner_py_pb2",
	])

py_test(
	name = "state_function_test",
	srcs = ["state_function_test.py"],
	deps = [":state_function"],
  timeout = "short",
)

py_library(
  name = "entity",
  srcs = ["entity.py"],
  deps = [
    ":state_function",
    "//proto:spawner_py_pb2",
  ],
)

py_test(
  name = "entity_test",
  srcs = ["entity_test.py"],
  deps = [
    ":entity",
    ":state_function",
  ],
  timeout = "short",
)

py_binary(
	name = "main",
	srcs = ["main.py"],
	deps = [
    ":entity",
    ":state_function",
		"//proto:spawner_py_pb2",
		"@rules_python//python/runfiles",
    "@my_deps//pygame",
	],
  imports = [
    "pygame",
  ],
	data = [
		"my_first_entity.textproto",
    "simple_solar_system.textproto",
	] + glob("resources/images/*.png") + glob("resources/images/*.jpg"),
)