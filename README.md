gocd-dashboard
==============

A leightwieght GoCD dashboard that can recursively show pipeline materials. 

Deployment
----------

_Requirements: Python 3.3 or above, the `gocd_dashboard` and `gunicorn`
python packages (and their dependencies)._

Run the server using [Gunicorn]:

```bash
gunicorn 'gocd_dashboard:create_app()'
```

Development
-----------

_Requirements: Python 3.3 or above, the `virtualenv` python package, NodeJS
and the `npm` package manager._

Install the module into a Python virtualenv in development mode:

```bash
pip install -e .
```

Install a [Sass] compiler and [materialize.css]:

```bash
npm install
```

Compile CSS files using `node-sass`:

```bash
./node_modules/.bin/node-sass --watch gocd_dashboard/static --output gocd_dashboard/static
```

Run the development server:

```bash
gocd-dashboard run
```

Authors
-------

- [Sam Clements]

[Gunicorn]: http://gunicorn.org/
[Sam Clements]: https://github.com/borntyping/
[Sass]: http://sass-lang.com/
[materialize.css]: http://materializecss.com/
