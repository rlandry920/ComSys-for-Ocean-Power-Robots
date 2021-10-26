# ComSys-for-Ocean-Power-Robots

This project allows communication between an ocean powered robot and a landbase UI

## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install flask.

```bash
pip install flask
```

Make sure to have Python3 installed

## Usage

Run the python script, the output should something look like this:

```bash
python .\robot_flask.py
 * Serving Flask app 'robot_flask' (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.
 * Debug mode: off
 * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)
```

Update line 15 in index.js so that the url matches that of the robot flask script

Open the index.html on your local host while the python script is still running

You can now send move commands to the robot
