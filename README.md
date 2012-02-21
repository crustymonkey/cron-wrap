# cron-wrap #

## ABOUT ##
"Obviously, you're not a golfer".  But you are probably a sysadmin.

The cwrap.py script is meant to be used as a wrapper for cron jobs.  The idea
here is that you use this script to wrap whatever would be a normal cronjob
for you to perform functions based on what options are specified.  I think
this is best explained with an example.

I have a cronjob that runs every minute.  First, I don't want
"overlap", a second instance is run while the first one is still running, 
if a single run takes a long time.  Solved.  The nature of my cronjob (just
a script that is being run) is such that there will be an occasional failure,
but an occasional failure, in this case, can be ignored.  Instead, I only want
to know when the script has failed 5 times in a row.  Solved.  By default,
cwrap.py will also swallow all the output for the occasional fails, but I
at least want a record of those failures so that I can determine whether
the intermittent fails are happening more frequently and constitute a
different problem.  Solved (by turning on the syslog option).

This script may not be useful for everyone, but for some out there, it will
save you a lot of time, effort and probably emails in your inbox.

## INSTALL ##
Just follow the basic install practice for a Python package.

1. If you have a .tar.gz, extract that first
        
        tar -xvzf cron-wrap*.tar.gz

2. Now, just cd into the directory and install it

        cd cron-wrap*
        python setup.py install

This should install the script in either /usr/bin or /usr/local/bin depending
on your platform.  A man page should also be installed.

You can also install this using *pip* or *easy_install*

        pip install cron-wrap

## DOCUMENTATION ##
You have a few options here.  Run the script with either "-h" or "--help" to
see a list of all the options with a brief description.  Otherwise, 
"man cwrap.py" will give you a bit more info.  You can also check the web page
at http://stuffivelearned.org/doku.php?id=programming:python:cwrap

## BUGS AND FEATURE REQUESTS ##
Please use the [github page](https://github.com/crustymonkey/cron-wrap) for 
reporting bugs and filing feature requests.

## CODE CONTRIBUTIONS ##
I'm also open to fixes and additions from others.  If you wish to contribute,
please use the "fork" and "pull request" mechanisms of 
[github](http://github.com) for this.
