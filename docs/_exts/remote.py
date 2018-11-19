import urllib

from docutils import nodes, utils
from docutils.parsers.rst import Directive, directives
from docutils.statemachine import ViewList

from six import string_types

from sphinx.locale import _
from sphinx.util import parselinenos
from sphinx.util.nodes import set_source_info

from string import split, strip

def dedent_lines(lines, dedent):
    if not dedent:
        return lines

    new_lines = []
    for line in lines:
        new_line = line[dedent:]
        if line.endswith('\n') and not new_line:
            new_line = '\n'  # keep CRLF
        new_lines.append(new_line)

    return new_lines


def container_wrapper(directive, literal_node, caption):
    container_node = nodes.container('', literal_block=True,
                                     classes=['literal-block-wrapper'])
    parsed = nodes.Element()
    directive.state.nested_parse(ViewList([caption], source=''),
                                 directive.content_offset, parsed)
    if isinstance(parsed[0], nodes.system_message):
        raise ValueError(parsed[0])
    caption_node = nodes.caption(parsed[0].rawsource, '',
                                 *parsed[0].children)
    caption_node.source = literal_node.source
    caption_node.line = literal_node.line
    container_node += caption_node
    container_node += literal_node
    return container_node

class RemoteInclude(Directive):
    """
    Cut-n-paste of LiteralInclude from sphinx 1.5.5; the argument is a URI instead of a local file name.
    Removed the diff and pyobject options.
    """

    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {
        'dedent': int,
        'linenos': directives.flag,
        'lineno-start': int,
        'lineno-match': directives.flag,
        'tab-width': int,
        'language': directives.unchanged_required,
        'encoding': directives.encoding,
        'lines': directives.unchanged_required,
        'start-after': directives.unchanged_required,
        'end-before': directives.unchanged_required,
        'start-at': directives.unchanged_required,
        'end-at': directives.unchanged_required,
        'prepend': directives.unchanged_required,
        'append': directives.unchanged_required,
        'emphasize-lines': directives.unchanged_required,
        'caption': directives.unchanged,
        'class': directives.class_option,
        'name': directives.unchanged
    }

    def read_uri(self, uri, document):

        print "Pulling source content from " + uri

        try:
                f = urllib.urlopen(uri)
                lines = f.readlines()
                lines = dedent_lines(lines, self.options.get('dedent'))
                return lines
        except (IOError, OSError):
            return [document.reporter.warning(
                'Include resource %r not found or reading it failed' % uri,
                line=self.lineno)]

    def run(self):
        document = self.state.document
        if not document.settings.file_insertion_enabled:
            return [document.reporter.warning('File insertion disabled',
                                              line=self.lineno)]
        uri =self.arguments[0]

        if 'pyobject' in self.options and 'lines' in self.options:
            return [document.reporter.warning(
                'Cannot use both "pyobject" and "lines" options',
                line=self.lineno)]

        if 'lineno-match' in self.options and 'lineno-start' in self.options:
            return [document.reporter.warning(
                'Cannot use both "lineno-match" and "lineno-start"',
                line=self.lineno)]

        if 'lineno-match' in self.options and \
                (set(['append', 'prepend']) & set(self.options.keys())):
            return [document.reporter.warning(
                'Cannot use "lineno-match" and "append" or "prepend"',
                line=self.lineno)]

        if 'start-after' in self.options and 'start-at' in self.options:
            return [document.reporter.warning(
                'Cannot use both "start-after" and "start-at" options',
                line=self.lineno)]

        if 'end-before' in self.options and 'end-at' in self.options:
            return [document.reporter.warning(
                'Cannot use both "end-before" and "end-at" options',
                line=self.lineno)]

        lines = self.read_uri(uri, document)
        if lines and not isinstance(lines[0], string_types):
            return lines

        linenostart = self.options.get('lineno-start', 1)

        linespec = self.options.get('lines')
        if linespec:
            try:
                linelist = parselinenos(linespec, len(lines))
            except ValueError as err:
                return [document.reporter.warning(str(err), line=self.lineno)]

            if 'lineno-match' in self.options:
                # make sure the line list is not "disjoint".
                previous = linelist[0]
                for line_number in linelist[1:]:
                    if line_number == previous + 1:
                        previous = line_number
                        continue
                    return [document.reporter.warning(
                        'Cannot use "lineno-match" with a disjoint set of '
                        '"lines"', line=self.lineno)]
                linenostart = linelist[0] + 1
            # just ignore non-existing lines
            lines = [lines[i] for i in linelist if i < len(lines)]
            if not lines:
                return [document.reporter.warning(
                    'Line spec %r: no lines pulled from resource %r' %
                    (linespec, uri), line=self.lineno)]

        linespec = self.options.get('emphasize-lines')
        if linespec:
            try:
                hl_lines = [x + 1 for x in parselinenos(linespec, len(lines))]
            except ValueError as err:
                return [document.reporter.warning(str(err), line=self.lineno)]
        else:
            hl_lines = None

        start_str = self.options.get('start-after')
        start_inclusive = False
        if self.options.get('start-at') is not None:
            start_str = self.options.get('start-at')
            start_inclusive = True
        end_str = self.options.get('end-before')
        end_inclusive = False
        if self.options.get('end-at') is not None:
            end_str = self.options.get('end-at')
            end_inclusive = True
        if start_str is not None or end_str is not None:
            use = not start_str
            res = []
            for line_number, line in enumerate(lines):
                if not use and start_str and start_str in line:
                    if 'lineno-match' in self.options:
                        linenostart += line_number + 1
                    use = True
                    if start_inclusive:
                        res.append(line)
                elif use and end_str and end_str in line:
                    if end_inclusive:
                        res.append(line)
                    break
                elif use:
                    res.append(line)
            lines = res

        prepend = self.options.get('prepend')
        if prepend:
            lines.insert(0, prepend + '\n')

        append = self.options.get('append')
        if append:
            lines.append(append + '\n')

        text = ''.join(lines)
        if self.options.get('tab-width'):
            text = text.expandtabs(self.options['tab-width'])
        retnode = nodes.literal_block(text, text, source=uri)
        set_source_info(self, retnode)
        if 'language' in self.options:
            retnode['language'] = self.options['language']
        retnode['linenos'] = 'linenos' in self.options or \
                             'lineno-start' in self.options or \
                             'lineno-match' in self.options
        retnode['classes'] += self.options.get('class', [])
        extra_args = retnode['highlight_args'] = {}
        if hl_lines is not None:
            extra_args['hl_lines'] = hl_lines
        extra_args['linenostart'] = linenostart

        caption = self.options.get('caption')
        if caption is not None:
            if not caption:
                caption = self.arguments[0]
            try:
                retnode = container_wrapper(self, retnode, caption)
            except ValueError as exc:
                document = self.state.document
                errmsg = _('Invalid caption: %s' % exc[0][0].astext())
                return [document.reporter.warning(errmsg, line=self.lineno)]

        # retnode will be note_implicit_target that is linked from caption and numref.
        # when options['name'] is provided, it should be primary ID.
        self.add_name(retnode)

        return [retnode]

# This is kind of like a macro for RemoteInclude that figures out the right
# GitHub URL from the two required arguments (tag and path).
class RemoteExample(Directive):

    has_content = False
    required_arguments = 2  # tag and path
    optional_arguments = 1

    option_spec = RemoteInclude.option_spec

    def run(self):
        tag = self.arguments[0]
        path = self.arguments[1]
        url = 'https://raw.githubusercontent.com/walmartlabs/clojure-game-geek/' + tag + '/' + path

        content = [".. remoteinclude:: " + url ]

        for k, v in self.options.iteritems():
            if v is None:
                content += ['  :' + k + ':']
            else:
                content += ['  :' + k + ': ' + v]

        if not(self.options.has_key('language')):
            content += ['  :language: clojure']

        if not(self.options.has_key('caption')):
            content += ['  :caption: ' + path]

        vl = ViewList(content, source='')
        node = nodes.Element()

        self.state.nested_parse(vl, self.content_offset, node)

        return node.children

def api_link_inner(baseurl, rawtext, text, options):

  package, varname = split(strip(text), "/")

  if package == '':
    package = 'com.walmartlabs.lacinia'
  else:
    package = 'com.walmartlabs.lacinia.' + package

  ref = '%s/%s.html#var-%s' % (baseurl, package, varname)
  title = '%s/%s' % (package, varname)
  node = nodes.reference(rawtext, utils.unescape(title), refuri=ref, **options)

  return [node], []



def api_link_role(role, rawtext, text, lineno, inliner, options={}, content=[]):

  return api_link_inner('http://walmartlabs.github.io/lacinia', rawtext, text, options)

def setup(app):
    app.add_directive('remoteinclude', RemoteInclude)
    app.add_directive('ex', RemoteExample)
    app.add_role('api', api_link_role)

    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
