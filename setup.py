import setuptools

setuptools.setup(
    name='gocd-dashboard',
    version='1.0.3',
    author="Sam Clements",
    author_email="sam.clements@datasift.com",
    description="A dashboard to highlight GoCD pipeline statuses.",
    long_description=open('README.md').read(),
    license='None',

    packages=setuptools.find_packages(),
    include_package_data=True,
    zip_safe=False,

    install_requires=[
        'attrs',
        'flask>=0.11.1',
        'Flask-Gravatar>=0.4.2',
        'requests',
        'requests-futures'
    ],

    extras_require={
        'debug': [
            'flask-debugtoolbar>=0.10.0'
        ],
        'deploy': [
            'gunicorn>=19.6.0'
        ]
    },

    entry_points={
        'console_scripts': [
            'gocd-dashboard = gocd_dashboard.__main__:main',
        ]
    },

    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.3'
    ]
)
