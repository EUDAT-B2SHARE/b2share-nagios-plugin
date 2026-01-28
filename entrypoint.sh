#!/bin/sh

. .venv/bin/activate

# Detect interactive TTY; display message only in interactive shells
if [ -t 1 ]; then
    cat <<'EOF'
=================================================================

 Welcome to this nagios plugin test container.

 In order to test the plugin, run the following command:

 ./check_b2share.py --url https://b2share.eudat.eu:443

=================================================================
EOF
fi

exec "$@"
