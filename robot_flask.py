#!flask/bin/python
import sys
from flask import Flask, render_template, request, redirect, Response
import random, json
app = Flask(__name__)
@app.route('/',methods = ['GET','POST','DELETE'])
def output():
	return
@app.route('/move', methods = ['POST','DELETE'])
def move():
	data = request.get_json()[0]
	latitude = ""
	longitude = ""
	if("lat_py" in data):
		lat = data["lat_py"][:-1].replace('.', '')
		lat = lat.replace('-','')
		if(lat.isnumeric()):
			latitude = data["lat_py"]
	if("long_py" in data):
		long = data["long_py"][:-1].replace('.', '')
		long = long.replace('-','')
		if(long.isnumeric()):
			longitude = data["long_py"]
	if(latitude == "" and longitude == ""):
		return "Invalid latitude and longitude"
	elif(latitude == ""):
		return "Invalid latitude"
	elif(longitude == ""):
		return "Invalid longitude"
	else:
		return "Moving to ("+latitude+", "+longitude+")"
if __name__ == '__main__':
	# run!
	app.run()