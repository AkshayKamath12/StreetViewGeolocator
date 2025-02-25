from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import tempfile
import tensorflow as tf
import numpy as np
import time
from redisData.getNearby import set_data, find_closest_coordinates, get_data_from_redis

#set up app and cors to allow requests from node server in front end
app = Flask(__name__)
CORS(app)


#CONSTANTS:
ALLOWED_EXTENSIONS = {"png", "jpg"}
MIN_LAT = 36.999301
MAX_LAT = 37.000198
MIN_LON = -122.064474
MAX_LON = -122.061568
COORDINATES = set_data()
model = tf.keras.models.load_model("geolocator.keras")

#upload an image and receive predicted coordinates
@app.route('/upload', methods=['POST'])
def upload_image():
    start = time.time()
    if 'image' not in request.files:
        return jsonify({'error': 'No file'}), 400
    
    file = request.files['image']
    
    if file and allowed(file.filename):
        filename, extension = file.filename.split('.')
        new_filename = generate_temp_upload_filename(filename, "." + extension)   
        file.save(os.path.join('images/upload', new_filename))
        image = tf.keras.utils.load_img(new_filename, target_size=(224, 224))
        image_array = tf.keras.utils.img_to_array(image) / 255.0
        image_array = tf.expand_dims(image_array, axis=0)
        predictions = model.predict(image_array)
        predictions = denormalize_predicted_coordinates(predictions, MIN_LAT, MAX_LAT, MIN_LON, MAX_LON)[0]
        os.remove(new_filename)
        end = time.time()
        print(f'Time for /upload endpoint = {end - start}')
        return jsonify({'prediction': predictions.tolist()}), 200
    else:
        return jsonify({'error': 'Invalid file'}), 400
    
def allowed(file_name):
    res = file_name.split('.')
    return len(res) == 2 and res[1] in ALLOWED_EXTENSIONS

def generate_temp_upload_filename(filename, extension):
    tmp_file = tempfile.NamedTemporaryFile(delete=False, dir="images/upload", prefix=filename, suffix=extension)
    return tmp_file.name

#prediction is normalized on a 0-1 scale for both latitude and longitude, so it needs to be converted back
def denormalize_predicted_coordinates(coords, min_latitude, max_latitude, min_longitude, max_longitude):
    lat = coords[:, 0] * (max_latitude - min_latitude) + min_latitude
    lon = coords[:, 1] * (max_longitude - min_longitude) + min_longitude
    return np.stack([lat, lon], axis=1)


'''
1) receives post request with coordinate array
2) returns an array of arrays
3) each array's first value is a closest coordinate and second value is a JSON description of that coordinate
'''
@app.route('/getNearbyLocationData', methods=['POST'])
def getNearbyLocationData():
    start = time.time()
    data = request.get_json()
    if data:
        coordinate = tuple(data)
        #note: change coordinates requested below to be a constant at top of file
        nearest_coordinates = find_closest_coordinates(coordinate, COORDINATES, coordinates_requested=2)
        res = [[elem[1], get_data_from_redis(elem[1])] for elem in nearest_coordinates]
        end = time.time()
        print(f'Time for /getNearbyLocationData endpoint = {end - start}')
        return jsonify({'res': res})
    else:
        return jsonify({'res': []})
    
if __name__ == "__main__":
    app.run(debug=True, port=8080)