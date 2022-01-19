Name:		nagios-plugins-eudat-b2share
Version:	0.5
Release:	1%{?dist}
Summary:	Nagios probe for B2SHARE
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

install -d %{buildroot}/%{_libexecdir}/argo-monitoring/probes/eudat-b2share
install -d %{buildroot}/%{_sysconfdir}/nagios/plugins/eudat-b2share
install -m 755 check_b2share.py %{buildroot}/%{_libexecdir}/argo-monitoring/probes/eudat-b2share/check_b2share.py

%files
%dir /%{_libexecdir}/argo-monitoring
%dir /%{_libexecdir}/argo-monitoring/probes/
%dir /%{_libexecdir}/argo-monitoring/probes/eudat-b2share

%attr(0755,root,root) /%{_libexecdir}/argo-monitoring/probes//eudat-b2share/check_b2share.py

%changelog
* Tue Nov 27 2018 Themis Zamani  <themiszamani@gmail.com> - 0.1-1
- Initial version of the package. 
* Tue Nov 27 2018 Harri Hirvonsalo   <harri.hirvonsalo@csc.fi> - 0.1-1
- Initial version of the package. 

