#!/usr/bin/env python
import user
import base

import os

class Machine (object):
  def __init__(self, host, dir = os.path.join('/sandbox', 'petsc', 'petsc-3'), rsh = 'ssh -1', rcp = 'scp -q -B -oProtocol=1'):
    '''Creates a machine description
       - "host" is the host account, e.g. petsc@smash.mcs.anl.gov
       - "dir" is the root directory of the install
       - "rsh" is the remote shell command, e.g. ssh -1
       - "rcp" is the remote copy command, e.g. scp -q -B -oProtocol=1'''
    self.dir  = dir
    self.rsh  = rsh
    self.rcp  = rcp
    self.host = host
    return

class RemoteBuild (base.Base):
  def __init__(self, machine, clArgs = None, argDB = None):
    base.Base.__init__(self, clArgs, argDB)
    self.machine = machine
    self.host    = machine.host
    self.dir     = machine.dir
    self.rsh     = machine.rsh
    self.rcp     = machine.rcp
    return

  def setupArgDB(self, argDB, clArgs):
    '''Setup argument types, using the database created by base.Base'''
    import nargs

    argDB.setType('mode',   nargs.Arg(None, 0, 'Action, e.g. build, log, ...', isTemporary = 1), forceLocal = 1)
    argDB.setType('dryRun', nargs.ArgBool(None, 0, 'Display but do not execute commands', isTemporary = 1), forceLocal = 1)

    self.argDB['mode']          = 'build'
    self.argDB['debugLevel']    = 3
    self.argDB['debugSections'] = []

    base.Base.setupArgDB(self, argDB, clArgs)
    return argDB

  def executeShellCommand(self, command, checkCommand = None):
    '''Execute a shell command returning the output, and optionally provide a custom error checker'''
    if self.argDB['dryRun']:
      print command
      return
    return base.Base.executeShellCommand(self, command, checkCommand)

  def clean(self):
    '''Remove all PETSc 3 files'''
    command = [self.rsh, self.host, '-n', 'rm -rf '+self.dir]
    output  = self.executeShellCommand(' '.join(command))
    command = [self.rsh, self.host, '-n', 'mkdir -m775 '+self.dir]
    output  = self.executeShellCommand(' '.join(command))
    return

  def getBootstrap(self):
    '''Right now, we get bootstrap.py from our PETSc 2 repository, but later we should get it from the webpage'''
    command = [self.rcp, os.path.join('/sandbox', 'petsc', 'petsc-test', 'python', 'BuildSystem', 'install', 'bootstrap.py'),  self.host+':'+self.dir]
    output  = self.executeShellCommand(' '.join(command))
    return

  def bootstrap(self):
    '''Run the bootstrap installer
       - TODO: Remove the dependence on csh of the pipe'''
    self.getBootstrap()
    command = [self.rsh, self.host, '-n', '"cd '+self.dir+'; ./bootstrap.py -batch |& tee bootstrap.log"']
    output  = self.executeShellCommand(' '.join(command))
    return

  def install(self, package, args = []):
    '''Install a normal package'''
    command = [self.rsh, self.host, '-n', '"cd '+self.dir+';', os.path.join('.', 'BuildSystem', 'install', 'installer.py'), package]+args+['|& tee installer.log"']
    output  = self.executeShellCommand(' '.join(command))
    return

  def build(self):
    self.clean()
    self.bootstrap()
    self.install('bk://mpib.bkbits.net/mpib-dev', ['--with-mpi-dir=/home/petsc/soft/linux-rh73/mpich-1.2.4'])
    return

  def copyLog(self):
    '''Copy all logs made during the build to a default location'''
    command = [self.rcp, self.host+':'+os.path.join(self.dir, 'bootstrap.log'), os.path.join('/home', 'petsc', 'logs', 'nightly')]
    output  = self.executeShellCommand(' '.join(command))
    command = [self.rcp, self.host+':'+os.path.join(self.dir, 'installer.log'), os.path.join('/home', 'petsc', 'logs', 'nightly')]
    output  = self.executeShellCommand(' '.join(command))
    command = [self.rcp, self.host+':'+os.path.join(self.dir, 'make.log'), os.path.join('/home', 'petsc', 'logs', 'nightly')]
    output  = self.executeShellCommand(' '.join(command))
    return

  def run(self):
    '''Fork off the build or log copying'''
    # Launch child
    if os.fork():
      # Parent returns
      return
    if self.argDB['mode'] == 'build':
      self.build()
    elif self.argDB['mode'] == 'log':
      self.copyLog()
    else:
      import sys
      sys.exit('Invalid mode: '+self.argDB['mode'])
    return

if __name__ == '__main__':
  import sys
  RemoteBuild(Machine('petsc@smash.mcs.anl.gov'), sys.argv[1:]).run()