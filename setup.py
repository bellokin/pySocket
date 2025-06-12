# setup.py
from setuptools import setup, find_packages

setup(
    name="pysocket",
    version="0.1.0",
    description="A simple real-time WebSocket server for Python/Django",
    author="Your Name",
    author_email="you@example.com",
    packages=find_packages(),
    install_requires=[
        "websockets>=11.0",
    ],
    python_requires=">=3.8",
)
