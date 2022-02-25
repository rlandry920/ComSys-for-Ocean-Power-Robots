from flask import Flask, render_template
from PIL import Image
import base64
import io


app = Flask(__name__)


@app.route('/')
def hello_world():

    # Full Script.
    im = Image.open("test.jpg")
    data = io.BytesIO()
    im.save(data, "JPEG")
    encoded_img_data = base64.b64encode(data.getvalue())

    return render_template("index.html", img_data=encoded_img_data.decode('utf-8'))


if __name__ == '__main__':
    app.run(host='0.0.0.0')
