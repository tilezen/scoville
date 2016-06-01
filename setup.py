from setuptools import setup, find_packages

version = '0.0.1'

setup(name='scoville',
      version=version,
      description="A tool for measureing tile latency.",
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
      keywords='tile latency mvt',
      author='Matt Amos, Mapzen',
      author_email='matt.amos@mapzen.com',
      url='https://github.com/tilezen/scoville',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'PyYAML',
          'contextlib2',
          'Shapely',
          'pycurl',
          'mapbox_vector_tile',
          'psycopg2',
          'boto3'
      ],
      entry_points=dict(
          console_scripts=[
              'scoville = scoville.command:scoville_main',
          ]
      )
)
