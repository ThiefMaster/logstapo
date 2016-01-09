# coding=utf-8

import ast
import re
from setuptools import setup


_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('logstapo/__init__.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(f.read().decode('utf-8')).group(1)))
with open('README.rst') as f:
    readme = f.read()
with open('requirements.txt') as f:
    requirements = f.read().splitlines()


setup(
    name='logstapo',
    version=version,
    description='A tool that checks new entries in log files and performs actions based on them.',
    long_description=readme,
    url='https://github.com/ThiefMaster/logstapo',
    download_url='https://github.com/ThiefMaster/logstapo',
    author=u'Adrian Mönnich',
    author_email='adrian@planetcoding.net',
    license='MIT',
    zip_safe=False,
    include_package_data=True,
    packages=('logstapo',),
    entry_points={
        'console_scripts': [
            'logstapo = logstapo.cli:main',
        ],
    },
    install_requires=requirements,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.4',
        'Environment :: Console',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Topic :: Internet :: Log Analysis',
        'Topic :: System :: Logging'
    ]
)
