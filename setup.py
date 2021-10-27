from setuptools import setup, find_packages

version = '0.2.0'

setup(
    name='scoville',
    version=version,
    description="A tool for attributing MVT tile size.",
    long_description=open('README.md').read(),
    classifiers=[
        # strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Utilities',
    ],
    keywords='tile size mvt',
    author='Matt Amos, Tilezen',
    author_email='zerebubuth@gmail.com',
    url='https://github.com/tilezen/scoville',
    license='MIT',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'click',
        'requests',
        'requests_futures',
        'squarify',
        'msgpack',
        'Pillow',
	'enum34'
    ],
    entry_points=dict(
        console_scripts=[
            'scoville = scoville.command:scoville_main',
        ]
    ),
    test_suite='tests',
)
