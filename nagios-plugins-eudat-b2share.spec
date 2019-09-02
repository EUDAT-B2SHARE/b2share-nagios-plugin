#   Licensed to the Apache Software Foundation (ASF) under one or more
#   contributor license agreements.  See the NOTICE file distributed with
#   this work for additional information regarding copyright ownership.
#   The ASF licenses this file to You under the Apache License, Version 2.0
#   (the "License"); you may not use this file except in compliance with
#   the License.  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

Name:		nagios-plugins-eudat-b2share
Version:	0.1.1
Release:	1%{?dist}
Summary:	Nagios B2SHARE probe
License:	Apache License, Version 2.0
Packager:	Themis Zamani  <themiszamani@gmail.com>

Source:		%{name}-%{version}.tar.gz
BuildArch:	noarch
BuildRoot:	%{_tmppath}/%{name}-%{version}

AutoReqProv: no

Requires:	python
Requires:	python-argparse
Requires:	python-requests
Requires:	python-jsonschema
Requires:	python-validators


%description
Nagios probe to check functionality of B2SHARE Service

%prep
%setup -q

%define _unpackaged_files_terminate_build 0
%define probe_namespace eudat-b2share 

%install

install -d %{buildroot}/%{_libexecdir}/argo-monitoring/probes/eudat-b2share
install -m 755 check_b2share.py %{buildroot}/%{_libexecdir}/argo-monitoring/probes/eudat-b2share/check_b2share.py

%files
%dir /%{_libexecdir}/argo-monitoring
%dir /%{_libexecdir}/argo-monitoring/probes/
%dir /%{_libexecdir}/argo-monitoring/probes/%{probe_namespace}

%attr(0755,root,root) /%{_libexecdir}/argo-monitoring/probes/%{probe_namespace}/check_b2share.py

%changelog
* Mon Sep 02 2019 Harri Hirvonsalo   <harri.hirvonsalo@csc.fi> - 0.1.1-1
- Improved error handling to address false positive alerts.
* Wed Dec 05 2018 Harri Hirvonsalo   <harri.hirvonsalo@csc.fi> - 0.1-1
- Added requirements to specfile
* Tue Nov 27 2018 Themis Zamani  <themiszamani@gmail.com> - 0.1-1
- Initial version of the package.
