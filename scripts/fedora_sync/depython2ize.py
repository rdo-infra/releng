#!/usr/bin/python3

import argparse
import json
import os
import pathlib
import subprocess
import re
import collections
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('-d', '--diff', action='store_true')
parser.add_argument('--debug', action='store_true')
parser.add_argument('-U', type=int, default=3)
parser.add_argument('-b', '--bumpspec', action='store_true')
parser.add_argument('-c', '--commit', action='store_true')
parser.add_argument('-u', '--user')
parser.add_argument('-w', '--write', action='store_true')
parser.add_argument('-r', '--results', action='store')
parser.add_argument('-p', '--package', help='Overwrite package name')
parser.add_argument('--remove-with-python2', type=int, default=1)
parser.add_argument('--remove-with-python3', type=int, default=1)
parser.add_argument('--remove-sections', type=int, default=1)
parser.add_argument('--remove-requires', type=int, default=1)
parser.add_argument('--remove-py3dir', type=int, default=1)
parser.add_argument('--remove-pushd2', type=int, default=1)
parser.add_argument('--remove-python-calls', type=int, default=1)
parser.add_argument('--remove-empty-ifs', type=int, default=1)
parser.add_argument('dirname', type=pathlib.Path, nargs='+')
opts = parser.parse_args()

def resolve_macro(specfile, macro):
    f = tempfile.NamedTemporaryFile(prefix=specfile.stem, suffix='.spec', mode='w+t', delete=False)
    f.write(specfile.read_text())
    f.write(f'\nMACRO: {macro}')
    f.flush()
    out = subprocess.check_output(['rpmspec', '-P', f.name], universal_newlines=True)
    blah = out.splitlines()[-1]
    assert blah.startswith('MACRO: ')
    return blah[7:]

def is_requires(type, pattern, line):
    return re.match(rf'{type}:\s*.*({pattern})', line) is not None

def split_reqs(line):
    start = 0
    k = 0
    macros = []
    for end in range(0, len(line)):
        if line[end] == '}':
            macros.pop()
        elif line[end:].startswith('%{'):
            macros.append(end)
        elif not macros and line[end] in ' \t':
            if line[end-1] in '<>=':
                continue
            next = line[end+1:].lstrip()
            if next and next[0] in '<>=':
                continue
            x = line[start:end].strip().rstrip(',')
            yield x
            start = end
    if line[start:].strip():
        yield line[start:].strip()

def reqcleanup(pattern1, pattern2, preservepattern, line):
    # This little dance is done to preserve the indentation
    m = re.match(f'^((?:{pattern1}):\s*)(.+)$', line)
    assert m
    lhs, rhs = m.groups()
    rhs = split_reqs(rhs)

    good = []
    for x in rhs:
        if re.match(preservepattern, x):
            good.append(x.replace('python2', 'python3').replace('python-', 'python3-').replace('py2_dist', 'py3_dist'))
        elif not re.match(pattern2, x):
            good.append(x)
    return [f'{lhs}{x}' for x in good]

def produced_packages(dirname, specfile):
    command = ['rpm', '--define', f'_sourcedir {dirname}',
               '--define', 'dist .fc30', '-q', '--qf', '%{NAME}\n',
               '--specfile', f'{specfile}']
    output = subprocess.check_output(command, universal_newlines=True)
    return set(output.splitlines())

def dprint(*args, **kwargs):
    if opts.debug:
        print(*args, **kwargs)

def remove_with_python(lines, *, v):
    assert v in {2,3}
    define = None
    nesting = []
    under_ours_if = False
    for k in range(len(lines)):
        m = re.match(f'^(%global\s+with_python{v}\s+1|%bcond(?:\s+|_)with(?:out)?\s+python{v})\s*$', lines[k])
        if m:
            if define:
                print('GOT SECOND DEFINE, IGNORING:', lines[k])
            else:
                define = m.group(1)
            continue
        m = re.match('^%if\s*(.*?)\s*$', lines[k])
        if m:
            cond = m.group(1)
            ours = re.match(f'^(0?%{{\??with_python{v}}}|%{{with\s+python{v}}})$', cond)
            nesting.append(cond if ours else False)
            if not nesting[-1]:
                yield lines[k]
            if nesting[-1]:
                under_ours_if = True
            continue
        m = re.match('^%else', lines[k])
        if m:
            assert(nesting)
            if not nesting[-1]:
                yield lines[k]
            if nesting[-1]:
                under_ours_if = False
            continue
        m = re.match('^%endif', lines[k])
        if m:
            if not nesting:
                print(f'NESTING ERROR: line {k}: {lines[k]}')
            else:
                if not nesting[-1]:
                    yield lines[k]
                nesting.pop()
                under_ours_if = bool(nesting and nesting[-1])
            continue
        # remove everything under %if 2 ... %else|%endif
        if v == 3 or not under_ours_if:
            yield lines[k]

def remove_sections(package, lines):
    " delete sections "
    def python_package_pattern(stanza):
        if package:
            return fr'%({stanza})\s+-n\s+{package}'
        else:
            return fr'%({stanza})$'

    sections = 'files|pre|post|preun|postun'
    if package:
        sections += '|package|description'
    start = python_package_pattern(sections)
    stop = fr'%({sections}|package|description|prep|build|install|changelog|check)'

    do_delete = []
    del_start = None
    if_start = None
    for j in range(len(lines)):
        dprint('--', lines[j])
        if not del_start and not if_start and re.match(start, lines[j]):
            dprint('match start')
            del_start = j

        elif del_start and not if_start and re.match('%if ', lines[j]):
            dprint('match if')
            if_start = j

        elif if_start and re.match(r'%endif', lines[j]):
            dprint('match endif')
            if_start = None

        if del_start and re.match(stop, lines[j+1]):
            dprint('match end')
            del_stop = if_start if if_start else j + 1
            do_delete.append(slice(del_start, del_stop))
            del_start = None
    assert del_start is None

    for nums in reversed(do_delete):
        dprint(nums)
        del lines[nums]

    return lines

for dirname in opts.dirname:
    if dirname.name.endswith('.spec'):
        dirname = dirname.parent

    specfile, = dirname.glob('*.spec')

    print(f'==== {specfile}')
    try:
        old_packages = produced_packages(dirname, specfile)
    except subprocess.CalledProcessError:
        print('CANNOT PARSE SPEC')
        continue

    new = pathlib.Path(f'{specfile}.tmp')
    try:
        # remove .tmp file to not leave obsolete stuff in case we bail out
        os.unlink(new)
    except FileNotFoundError:
        pass

    name = dirname.name
    if name != specfile.stem:
        print('BAD SPEC FILE NAME')

    with open(specfile, 'rt') as f:
        lines = f.readlines()
    lines = [line.rstrip('\n') for line in lines]

    # find name of python2 subpackage
    if opts.package is not None:
        package = opts.package
    else:
        for j,line in enumerate(lines):
            m = re.match('%package\s+-n\s+(python2?-.+?)\s*$', lines[j])
            if m:
                package = m.group(1)
                print(f'python2 subpackage is {package!r}')
                python2_package_line = j
                break
        else:
            print('cannot figure out python2 subpackage name')
            continue

    if opts.remove_with_python2:
        lines = list(remove_with_python(lines, v=2))

    if opts.remove_with_python3:
        lines = list(remove_with_python(lines, v=3))

    if opts.remove_sections:
        lines = remove_sections(package, lines)

    if opts.remove_python_calls:
        # try to fixup stuff like '%{__python} setup.py build_doc|build_sphinx'
        for k in range(len(lines)):
            m = re.match('(.*?%{?)__python2?(}?\s+.*(?:doc|sphinx).*?)\s*$', lines[k])
            if m:
                lines[k] = f'{m.group(1)}__python3{m.group(2)}'

    if opts.remove_requires:
        uglypatterns = r'%{?__python2?}?\b|py2_build|py2_install|(py\.?test|nosetests)-(2|%{python2_version})|(%{?__python2}?|python2) setup.py|cd\b.*%{?python2?_sitearch}?'

        # remove BuildRequires|Requires: python2-|python-
        just_removed = False
        for k in reversed(range(len(lines))):
            reqpattern1 = 'BuildRequires|Requires'
            reqpattern2 = 'python2?-.+|python2dist\(.*\)|%{py2_dist.*}'
            preservepattern = 'python2?-sphinx\w*|python2dist\(sphinx\w*\)|%{py2_dist sphinx}|python-.*-lang|python-.*-doc'
            if is_requires(reqpattern1, reqpattern2, lines[k]):
                repl = reqcleanup(reqpattern1, reqpattern2, preservepattern, lines[k])
                lines[k:k+1] = repl
                just_removed = not repl
            elif re.search(uglypatterns, lines[k]):
                del lines[k]
                just_removed = True
            elif just_removed and lines[k].startswith('#'):
                del lines[k]
                just_removed = True
            else:
                # remove empty lines
                if just_removed and not lines[k].strip() and not lines[k+1].strip():
                    del lines[k]
                just_removed = False

    if opts.remove_py3dir:
        popd_line = None
        for k in reversed(range(len(lines))):
            if re.match('find.*%{?py3dir}?', lines[k]):
                lines[k] = re.sub('%{?py3dir}?', '.', lines[k])
            elif not popd_line and re.search('%{?py3dir}?', lines[k]):
                assert 'pushd' not in lines[k]
                # just nuke everthing with that variable, hopefully what remains will make sense
                del lines[k]
            elif popd_line and re.search('pushd\s+%{?py3dir}?', lines[k]):
                del lines[popd_line]
                del lines[k]
                popd_line = None
            elif not popd_line and 'popd' in lines[k]:
                popd_line = k

    if opts.remove_pushd2:
        popd_line = None
        for k in reversed(range(len(lines))):
            if popd_line:
                if re.search(r'pushd\b.*%{?python2?_sitelib}?|^pushd\s+python2\s*$', lines[k]):
                    del lines[k:popd_line+1]
                popd_line = None
            elif not popd_line and 'popd' in lines[k]:
                popd_line = k

    # remove empty if blocks
    if opts.remove_empty_ifs:
        endif_line = None
        for k in reversed(range(len(lines))):
            if not endif_line and re.match(r'%endif', lines[k]):
                endif_line = k
            elif endif_line and re.match(r'%else', lines[k]):
                if endif_line-k == 1:
                    del lines[k]
                endif_line -= 1
            elif endif_line and re.match(r'%if\s', lines[k]):
                if endif_line-k == 1:
                    del lines[k:k+2]
                endif_line = None

    # write stuff out and diff
    with open(new, 'wt') as out:
        print('\n'.join(lines), file=out)

    try:
        new_packages = produced_packages(dirname, new)
    except subprocess.CalledProcessError:
        print('CANNOT PARSE SPEC')
        ok = False
    else:
        removed_packages = old_packages - new_packages
        print('Removed packages:', ', '.join(sorted(removed_packages)))

        ok = True
        if opts.results:
            with open(opts.results) as f:
                results = json.load(f)
            for pkg in removed_packages:
                if pkg not in results or results[pkg]['verdict'] != 'drop_now':
                    print(f'CANNOT REMOVE {pkg}')
                    ok = False
                    continue

    if ok:
        removed = ', '.join(sorted(removed_packages))
        one = len(removed_packages) == 1
        COMMENT = (f'Subpackage{"" if one else "s"} {removed} {"has" if one else "have"} been removed\n'
                   '  See https://fedoraproject.org/wiki/Changes/Mass_Python_2_Package_Removal')

        if opts.bumpspec:
            cmd = ['rpmdev-bumpspec', '-c', COMMENT, new]
            if opts.user:
                cmd += ['-u', opts.user]
            subprocess.check_call(cmd)

    if opts.diff:
        subprocess.call(['git', 'diff', f'-U{opts.U}', '--no-index', specfile, new])

    if not ok:
        continue

    if opts.write:
        new.rename(specfile)

    if opts.commit:
        subprocess.check_call(['git',
                               f'--git-dir={dirname}/.git',
                               f'--work-tree={dirname}/',
                               'commit', '-a',
                               '-m', COMMENT.split('\n')[0]])
