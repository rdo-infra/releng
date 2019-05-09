from rdopkg.utils.specfile import Spec

import sys

file_path = sys.argv[1]

specfile = Spec(fn=file_path)
new_version = specfile.get_vr().split('-')[0].split(':')[-1]
chnlog_text = ("Update to upstream version %s" % new_version)
specfile.new_changelog_entry('Alfredo Moralejo',
                             'amoralej@redhat.com',
                             changes=[chnlog_text])
specfile.save()
