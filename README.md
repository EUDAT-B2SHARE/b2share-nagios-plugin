# B2SHARE Monitoring probe for ARGO

## Setting up environment
This probe has been written for Python 3 and tested with Python 3.9
You may need to install (using e.g. `pip3`) the following Python modules as
they do not come with original distribution:
- requests
- jsonschema

## Overview
The B2SHARE probe for ARGO does the following interaction
with B2SHARE REST API:

- Search for records
- Fetch record's metadata from search results
- Fetch record's metadata schema
- Validate record's metadata agains record's metadata schema
- If a record with file is available, check that a file
  should be able to be downloaded (HTTP HEAD request)

B2SHARE ARGO probe:
- makes HTTP requests (GET, HEAD) to B2SHARE's REST API
- parses JSON responses obtained from B2SHARE's REST API

## Pre-requisites:
- None


## Package dependences

Python modules "requests" and "jsonschema" have the following dependencies:

```python
requests==2.31.0
├── certifi [required: >=2017.4.17, installed: 2024.2.2]
├── charset-normalizer [required: >=2,<4, installed: 3.3.2]
├── idna [required: >=2.5,<4, installed: 3.6]
└── urllib3 [required: >=1.21.1,<3, installed: 2.2.1]


jsonschema==4.21.1
├── attrs [required: >=22.2.0, installed: 23.2.0]
├── jsonschema-specifications [required: >=2023.03.6, installed: 2023.12.1]
│   └── referencing [required: >=0.31.0, installed: 0.34.0]
│       ├── attrs [required: >=22.2.0, installed: 23.2.0]
│       └── rpds-py [required: >=0.7.0, installed: 0.18.0]
├── referencing [required: >=0.28.4, installed: 0.34.0]
│   ├── attrs [required: >=22.2.0, installed: 23.2.0]
│   └── rpds-py [required: >=0.7.0, installed: 0.18.0]
└── rpds-py [required: >=0.7.1, installed: 0.18.0]
```
## How it works?

```
$ python check_b2share.py -h
usage: check_b2share.py [-h] -u URL [-t TIMEOUT] [-v] [--verify-tls]
                        [--error-if-no-records-present]

B2SHARE Nagios probe

optional arguments:
  -h, --help            show this help message and exit
  -u URL, --url URL     Base URL of B2SHARE instance to test.
  -t TIMEOUT, --timeout TIMEOUT
                        Timeout of the test. Positive integer.
  -v, --verbose         Increase output verbosity
  --verify-tls          Should TLS certificate of B2SHARE server be verified
  --error-if-no-records-present
                        Should probe give an error if no records are present
                        at the B2SHARE instance.
```

Example

`$ python3 check_b2share.py -u https://b2share.eudat.eu:443 -t 15 -vv`

```
TLS certificate verification: OFF
Verbosity level: 2
Timeout: 15 seconds
B2SHARE URL: https://b2share.eudat.eu:443
Starting B2SHARE Probe...
---------------------------
Making a search.
Search returned some results.
A record containing files was found.
Fetching record's metadata schema.
Validating record's metadata schema.
Validating record against metadata schema.
Accessing file bucket of the record.
Fetching first file of the bucket.
---------------------------
OK, records, metadata schemas and files are accessible.
```
# How to run the code in a conatiner

In the root folder of the project, build the container:
```bash
docker build -t <name_of_the_image>:<tag_of_the_image> .
```
Then run the code in the container
```bash
docker run -it --rm <name_of_the_image>:<tag_of_the_image> python3 check_b2share.py -u https://b2share.eudat.eu:443 -t 15 -vv
```

## Credits
This code is based on [EUDAT-B2ACCESS/b2access-probe](https://github.com/EUDAT-B2ACCESS/b2access-probe)
