
======
 Clik
======

Clik (CLI Kit) requires Python 2.5 [#]_.

Clik provides glue code for subcommand-style CLI applications. It does
command dispatch and option parsing. It provides
a terminal output helper connected to the standard ``-v/-q`` flags. It
transparently gives your application a command shell. If you want,
clik will set up a ConfigParser instance and read in ini-style config files for
you. If your application wants logging, clik can set up a logging
handler for you as well.

Clik is one module and less than a thousand lines of code, so it's
easy to read, modify and include in your projects.

This README is an introduction, tutorial and the documentation wrapped
in one. It shows the development of a simple app named ``downloader``,
which downloads content to a local directory. You can check out the
example code, which basically matches the development of the code in
this file, from git://github.com/jds/downloader. The output is
included in the repository files; if you're not interested in my
commentary you can simply step through the history.



Installation
============

Setuptools::

    easy_install clik

Or download the latest version from http://pypi.python.org/pypi/clik,
extract the tarball and run ``python setup.py install``.

The git repository is at git://github.com/jds/clik.



The Basics
==========

To start writing an application, you'll create an instance of ``clik.App`` and
call its ``main`` method::

    import clik

    downloader = clik.App('downloader')

    if __name__ == '__main__':
        downloader.main()

At this point you have a working application::

    $ python downloader.py
    downloader
    Basic usage: downloader <subcommand> [options]

    shell, sh
        A command shell for this application.

    Run downloader <command> -h for command help

Typically you'll also want to provide a version and short summary::

    downloader = clik.App('downloader',
                          version='1.0',
                          description='Manages downloads in a local directory.')


    $ python downloader.py
    downloader 1.0 -- Manages downloads in a local directory.
    Basic usage: downloader <subcommand> [options]
    # same output as before
    
    $ python downloader.py --version
    1.0

Add subcommands by defining a function and decorating it with the app
instance. The command name will be the function name::

    @downloader
    def hello_world():
        print 'Hello, world!'


    $ python downloader.py 
    downloader 1.0 -- Manages downloads in a local directory.
    Basic usage: downloader <subcommand> [options]
    
    hello_world
        No description.
    
    shell, sh
        A command shell for this application.
    
    Run downloader <command> -h for command help
    

    $ python downloader.py hello_world -h
    Usage: downloader hello_world [options]
    
    No description.
    
    Options:
      --version   show program's version number and exit
      -h, --help  show this help message and exit
    
    
    $ python downloader.py hello_world
    Hello, world!

Help is taken from the function's docstring, if it exists. The
docstring should be formatted conventionally [#]_::

      @downloader
      def hello_world():
          """
          Says hello to the world.

          For nontrivial commands, this text right here would be a
          more thorough description of what the command does and how
          to use it. For hello_world, you'd typically just use a
          one-liner with no extended help.
          """

    $ python downloader.py 
    downloader 1.0 -- Manages downloads in a local directory.
    Basic usage: downloader <subcommand> [options]
    
    hello_world
        Says hello to the world.
    
    shell, sh
        A command shell for this application.
    
    Run downloader <command> -h for command help
    

    $ python downloader.py hello_world -h
    Usage: downloader hello_world [options]
    
    Says hello to the world.
    
    Options:
      --version   show program's version number and exit
      -h, --help  show this help message and exit
    
    For nontrivial commands, this text right here would be a
    more thorough description of what the command does and how
    to use it. For hello_world, you'd typically just use a
    one-liner with no extended help.

``hello_world`` is aptly named but a bit painful to type over and
over again. Adding shorter names is easy::

    @downloader(alias='hw')
    def hello_world():
        print 'Hello, world!'

    # or

    @downloader(alias=['hw', 'hllwrld'])
    def hello_world():
        print 'Hello, world!'


    $ python downloader.py 
    downloader 1.0 -- Manages downloads in a local directory.
    Basic usage: downloader <subcommand> [options]
    
    hello_world, hw, hllwrld
        Says hello to the world.
    
    shell, sh
        A command shell for this application.
    
    Run downloader <command> -h for command help
    

    $ python downloader.py hw
    Hello, world!

    $ python downloader.py hllwrld
    Hello, world!

Of course, clik makes sure your names don't run over each other::

    @downloader
    def hw():
        print 'You will not see me because the script will not run!'

    
    $ python downloader.py
    Traceback (most recent call last):
      File "downloader.py", line 22, in <module>
        @downloader
      File "/Users/jds/.virtualenvs/clik-tutorial/lib/python2.6/site-packages/clik.py", line 55, in __call__
        self.add(maybe_fn)
      File "/Users/jds/.virtualenvs/clik-tutorial/lib/python2.6/site-packages/clik.py", line 199, in add
        existing_fn.__module__, existing_fn.__name__))
    ValueError: Command name hw from __main__.hw conflicts with name defined in __main__.hello_world

This is typical of much of the interaction with clik: start
with the least amount of code necessary, extend application-wide
functionality by providing arguments to the app constructor and
configure subcommand-level functionality by providing arguments to the
decorator.

Before moving on, I should be clear: while ``hello_world()`` has
started its life as a typical function, its signature is inspected at
runtime and dynamically passed the desired arguments. You may only ask
for arguments with known names. Base arguments:

* ``args``: List of arguments, not including application or command name.
* ``argv``: List of arguments including the command name.
* ``opts``: ``optparse.Values`` for the invocation.
* ``app``: The ``click.App`` running the subcommand.
* ``console``: ``clik.Console`` object.
* ``conf``: ``ConfigParser.ConfigParser`` instance. Will be empty if
  conf is not enabled.
* ``log``: ``logging.Logger`` instance for the application. Has no
  handlers (thus does "nothing") if logging is not enabled.

You can extend (or override, if you want) the argument values by
providing the ``args_callback`` a value in the app constructor::

    def my_callback(opts, args):
        # my_callback can take any of the base objects as arguments.
        return {'conf': MyConfigObject(), 'someval': AnotherThing()}

    downloader = clik.App('downloader',
                          args_callback=my_callback)

    @downloader
    def my_subcommand(conf, someval):
        # conf will be the MyConfigObject()
        # someval is the AnotherThing instance

``downloader`` eventually makes use of all these facilities. Read on
to see how.


Downloader
==========

Let's get down to business with the code. I'll start by showing you
the basic working implementation and then trick it out with only a bit
more code.

``downloader`` should be able to list files in a local downloads
directory, remove files from the directory and download data from URLs
into the directory.

::

    import os
    import urllib
    import urlparse
    
    import clik
    
    
    DOWNLOADS_PATH = os.path.join(os.path.dirname(__file__), 'downloads')
    
    
    def downloads_dir():
        path = os.path.expanduser(os.path.expandvars(DOWNLOADS_PATH))
        if not os.path.exists(path):
            os.mkdir(path)
        return path
    
    
    downloader = clik.App('downloader',
                          version='1.0',
                          description='Manages downloads in a local directory.')
    
    
    @downloader(alias='ls')
    def list():
        """List the contents of the downloads directory."""
        downloads = downloads_dir()
        filenames = os.listdir(downloads)
        for filename in filenames:
            print filename
        return 0
    
    
    @downloader(alias='rm')
    def remove(args):
        """Remove a downloaded file."""
        if len(args) < 1:
            print >>sys.stderr, 'error: expecting at least one filename to remove'
            return 1
        downloads = downloads_dir()
        for arg in args:
            path = os.path.join(downloads, arg)
            if os.path.exists(path):
                os.unlink(path)
            else:
                print >>sys.stdout, 'no such file or directory: '+path
        return 0
    
    
    @downloader(alias='dl')
    def download(args):
        if len(args) < 1:
            print >>sys.stderr, 'error: you must provide a URL'
            return 1
        url = args[0]
        
        if len(args) > 1:
            name = args[1]
        else:
            name = urlparse.urlparse(url).path.split('/')[-1]
            if not name:
                name = 'index.html'
    
        downloads = downloads_dir()
        download_path = os.path.join(downloads, name)
        if os.path.exists(download_path):
            return 0
    
        print 'fetching %s...' % url
        try:
            urllib.urlretrieve(url, download_path)
        except IOError, e:
            print >>sys.stderr, e
            return 1
        return 0


In action::

    $ python downloader.py dl -h
    Usage: downloader download|dl [options]
    
    No description.
    
    Options:
      --version   show program's version number and exit
      -h, --help  show this help message and exit
    
    
    $ python downloader.py ls -h
    Usage: downloader list|ls [options]
    
    List the contents of the downloads directory.
    
    Options:
      --version   show program's version number and exit
      -h, --help  show this help message and exit
    
    
    $ python downloader.py rm -h
    Usage: downloader remove|rm [options]
    
    Remove a downloaded file.
    
    Options:
      --version   show program's version number and exit
      -h, --help  show this help message and exit
    
    
    $ python downloader.py ls
    $ python downloader.py dl http://python.org python-index.html
    fetching http://python.org...
    $ python downloader.py dl http://python.org python-index.html
    $ python downloader.py ls
    python-index.html
    $ python downloader.py rm python-index.html
    $ python downloader.py ls
    $    
    
The first niggling issue to take care of is the usage for ``dl`` and
``rm``. Clik will always make the usage start with ``<app-name>
<command-name>`` but you can override what comes after::

    @downloader(alias='rm', usage='[file1 [file2 [...]]] [options]')
    def remove(args):
        ...

    @downloader(alias='dl', usage='URL [local-name] [options]')
    def download(args):
        ...
    

    $ python downloader.py dl -h
    Usage: downloader download|dl URL [local-name] [options]
    
    No description.
    
    Options:
      --version   show program's version number and exit
      -h, --help  show this help message and exit
    
    
    $ python downloader.py rm -h
    Usage: downloader remove|rm [file1 [file2 [...]]] [options]
    
    Remove a downloaded file.
    
    Options:
      --version   show program's version number and exit
      -h, --help  show this help message and exit


Command Shell
=============

Perhaps you noticed the ``shell/sh`` command I've neglected to talk
about thus far. In my opinion, clik's best feature is the
transparently-provided command shell for your application. Without
changing a single line, ``downloader`` can do this::

    $ python downloader.py sh
    (downloader)> ?
    
    Documented commands (type help <topic>):
    ========================================
    clear  download  exit  list  quit  remove
    
    Undocumented commands:
    ======================
    dl  help  ls  rm
    
    (downloader)> ? download
    Usage: download|dl URL [local-name] [options]
    
    No description.
    
    Options:
      --version   show program's version number and exit
      -h, --help  show this help message and exit
    
    
    (downloader)> ls
    (downloader)> dl http://python.org python-index.html
    fetching http://python.org...
    (downloader)> dl http://python.org python-index.html
    (downloader)> ls
    python-index.html
    (downloader)> rm python-index.html
    (downloader)> ls
    (downloader)> exit
    $     

Aliases are listed as undocumented commands so that "working command
set" is clear.

**Nitty Gritty**

* Passing ``shell_command=False`` to the app constructor disables the
  shell command entirely.
* Passing ``shell_clear_command=False`` to the app constructor
  disables the automatically-provided shell ``clear`` command. If
  ``shell_command`` is ``False``, this has no effect (the clear
  command will not be added).
* You can change the prompt by passing a string to ``shell_prompt`` in
  the app constructor. ``%name`` will be substituted with the
  application name. E.g. ``shell_prompt='%name%'`` would make
  downloader's shell prompt ``downloader%``.
* You can change the shell's alias by passing ``shell_alias`` to the
  app constructor. This accepts the same values as other aliases
  (string or sequence of strings). Defaults to ``sh``.
* You can indicate that a subcommand should be unavailable in the
  command shell by passing ``shell=False`` to the decorator. E.g.::

      @downloader(shell=False)
      def no_shell_example():
          print 'I will be available only from the command-line'

* You can indicate a subcommand should be unavailable from the command
  line by passing ``cli=False`` to the decorator. E.g.::

      @downloader(cli=False)
      def no_cli_example():
          print 'I will be available only in the command shell'


Options
=======

Right now, the downloads path is hardcoded into ``downloader``. Let's
add an option to the app to let users specify which directory should
contain the downloads::

    from optparse import make_option as opt

    def downloads_dir(opts):
        path = opts.downloads_directory or DOWNLOADS_PATH
        # ...

    downloader = clik.App('downloader',
                          opts=opt('-d', '--downloads-dir',
                                   dest='downloads_directory', default=None,
                                   help=('Directory where downloads are stored '
                                         '[default: '+DOWNLOADS_PATH+']')))


    # Add ``opts`` to each subcommand signature and call to downloads_dir() E.g.

    @downloader(alias='ls')
    def list(opts):
        downloads = downloads_dir(opts)
        # ...


    $ python downloader.py ls -h
    Usage: downloader list|ls [options]
    
    List the contents of the downloads directory.
    
    Options:
      -d DOWNLOADS_DIRECTORY, --downloads-dir=DOWNLOADS_DIRECTORY
                            Directory where downloads are stored [default:
                            downloads]
      --version             show program's version number and exit
      -h, --help            show this help message and exit
    
    
    $ python downloader.py ls
    $ python downloader.py dl http://python.org
    fetching http://python.org...
    $ python downloader.py ls
    index.html
    $ python downloader.py ls -d otherdir
    $ python downloader.py dl http://python.org -d otherdir
    fetching http://python.org...
    $ python downloader.py ls -d otherdir
    index.html
    $ python downloader.py rm index.html -d otherdir
    $ python downloader.py ls -d otherdir
    $ python downloader.py ls
    index.html
    
This is a step in the right direction, but still pretty
annoying as there's no way to permanently specify the downloads
directory. We'll deal with this later on, with the configuration
system.

Note that ``opts`` can be a single ``optparse.Option`` or a sequence
of options.

If you've tried to download content from a nonexistent URL, you
might have noticed that ``downloader`` hangs forever (or, longer than
I was willing to wait to find out). We'll add a ``-t`` option to let
users specify the timeout.

Also, to get a fresh copy of a URL, the user must ``rm`` the local
file before running ``dl``. We'll add an ``-o`` option so users can
indicate they'd like a fresh download::


    @downloader(alias='dl', usage='URL [local-name] [options]',
                opts=(opt('-t', '--timeout', dest='timeout', type='int',
                          default=30, help='Connection timeout [default %default]'),
                      opt('-o', '--overwrite', dest='overwrite', action='store_true',
                          default=False, help='Overwrite (re-download) file')))
    def download(args, opts):
        # ...
        if os.path.exists(download_path):
            if opts.overwrite:
                os.unlink(download_path)
            else:
                return 0
    
        import socket
        socket.setdefaulttimeout(opts.timeout)
        print 'fetching %s...' % url
        # ...



    $ python downloader.py dl -h
    Usage: downloader download|dl URL [local-name] [options]
    
    Downloads content from the internet.
    
    Options:
      -t TIMEOUT, --timeout=TIMEOUT
                            Connection timeout [default 30]
      -o, --overwrite       Overwrite (re-download) file
      -d DOWNLOADS_DIRECTORY, --downloads-dir=DOWNLOADS_DIRECTORY
                            Directory where downloads are stored [default:
                            downloads]
      --version             show program's version number and exit
      -h, --help            show this help message and exit
    
    
    $ python downloader.py ls
    $ python downloader.py dl http://python.org
    fetching http://python.org...
    $ python downloader.py dl http://python.org
    $ python downloader.py dl http://python.org -o
    fetching http://python.org...
    $ python downloader.py ls
    index.html


Supplying Custom Arguments
==========================

Each subcommand has to call ``downloads_dir``, which is annoying
(especially in the case of ``ls`` and ``rm`` which otherwise don't use the
options argument). In this case you can use the ``args_callback``
argument to the app constructor. ``args_callback`` should be a
function whose signature follows the same rules as subcommands and
should return a dictionary with {argument name: value} pairs.

::

    def downloads_dir(opts):
        # ...
        return {'downloads': path}

    downloader = clik.App('downloader',
                          args_callback=downloads_dir)

    def list(downloads):
        # -downloads = downloads_dir(opts)
        # ...

    def remove(args, downloads):
        # -downloads = downloads_dir(opts)
        # ...

    def download(args, opts, downloads):
        # -downloads = downloads_dir(opts)
        # ...

    

Configuration
=============

Sooner or later every CLI application needs configuration. Clik
provides for ini-style configuration with the common pattern of
reading a list of files, each successive file's configuration
overriding any previously-read values. By default, clik will look for
configuration files in ``/etc/your-app-name``, then
``~/.your-app-name``, then the filepath given in the
``$YOURAPPNAME_CONFIG`` envvar, then the value of ``--config``, if
provided.

For downloader, we want the user to be able to permanently configure
the download directory. In their configuration file, they'll set it up
like this::

     [downloader]
     path = /path/to/their/downloads

To enable configuration, add ``conf_enabled=True`` to the
app constructor and specify the defaults::

    downloader = clik.App('downloader',
                          conf_enabled=True,
                          conf_defaults={'downloader': {'path': DOWNLOADS_PATH}})

``conf_defaults`` should be a dictionary of dictionaries representing
the default sections and options. It can also be a string pointing to
a module with a similarly-defined ``conf_defaults`` attribute. That is,
we could create a file "downloader_conf.py", define ``conf_defaults``
in that file, and use ``clik.App(conf_defaults='downloader_conf')``.

When conf is enabled, subcommands can take the ``conf`` argument,
which will be an instance of ``ConfigParser.SafeConfigParser`` by
default. Because the directory-handling code for ``downloader`` is in
``downloads_dir()`` we'll add the config-handling code there::

    def downloads_dir(opts, conf):
        path = opts.downloads_directory or conf.get('downloader', 'path') or DOWNLOADS_PATH
        # ...


    $ python downloader.py ls -h
    Usage: downloader list|ls [options]
    
    List the contents of the downloads directory.
    
    Options:
      -d DOWNLOADS_DIRECTORY, --downloads-dir=DOWNLOADS_DIRECTORY
                            Directory where downloads are stored [default:
                            downloads]
      --config=CONF_PATH    Path to config file (will read /etc/downloader,
                            ~/.downloader, $DOWNLOADER_CONFIG, then this value, if
                            set)
      --version             show program's version number and exit
      -h, --help            show this help message and exit
    
    
    $ python downloader.py ls
    $ python downloader.py dl http://python.org
    fetching http://python.org...
    $ python downloader.py ls
    index.html
    $ cat >>~/.downloader
    [downloader]
    path = ./downloads2
    ^C
    $ python downloader.py ls
    $ python downloader.py dl http://python.org
    fetching http://python.org...
    $ python downloader.py ls
    index.html
    $ ls
    README		downloader.py	downloads	downloads2
    $ cat >>cfg
    [downloader]
    path = ./downloads3
    ^C
    $ export DOWNLOADER_CONFIG=./cfg
    $ python downloader.py ls
    $ python downloader.py dl http://python.org
    fetching http://python.org...
    $ python downloader.py ls
    index.html
    $ ls
    README	downloader.py	downloads2
    cfg		downloads	downloads3
    $ cat >>cfg2
    [downloader]
    path = ./downloads4
    ^C
    $ python downloader.py ls --config=./cfg2
    $ python downloader.py dl http://python.org --config=./cfg2
    fetching http://python.org...
    $ python downloader.py ls --config=./cfg2
    index.html
    $ ls
    README	cfg2		downloads	downloads3
    cfg		downloader.py	downloads2	downloads4

**Details**

* You can change the ``ConfigParser`` class by passing a value to
  ``configparser_class`` in the app constructor. By default this is
  ``ConfigParser.SafeConfigParser``.
* ``conf_locations`` determines the base list of places to look for
  configuration. This can be a string or sequence of
  strings. ``%name`` is replaced with the application's name. Defaults
  to ``('/etc/%name', '~/.%name')``.
* Disable configuration via ``--config`` by passing
  ``conf_opts=False`` to the app constructor.
* You can change the envvar name by passing a string to
  ``conf_envvar_name``. ``%NAME`` will be substituted with the app
  name in all caps. For example, to change the envvar name from
  ``DOWNLOADER_CONFIG`` to ``DOWNLOADER_CFG``::

      downloader = clik.App('downloader',
                            conf_envvar_name='%NAME_CFG')

* Disable config via envvar by passing ``conf_envvar_name=None``.


Console Output
==============

Another common need among CLI applications is output control
(``-v/-q`` options). To enable those options, add
``console_opts=True`` to the app constructor::

    downloader = clik.App('downloader',
                          console_opts=True)

Subcommand functions can take the ``console`` object, which has these
methods::

    console.quiet('Always emitted to stdout')
    console.q('Alias for console.quiet()')
    console.normal('Emitted if the user does not pass -q')
    console.n('Alias for console.normal()')
    console.verbose('Emitted only if the user passes -v')
    console.v('Alias for console.verbose()')
    console.error('Always emitted to stderr')

By default, a single newline is emitted after the string. You can
change that using the ``newlines`` argument::

    console.n('Doing something...', newlines=0)
    console.n('done')

There is also a small colorization markup language::

    console.q('<red>Error:</> something bad happened.')

The complete list of colors is in the appendix.

Updating ``downloader`` to use the console system::


    def downloads_dir(opts, conf, console):
        path = opts.downloads_directory or conf.get('downloader', 'path') or DOWNLOADS_PATH
        path = os.path.expanduser(os.path.expandvars(path))
        console.v('downloads directory is '+path)
        if not os.path.exists(path):
            console.v('downloads directory does not exist, creating')
            os.mkdir(path)
        return {'downloads': path}
    
    
    downloader = clik.App('downloader',
                          version='1.0',
                          description='Manages downloads in a local directory.',
                          console_opts=True,
                          conf_enabled=True,
                          conf_defaults={'downloader': {'path': DOWNLOADS_PATH}},
                          opts=opt('-d', '--downloads-dir',
                                   dest='downloads_directory', default=None,
                                   help=('Directory where downloads are stored '
                                         '[default: '+DOWNLOADS_PATH+']')),
                          args_callback=downloads_dir)
    
    
    @downloader(alias='ls')
    def list(downloads, console):
        """List the contents of the downloads directory."""
        filenames = os.listdir(downloads)
        console.n('%i files in downloads' % len(filenames))
        for filename in filenames:
            console.q(filename)
        return 0
    
    
    @downloader(alias='rm', usage='[file1 [file2 [...]]] [options]')
    def remove(args, downloads, console):
        """Remove a downloaded file."""
        if len(args) < 1:
            console.error('error: expecting at least one filename to remove')
            return 1
        for arg in args:
            path = os.path.join(downloads, arg)
            if os.path.exists(path):
                console.v('removing '+path)
                os.unlink(path)
            else:
                console.error('<red>error:</> no such file or directory: '+path)
        return 0
    
    
    @downloader(alias='dl', usage='URL [local-name] [options]',
                opts=(opt('-t', '--timeout', dest='timeout', type='int',
                          default=30, help='Connection timeout [default %default]'),
                      opt('-o', '--overwrite', dest='overwrite', action='store_true',
                          default=False, help='Overwrite (re-download) file')))
    def download(args, opts, downloads, console):
        """Downloads content from the internet."""
        if len(args) < 1:
            console.error('<red>error:</> you must provide a URL')
            return 1
        url = args[0]
        
        if len(args) > 1:
            name = args[1]
        else:
            name = urlparse.urlparse(url).path.split('/')[-1]
            if not name:
                name = 'index.html'
        console.v('url is %s, local name is %s' % (url, name))
    
        download_path = os.path.join(downloads, name)
        if os.path.exists(download_path):
            if opts.overwrite:
                console.v('local file already exists, overwriting')
                os.unlink(download_path)
            else:
                console.v('local file already exists, not downloading')
                return 0
    
        import socket
        socket.setdefaulttimeout(opts.timeout)
        console.n('fetching %s...' % url, newlines=0)
        try:
            urllib.urlretrieve(url, download_path)
        except IOError, e:
            console.n('<red>error</>')
            console.error(e)
            return 1
        console.n('<bold>done</>')
        return 0
    
In the terminal::

    $ python downloader.py dl -h
    Usage: downloader download|dl URL [local-name] [options]

    Downloads content from the internet.
    
    Options:
      -t TIMEOUT, --timeout=TIMEOUT
                            Connection timeout [default 30]
      -o, --overwrite       Overwrite (re-download) file
      -d DOWNLOADS_DIRECTORY, --downloads-dir=DOWNLOADS_DIRECTORY
                            Directory where downloads are stored [default:
                            downloads]
      -v, --verbose         Emit verbose information
      -q, --quiet           Emit only errors
      --no-color            Do not colorize output
      --config=CONF_PATH    Path to config file (will read /etc/downloader,
                            ~/.downloader, $DOWNLOADER_CONFIG, then this value, if
                            set)
      --version             show program's version number and exit
      -h, --help            show this help message and exit
    

    $ python downloader.py dl http://python.org -v
    downloads directory is downloads
    downloads directory does not exist, creating
    url is http://python.org, local name is index.html
    fetching http://python.org...done
    
    $ python downloader.py dl http://python.org -v
    downloads directory is downloads
    url is http://python.org, local name is index.html
    local file already exists, not downloading
    
    $ python downloader.py dl http://python.org -vo
    downloads directory is downloads
    url is http://python.org, local name is index.html
    local file already exists, overwriting
    fetching http://python.org...done
    
    $ python downloader.py dl http://python.org
    
    $ python downloader.py dl http://python.org -oq
    
    $ python downloader.py ls
    1 files in downloads
    index.html
    
    $ python downloader.py ls -q
    index.html
    
    $ python downloader.py ls -v
    downloads directory is downloads
    1 files in downloads
    index.html
    
    $ python downloader.py rm foo
    error: no such file or directory: downloads/foo
    
    $ python downloader.py rm foo --no-color
    error: no such file or directory: downloads/foo
    
    $ python downloader.py rm index.html -v
    downloads directory is downloads
    removing downloads/index.html


Logging
=======

Last but not least, clik provides an easy, flexible way to set up file-based
logging. To get started, set ``log_enabled=True`` in the app
constructor::

    downloader = clik.App('downloader',
                          log_enabled=True)

Subcommands can take the ``log`` argument, which will be the
``logging.Logger`` instance for the application::

    def downloads_dir(opts, conf, console, log):
        # ...
        if not os.path.exists(path):
            msg = 'downloads directory does not exist, creating'
            log.info(msg)
            console.v(msg)
            os.mkdir(path)
        return {'downloads': path}

    def remove(args, downloads, console, log):
        # ...
        for arg in args:
            path = os.path.join(downloads, arg)
            if os.path.exists(path):
                console.v('removing '+path)
                os.unlink(path)
                log.info('removed '+path)
            else:
                console.error('<red>error:</> no such file or directory: '+path)
        return 0

    def download(args, opts, downloads, console, log):
        # ...
        download_path = os.path.join(downloads, name)
        if os.path.exists(download_path):
            if opts.overwrite:
                console.v('local file already exists, overwriting')
                os.unlink(download_path)
                log.info('removed '+download_path)
            else:
                console.v('local file already exists, not downloading')
                return 0
    
        import socket
        socket.setdefaulttimeout(opts.timeout)
        console.n('fetching %s...' % url, newlines=0)
        try:
            urllib.urlretrieve(url, download_path)
        except IOError, e:
            console.n('<red>error</>')
            console.error(e)
            log.error('could not fetch %s: %s' % (url, e))
            return 1
        log.info('fetched '+url)
        console.n('<bold>done</>')
        return 0


In the shell::

    $ python downloader.py dl -h
    Usage: downloader download|dl URL [local-name] [options]

    Downloads content from the internet.

    Options:
      -t TIMEOUT, --timeout=TIMEOUT
                            Connection timeout [default 30]
      -o, --overwrite       Overwrite (re-download) file
      -d DOWNLOADS_DIRECTORY, --downloads-dir=DOWNLOADS_DIRECTORY
                            Directory where downloads are stored [default:
                            downloads]
      -v, --verbose         Emit verbose information
      -q, --quiet           Emit only errors
      --no-color            Do not colorize output
      --config=CONF_PATH    Path to config file (will read /etc/downloader,
                            ~/.downloader, $DOWNLOADER_CONFIG, then this value, if
                            set)
      --log-filename=LOG_FILENAME
                            Log to file [default: ~/downloader.log]
      --log-level=LOG_LEVEL
                            Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                            [default INFO]
      --version             show program's version number and exit
      -h, --help            show this help message and exit


    $ python downloader.py dl http://python.org
    fetching http://python.org...done
    $ python downloader.py rm index.html
    $ python downloader.py dl http://does.not.exist
    fetching http://does.not.exist...error
    [Errno socket error] [Errno 8] nodename nor servname provided, or not known
    $ cat ~/downloader.log
    2010-01-02 05:46:59,274 INFO downloads directory does not exist, creating
    2010-01-02 05:46:59,886 INFO fetched http://python.org
    2010-01-02 05:47:02,409 INFO removed downloads/index.html
    2010-01-02 05:47:05,226 ERROR could not fetch http://does.not.exist: [Errno socket error] [Errno 8] nodename nor servname provided, or not known
    $
    

**Detail**

Logging is extremely configurable, both by you and your end
users. Arguments to the app constructor that affect logging:

* ``log_enabled``: If ``True``, a file-based logging handler is
  created for the application and attached to the logger with the name
  given in ``log_name``. Defaults to ``False``.
* ``log_name``: Logger name. "%name" is substituted with the
  application name. Defaults to "%name".
* ``log_filename``: Default filepath for the application's log (the
  user can override the log path). "%name" is subsituted with the
  application name. Defaults to "~/%name.log".
* ``log_level``: Default logging level for the application (user user
  can override the log level). Defaults to ``logging.INFO``.
* ``log_format``: The string to use for the ``logging.Formatter`` for
  the handler. Defaults to "%(asctime)s %(levelname)s %(message)s".
* ``log_handler_class``: File-based handler class to use. Defaults to
  ``logging.handlers.RotatingFileHandler``.
* ``log_handler_kwargs``: Dictionary to use as keyword arguments when
  constructing ``log_handler_class``. ``filename`` will always be
  added to this dictionary. Defaults to::

      {'maxBytes': 10 * 1024 * 1024,
       'backupCount': 10,
       'delay': True}

* ``log_conf``: If ``True``, the user can configure logging via config
  files (assuming ``conf_enabled=True``). Defaults to ``True``.
* ``log_conf_section``: The section of the configuration file containing
  log filepath and log level options. "%name" is substituted with the
  application name. Defaults to "%name".
* ``log_conf_filename_option``: Name of the option inside
  ``log_conf_section`` where the log filepath is specified. "%name" is
  substituted with the application name. Defaults to "log_filename".
* ``log_conf_level_option``: Name of the option inside
  ``log_conf_section`` where the log filepath is specified. "%name" is
  substituted with the application name. Defaults to "log_level".
* ``log_opts``: If ``True`` and logging is enabled, subcommands will
  accept ``--log-filename`` and ``--log-level`` options which can be
  used to configure logging on a per-call basis. Defaults to ``True``
  (ie. "on" if logging is enabled).

*Configuration via config files.* For example, you can change the log
filepath and level for ``downloader`` by setting ``log_filepath`` and
``log_level`` in one of the configuration files::

    [downloader]
    path = path/to/the/downloads/dir
    log_filepath = ~/my-logs/downloader.log
    log_level = DEBUG


Appendix: ``clik.App`` Constructor Arguments
============================================

* ``name``: Application name. Required.
* ``description``: One-line description of the application. Defaults to ``None``.
* ``version``: Version number string. Defaults to ``None``.
* ``args_callback``: Callback function for adding arguments for
  subcommands. Defaults to ``None``.
* ``conf_enabled``: Boolean indicating whether the config system is
  enabled. Defaults to ``False``.
* ``conf_defaults``: Dictionary of dictionaries specifying defaults
  for the config system. Can also be a string naming a module that has
  a ``conf_defaults`` attribute with the same format (dictionary of
  dictionaries of defaults). Defaults to ``{}``.
* ``conf_envvar_name``: Environment variable name letting the user
  specify a path to a config file. If ``None``, configuration via
  envvar is not allowed. Defaults to ``%NAME_CONFIG``.
* ``configparser_class``: ``ConfigParser`` based class for the config
  object. Defaults to ``ConfigParser.SafeConfigParser``.
* ``log_enabled``: If ``True``, a file-based logging handler is
  created for the application and attached to the logger with the name
  given in ``log_name``. Defaults to ``False``.
* ``log_name``: Logger name. "%name" is substituted with the
  application name. Defaults to "%name".
* ``log_filename``: Default filepath for the application's log (the
  user can override the log path). "%name" is subsituted with the
  application name. Defaults to "~/%name.log".
* ``log_level``: Default logging level for the application (user user
  can override the log level). Defaults to ``logging.INFO``.
* ``log_format``: The string to use for the ``logging.Formatter`` for
  the handler. Defaults to "%(asctime)s %(levelname)s %(message)s".
* ``log_handler_class``: File-based handler class to use. Defaults to
  ``logging.handlers.RotatingFileHandler``.
* ``log_handler_kwargs``: Dictionary to use as keyword arguments when
  constructing ``log_handler_class``. ``filename`` will always be
  added to this dictionary. Defaults to::

      {'maxBytes': 10 * 1024 * 1024,
       'backupCount': 10,
       'delay': True}

* ``log_conf``: If ``True``, the user can configure logging via config
  files (assuming ``conf_enabled=True``). Defaults to ``True``.
* ``log_conf_section``: The section of the configuration file containing
  log filepath and log level options. "%name" is substituted with the
  application name. Defaults to "%name".
* ``log_conf_filename_option``: Name of the option inside
  ``log_conf_section`` where the log filepath is specified. "%name" is
  substituted with the application name. Defaults to "log_filename".
* ``log_conf_level_option``: Name of the option inside
  ``log_conf_section`` where the log filepath is specified. "%name" is
  substituted with the application name. Defaults to "log_level".
* ``log_opts``: If ``True`` and logging is enabled, subcommands will
  accept ``--log-filename`` and ``--log-level`` options which can be
  used to configure logging on a per-call basis. Defaults to ``True``
  (ie. "on" if logging is enabled).
* ``opts``: Application-wide options. Can be an ``optparse.Option`` or
  sequence of options. Defaults to ``None``.
* ``console_opts``: Whether ``-v/-q/--no-color`` are enabled. Defaults
  to ``False``.
* ``conf_opts``: If ``conf_enabled=True`` and this is ``True``, the
  user can set the configuration file via the ``--config``
  option. Defaults to ``True``.
* ``log_opts``: If ``log_enabled=True`` and this is ``True``, the user
  can configure the log filename and log level via ``--log-filename``
  and ``--log-level`` options.
* ``shell_command``: If ``True``, provide the ``shell`` command for
  this application. Defaults to ``True``.
* ``shell_alias``: String or list of strings for the ``shell``
  command's alias. Defaults to ``sh``.
* ``shell_prompt``: Prompt for the shell. "%name" is substituted with
  the application name. Defaults to "(%name)> ".
* ``shell_clear_command``: If ``shell_command=True`` and this is
  ``True``, add the ``clear`` command to the command shell.


Appendix: Decorator Arguments
=============================

* ``alias``: Optional string or list of strings to use as aliases to
  this command. The "canonical" name is the name of the
  function. Defaults to ``None`` (no aliases).
* ``usage``: Usage string for help. The string "<app-name> <command-name> " is
  prepended to this string. Defaults to "[options]".
* ``shell``: Boolean indicating whether the command should be
  available in the command shell. Defaults to ``True``.
* ``cli``: Boolean indicating whether the command should be available
  from the command line. Defaults to ``True``.
* ``opts``: Extra options for this command.

You can also selectively disable any of the automatically added
options. Note that this generally is not a good idea as that option
becomes "global-except-for-that-one-command", which is annoying. Pass
``False`` to any one of these arguments to disable the associated
options:

* ``console_opts``: -v/--verbose, -q/--quiet, --no-color
* ``version_opts``: --version
* ``conf_opts``: --config
* ``log_opts``: --log-filename, --log-level
* ``app_opts``: Application-wide options.

In the extreme case where you want to turn off all these options, you
can pass ``global_opts=False``. With ``global_opts=False``, you can
selectively add the options back in by setting the associated
arguments to ``True``. For example, to disable all arguments except
``-v/-q``, the decorator would be::

    @downloader(version_opts=False, conf_opts=False, log_opts=False, app_opts=False)

   # or

   @downloader(global_opts=False, console_opts=True)


Appendix: Terminal Colors
=========================

These are the colors in the ``clik.Console`` library:

* bold
* faint
* standout
* underline
* blink
* black
* darkgray
* darkred
* red
* darkgreen
* green
* brown
* yellow
* darkblue
* blue
* purple
* fuchsia
* turqoise
* teal
* lightgray
* white

``clik.Console`` is based on Georg Brandl's Sphinx project's ``console.py``.

.. [#] I don't have a machine handy to test on anything earlier. I'll
       let you know once I get around to it.

.. [#] Specifically, clik can properly handle docstrings that consist
       of one line::

           def hello_world():
               """Says hello to the world."""

           def hello_world():
               """
               Says hello to the world.
               """

       Docstrings with more information should have a one line
       description followed by a blank line followed by the extended
       info::

           def hello_world():
               """
               Says hello to the world.

               If there were more to say about a hello world function,
               this is where it would go. The indentation of the first
               line after the short description is used as the
               baseline for the rest of the text. Otherwise,
               formatting is preserved. This is unlike optparse's
               handling of `epilog`, which annoyingly reformats the
               input its given. That makes it hard to write
               clearly-formatted examples, which is exactly
               what you want to do in the "more help" text!
               """
