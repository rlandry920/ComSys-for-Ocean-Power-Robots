import time
from base_camera import BaseCamera


class Camera(BaseCamera):
    """An emulated camera implementation that streams a repeated sequence of
    files 1.jpg, 2.jpg and 3.jpg at a rate of one frame per second."""
    imgs = [open('reindeer' + f + '.jpg', 'rb').read()
            for f in ['1', '2', '3', '4', '5', '6', '7', '8', '9']]

    @staticmethod
    def frames():
        while True:
            yield Camera.imgs[int(time.time()) % 9]
            time.sleep(1)
