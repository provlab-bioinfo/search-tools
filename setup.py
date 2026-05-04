from setuptools import setup, find_packages

setup(
    name='search_tools',
    version='1.0.0',
    packages=find_packages(exclude=['tests*']),
    install_requires=[
        'alive_progress',
        'pandas',
        'pyahocorasick',
        'setuptools',
        "openpyxl"
    ],
    python_requires='>=3.10, <4',
    description='A library of search functions for various projects at APL.',
    url='https://github.com/provlab-bioinfo/search-tools',
    author='Andrew Lindsay',
    author_email='andrew.lindsay@albertaprecisionlabs.ca',
    include_package_data=True,
    keywords=[],
    zip_safe=False
)