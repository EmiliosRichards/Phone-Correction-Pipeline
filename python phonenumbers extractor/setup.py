#!/usr/bin/env python3
"""
Setup script for the Phone Extraction project.
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = fh.read().splitlines()

setup(
    name="phone-extraction",
    version="0.1.0",
    author="Phone Extraction Team",
    author_email="example@example.com",
    description="A project for extracting and analyzing phone numbers from scraped web content",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/phone-extraction",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=4.0.0',
        ],
    },
    entry_points={
        "console_scripts": [
            "phone-normalize=scripts.normalize_text:main",
            "phone-extract=scripts.extract_phones:main",
            "phone-analyze=scripts.analyze_results:main",
            "phone-pipeline=main:main",
        ],
    },
)