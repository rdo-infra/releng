#!/bin/bash

GNUPGHOME="/tmp/gpg"

OPENSTACK_PUBKEYS="
0x01527a34f0d0080f8a5db8d6eb6c5df21b4b6363
0x4c8b8b5a694f612544b3b4bac52f01a3fbdb9949
0x4c29ff0e437f3351fd82bdf47c5a3bc787dc7035
0x5d2d1e4fb8d38e6af76c50d53d4fec30cf5ce3da
0x80fcce3dc49bd7836fc2464664dbb05acc5e7c28
0x2426b928085a020d8a90d0d879ab7008d0896c8a
0x27023b1ffccd8e3ae9a5ce95d943d5d270273ada
0xa63ea142678138d1bb15f2e303bdfd64dd164087
0xbba3b1e67a7303dd1769d34595bf2e4d09004514
0xc96bfb160752606daa0de2fa05eb5792c876df9a
0xc31292066be772022438222c184fd3e1edf21a78
0xcdc08088c3cb45a9be08332b2354069e5b504663
0xd47bab1b7dc2e262a4f6171e8b1b03fd54e2ac07
"

stat $GNUPGHOME >/dev/null 2>&1 || mkdir $GNUPGHOME
chmod 700 $GNUPGHOME

set -e
for pubkey in $OPENSTACK_PUBKEYS; do
    pubkey_file_path=$GNUPGHOME/$pubkey.txt
    if [ ! -f "$pubkey_file_path" ]; then
        curl -sL https://releases.openstack.org/_static/$pubkey.txt -o $pubkey_file_path >/dev/null
        gpg --homedir $GNUPGHOME --import $pubkey_file_path
    fi
done
set +e

spectool -g *.spec

if compgen -G "*.asc" >/dev/null; then
    key_fingerprint=$(gpg --homedir $GNUPGHOME --verify *.asc *.tar.gz 2>&1 | grep -e "^Primary key fingerprint" | cut -d: -f2 | tr -d ' ')
    sources_gpg_sign=0x${key_fingerprint,,}
    if [ -n "$key_fingerprint" ]; then
        sed -i "s/%global sources_gpg_sign.*/%global sources_gpg_sign $sources_gpg_sign/" *.spec
        git commit -a --amend --no-edit
    fi
fi
