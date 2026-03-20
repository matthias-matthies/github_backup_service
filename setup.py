"""Package setup for the GitHub Organisation Backup Service."""

from setuptools import find_packages, setup

setup(
    name="github-backup-service",
    version="1.0.0",
    description="Automated backup service for GitHub organisations.",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "PyGithub",
        "requests",
        "PyYAML",
        "tenacity",
        "GitPython",
        "PyJWT",
        "cryptography",
    ],
    entry_points={
        "console_scripts": [
            "backup=src.backup:main",
        ],
    },
)
