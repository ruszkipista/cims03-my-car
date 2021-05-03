# ToDos
A Flask and MongoDB-Atlas based CRUD demo application, styled with Material Design Bootstrap. Inspired by the code along mini project by the same name in the Code Institute curriculum.
You can initialize the MongoDB collection by setting environment variable `MONGO_INIT` to `True`

### How To Run the application
1. Install `virtualenv`:
```
$ pip install virtualenv
```
2. Open a terminal in the project root directory and run:
```
$ virtualenv env
```
3. Then run the command:
```
$ .\env\Scripts\activate
```
4. Then install the dependencies:
```
$ (env) pip install -r requirements.txt
```
5. Finally start the web server:
```
$ (env) python app.py
```

The application is deployed on [Heroku](https://task-master-ruszkipista.herokuapp.com/)