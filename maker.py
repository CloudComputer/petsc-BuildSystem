import script

import os

class Make(script.Script):
  '''Template for individual project makefiles. All project makes start with a local RDict.'''
  def __init__(self, builder = None):
    import RDict
    import project
    import sys

    script.Script.__init__(self, sys.argv[1:], RDict.RDict())
    if builder is None:
      import sourceDatabase
      import config.framework

      self.framework  = config.framework.Framework(self.clArgs+['-noOutput'], self.argDB)
      self.builder    = __import__('builder').Builder(self.framework, sourceDatabase.SourceDB(self.root))
    else:
      self.builder    = builder
      self.framework  = builder.framework
    self.builder.pushLanguage('C')
    return

  def getMake(self, url):
    '''Return the Make object corresponding to the project with the given URL'''
    # FIX THIS: For now ignore RDict project info, and just use a fixed path
    import install.urlMapping

    self.logPrint('Adding project dependency: '+url)
    path   = os.path.join(self.argDB['defaultRoot'], install.urlMapping.UrlMappingNew.getRepositoryPath(url))
    oldDir = os.getcwd()
    os.chdir(path)
    make   = self.getModule(path, 'make').Make()
    make.run(setupOnly = 1)
    os.chdir(oldDir)
    return make

  def setupHelp(self, help):
    import nargs

    help = script.Script.setupHelp(self, help)
    help.addArgument('Make', 'forceConfigure', nargs.ArgBool(None, 0, 'Force a reconfiguration', isTemporary = 1))
    help.addArgument('Make', 'defaultRoot', nargs.ArgDir(None, '../..', 'Directory root for all packages', isTemporary = 1))
    help.addArgument('Make', 'prefix', nargs.ArgDir(None, None, 'Root for installation of libraries and binaries', mustExist = 0, isTemporary = 1))
    return help

  def getPrefix(self):
    if not hasattr(self, '_prefix'):
      if 'prefix' in self.argDB:
        return self.argDB['prefix']
      return None
    return self._prefix
  def setPrefix(self, prefix):
    self._prefix = prefix
  prefix = property(getPrefix, setPrefix, doc = 'The installation root')

  def setupDependencies(self, sourceDB):
    '''Override this method to setup dependencies between source files'''
    return

  def setup(self):
    script.Script.setup(self)
    self.builder.setup()
    self.setupDependencies(self.builder.sourceDB)
    return

  def shouldConfigure(self, builder, framework):
    '''Determine whether we should reconfigure
       - If the configure header or substitution files are missing
       - If -forceConfigure is given
       - If configure.py has changed
       - If the database does not contain a cached configure'''
    if framework.header and not os.path.isfile(framework.header):
      self.logPrint('Reconfiguring due to absence of configure header: '+str(framework.header))
      return 1
    if not reduce(lambda x,y: x and y, [os.path.isfile(pair[1]) for pair in framework.substFiles], True):
      self.logPrint('Reconfiguring due to absence of configure generated files: '+str([os.path.isfile(pair[1]) for pair in framework.substFiles]))
      return 1
    if self.argDB['forceConfigure']:
      self.logPrint('Reconfiguring forced')
      return 1
    if (not 'configure.py' in self.builder.sourceDB or
        not self.builder.sourceDB['configure.py'][0] == self.builder.sourceDB.getChecksum('configure.py')):
      self.logPrint('Reconfiguring due to changed configure.py')
      return 1
    if not 'configureCache' in self.argDB:
      self.logPrint('Reconfiguring due to absence of configure cache')
      return 1
    return 0

  def setupConfigure(self, framework):
    framework.header = os.path.join('include', 'config.h')
    try:
      framework.addChild(self.getModule(self.root, 'configure').Configure(framework))
    except ImportError, e:
      self.logPrint('Configure module not present: '+str(e))
      return 0
    return 1

  def configure(self, builder):
    '''Run configure if necessary and return the configuration Framework'''
    import cPickle

    if not self.setupConfigure(self.framework):
      return
    doConfigure = self.shouldConfigure(builder, self.framework)
    if not doConfigure:
      framework = self.loadConfigure()
      if framework is None:
        doConfigure = 1
      else:
        self.framework         = framework
        self.builder.framework = self.framework
    if doConfigure:
      self.logPrint('Starting new configuration')
      self.framework.configure()
      self.builder.sourceDB.updateSource('configure.py')
      cache = cPickle.dumps(self.framework)
      self.argDB['configureCache'] = cache
      self.logPrint('Wrote configure to cache: size '+str(len(cache)))
    else:
      self.logPrint('Using cached configure')
      self.framework.cleanup()
    return self.framework

  def updateDependencies(self, sourceDB):
    '''Override this method to update dependencies between source files. This method saves the database'''
    sourceDB.save()
    return

  def build(self, builder, setupOnly = 0):
    '''Override this method to execute all build operations. This method does nothing.'''
    return

  def install(self, builder, argDB):
    '''Override this method to execute all install operations. This method does nothing.'''
    return

  def outputBanner(self):
    import time

    self.log.write(('='*80)+'\n')
    self.log.write(('='*80)+'\n')
    self.log.write('Starting Build Run at '+time.ctime(time.time())+'\n')
    self.log.write('Build Options: '+str(self.clArgs)+'\n')
    self.log.write('Working directory: '+os.getcwd()+'\n')
    self.log.write(('='*80)+'\n')
    return

  def executeSection(self, section, *args):
    import time

    self.log.write(('='*80)+'\n')
    self.logPrint('SECTION: '+str(section.im_func.func_name)+' in '+self.getRoot()+' from '+str(section.im_class.__module__)+'('+str(section.im_func.func_code.co_filename)+':'+str(section.im_func.func_code.co_firstlineno)+') at '+time.ctime(time.time()), debugSection = 'screen', indent = 0)
    if section.__doc__: self.logWrite('  '+section.__doc__+'\n')
    return section(*args)

  def run(self, setupOnly = 0):
    self.setup()
    self.logPrint('Starting Build', debugSection = 'build')
    self.executeSection(self.configure, self.builder)
    self.build(self.builder, setupOnly)
    self.updateDependencies(self.builder.sourceDB)
    self.executeSection(self.install, self.builder, self.argDB)
    self.logPrint('Ending Build', debugSection = 'build')
    return 1

try:
  import sets
except ImportError:
  import config.setsBackport

class SIDLMake(Make):
  def __init__(self, builder = None):
    import re

    Make.__init__(self, builder)
    self.implRE       = re.compile(r'^((.*)_impl\.(c|h|py)|__init__\.py)$')
    self.dependencies = {}
    return

  def getSidl(self):
    if not hasattr(self, '_sidl'):
      self._sidl = [os.path.join(self.root, 'sidl', f) for f in filter(lambda s: os.path.splitext(s)[1] == '.sidl', os.listdir(os.path.join(self.root, 'sidl')))]
    return self._sidl
  def setSidl(self, sidl):
    self._sidl = sidl
    return
  sidl = property(getSidl, setSidl, doc = 'The list of input SIDL files')

  def getIncludes(self):
    if not hasattr(self, '_includes'):
      self._includes = []
      [self._includes.extend([os.path.join(make.getRoot(), 'sidl', f) for f in sidlFiles]) for make, sidlFiles in self.dependencies.values()]
    return self._includes
  def setIncludes(self, includes):
    self._includes = includes
    return
  includes = property(getIncludes, setIncludes, doc = 'The list of SIDL include files')

  def getClientLanguages(self):
    if not hasattr(self, '_clientLanguages'):
      self._clientLanguages = ['Python']
    return self._clientLanguages
  def setClientLanguages(self, clientLanguages):
    self._clientLanguages = clientLanguages
    return
  clientLanguages = property(getClientLanguages, setClientLanguages, doc = 'The list of client languages')

  def getServerLanguages(self):
    if not hasattr(self, '_serverLanguages'):
      self._serverLanguages = ['Python']
    return self._serverLanguages
  def setServerLanguages(self, serverLanguages):
    self._serverLanguages = serverLanguages
    return
  serverLanguages = property(getServerLanguages, setServerLanguages, doc = 'The list of server languages')

  def setupHelp(self, help):
    import nargs

    help = Make.setupHelp(self, help)
    help.addArgument('SIDLMake', 'bootstrap', nargs.ArgBool(None, 0, 'Generate the boostrap client', isTemporary = 1))
    help.addArgument('SIDLMake', 'excludeLanguages=<languages>', nargs.Arg(None, [], 'Do not load configurations from RDict for the given languages', isTemporary = 1))
    help.addArgument('SIDLMake', 'excludeBasenames=<names>', nargs.Arg(None, [], 'Do not load configurations from RDict for these SIDL base names', isTemporary = 1))
    return help

  def setupConfigure(self, framework):
    framework.require('config.libraries', None)
    framework.require('config.python', None)
    framework.require('config.ase', None)
    return Make.setupConfigure(self, framework)

  def configure(self, builder):
    framework = Make.configure(self, builder)
    if framework is None:
      for depMake, depSidlFiles in self.dependencies.values():
        self.logWrite('Loading configure for '+depMake.getRoot())
        framework = depMake.loadConfigure()
        if not framework is None:
          self.framework         = framework
          self.builder.framework = framework
          break
    if framework is None:
      raise RuntimeError('Could not find a configure framework')
    self.compilers = framework.require('config.compilers', None)
    self.libraries = framework.require('config.libraries', None)
    self.python    = framework.require('config.python', None)
    self.ase       = framework.require('config.ase', None)
    return framework

  def addDependency(self, url, sidlFile):
    if not url in self.dependencies:
      self.dependencies[url] = (self.getMake(url), sets.Set())
      for depMake, depSidlFiles in self.dependencies[url][0].dependencies.values():
        for depSidlFile in depSidlFiles:
          self.addDependency(depMake.project.getUrl(), depSidlFile)
    self.dependencies[url][1].add(sidlFile)
    return

  def loadConfiguration(self, builder, name):
    if len(self.argDB['excludeLanguages']) and len(self.argDB['excludeBasenames']):
      for language in self.argDB['excludeLanguages']:
        if name.startswith(language):
          for basename in self.argDB['excludeBasenames']:
            if name.endswith(basename):
              return
    elif len(self.argDB['excludeLanguages']):
      for language in self.argDB['excludeLanguages']:
        if name.startswith(language):
          return
    elif len(self.argDB['excludeBasenames']):
      for basename in self.argDB['excludeBasenames']:
        if name.endswith(basename):
          return
    builder.loadConfiguration(name)
    return

  def setupSIDL(self, builder, sidlFile):
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    self.loadConfiguration(builder, 'SIDL '+baseName)
    builder.pushConfiguration('SIDL '+baseName)
    builder.pushLanguage('SIDL')
    compiler            = builder.getCompilerObject()
    compiler.clients    = self.clientLanguages
    compiler.clientDirs = dict([(lang, 'client-'+lang.lower()) for lang in self.clientLanguages])
    compiler.servers    = self.serverLanguages
    compiler.serverDirs = dict([(lang, 'server-'+lang.lower()+'-'+baseName) for lang in self.serverLanguages])
    compiler.includes   = self.includes+list(builder.sourceDB.getDependencies(sidlFile))
    builder.popLanguage()
    builder.popConfiguration()
    return

  def getSIDLClientDirectory(self, builder, sidlFile, language):
    baseName  = os.path.splitext(os.path.basename(sidlFile))[0]
    clientDir = None
    builder.pushConfiguration('SIDL '+baseName)
    builder.pushLanguage('SIDL')
    if language in builder.getCompilerObject().clientDirs:
      clientDir = builder.getCompilerObject().clientDirs[language]
    builder.popLanguage()
    builder.popConfiguration()
    return clientDir

  def getSIDLServerDirectory(self, builder, sidlFile, language):
    baseName  = os.path.splitext(os.path.basename(sidlFile))[0]
    serverDir = None
    builder.pushConfiguration('SIDL '+baseName)
    builder.pushLanguage('SIDL')
    if language in builder.getCompilerObject().serverDirs:
      serverDir = builder.getCompilerObject().serverDirs[language]
    builder.popLanguage()
    builder.popConfiguration()
    return serverDir

  def addDependencyIncludes(self, compiler, language):
    for depMake, depSidlFiles in self.dependencies.values():
      for depSidlFile in depSidlFiles:
        try:
          compiler.includeDirectories.add(os.path.join(depMake.getRoot(), self.getSIDLClientDirectory(depMake.builder, depSidlFile, language)))
        except KeyError, e:
          if e.args[0] == language:
            self.logPrint('Dependency '+depSidlFile+' has no client for '+language, debugSection = 'screen')
          else:
            raise e
    return

  def addDependencyLibraries(self, linker, language):
    for depMake, depSidlFiles in self.dependencies.values():
      for depSidlFile in depSidlFiles:
        self.logPrint('Checking dependency '+depSidlFile+' for a '+language+' client', debugSection = 'build')
        try:
          clientConfig = depMake.builder.pushConfiguration(language+' Stub '+os.path.splitext(os.path.basename(depSidlFile))[0])
          if 'Linked ELF' in clientConfig.outputFiles:
            files = sets.Set([os.path.join(depMake.getRoot(), lib) for lib in clientConfig.outputFiles['Linked ELF']])
            self.logPrint('Adding '+str(files)+'from dependency '+depSidlFile, debugSection = 'build')
            linker.libraries.update(files)
          depMake.builder.popConfiguration()
        except KeyError, e:
          if e.args[0] == language:
            self.logPrint('Dependency '+depSidlFile+' has no client for '+language, debugSection = 'screen')
          else:
            raise e
    return

  def setupIOR(self, builder, sidlFile, language):
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    self.loadConfiguration(builder, language+' IOR '+baseName)
    builder.pushConfiguration(language+' IOR '+baseName)
    compiler = builder.getCompilerObject()
    compiler.includeDirectories.add(self.getSIDLServerDirectory(builder, sidlFile, language))
    for depFile in builder.sourceDB.getDependencies(sidlFile):
      dir = self.getSIDLServerDirectory(builder, depFile, language)
      if not dir is None:
        compiler.includeDirectories.add(dir)
    self.addDependencyIncludes(compiler, language)
    builder.popConfiguration()
    return

  def setupPythonClient(self, builder, sidlFile, language):
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    self.loadConfiguration(builder, language+' Stub '+baseName)
    builder.pushConfiguration(language+' Stub '+baseName)
    compiler = builder.getCompilerObject()
    linker   = builder.getLinkerObject()
    compiler.includeDirectories.update(self.python.include)
    compiler.includeDirectories.add(self.getSIDLClientDirectory(builder, sidlFile, language))
    self.addDependencyIncludes(compiler, language)
    linker.libraries.update(self.ase.lib)
    linker.libraries.update(self.python.lib)
    builder.popConfiguration()
    return

  def setupPythonSkeleton(self, builder, sidlFile, language):
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    self.loadConfiguration(builder, language+' Skeleton '+baseName)
    builder.pushConfiguration(language+' Skeleton '+baseName)
    compiler = builder.getCompilerObject()
    compiler.includeDirectories.update(self.python.include)
    compiler.includeDirectories.add(self.getSIDLServerDirectory(builder, sidlFile, language))
    for depFile in builder.sourceDB.getDependencies(sidlFile):
      dir = self.getSIDLServerDirectory(builder, depFile, language)
      if not dir is None:
        compiler.includeDirectories.add(dir)
    self.addDependencyIncludes(compiler, language)
    builder.popConfiguration()
    return

  def setupPythonServer(self, builder, sidlFile, language):
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    self.setupIOR(builder, sidlFile, language)
    self.setupPythonSkeleton(builder, sidlFile, language)
    self.loadConfiguration(builder, language+' Server '+baseName)
    builder.pushConfiguration(language+' Server '+baseName)
    linker   = builder.getLinkerObject()
    if not baseName == self.ase.baseName:
      linker.libraries.update(self.ase.lib)
    linker.libraries.update(self.python.lib)
    builder.popConfiguration()
    return

  def setupCxxClient(self, builder, sidlFile, language):
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    self.loadConfiguration(builder, language+' Stub '+baseName)
    builder.pushConfiguration(language+' Stub '+baseName)
    compiler = builder.getCompilerObject()
    linker   = builder.getLinkerObject()
    compiler.includeDirectories.add(self.getSIDLClientDirectory(builder, sidlFile, language))
    self.addDependencyIncludes(compiler, language)
    linker.libraries.update(self.ase.lib)
    builder.popConfiguration()
    return

  def setupCxxSkeleton(self, builder, sidlFile, language):
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    self.loadConfiguration(builder, language+' Skeleton '+baseName)
    builder.pushConfiguration(language+' Skeleton '+baseName)
    compiler = builder.getCompilerObject()
    compiler.includeDirectories.add(self.getSIDLServerDirectory(builder, sidlFile, language))
    compiler.includeDirectories.add(self.getSIDLClientDirectory(builder, sidlFile, language))
    for depFile in builder.sourceDB.getDependencies(sidlFile):
      dir = self.getSIDLServerDirectory(builder, depFile, language)
      if not dir is None:
        compiler.includeDirectories.add(dir)
    self.addDependencyIncludes(compiler, language)
    builder.popConfiguration()
    return

  def setupCxxServer(self, builder, sidlFile, language):
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    self.setupIOR(builder, sidlFile, language)
    self.setupCxxSkeleton(builder, sidlFile, language)
    self.loadConfiguration(builder, language+' Server '+baseName)
    builder.pushConfiguration(language+' Server '+baseName)
    linker   = builder.getLinkerObject()
    self.addDependencyLibraries(linker, language)
    if not baseName == self.ase.baseName:
      linker.libraries.update(self.ase.lib)
    builder.popConfiguration()
    return

  def setupBootstrapClient(self, builder, sidlFile, language):
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    self.loadConfiguration(builder, language+' Stub '+baseName)
    builder.pushConfiguration(language+' Stub '+baseName)
    builder.popConfiguration()
    return

  def buildSIDL(self, builder, sidlFile):
    self.logPrint('Building '+sidlFile)
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    config   = builder.pushConfiguration('SIDL '+baseName)
    builder.pushLanguage('SIDL')
    builder.compile([sidlFile])
    builder.popLanguage()
    builder.popConfiguration()
    builder.saveConfiguration('SIDL '+baseName)
    self.logPrint('generatedFiles: '+str(config.outputFiles), debugSection = 'sidl')
    return config.outputFiles

  def editServer(self, builder, sidlFile):
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    builder.pushConfiguration('SIDL '+baseName)
    builder.pushLanguage('SIDL')
    compiler            = builder.getCompilerObject()
    builder.popLanguage()
    builder.popConfiguration()
    for serverDir in compiler.serverDirs.values():
      for root, dirs, files in os.walk(serverDir):
        if os.path.basename(root) == 'SCCS':
          continue
        builder.versionControl.edit(builder.versionControl.getClosedFiles([os.path.join(root, f) for f in filter(lambda a: self.implRE.match(a), files)]))
    return

  def checkinServer(self, builder, sidlFile):
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    builder.pushConfiguration('SIDL '+baseName)
    builder.pushLanguage('SIDL')
    compiler = builder.getCompilerObject()
    builder.popLanguage()
    builder.popConfiguration()
    vc        = builder.versionControl
    added     = 0
    reverted  = 0
    committed = 0
    for serverDir in compiler.serverDirs.values():
      for root, dirs, files in os.walk(serverDir):
        if os.path.basename(root) == 'SCCS':
          continue
        implFiles = filter(lambda a: self.implRE.match(a), files)
        added     = added or vc.add(builder.versionControl.getNewFiles([os.path.join(root, f) for f in implFiles]))
        reverted  = reverted or vc.revert(builder.versionControl.getUnchangedFiles([os.path.join(root, f) for f in implFiles]))
        committed = committed or vc.commit(builder.versionControl.getChangedFiles([os.path.join(root, f) for f in implFiles]))
    if added or committed:
      vc.changeSet()
    return

  def buildIOR(self, builder, sidlFile, language, generatedSource):
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    config   = builder.pushConfiguration(language+' IOR '+baseName)
    for f in generatedSource:
      builder.compile([f])
    builder.popConfiguration()
    builder.saveConfiguration(language+' IOR '+baseName)
    if 'ELF' in config.outputFiles:
      return config.outputFiles['ELF']
    return sets.Set()

  def buildPythonClient(self, builder, sidlFile, language, generatedSource):
    if not 'Client '+language in generatedSource:
      return sets.Set()
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    config   = builder.pushConfiguration(language+' Stub '+baseName)
    for f in generatedSource['Client '+language]['Cxx']:
      builder.compile([f])
      builder.link([builder.getCompilerTarget(f)], shared = 1)
    builder.popConfiguration()
    builder.saveConfiguration(language+' Stub '+baseName)
    if 'Linked ELF' in config.outputFiles:
      return config.outputFiles['Linked ELF']
    return sets.Set()

  def buildPythonSkeleton(self, builder, sidlFile, language, generatedSource):
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    config   = builder.pushConfiguration(language+' Skeleton '+baseName)
    for f in generatedSource:
      builder.compile([f])
    builder.popConfiguration()
    builder.saveConfiguration(language+' Skeleton '+baseName)
    if 'ELF' in config.outputFiles:
      return config.outputFiles['ELF']
    return sets.Set()

  def buildPythonServer(self, builder, sidlFile, language, generatedSource):
    if not 'Server IOR Python' in generatedSource:
      return sets.Set()
    baseName    = os.path.splitext(os.path.basename(sidlFile))[0]
    iorObjects  = self.buildIOR(builder, sidlFile, language, generatedSource['Server IOR Python']['Cxx'])
    skelObjects = self.buildPythonSkeleton(builder, sidlFile, language, generatedSource['Server '+language]['Cxx'])
    config      = builder.pushConfiguration(language+' Server '+baseName)
    library     = os.path.join(os.getcwd(), 'lib', 'lib-'+language.lower()+'-'+baseName+'.so')
    if not os.path.isdir(os.path.dirname(library)):
      os.makedirs(os.path.dirname(library))
    builder.link(iorObjects.union(skelObjects), library, shared = 1)
    builder.popConfiguration()
    builder.saveConfiguration(language+' Server '+baseName)
    if 'Linked ELF' in config.outputFiles:
      return config.outputFiles['Linked ELF']
    return sets.Set()

  def buildCxxClient(self, builder, sidlFile, language, generatedSource):
    if not 'Client '+language in generatedSource:
      return sets.Set()
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    config   = builder.pushConfiguration(language+' Stub '+baseName)
    for f in generatedSource['Client '+language]['Cxx']:
      builder.compile([f])
      builder.link([builder.getCompilerTarget(f)], shared = 1)
    builder.popConfiguration()
    builder.saveConfiguration(language+' Stub '+baseName)
    if 'Linked ELF' in config.outputFiles:
      return config.outputFiles['Linked ELF']
    return sets.Set()

  def buildCxxImplementation(self, builder, sidlFile, language, generatedSource):
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    config   = builder.pushConfiguration(language+' Skeleton '+baseName)
    for f in generatedSource:
      builder.compile([f])
    builder.popConfiguration()
    builder.saveConfiguration(language+' Skeleton '+baseName)
    if 'ELF' in config.outputFiles:
      return config.outputFiles['ELF']
    return sets.Set()

  def buildCxxServer(self, builder, sidlFile, language, generatedSource):
    baseName    = os.path.splitext(os.path.basename(sidlFile))[0]
    iorObjects  = self.buildIOR(builder, sidlFile, language, generatedSource['Server IOR Cxx']['Cxx'])
    implObjects = self.buildCxxImplementation(builder, sidlFile, language, generatedSource['Server '+language]['Cxx'])
    config      = builder.pushConfiguration(language+' Server '+baseName)
    library     = os.path.join(os.getcwd(), 'lib', 'lib-'+language.lower()+'-'+baseName+'.so')
    linker      = builder.getLinkerObject()
    if not os.path.isdir(os.path.dirname(library)):
      os.makedirs(os.path.dirname(library))
    for depSidlFile in builder.sourceDB.getDependencies(sidlFile)+(sidlFile,):
      self.logPrint('Checking dependency '+depSidlFile+' for a '+language+' client', debugSection = 'build')
      clientConfig = builder.pushConfiguration(language+' Stub '+os.path.splitext(os.path.basename(depSidlFile))[0])
      if 'Linked ELF' in clientConfig.outputFiles:
        files = clientConfig.outputFiles['Linked ELF']
        self.logPrint('Adding '+str(files)+'from dependency '+depSidlFile, debugSection = 'build')
        linker.libraries.update(files)
      builder.popConfiguration()
    builder.link(iorObjects.union(implObjects), library, shared = 1)
    builder.popConfiguration()
    builder.saveConfiguration(language+' Server '+baseName)
    if 'Linked ELF' in config.outputFiles:
      return config.outputFiles['Linked ELF']
    return sets.Set()

  def buildBootstrapClient(self, builder, sidlFile, language, generatedSource):
    baseName = os.path.splitext(os.path.basename(sidlFile))[0]
    config   = builder.pushConfiguration(language+' Stub '+baseName)
    builder.popConfiguration()
    builder.saveConfiguration(language+' Stub '+baseName)
    return sets.Set()

  def setupBootstrap(self, builder):
    '''If bootstrap flag is enabled, setup varaibles to generate the bootstrap client'''
    if self.argDB['bootstrap']:
      self.serverLanguages = []
      self.clientLanguages = ['Bootstrap']
      builder.shouldCompile.force(self.sidl)
    return

  def buildSetup(self, builder):
    '''This is a utility method used when only setup is necessary'''
    self.setupBootstrap(builder)
    for f in self.sidl:
      self.executeSection(self.setupSIDL, builder, f)
      for language in self.serverLanguages:
        self.executeSection(getattr(self, 'setup'+language+'Server'), builder, f, language)
      for language in self.clientLanguages:
        self.executeSection(getattr(self, 'setup'+language+'Client'), builder, f, language)
    return

  def build(self, builder, setupOnly = 0):
    import shutil

    self.setupBootstrap(builder)
    for f in self.sidl:
      self.executeSection(self.setupSIDL, builder, f)
      for language in self.serverLanguages:
        self.executeSection(getattr(self, 'setup'+language+'Server'), builder, f, language)
      for language in self.clientLanguages:
        self.executeSection(getattr(self, 'setup'+language+'Client'), builder, f, language)
      if not setupOnly:
        # We here require certain keys to be present in generatedSource, e.g. 'Server IOR Python'.
        # These keys can be checked for, and if absent the SIDL file would be compiled
        generatedSource = self.executeSection(self.buildSIDL, builder, f)
	if self.project.getUrl() == 'bk://ase.bkbits.net/Runtime':
          for language in self.serverLanguages:
            self.executeSection(getattr(self, 'build'+language+'Server'), builder, f, language, generatedSource)
        for language in self.clientLanguages:
          self.executeSection(getattr(self, 'build'+language+'Client'), builder, f, language, generatedSource)
	if not self.project.getUrl() == 'bk://ase.bkbits.net/Runtime':
          for language in self.serverLanguages:
            self.executeSection(getattr(self, 'build'+language+'Server'), builder, f, language, generatedSource)
        self.argDB.save(force = 1)
        shutil.copy(self.argDB.saveFilename, self.argDB.saveFilename+'.bkp')
        builder.sourceDB.save()
        shutil.copy(str(builder.sourceDB.filename), str(builder.sourceDB.filename)+'.bkp')
    return

  def install(self, builder, argDB):
    '''Install all necessary data for this project into the current RDict
       - FIX: Build project graph
       - FIX: Update language specific information'''
    if not 'installedprojects' in argDB:
      return
    for sidlFile in self.sidl:
      baseName = os.path.splitext(os.path.basename(sidlFile))[0]
      #self.loadConfiguration(builder, 'SIDL '+baseName)
      for language in self.serverLanguages:
        self.project.appendPath(language, os.path.join(self.root, self.getSIDLServerDirectory(builder, sidlFile, language)))
      for language in self.clientLanguages:
        self.project.appendPath(language, os.path.join(self.root, self.getSIDLClientDirectory(builder, sidlFile, language)))
    # self.compileTemplate.install()
    projects = filter(lambda project: not project.getUrl() == self.project.getUrl(), argDB['installedprojects'])
    argDB['installedprojects'] = projects+[self.project]
    self.logPrint('Installed project '+str(self.project), debugSection = 'install')
    # Update project in 'projectDependenceGraph'
    return
