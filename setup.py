#!/usr/bin/python
# coding: utf8
# /*##########################################################################
#
# Copyright (c) 2015-2017 European Synchrotron Radiation Facility
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# ###########################################################################*/

__copyright__ = "European Synchrotron Radiation Facility, Grenoble, France"
__date__ = "23/05/2017"
__status__ = "stable"


import io
import sys
import os
import platform
import shutil
import logging
import glob

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("pyFAI.setup")


from distutils.command.clean import clean as Clean
from distutils.command.build import build as _build
try:
    from setuptools import Command
    from setuptools.command.build_py import build_py as _build_py
    from setuptools.command.build_ext import build_ext
    from setuptools.command.sdist import sdist
    logger.info("Use setuptools")
except ImportError:
    try:
        from numpy.distutils.core import Command
    except ImportError:
        from distutils.core import Command
    from distutils.command.build_py import build_py as _build_py
    from distutils.command.build_ext import build_ext
    from distutils.command.sdist import sdist
    logger.info("Use distutils")

try:
    import sphinx
    import sphinx.util.console
    sphinx.util.console.color_terminal = lambda: False
    from sphinx.setup_command import BuildDoc
except ImportError:
    sphinx = None


PROJECT = "pyFAI"

if "LANG" not in os.environ and sys.platform == "darwin" and sys.version_info[0] > 2:
    print("""WARNING: the LANG environment variable is not defined,
an utf-8 LANG is mandatory to use setup.py, you may face unexpected UnicodeError.
export LANG=en_US.utf-8
export LC_ALL=en_US.utf-8
""")


def get_version():
    """Returns current version number from version.py file"""
    import version
    return version.strictversion


def get_readme():
    """Returns content of README.rst file"""
    dirname = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(dirname, "README.rst")
    with io.open(filename, "r", encoding="utf-8") as fp:
        long_description = fp.read()
    return long_description

# double check classifiers on https://pypi.python.org/pypi?%3Aaction=list_classifiers
classifiers = ["Development Status :: 5 - Production/Stable",
               "Intended Audience :: Developers",
               "Programming Language :: Python :: 2",
               "Programming Language :: Python :: 3",
               "Programming Language :: Cython",
               "Environment :: Console",
               "Environment :: X11 Applications :: Qt",
               "Intended Audience :: Science/Research",
               "License :: OSI Approved :: MIT License",
               "Topic :: Software Development :: Libraries :: Python Modules",
               "Operating System :: Microsoft :: Windows",
               "Operating System :: Unix",
               "Operating System :: MacOS :: MacOS X",
               "Operating System :: POSIX",
               "Topic :: Scientific/Engineering :: Physics"
               ]

# ########## #
# version.py #
# ########## #

class build_py(_build_py):
    """
    Enhanced build_py which copies version.py to <PROJECT>._version.py
    """
    def find_package_modules(self, package, package_dir):
        modules = _build_py.find_package_modules(self, package, package_dir)
        if package == PROJECT:
            modules.append((PROJECT, '_version', 'version.py'))
        return modules


########
# Test #
########

class PyTest(Command):
    """Command to start tests running the script: run_tests.py -i"""
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import subprocess
        errno = subprocess.call([sys.executable, 'run_tests.py', '-i'])
        if errno != 0:
            raise SystemExit(errno)


# ################### #
# build_doc command   #
# ################### #

if sphinx is None:
    class SphinxExpectedCommand(Command):
        """Command to inform that sphinx is missing"""
        user_options = []

        def initialize_options(self):
            pass

        def finalize_options(self):
            pass

        def run(self):
            raise RuntimeError(
                'Sphinx is required to build or test the documentation.\n'
                'Please install Sphinx (http://www.sphinx-doc.org).')


class BuildMan(Command):
    """Command to build man pages"""
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def entry_points_iterator(self):
        """Iterate other entry points available on the project."""
        entry_points = self.distribution.entry_points
        console_scripts = entry_points.get('console_scripts', [])
        gui_scripts = entry_points.get('gui_scripts', [])
        scripts = []
        scripts.extend(console_scripts)
        scripts.extend(gui_scripts)
        for script in scripts:
            elements = script.split("=")
            target_name = elements[0].strip()
            elements = elements[1].split(":")
            module_name = elements[0].strip()
            function_name = elements[1].strip()
            yield target_name, module_name, function_name

    def run(self):
        build = self.get_finalized_command('build')
        path = sys.path
        path.insert(0, os.path.abspath(build.build_lib))

        env = dict((str(k), str(v)) for k, v in os.environ.items())
        env["PYTHONPATH"] = os.pathsep.join(path)

        import subprocess

        status = subprocess.call(["mkdir", "-p", "build/man"])
        if status != 0:
            raise RuntimeError("Fail to create build/man directory")

        import tempfile
        import stat
        script_name = None

        entry_points = self.entry_points_iterator()
        for target_name, module_name, function_name in entry_points:
            logger.info("Build man for entry-point target '%s'" % target_name)
            # help2man expect a single executable file to extract the help
            # we create it, execute it, and delete it at the end

            py3 = sys.version_info >= (3, 0)
            try:
                # create a launcher using the right python interpreter
                script_fid, script_name = tempfile.mkstemp(prefix="%s_" % target_name, text=True)
                script = os.fdopen(script_fid, 'wt')
                script.write("#!%s\n" % sys.executable)
                script.write("import %s as app\n" % module_name)
                script.write("app.%s()\n" % function_name)
                script.close()
                # make it executable
                mode = os.stat(script_name).st_mode
                os.chmod(script_name, mode + stat.S_IEXEC)

                # execute help2man
                man_file = "build/man/%s.1" % target_name
                command_line = ["help2man", script_name, "-o", man_file]
                if not py3:
                    # Before Python 3.4, ArgParser --version was using
                    # stderr to print the version
                    command_line.append("--no-discard-stderr")

                p = subprocess.Popen(command_line, env=env)
                status = p.wait()
                if status != 0:
                    raise RuntimeError("Fail to generate '%s' man documentation" % target_name)
            finally:
                # clean up the script
                if script_name is not None:
                    os.remove(script_name)


if sphinx is not None:
    class BuildDocCommand(BuildDoc):
        """Command to build documentation using sphinx.

        Project should have already be built.
        """

        def run(self):
            # make sure the python path is pointing to the newly built
            # code so that the documentation is built on this and not a
            # previously installed version

            build = self.get_finalized_command('build')
            sys.path.insert(0, os.path.abspath(build.build_lib))

            # # Copy .ui files to the path:
            # dst = os.path.join(
            #     os.path.abspath(build.build_lib), "silx", "gui")
            # if not os.path.isdir(dst):
            #     os.makedirs(dst)
            # for i in os.listdir("gui"):
            #     if i.endswith(".ui"):
            #         src = os.path.join("gui", i)
            #         idst = os.path.join(dst, i)
            #         if not os.path.exists(idst):
            #             shutil.copy(src, idst)

            # Build the Users Guide in HTML and TeX format
            for builder in ['html', 'latex']:
                self.builder = builder
                self.builder_target_dir = os.path.join(self.build_dir, builder)
                self.mkpath(self.builder_target_dir)
                BuildDoc.run(self)
            sys.path.pop(0)
else:
    BuildDocCommand = SphinxExpectedCommand


# ################### #
# test_doc command    #
# ################### #

if sphinx is not None:
    class TestDocCommand(BuildDoc):
        """Command to test the documentation using sphynx doctest.

        http://www.sphinx-doc.org/en/1.4.8/ext/doctest.html
        """
        def run(self):
            # make sure the python path is pointing to the newly built
            # code so that the documentation is built on this and not a
            # previously installed version

            build = self.get_finalized_command('build')
            sys.path.insert(0, os.path.abspath(build.build_lib))

            # Build the Users Guide in HTML and TeX format
            for builder in ['doctest']:
                self.builder = builder
                self.builder_target_dir = os.path.join(self.build_dir, builder)
                self.mkpath(self.builder_target_dir)
                BuildDoc.run(self)
            sys.path.pop(0)

else:
    TestDocCommand = SphinxExpectedCommand

# ############################# #
# numpy.distutils Configuration #
# ############################# #

def configuration(parent_package='', top_path=None):
    """Recursive construction of package info to be used in setup().

    See http://docs.scipy.org/doc/numpy/reference/distutils.html#numpy.distutils.misc_util.Configuration
    """
    try:
        from numpy.distutils.misc_util import Configuration
    except ImportError:
        raise ImportError(
            "To install this package, you must install numpy first\n"
            "(See https://pypi.python.org/pypi/numpy)")
    config = Configuration(None, parent_package, top_path)
    config.set_options(
        ignore_setup_xxx_py=True,
        assume_default_configuration=True,
        delegate_options_to_subpackages=True,
        quiet=True)
    config.add_subpackage(PROJECT)
    return config

# ############## #
# Compiler flags #
# ############## #


class Build(_build):
    """Command to support more user options for the build."""

    user_options = [
        ('no-openmp', None,
         "do not use OpenMP for compiled extension modules"),
        ('openmp', None,
         "use OpenMP for the compiled extension modules"),
        ('no-cython', None,
         "do not compile Cython extension modules (use default compiled c-files)"),
        ('force-cython', None,
         "recompile all Cython extension modules"),
    ]
    user_options.extend(_build.user_options)

    boolean_options = ['no-openmp', 'openmp', 'no-cython', 'force-cython']
    boolean_options.extend(_build.boolean_options)

    def initialize_options(self):
        _build.initialize_options(self)
        self.no_openmp = None
        self.openmp = None
        self.no_cython = None
        self.force_cython = None

    def finalize_options(self):
        _build.finalize_options(self)
        self.finalize_cython_options(min_version='0.21.1')
        self.finalize_openmp_options()

    def _parse_env_as_bool(self, key):
        content = os.environ.get(key, "")
        value = content.lower()
        if value in ["1", "true", "yes", "y"]:
            return True
        if value in ["0", "false", "no", "n"]:
            return False
        if value in ["none", ""]:
            return None
        msg = "Env variable '%s' contains '%s'. But a boolean or an empty \
            string was expected. Variable ignored."
        logger.warning(msg, key, content)
        return None

    def finalize_openmp_options(self):
        """Check if extensions must be compiled with OpenMP.

        The result is stored into the object.
        """
        if self.openmp:
            use_openmp = True
        elif self.no_openmp:
            use_openmp = False
        else:
            env_force_cython = self._parse_env_as_bool("WITH_OPENMP")
            if env_force_cython is not None:
                use_openmp = env_force_cython
            else:
                # Use it by default
                use_openmp = True

        if use_openmp:
            if platform.system() == "Darwin":
                # By default Xcode5 & XCode6 do not support OpenMP, Xcode4 is OK.
                osx = tuple([int(i) for i in platform.mac_ver()[0].split(".")])
                if osx >= (10, 8):
                    logger.warning("OpenMP support ignored. Your platform do not support it")
                    use_openmp = False

        # Remove attributes used by distutils parsing
        # use 'use_openmp' instead
        del self.no_openmp
        del self.openmp
        self.use_openmp = use_openmp

    def finalize_cython_options(self, min_version=None):
        """
        Check if cythonization must be used for the extensions.

        The result is stored into the object.
        """

        if self.force_cython:
            use_cython = "force"
        elif self.no_cython:
            use_cython = "no"
        else:
            env_force_cython = self._parse_env_as_bool("FORCE_CYTHON")
            env_with_cython = self._parse_env_as_bool("WITH_CYTHON")
            if env_force_cython is True:
                use_cython = "force"
            elif env_with_cython is True:
                use_cython = "yes"
            elif env_with_cython is False:
                use_cython = "no"
            else:
                # Use it by default
                use_cython = "yes"

        if use_cython in ["force", "yes"]:
            try:
                import Cython.Compiler.Version
                if min_version and Cython.Compiler.Version.version < min_version:
                    msg = "Cython version is too old. At least version is %s \
                        expected. Cythonization is skipped."
                    logger.warning(msg, str(min_version))
                    use_cython = "no"
            except ImportError:
                msg = "Cython is not available. Cythonization is skipped."
                logger.warning(msg)
                use_cython = "no"

        # Remove attribute used by distutils parsing
        # use 'use_cython' and 'force_cython' instead
        del self.no_cython
        self.force_cython = use_cython == "force"
        self.use_cython = use_cython in ["force", "yes"]


class BuildExt(build_ext):
    """Handle extension compilation.

    Command-line argument and environment can custom:

    - The use of cython to cythonize files, else a default version is used
    - Build extension with support of OpenMP (by default it is enabled)
    - If building with MSVC, compiler flags are converted from gcc flags.
    """

    COMPILE_ARGS_CONVERTER = {'-fopenmp': '/openmp'}

    LINK_ARGS_CONVERTER = {'-fopenmp': ''}

    description = 'Build pyFAI extensions'

    def finalize_options(self):
        build_ext.finalize_options(self)
        build_obj = self.distribution.get_command_obj("build")
        self.use_openmp = build_obj.use_openmp
        self.use_cython = build_obj.use_cython
        self.force_cython = build_obj.force_cython

    def patch_with_default_cythonized_files(self, ext):
        """Replace cython files by .c or .cpp files in extension's sources.

        It replaces the *.pyx and *.py source files of the extensions
        to either *.cpp or *.c source files.
        No compilation is performed.

        :param Extension ext: An extension to patch.
        """
        new_sources = []
        for source in ext.sources:
            base, file_ext = os.path.splitext(source)
            if file_ext in ('.pyx', '.py'):
                if ext.language == 'c++':
                    cythonized = base + '.cpp'
                else:
                    cythonized = base + '.c'
                if not os.path.isfile(cythonized):
                    raise RuntimeError("Source file not found: %s. Cython is needed" % cythonized)
                print("Use default cythonized file for %s" % source)
                new_sources.append(cythonized)
            else:
                new_sources.append(source)
        ext.sources = new_sources

    def patch_extension(self, ext):
        """
        Patch an extension according to requested Cython and OpenMP usage.

        :param Extension ext: An extension
        """
        # Cytonize
        if not self.use_cython:
            self.patch_with_default_cythonized_files(ext)
        else:
            from Cython.Build import cythonize
            patched_exts = cythonize(
                [ext],
                compiler_directives={'embedsignature': True},
                force=self.force_cython,
                compile_time_env={"HAVE_OPENMP": self.use_openmp}
            )
            ext.sources = patched_exts[0].sources

        # Remove OpenMP flags if OpenMP is disabled
        if not self.use_openmp:
            ext.extra_compile_args = [
                f for f in ext.extra_compile_args if f != '-fopenmp']
            ext.extra_link_args = [
                f for f in ext.extra_link_args if f != '-fopenmp']

        # Convert flags from gcc to MSVC if required
        if self.compiler.compiler_type == 'msvc':
            ext.extra_compile_args = [self.COMPILE_ARGS_CONVERTER.get(f, f)
                                      for f in ext.extra_compile_args]
            ext.extra_link_args = [self.LINK_ARGS_CONVERTER.get(f, f)
                                   for f in ext.extra_link_args]

    def build_extensions(self):
        for ext in self.extensions:
            self.patch_extension(ext)
        build_ext.build_extensions(self)


################################################################################
# Clean command
################################################################################


class CleanCommand(Clean):
    description = "Remove build artifacts from the source tree"

    def expand(self, path_list):
        """Expand a list of path using glob magic.

        :param list[str] path_list: A list of path which may contains magic
        :rtype: list[str]
        :returns: A list of path without magic
        """
        path_list2 = []
        for path in path_list:
            if glob.has_magic(path):
                iterator = glob.iglob(path)
                path_list2.extend(iterator)
            else:
                path_list2.append(path)
        return path_list2

    def run(self):
        Clean.run(self)
        # really remove the directories
        # and not only if they are empty
        to_remove = [self.build_base]
        to_remove = self.expand(to_remove)

        if not self.dry_run:
            for path in to_remove:
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    logger.info("removing '%s'", path)
                except OSError:
                    pass

################################################################################
# Debian source tree
################################################################################


class sdist_debian(sdist):
    """
    Tailor made sdist for debian
    * remove auto-generated doc
    * remove cython generated .c files
    * remove cython generated .c files
    * remove .bat files
    * include .l man files
    """
    @staticmethod
    def get_debian_name():
        import version
        name = "%s_%s" % (PROJECT, version.debianversion)
        return name

    def prune_file_list(self):
        sdist.prune_file_list(self)
        to_remove = ["doc/build", "doc/pdf", "doc/html", "pylint", "epydoc"]
        print("Removing files for debian")
        for rm in to_remove:
            self.filelist.exclude_pattern(pattern="*", anchor=False, prefix=rm)

        # this is for Cython files specifically: remove C & html files
        search_root = os.path.dirname(os.path.abspath(__file__))
        for root, _, files in os.walk(search_root):
            for afile in files:
                if os.path.splitext(afile)[1].lower() == ".pyx":
                    base_file = os.path.join(root, afile)[len(search_root) + 1:-4]
                    self.filelist.exclude_pattern(pattern=base_file + ".c")
                    self.filelist.exclude_pattern(pattern=base_file + ".cpp")
                    self.filelist.exclude_pattern(pattern=base_file + ".html")

        # do not include third_party files
        self.filelist.exclude_pattern(pattern="*", prefix="pyFAI/third_party")

    def make_distribution(self):
        self.prune_file_list()
        sdist.make_distribution(self)
        dest = self.archive_files[0]
        dirname, basename = os.path.split(dest)
        base, ext = os.path.splitext(basename)
        while ext in [".zip", ".tar", ".bz2", ".gz", ".Z", ".lz", ".orig"]:
            base, ext = os.path.splitext(base)
        if ext:
            dest = "".join((base, ext))
        else:
            dest = base
        # sp = dest.split("-")
        # base = sp[:-1]
        # nr = sp[-1]
        debian_arch = os.path.join(dirname, self.get_debian_name() + ".orig.tar.gz")
        os.rename(self.archive_files[0], debian_arch)
        self.archive_files = [debian_arch]
        print("Building debian .orig.tar.gz in %s" % self.archive_files[0])

#################
# PyFAI specific
#################


class PyFaiTestData(Command):
    """
    Tailor made tarball with test data
    """
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def download_images(self):
        """
        Download all test images and
        """
        root_dir = os.path.dirname(os.path.abspath(__file__))
        test_dir = os.path.join(root_dir, PROJECT, "test")
        sys.path.insert(0, test_dir)
        from utilstest import UtilsTest
        image_home = os.path.join(root_dir, "testimages")
        testimages = os.path.join(image_home, "all_testimages.json")
        UtilsTest.image_home = image_home
        UtilsTest.testimages = testimages
        if os.path.exists(testimages):
            import json
            with open(testimages) as f:
                all_files = set(json.load(f))
        else:
            raise(RuntimeError("Please run 'python setup.py build test' to download all images"))
        return list(all_files)

    def run(self):
        datafiles = self.download_images()
        dist = "dist"
        arch = os.path.join(dist, PROJECT + "-testimages.tar.gz")
        print("Building testdata tarball in %s" % arch)
        if not os.path.isdir(dist):
            os.mkdir(dist)
        if os.path.exists(arch):
            os.unlink(arch)
        import tarfile
        with tarfile.open(name=arch, mode='w:gz') as tarball:
            for afile in datafiles:
                tarball.add(os.path.join("testimages", afile), afile)


# ##### #
# setup #
# ##### #

def get_project_configuration(dry_run):
    """Returns project arguments for setup"""

    install_requires = [
        "numpy",
        # h5py was removed from dependencies cause it creates an issue with
        # Debian 8. Pip is not aware that h5py is installed and pkg_resources
        # check dependencies and in this case raise an exception
        # FIXME we still have to investigate
        # "h5py",
        "fabio",
        "matplotlib",
        "scipy",
        "numexpr",
        # for the use of pkg_resources on script launcher
        "setuptools"]

    setup_requires = [
        "setuptools",
        "numpy",
        "cython"]

    package_data = {
        'pyFAI.resources': [
            # Add here all resources files
            'calibration/*.D',
            'gui/*.ui',
            'gui/icons/*.svg',
            'gui/icons/*.png',
            'openCL/*.cl',
        ]
    }

    console_scripts = [
        'check_calib = pyFAI.app.check_calib:main',
        'detector2nexus = pyFAI.app.detector2nexus:main',
        'diff_map = pyFAI.app.diff_map:main',
        'diff_tomo = pyFAI.app.diff_tomo:main',
        'eiger-mask = pyFAI.app.eiger_mask:main',
        'MX-calibrate = pyFAI.app.mx_calibrate:main',
        'pyFAI-average = pyFAI.app.average:main',
        'pyFAI-benchmark = pyFAI.app.benchmark:main',
        'pyFAI-calib = pyFAI.app.calib:main',
        'pyFAI-calib2 = pyFAI.app.calib2:main',
        'pyFAI-drawmask = pyFAI.app.drawmask:main',
        'pyFAI-integrate = pyFAI.app.integrate:main',
        'pyFAI-recalib = pyFAI.app.recalib:main',
        'pyFAI-saxs = pyFAI.app.saxs:main',
        'pyFAI-waxs = pyFAI.app.waxs:main',
    ]

    entry_points = {
        'console_scripts': console_scripts,
        # 'gui_scripts': [],
    }

    cmdclass = dict(
        build=Build,
        build_py=build_py,
        test=PyTest,
        build_doc=BuildDocCommand,
        test_doc=TestDocCommand,
        build_ext=BuildExt,
        build_man=BuildMan,
        clean=CleanCommand,
        debian_src=sdist_debian,
        testimages=PyFaiTestData,
    )

    if dry_run:
        # DRY_RUN implies actions which do not require NumPy
        #
        # And they are required to succeed without Numpy for example when
        # pip is used to install silx when Numpy is not yet present in
        # the system.
        setup_kwargs = {}
    else:
        config = configuration()
        setup_kwargs = config.todict()

    setup_kwargs.update(name=PROJECT,
                        version=get_version(),
                        url="https://github.com/silx-kit/pyFAI",
                        download_url="https://github.com/silx-kit/pyFAI/releases",
                        author="Jérôme Kieffer (python), \
          Peter Boesecke (geometry), Manuel Sanchez del Rio (algorithm), \
          Vicente Armando Sole (algorithm), \
          Dimitris Karkoulis (GPU), Jon Wright (adaptations) \
          and Frederic-Emmanuel Picca",
                        author_email="jerome.kieffer@esrf.fr",
                        classifiers=classifiers,
                        description='Python implementation of fast azimuthal integration',
                        long_description=get_readme(),
                        install_requires=install_requires,
                        setup_requires=setup_requires,
                        cmdclass=cmdclass,
                        package_data=package_data,
                        zip_safe=False,
                        entry_points=entry_points,
                        )
    return setup_kwargs


def setup_package():
    """Run setup(**kwargs)

    Depending on the command, it either runs the complete setup which depends on numpy,
    or a *dry run* setup with no dependency on numpy.
    """

    # Check if action requires build/install
    dry_run = len(sys.argv) == 1 or (len(sys.argv) >= 2 and (
        '--help' in sys.argv[1:] or
        sys.argv[1] in ('--help-commands', 'egg_info', '--version',
                        'clean', '--name')))

    if dry_run:
        # DRY_RUN implies actions which do not require dependancies (i.e. NumPy)
        try:
            from setuptools import setup
            logger.info("Use setuptools.setup")
        except ImportError:
            from distutils.core import setup
            logger.info("Use distutils.core.setup")
    else:
        try:
            from setuptools import setup
        except ImportError:
            from numpy.distutils.core import setup
            logger.info("Use numpydistutils.setup")

    setup_kwargs = get_project_configuration(dry_run)
    setup(**setup_kwargs)

if __name__ == "__main__":
    setup_package()
