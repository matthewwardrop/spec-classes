from setuptools import setup


setup(
    name='spec-classes',
    versioning='post',
    author='Matthew Wardrop',
    author_email='mpwardrop@gmail.com',
    description='Represent type-checked specifications as Python classes and incrementally build them.',
    keywords='spec-classes',
    url='https://github.com/matthewwardrop/spec-classes',
    python_requires='>=3.7',
    setup_requires=['setupmeta>=3.0'],
    install_requires='@requirements.txt',
    tests_require='@requirements_test.txt',  # Only used by defunct `setup.py test`
    extras_require={'test': '@requirements_test.txt'},
    packages=['spec_classes', 'spec_classes.utils'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
