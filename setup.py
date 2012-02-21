#!/usr/bin/env python

from distutils.core import setup

setup(name='cron-wrap' ,
    version='0.4.2' ,
    author='Jay Deiman' ,
    author_email='admin@splitstreams.com' ,
    url='http://stuffivelearned.org/doku.php?id=programming:python:cwrap' ,
    description='A cron job wrapper used to suppress output' ,
    long_description='Full documentation can be found in the man page or here: '
        'http://stuffivelearned.org/doku.php?id=programming:python:cwrap' ,
    scripts=['cwrap.py'] ,
    data_files = [ ('man/man1' , ['cwrap.py.1']) ] ,
    classifiers=[
        'Development Status :: 5 - Production/Stable' ,
        'Environment :: Console' ,
        'Intended Audience :: System Administrators' ,
        'License :: OSI Approved :: GNU General Public License (GPL)' ,
        'Natural Language :: English' ,
        'Operating System :: POSIX' ,
        'Programming Language :: Python' ,
        'Topic :: System :: Systems Administration' ,
    ]
)
