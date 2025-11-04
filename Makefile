PROTO_DIR := src/proto
OUT_DIR := src/vlog
PY := python3
PROTOC := $(shell command -v protoc 2>/dev/null)
PROTOC_GEN_JSONSCHEMA := $(shell command -v protoc-gen-jsonschema 2>/dev/null)
JSON_SCHEMA_OUT := src/proto/describe.schema.json


.PHONY: check-protoc proto proto-stub clean-proto

check-protoc:
	@if [ -z "$(PROTOC)" ]; then \
		echo ""; \
		echo "Error: protoc not found."; \
		echo "Please install Protocol Buffers compiler."; \
		echo "Visit https://protobuf.dev/installation/ for instructions."; \
		echo ""; \
		exit 1; \
	fi

jsonschema: check-protoc $(PROTO_SRC)
	$(PROTOC) --jsonschema_out=$(PROTO_DIR) $(PROTO_DIR)/describe.proto

proto:
	$(PROTOC) -I=src --python_out=src $(PROTO_DIR)

clean-proto:
	-rm -f $(OUT_DIR)/*_pb2.py $(OUT_DIR)/*_pb2.pyi
