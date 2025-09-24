.PHONY: proto install-dev install-agent install-cli run-agent clean

proto:
	python3 -m grpc_tools.protoc -I./proto --python_out=. --grpc_python_out=. proto/dockyard.proto

install-dev:
	pip3 install -r requirements.txt

install-agent:
	pip3 install -r agent/requirements.txt

install-cli:
	pip3 install -r cli/requirements.txt

run-agent:
	python3 agent/main.py

clean:
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete
	rm -f dockyard_pb2.py dockyard_pb2_grpc.py
