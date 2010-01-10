from setuptools import setup, find_packages


setup(
    name="clik",
    version="0.3.1",
    url='http://github.com/jds/clik',
    author='Joe Strickler',
    author_email='jd.strickler@gmail.com',
    description='Library for creating subcommand-style CLI applications.',
    packages=find_packages(),
    extras_require={'dev': ['nose==0.11.1', 'coverage==3.2']})
