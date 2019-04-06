from os import path
import sys

from setuptools import setup, find_packages


# Open encoding isn't available for Python 2.7 (sigh)
if sys.version_info < (3, 0):
    from io import open

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()



# The setup is currently only used for tests.
setup(
    name='nvfm',
    description='A colorful, hackable file manager based on Neovim',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=find_packages(where='src'),
    author='numirias',
    author_email='numirias@users.noreply.github.com',
    version='0.0.1',
    url='https://github.com/numirias/nvfm',
    license='MIT',
    python_requires='>=3.5',
    install_requires=[
        'pytest>=3.3.2',
        'pynvim>=0.3.2',
        'future-fstrings',
        'appdirs',
    ],
    scripts=['src/bin/nvfm'],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Desktop Environment :: File Managers',
        'Topic :: Text Editors',
    ],
    # Include data files specified in MANIFEST.in
    include_package_data=True,
    # package_data ={
    #     'nvfm': ['*']
    # },
    package_dir={'nvfm':'src/nvfm'},
    # data_files=[('nvfm', ['nvfm/runtime'])],
    # package_data={'nvfm':['src/*']},
)
