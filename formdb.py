import os
# Support for mongodb+srv:// URIs requires dnspython:
#!pip install dnspython pymongo
import pymongo
import json
import time
from datetime import date, datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import certifi
from flask import g, session
from bson.objectid import ObjectId
from bson.binary import Binary

# envDB.py should exist only in Development
if os.path.exists("envDB.py"):
    import envDB

# MongoDB parameters
dbConfig = {}

dbConfig["OS_DATA_PATH"] = os.environ.get("OS_DATA_PATH","./static/data/")
dbConfig["UPLOAD_EXTENSIONS"] = set(['png', 'jpg', 'jpeg', 'gif'])

dbConfig["MONGO_CLUSTER"] = os.environ.get("MONGO_CLUSTER")
dbConfig["MONGO_DB_NAME"] = os.environ.get("MONGO_DB_NAME")
dbConfig["MONGO_URI"] = f"mongodb+srv:" + \
                          f"//{os.environ.get('MONGO_DB_USER')}" + \
                          f":{os.environ.get('MONGO_DB_PASS')}" + \
                          f"@{dbConfig['MONGO_CLUSTER']}" + \
                          f".ueffo.mongodb.net" + \
                          f"/{dbConfig['MONGO_DB_NAME']}" + \
                          f"?retryWrites=true&w=majority"

dbConfig["MONGO_BASE"] = os.environ.get("MONGO_BASE","db_base.json")
dbConfig["MONGO_DEMO"] = os.environ.get("MONGO_DEMO","db_demo.json")
dbConfig["MONGO_INIT"] = os.environ.get("MONGO_INIT",   "False").lower() in {'1','true','t','yes','y'}# => Heroku Congig Vars
dbConfig["MONGO_IMAGES"]            = 'images'
dbConfig["MONGO_USERS"]             = 'users'
dbConfig["MONGO_CARS"]              = 'cars'
dbConfig["MONGO_USERS_CARS"]        = 'users_cars'
dbConfig["MONGO_FIELDCATALOG"]      = 'fieldcatalog'
dbConfig["MONGO_CURRENCIES"]        = 'currencies'
dbConfig["MONGO_COUNTRIES"]         = 'countries'
dbConfig["MONGO_MEASURE_TYPES"]     = 'measure_types'
dbConfig["MONGO_UNIT_OF_MEASURES"]  = 'unit_of_measures'
dbConfig["MONGO_UNIT_CONVERSIONS"]  = 'unit_conversions'
dbConfig["MONGO_EXPENDITURE_TYPES"] = 'expenditure_types'
dbConfig["MONGO_MATERIAL_TYPES"]    = 'material_types'
dbConfig["MONGO_RELATIONSHIP_TYPES"]= 'relationship_types'
dbConfig["MONGO_MATERIALS"]         = 'materials'


class Result:
    def __init__(self, record={}, messages=[]):
        self.record = record
        self.messages = messages


# inspired by https://stackoverflow.com/questions/4830535/how-do-i-format-a-date-in-jinja2
from math import floor
def translate_unix_timestamp_to_time_ago_text(unix_timestamp:int):
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
    seconds = get_utc_timestamp() - unix_timestamp
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


def is_password_hash_correct(pwhash,password:str):
    return check_password_hash(pwhash,password)


def get_utc_timestamp():
    return datetime.utcnow().timestamp()

    
def get_form_reglog_field_username(request):
    return request.form.get('username', None)


def get_form_reglog_field_password(request):
    return request.form.get('password', None)


def get_form_reglog_field_is_admin(request):
    return request.form.get('user_is_admin', None)


def get_form_profile_field_password_old(request):
    return request.form.get('password_old', None)


def get_form_profile_field_password_new(request):
    return request.form.get('password_new', None)


def create_form_data_attributes(coll_fieldcat:dict, record:dict, filter_postfix:str):
    attributes = ""
    if coll_fieldcat.get('filter', None):
        for field in coll_fieldcat['fields']:
            if field['name'] in coll_fieldcat['filter']:
                attributes += "data-" + field['name'] + "_" + filter_postfix \
                            + "=" + str(record[field['name']])
    return attributes


# MongoDB
#=========
def get_db_coll_name_cars():
    return dbConfig["MONGO_CARS"]


def get_db_collection(collection):
    conn = getattr(g, '_database_mongo', None)
    if conn is None:
        try:
            conn = g._database_mongo = pymongo.MongoClient(dbConfig["MONGO_URI"], tlsCAFile=certifi.where())
        except pymongo.errors.ConnectionFailure as e:
            print(f"Could not connect to MongoDB {dbConfig['MONGO_DB_NAME']}: {e}")
            return None
    return conn[dbConfig["MONGO_DB_NAME"]][collection]


def close_db_connection(exception):
    db = getattr(g, '_database_mongo', None)
    if db is not None:
        db.close()


def insert_db_user(username, password, is_admin=False):
    user_new = {
        "username": username,
        "password": generate_password_hash(password),
        "date_time_insert": get_utc_timestamp()
    }
    if is_admin:
        user_new["user_is_admin"] = True
 
    loggedin_user = get_db_user_id()
    if loggedin_user:
        user_new["changed_by"] = loggedin_user
    return insert_db_record(dbConfig["MONGO_USERS"], user_new)


def get_db_user_by_name(username):
    coll = get_db_collection(dbConfig["MONGO_USERS"])
    user = coll.find_one({"username": username.lower()}, {"password": 1, 'user_is_admin':1})
    return user


def get_db_user_by_id(user_id):
    return get_db_record_by_id(dbConfig["MONGO_USERS"], user_id)


def get_db_user_id(user=None):
    if user:
        return user.get('_id', None)
    user_id = session.get('user_id', None)
    if user_id:
        return ObjectId(user_id)
    else:
        return user_id


def get_db_user_password(record):
    return record.get('password', None)


def get_db_user_is_admin(user=None):
    if user:
        return user.get('user_is_admin', False)
    else:
        return session.get('user_is_admin', False)


def login_db_user(user):
    loggedin_user_id = get_db_user_id(user)
    session['user_id'] = str(loggedin_user_id)
    session['user_is_admin'] = get_db_user_is_admin(user)
    car_ids = get_db_car_ids_for_loggedin_user()
    session['car_id'] = [ str(id) for id in car_ids]


def logout_db_user():
        session.pop('user_id', None)
        session.pop('user_is_admin', None)
        session.pop('car_id', None)


def set_db_user_password(user_id, password_new):
    user_update = {
        "password":         generate_password_hash(password_new),
        "changed_by":       ObjectId(session['user_id']),
        "date_time_update": get_utc_timestamp()
    }
    coll = get_db_collection(dbConfig["MONGO_USERS"])
    result = coll.update_one({'_id':user_id}, {"$set":user_update})
    return result.modified_count == 1


def get_db_image_by_id(image_id):
    return get_db_record_by_id(dbConfig["MONGO_IMAGES"], image_id)


def insert_db_image(filename, image_binary):
    record_new = { 
        'source': filename, 
        'image':  image_binary
    }
    record_new = insert_db_record(dbConfig["MONGO_IMAGES"], record_new)
    return record_new['_id']


def update_db_image(filename, image_binary, record_new):
    record_new['source'] = filename
    record_new['image']  = image_binary
    return record_new


def get_db_cars_for_user():
    car_ids = get_db_car_ids_for_loggedin_user()
    cars = get_db_all_records(dbConfig["MONGO_CARS"])
    cars_filtered = [ car for car in cars if car['_id'] in car_ids]
    return cars_filtered


def get_db_car_ids_for_loggedin_user():
    if get_db_user_is_admin():
        cars = get_db_all_records(dbConfig["MONGO_CARS"])
        return [rec['_id'] for rec in cars]
    else:
        loggedin_user_id = get_db_user_id()
        users_cars = get_db_all_records(dbConfig["MONGO_USERS_CARS"])
        return [rec['car_id'] for rec in users_cars if rec['user_id']==loggedin_user_id]


def get_db_entity_select_field(entity_id, collection_name):
    fieldcatalog = get_db_fieldcatalog(collection_name)
    select_field_name = fieldcatalog['select_field']
    coll = get_db_collection(collection_name)
    try:
        entity_old = coll.find_one({'_id': entity_id}, {select_field_name: 1})
        if entity_old:
            return entity_old[select_field_name]
    except:
        pass
    return ""


def get_db_all_records(collection_name):
    coll = get_db_collection(collection_name)
    coll_fieldcatalog = get_db_fieldcatalog(collection_name)
    filter_field_names = coll_fieldcatalog.get('filter', [])
    if 'car_id' in filter_field_names:
        car_ids = get_db_car_ids_for_loggedin_user()
        coll_records = coll.find({'car_id':{"$in":car_ids}})
    else:
        coll_records = coll.find()
    sorting = coll_fieldcatalog.get('sort', None)
    if sorting:
        coll_records = coll_records.sort(list(sorting.items()))
    return list(coll_records)


def get_db_records(collection_name):
    if not getattr(g, "_collections", None):
        g._collections = {}
    records = getattr(g._collections, collection_name, None)
    if records is None:
        coll = get_db_collection(collection_name)
        if coll:
            if collection_name==dbConfig["MONGO_FIELDCATALOG"]:
                records = g._collections[collection_name] = {doc["collection_name"]:doc for doc in coll.find()}
            else:
                records = g._collections[collection_name] = { c['_id']:c for c in coll.find()}
    return records


def get_db_select_field_lookup(collection_name):
    if not getattr(g, "_lookups", None):
        g._lookups = {}
    records = getattr(g._lookups, collection_name, None)
    if records is None:
        coll = get_db_collection(collection_name)
        if coll:
            fieldcatalog = get_db_fieldcatalog(collection_name)
            select_field = fieldcatalog.get('select_field', None)
            if select_field:
                records = g._lookups[collection_name] = { c[select_field]:c['_id'] for c in coll.find()}
            else:
                records = g._lookups[collection_name] = {}
    return records


def get_db_entity_name(collection_name):
    coll_fieldcatalog = get_db_fieldcatalog(collection_name)
    return coll_fieldcatalog["entity_name"]


def get_db_fieldcatalog(collection_name=None):
    fieldcatalog = get_db_records(dbConfig["MONGO_FIELDCATALOG"])
    if collection_name:
        return fieldcatalog[collection_name]
    else:
        return fieldcatalog


def get_db_buffered_collections():
    coll_fieldcatalogs = get_db_fieldcatalog()
    return [ coll for coll,fcat in coll_fieldcatalogs.items() if fcat.get('buffered', None)]


def get_db_record_by_id(collection_name, record_id):
    coll = get_db_collection(collection_name)
    return coll.find_one({"_id":ObjectId(record_id)})


def get_db_field_type_lookup_triples(collection_name, field_names):
    triples = []
    coll_fields = get_db_fieldcatalog(collection_name)['fields']
    for field_name in field_names:
        field_def = next((f for f in coll_fields if f['name']==field_name), '')
        input_type = field_def.get('input_type', None)
        lookup_collection_name = field_def.get('values', None)
        triples.append((field_name,input_type,lookup_collection_name))
    return triples


def insert_db_record(collection_name, record):
    coll = get_db_collection(collection_name)
    record["_id"] = coll.insert_one(record).inserted_id
    return record


def update_db_record(collection_name, record_old, record_new):
    coll = get_db_collection(collection_name)
    coll.update_one({"_id":record_old["_id"]}, {"$set":record_new})


def delete_db_record(collection_name, record):
    coll = get_db_collection(collection_name)
    coll.delete_one({"_id":record["_id"]})


def get_db_is_admin_maintainable(collection_name):
    coll_fieldcatalog = get_db_fieldcatalog(collection_name)
    return coll_fieldcatalog.get('admin', None)


def insert_db_many_records(collection_name, records):
    coll = get_db_collection(collection_name)
    coll.insert_many(records)


def delete_db_all_records(collection_name):
    coll = get_db_collection(collection_name)
    coll.delete_many({})


def translate_db_external_to_internal(source_field_name, input_type, lookup_collection_name, record):
    external_value = record.get(source_field_name, None)
    internal_value = None

    if input_type == "ObjectId":
        internal_value = ObjectId(external_value)

    elif input_type == "changedby":
        internal_value = get_db_user_id()

    elif input_type == 'imageid':
        filename = record[source_field_name]
        if filename:
            with open(os.path.join(dbConfig["OS_DATA_PATH"], filename), mode='rb') as image_file:
                # read file into memory
                image_binary = Binary(image_file.read())
                # insert image into DB, get new ID
                internal_value = insert_db_image(filename, image_binary)

    elif input_type == 'password':
        if external_value and len(external_value)>0:
            internal_value = generate_password_hash(external_value)
        else:
            record.pop(source_field_name)

    elif input_type == 'date':
        if external_value == '' or external_value is None:
            del record[source_field_name]
        else:
            # convert isodatestring YYYY-MM-DD into datetime object
            internal_value = datetime.fromisoformat(external_value)

    elif input_type == 'timestamp_update':
        internal_value = get_utc_timestamp()

    elif input_type == 'timestamp_insert':
        internal_value = get_utc_timestamp()

    else:
        lookup = get_db_select_field_lookup(lookup_collection_name)
        internal_value = lookup.get(external_value, None)

    if internal_value:
        record[source_field_name] = internal_value


def init_db_mongo(file_name, clear_content=False):
    # initialize collections on DB from JSON file
    with open(file_name, mode='r', encoding="utf-8") as f:
        collections = json.loads(f.read())

        if clear_content:
            fieldcatalog = []
            for coll_name,coll_docs in collections.items():
                # filter fieldcatalog records
                for doc in coll_docs:
                    if doc.get("entity_name", False):
                        doc["collection_name"] = coll_name
                        fieldcatalog.append(doc)
            # write out Fieldcatalog
            coll_fieldcatalog = get_db_collection(dbConfig["MONGO_FIELDCATALOG"])
            if fieldcatalog:
                coll_fieldcatalog.delete_many({})
                coll_fieldcatalog.insert_many(fieldcatalog)

        for coll_name,coll_docs in collections.items():
            if clear_content:
                delete_db_all_records(coll_name)
            # filter data records
            coll_records = []
            for doc in coll_docs:
                if not doc.get("entity_name", False):
                    coll_records.append(doc)

            if coll_name=="users":
                coll_records = init_db_users(coll_name, coll_records)
            elif coll_name=="currency_conversions":
                coll_records = init_db_currency_conversions(coll_name, coll_records)
            elif coll_name=="countries":
                coll_records = init_db_countries(coll_name, coll_records)
            elif coll_name=="unit_of_measures":
                coll_records = init_db_unit_of_measures(coll_name, coll_records)
            elif coll_name=="unit_conversions":
                coll_records = init_db_unit_conversions(coll_name, coll_records)
            elif coll_name=="material_types":
                coll_records = init_db_material_types(coll_name, coll_records)
            elif coll_name=="materials":
                coll_records = init_db_materials(coll_name, coll_records)
            elif coll_name=="cars":
                coll_records = init_db_cars(coll_name, coll_records)
            elif coll_name=="users_cars":
                coll_records = init_db_users_cars(coll_name, coll_records)
            elif coll_name=="partners":
                coll_records = init_db_partners(coll_name, coll_records)
            elif coll_name=="transactions":
                coll_records = init_db_transactions(coll_name, coll_records)

            if coll_records:
                insert_db_many_records(coll_name, coll_records)

        if clear_content:
            # create index for unique field(s)
            for coll_def in fieldcatalog:
                unique_fields = [ (field["name"], pymongo.ASCENDING) 
                                    for field in coll_def["fields"] if field.get("unique", False)]
                if unique_fields:
                    coll = get_db_collection(coll_def["collection_name"])
                    coll.create_index(unique_fields, unique=True)


def init_db_users(collection_name, records):
    field_names = ['password','date_time_insert']
    field_type_lookup_triples = get_db_field_type_lookup_triples(collection_name, field_names)
    for record in records:
        # encrypt password
        # set timestamp of creation
        record['date_time_insert'] = get_utc_timestamp()
        for field, type, lookup in field_type_lookup_triples:
            translate_db_external_to_internal(field, type, lookup, record)
    return records


def init_db_currency_conversions(collection_name, records):
    field_names = ['currency_id_from','currency_id_to','from_date']
    field_type_lookup_triples = get_db_field_type_lookup_triples(collection_name, field_names)
    for record in records:
        # convert From Date isodatestring to datetime
        # convert Currency ID to _id
        for field, type, lookup in field_type_lookup_triples:
            translate_db_external_to_internal(field, type, lookup, record)
    return records


def init_db_countries(collection_name, records):
    field_names = ['currency_id', 'distance_unit_id', 'fuel_unit_id']
    field_type_lookup_triples = get_db_field_type_lookup_triples(collection_name, field_names)
    for record in records:
        # convert Currency ID, Distance Unit, Fuel Unit to _id
        for field, type, lookup in field_type_lookup_triples:
            translate_db_external_to_internal(field, type, lookup, record)
    return records


def init_db_unit_of_measures(collection_name, records):
    field_names = ['measure_type_id']
    field_type_lookup_triples = get_db_field_type_lookup_triples(collection_name, field_names)
    for record in records:
        # convert Measure Type ID to _id
        for field, type, lookup in field_type_lookup_triples:
            translate_db_external_to_internal(field, type, lookup, record)
    return records


def init_db_unit_conversions(collection_name, records):
    field_names = ['uom_id_from','uom_id_to']
    field_type_lookup_triples = get_db_field_type_lookup_triples(collection_name, field_names)
    for record in records:
        # convert Unit of Measure ID to _id
        for field, type, lookup in field_type_lookup_triples:
            translate_db_external_to_internal(field, type, lookup, record)
    return records


def init_db_material_types(collection_name, records):
    field_names = ['measure_type_id','expenditure_type_id']
    field_type_lookup_triples = get_db_field_type_lookup_triples(collection_name, field_names)
    for record in records:
        # convert Measure Type ID and Expenditure Type ID to _id
        for field, type, lookup in field_type_lookup_triples:
            translate_db_external_to_internal(field, type, lookup, record)
    return records


def init_db_materials(collection_name, records):
    field_names = ['material_type_id']
    field_type_lookup_triples = get_db_field_type_lookup_triples(collection_name, field_names)
    for record in records:
        # convert Material Type ID to _id
        for field, type, lookup in field_type_lookup_triples:
            translate_db_external_to_internal(field, type, lookup, record)
    return records

def init_db_cars(collection_name, records):
    field_names = ['reg_country_id', 'odometer_unit_id', 'fuel_material_id',
                   'fuel_economy_unit_id', 'car_image_id']
    field_type_lookup_triples = get_db_field_type_lookup_triples(collection_name, field_names)
    for record in records:
        # convert Registration Country, Odometer Unit, Fuel Material ID,
        # Fuel Economy Unit, Car Image FileName to _id
        for field, type, lookup in field_type_lookup_triples:
            translate_db_external_to_internal(field, type, lookup, record)
    return records


def init_db_users_cars(collection_name, records):
    field_names = ['user_id', 'car_id', 'relationship_id']
    field_type_lookup_triples = get_db_field_type_lookup_triples(collection_name, field_names)
    for record in records:
        # convert User Name, Car ID, Relationship ID to _id
        for field, type, lookup in field_type_lookup_triples:
            translate_db_external_to_internal(field, type, lookup, record)
    return records


def init_db_partners(collection_name, records):
    field_names = ['country_id']
    field_type_lookup_triples = get_db_field_type_lookup_triples(collection_name, field_names)
    for record in records:
        # convert Country ID to _id
        for field, type, lookup in field_type_lookup_triples:
            translate_db_external_to_internal(field, type, lookup, record)
    return records


def init_db_transactions(collection_name, records):
    field_names = ['car_id', 'transaction_date', 'partner_id', 'material_id', 'uom_id', 'currency_id']
    field_type_lookup_triples = get_db_field_type_lookup_triples(collection_name, field_names)
    for record in records:
        # convert From Date isodatestring to datetime
        # convert entity key fields into _id
        for field, type, lookup in field_type_lookup_triples:
            translate_db_external_to_internal(field, type, lookup, record)
    return records


def save_record_to_db(request, collection_name, record_old={}):
    messages = []
    coll_fieldcatalog = get_db_fieldcatalog(collection_name)
    fields = [field['name'] for field in coll_fieldcatalog['fields']]
    record_new = {f:request.form.get(f) for f in fields 
                    if request.form.get(f,None) is not None and \
                       request.form.get(f) != record_old.get(f,None)}
    
    images_old = []
    for field in coll_fieldcatalog['fields']:
        field_name = field['name']
        field_values = field.get('values', None)
        field_input_type = field.get('input_type', None)
        if not field_input_type:
            continue

        # store logged in user as last updater
        # store foreign key from lookup of text value
        # store password
        if field_input_type in {'changedby', 'lookup', 'password'}:
            translate_db_external_to_internal(field_name, field_input_type, field_values, record_new)

        # store timestamp
        elif field_input_type=='timestamp_update' and record_old:
            translate_db_external_to_internal(field_name, field_input_type, field_values, record_new)
        elif field_input_type=='timestamp_insert' and not record_old:
            translate_db_external_to_internal(field_name, field_input_type, field_values, record_new)

        # convert date value to datetime object
        elif field_input_type=='date':
            record_new[field_name] = request.form.get(field_name, None)
            translate_db_external_to_internal(field_name, field_input_type, field_values, record_new)

        # store foreign key from select-option
        elif field_input_type=='select':
            # get foreign key of selected value
            if record_new.get(field_name, None):
                # insert foreign key as object into field
                record_new[field_name] = ObjectId(record_new[field_name])

        # store check box as boolean
        elif field_input_type=='checkbox':
            record_new[field_name] = True if record_new.get(field_name, 'off')=='on' else False

        # store image and save new Image ID
        elif field_input_type=='imageid' or field_input_type=='image':
            # following instructions from https://flask.palletsprojects.com/en/1.1.x/patterns/fileuploads/
            image = request.files[field_name]
            if image:
                filename_source = secure_filename(image.filename)
                extension = filename_source.rsplit('.', 1)[1] if '.' in filename_source else ''
                if extension in dbConfig["UPLOAD_EXTENSIONS"]:
                    # store image
                    if field_input_type=='imageid':
                        image_id_new = insert_db_image(filename_source, Binary(image.read()))
                        record_new[field_name] = image_id_new
                        if record_old.get(field_name, False):
                            images_old.append(record_old[field_name])
                    else:
                        record_new = update_db_image(filename_source, Binary(image.read()), record_new)

    if not record_new:
        messages.append((f"Did not {'update' if record_old else 'add'} record", "error"))
    else:
        if record_old:
            try:
                update_db_record(collection_name, record_old, record_new)
                messages.append((f"Successfully updated one {get_db_entity_name(collection_name)} record", "success"))
                # delete old images if new got uploaded
                coll_images = get_db_collection(dbConfig["MONGO_IMAGES"])
                for image_old in images_old:
                    coll_images.delete_one({"_id":image_old})
                record_new = {}
            except:
                messages.append((f"Error in update operation!", "danger"))
        else:
            try:
                record_new = insert_db_record(collection_name, record_new)
                # create empty record - this clears the input fields, because the update was OK
                record_new = {}
                messages.append((f"Successfully added one {get_db_entity_name(collection_name)} record", "success"))
            except:
                messages.append((f"Error in addition operation!", "danger"))

    return Result(record_new, messages)


def filter_db_records(records:dict, field_details:dict):
    filter = field_details.get('filter', None)
    recs_copy = records.copy()
    if filter:
        for filter_field_name, filter_values in filter.items():
            if filter_values=='SESSION':
                # in SESSION filter values are _id's, stored in string form
                id_strings = session.get(filter_field_name, [])
                # replace string form of _id's with ObjectID form
                filter[filter_field_name] = [ObjectId(id) for id in id_strings]
                for _id in records:
                    for filter_field_name, filter_values in filter.items():
                        if _id not in filter_values:
                            del recs_copy[_id]
            else:
                lookup1_fieldcat = get_db_fieldcatalog(field_details['values'])
                lookup1_fields = lookup1_fieldcat['fields']
                field_def = next((f for f in lookup1_fields if f['name']==filter_field_name), '')
                lookup2_table_name = field_def.get('values', None)
                lookup2_fieldcat = get_db_fieldcatalog(lookup2_table_name)
                select_field = lookup2_fieldcat['select_field']
                lookup2_records = get_db_records(lookup2_table_name)
                lookup2 = {rec[select_field]:key for key,rec in lookup2_records.items()}
                for i in range(len(filter_values)):
                    filter_values[i] = lookup2[filter_values[i]]
                for _id in records:
                    for filter_field_name, filter_values in filter.items():
                        field_value = records[_id].get(filter_field_name, None)
                        if not field_value or field_value not in filter_values:
                            del recs_copy[_id]
    return recs_copy


def init_db():
    if dbConfig["MONGO_INIT"]:
        init_db_mongo(os.path.join(dbConfig["OS_DATA_PATH"], dbConfig["MONGO_BASE"]), True)
        init_db_mongo(os.path.join(dbConfig["OS_DATA_PATH"], dbConfig["MONGO_DEMO"]), False)
        