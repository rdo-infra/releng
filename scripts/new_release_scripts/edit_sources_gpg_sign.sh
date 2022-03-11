#!/bin/bash

# Set the right fingerprint to sources_gpg_sign in SPEC file.
#
# This script aims to find out which Openstack release cycle signing
# key has been used to sign a tarball, and put it as value of
# sources_gpg_sign in SPEC file.
#
# example:
#         bash edit_source_gpg_sign.sh
#         bash edit_source_gpg_sign.sh python-oslo-cache.spec
#
# Even though it's recommanded to check the fingerprints after
# importing the keys into the keyring to avoid MITM attacks,
# it's not necessary in this case. We're using those GPG
# keys only to get the primary key fingerprint used to sign
# the tarball file. If there is something wrong, we'll hit
# issue while building SRPM as spectool won't be able to
# download the key file (i.e as per https://releases.openstack.org/_static/%{sources_gpg_sign}.txt)

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

SPEC_FILE=$1
if [ ! -f "$SPEC_FILE" ]; then
    is_spec_file=$(compgen -G "*.spec")
    if [ -n "$is_spec_file" ]; then
        SPEC_FILE=$is_spec_file
    else
        echo "There is no SPEC file to check."
        exit 1
    fi
fi

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

rm -f $GNUPGHOME/{*.tar.gz,*.asc} >/dev/null 2>&1
spectool -g -S -C $GNUPGHOME $SPEC_FILE >/dev/null 2>&1

if compgen -G "$GNUPGHOME/*.asc" >/dev/null; then
    key_fingerprint=$(gpg --homedir $GNUPGHOME --verify $GNUPGHOME/*.asc $GNUPGHOME/*.tar.gz 2>&1 | grep -e "^Primary key fingerprint" | cut -d: -f2 | tr -d ' ')
    sources_gpg_sign=0x${key_fingerprint,,}
    if [ -n "$key_fingerprint" ]; then
        grep $sources_gpg_sign $SPEC_FILE >/dev/null 2>&1
        if [ $? -ne 0 ]; then
            sed -i "s/%global sources_gpg_sign.*/%global sources_gpg_sign $sources_gpg_sign/" $SPEC_FILE
            git commit -a --amend --no-edit >/dev/null
            echo "sources_gpg_sign is now set to $sources_gpg_sign"
        fi
    fi
fi
