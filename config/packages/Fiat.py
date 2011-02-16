import config.package
import os, sys

class Configure(config.package.Package):
  def __init__(self, framework):
    config.package.Package.__init__(self, framework)
    self.download = ['http://ftp.mcs.anl.gov/pub/petsc/externalpackages/fiat-dev.tar.gz', 'http://www.fenicsproject.org/pub/software/fiat/FIAT-0.3.0.tar.gz']
    self.downloadname      = self.name.lower()
    self.archIndependent   = 1
    self.worksonWindows    = 1
    self.downloadonWindows = 1
    self.liblist           = [['Lagrange.py']]
    self.libdir            = os.path.join('lib', 'python', 'site-packages')
    self.altlibdir         = os.path.join('lib', 'python'+'.'.join(map(str, sys.version_info[0:2])), 'site-packages')
    return

  def setupDependencies(self, framework):
    config.package.Package.setupDependencies(self, framework)
    self.deps = []
    return

  def Install(self):
    import shutil
    # We could make a check of the md5 of the current configure framework
    self.logPrintBox('Installing FIAT')
    # Copy FIAT into $PETSC_ARCH/lib/python/site-packages
    installLoc = os.path.join(self.installDir, self.altlibdir)
    packageDir = os.path.join(installLoc, 'FIAT')
    if not os.path.isdir(installLoc):
      os.makedirs(installLoc)
    if os.path.exists(packageDir):
      shutil.rmtree(packageDir)
    shutil.copytree(os.path.join(self.packageDir, 'FIAT'), packageDir)
    self.framework.actions.addArgument('FIAT', 'Install', 'Installed FIAT into '+self.installDir)
    return self.installDir

  def configureLibrary(self):
    '''Find an installation ando check if it can work with PETSc'''
    import sys
    self.framework.log.write('==================================================================================\n')
    self.framework.log.write('Checking for a functional '+self.name+'\n')

    for location, rootDir, lib, incDir in self.generateGuesses():
      try:
        libDir = os.path.dirname(lib[0])
        self.framework.logPrint('Checking location '+location)
        self.framework.logPrint('Added directory '+libDir+' to Python path')
        sys.path.insert(0, libDir)
        import FIAT
        import FIAT.ufc_simplex
        import FIAT.lagrange
        import FIAT.quadrature
        return
      except ImportError, e:
        self.framework.logPrint('ERROR: Could not import FIAT: '+str(e))
    raise RuntimeError('Could not find a functional '+self.name+'\n')
