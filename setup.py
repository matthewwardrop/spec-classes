from setuptools import setup, find_packages


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
    extras_require={'test': '@requirements_test.txt'},
    packages=find_packages(),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
)
