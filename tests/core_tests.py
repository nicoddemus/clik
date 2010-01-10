import sys
import clik
from nose.tools import assert_raises
from tests import assert_stdout, assert_stderr, capture_output, reset_stdout, reset_stderr


boilerplate = clik.App('boilerplate')

def dispatch_app():
    app = clik.App('dispatch')

    def hello_world():
        print 'Hello, world!'
    app(hello_world)

    def an_alias():
        print 'Command with an alias'
    app(alias='aa')(an_alias)
    
    def double_alias():
        print 'Command with two aliases'
    app(alias=['dbl', 'da'])(double_alias)

    return app


def version_app():
    app = clik.App('versiontest', version='1.0')

    def cmd():
        pass
    app(cmd)

    return app


def noversion_app():
    app = clik.App('versiontest')

    def cmd():
        pass
    app(cmd)

    return app


def help_app(version=None):
    app = clik.App('helptest', version=version)

    def an_alias():
        pass
    app(alias='aa')(an_alias)

    def oneline_help():
        """A short description of the command."""
    app(oneline_help)

    def multiline_help():
        """
        A short description of the command.

        This is extended help about the command. Fancy.
        """
    app(multiline_help)

    return app


def arg_app():
    app = clik.App('argtest')

    def echo(args, argv):
        print ' '.join(args)
        print ' '.join(argv)
    app(echo)

    return app


def test_boilerplate_noargs():
    boilerplate.main(argv=[])
    assert_stdout("""boilerplate
Basic usage: boilerplate <subcommand> [options]

shell, sh
    A command shell for this application.

`boilerplate <command> -h` for command help
""");
    assert_stderr('')
test_boilerplate_noargs = capture_output(test_boilerplate_noargs)


def test_boilerplate_invalid_command():
    boilerplate.main(argv=['foo'])
    assert_stdout("""boilerplate
Basic usage: boilerplate <subcommand> [options]

shell, sh
    A command shell for this application.

`boilerplate <command> -h` for command help
""");
    assert_stderr('error: unknown command foo\n')
test_boilerplate_invalid_command = capture_output(test_boilerplate_invalid_command)


def test_app_version_metadata():
    version = clik.App('versiontest', version='1.0')
    version.main(argv=[])
    assert_stdout("""versiontest 1.0
Basic usage: versiontest <subcommand> [options]

shell, sh
    A command shell for this application.

`versiontest <command> -h` for command help
`versiontest --version` prints version and exits
""");
    assert_stderr('')
test_app_version_metadata = capture_output(test_app_version_metadata)


def test_app_description_metadata():
    description = clik.App('descriptiontest',
                           description='A command with a description.')
    description.main(argv=[])
    assert_stdout("""descriptiontest -- A command with a description.
Basic usage: descriptiontest <subcommand> [options]

shell, sh
    A command shell for this application.

`descriptiontest <command> -h` for command help
""");
    assert_stderr('')
test_app_description_metadata = capture_output(test_app_description_metadata)


def test_app_combined_metadata():
    combined = clik.App('combinedtest',
                        version='1.0',
                        description='A command with a description and version.')
    combined.main(argv=[])
    assert_stdout("""combinedtest 1.0 -- A command with a description and version.
Basic usage: combinedtest <subcommand> [options]

shell, sh
    A command shell for this application.

`combinedtest <command> -h` for command help
`combinedtest --version` prints version and exits
""");
    assert_stderr('')
test_app_combined_metadata = capture_output(test_app_combined_metadata)


def test_basic_dispatch():
    dispatch_app().main(argv=['hello_world'])
    assert_stdout('Hello, world!\n')
    assert_stderr('')
test_basic_dispatch = capture_output(test_basic_dispatch)


def test_alias_dispatch():
    dispatch = dispatch_app()

    dispatch.main(argv=['an_alias'])
    assert_stdout('Command with an alias\n')
    assert_stderr('')

    reset_stdout()
    dispatch.main(argv=['aa'])
    assert_stdout('Command with an alias\n')
    assert_stderr('')
test_alias_dispatch = capture_output(test_alias_dispatch)


def test_multiple_alias_dispatch():
    dispatch = dispatch_app()

    dispatch.main(argv=['double_alias'])
    assert_stdout('Command with two aliases\n')
    assert_stderr('')

    reset_stdout()    
    dispatch.main(argv=['dbl'])
    assert_stdout('Command with two aliases\n')
    assert_stderr('')

    reset_stdout()
    dispatch.main(argv=['da'])
    assert_stdout('Command with two aliases\n')
    assert_stderr('')
test_multiple_alias_dispatch = capture_output(test_multiple_alias_dispatch)


def test_name_conflicts():
    def define_name_conflict_app():
        app = clik.App('someapp')
        def duplicate():
            pass
        app(duplicate)
        def duplicate():
            pass
        app(duplicate)

    def define_alias_conflict_app():
        app = clik.App('someapp')
        def duplicate():
            pass
        app(duplicate)
        def dupe():
            pass
        app(alias='duplicate')(dupe)

    assert_raises(ValueError, define_name_conflict_app)
    assert_raises(ValueError, define_alias_conflict_app)


def test_version_option_with_version_set():
    version_app().main(argv=['--version'])
    assert_stdout('1.0\n')
    assert_stderr('')
test_version_option_with_version_set = capture_output(test_version_option_with_version_set)


def test_version_option_with_version_unset():
    noversion_app().main(argv=['--version'])
    assert_stdout("""versiontest
Basic usage: versiontest <subcommand> [options]

cmd
    No description.

shell, sh
    A command shell for this application.

`versiontest <command> -h` for command help
""")
    assert_stderr('')
test_version_option_with_version_unset = capture_output(test_version_option_with_version_unset)


def test_version_option_to_subcommand_with_version_unset():
    noversion_app().main(argv=['cmd', '--version'])
    assert_stdout('')
    assert_stderr("""Usage: versiontest cmd [options]

versiontest: error: no such option: --version
""")
test_version_option_to_subcommand_with_version_unset = capture_output(test_version_option_to_subcommand_with_version_unset)


def test_help_subcommand_list():
    help_app().main(argv=[])
    assert_stdout("""helptest
Basic usage: helptest <subcommand> [options]

an_alias, aa
    No description.

multiline_help
    A short description of the command.

oneline_help
    A short description of the command.

shell, sh
    A command shell for this application.

`helptest <command> -h` for command help
""");
    assert_stderr('')
test_help_subcommand_list = capture_output(test_help_subcommand_list)


def test_help_one_liner():
    help_app(version='1.0').main(argv=['oneline_help', '-h'])
    assert_stdout("""Usage: helptest oneline_help [options]

A short description of the command.

Options:
  -h, --help  show this help message and exit


""")
    assert_stderr('')
test_help_one_liner = capture_output(test_help_one_liner)


def test_help_multiline():
    help_app().main(argv=['multiline_help', '-h'])
    assert_stdout("""Usage: helptest multiline_help [options]

A short description of the command.

Options:
  -h, --help  show this help message and exit

This is extended help about the command. Fancy.

""")
    assert_stderr('')
test_help_multiline = capture_output(test_help_multiline)


def test_help_alias():
    help_app().main(argv=['an_alias', '-h'])
    assert_stdout("""Usage: helptest an_alias|aa [options]

No description.

Options:
  -h, --help  show this help message and exit


""")
    assert_stderr('')
test_help_alias = capture_output(test_help_alias)


def test_args():
    arg_app().main(argv=['echo', 'foo', 'bar', 'baz'])
    assert_stdout('foo bar baz\necho foo bar baz\n')
    assert_stderr('')
test_args = capture_output(test_args)
