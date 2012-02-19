#!/usr/bin/env python

from distutils.core import setup
from cwrap import __version__ as cwv
import sys , os , shutil

MANPATHS = (
    '/usr/man' ,
    '/usr/share/man' ,
    '/usr/local/man' ,
    '/usr/local/share/man'
)

def installMan(manpage):
    # Check for the man location
    for d in MANPATHS:
        man1 = os.path.join(d , 'man1')
        if os.path.isdir(d) and os.path.isdir(man1):
            # We have found a man directory, install!
            print 'Copying %s to %s' % (manpage , os.path.join(man1 , manpage))
            shutil.copyfile(manpage , man1)
            os.system('gzip -9 %s' % os.path.join(man1 , manpage))

setup(name='cron-wrap' ,
    version=cwv ,
    author='Jay Deiman' ,
    author_email='admin@splitstreams.com' ,
    url='http://stuffivelearned.org/doku.php?id=programming:python:cwrap' ,
    description='A cron job wrapper used to suppress output' ,
    scripts=['cwrap.py']
)



if 'install' in sys.argv:
    # Try to install the man page
    installMan('./cwrap.py.1')
