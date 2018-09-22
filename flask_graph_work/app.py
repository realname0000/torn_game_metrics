import sqlite3
import time
import json
from sqlalchemy import create_engine
from flask import Flask, render_template
import pandas as pd
import re
import base64
import hmac
import hashlib

token = re.compile('^([-\d]+)([a-z]+)(\d+)-([0-9a-f]+)$')
now = int(time.time())
hmac_key_f = open('/var/torn/hmac_key', 'r')
hmac_key = bytes(hmac_key_f.read(),'utf-8')
hmac_key_f.close()

app = Flask(__name__)

@app.route("/graph/<what_graph>", methods=['GET'])
def index(what_graph):
    p_id = None
    graph_type = None
    timestamp = None
    given_hmac = None
    df = None

    # what graph is this meant to produce?
    re_object = token.match(what_graph)
    if re_object:
        p_id = re_object.group(1)
        graph_type = re_object.group(2)
        timestamp = re_object.group(3)
        given_hmac =  re_object.group(4)
        print("planning graph for: ", p_id, graph_type, timestamp, given_hmac)
    else:
        print("RE did not match URL")
        return render_template("bad_graph_request.html")

    # calc correct hmac
    if 'crime' == graph_type:
        graph_selection = ( str(p_id) + 'crime' + str(timestamp) ).encode("utf-8")
    elif 'drug' == graph_type:
        graph_selection = ( str(p_id) + 'drug' + str(timestamp) ).encode("utf-8")
    else:
        return render_template("bad_graph_request.html")
    hmac_hex = hmac.new(hmac_key, graph_selection, digestmod=hashlib.sha1).hexdigest()

    # test for correct hmac
    if not hmac.compare_digest(hmac_hex, given_hmac):
        print("HMAC disagreement")
        return render_template("bad_graph_request.html")
    # test for acceptable timestamp
    if ((int(timestamp) + 86400) < now):
        print("timestamp disagreement is old:", timestamp)
        return render_template("bad_graph_request.html")

    conn = sqlite3.connect('file:/var/torn/readonly_db?mode=ro', uri=True)
    if 'crime' == graph_type:
        parm = (int(p_id),)
        df = pd.read_sql_query("select et,selling_illegal_products,theft,auto_theft,drug_deals,computer_crimes,murder,fraud_crimes,other,total from playercrimes where player_id=? order by et", conn, params=parm)
    elif 'drug' == graph_type:
        parm = (int(p_id),)
        df = pd.read_sql_query("select et,cantaken,exttaken,lsdtaken,opitaken,shrtaken,pcptaken,xantaken,victaken,spetaken,kettaken from drugs where player_id=? order by et", conn, params=parm)
    else:
        return render_template("bad_graph_request.html")
    conn.close()

    # Does df contain reasonable data? TODO
    print("LEN DF", len(df))

    # convert et to date-as-string so it can be parsed in JS
    df['et'] = pd.to_datetime(df['et'],unit='s').astype(str)

    chart_data = df.to_dict(orient='records')
    data = {'chart_data': chart_data}

    if 'crime' == graph_type:
        return render_template("playercrimes.html", data=data)
    elif 'drug' == graph_type:
        return render_template("drug.html", data=data)
    else:
        return render_template("bad_graph_request.html")

if __name__ == "__main__":
    app.run(debug=True)
