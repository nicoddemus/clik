import sys
import difflib
from nose.tools import ok_, with_setup


_stdout, _stderr = None, None


class DummyOutput(object):
    def __init__(self):
        self.buffer = ''

    def write(self, s):
        self.buffer += s

    def clear(self):
        self.buffer = ''

    def __contains__(self, s):
        return s in self.buffer

    def __eq__(self, other):
        return other == self.buffer

    def __ne__(self, other):
        return other != self.buffer

    def __str__(self):
        return self.buffer

    def __repr__(self):
        return self.buffer.replace('\n', '\\n')


def capture_output(fn):
    orig = sys.stdout, sys.stderr
    def setup():
        global _stdout, _stderr
        sys.stdout, sys.stderr = _stdout, _stderr = DummyOutput(), DummyOutput()
    def teardown():
        global _stdout, _stderr
        sys.stdout, sys.stderr = orig
        _stdout, _stderr = None, None
    return with_setup(setup, teardown)(fn)


def assert_stdout(expected):
    if _stdout is None:
        raise Exception('Test function not decorated with capture_output')
    assert_string(expected, _stdout.buffer)


def assert_stderr(expected):
    if _stderr is None:
        raise Exception('Test function not decorated with capture_output')
    assert_string(expected, _stderr.buffer)


def reset_stdout():
    if _stdout is None:
        raise Exception('Test function not decorated with capture_output')
    _stdout.buffer = ''


def reset_stderr():
    if _stderr is None:
        raise Exception('Test function not decorated with capture_output')
    _stderr.buffer = ''


def assert_string(expected, actual):
    if expected == actual:
        passed, message = True, ''
    else:
        passed = False
        message = 'Strings did not match\n'
        diff = list(difflib.unified_diff(actual.split('\n'),
                                         expected.split('\n'),
                                         fromfile='expected',
                                         tofile='actual'))
        message += ''.join(diff[:2])+'\n'.join(diff[2:])
    ok_(passed, message)
