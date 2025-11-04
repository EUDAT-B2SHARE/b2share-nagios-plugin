Name:		argo-probe-eudat-b2share
Version:	0.8
Release:	1%{?dist}
Summary:	Monitoring scripts that check the functionalities of B2SHARE
License:	GPLv3+
Packager:	Themis Zamani <themiszamani@gmail.com>

Source:		%{name}-%{version}.tar.gz
BuildArch:	noarch
BuildRoot:	%{_tmppath}/%{name}-%{version}
AutoReqProv:    no
Requires:	python3
Requires:	python3-requests
Requires: 	python-jsonschema

%description
Nagios probe to check functionality of B2SHARE service

%prep
%setup -q

%define _unpackaged_files_terminate_build 0 

%install
install -d %{buildroot}/%{_libexecdir}/argo/probes/eudat-b2share
install -m 755 check_b2share.py %{buildroot}/%{_libexecdir}/argo/probes/eudat-b2share/check_b2share.py

%files
%dir /%{_libexecdir}/argo
%dir /%{_libexecdir}/argo/probes/
%dir /%{_libexecdir}/argo/probes/eudat-b2share

%attr(0755,root,root) /%{_libexecdir}/argo/probes/eudat-b2share/check_b2share.py

%changelog
* Tue Nov 04 2025 Themis Zamani <themiszamani@gmail.com> - 0.8.1
- Minor updates to url check 
* Fri Apr 05 2024 Giacomo Furlan   <giacomo.furlan@csc.fi> - 0.2.1
- Update python to 3.9
- Update requirements and dependencies
- Remove validator dependency
* Mon Mar 14 2022 Themis Zamani <themiszamani@gmail.com> - 0.5
- Update package prerequisites based on argo monitoring. 
* Mon Mar 14 2022 Themis Zamani <themiszamani@gmail.com> - 0.5
- Update package prerequisites based on argo monitoring. 
* Tue Nov 27 2018 Themis Zamani  <themiszamani@gmail.com> - 0.1-1
- Initial version of the package. 
* Tue Nov 27 2018 Harri Hirvonsalo   <harri.hirvonsalo@csc.fi> - 0.1-1
- Initial version of the package. 
