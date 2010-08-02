from __future__ import generators
import config.package

class Configure(config.package.Package):
  def __init__(self, framework):
    config.package.Package.__init__(self, framework)
    self.download        = ['http://ftp.mcs.anl.gov/pub/petsc/externalpackages/cusp_1_2.tar.gz']
    self.includes        = ['cusp/version.h']
    self.includedir      = ''
    self.forceLanguage   = 'CUDA'
    self.cxx             = 0
    self.archIndependent = 1
    self.worksonWindows  = 1
    return

  def setupDependencies(self, framework):
    config.package.Package.setupDependencies(self, framework)
    self.thrust = framework.require('config.packages.thrust', self)
    self.deps   = [self.thrust]
    return

  def Install(self):
    import shutil
    import os
    self.framework.log.write('cuspDir = '+self.packageDir+' installDir '+self.installDir+'\n')
    srcdir = os.path.join(self.packageDir, 'cusp')
    destdir = os.path.join(self.installDir, 'include', 'cusp')
    try:
      if os.path.isdir(destdir): shutil.rmtree(destdir)
      shutil.copytree(srcdir,destdir)
    except RuntimeError,e:
      raise RuntimeError('Error installing Cusp include files: '+str(e))
    return self.installDir

  def getSearchDirectories(self):
    import os
    yield os.path.join('/usr','local','cuda')
    yield ''
    return

  def configurePC(self):
    self.pushLanguage('CUDA')
    if self.checkLink('#include <cusp/version.h>\n#include <cusp/precond/smoothed_aggregation.h>\n', ''):
      self.addDefine('HAVE_CUSP_SMOOTHED_AGGREGATION','1')
    self.popLanguage()
    return

  def configureLibrary(self):
    '''Calls the regular package configureLibrary and then does an additional tests needed by CUSP'''
    config.package.Package.configureLibrary(self)
    self.executeTest(self.configurePC)
    return
