#!/bin/bash

# Create directory structure
mkdir -p python

# Install dependencies
pip install -r requirements.txt -t python

# Create zip file
zip -r opensearch-layer.zip python

echo "Layer created: opensearch-layer.zip"
