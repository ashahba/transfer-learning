# Documentation

## Sphinx Documentation

To build these docs, you need to have the following installed:

```
pip3 install sphinx sphinx_click sphinx_rtd_theme
```
 
Then run this command from the `transfer-learning/docs` directory:

```
make clean html 
```

The output HTML files will be located in `transfer-learning/docs/_build/html`.

To run the doctests, use this command:

```
make doctest
```

## Software Design Documents

* [Transfer_Learning_CLI_and_API_Design.pdf](/docs/sw_design/Transfer_Learning_CLI_and_API_Design.pdf)
