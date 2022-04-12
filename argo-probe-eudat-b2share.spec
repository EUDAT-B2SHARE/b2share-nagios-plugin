Name:		argo-probe-eudat-b2share
Version:	0.6
Release:	1%{?dist}
Summary:	Monitoring scripts that check the functionalities of B2SHARE
License:	GPLv3+
Packager:	Themis Zamani <themiszamani@gmail.com>

Source:		%{name}-%{version}.tar.gz
BuildArch:	noarch
BuildRoot:	%{_tmppath}/%{name}-%{version}
AutoReqProv:    no
Requires:       python-requests, python2-jsonschema, python-enum34

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
* Mon Mar 14 2022 Themis Zamani <themiszamani@gmail.com> - 0.5
- Update package prerequisites based on argo monitoring. 
* Tue Nov 27 2018 Themis Zamani  <themiszamani@gmail.com> - 0.1-1
- Initial version of the package. 
* Tue Nov 27 2018 Harri Hirvonsalo   <harri.hirvonsalo@csc.fi> - 0.1-1
- Initial version of the package. 

