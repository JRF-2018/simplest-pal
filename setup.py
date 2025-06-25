# setup.py
import setuptools
import os

VERSION = "0.1.0"

here = os.path.abspath(os.path.dirname(__file__))
readme_path = os.path.join(here, 'README.md')
long_description = ""
if os.path.exists(readme_path):
    with open(readme_path, encoding='utf-8') as f:
        long_description = f.read()

setuptools.setup(
    name="simplest-pal",
    version=VERSION, 
    author="JRF",
    # author_email="your.email@example.com",
    description="A simplest PDB automation layer for AI interaction.", 
    long_description=long_description,
    long_description_content_type='text/markdown',
    url="https://github.com/JRF-2018/simplest-pal", 
    py_modules=['simplest_pal'],
    # packages=setuptools.find_packages(),

    entry_points={
        'console_scripts': [
            'simplest-pal = simplest_pal:simplest_pal_main',
        ],
    },

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)
