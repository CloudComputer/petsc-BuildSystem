import config.base

import os
import re

class Configure(config.base.Configure):
  def __init__(self, framework, libraries = []):
    config.base.Configure.__init__(self, framework)
    self.headerPrefix = ''
    self.substPrefix  = ''
    self.libraries    = libraries
    self.setCompilers = self.framework.require('config.setCompilers', self)
    self.compilers    = self.framework.require('config.compilers',    self)
    self.headers      = self.framework.require('config.headers',      self)
    self.headers.headers.append('dlfcn.h')
    self.libraries.append(('dl', 'dlopen'))
    return

  def getIncludeArgument(self, include):
    '''Return the proper include line argument for the given filename
       - If the path is empty, return it unchanged
       - If starts with - then return unchanged
       - Otherwise return -I<include>'''
    if not include:
      return ''
    if include[0] == '-':
      return include
    return '-I'+include

  def getLibArgument(self, library):
    '''Return the proper link line argument for the given filename library
       - If the path is empty, return it unchanged
       - If the path ends in ".lib" return it unchanged
       - If the path ends in ".so" return it unchanged       
       - If the path is absolute and the filename is "lib"<name>, return -L<dir> -l<name>
       - If the filename is "lib"<name>, return -l<name>
       - If the path is absolute, return it unchanged
       - If the filename is <dir>/<name>.so, it remains unchanged
       - If starts with - then return unchanged
       - Otherwise return -l<library>'''
    if not library:
      return ''
    if library.startswith('${CC_LINKER_SLFLAG}'):
      return library
    if library.startswith('${FC_LINKER_SLFLAG}'):
      return library
    if library[0] == '-':
      return library
    if len(library) > 3 and library[-4:] == '.lib':
      return library
    if os.path.basename(library).startswith('lib'):
      name = Configure.getLibName(library)
      if ((len(library) > 2 and library[1] == ':') or os.path.isabs(library)):
        flagName  = self.language[-1].replace('+', 'x')+'SharedLinkerFlag'
        flagSubst = self.language[-1].replace('+', 'x').upper()+'_LINKER_SLFLAG'
        if hasattr(self.setCompilers, flagName) and not getattr(self.setCompilers, flagName) is None:
          return getattr(self.setCompilers, flagName)+os.path.dirname(library)+' -L'+os.path.dirname(library)+' -l'+name
        if flagSubst in self.framework.argDB:
          return self.framework.argDB[flagSubst]+os.path.dirname(library)+' -L'+os.path.dirname(library)+' -l'+name
        else:
          return '-L'+os.path.dirname(library)+' -l'+name
      else:
        return '-l'+name
    if os.path.splitext(library)[1] == '.so':
      return library
    if os.path.isabs(library):
      return library
    return '-l'+library

  def getLibName(library):
    if os.path.basename(library).startswith('lib'):
      return os.path.splitext(os.path.basename(library))[0][3:]
    return library
  getLibName = staticmethod(getLibName)

  def getDefineName(self, library):
    return 'HAVE_LIB'+self.getLibName(library).upper().replace('-','_').replace('=','_')

  def haveLib(self, library):
    return self.getDefineName(library) in self.defines

  def check(self, libName, funcName, libDir = None, otherLibs = '', prototype = '', call = '', fortranMangle = 0):
    '''Checks that the library "libName" contains "funcName", and if it does adds "libName" to $LIBS and defines HAVE_LIB"libName"
       - libDir may be a list of directories
       - libName may be a list of library names'''
    self.framework.log.write('Checking for function '+funcName+' in library '+str(libName)+'\n')
    # Handle Fortran mangling
    if fortranMangle:
      funcName = self.compilers.mangleFortranFunction(funcName)
    includes = '/* Override any gcc2 internal prototype to avoid an error. */\n'
    # Handle C++ mangling
    if self.language[-1] == 'C++':
      includes += '''
      #ifdef __cplusplus
      extern "C"
      #endif'''
    # Construct prototype
    if prototype:
      includes += prototype
    else:
      includes += '/* We use char because int might match the return type of a gcc2 builtin and then its argument prototype would still apply. */\n'
      includes += 'char '+funcName+'();\n'
    # Construct function call
    if call:
      body = call
    else:
      body = funcName+'()\n'
    # Setup link line
    oldLibs = self.framework.argDB['LIBS']
    if libDir:
      if not isinstance(libDir, list): libDir = [libDir]
      for dir in libDir:
        self.framework.argDB['LIBS'] += ' -L'+dir
    if not isinstance(libName, list): libName = [libName]
    for lib in libName:
      self.framework.argDB['LIBS'] += ' '+self.getLibArgument(lib)
    self.framework.argDB['LIBS'] += ' '+otherLibs
    self.pushLanguage(self.language[-1])
    if self.checkLink(includes, body):
      found = 1
      self.framework.argDB['LIBS'] = oldLibs
      for lib in libName:
        self.framework.argDB['LIBS'] += ' '+self.getLibArgument(lib)
        strippedlib = os.path.splitext(os.path.basename(lib))[0]
        if strippedlib: self.addDefine(self.getDefineName(strippedlib), 1)
    else:
      found = 0
      self.framework.argDB['LIBS'] = oldLibs
    self.popLanguage()
    return found

  def checkShared(self, includes, initFunction, checkFunction, finiFunction = None, checkLink = None, libraries = [], initArgs = '&argc, &argv', boolType = 'int', noCheckArg = 0):
    '''Determine whether a library is shared
       - initFunction(int *argc, char *argv[]) is called to initialize some static data
       - checkFunction(int *check) is called to verify that the static data wer set properly
       - finiFunction() is called to finalize the data, and may be omitted
       - checkLink may be given as ana alternative to the one in base.Configure'''
    isShared = 0
    if checkLink is None: checkLink = self.checkLink

    # Fix these flags
    oldFlags                         = self.framework.argDB['LDFLAGS']
    self.framework.argDB['LDFLAGS'] += ' -shared'
    for lib in libraries:
      self.framework.argDB['LDFLAGS'] += ' -Wl,-rpath,'+os.path.dirname(lib)

    # Make a library which calls initFunction(), and returns checkFunction()
    if noCheckArg:
      checkCode = 'isInitialized = '+checkFunction+'();'
    else:
      checkCode = checkFunction+'(&isInitialized);'
    codeBegin = '''
#ifdef __cplusplus
extern "C"
#endif
int init(int argc,  char *argv[]) {
'''
    body      = '''
  %s isInitialized;

  %s(%s);
  %s
  return (int) isInitialized;
''' % (boolType, initFunction, initArgs, checkCode)
    codeEnd   = '\n}\n'
    if not checkLink(includes, body, cleanup = 0, codeBegin = codeBegin, codeEnd = codeEnd):
      if os.path.isfile(self.compilerObj): os.remove(self.compilerObj)
      self.framework.argDB['LDFLAGS'] = oldFlags
      raise RuntimeError('Could not complete shared library check')
    if os.path.isfile(self.compilerObj): os.remove(self.compilerObj)
    os.rename(self.linkerObj, 'lib1.so')

    # Make a library which calls checkFunction()
    codeBegin = '''
#ifdef __cplusplus
extern "C"
#endif
int checkInit(void) {
'''
    body      = '''
  %s isInitialized;

  %s
  return (int) isInitialized;
''' % (boolType, checkCode)
    codeEnd   = '\n}\n'
    if not checkLink(includes, body, cleanup = 0, codeBegin = codeBegin, codeEnd = codeEnd):
      if os.path.isfile(self.compilerObj): os.remove(self.compilerObj)
      self.framework.argDB['LDFLAGS'] = oldFlags
      self.framework.log.write('Could not complete shared library check\n')
      return 0
    if os.path.isfile(self.compilerObj): os.remove(self.compilerObj)
    os.rename(self.linkerObj, 'lib2.so')

    self.framework.argDB['LDFLAGS'] = oldFlags

    # Make an executable that dynamically loads and calls both libraries
    #   If the check returns true in the second library, the static data was shared
    guard = self.headers.getDefineName('dlfcn.h')
    if self.headers.headerPrefix:
      guard = self.headers.headerPrefix+'_'+guard
    defaultIncludes = '''
#include <stdio.h>
#include <stdlib.h>
#ifdef %s
  #include <dlfcn.h>
#endif
    ''' % guard
    body = '''
  int   argc    = 1;
  char *argv[1] = {"conftest"};
  void *lib;
  int (*init)(int, char **);
  int (*checkInit)(void);

  lib = dlopen("./lib1.so", RTLD_LAZY);
  if (!lib) {
    fprintf(stderr, "Could not open lib1.so: %s\\n", dlerror());
    exit(1);
  }
  init = (int (*)(int, char **)) dlsym(lib, "init");
  if (!init) {
    fprintf(stderr, "Could not find initialization function\\n");
    exit(1);
  }
  if (!(*init)(argc, argv)) {
    fprintf(stderr, "Could not initialize library\\n");
    exit(1);
  }
  lib = dlopen("./lib2.so", RTLD_LAZY);
  if (!lib) {
    fprintf(stderr, "Could not open lib2.so: %s\\n", dlerror());
    exit(1);
  }
  checkInit = (int (*)(void)) dlsym(lib, "checkInit");
  if (!checkInit) {
    fprintf(stderr, "Could not find initialization check function\\n");
    exit(1);
  }
  if (!(*checkInit)()) {
    fprintf(stderr, "Did not link with shared library\\n");
    exit(2);
  }
    '''
    oldLibs = self.framework.argDB['LIBS']
    if self.haveLib('dl'):
      self.framework.argDB['LIBS'] += ' -ldl'
    if self.checkRun(defaultIncludes, body):
      isShared = 1
    self.framework.argDB['LIBS'] = oldLibs
    if os.path.isfile('lib1.so'): os.remove('lib1.so')
    if os.path.isfile('lib2.so'): os.remove('lib2.so')
    if not isShared:
      self.framework.log.write('Library was not shared\n')
    return isShared

  def checkMath(self):
    '''Check for sin() in libm, the math library'''
    if not self.check('','sin', prototype = 'double sin(double);', call = 'sin(1.0);\n'):
      self.check('m', 'sin', prototype = 'double sin(double);', call = 'sin(1.0);\n')
    return

  def checkSuffix(self):
    '''(Belongs in config.libraries) Determine the suffix used for libraries'''
    # If MS Windows's kernel32.lib is available then use lib for the suffix, otherwise use a.
    # Cygwin w32api uses libkernel32.a for this symbol.
    oldLibs = self.framework.argDB['LIBS']
    found = self.check(['kernel32.lib'],'GetCurrentProcess',prototype='int __stdcall GetCurrentProcess(void);\n')
    if not found:
      found = self.check(['PSDK/kernel32.lib'],'GetCurrentProcess',prototype='int __stdcall GetCurrentProcess(void);\n')
    if found:
      self.suffix = 'lib'
    else:
      self.suffix = 'a'
    self.addSubstitution('LIB_SUFFIX', self.suffix)
    self.framework.argDB['LIBS'] = oldLibs
    return

  def configure(self):
    self.framework.argDB['LIBS'] = ''
    map(lambda args: self.executeTest(self.check, list(args)), self.libraries)
    self.executeTest(self.checkMath)
    self.executeTest(self.checkSuffix)
    self.addArgumentSubstitution('LDFLAGS', 'LDFLAGS')
    self.addArgumentSubstitution('LIBS',    'LIBS')
    return
