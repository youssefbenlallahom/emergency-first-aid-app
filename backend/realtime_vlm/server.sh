#!/usr/bin/env bash

# start the llama.cpp server

llama-server -hf ggml-org/SmolVLM-500M-Instruct-GGUF -ngl 99 --host 0.0.0.0 --port 8080