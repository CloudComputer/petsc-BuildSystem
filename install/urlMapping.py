import base

import os
import urlparse
# Fix parsing for nonstandard schemes
urlparse.uses_netloc.extend(['bk', 'ssh'])

class UrlMapping (base.Base):
  def __init__(self, clArgs = None, argDB = None, stamp = None):
    base.Base.__init__(self, clArgs, argDB)
    self.stamp   = stamp
    self.urlMaps = []
    self.setupUrlMapping()
    return

  def setupUrlMapping(self):
    self.urlMaps.append(self.bootstrapUrlMap)
    if not self.argDB.has_key('urlMappingModules') or not self.argDB['urlMappingModules']:
      self.argDB['urlMappingModules'] = []
    elif not isinstance(self.argDB['urlMappingModules'], list):
      self.argDB['urlMappingModules'] = [self.argDB['urlMappingModules']]
    for moduleName in self.argDB['urlMappingModules']:
      __import__(moduleName, globals(), locals(), ['setupUrlMapping']).setupUrlMapping(self, self.urlMaps)
    return

  def checkBootstrap(self):
    '''If the compiler or runtime is not available, we will have to bootstrap and this function returns true'''
    try:
      import SIDL.Loader
      import SIDLLanguage.Parser
    except ImportError:
      return 1
    return 0

  def bootstrapUrlMap(self, url):
    if self.checkBootstrap():
      (scheme, location, path, parameters, query, fragment) = urlparse.urlparse(url)
      if scheme == 'bk':
        path = os.path.join('/pub', 'petsc', self.getRepositoryPath(url))
        return (1, urlparse.urlunparse(('ftp', 'ftp.mcs.anl.gov', path, parameters, query, fragment)))
    return (0, url)

  def getRepositoryName(self, url):
    '''Return the repository name from a project URL. This is the base filename that should be used for tarball distributions.'''
    (scheme, location, path, parameters, query, fragment) = urlparse.urlparse(url)
    return os.path.basename(path)

  def getRepositoryPath(self, url, noBase = 0):
    '''Return the repository path from a project URL. This is the name that should be used for alternate retrieval.
    - You can omit the repository name itself by giving the noBase flag'''
    (scheme, location, path, parameters, query, fragment) = urlparse.urlparse(url)
    sitename = location.split('.')[0]
    pathname = path[1:]
    if noBase: pathname = os.path.dirname(pathname)
    return os.path.join(sitename, pathname)

  def getMappedUrl(self, url):
    '''Return a new URL produced by a URL map function. Users can register new maps by adding to the list self.urlMaps'''
    # We do not allow BuildSystem to be mapped
    if url == 'bk://sidl.bkbits.net/BuildSystem': return url
    for map in self.urlMaps:
      ret, newUrl = map(url)
      if ret: return newUrl
    return url

  def getInstallRoot(self, url, isBackup = 0):
    '''Guess the install root from the project URL. Note this method does not map the URL.'''
    root = self.getRepositoryPath(url)
    if isBackup:
      root = os.path.join('backup', root)
    return os.path.abspath(root)
