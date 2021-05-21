import os
from flask import Flask, render_template, g, request, redirect, flash, send_file, session, url_for
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# Support for mongodb+srv:// URIs requires dnspython:
#!pip install dnspython pymongo
import pymongo
from bson.objectid import ObjectId
from bson.binary import Binary
from io import BytesIO
import json
import time
from datetime import date, datetime

# env.py should exist only in Development
if os.path.exists("env.py"):
    import env


app = Flask(__name__)

# take app configuration from OS environment variables
app.secret_key               = os.environ.get("FLASK_SECRET_KEY")            # => Heroku Congig Vars
app.config["FLASK_IP"]       = os.environ.get("FLASK_IP",      "0.0.0.0")
# the source 'PORT' name is mandated by Heroku app deployment
app.config["FLASK_PORT"]     = int(os.environ.get("PORT"))
app.config["FLASK_DEBUG"]    = os.environ.get("FLASK_DEBUG",   "False").lower() in {'1','true','t','yes','y'}
app.config["UPLOAD_EXTENSIONS"] = set(['png', 'jpg', 'jpeg', 'gif'])

# MongoDB parameters
app.config["MONGO_CLUSTER"] = os.environ.get("MONGO_CLUSTER")
app.config["MONGO_DB_NAME"] = os.environ.get("MONGO_DB_NAME")
app.config["MONGO_URI"] = f"mongodb+srv:" + \
                          f"//{os.environ.get('MONGO_DB_USER')}" + \
                          f":{os.environ.get('MONGO_DB_PASS')}" + \
                          f"@{app.config['MONGO_CLUSTER']}" + \
                          f".ueffo.mongodb.net" + \
                          f"/{app.config['MONGO_DB_NAME']}" + \
                          f"?retryWrites=true&w=majority"

app.config["MONGO_DATA"]    = os.environ.get("MONGO_DATA","./static/data/")
app.config["MONGO_CONTENT"] = os.environ.get("MONGO_CONTENT","mongo_content.json")
app.config["MONGO_INIT"]    = os.environ.get("MONGO_INIT",   "False").lower() in {'1','true','t','yes','y'}# => Heroku Congig Vars
app.config["MONGO_USERS"]             = 'users'
app.config["MONGO_FIELDCATALOG"]      = 'fieldcatalog'
app.config["MONGO_CURRENCIES"]        = 'currencies'
app.config["MONGO_COUNTRIES"]         = 'countries'
app.config["MONGO_MEASURE_TYPES"]     = 'measure_types'
app.config["MONGO_UNIT_OF_MEASURES"]  = 'unit_of_measures'
app.config["MONGO_UNIT_CONVERSIONS"]  = 'unit_conversions'
app.config["MONGO_EXPENDITURE_TYPES"] = 'expenditure_types'
app.config["MONGO_MATERIAL_TYPES"]    = 'material_types'
app.config["MONGO_MATERIALS"]         = 'materials'
app.config["MONGO_COLLECTION_NAME"]   = 'collection_name'
app.config["MONGO_ENTITY_NAME"]       = 'entity_name'
app.config["MONGO_BUFFERED_COLLECTIONS"] = [
    app.config["MONGO_CURRENCIES"],
    app.config["MONGO_COUNTRIES"],
    app.config["MONGO_MEASURE_TYPES"],
    app.config["MONGO_UNIT_OF_MEASURES"],
    app.config["MONGO_UNIT_CONVERSIONS"],
    app.config["MONGO_EXPENDITURE_TYPES"],
    app.config["MONGO_MATERIAL_TYPES"],
    app.config["MONGO_MATERIALS"],
]

app.config["MONGO_COLLECTION_IMAGES"] = {
        "name":"images",
        "title":"Task Images",
        "fields":["source","image"]
}
app.config["MONGO_COLLECTION_TASKS"] = {
        "name":"tasks",
        "title":"Task Master",
        "fields":["name","description","is_urgent","due_date","is_complete","date_time_insert","date_time_update",
                  "category_id","image_id","user_id"]
}


# App routes
#==============
@app.route("/")  # trigger point through webserver: "/"= root directory
def index():
    return render_template("index.html", page_title="Home")


@app.route("/register", methods=['GET','POST'])
def register():
    if request.method == "GET":
        return render_template("reglog.html", register=True)
        
    # request.method == POST
    fieldcat = get_records(app.config["MONGO_FIELDCATALOG"])[app.config["MONGO_USERS"]]
    username_field = fieldcat['fields'][0]['name']
    username = request.form.get(username_field).lower()
    password_field = fieldcat['fields'][1]['name']
    admin_field    = fieldcat['fields'][2]['name']
    # check if username already exists in db
    coll = get_mongo_coll(app.config["MONGO_USERS"])
    user_old = coll.find_one({username_field: username}, {'_id': 1})
    if user_old:
        flash(f"{fieldcat['fields'][0]['heading']} already exists", 'danger')
        return redirect(url_for("register"))

    user_new = {
        username_field: username,
        password_field: generate_password_hash(request.form.get(password_field))
    }
    # put the new user_id into 'session' cookie
    session['user_id'] = str(coll.insert_one(user_new).inserted_id)
    session[admin_field] = False
    flash("Registration Successful!", "success")
    return redirect(url_for("tasks"))


@app.route("/login", methods=['GET','POST'])
def login():
    if request.method == "GET":
        return render_template("reglog.html", register=False)

    # request.method == POST
    fieldcat = get_records(app.config["MONGO_FIELDCATALOG"])[app.config["MONGO_USERS"]]
    username_field = fieldcat['fields'][0]['name']
    password_field = fieldcat['fields'][1]['name']
    admin_field    = fieldcat['fields'][2]['name']
    # check if username already exists in db
    username = request.form.get(username_field).lower()
    password = request.form.get(password_field)
    coll = get_mongo_coll(app.config["MONGO_USERS"])
    user_old = coll.find_one({username_field: username}, {password_field: 1, 'user_is_admin':1})
    if not user_old or not check_password_hash(user_old[password_field], password):
        # incorrect username and/or password
        flash(f"Incorrect {fieldcat['fields'][0]['heading']} and/or {fieldcat['fields'][1]['heading']}", 'danger')
        return redirect(url_for("login"))

    # put the user_id into session cookie
    session['user_id'] = str(user_old["_id"])
    session[admin_field] = user_old.get(admin_field, False)
    flash(f"Welcome, {username}", "success")
    return redirect(url_for("tasks"))


@app.route("/logout")
def logout():
    # is a user logged in?
    if session.get('user_id', None):
        session.pop('user_id')
        flash("You have been logged out", "info")
    if session.get('user_is_admin', None):
        session.pop('user_is_admin')
    return redirect(url_for("index"))


@app.route("/profile", methods=['GET','POST'])
def profile():
    # is a user logged in?
    if not session.get('user_id', None):
        return redirect(url_for("login"))
    coll = get_mongo_coll(app.config["MONGO_USERS"])
    user_old = coll.find_one({'_id': ObjectId(session['user_id'])})
    if not user_old:
        flash("Invalid logged in user!", 'danger')
        return redirect(url_for("logout"))
    if request.method == "GET":
        return render_template("profile.html", user=user_old)
    # request.method == POST
    fieldcat = get_records(app.config["MONGO_FIELDCATALOG"])[app.config["MONGO_USERS"]]
    password_field = fieldcat['fields'][1]['name']
    password_old = request.form.get('password_old')
    if not check_password_hash(user_old[password_field], password_old):
        flash("Wrong old password", 'danger')
        return redirect(url_for("profile"))
    password_new = request.form.get('password_new')
    if check_password_hash(user_old[password_field], password_new):
        flash("Old and New passwords are the same, not changed!", "warning")
        return redirect(url_for("profile"))
    user_update = {
        password_field:     generate_password_hash(password_new),
        "changed_by":       user_old['_id'],
        "date_time_update": datetime.utcnow().timestamp()
    }
    # update password in DB
    coll.update_one({'_id':user_old['_id']}, {"$set":user_update})
    flash("Your password has been changed", "success")
    return render_template("profile.html", user=user_old)


@app.route("/maintain/<collection_name>", methods=['GET','POST'])
def maintain(collection_name):
    # is a user logged in?
    if not session.get('user_id', None):
        return redirect(url_for("login"))
    coll_fieldcatalog = get_records(app.config["MONGO_FIELDCATALOG"])[collection_name]
    # is collection maintanable by admin only?
    if coll_fieldcatalog.get('admin', None):
        # is logged in user an admin?
        if not session.get('user_is_admin', None):
            return redirect(url_for("index"))
    # create an empty record
    record = {}
    if request.method == 'POST':
        record = save_record_to_db(request, coll_fieldcatalog, record)
        if not record:
            return redirect(url_for('maintain', collection_name=collection_name))

    coll = get_mongo_coll(collection_name)
    records = list(coll.find())
    if not records:
        flash("There are no records. Create one below!", 'info')
    return render_template("maintain.html",
        collection_name=collection_name,
        records=records, 
        last_record=record)


def save_record_to_db(request, coll_fieldcatalog, record_old):
    fields = [field['name'] for field in coll_fieldcatalog['fields']]
    record_new = {f:request.form.get(f) for f in fields if request.form.get(f,None) is not None and request.form.get(f) != record_old.get(f,None)}
    if not record_new:
        flash(f"Did not {'update' if record_old else 'add'} record", "info")
        return {}
    
    images_old = []
    for field in coll_fieldcatalog['fields']:
        if not field.get('input_type', False):
            continue
        # store logged in user as last updater
        if field['input_type']=='user':
            record_new[field['name']] = ObjectId(session['user_id'])
        # convert date value to datetime object
        elif field['input_type']=='date':
            date_value = request.form.get(field['name'],None)
            if date_value == '':
                del record_new[field['name']]
            elif date_value is not None:
                record_new[field['name']] = datetime.fromisoformat(date_value)
        # store foreign key from select-option
        elif field['input_type']=='select':
            # get foreign key of selected value
            record_id = record_new.get(field['name'], None)
            if record_id:
                # insert foreing key as object into field
                record_new[field['name']] = ObjectId(record_id)
        # store check box as boolean
        elif field['input_type']=='checkbox':
            record_new[field['name']] = True if record_new.get(field['name'], None)=='on' else False
        # store password
        elif field['input_type']=='password':
            record_new[field['name']] = generate_password_hash(record_new.get(field['name'], None))
        # store timestamp
        elif field['input_type']=='timestamp_update':
            record_new[field['name']] = datetime.utcnow().timestamp()
        # store image
        elif field['input_type']=='image':
            # following instructions from https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
            image = request.files[field['name']]
            if image:
                filename_source = secure_filename(image.filename)
                extension = filename_source.rsplit('.', 1)[1] if '.' in filename_source else ''
                if extension in app.config["UPLOAD_EXTENSIONS"]:
                    # store image
                    image_new = {'source': filename_source, 'image': Binary(image.read())}
                    coll_images = get_mongo_coll(app.config["MONGO_COLLECTION_IMAGES"]['name'])
                    record_new[field['name']] = coll_images.insert_one(image_new).inserted_id
                    if record_old.get(field['name'], False):
                        images_old.append(record_old[field['name']])

    coll = get_mongo_coll(coll_fieldcatalog[app.config['MONGO_COLLECTION_NAME']])
    try:
        if record_old:
            # update existing record
            coll.update_one({'_id':record_old['_id']}, {"$set":record_new})
            # delete old images if new got uploaded
            coll_images = get_mongo_coll(app.config["MONGO_COLLECTION_IMAGES"]['name'])
            for image_old in images_old:
                coll_images.delete_one({"_id":image_old})
        else:
            coll.insert_one(record_new)
        # create empty record - this clears the input fields, because the update was OK
        record_new = {}
        flash(f"Successfully {'updated' if record_old else 'added'} one {coll_fieldcatalog[app.config['MONGO_ENTITY_NAME']]} record", "success")
    except:
        flash(f"Error in {'update' if record_old else 'insert'} operation!", "danger")
    return record_new


@app.route("/update/<collection_name>/<record_id>", methods=['GET','POST'])
def update_record(collection_name, record_id):
    coll_fieldcatalog = get_records(app.config["MONGO_FIELDCATALOG"])[collection_name]
    if not session.get('user_id', None):
        return redirect(url_for("login"))
    if coll_fieldcatalog.get('admin', None):
        if not session.get('user_is_admin', None):
            return redirect(url_for("index"))
    coll = get_mongo_coll(collection_name)
    record = coll.find_one({"_id":ObjectId(record_id)})
    if not record:
        flash(f"{coll_fieldcatalog[app.config['MONGO_ENTITY_NAME']]} {record_id} does not exist", "danger")
        return redirect(url_for('maintain', collection_name=collection_name))

    if request.method == 'POST':
        record = save_record_to_db(request, coll_fieldcatalog, record)
        # if record is empty, then the update was successful
        if not record:
            return redirect(url_for('maintain', collection_name=collection_name))

    records = coll.find()
    return render_template("maintain.html",
        collection_name=collection_name,
        records=records, 
        last_record=record)


@app.route("/delete/<collection_name>/<record_id>", methods=['POST'])
def delete_record(collection_name, record_id):
    coll_fieldcatalog = get_records(app.config["MONGO_FIELDCATALOG"])[collection_name]
    if not session.get('user_id', None):
        return redirect(url_for("login"))
    if not session.get('user_is_admin', None):
        return redirect(url_for("index"))
    coll = get_mongo_coll(collection_name)
    record = coll.find_one({"_id":ObjectId(record_id)})
    if not record:
        flash(f"Record {record_id} does not exist", "danger")
    else:
        # delete record
        coll.delete_one({"_id":record["_id"]})
        flash(f"Deleted one {coll_fieldcatalog[app.config['MONGO_ENTITY_NAME']]} record", "info")
    return redirect(url_for('maintain', collection_name=collection_name))


@app.route("/tasks", methods=['GET','POST'])
def tasks():
    if not session.get('user_id', None):
        return redirect(url_for("login"))
    # create an empty task
    task = {}
    if request.method == 'POST':
        task = save_task_to_db(request, task)
        # if task is empty, then the update was successful
        if not task:
            return redirect(url_for('tasks'))

    coll = get_mongo_coll(app.config["MONGO_COLLECTION_TASKS"]['name'])
    tasks = list(coll.find({'user_id':ObjectId(session['user_id'])}))
    if not tasks:
        flash("There are no tasks. Create one below!", "info")
    return render_template("tasks.html", 
        page_title=app.config["MONGO_COLLECTION_TASKS"]["title"],
        categories=get_records('categories'),
        query="",
        tasks=tasks, 
        last_task=task)


@app.route("/search", methods=["GET", "POST"])
def search():
    query = request.form.get("query")
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_TASKS"]['name'])
    tasks = list(coll.find({"$text": {"$search": query}}))
    if not tasks:
        flash("No results found", "warning")
    return render_template("tasks.html", 
        page_title=app.config["MONGO_COLLECTION_TASKS"]["title"],
        categories=get_records('categories'),
        query=query,
        tasks=tasks, 
        last_task={})


@app.route("/tasks/update/<task_id>", methods=['GET','POST'])
def update_task(task_id):
    if not session.get('user_id', None):
        return redirect(url_for("login"))
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_TASKS"]['name'])
    task = coll.find_one({"_id":ObjectId(task_id), "user_id":ObjectId(session["user_id"])})
    if not task:
        flash(f"Task {task_id} does not exist", "danger")
        return redirect(url_for('tasks'))

    if request.method == 'POST':
        task = save_task_to_db(request, task)
        # if task is empty, then the update was successful
        if not task:
            return redirect(url_for('tasks'))

    tasks = coll.find()
    return render_template("tasks.html", 
        page_title=app.config["MONGO_COLLECTION_TASKS"]["title"],
        categories=get_records('categories'),
        query="",
        tasks=tasks, 
        last_task=task)


@app.route("/tasks/delete/<task_id>", methods=['POST'])
def delete_task(task_id):
    if not session.get('user_id', None):
        return redirect(url_for("login"))
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_TASKS"]['name'])
    task = coll.find_one({"_id":ObjectId(task_id), "user_id":ObjectId(session["user_id"])})
    if not task:
        flash(f"Task {task_id} does not exist", "danger")
    else:
        # delete task
        coll.delete_one({"_id":task["_id"]})
        # delete image
        if task.get("image_id",None) is not None:
            coll = get_mongo_coll(app.config["MONGO_COLLECTION_IMAGES"]['name'])
            coll.delete_one({"_id":task["image_id"]})
    return redirect(url_for('tasks'))


@app.route("/tasks/image/<image_id>")
def serve_image(image_id):
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_IMAGES"]['name'])
    image = coll.find_one({"_id":ObjectId(image_id)})
    if image:
        return send_file(BytesIO(image['image']), mimetype='application/octet-stream')


# MongoDB helpers
#=================
def get_mongo_coll(collection):
    conn = getattr(g, '_database_mongo', None)
    if conn is None:
        try:
            conn = g._database_mongo = pymongo.MongoClient(app.config["MONGO_URI"])
        except pymongo.errors.ConnectionFailure as e:
            print(f"Could not connect to MongoDB {app.config['MONGO_DB_NAME']}: {e}")
            return None
    return conn[app.config["MONGO_DB_NAME"]][collection]


def init_mongo_db(load_content=False):
    with app.app_context():
        fieldcatalog = []
        # initialize collections on DB from JSON file
        with open(os.path.join(app.config["MONGO_DATA"], app.config["MONGO_CONTENT"]), 
                  mode='r', encoding="utf-8") as f:
            collections = json.loads(f.read())
            for coll_name,coll_docs in collections.items():
                coll = get_mongo_coll(coll_name)
                coll.delete_many({})
                # separate fieldcatalog record from data records
                for doc in coll_docs:
                    if doc.get(app.config["MONGO_ENTITY_NAME"], False):
                        doc[app.config["MONGO_COLLECTION_NAME"]] = coll_name
                        fieldcatalog.append(doc)
                # remove fieldcatalog record, leave only data records
                coll_docs = [doc for doc in coll_docs if not doc.get(app.config["MONGO_ENTITY_NAME"], False)]
                if coll_docs:
                    coll.insert_many(coll_docs)

        # write out Fieldcatalog
        coll = get_mongo_coll(app.config["MONGO_FIELDCATALOG"])
        coll.delete_many({})
        coll.insert_many(fieldcatalog)

        # encrypt password in Users
        coll = get_mongo_coll('users')
        users = list(coll.find())
        for user in users:
            user_update = {
                'password':         generate_password_hash(user['password']),
                "date_time_insert": datetime.utcnow().timestamp()
            }
            coll.update_one({'_id':user['_id']}, {"$set":user_update})

        # get all Currencies
        coll = get_mongo_coll('currencies')
        currencies = list(coll.find())

        # convert Currency_Conversions
        coll = get_mongo_coll('currency_conversions')
        records = list(coll.find())
        for record in records:
            # convert From Date isodatestring to datetime
            from_date = datetime.strptime(record['from_date'], '%Y-%m-%d')
            # convert Currency ID to _id
            currency_id_from = next((c['_id'] for c in currencies if c['currency_id'] == record['currency_id_from']), '')
            currency_id_to   = next((c['_id'] for c in currencies if c['currency_id'] == record['currency_id_to']), '')
            # update the record
            coll.update_one({'_id':record['_id']}, {"$set":{
                'currency_id_from': currency_id_from,
                'currency_id_to':   currency_id_to,
                'from_date': from_date
                }})

        # convert Countries
        coll = get_mongo_coll('countries')
        records = list(coll.find())
        for record in records:
            # convert Currency ID to _id
            currency_id = next((c['_id'] for c in currencies if c['currency_id'] == record['currency_id']), '')
            # update the record
            coll.update_one({'_id':record['_id']}, {"$set":{
                'currency_id': currency_id,
                }})            

        # get all Measure Types
        coll = get_mongo_coll('measure_types')
        measure_types = list(coll.find())

        # convert Unit of Measures
        coll = get_mongo_coll('unit_of_measures')
        records = list(coll.find())
        for record in records:
            # convert Measure Type ID to _id
            measure_type_id = next((c['_id'] for c in measure_types if c['measure_type_id'] == record['measure_type_id']), '')
            # update the record
            coll.update_one({'_id':record['_id']}, {"$set":{
                'measure_type_id': measure_type_id,
                }})

        # get all Unit of Measures
        unit_of_measures = list(coll.find())

        # convert Unit Conversions
        coll = get_mongo_coll('unit_conversions')
        records = list(coll.find())
        for record in records:
            # convert Unit of Measure ID to _id
            uom_id_from = next((c['_id'] for c in unit_of_measures if c['uom_id'] == record['uom_id_from']), '')
            uom_id_to   = next((c['_id'] for c in unit_of_measures if c['uom_id'] == record['uom_id_to']), '')
            # update the record
            coll.update_one({'_id':record['_id']}, {"$set":{
                'uom_id_from': uom_id_from,
                'uom_id_to':   uom_id_to
                }})

        # get all Expenditure Types
        coll = get_mongo_coll('expenditure_types')
        expenditure_types = list(coll.find())

        # convert Material Types
        coll = get_mongo_coll('material_types')
        records = list(coll.find())
        for record in records:
            # convert Measure Type ID and Expenditure Type ID to _id
            measure_type_id     = next((c['_id'] for c in measure_types     if c['measure_type_id']     == record['measure_type_id']), '')
            expenditure_type_id = next((c['_id'] for c in expenditure_types if c['expenditure_type_id'] == record['expenditure_type_id']), '')
            # update the record
            coll.update_one({'_id':record['_id']}, {"$set":{
                'measure_type_id':     measure_type_id,
                'expenditure_type_id': expenditure_type_id,
                }})

        # get all Material Types
        material_types = list(coll.find())

        # convert Materials
        coll = get_mongo_coll('materials')
        records = list(coll.find())
        for record in records:
            # convert Material Type ID to _id
            material_type_id = next((c['_id'] for c in material_types if c['material_type_id'] == record['material_type_id']), '')
            # update the record
            coll.update_one({'_id':record['_id']}, {"$set":{
                'material_type_id': material_type_id,
                }})
        # get all Materials
        materials = list(coll.find())

        # get all Countries
        coll = get_mongo_coll('countries')
        countries = list(coll.find())
        # get all Unit Of Measures
        coll = get_mongo_coll('unit_of_measures')
        unit_of_measures = list(coll.find())

        coll_img = get_mongo_coll(app.config["MONGO_COLLECTION_IMAGES"]['name'])

        # convert Cars
        coll = get_mongo_coll('cars')
        records = list(coll.find())
        for record in records:
            # convert Registration Country to _id
            reg_country_id   = next((c['_id'] for c in countries        if c['country_id']  == record['reg_country_id']), '')
            # convert Distance Unit to _id
            distance_unit_id = next((c['_id'] for c in unit_of_measures if c['uom_id']      == record['distance_unit_id']), '')
            # convert Odometer Unit to _id
            odometer_unit_id = next((c['_id'] for c in unit_of_measures if c['uom_id']      == record['odometer_unit_id']), '')
            # convert Fuel Material ID to _id
            fuel_material_id = next((c['_id'] for c in materials        if c['material_id'] == record['fuel_material_id']), '')
            # convert Fuel Unit to _id
            fuel_unit_id     = next((c['_id'] for c in unit_of_measures if c['uom_id']      == record['fuel_unit_id']), '')
            # convert Fuel Economy Unit to _id
            fuel_economy_unit_id = next((c['_id'] for c in unit_of_measures if c['uom_id']  == record['fuel_economy_unit_id']), '')
            # convert Currency ID to _id
            currency_id      = next((c['_id'] for c in currencies       if c['currency_id'] == record['currency_id']), '')
            # update the record
            coll.update_one({'_id': record['_id']}, {"$set":{
                'reg_country_id':       reg_country_id,
                'distance_unit_id':     distance_unit_id,
                'odometer_unit_id':     odometer_unit_id,
                'fuel_material_id':     fuel_material_id,
                'fuel_unit_id':         fuel_unit_id,
                'fuel_economy_unit_id': fuel_economy_unit_id,
                'currency_id':          currency_id,
                }})   
            # convert Car Image ID to _id
            filename_source = record['car_image_id']
            if filename_source:
                with open(os.path.join(app.config["MONGO_DATA"], filename_source), mode='rb') as image:
                    # read image
                    image_new = { 'source': filename_source, 'image': Binary(image.read()) }
                    # update the record
                    coll.update_one({'_id': record['_id']}, {"$set":{
                        'car_image_id': coll_img.insert_one(image_new).inserted_id,  # store image
                        }})


        # get all Categories
        coll = get_mongo_coll('categories')
        categories = list(coll.find())
        # in Tasks
        coll = get_mongo_coll('tasks')
        tasks = coll.find()
        for task in tasks:
            # add timestamp
            timestamp = datetime.utcnow().timestamp()
            # convert category description to _id in Tasks
            category_id = next((c['_id'] for c in categories if c['description'] == task['category_id']), '')
            # convert category description to _id in Tasks
            user_id = next((u['_id'] for u in users if u['username'] == task['user_id']), '')
            # convert due_date isodatestring to datetime
            due_date = datetime.strptime(task['due_date'], '%Y-%m-%d')
            # update a task in Tasks
            coll.update_one({'_id':task['_id']}, {"$set":{
                'date_time_insert': timestamp,
                'category_id':      category_id,
                'user_id':          user_id,
                'due_date':         due_date
                }})

        # create search index in Tasks
        # coll = get_mongo_coll(app.config["MONGO_COLLECTION_TASKS"]['name'])
        # coll.drop_indexes()
        # coll.create_index([("name",pymongo.TEXT), 
        #                    ("description",pymongo.TEXT)], name='name_description')
 

def save_task_to_db(request, task_old):
    fields = app.config["MONGO_COLLECTION_TASKS"]['fields']
    task_new = {f:request.form.get(f) for f in fields if request.form.get(f,None) is not None and request.form.get(f) != task_old.get(f,None)}
    task_new['user_id'] = ObjectId(session['user_id'])
    due_date = request.form.get('due_date',None)
    if due_date == '':
        del task_new['due_date']
    elif due_date is not None:
        task_new['due_date'] = datetime.fromisoformat(due_date)

    category_id = task_new.get('category_id', None)
    if category_id:
        task_new['category_id'] = ObjectId(category_id)

    task_new['is_complete'] = True if task_new.get('is_complete', None)=='on' else False
    task_new['is_urgent']   = True if task_new.get('is_urgent',   None)=='on' else False
    # following instructions from https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
    data = request.files['SourceFileName']
    if data:
        filename_source = secure_filename(data.filename)
        extension = filename_source.rsplit('.', 1)[1] if '.' in filename_source else ''
        if extension in app.config["UPLOAD_EXTENSIONS"]:
            # store image
            image_new = {}
            image_new['source'] = filename_source
            image_new['image'] = Binary(data.read())
            coll = get_mongo_coll(app.config["MONGO_COLLECTION_IMAGES"]['name'])
            task_new["image_id"] = coll.insert_one(image_new).inserted_id
    coll = get_mongo_coll(app.config["MONGO_COLLECTION_TASKS"]['name'])
    try:
        if task_old:
            task_new['date_time_update'] = datetime.utcnow().timestamp()
            # update existing task
            coll.update_one({'_id':task_old['_id']}, {"$set":task_new})
            # delete old image
            if task_new.get("image_id", False) and task_old.get("image_id", False):
                coll = get_mongo_coll(app.config["MONGO_COLLECTION_IMAGES"]['name'])
                coll.delete_one({"_id":task_old["image_id"]})
        else:
            task_new['date_time_insert'] = datetime.utcnow().timestamp()
            coll.insert_one(task_new)
        # create empty task - this clears the input fields, because the update was OK
        task_new = {}
        flash(f"One task successfully {'updated' if task_old else 'added'}", "success")
    except:
        flash(f"Error in {'update' if task_old else 'insert'} operation!", "danger")
    return task_new


# inspired by https://stackoverflow.com/questions/4830535/how-do-i-format-a-date-in-jinja2
@app.template_filter('datetime_to_str')
def _jinja2_filter_datetime_to_str(dt, format):
    if dt:
        return dt.strftime(format)
    else:
        return str()

# learnt about calling functions from jinja template from here https://stackoverflow.com/a/22966127/8634389
@app.context_processor
def context_variables():
    return dict(
        fieldcatalog = get_records(app.config["MONGO_FIELDCATALOG"]),
        buffer       = {coll:get_records(coll) for coll in app.config["MONGO_BUFFERED_COLLECTIONS"] }
    )


def get_records(collection_name):
    if not getattr(g, "_collections", None):
        g._collections = {}
    records = getattr(g._collections, collection_name, None)
    if records is None:
        coll = get_mongo_coll(collection_name)
        if coll:
            if collection_name==app.config["MONGO_FIELDCATALOG"]:
                records = g._collections[collection_name] = {doc[app.config["MONGO_COLLECTION_NAME"]]:doc for doc in coll.find()}
            else:
                records = g._collections[collection_name] = { c['_id']:c for c in coll.find()}
    return records

@app.template_filter('get_entity_select_field')
def _jinja2_filter_get_entity_select_field(entity_id, collection_name):
    fieldcatalog = get_records(app.config["MONGO_FIELDCATALOG"])[collection_name]
    select_field_name = fieldcatalog['select_field']
    coll = get_mongo_coll(collection_name)
    entity_old = coll.find_one({'_id': entity_id})
    if entity_old:
        return entity_old[select_field_name]
    else:
        return ""


# inspired by https://stackoverflow.com/questions/4830535/how-do-i-format-a-date-in-jinja2
from math import floor
@app.template_filter('unix_time_ago')
def _jinja2_filter_time_ago(unix_timestamp:int):
    time_formats = (
        (60, 'seconds', 1),                           # 60
        (120, '1 minute ago', '1 minute from now'),   # 60*2
        (3600, 'minutes', 60),                        # 60*60, 60
        (7200, '1 hour ago', '1 hour from now'),      # 60*60*2
        (86400, 'hours', 3600),                       # 60*60*24, 60*60
        (172800, 'Yesterday', 'Tomorrow'),            # 60*60*24*2
        (604800, 'days', 86400),                      # 60*60*24*7, 60*60*24
        (1209600, 'Last week', 'Next week'),          # 60*60*24*7*4*2
        (2419200, 'weeks', 604800),                   # 60*60*24*7*4, 60*60*24*7
        (4838400, 'Last month', 'Next month'),        # 60*60*24*7*4*2
        (29030400, 'months', 2419200),                # 60*60*24*7*4*12, 60*60*24*7*4
        (58060800, 'Last year', 'Next year'),         # 60*60*24*7*4*12*2
        (2903040000, 'years', 29030400),              # 60*60*24*7*4*12*100, 60*60*24*7*4*12
        (5806080000, 'Last century', 'Next century'), # 60*60*24*7*4*12*100*2
        (58060800000, 'centuries', 2903040000)        # 60*60*24*7*4*12*100*20, 60*60*24*7*4*12*100
    )
    seconds = datetime.utcnow().timestamp() - unix_timestamp
    if 0 <= seconds < 1:
        return 'Just now'
    if seconds < 0 :
        seconds = abs(seconds)
        token = 'from now'
        list_choice = 2
    else:
        token = 'ago'
        list_choice = 1

    for format in time_formats:
        if seconds < format[0]:
            if type(format[2]) == str:
                return format[list_choice]
            else:
                return f"{floor(seconds / format[2])} {format[1]} {token}"
    return time


# Flask pattern from https://flask.palletsprojects.com/en/1.1.x/patterns/sqlite3/
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database_mongo', None)
    if db is not None:
        db.close()

# Run the App
#=================
if __name__ == "__main__":
    if app.config["MONGO_INIT"]:
        init_mongo_db()

    app.run(
        host  = app.config["FLASK_IP"],
        port  = app.config["FLASK_PORT"],
        debug = app.config["FLASK_DEBUG"])
