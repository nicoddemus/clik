import re
import os
import sys
import cmd
import types
import shlex
import inspect
import optparse
import subprocess
import ConfigParser

import logging
import logging.handlers

try:
    import readline
except ImportError:
    pass


class App(object):
    def __init__(self, name, **kwargs):
        self.name = name
        self.commands = {}
        self._in_shell = False
        self._configure(**kwargs)

        self._log_formatter = logging.Formatter(self.log_format)
        self._current_handler = None

        # Logging complains if there are no loggers. Add one that does nothing.
        logger_name = self.sub_name(self.log_name)
        logging.getLogger(logger_name).addHandler(_null_logging_handler)

        # If the user wants them, add the shell & clear commands.
        if self.shell_command:
            self.add(shell, self.shell_alias, shell=False)
            if self.shell_clear_command:
                self.add(clear, cli=False)

    def __call__(self, maybe_fn=None, **kwargs):
        """Decorator used for specifying/configuring subcommands."""
        if maybe_fn is None:
            # @myapp(with=some, keyword=args)
            # def user_fn():
            #     ...
            def decorator(fn):
                self.add(fn, **kwargs)
                return fn
            return decorator
        else:
            # @myapp
            # def user_fn():
            #     ...
            self.add(maybe_fn)
            return maybe_fn

    def main(self, argv=None):
        """Entry point for the application. If no argv given, uses sys.argv."""
        if argv is None:
            argv = sys.argv[1:]
        return self.run(argv)

    def run(self, argv):
        """Looks for a subcommand in argv, executes that command."""
        # Find the first non-option in the arguments.
        for name in argv:
            if name.startswith('-'):
                continue
            break
        else:
            # No subcommand name given.
            if '--version' in argv:
                print '0' if self.version is None else self.version
            else:
                self.print_help()
            return 1

        # Find the function with the specified name, make sure that command
        # can be run in the current "environment" (command shell or CLI)
        for fn, command in self.commands.iteritems():
            if name in command['names'] and \
               command['shell' if self._in_shell else 'cli']:
                break
        else:
            # No command with that name, print subcommand list and error,
            # then bail.
            self.print_help()
            print >>sys.stderr, 'error: unknown command', name
            return 1

        try:
            opts, args = self._get_parser(command).parse_args(argv)
        except OptionParserExit:
            # optparse.OptionParser is subclassed to circumvent the
            # sys.exit() call (which is extremely undesirable when in the
            # command shell). When sys.exit() would have been called, it
            # instead throws an OptionParserExit.
            return 1

        console = self._get_console(opts)
        conf = self._get_conf(opts)
        log = self._get_log(opts, conf)

        # Inspect the subcommand function signature and pass it the
        # desired objects.

        def get_arguments(fn, argument_dict):
            args = []
            for arg_name in inspect.getargspec(fn)[0]:
                if arg_name not in argument_dict:
                    raise TypeError('Expected any selection of %s and no other '
                                    'arguments, found %s' %
                                    (', '.join(arguments.keys()), arg_name))
                args.append(arguments[arg_name])
            return args

        arguments = {'opts': opts, 'args': args[1:], 'argv': argv,
                     'console': console, 'log': log, 'conf': conf, 'app': self}
        if self.args_callback:
            callback_args = get_arguments(self.args_callback, arguments)
            arguments.update(self.args_callback(*callback_args))

        return fn(*get_arguments(fn, arguments))

    def print_help(self):
        """Prints the basic information and subcommand list for the app."""
        # May or may not have a version and description.
        # Build an appropriate first line based on what's there.
        info_line = self.name
        if self.version:
            info_line += ' '+self.version
        if self.description:
            info_line += ' -- '+self.description
        print info_line
        print 'Basic usage:', self.name, '<subcommand> [options]\n'

        # Print a sorted list of the available subcommands.
        for data in sorted(self.commands.values(), key=lambda a: a['names'][0]):
            if data['cli']:
                print ', '.join(data['names'])
                print '   ', data['description']
                print
        print 'Run %s <command> -h for command help' % self.name
        return 1

    def add(self, fn, alias=None, usage=None, shell=True, cli=True, opts=None,
            global_opts=True, console_opts=None, version_opts=None,
            help_opts=None, conf_opts=None, log_opts=None, app_opts=None):
        """Adds a function as a subcommand to the application."""
        names = [fn.__name__]
        if alias is None:
            alias = []
        elif isinstance(alias, types.StringTypes):
            alias = [alias]
        else:
            alias = list(alias)
        names.extend(alias)

        # Parse the docstring, dealing with alignment issues.
        docstring = (fn.__doc__ or '').strip()
        if docstring:
            lines = docstring.split('\n')
            for line in lines[1:]:
                # Find the first non-blank line after the first line.
                # Use the indentation of that line as the baseline for
                # the rest of the docstring.
                if line.strip():
                    indent = 0
                    line_left = line
                    while line_left[0] == ' ':
                        indent += 1
                        line_left = line_left[1:]
                    description = lines[0].strip()
                    help = '\n'.join([l[indent:] if l.strip() else ''
                                      for l in lines[1:]])
                    break
            else:
                # Only one line (otherwise would have hit break)
                description, help = docstring, ''
        else:
            description, help = 'No description.', ''

        meta = {'names': names, 'usage': usage, 'shell': shell, 'cli': cli,
                'description': description, 'help': help, 'opts': opts,
                'global_opts': global_opts, 'console_opts': console_opts,
                'version_opts': version_opts, 'help_opts': help_opts,
                'conf_opts': conf_opts, 'log_opts': log_opts,
                'app_opts': app_opts}

        # Make sure none of the existing commands share a name.
        for name in names:
            for existing_fn, data in self.commands.iteritems():
                if name in data['names']:
                    raise ValueError(
                        'Command name %s from %s.%s conflicts with name '
                        'defined in %s.%s' %
                        (name, fn.__module__, fn.__name__,
                         existing_fn.__module__, existing_fn.__name__))

        self.commands[fn] = meta

    def sub_name(self, s):
        """Returns `s` with %name -> appname, %NAME -> APPNAME."""
        return s.replace('%name', self.name).replace('%NAME', self.name.upper())

    def _configure(self, description=None, version=None, conf_enabled=False,
                   conf_defaults={}, conf_locations=('/etc/%name', '~/.%name'),
                   conf_envvar_name='%NAME_CONFIG',
                   configparser_class=ConfigParser.SafeConfigParser,
                   log_enabled=False, log_name='%name',
                   log_filename='~/%name.log', log_level=logging.INFO,
                   log_format='%(asctime)s %(levelname)s %(message)s',
                   log_handler_class=logging.handlers.RotatingFileHandler,
                   log_handler_kwargs={'maxBytes': 10 * 1024 * 1024,
                                       'backupCount': 10, 'delay': True},
                   log_conf=True, log_conf_section='%name',
                   log_conf_filename_option='log_filename',
                   log_conf_level_option='log_level', opts=None,
                   console_opts=False, conf_opts=True, log_opts=True,
                   shell_command=True, shell_alias='sh',
                   shell_prompt='(%name)> ', shell_clear_command=True,
                   args_callback=None):
        self.description = description
        self.version = version
        self.args_callback = args_callback
        
        self.conf_enabled = conf_enabled
        self.conf_defaults = conf_defaults
        self.conf_locations = conf_locations
        self.conf_envvar_name = conf_envvar_name
        self.configparser_class = configparser_class

        self.log_enabled = log_enabled
        self.log_name = log_name
        self.log_filename = log_filename
        self.log_level = log_level
        self.log_format = log_format
        self.log_handler_class = log_handler_class
        self.log_handler_kwargs = log_handler_kwargs
        self.log_conf = log_conf
        self.log_conf_section = log_conf_section
        self.log_conf_filename_option = log_conf_filename_option
        self.log_conf_level_option = log_conf_level_option

        self.opts = opts
        self.console_opts = console_opts
        self.conf_opts = conf_opts
        self.log_opts = log_opts

        self.shell_command = shell_command
        self.shell_alias = shell_alias
        self.shell_prompt = shell_prompt
        self.shell_clear_command = shell_clear_command

    def _get_parser(self, meta):
        opt = optparse.make_option
        opts = ()

        # Determine which options should be added to the command.

        if meta['opts'] is not None:
            if isinstance(meta['opts'], optparse.Option):
                opts += (meta['opts'],)
            else:
                opts += tuple(meta['opts'])

        # Aside from the command opts, we have the app_opts, console_opts,
        # conf_opts, log_opts, help_opts and version_opts. When global_opts
        # is True, we want these to default to True if not set (None). When
        # global_opts is False we want them to default to False.
        def wants_opts(key):
            key += '_opts'
            if meta[key] is None:
                return True if meta['global_opts'] else False
            return bool(meta[key])

        if wants_opts('app') and self.opts is not None:
            if isinstance(self.opts, optparse.Option):
                opts += (self.opts,)
            else:
                opts += tuple(self.opts)

        if wants_opts('console') and self.console_opts:
            opts += (
                opt('-v', '--verbose', dest='console_verbosity',
                    action='store_const', const=2, default=1,
                    help='Emit verbose information'),
                opt('-q', '--quiet', dest='console_verbosity',
                    action='store_const', const=0, default=1,
                    help='Emit only errors'),
                opt('--no-color', dest='console_color',
                    action='store_false', default=True,
                    help='Do not colorize output')
            )

        if wants_opts('conf') and self.conf_enabled and self.conf_opts:
            # Figure out the list of paths so we can display that in the -h
            # output.
            if isinstance(self.conf_locations, types.StringTypes):
                paths = [self.conf_locations]
            else:
                paths = list(self.conf_locations)
            paths = map(self.sub_name, paths)

            help_text = 'Path to config file (will read '+(', '.join(paths))
            if self.conf_envvar_name:
                help_text += ', $'+self.sub_name(self.conf_envvar_name)
            help_text += ', then this value, if set)'

            opts += (opt('--config', dest='conf_path', action='store',
                         default=None, help=help_text),)

        if wants_opts('log') and self.log_enabled and self.log_opts:
            level_choices = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
            opts += (
                opt('--log-filename', dest='log_filename', action='store',
                    default=None, help=('Log to file [default: %s]' %
                                        self.sub_name(self.log_filename))),
                opt('--log-level', dest='log_level', action='store',
                    default=logging.getLevelName(self.log_level),
                    choices=level_choices,
                    help=('Logging level '
                          '('+(', '.join(level_choices))+') '
                          '[default %default]'))
            )

        # If we're in the shell, we don't need to prefix usage with appname.
        usage = '' if self._in_shell else self.name+' '
        usage += '|'.join(meta['names'])+' '
        usage +=  '[options]' if meta['usage'] is None else meta['usage']

        # OptionParser omits --version if no version is supplied.
        version = self.version if wants_opts('version') else None
        
        return OptionParser(prog=self.name,
                            description=meta['description'],
                            usage=usage,
                            epilog=meta['help'] or '',
                            option_list=opts,
                            add_help_option=wants_opts('help'),
                            version=version)

    def _get_console(self, opts):
        # Initialize a console object. This command may not have added
        # console_opts, default to reasonable values in that case.
        console = Console()
        console.color = getattr(opts, 'console_color', None)
        console.verbosity = getattr(opts, 'console_verbosity', 1)
        return console

    def _get_conf(self, opts):
        # If conf_enabled=False, just return this empty object.
        conf = self.configparser_class()
        if self.conf_enabled:
            # conf_defaults is a dict or string naming a module with the dict.
            if isinstance(self.conf_defaults, types.StringTypes):
                d = __import__(self.conf_defaults, {}, {}, ['']).conf_defaults
            else:
                d = self.conf_defaults

            # Set the defaults in the object with the values from conf_default.
            for section, options in d.iteritems():
                conf.add_section(section)
                for name, value in options.iteritems():
                    conf.set(section, name, str(value))

            # Make a list of the files to read for configuration.
            if isinstance(self.conf_locations, types.StringTypes):
                # conf_locations = '/path/to/config'
                conf_locations = [self.conf_locations]
            else:
                # conf_locations = ('/sequence', '/of', 'paths/to/config')
                conf_locations = list(self.conf_locations)
            if self.conf_envvar_name:
                # Also allowing config file to be set via envvar.
                envvar = self.sub_name(self.conf_envvar_name)
                if envvar in os.environ:
                    conf_locations.append(os.environ[envvar])
            if hasattr(opts, 'conf_path') and opts.conf_path:
                # conf_opts was added and user supplied a value for it.
                conf_locations.append(opts.conf_path)

            conf.read([expand_path(self.sub_name(filename))
                       for filename in conf_locations])

        return conf

    def _get_log(self, opts, conf):
        # If logging not enabled, return the logger (with the null handler
        # set up in __init__)
        log = logging.getLogger(self.sub_name(self.log_name))
        if self.log_enabled:
            # level will either be the integer value (log_level=logging.INFO)
            # or a string (--log-level=INFO) depending on where the value comes
            # from. This translates it into the integer value used by `logging`.
            lvl = lambda v: v if isinstance(v, int) else getattr(logging, v)

            # Start with the defaults, overwrite if other values are set.
            filename = self.sub_name(self.log_filename)
            level = lvl(self.log_level)

            if self.conf_enabled and self.log_conf:
                # Allowing configuration of logging via the conf system.
                # Determine the section & option names and see if the user
                # has overridden any of those options.
                section = self.sub_name(self.log_conf_section)
                option = lambda v: self.sub_name(
                    getattr(self, 'log_conf_%s_option' % v))
                try:
                    filename = conf.get(section, option('filename'))
                except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                    pass
                try:
                    level = lvl(conf.get(section, option('level')))
                except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                    pass

            # If log_opts was added and a value supplied by the user, prefer
            # that value.
            if hasattr(opts, 'log_filename') and opts.log_filename:
                filename = opts.log_filename
            if hasattr(opts, 'log_level') and opts.log_level:
                level = lvl(opts.log_level)

            # log_handler_class should always take filename. Grab the
            # rest of the keyword args from the app configuration.
            kwargs = {'filename': expand_path(filename)}
            kwargs.update(self.log_handler_kwargs)

            # If we have previously set up a logging handler, detach it from
            # the logger so it no longer handles messages.
            if self._current_handler:
                log.removeHandler(self._current_handler)

            # Set up the new handler.
            self._current_handler = self.log_handler_class(**kwargs)
            self._current_handler.setFormatter(self._log_formatter)
            self._current_handler.setLevel(level)

            # Set the log level to the same as our handler's level and
            # attach the handler.
            log.setLevel(level)
            log.addHandler(self._current_handler)

        return log


def shell(app):
    """A command shell for this application."""
    app._in_shell = True

    # Note: the cmd module is frigging sweet.
    class ApplicationShell(cmd.Cmd):
        prompt = app.sub_name(app.shell_prompt)

        def default(self, line):
            print 'error: unknown command:', line

        def do_exit(self, args):
            raise StopIteration
        
        def help_exit(self):
            print app.sub_name('Exits the %name shell')
            
        def do_quit(self, args):
            self.do_exit(args)

        def help_quit(self):
            self.help_exit()

    def contribute_to_shell(names):
        canonical, aliases = names[0], names[1:]
        def run(self, args):
            # When called, break up the arguments using shlex and run it
            # like main() does.
            app.run(shlex.split(canonical+' '+args))
            return 0

        # The 'canonical' name will have help attached to it.
        setattr(ApplicationShell, 'do_'+canonical, run)
        setattr(ApplicationShell, 'help_'+canonical,
                lambda self: app.run([canonical, '-h']))

        # Aliases do not get help. This is slightly annoying but less annoying
        # than having all commands show up in "Documented Commands" and not
        # knowing which are just aliases...
        for alias in aliases:
            setattr(ApplicationShell, 'do_'+alias, run)

    for data in app.commands.itervalues():
        if data['shell']:
            contribute_to_shell(data['names'])

    try:
        while True:
            try:
                ApplicationShell().cmdloop()
            except OptionParserExit:
                # Our OptionParser overrides optparse's OptionParser's exit()
                # method and raises an OptionParserExit instead of running
                # sys.exit() (we do not want to exit the command shell on one
                # bad option to one command). When this happens, just start
                # the command loop over.
                pass
    except KeyboardInterrupt:
        # User hit Ctl-c, output \n so their prompt appears on the next line.
        print
    except StopIteration:
        # Raised from do_exit()/do_quit(). User has hit enter so the \n
        # is already there.
        pass

    return 0


def clear():
    """Runs the `clear` command for your shell."""
    subprocess.call(['clear'])


class OptionParserExit(Exception):
    """Thrown in lieu of sys.exit() in OptionParser.exit()"""


class OptionParser(optparse.OptionParser):
    def format_epilog(self, formatter):
        # Help comes from the docstring, assume it's already formatted how
        # the author intends.
        return self.epilog+'\n\n'

    def exit(self, status=0, msg=None):
        # *I* decide when my application exits, damn it!
        if msg:
            sys.stderr.write(msg)
        raise OptionParserExit


class NullLoggingHandler(logging.Handler):
    def emit(self, record):
        pass
_null_logging_handler = NullLoggingHandler()


def expand_path(path):
    return os.path.expanduser(os.path.expandvars(path))


class Console(object):
    def __init__(self, verbosity=1, color=None):
        self.verbosity = verbosity
        self.color = color

    def _create_markup_re(self):
        markup_re = re.compile(r'<(%s|/)>' % ('|'.join(self.color_codes)))
        self.__class__.markup_re = markup_re
        return markup_re

    def _set_verbosity(self, value):
        if value not in (0, 1, 2):
            raise ValueError('console.verbosity must be 0, 1 or 2')
        self._verbosity = value

    def _get_verbosity(self):
        return self._verbosity

    def _auto_color(self):
        # From Sphinx's console.py
        if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
            return False
        if 'COLORTERM' in os.environ:
            return True
        term = os.environ.get('TERM', 'dumb').lower()
        if term in ('xterm', 'linux') or 'color' in term:
            return True
        return False

    def _set_color(self, value):
        if value is None:
            self._color = self._auto_color()
        else:
            self._color = bool(value)

    def _get_color(self):
        return self._color

    def _create_color_map(self):
        # From Sphinx's console.py, adapted for this class.
        codes = {}
        
        _attrs = {
            'reset':     '39;49;00m',
            'bold':      '01m',
            'faint':     '02m',
            'standout':  '03m',
            'underline': '04m',
            'blink':     '05m',
        }

        for _name, _value in _attrs.items():
            codes[_name] = '\x1b[' + _value

        _colors = [
            ('black',     'darkgray'),
            ('darkred',   'red'),
            ('darkgreen', 'green'),
            ('brown',     'yellow'),
            ('darkblue',  'blue'),
            ('purple',    'fuchsia'),
            ('turqoise',  'teal'),
            ('lightgray', 'white'),
        ]

        for i, (dark, light) in enumerate(_colors):
            codes[dark] = '\x1b[%im' % (i+30)
            codes[light] = '\x1b[%i;01m' % (i+30)

        self.__class__.color_codes = codes
        return codes

    verbosity = property(_get_verbosity, _set_verbosity)
    color = property(_get_color, _set_color)
    color_codes = property(_create_color_map)
    markup_re = property(_create_markup_re)

    def emit(self, message, verbosity=1, newlines=1, stream=sys.stdout):
        if self.verbosity >= verbosity:
            message = str(message)
            if self.color:
                # `out` holds the stream of text we'll eventually output
                # `stack` is the currently applied color codes
                # `remaining` holds the still-unparsed part of message
                # `match` is any <colorcode> or </> construct
                out = ''
                stack = []
                remaining = message
                match = self.markup_re.search(remaining)
                while match:
                    # `token` is either 'colorcode' or '/'.
                    token = match.groups()[0]
                    out += remaining[:match.start()]
                    remaining = remaining[match.end():]

                    if token == '/':
                        if stack:
                            # Pull the last style off the stack.
                            # Emit a reset then reapply the remaining styles.
                            stack.pop()
                            out += self.color_codes['reset']
                            for name in stack:
                                out += self.color_codes[name]
                    else:
                        out += self.color_codes[token]
                        stack.append(token)

                    match = self.markup_re.search(remaining)

                # Get any remaining text that doesn't have markup and
                # reset the terminal if there are any unclosed color tags.
                out += remaining
                if stack:
                    out += self.color_codes['reset']
            else:
                # No color, just strip that information from the message
                out = self.markup_re.sub('', message)

            stream.write(out+('\n' * newlines))
            stream.flush()

    def error(self, message, newlines=1):
        message = str(message)
        self.emit(message, verbosity=0, newlines=newlines, stream=sys.stderr)

    def quiet(self, message='', newlines=1):
        return self.emit(message, verbosity=0, newlines=newlines)

    def q(self, message='', newlines=1):
        return self.emit(message, verbosity=0, newlines=newlines)

    def normal(self, message='', newlines=1):
        return self.emit(message, verbosity=1, newlines=newlines)

    def n(self, message='', newlines=1):
        return self.emit(message, verbosity=1, newlines=newlines)

    def verbose(self, message='', newlines=1):
        return self.emit(message, verbosity=2, newlines=newlines)

    def v(self, message='', newlines=1):
        return self.emit(message, verbosity=2, newlines=newlines)
