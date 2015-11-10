from setuptools import setup

setup(
    name = "simplecpreprocessor",
    version = "0.0.3",
    author = "Seppo Yli-Olli",
    author_email = "seppo.yli-olli@iki.fi",
    description = "Simple C preprocessor for usage eg before CFFI",
    keywords = "python c preprocessor",
    license = "BSD",
    url = "http://packages.python.org/simplepreprocessor",
    py_modules=["simplepreprocessor"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Utilities",
        "License :: OSI Approved :: BSD License",
        ],
    )
