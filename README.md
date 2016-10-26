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

_Requirements: Python 3.3 or above, the `virtualenv` python package, the `sass`
ruby package._

Install the module into a Python virtualenv in development mode (`pip -e .`).

Run the development server with `gocd-dashboard run`.

Compile [Sass] files to CSS with `sass --watch gocd_dashboard/static`.

Authors
-------

- [Sam Clements]

[Gunicorn]: http://gunicorn.org/
[Sam Clements]: https://github.com/borntyping/
[Sass]: http://sass-lang.com/

