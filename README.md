# Slack Channel Exporter

Exports Slack channel messages, including threads and images, to JSON or PDF format.

![Dependency Status](https://img.shields.io/badge/dependencies-up%20to%20date-brightgreen)

![Code Scanning](https://github.com/johann8384/slack-exporter/actions/workflows/codeql.yml/badge.svg)

![Test Status](https://github.com/johann8384/slack-exporter/actions/workflows/tests.yml/badge.svg)


## Features
- Exports messages in chronological order
- Includes user avatars and names
- Preserves threaded conversations
- Embeds images as base64 data
- Supports JSON and PDF output formats

## Requirements
- Python 3.11+
- Slack Bot Token with required permissions:
  - channels:history
  - channels:read
  - files:read
  - users:read

## Installation

```bash
pip install -r requirements.txt
```

## Usage

Set your Slack token:
```bash
export SLACK_TOKEN='xoxb-your-token'
```

Run the exporter:
```bash
# Export to JSON
python exporter.py --format json

# Export to PDF
python exporter.py --format pdf
```

## Docker

Build:
```bash
docker build -t slack-exporter .
```

Run:
```bash
docker run -v "$(pwd):/app" -e SLACK_TOKEN='xoxb-your-token' slack-exporter --format pdf
