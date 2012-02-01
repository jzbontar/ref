import unittest
import os
import sys
from distutils.core import setup, Command

    
class TestCommand(Command):
    description = "Run unittests"
    user_options = [('all-tests', 'a', 'Run all tests.')]

    def initialize_options(self):
        self.all_tests = False

    def finalize_options(self):
        pass

    def run(self):
        os.chdir('test')
        sys.path.insert(0, os.getcwd())
        name = 'test_ref' if self.all_tests else 'test_ref.Test'
        tests = unittest.TestLoader().loadTestsFromName(name)
        runner = unittest.TextTestRunner()
        runner.run(tests)

setup(name='ref',
    version='0.1',
    url='https://bitbucket.org/jzbontar/ref/',
    description='A usable reference manager.',
    py_modules=['ref', 'gui_vim'],
    package_dir={'': 'src'},
    scripts=['src/ref'],
    cmdclass={'test': TestCommand})
