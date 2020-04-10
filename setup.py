from setuptools import setup, find_packages

setup(
    name="pynetcf",
    version="v0.1",
    author="Reynold Tabuena",
    author_email="rynldtbuen@gmail.com",
    description=(
        """
        Network Configuration Models.
        """
    ),
    license="MIT",
    packages=find_packages(),
    install_requires=["pynsot"],
    classifiers=[
        "Programming Language :: Python :: 3.5",
        "License :: OSI Approved :: MIT License",
    ],
)
