"""Read-only Jekyll source auditor. No Jekyll, plugins or repository code is executed."""
import argparse
import csv
import datetime
import fnmatch
import html
import json
import os
import pathlib
import posixpath
import re
from collections import defaultdict, deque
from urllib.parse import unquote, urlsplit

import yaml

VERSION = '1.2'
FIELDS = ['file', 'kind', 'publication', 'usage', 'references']
TEXT_EXTENSIONS = {'.html', '.htm', '.md', '.markdown', '.liquid', '.css', '.scss',
                   '.sass', '.js', '.mjs', '.cjs', '.yml', '.yaml', '.json', '.xml',
                   '.txt', '.svg', '.csv', '.tsv'}
DATA_EXTENSIONS = {'.yml', '.yaml', '.json', '.csv', '.tsv'}
SKIP = {'.git', '_site', 'vendor', 'node_modules', '.jekyll-cache', '.sass-cache'}
PAGE_EXTENSIONS = {'.html', '.htm', '.md', '.markdown', '.xml'}
DEFAULT_EXCLUDES = ['Gemfile', 'Gemfile.lock', 'gemfiles', 'node_modules', 'vendor',
                    '.sass-cache', '.jekyll-cache']


def matches(path, pattern):
    """Directory prefixes plus common Jekyll glob forms, relative to source."""
    pattern = str(pattern).removeprefix('./').rstrip('/')
    if not pattern:
        return True
    candidates = [path] + [str(p) for p in pathlib.PurePosixPath(path).parents if str(p) != '.']
    return any(fnmatch.fnmatchcase(candidate, pattern) or
               (pattern.startswith('**/') and fnmatch.fnmatchcase(candidate, pattern[3:]))
               for candidate in candidates)


def mapping(text):
    value = yaml.safe_load(text) or {}
    if not isinstance(value, dict):
        raise ValueError('Expected a YAML mapping')
    return value


def front_matter(text):
    match = re.match(r'\A\ufeff?---[^\S\n]*\n(.*?)(?m:^(?:---|\.\.\.)[^\S\n]*)(?:\n|$)', text, re.S)
    if not match:
        return {}, text, bool(re.match(r'\A\ufeff?---\s*\n', text))
    try:
        return mapping(match[1]), text[match.end():], False
    except (yaml.YAMLError, ValueError):
        return {}, text[match.end():], True


def strip_comments(text, suffix):
    text = re.sub(r'{%-?\s*comment\s*-?%}.*?{%-?\s*endcomment\s*-?%}', '', text, flags=re.S)
    # Raw blocks render literal text, so only suppress Liquid parsing inside them later.
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    if suffix in {'.css', '.scss', '.sass', '.js', '.mjs', '.cjs'}:
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
        text = re.sub(r'^\s*//.*$', '', text, flags=re.M)
    if suffix in {'.md', '.markdown'}:
        text = re.sub(r'(?m)^(`{3,}|~{3,}).*?\n[\s\S]*?^\1[^\n]*$', '', text)
        text = re.sub(r'`[^`\n]+`', '', text)
    return text


class Auditor:
    def __init__(self, root, today=None):
        self.root = pathlib.Path(root).resolve()
        self.today = today or datetime.datetime.now(datetime.timezone.utc).date()
        self.files = {}
        self.texts = {}
        self.meta = {}
        self.edges = []
        self.graph = defaultdict(set)
        self.unresolved = []
        self.warnings = []
        self.global_unknown = False
        self.config = {}
        self.roots = defaultdict(set)
        self.uncertain = defaultdict(set)
        self.publication = {}
        self.system = set()
        self.source_prefix = ''

    def warn(self, message):
        self.warnings.append(message)

    def inventory(self):
        for directory, dirs, names in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in SKIP and
                             not pathlib.Path(directory, d).is_symlink())
            for name in sorted(names):
                path = pathlib.Path(directory, name)
                if path.is_symlink() or not path.is_file():
                    continue
                key = path.relative_to(self.root).as_posix()
                self.files[key] = path
                if path.suffix.lower() in TEXT_EXTENSIONS:
                    self.texts[key] = path.read_text(encoding='utf-8', errors='replace')
        try:
            self.config = mapping(self.texts.get('_config.yml', ''))
        except (yaml.YAMLError, ValueError) as exc:
            self.warn('Invalid _config.yml; configuration-dependent results are Unknown: ' + str(exc))
            self.global_unknown = True
        source = str(self.config.get('source', ''))
        if source not in ('', '.'):
            candidate = (self.root / source).resolve()
            if candidate == self.root or self.root not in candidate.parents:
                self.warn('Source outside repository is not read; results are Unknown.')
                self.global_unknown = True
            else:
                self.source_prefix = candidate.relative_to(self.root).as_posix() + '/'
        self.dirs = {key: str(self.config.get(key + '_dir', '_' + key)).rstrip('/')
                     for key in ('layouts', 'includes', 'data')}
        for key, value in self.dirs.items():
            if '..' in pathlib.PurePosixPath(value).parts or value.startswith('/'):
                self.warn('Unsupported template directory: ' + key)
                self.global_unknown = True
        self.collections = self.config.get('collections', {})
        if isinstance(self.collections, list):
            self.collections = {str(key): {} for key in self.collections}
        if not isinstance(self.collections, dict):
            self.collections = {}
            self.global_unknown = True
        self.collection_prefix = str(self.config.get('collections_dir', '')).strip('/')
        for name in self.files:
            fm, body, invalid = front_matter(self.texts.get(name, ''))
            local = self.local(name)
            kind = self.role(local)
            self.meta[name] = dict(front=fm, body=body, invalid=invalid, local=local, role=kind)
            if self.is_system(local):
                self.system.add(name)
            values = self.defaults(local, kind) if kind not in ('layouts', 'includes', 'data') else {}
            values.update(fm)
            self.meta[name]['effective'] = values
        self.config_uncertain = self.global_unknown
        for name in self.files:
            self.classify(name)

    def local(self, name):
        if self.source_prefix and not name.startswith(self.source_prefix):
            return None
        return name[len(self.source_prefix):]

    def role(self, local):
        if local is None:
            return 'outside source'
        for key, directory in self.dirs.items():
            if local.startswith(directory + '/'):
                return key
        for role in ('posts', 'drafts', *self.collections):
            prefix = posixpath.join(self.collection_prefix, '_' + role) + '/'
            if local.startswith(prefix):
                return role
        return 'pages'

    @staticmethod
    def is_system(local):
        if local is None:
            return False
        return any(part in {'.DS_Store', 'Thumbs.db', 'desktop.ini', '__MACOSX'} or
                   part.startswith('._') for part in pathlib.PurePosixPath(local).parts)

    def defaults(self, local, role):
        result = {}
        candidates = []
        defaults = self.config.get('defaults', [])
        if not isinstance(defaults, list):
            self.global_unknown = True
            return result
        for index, rule in enumerate(defaults):
            if not isinstance(rule, dict) or not isinstance(rule.get('scope', {}), dict) or not isinstance(rule.get('values', {}), dict):
                self.global_unknown = True
                continue
            scope = rule.get('scope', {})
            path = str(scope.get('path', ''))
            if local is not None and matches(local, path) and scope.get('type', role) == role:
                candidates.append((len(path), bool(scope.get('type')), index, rule.get('values', {})))
        for _, _, _, values in sorted(candidates):
            result.update(values)
        return result

    def excluded(self, local):
        if local is None:
            return True
        include = self.config.get('include', [])
        exclude = self.config.get('exclude', [])
        if not isinstance(include, list) or not isinstance(exclude, list):
            self.global_unknown = True
            return True
        if any(matches(local, pattern) for pattern in include):
            return False
        destination = str(self.config.get('destination', '_site')).strip('/')
        if destination and matches(local, destination):
            return True
        return any(matches(local, pattern) for pattern in DEFAULT_EXCLUDES + exclude)

    def classify(self, name):
        meta = self.meta[name]
        local, role, fm = meta['local'], meta['role'], meta['effective']
        publication = 'Not assessed'
        group = None
        if name in self.system:
            publication = 'System file'
        elif meta['invalid']:
            publication, group = 'Unknown: invalid front matter', 'unknown'
        elif role in ('layouts', 'includes', 'data'):
            publication = 'Not a standalone page'
        elif self.excluded(local):
            publication = 'Excluded / outside source (inferred)'
        elif role == 'drafts':
            publication = 'Draft'
            group = 'potentially_published' if self.config.get('show_drafts') is True else 'draft'
            if group == 'potentially_published' and fm.get('published') is False and self.config.get('unpublished') is not True:
                publication, group = 'Draft, explicitly unpublished', 'unpublished'
        elif fm.get('published') is False:
            publication = 'Explicitly unpublished'
            group = 'potentially_published' if self.config.get('unpublished') is True else 'unpublished'
        else:
            hidden = local is None or any(part.startswith(('.', '_', '#')) or part.endswith('~')
                                         for part in pathlib.PurePosixPath(local).parts)
            document = role in ('posts', *self.collections)
            collection = self.collections.get(role, {}) or {}
            if role in self.collections and not isinstance(collection, dict):
                collection = {}
                self.global_unknown = True
            output = role not in self.collections or collection.get('output') is True
            if document and not output:
                publication, group = 'Collection output disabled (inferred)', 'unpublished'
            elif document or (not hidden and (fm or re.match(r'\A\ufeff?---\s*\n', self.texts.get(name, '')))):
                publication, group = 'Potentially published (not build verified)', 'potentially_published'
            elif not hidden or any(matches(local, pattern) for pattern in self.config.get('include', [])):
                publication = 'Static copy candidate (not build verified)'
                # HTML without front matter is copied, so browser references still matter.
                if pathlib.PurePosixPath(name).suffix.lower() in PAGE_EXTENSIONS:
                    group = 'potentially_published'
        if group == 'potentially_published' and role in self.collections:
            collection = self.collections[role] or {}
            if not isinstance(collection, dict) or collection.get('output') is not True:
                publication, group = 'Collection output disabled (inferred)', 'unpublished'
        if group == 'potentially_published' and role in ('posts', 'drafts', *self.collections):
            date = fm.get('date')
            date_match = re.search(r'(\d{4}-\d\d-\d\d)', str(date or pathlib.PurePosixPath(name).name))
            if date_match:
                try:
                    if datetime.date.fromisoformat(date_match[1]) > self.today and self.config.get('future') is not True:
                        publication, group = 'Future dated (inferred)', 'unpublished'
                except ValueError:
                    publication, group = 'Unknown: invalid date', 'unknown'
        if group == 'potentially_published' and self.config_uncertain:
            publication, group = 'Unknown: configuration could not be resolved', 'unknown'
        self.publication[name] = publication
        if group:
            self.roots[group].add(name)
        meta['group'] = group

    def add_edge(self, source, target, kind, token, line=None):
        if target in self.files and target not in self.system:
            edge = dict(source=source, target=target, kind=kind, expression=token, line=line)
            if edge not in self.edges:
                self.edges.append(edge)
                self.graph[source].add(target)
            return True
        return False

    def unknown(self, source, kind, expression, candidates=(), line=None):
        self.unresolved.append(dict(source=source, kind=kind, expression=expression,
                                    line=line, candidates=sorted(candidates)))
        self.uncertain[source].update(candidates)

    def names_for(self, role):
        return [name for name, meta in self.meta.items() if meta['role'] == role and name not in self.system]

    def resolve_layout(self, source, value):
        if value is None or value is False or value == 'none':
            return
        token = str(value)
        choices = self.names_for('layouts')
        found = [name for name in choices if self.meta[name]['local'][len(self.dirs['layouts']) + 1:].rsplit('.', 1)[0] == token]
        if len(found) == 1:
            self.add_edge(source, found[0], 'layout', token)
        else:
            self.unknown(source, 'layout', token, found or choices)

    def static_path(self, source, token, kind, line=None):
        token = html.unescape(token.strip())
        # Resolve only established URL prefix filters/variables and string literals.
        token = re.sub(r'{{-?\s*[\"\']([^\"\']+)[\"\']\s*\|\s*(?:relative_url|absolute_url)\s*-?}}', r'\1', token)
        token = re.sub(r'{{-?\s*site\.(?:baseurl|url)\s*-?}}', '', token)
        if '{{' in token or '{%' in token or '${' in token or 'var(' in token:
            self.unknown(source, 'dynamic ' + kind, token, self.asset_candidates())
            return
        try:
            url = urlsplit(token)
        except ValueError:
            self.unknown(source, kind, token)
            return
        if url.scheme or url.netloc or not url.path or token.startswith('#'):
            return
        path = unquote(url.path)
        baseurl = str(self.config.get('baseurl', '')).rstrip('/')
        if baseurl and path.startswith(baseurl + '/'):
            path = path[len(baseurl):]
        local = self.meta[source]['local'] or source
        if path.startswith('/'):
            target = self.source_prefix + posixpath.normpath(path).lstrip('/')
        else:
            target = self.source_prefix + posixpath.normpath(posixpath.join(posixpath.dirname(local), path))
        if target.startswith('../'):
            self.unknown(source, kind, token)
            return
        if not path.startswith('/') and (self.meta[source]['role'] in ('layouts', 'includes', 'posts', 'drafts') or self.meta[source]['effective'].get('permalink')):
            candidates = [name for name in self.asset_candidates() if name.endswith('/' + path) or name == path or name == target]
            self.unknown(source, 'relative output URL', token, candidates, line)
            return
        if self.add_edge(source, target, kind, token, line):
            return
        # Liquid templates and Markdown URLs resolve against generated page URLs.
        # Relative paths cannot be proven against the template's source directory.
        if not path.startswith('/') and self.meta[source]['role'] in ('layouts', 'includes', 'posts', 'drafts', 'pages'):
            candidates = [name for name in self.asset_candidates() if name.endswith('/' + path) or name == path]
            if candidates:
                self.unknown(source, 'relative output URL', token, candidates, line)
                return
        # Sass partial and extension resolution.
        if kind == 'style import':
            parent, leaf = posixpath.split(path)
            candidates = []
            sass = self.config.get('sass', {})
            sass_dir = sass.get('sass_dir', '_sass') if isinstance(sass, dict) else '_sass'
            for directory in (posixpath.dirname(local), str(sass_dir)):
                for stem in (leaf, '_' + leaf):
                    for extension in ('', '.scss', '.sass', '.css'):
                        candidate = self.source_prefix + posixpath.normpath(posixpath.join(directory, parent, stem + extension))
                        if candidate in self.files:
                            candidates.append(candidate)
            if len(set(candidates)) == 1:
                self.add_edge(source, candidates[0], kind, token, line)
                return
            if candidates:
                self.unknown(source, kind, token, candidates, line)
                return
        # No guessed permalink-to-source edges. Keep missing URLs as diagnostics.
        self.unknown(source, 'unresolved ' + kind, token, (), line)

    def asset_candidates(self):
        return [name for name, meta in self.meta.items() if meta['role'] not in ('layouts', 'includes', 'data') and name not in self.system]

    def parse_dependencies(self):
        for source, meta in self.meta.items():
            if source in self.system or meta['role'] == 'outside source':
                continue
            local = meta['local'] or source
            if local.startswith(('.github/', 'tests/', '.vscode/')) or local in ('_config.yml', 'scripts/jekyll-audit.py'):
                continue
            suffix = pathlib.PurePosixPath(source).suffix.lower()
            text = strip_comments(meta['body'], suffix)
            if 'layout' in meta['effective'] and meta['role'] in ('layouts', 'posts', 'drafts', 'pages', *self.collections):
                self.resolve_layout(source, meta['effective']['layout'])
            liquid = re.sub(r'{%-?\s*comment\s*-?%}.*?{%-?\s*endcomment\s*-?%}', '', meta['body'], flags=re.S)
            liquid = re.sub(r'{%-?\s*raw\s*-?%}.*?{%-?\s*endraw\s*-?%}', '', liquid, flags=re.S)
            if meta['role'] == 'data':
                liquid = ''
            for match in re.finditer(r'{%-?\s*(include_relative|include)\s+(.*?)\s*-?%}', liquid, re.S):
                kind, expression = match[1], match[2]
                literal = re.match(r'([\"\'])(.*?)\1(?:\s|$)|([^\s]+)', expression)
                token = (literal[2] if literal and literal[1] else literal[3] if literal else '')
                choices = self.names_for('includes') if kind == 'include' else self.asset_candidates()
                if not token or '{{' in token or '{%' in token or token.startswith(('page.', 'include.', 'site.')):
                    self.unknown(source, 'dynamic ' + kind, expression, choices)
                    continue
                if '..' in pathlib.PurePosixPath(token).parts or token.startswith('/'):
                    self.unknown(source, 'invalid ' + kind, expression)
                    continue
                directory = self.dirs['includes'] if kind == 'include' else posixpath.dirname(local)
                target = self.source_prefix + posixpath.join(directory, token)
                if not self.add_edge(source, target, kind, expression):
                    self.unknown(source, kind, expression)
            # Parse data expressions only inside Liquid output/tag expressions.
            for block in re.findall(r'{{.*?}}|{%.*?%}', liquid, re.S):
                for match in re.finditer(r'\bsite\.data\b((?:\.[\w-]+|\s*\[[^\]]+\])*)', block):
                    expression = match[0]
                    keys = []
                    dynamic = False
                    for part in re.finditer(r'\.([\w-]+)|\[\s*([^\]]+)\s*\]', match[1]):
                        if part[1]:
                            keys.append(part[1])
                        elif re.fullmatch(r'([\"\']).*\1', part[2].strip()):
                            keys.append(part[2].strip()[1:-1])
                        else:
                            dynamic = True
                            break
                    candidates = []
                    for name in self.names_for('data'):
                        if pathlib.PurePosixPath(name).suffix.lower() not in DATA_EXTENSIONS:
                            continue
                        data_key = self.meta[name]['local'][len(self.dirs['data']) + 1:].rsplit('.', 1)[0].split('/')
                        if keys[:len(data_key)] == data_key or data_key[:len(keys)] == keys:
                            candidates.append(name)
                    if dynamic:
                        exact_files = [name for name in candidates if len(keys) >= len(self.meta[name]['local'][len(self.dirs['data']) + 1:].rsplit('.', 1)[0].split('/'))]
                        for target in exact_files:
                            self.add_edge(source, target, 'site.data static file / dynamic key', expression)
                        self.unknown(source, 'dynamic data', expression, [name for name in candidates if name not in exact_files])
                    else:
                        for target in candidates:
                            self.add_edge(source, target, 'site.data', expression)
                        if not candidates:
                            self.unknown(source, 'site.data', expression)
            for match in re.finditer(r'\b(?:src|href|poster|data-src|action)\s*=\s*([\"\'])(.*?)\1', text, re.S | re.I):
                self.static_path(source, match[2], 'HTML attribute')
            for match in re.finditer(r'\bsrcset\s*=\s*([\"\'])(.*?)\1', text, re.S | re.I):
                if '{{' in match[2] or match[2].lstrip().startswith('data:'):
                    self.unknown(source, 'dynamic srcset', match[2], self.asset_candidates())
                else:
                    for item in match[2].split(','):
                        if item.strip():
                            self.static_path(source, item.strip().split()[0], 'srcset')
            for match in re.finditer(r'url\(\s*([\"\']?)(.*?)\1\s*\)', text, re.I):
                self.static_path(source, match[2], 'CSS URL')
            for match in re.finditer(r'@(?:import|use|forward)\s+([\"\'])(.*?)\1', text):
                if not match[2].startswith('sass:'):
                    self.static_path(source, match[2], 'style import')
            if suffix in {'.md', '.markdown'}:
                for match in re.finditer(r'!?\[[^\]]*\]\(\s*([^\s)]+)', text):
                    self.static_path(source, match[1].strip('<>'), 'Markdown URL')
                for match in re.finditer(r'^\s*\[[^\]]+\]:\s*<?([^\s>]+)', text, re.M):
                    self.static_path(source, match[1], 'Markdown reference URL')
            if suffix in {'.js', '.mjs', '.cjs', '.html', '.htm', '.liquid'}:
                patterns = [r'\b(?:fetch|import|require|Worker)\s*\(\s*([\"\'`])(.*?)\1',
                            r'\bfrom\s+([\"\'])(.*?)\1',
                            r'\bimport\s+([\"\'])(.*?)\1',
                            r'\bnew\s+URL\s*\(\s*([\"\'`])(.*?)\1',
                            r'\.(?:src|href)\s*=\s*([\"\'`])(.*?)\1']
                for pattern in patterns:
                    for match in re.finditer(pattern, text, re.S):
                        remainder = text[match.end():].lstrip()
                        if remainder.startswith('+'):
                            self.unknown(source, 'dynamic JavaScript URL', match[0] + ' + …', self.asset_candidates())
                        else:
                            self.static_path(source, match[2], 'JavaScript URL')
                for match in re.finditer(r'\b(?:fetch|import|require|Worker)\s*\(\s*(?![\s\"\'`])[^)]+\)', text):
                    self.unknown(source, 'dynamic JavaScript URL', match[0], self.asset_candidates())
            # Front matter/data strings can feed dynamic URL attributes at render time.
            # Keep them as uncertain evidence rather than asserting rendered use.
            if meta['front'] or meta['role'] == 'data':
                for match in re.finditer(r'[\"\']?(/(?:assets|images|media)/[^\s\"\'<>\]}]+)', self.texts.get(source, '')):
                    target = self.source_prefix + match[1].split('?', 1)[0].lstrip('/')
                    if target in self.files:
                        self.unknown(source, 'data/front matter URL value', match[1], [target])

    def walk(self, starts):
        reached = set(starts)
        queue = deque(sorted(starts))
        while queue:
            source = queue.popleft()
            for target in sorted(self.graph[source]):
                if target not in reached:
                    reached.add(target)
                    queue.append(target)
        return reached

    def cycles(self):
        # Iterative DFS supports long dependency chains and cycles without recursion.
        colors = {}
        cycles = []
        for start in sorted(self.files):
            if colors.get(start):
                continue
            colors[start] = 1
            path = [start]
            positions = {start: 0}
            stack = [iter(sorted(self.graph[start]))]
            while stack:
                target = next(stack[-1], None)
                if target is None:
                    colors[path[-1]] = 2
                    positions.pop(path.pop())
                    stack.pop()
                elif colors.get(target) == 1:
                    cycles.append(path[positions[target]:] + [target])
                elif not colors.get(target):
                    colors[target] = 1
                    positions[target] = len(path)
                    path.append(target)
                    stack.append(iter(sorted(self.graph[target])))
        return cycles

    def run(self):
        self.inventory()
        self.parse_dependencies()
        reach = {group: self.walk(self.roots[group]) for group in
                 ('potentially_published', 'draft', 'unpublished', 'unknown')}
        uncertain_starts = set(reach['unknown'])
        # Unknown references from reachable uncertain candidates propagate to a fixpoint.
        known_reach = set().union(*reach.values())
        while True:
            candidates = set().union(*(self.uncertain[source] for source in known_reach | uncertain_starts))
            expanded = self.walk(uncertain_starts | candidates)
            if expanded == uncertain_starts:
                break
            uncertain_starts = expanded
        if self.config.get('plugins') or self.config.get('theme') or self.config.get('remote_theme'):
            self.global_unknown = True
            self.warn('Plugins/theme may supply or generate dependencies; unreachable files are Unknown.')
        if self.global_unknown:
            uncertain_starts.update(self.files)
        inbound = defaultdict(set)
        for edge in self.edges:
            inbound[edge['target']].add(edge['source'])
        rows = []
        evidence = {}
        for name in sorted(self.files):
            if name in self.system:
                usage = 'System file'
            elif name in reach['potentially_published']:
                usage = 'Active'
            elif name in uncertain_starts:
                usage = 'Unknown'
            elif name in reach['draft'] and name in reach['unpublished']:
                usage = 'Draft and unpublished only'
            elif name in reach['draft']:
                usage = 'Draft only'
            elif name in reach['unpublished']:
                usage = 'Unpublished only'
            elif self.meta[name]['role'] in ('layouts', 'includes', 'data') or self.files[name].suffix.lower() in TEXT_EXTENSIONS or (self.meta[name]['local'] or name).startswith(('assets/', 'images/', 'media/')) or self.publication[name].startswith('Static copy'):
                usage = 'Potentially unused'
            else:
                usage = 'Not assessed'
            local = self.meta[name]['local'] or name
            if local.startswith(('.github/', 'scripts/', 'tests/', '.vscode/')) or local in ('_config.yml', 'Gemfile', 'Gemfile.lock'):
                if usage == 'Potentially unused':
                    usage = 'Not assessed'
            rows.append(dict(file=name, kind=name.split('/')[0] if '/' in name else 'root',
                             publication=self.publication[name], usage=usage,
                             references='; '.join(sorted(inbound[name]))))
            evidence[name] = dict(roots=[group for group in self.roots if name in self.roots[group]],
                                  reachable_from=[group for group in reach if name in reach[group]],
                                  uncertain=name in uncertain_starts,
                                  effective_front_matter=self.meta[name]['effective'])
        details = dict(version=VERSION, analysis='static inference',
                       build_verification=dict(performed=False, result='not run'),
                       source=self.source_prefix or '.', as_of=str(self.today),
                       edges=self.edges, unresolved=self.unresolved, cycles=self.cycles(),
                       warnings=self.warnings, evidence=evidence,
                       limitations=[
                           'Active means static reachability from potentially published roots, not verified live use.',
                           'Liquid conditions and loops are not executed; dependencies in branches are conservative.',
                           'Ruby/Jekyll plugins, themes, generated pages and build outputs are not executed or verified.',
                           'Only _config.yml is loaded. Environment/CLI overrides and additional config files are not inferred.',
                           'Common globs/default scopes are approximated; Ruby glob edge cases and deep default merges may differ.',
                           'Relative generated URLs, permalinks, dynamic expressions and bundlers can remain unresolved.',
                           'Symlinks and generated/dependency directories are skipped; no deletion is recommended.'])
        return rows, details
def render_report(rows, target, label):
 from collections import Counter
 e=lambda s: html.escape(str(s), quote=True)
 kinds=sorted({r['kind'] for r in rows}); pubs=sorted({r['publication'] for r in rows}); usages=sorted({r['usage'] for r in rows})
 def options(values): return '<option value="">All</option>'+''.join(f'<option>{e(v)}</option>' for v in values)
 counts=Counter(r['usage'] for r in rows)
 stats=[('Total files',len(rows)),('Active (inferred)',counts['Active']),('Needs review',counts['Potentially unused']),('Unknown',counts['Unknown'])]
 cards=''.join(f'<div class="metric"><span>{e(k)}</span><strong>{v:,}</strong></div>' for k,v in stats)
 body=[]
 for r in rows:
  refs=[x for x in r['references'].split('; ') if x]; detail=(f'<details><summary>{len(refs)} source files</summary><ul>'+''.join(f'<li>{e(x)}</li>' for x in refs)+'</ul></details>') if refs else '—'
  body.append(f'<tr data-kind="{e(r["kind"])}" data-pub="{e(r["publication"])}" data-use="{e(r["usage"])}"><td data-label="File" class="filename">{e(r["file"])}</td><td data-label="Folder">{e(r["kind"])}</td><td data-label="Publication">{e(r["publication"])}</td><td data-label="Usage">{e(r["usage"])}</td><td data-label="References">{detail}</td></tr>')
 page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Jekyll Site Auditor</title><style>
 *{box-sizing:border-box}body{margin:0;background:#f5f4f0;color:#202321;font:14px/1.5 system-ui,-apple-system,sans-serif}main{max-width:1240px;margin:auto;padding:24px}h1{font-size:28px;margin:0}p{color:#525953} .metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:24px 0}.metric{background:white;border:1px solid #d8ddd8;border-radius:10px;padding:16px}.metric span{display:block;color:#59645e}.metric strong{font-size:28px;display:block}.filters{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:10px;margin:16px 0}label{display:block;font-weight:600;min-width:0}input,select{display:block;width:100%;min-width:0;font:inherit;padding:10px;border:1px solid #aeb8b0;border-radius:6px;background:white;color:#202321}table{width:100%;table-layout:fixed;border-collapse:collapse;background:white}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #dfe3df;overflow-wrap:anywhere}th{background:#e7ebe6}th:first-child{width:32%}th:nth-child(2){width:12%}th:nth-child(5){width:18%}summary{cursor:pointer;color:#365e4b}ul{padding-left:18px;margin:6px 0}li{margin-bottom:5px}tr[hidden]{display:none!important}button{font:inherit;padding:7px 12px;border:1px solid #aeb8b0;border-radius:6px;background:white;color:#202321;cursor:pointer} .bar{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:12px 0} @media(max-width:760px){main{padding:16px}.metrics,.filters{grid-template-columns:repeat(2,minmax(0,1fr))}.metric{padding:12px}.metric strong{font-size:23px}table,tbody,tr,td{display:block;width:100%}thead{display:none}tr{padding:12px;margin-bottom:10px;border:1px solid #d8ddd8;border-radius:8px;background:white}td{padding:4px 0;border:0}td:before{content:attr(data-label) ": ";font-weight:600;color:#59645e}.filename{font-weight:600}.filename:before{display:none}details{display:inline-block;max-width:100%}}
 </style></head><body><main><h1>Jekyll Site Auditor</h1><p>VERSION 1.2 · LABEL · Read-only static analysis</p><p>Build verification: not performed. Active means reachable from potentially published content by static inference. Review audit-details.json for evidence, unresolved references and limitations. Potentially unused is a review candidate, never a deletion recommendation.</p><div class="metrics">CARDS</div><div class="filters"><label>Search<input id="q" type="search" placeholder="File or reference"></label><label>Folder<select id="kind">KINDS</select></label><label>Publication<select id="pub">PUBS</select></label><label>Usage<select id="use">USES</select></label></div><div class="bar"><span id="count" aria-live="polite">TOTAL files</span><button id="reset" type="button">Reset filters</button></div><table><thead><tr><th>File</th><th>Folder</th><th>Publication</th><th>Usage</th><th>References</th></tr></thead><tbody>ROWS</tbody></table></main><script>
 (function(){var q=document.getElementById('q'),k=document.getElementById('kind'),p=document.getElementById('pub'),u=document.getElementById('use'),rows=Array.from(document.querySelectorAll('tbody tr'));function filter(){var n=0,term=q.value.trim().toLowerCase();rows.forEach(function(r){var show=(!k.value||r.dataset.kind===k.value)&&(!p.value||r.dataset.pub===p.value)&&(!u.value||r.dataset.use===u.value)&&(!term||r.textContent.toLowerCase().indexOf(term)!==-1);r.hidden=!show;if(show)n++;});document.getElementById('count').textContent=n.toLocaleString()+' of '+rows.length.toLocaleString()+' files';}[q,k,p,u].forEach(function(x){x.addEventListener('input',filter);x.addEventListener('change',filter);});document.getElementById('reset').addEventListener('click',function(){[q,k,p,u].forEach(function(x){x.value='';});filter();});filter();})();</script></body></html>'''
 replacements={'LABEL':e(label),'CARDS':cards,'KINDS':options(kinds),'PUBS':options(pubs),'USES':options(usages),'TOTAL':str(len(rows)),'ROWS':''.join(body)}
 page=re.sub(r'\b(?:LABEL|CARDS|KINDS|PUBS|USES|TOTAL|ROWS)\b',lambda m: replacements[m.group()],page)
 target.write_text(page,encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root = pathlib.Path(args.root).resolve()
    output = pathlib.Path(args.output).resolve()
    if not root.is_dir():
        parser.error('Root must be an existing directory')
    if output == root or root in output.parents:
        parser.error('Output must be outside repository')
    auditor = Auditor(root)
    rows, details = auditor.run()
    for filename in ('audit.json', 'audit.csv', 'audit.html', 'audit-details.json'):
        if (output / filename).is_symlink() or ((output / filename).exists() and (output / filename).stat().st_nlink > 1):
            parser.error('Report destination must not be a symbolic or hard link')
    output.mkdir(parents=True, exist_ok=True)
    # Keep the original list schema and CSV columns for existing consumers.
    (output / 'audit.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    with (output / 'audit.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (output / 'audit-details.json').write_text(json.dumps(details, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    render_report(rows, output / 'audit.html', os.environ.get('GITHUB_REPOSITORY', root.name))
    print(f'Jekyll Site Auditor {VERSION}: {len(rows)} files. Static inference; build verification not performed.')


if __name__ == '__main__':
    main()
