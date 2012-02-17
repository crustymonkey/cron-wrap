#!/usr/local/bin/python

# This file is part of cron-wrap.
# 
# cron-wrap is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# cron-wrap is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with cron-wrap.  If not, see <http://www.gnu.org/licenses/>.

from optparse import OptionParser , OptionValueError , OptionGroup
import cPickle as pickle
from hashlib import md5
import subprocess as sp
import sys , time , os , signal , syslog

DEBUG = False
STATEFILE = None
LOGPRI = 0
__version__ = '0.4.1'

# File creation error exit code
E_FC = 1
# Failure limit reached
E_FLR = 2

# Exceptions
class LockError(Exception):
    """
    Error to be raised when a lockfile is found
    """
    pass

class FileCreationError(Exception):
    def __init__(self , msg , errorList=[]):
        self.msg = msg
        self.eList = errorList

    def __str__(self):
        return '%s\n%s' % (self.msg , '\n'.join([str(e) for e in self.eList]))

class CmdTimeout(Exception):
    pass

# Define classes
class StateFile(file):
    def __init__(self , name , mode='r+' , buffering=-1 , lockFile=None):
        """
        Override the init function to create a lockfile
        """
        if lockFile:
            self._lockName = lockFile
        else:
            self._lockName = '%s.lock' % name
        self._lock()
        # In order to open this r+, we need to have an existing file.  If it
        # does not exist, we want to create it first
        self._create(name)
        super(StateFile , self).__init__(name , mode , buffering)

    def close(self):
        """
        Override close to delete the lockfile
        """
        super(StateFile , self).close()
        self._unlock()

    def getObject(self):
        """
        Returns the object stored in the state file
        """
        self.seek(0)
        obj = None
        try:
            obj = pickle.load(self)
        except Exception , e:
            # Can't unpickle for some reason, create a new state
            pass
        return obj

    def saveObject(self , obj):
        """ 
        This will pickle the object in the current state file
        """
        # delete file contents and add new
        self.seek(0)
        self.truncate(0)
        pickle.dump(obj , self)

    def _create(self , fname):
        if not os.path.exists(fname):
            # Basically "touch" the file
            fh = open(fname , 'w')
            fh.close()
        os.chmod(fname , 0600)

    def _lock(self):
        """
        Create a lockfile or raise LockError if a lockfile is found
        """
        fd = None
        try:
            fd = os.open(self._lockName , os.O_CREAT | os.O_WRONLY | os.O_EXCL)
        except OSError , e:
            raise LockError('Lock file exists, cannot open state file: %s' % 
                self._lockName)
        os.fchmod(fd , 0600)
        os.write(fd , '%d' % os.getpid())
        os.close(fd)

    def _unlock(self):
        """
        Simply deletes the lockfile
        """
        try:
            pid = int(open(self._lockName).read())
            if pid != os.getpid():
                raise LockError('Lock file does not contain current process '
                    'pid! lock file: %d ; cur pid: %d' % pid , os.getpid())
            os.unlink(self._lockName)
        except:
            pass

    def __del__(self):
        self._unlock()

    @staticmethod
    def getStateFileName(opts , cmdList):
        """
        This basically just hashes the cmdList to create a filename unique
        to this cron commmand.

            opts<optparse.Values>:  The options list from the command line
            cmdList<list>:      The command line wherein each element is an item
                                in the list
            
            returns -> <str>:   The full path to the state file
        """
            
        dig = md5(''.join(cmdList)).hexdigest()
        # Use the item we are executing as part of the file name
        baseCmd = cmdList[0]
        if opts.singStr:
            baseCmd = cmdList[0].split()[0]
        binExec = baseCmd.replace('/' , '-').strip('-.')
        fname = '%s.%s' % (binExec , dig)
        return os.path.join(opts.stateDir , fname)

    @staticmethod
    def getStateFile(opts , cmdList):
        """
        This will determine the state file name and return the StateFile object
        if it is successful.  If it can't get a statefile within the optionally
        specified period (usually because a previously started process is still
        running), it will raise an OSError.

            opts<optparse.Values>:      Options passed in on the command line
            cmdList<list>:              The command and args list
            
            returns -> <StateFile>:     A created StateFile instance

            raises -> FileCreationError
        """
        stFName = StateFile.getStateFileName(opts , cmdList)
        lockFile = None
        if opts.lockFile:
            lockFile = opts.lockFile
        errs = []
        sf = None
        for i in xrange(opts.numRetries + 1):
            try:
                sf = StateFile(stFName , lockFile=lockFile)
            except Exception , e:
                errs.append(e)
            else:
                break
            if opts.numRetries:
                time.sleep(opts.retrySecs)
        if not sf:
            raise FileCreationError('Could not create state file: %s' % 
                stFName , errs)
        return sf

class Failure(object):
    """
    This is a simple class to encapsulate the items pertaining to a failure
    """
    mainDelim = '=' * 40
    subDelim = '-' * 40
    def __init__(self , command , timeStarted , runTime , exitCode , 
            stdout='' , stderr='' , pythonError=''):
        """
        Pass in all the info for a command run

            command<list>:      A list containing all the command line items
            timeStarted<float>: The timestamp for when this was started
            runTime<float>:     The amount of time that the process ran for
            exitCode<int>:      The exit code from the process
            stdout<str>:        The output printed to stdout
            stderr<str>:        The output printed to stderr
            pythonError<str>:   An error that occured in Python trying to
                                run the program (exitCode should be -1)
        """
        self.command = command
        self.timeStarted = timeStarted
        self.runTime = runTime
        self.exitCode = exitCode
        self.stdout = stdout
        self.stderr = stderr
        self.pyError = pythonError

    def __str__(self):
        ret = '%s\nCommand: %s\n' % (self.mainDelim , ' '.join(self.command))
        ret += 'Start Time: %s\n' % time.ctime(self.timeStarted)
        ret += 'Run Time (seconds): %.02f\n' % self.runTime
        ret += 'Exit Code: %d (-1 is a python error)\n' % self.exitCode
        if self.stdout:
            ret += '\nSTDOUT:\n%s\n%s\n%s\n' % (self.subDelim , self.stdout ,
                self.subDelim)
        if self.stderr:
            ret += '\nSTDERR:\n%s\n%s\n%s\n' % (self.subDelim , self.stderr ,
                self.subDelim)
        if not self.stdout and not self.stderr:
            ret += '\nNothing printed to STDOUT or STDERR\n'
        if self.pyError:
            ret += '\nPYTHON ERROR:\n%s\n%s\n%s\n' % (self.subDelim , 
                self.pyError , self.subDelim)
        ret += '%s\n' % self.mainDelim
        return ret

class CommandState(object):
    """
    This is the object that will be used to maintain the state of failures
    of the process that this script is wrapping.  This object instance will
    be serialized to disk and imported to preserve all state when run.
    """
    def __init__(self , opts , cmdList):
        """
        Instantiate this object with the command line options and the command
        list.  The command list should start with the command and essentially
        be the full command line to be run.

            opts<optparse.Values>:      The options passed in on the command
                                        line
            cmdList<list>:              A list containing each element of the
                                        command line
        """
        self.opts = opts
        self.cmdList = cmdList
        self._reset()

    def getNumFails(self):
        return len(self.failures)
    NumFails = property(getNumFails)

    def run(self):
        """
        Performs this run and prints an error report if necessary.
        """
        start = self.lastRunStartTime = time.time()
        ph = None
        stdout = ''
        stderr = ''
        if self.opts.timeout:
            # We set an alarm for the execution of this program since a 
            # timeout was set
            signal.signal(signal.SIGALRM , self._timeoutHandler)
            signal.alarm(self.opts.timeout)
        try:
            if self.opts.singStr:
                ph = sp.Popen(self.cmdList[0] , shell=True , stdout=sp.PIPE ,
                     stderr=sp.PIPE)
            else:
                ph = sp.Popen(self.cmdList , stdout=sp.PIPE , stderr=sp.PIPE)
            stdout , stderr = ph.communicate()
            if self.opts.timeout:
                # If we get here, disable the alarm
                signal.alarm(0)
        except Exception , e:
            self.lastRunRunTime = time.time() - start
            self.lastRunExitCode = -1
            self.lastRunStdout = ''
            self.lastRunStderr = ''
            self.lastRunPyError = str(e)
            self._procFail()
            return False
        self.lastRunRunTime = time.time() - start
        self.lastRunExitCode = ph.returncode
        self.lastRunStdout = stdout
        self.lastRunStderr = stderr
        self.lastRunPyError = ''
        if ph.returncode == 0:
            # We have a successful run, reset everything and then just 
            # print the stdout and stderr vals
            self._reset()
            if not self.opts.quiet:
                sys.stdout.write(stdout)
                sys.stderr.write(stderr)
            return True
        self._procFail()
        return False

    def _timeoutHandler(self , signum , frame):
        """
        This is just an alarm signal handler to handle the timeout specified
        on the command line.
        """
        raise CmdTimeout('Command reached timeout of %d seconds' % 
            self.opts.timeout)

    def _procFail(self):
        """
        This processes a failure and adds it to the list of failures.  It
        then determines whether the specified threshold has been reached and
        writes out the failures if it has.
        """
        f = Failure(self.cmdList , self.lastRunStartTime , self.lastRunRunTime ,
            self.lastRunExitCode , self.lastRunStdout , self.lastRunStderr ,
            self.lastRunPyError)
        self.failures.append(f)
        if self.opts.syslog:
            self._logFail(f)
        if self.NumFails:
            if self.NumFails % self.opts.numFails == 0 or \
                    (self.opts.fstFail and self.NumFails == 1):
                self._writeFails()
                self._reset(False)

    def _writeFails(self):
        """
        This will actually write all the failures out to stdout
        """
        if self.NumFails == 1 and self.opts.fstFail:
            # We have a first fail
            print 'The following command has failed for the first time and'
            print 'the option to print a report for the first fail is set.'
        else:
            print 'The specified number of failures, %d,' % self.opts.numFails,
            print 'has been reached for the following '
            print 'command which has failed %d times in a row:' % self.NumFails
        print '\n%s\n\nFAILURES:' % ' '.join(self.cmdList)
        for f in self.failures[-self.opts.numFails:]:
            print f

    def _logFail(self , fail):
        msg = 'CMD: %s; EXIT: %d; RUNTIME: %.02f; ' % (fail.command , 
            fail.exitCode , fail.runTime)
        if fail.pyError:
            msg += 'PYERR: %s; ' % fail.pyError
        if fail.stdout:
            msg += 'STDOUT: %s; ' % fail.stdout.replace('\n' , ' ')
        if fail.stderr:
            msg += 'STDERR: %s;' % fail.stderr.replace('\n' , ' ')
        log(msg)
        
    def _reset(self , resetFails=True):
        """
        Resets all the variables back to empty defaults
        """
        if resetFails:
            self.failures = []
        self.lastRunExitCode = None
        self.lastRunStdout = None
        self.lastRunStderr = None
        self.lastRunStartTime = None
        self.lastRunRunTime = None
        self.lastRunPyError = None

    def _getEscCmd(self):
        cmd = "'%s'" % self.cmdList[0].replace("'" , "'\"'\"'")
        return cmd

# Utility functions
def getOpts():
    global LOGPRI
    """
    Parses the command line options and returns the output of 
    OptionParser.parse_args()

    returns -> (<OptionParser.Values> , <list>)
    """
    # Callback for the state directory that checks to make sure
    # the directory exists and is writable
    def cb_sd(o , ostr , val , p):
        if not val:
            val = o.default
        if not os.path.isdir(val) or not os.access(val , os.F_OK | os.W_OK):
            raise OptionValueError(
                'State directory must be a writable directory')
        setattr(p.values , o.dest , val)

    usage = 'Usage: %prog [options] (command [cmd-arg [cmd-arg ...]] | ' \
        '\'command [cmd-arg [cmd-arg ...]]\')'
    p = OptionParser(usage=usage)
    p.disable_interspersed_args()
    gState = OptionGroup(p , 'State Options' , 'These options pertain to '
        'state and lock maintenance')
    gFailure = OptionGroup(p , 'Failure Options' , 'These are the options '
        'for how to handle failures when they occur.')
    gRetry = OptionGroup(p , 'Retry Options' , 'These options relate to '
        'the built in retry mechanism.  The retry mechanism only relates '
        'to the cwrap locking function and how many times to try if a '
        'previous instance of this script is already running.')
    gCommand = OptionGroup(p , 'Command Options' , 'These options define how '
        'the command is interpreted and run.')
    gSyslog = OptionGroup(p , 'Syslog Options' , 'Options for logging errors '
        'via syslog in addition to normal output.')

    p.add_option('-V' , '--version' , dest='version' , default=False ,
        action='store_true' ,
        help='Print the version number and exit [default: %default]')

    gState.add_option('-d' , '--state-directory' , dest='stateDir' , 
        action='callback' , default='/var/tmp' , metavar='PATH' , 
        callback=cb_sd ,  type='string' ,
        help='The directory to write the state file to. [default: %default]')
    gState.add_option('-F' , '--lock-file' , dest='lockFile' , default=None ,
        metavar='FILE' , 
        help='Set a specific lock file to use.  This is useful when running '
        '2 different scripts, or the same script with different command-line '
        'opts, that cannot run at the same time. '
        '[default: <auto-gen lockfile>]')
    gRetry.add_option('-r' , '--num-retries' , dest='numRetries' , type='int' ,
        default=0 , metavar='INT' , 
        help='The number of times to retry this if a previous instance is '
        'running.  The script will retry every "-s" seconds if this is '
        'greater than zero. [default: %default]')
    gRetry.add_option('-s' , '--retry-seconds' , dest='retrySecs' , type='int' ,
        default=10 , metavar='INT' ,
        help='This is the number of seconds between retries.  This only '
        'matters if the "-r" option is set to greater than zero. '
        '[default: %default]')
    gRetry.add_option('-i' , '--ignore-retry-fails' , dest='ignoreRetFail' ,
        action='store_true' , default=False ,
        help='Ignore the failures which occur because this tried to run '
        'while a previous instance was still running.  Basically, an error '
        'will not be printed if the number of run retries are exceeded. '
        '[default: %default]')
    gFailure.add_option('-n' , '--num-fails' , dest='numFails' , type='int' ,
        default=1 , metavar='INT' ,
        help='The number of consecutive failures that must occur '
        'before a report is printed [default: %default]')
    gFailure.add_option('-f' , '--first-fail' , dest='fstFail' , 
        action='store_true' , default=False ,
        help='The default is to print a failure report only when a multiple '
        'of the failure threshold is reached. If this is set, an email will '
        '*also* be sent on the first failure. [default: %default]')
    gCommand.add_option('-p' , '--path' , dest='PATH' , 
        default=os.environ['PATH'] , metavar='CMD_PATH' ,
        help='Use this for command path instead of the environment $PATH. '
        '[default: %default]')
    gCommand.add_option('-g' , '--single-string' , dest='singStr' , 
        action='store_true' , default=False ,
        help='This says that you are passing in a command line as a single '
        'string.  This means that the entire command (with args) MUST be '
        'encased in quotes!  This is handy if you want to encapsulate '
        'a pipe ("|") '
        'in your command to be run: "cat /tmp/file | grep stuff".  That '
        'would be passed directly to a subshell for execution '
        '[default: %default]')
    gCommand.add_option('-t' , '--timeout' , dest='timeout' ,
        metavar='INT' , default=0 , type='int' ,
        help='The number of seconds to allow the command to run before '
        'terminating.  Set to zero to disable timeouts. [default: %default]')
    gCommand.add_option('-q' , '--quiet' , dest='quiet' , default=False ,
        action='store_true' ,
        help='Only output error reports.  If the command runs successfully, '
        'nothing will be printed, even if the command had stdout or stderr '
        'output. [default: %default]')
    gSyslog.add_option('-S' , '--syslog' , dest='syslog' , default=False ,
        action='store_true' ,
        help='Turn on syslogging.  This will log *all* failures to syslog. '
        'This is useful for diagnosing intermittent issues that don\'t '
        'necessarily reach the "--num-fails" limit.  See "-C" and "-P" for '
        'facility and priority options [default: %default]')
    gSyslog.add_option('-C' , '--syslog-facility' , dest='sFacility' , 
        metavar='FACILITY' ,
        default='LOG_LOCAL7' , help='The syslog facility to use.  See '
        'the facility section in "man syslog" for a list of choices. You '
        'must use "--syslog" with this. [default: %default]')
    gSyslog.add_option('-P' , '--syslog-priority' , dest='sPriority' , 
        metavar='PRIORITY' ,
        default='LOG_INFO' , help='Sets the priority for the syslog messages. '
        'See the level section in "man syslog" for a list of choices. You '
        'must use "--syslog" with this. [default: %default]')

    p.add_option_group(gState)
    p.add_option_group(gRetry)
    p.add_option_group(gFailure)
    p.add_option_group(gCommand)
    p.add_option_group(gSyslog)
    opts , cmdList = p.parse_args()
    if opts.version:
        print 'cwrap: %s' % __version__
        sys.exit(0)
    # Eval the syslog priority and facility if syslogging is on
    if opts.syslog:
        try:
            fac = eval('syslog.%s' % opts.sFacility)
        except:
            p.error('Invalid syslog facility, "%s", see "man syslog" for '
                'facility choices')
        try:
            pri = eval('syslog.%s' % opts.sPriority)
        except:
            p.error('Invalid syslog priority, "%s", see "man syslog" for '
                 'priority (level) options')
        try:
            syslog.openlog('cwrap' , syslog.LOG_PID , fac)
        except Exception , e:
            p.error('Error opening syslog with facility %s: %s' % (
                opts.sFacility , e))
        LOGPRI = pri
    if opts.numFails < 1:
        p.error('Number of fails must be at least 1.')
    if opts.numRetries < 0:
        p.error('Number of retries can not be less than 0')
    if opts.retrySecs < 1:
        p.error('Retry seconds cannot be less than 1')
    if opts.timeout < 0:
        p.error('Command timeout must be set to a positive integer or zero to'
            'disable it')
    if not cmdList:
        p.error('You must specify a command to be executed')
    return p.parse_args()

def sigHandler(frame , num):
    global STATEFILE
    STATEFILE.close()
    sys.exit(0)

def log(msg):
    syslog.syslog(LOGPRI , msg)

def main():
    global STATEFILE
    opts , cmdList = getOpts()
    oldPath = os.environ['PATH']
    if oldPath != opts.PATH:
        os.environ['PATH'] = opts.PATH
    stFName = StateFile.getStateFileName(opts , cmdList)
    stFh = None
    try:
        stFh = StateFile.getStateFile(opts , cmdList)
    except FileCreationError , e:
        if opts.ignoreRetFail:
            # Option is set to ignore this type of failure.  Exit as if
            # successful.  This will keep a message from being sent by
            # cron
            sys.exit(0)
        else:
            print >> sys.stderr , e
            sys.exit(E_FC)
    STATEFILE = stFh
    # Set the signal handlers
    signal.signal(signal.SIGINT , sigHandler)
    signal.signal(signal.SIGHUP , sigHandler)
    signal.signal(signal.SIGTERM , sigHandler)
    # Either get the command state from a previous run or create it
    comSt = stFh.getObject()
    if not comSt:
        comSt = CommandState(opts , cmdList)
    # Set any new command line opts
    comSt.opts = opts
    comSt.run()
    stFh.saveObject(comSt)
    stFh.close()
    os.environ['PATH'] = oldPath
    try:
        syslog.closelog()
    except:
        pass

if __name__ == '__main__':
    main()
