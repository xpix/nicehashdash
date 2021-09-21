import requests
import flask
from flask import request, jsonify

app = flask.Flask(__name__)
app.config["DEBUG"] = True

chart = [0] * 20

@app.route('/', methods=['GET'])
def home():
    return '''<h1>Proxy miner api</h1>
<p>Redirect api data from miner to to external port (5000)</p>'''


# A route to return all of the available entries in our catalog.
@app.route('/api/v1/resources/nbminer/all', methods=['GET'])
def api_all():
    res = requests.get('http://localhost:4000/api/v1/status')
    data = res.json()
    chart.append(data['miner']['total_hashrate_raw'])
    data['chart'] = chart
    chart.pop(0)
    return jsonify(data)

app.run(host='0.0.0.0', port=5000)