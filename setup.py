from setuptools import setup, find_namespace_packages

setup(
    name='search-tools',
    version='0.1.0-alpha',
    packages=find_namespace_packages(),
    entry_points={
    },
    scripts=[],
    package_data={
    },
    install_requires=[
    ],
    description='A library of search functions for various projects at APL.',
    url='https://github.com/provlab-bioinfo/search-tools',
    author='Andrew Lindsay',
    author_email='andrew.lindsay@albertaprecisionlabs.ca',
    include_package_data=True,
    keywords=[],
    zip_safe=False
)